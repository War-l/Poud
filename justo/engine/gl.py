"""Tubería de render en OpenGL (llvmpipe: shaders ejecutados por la CPU, sin GPU física).

Orden por fotograma:
  cielo (dispersión atmosférica) -> planos de atrás hacia delante (luz aditiva, niebla,
  profundidad de campo, desenfoque de movimiento) intercalados con partículas (mezcla
  aditiva) -> rayos volumétricos -> bloom -> lente + ACES + gradación + grano -> 8 bits.
"""
import math

import moderngl
import numpy as np

from . import shaders as S


class SafeProgram:
    """Envoltorio que ignora uniforms que el compilador GLSL haya eliminado."""

    def __init__(self, prog):
        self.prog = prog

    def __setitem__(self, k, v):
        if k in self.prog:
            self.prog[k].value = v

    def __contains__(self, k):
        return k in self.prog


class Tex:
    """Textura en luz lineal premultiplicada (float16) con mipmaps."""

    def __init__(self, gltex, size):
        self.tex, self.size = gltex, size


class Plane:
    def __init__(self, axis, value, ext, albedo, emit=None, flat=0.0, rim=0.0, self_lit=0.0, emit_gain=1.0,
                 name=""):
        self.axis, self.value, self.ext = axis, value, ext
        self.albedo, self.emit = albedo, emit
        self.flat, self.rim, self.self_lit, self.emit_gain = flat, rim, self_lit, emit_gain
        self.name = name


class Particles:
    def __init__(self, eng, n, box_min, box_max, seed=1, drift=(0, 0, 0), turb=0.05, size_m=0.0015,
                 color=(1, 1, 1), gain=1.0, beam=None, bright_pow=3.0):
        rng = np.random.default_rng(seed)
        bmin, bmax = np.array(box_min, "f4"), np.array(box_max, "f4")
        p = np.empty((n, 4), "f4")
        p[:, :3] = rng.uniform(bmin, bmax, (n, 3))
        p[:, 3] = rng.random(n)
        v = np.empty((n, 4), "f4")
        v[:, :3] = np.array(drift, "f4") * rng.uniform(0.5, 1.5, (n, 1)) + rng.normal(0, 0.01, (n, 3))
        v[:, 3] = rng.random(n) ** bright_pow  # pocas motas muy brillantes, muchas tenues
        self.n = n
        self.vbo = eng.ctx.buffer(np.hstack([p, v]).astype("f4").tobytes())
        self.vao = eng.ctx.vertex_array(eng.p_part_raw, [(self.vbo, "4f 4f", "in_p", "in_v")])
        self.box = (bmin, bmax)
        self.turb, self.size_m, self.color, self.gain, self.beam = turb, size_m, color, gain, beam


class Rain:
    def __init__(self, eng, n, box_min, box_max, vel=(0.6, -7.5, 0.0), color=(0.5, 0.55, 0.6), seed=3):
        rng = np.random.default_rng(seed)
        bmin, bmax = np.array(box_min, "f4"), np.array(box_max, "f4")
        p = rng.uniform(bmin, bmax, (n, 3)).astype("f4")
        s = rng.random((n, 1)).astype("f4")
        pts = np.hstack([p, s])
        verts = np.empty((n * 2, 5), "f4")
        verts[0::2, :4] = pts
        verts[1::2, :4] = pts
        verts[0::2, 4] = 0
        verts[1::2, 4] = 1
        self.vbo = eng.ctx.buffer(verts.tobytes())
        self.vao = eng.ctx.vertex_array(eng.p_rain_raw, [(self.vbo, "4f 1f", "in_p", "in_end")])
        self.box, self.vel, self.color = (bmin, bmax), np.array(vel, "f4"), color


class Engine:
    def __init__(self, W, H):
        self.W, self.H = W, H
        self.ctx = moderngl.create_standalone_context(backend="egl", require=430)
        ctx = self.ctx
        ctx.enable(moderngl.PROGRAM_POINT_SIZE)
        quad = ctx.buffer(np.array([-1, -1, 3, -1, -1, 3], "f4"))

        def prog(fs, vs=S.VS_FULL):
            p = ctx.program(vertex_shader=vs, fragment_shader=fs)
            return SafeProgram(p), ctx.vertex_array(p, [(quad, "2f", "in_pos")])

        self.p_sky, self.v_sky = prog(S.FS_SKY)
        self.p_plane, self.v_plane = prog(S.FS_PLANE)
        self.p_rays, self.v_rays = prog(S.FS_GODRAYS)
        self.p_down, self.v_down = prog(S.FS_DOWN)
        self.p_up, self.v_up = prog(S.FS_UP)
        self.p_final, self.v_final = prog(S.FS_FINAL)
        self.p_copy, self.v_copy = prog(S.FS_COPY)
        self.p_lin, self.v_lin = prog(S.FS_LINEARIZE)
        self.p_part_raw = ctx.program(vertex_shader=S.VS_PART, fragment_shader=S.FS_PART)
        self.p_rain_raw = ctx.program(vertex_shader=S.VS_RAIN, fragment_shader=S.FS_RAIN)
        self.p_part, self.p_rain = SafeProgram(self.p_part_raw), SafeProgram(self.p_rain_raw)

        def rt(w, h, comps=4, dtype="f2"):
            t = ctx.texture((w, h), comps, dtype=dtype)
            t.filter = (moderngl.LINEAR, moderngl.LINEAR)
            t.repeat_x = t.repeat_y = False
            return t, ctx.framebuffer([t])

        self.hdr, self.fbo_hdr = rt(W, H)
        self.sky_scale = 4
        self.sky, self.fbo_sky = rt(W // self.sky_scale, H // self.sky_scale)
        self.rays, self.fbo_rays = rt(W // 2, H // 2)
        self.half, self.fbo_half = rt(W // 2, H // 2)
        self.p_upc, self.v_upc = prog(S.FS_UPCOMP)
        self.p_vol, self.v_vol = prog(S.FS_VOLUME)
        self.down, self.up = [], []
        w, h = W, H
        for i in range(6):
            w, h = max(w // 2, 1), max(h // 2, 1)
            self.down.append(rt(w, h))
            self.up.append(rt(w, h))
        self.out, self.fbo_out = rt(W, H, 4, "f1")
        self.chars_tmp = ctx.texture((W, H), 4, dtype="f1")
        self.chars_tmp.filter = (moderngl.NEAREST, moderngl.NEAREST)
        self.overlay = ctx.texture((W, H), 4, dtype="f1")
        self.shadow = ctx.texture((W, H), 1, dtype="f1")
        self.shadow.filter = (moderngl.LINEAR_MIPMAP_LINEAR, moderngl.LINEAR)
        self.black = self.texture_from_cairo(np.zeros((4, 4, 4), np.uint8))
        self.char_pool = []

    # ------------------------------------------------------------- texturas
    def _linearize(self, src_tex, dst_fbo, size, weight=1.0, flip=True, additive=False):
        dst_fbo.use()
        self.ctx.viewport = (0, 0, size[0], size[1])
        if additive:
            self.ctx.enable(moderngl.BLEND)
            self.ctx.blend_func = moderngl.ONE, moderngl.ONE
        src_tex.use(0)
        self.p_lin["uSrc"] = 0
        self.p_lin["uSize"] = size
        self.p_lin["uWeight"] = weight
        self.p_lin["uFlip"] = 1.0 if flip else 0.0
        self.v_lin.render()
        self.ctx.disable(moderngl.BLEND)

    def texture_from_cairo(self, bgra):
        """bgra: array (h, w, 4) uint8 de Cairo -> Tex lineal float16 con mipmaps."""
        h, w = bgra.shape[:2]
        src = self.ctx.texture((w, h), 4, bgra.tobytes(), dtype="f1")
        src.filter = (moderngl.NEAREST, moderngl.NEAREST)
        dst = self.ctx.texture((w, h), 4, dtype="f2")
        fbo = self.ctx.framebuffer([dst])
        fbo.clear(0, 0, 0, 0)
        self._linearize(src, fbo, (w, h))
        dst.build_mipmaps()
        dst.filter = (moderngl.LINEAR_MIPMAP_LINEAR, moderngl.LINEAR)
        dst.anisotropy = 4.0
        dst.repeat_x = dst.repeat_y = False
        fbo.release()
        src.release()
        return Tex(dst, (w, h))

    def char_layer(self, idx, subframes):
        """Capa de personajes en espacio de pantalla, promedio de varios subfotogramas
        (desenfoque de movimiento real de brazos y piernas)."""
        while len(self.char_pool) <= idx:
            t = self.ctx.texture((self.W, self.H), 4, dtype="f2")
            t.filter = (moderngl.LINEAR_MIPMAP_LINEAR, moderngl.LINEAR)
            t.repeat_x = t.repeat_y = False
            self.char_pool.append((Tex(t, (self.W, self.H)), self.ctx.framebuffer([t])))
        tex, fbo = self.char_pool[idx]
        fbo.clear(0, 0, 0, 0)
        for sf in subframes:
            self.chars_tmp.write(sf)
            self._linearize(self.chars_tmp, fbo, (self.W, self.H), 1.0 / len(subframes), True, True)
        tex.tex.build_mipmaps()
        return tex

    # ------------------------------------------------------------- frame
    def _common(self, p, f):
        for k, v in (("uRes", (self.W, self.H)), ("uCam", tuple(f["cam"])), ("uF", f["f"]),
                     ("uShift", tuple(f.get("shift", (0, 0))))):
            if k in p:
                p[k] = v

    def render(self, f):
        ctx = self.ctx
        W, H = self.W, self.H
        env = f["env"]
        # --- cielo
        self.fbo_hdr.use()
        ctx.viewport = (0, 0, W, H)
        bg = env.get("clear", (0, 0, 0))
        self.fbo_hdr.clear(*bg, 0.0)
        if f.get("sky"):
            sk = f["sky"]
            self.fbo_sky.use()
            ctx.viewport = (0, 0, W // self.sky_scale, H // self.sky_scale)
            p = self.p_sky
            self._common(p, f)
            p["uSunDir"] = tuple(sk["sun_dir"])
            p["uHaze"] = sk.get("haze", 1.0)
            p["uSunDisk"] = sk.get("disk", 1.0)
            p["uSkyGain"] = sk.get("gain", 1.0)
            p["uScale"] = float(self.sky_scale)
            self.v_sky.render()
            self.fbo_hdr.use()
            ctx.viewport = (0, 0, W, H)
            self.sky.use(0)
            self.p_copy["uSrc"] = 0
            self.p_copy["uSize"] = (W, H)
            self.v_copy.render()

        # --- planos y partículas
        p = self.p_plane
        self._common(p, f)
        p["uTime"] = f["t"]
        p["uAmbTop"] = tuple(env["amb_top"])
        p["uAmbBot"] = tuple(env["amb_bot"])
        p["uSunCol"] = tuple(env.get("sun_col", (0, 0, 0)))
        p["uSunDir"] = tuple(env.get("sun_dir", (0, 1, 0)))
        lights = env.get("lights", [])[:6]
        p["uNL"] = len(lights)
        if lights:
            p["uLPos"] = [tuple(l[0]) + (l[1],) for l in lights] + [(0, 0, 0, 1)] * (6 - len(lights))
            p["uLCol"] = [tuple(l[2]) + (0,) for l in lights] + [(0, 0, 0, 0)] * (6 - len(lights))
        win = env.get("windows")
        if win:
            p["uWinAxis"], p["uWinValue"] = win["axis"], win["value"]
            rects = win["rects"][:6]
            p["uNW"] = len(rects)
            p["uWin"] = [tuple(r) for r in rects] + [(0, 0, 0, 0)] * (6 - len(rects))
            p["uBlinds"] = tuple(win.get("blinds", (0, 0, 0, 0)))
        else:
            p["uNW"] = 0
        p["uCanopy"] = tuple(env.get("canopy", (0, 0, 0, 0)))
        p["uSigma"] = tuple(env.get("sigma", (0, 0, 0)))
        p["uFogCol"] = tuple(env.get("fog", (0, 0, 0)))
        p["uFogSun"] = tuple(env.get("fog_sun", (0, 0, 0)))
        p["uCocK"] = f["coc_k"]
        p["uFocus"] = f["focus"]
        cv = f.get("cam_vel", (0, 0, 0))
        p["uVel"] = (-cv[0] * f["f"], -cv[1] * f["f"])
        p["uCamVel"] = tuple(cv)
        p["uMaxTaps"] = f.get("max_taps", 48)
        shadow = f.get("shadow")
        if shadow is not None:
            self.shadow.write(shadow.tobytes())
            self.shadow.build_mipmaps()
        p["uShadowSoft"] = env.get("shadow_soft", 2.5) + math.log2(W / 1280)
        p["uRimCol"] = tuple(env.get("rim_col", (0, 0, 0)))
        rd = env.get("rim_dir", (0, 0))
        p["uRimDir"] = (rd[0] * W / 2560, rd[1] * W / 2560)

        for item in f["items"]:
            kind = item[0]
            if kind in ("plane", "chars"):
                if kind == "plane":
                    pl, ov = item[1], item[2] if len(item) > 2 else {}
                    tex = pl.albedo
                    p["uScreenSpace"] = 0
                    p["uAxis"], p["uValue"] = pl.axis, pl.value
                    p["uExt"] = tuple(pl.ext)
                    p["uTexSize"] = tex.size
                    emit = pl.emit
                    flat, rim, selfl, eg = pl.flat, pl.rim, pl.self_lit, pl.emit_gain
                else:
                    tex, depth, ov = item[1], item[2], item[3] if len(item) > 3 else {}
                    p["uScreenSpace"] = 1
                    p["uAxis"], p["uValue"] = 2, depth
                    p["uExt"] = (0, 1, 0, 1)
                    p["uTexSize"] = tex.size
                    emit, flat, rim, selfl, eg = None, 1.0, ov.get("rim", 1.0), 0.0, 1.0
                infl = ov.get("inflate", getattr(pl, "inflate", None) if kind == "plane" else (14.0, 2.2, 0.45))
                if infl:
                    p["uInflate"] = (infl[0] * W / 2560, infl[1], infl[2])
                    flat = 0.0
                else:
                    p["uInflate"] = (0.0, 0.0, 0.0)
                p["uFlat"] = ov.get("flat", flat)
                p["uRim"] = ov.get("rim", rim)
                p["uSelfLit"] = ov.get("self_lit", selfl)
                p["uSunOn"] = ov.get("sun", 1.0)
                half = False
                if kind == "plane" and pl.axis == 2 and not ov.get("full"):
                    d = pl.value - f["cam"][2]
                    coc = f["coc_k"] * abs(1 - f["focus"] / max(d, 0.01))
                    half = coc > 7.0 * (W / 2560)
                elif kind == "chars":
                    d = depth - f["cam"][2]
                    half = f["coc_k"] * abs(1 - f["focus"] / max(d, 0.01)) > 9.0 * (W / 2560)
                p["uPxScale"] = 2.0 if half else 1.0
                p["uShadowOn"] = 1.0 if (ov.get("receive_shadow") and shadow is not None) else 0.0
                p["uEmitGain"] = ov.get("emit_gain", eg)
                p["uDetail"] = tuple(ov.get("detail", getattr(pl, "detail", (0, 1, 1)) if kind == "plane" else (0, 1, 1)))
                tex.tex.use(0)
                p["uTex"] = 0
                (emit or self.black).tex.use(1)
                p["uEmit"] = 1
                p["uHasEmit"] = 1.0 if emit else 0.0
                self.shadow.use(2)
                p["uShadow"] = 2
                if half:
                    self.fbo_half.use()
                    ctx.viewport = (0, 0, W // 2, H // 2)
                    self.fbo_half.clear(0, 0, 0, 0)
                    self.v_plane.render()
                    self.fbo_hdr.use()
                    ctx.viewport = (0, 0, W, H)
                    ctx.enable(moderngl.BLEND)
                    ctx.blend_func = moderngl.ONE, moderngl.ONE_MINUS_SRC_ALPHA
                    self.half.use(0)
                    self.p_upc["uSrc"] = 0
                    self.p_upc["uSize"] = (W, H)
                    self.v_upc.render()
                    ctx.disable(moderngl.BLEND)
                else:
                    ctx.enable(moderngl.BLEND)
                    ctx.blend_func = moderngl.ONE, moderngl.ONE_MINUS_SRC_ALPHA
                    self.v_plane.render()
                    ctx.disable(moderngl.BLEND)
            elif kind == "particles":
                ps = item[1]
                ov = item[2] if len(item) > 2 else {}
                q = self.p_part
                self._common(q, f)
                q["uTime"] = f["t"]
                q["uCocK"] = f["coc_k"]
                q["uFocus"] = f["focus"]
                q["uBoxMin"] = tuple(ps.box[0])
                q["uBoxMax"] = tuple(ps.box[1])
                q["uTurb"] = ps.turb
                q["uSizeM"] = ps.size_m
                q["uCol"] = tuple(ov.get("color", ps.color))
                q["uGain"] = ov.get("gain", ps.gain)
                q["uMaxPt"] = 40.0 * W / 2560
                q["uSigma"] = tuple(env.get("sigma", (0, 0, 0)))
                q["uSunDirP"] = tuple(env.get("sun_dir", (0, 1, 0)))
                win = env.get("windows")
                if win and getattr(ps, "win_mode", False):
                    q["uWinMode"] = 1.0
                    q["uWinAxis"], q["uWinValue"] = win["axis"], win["value"]
                    rects = win["rects"][:6]
                    q["uNW"] = len(rects)
                    q["uWin"] = [tuple(r) for r in rects] + [(0, 0, 0, 0)] * (6 - len(rects))
                    q["uBlinds"] = tuple(win.get("blinds", (0, 0, 0, 0)))
                else:
                    q["uWinMode"] = 0.0
                q["uPhase"] = (ps.phase, 1.0) if getattr(ps, "phase", None) else (0.0, 0.0)
                if ps.beam:
                    q["uBeamO"], q["uBeamD"], q["uBeamR"] = tuple(ps.beam[0]), tuple(ps.beam[1]), ps.beam[2]
                    q["uBeamOn"] = 1.0
                else:
                    q["uBeamOn"] = 0.0
                ctx.enable(moderngl.BLEND)
                ctx.blend_func = moderngl.ONE, moderngl.ONE
                ps.vao.render(moderngl.POINTS)
                ctx.disable(moderngl.BLEND)
            elif kind == "volume":
                vol = item[1]
                q = self.p_vol
                self._common(q, f)
                q["uTime"] = f["t"]
                q["uSunDir"] = tuple(env.get("sun_dir", (0, 1, 0)))
                q["uSunCol"] = tuple(env.get("sun_col", (0, 0, 0)))
                q["uSigmaS"], q["uSigmaT"], q["uG"] = vol["sigma_s"], vol.get("sigma_t", vol["sigma_s"]), vol.get("g", 0.55)
                win = env.get("windows")
                if win:
                    q["uWinAxis"], q["uWinValue"] = win["axis"], win["value"]
                    rects = win["rects"][:6]
                    q["uNW"] = len(rects)
                    q["uWin"] = [tuple(r) for r in rects] + [(0, 0, 0, 0)] * (6 - len(rects))
                    q["uBlinds"] = tuple(win.get("blinds", (0, 0, 0, 0)))
                else:
                    q["uNW"] = 0
                q["uNL"] = len(lights)
                if lights:
                    q["uLPos"] = [tuple(l[0]) + (l[1],) for l in lights] + [(0, 0, 0, 1)] * (6 - len(lights))
                    q["uLCol"] = [tuple(l[2]) + (0,) for l in lights] + [(0, 0, 0, 0)] * (6 - len(lights))
                q["uLightK"] = vol.get("light_k", 1.0)
                q["uBoxMin"], q["uBoxMax"] = tuple(vol["box"][0]), tuple(vol["box"][1])
                q["uZRange"] = tuple(item[2])
                q["uSteps"] = vol.get("steps", 28)
                q["uNoise"] = vol.get("noise", 0.5)
                self.fbo_half.use()
                ctx.viewport = (0, 0, W // 2, H // 2)
                self.fbo_half.clear(0, 0, 0, 0)
                self.v_vol.render()
                self.fbo_hdr.use()
                ctx.viewport = (0, 0, W, H)
                ctx.enable(moderngl.BLEND)
                ctx.blend_func = moderngl.ONE, moderngl.ONE
                self.half.use(0)
                self.p_upc["uSrc"] = 0
                self.p_upc["uSize"] = (W, H)
                self.v_upc.render()
                ctx.disable(moderngl.BLEND)
            elif kind == "rain":
                rn = item[1]
                ov = item[2] if len(item) > 2 else {}
                q = self.p_rain
                self._common(q, f)
                q["uTime"] = f["t"]
                q["uBoxMin"], q["uBoxMax"] = tuple(rn.box[0]), tuple(rn.box[1])
                q["uVelR"] = tuple(rn.vel)
                q["uShutter"] = f.get("shutter", 1 / 48)
                q["uCocK"], q["uFocus"] = f["coc_k"], f["focus"]
                q["uCol"] = tuple(ov.get("color", rn.color))
                ctx.enable(moderngl.BLEND)
                ctx.blend_func = moderngl.ONE, moderngl.ONE
                rn.vao.render(moderngl.LINES)
                ctx.disable(moderngl.BLEND)

        post = f["post"]
        # --- rayos volumétricos
        rays = post.get("rays")
        self.fbo_rays.use()
        ctx.viewport = (0, 0, W // 2, H // 2)
        self.fbo_rays.clear(0, 0, 0, 1)
        if rays:
            # fuente a media resolución (filtro 2x2) para la dispersión en espacio de pantalla
            self.fbo_half.use()
            self.hdr.use(0)
            self.p_upc["uSrc"] = 0
            self.p_upc["uSize"] = (W // 2, H // 2)
            self.v_upc.render()
            self.fbo_rays.use()
            q = self.p_rays
            self.half.use(0)
            q["uSrc"] = 0
            q["uLight"] = tuple(rays["pos"])
            q["uSize"] = (W // 2, H // 2)
            q["uThresh"] = rays.get("thresh", 1.0)
            q["uDecay"] = rays.get("decay", 0.965)
            q["uDensity"] = rays.get("density", 0.9)
            q["uWeight"] = rays.get("weight", 1.0)
            q["uTime"] = f["t"]
            self.v_rays.render()
        # --- bloom
        src = self.hdr
        for i, (t, fb) in enumerate(self.down):
            fb.use()
            ctx.viewport = (0, 0, t.width, t.height)
            src.use(0)
            q = self.p_down
            q["uSrc"] = 0
            q["uTexel"] = (1.0 / src.width, 1.0 / src.height)
            q["uFirst"] = 1 if i == 0 else 0
            q["uThresh"] = post.get("bloom_thresh", 1.5)
            self.v_down.render()
            src = t
        prev = self.down[-1][0]
        for i in range(len(self.down) - 2, -1, -1):
            t, fb = self.up[i]
            fb.use()
            ctx.viewport = (0, 0, t.width, t.height)
            prev.use(0)
            self.down[i][0].use(1)
            q = self.p_up
            q["uSrc"], q["uBase"] = 0, 1
            q["uTexel"] = (1.0 / prev.width, 1.0 / prev.height)
            q["uRadius"] = 1.0
            q["uDst"] = (t.width, t.height)
            self.v_up.render()
            prev = t
        # --- final
        ov = f.get("overlay")
        if ov is not None:
            self.overlay.write(ov)
        else:
            self.overlay.write(bytes(W * H * 4))
        self.fbo_out.use()
        ctx.viewport = (0, 0, W, H)
        q = self.p_final
        self.hdr.use(0)
        self.up[0][0].use(1)
        self.rays.use(2)
        self.overlay.use(3)
        q["uHDR"], q["uBloom"], q["uRays"], q["uOverlay"] = 0, 1, 2, 3
        q["uRes"] = (W, H)
        q["uExposure"] = post.get("exposure", 1.0)
        q["uBloomK"] = post.get("bloom", 0.04)
        q["uRaysK"] = 1.0 if rays else 0.0
        q["uWB"] = tuple(post.get("wb", (1, 1, 1)))
        q["uSat"] = post.get("sat", 1.0)
        q["uContrast"] = post.get("contrast", 1.0)
        q["uLift"] = tuple(post.get("lift", (0, 0, 0)))
        q["uGain"] = tuple(post.get("gain", (1, 1, 1)))
        q["uShadowTint"] = tuple(post.get("shadow_tint", (0, 0, 0)))
        q["uHighTint"] = tuple(post.get("high_tint", (0, 0, 0)))
        q["uVignette"] = post.get("vignette", 0.25)
        q["uCA"] = post.get("ca", 0.004)
        q["uGrain"] = post.get("grain", 0.02)
        q["uTime"] = f["t"]
        q["uFade"] = post.get("fade", 1.0)
        q["uFlash"] = post.get("flash", 0.0)
        self.v_final.render()
        return self.fbo_out.read(components=3, alignment=1)
