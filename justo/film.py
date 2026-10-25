"""Coreografía de «El hombre que quería ser justo»: escenas, planos, actores y objetos."""
import json
import math
from pathlib import Path

import numpy as np
import soundfile as sf

from engine import physics as ph
from engine.characters import CAST, citizen
from engine.director import Lens, Actor, Prop
from engine.paint import setc, ellipse, poly, smooth_path, rrect, shade
from engine.physics import Track, smoothstep, fbm1
from guion import SCENES, TITLE_DUR, build_timeline

ROOT = Path(__file__).resolve().parent
ENV_HZ = 100


# ------------------------------------------------------------------ utilidades de animación
def load_timeline():
    meta = json.loads((ROOT / "build" / "voz" / "lines.json").read_text())
    durs = {(m["scene"], m["idx"]): m["dur"] for m in meta}
    files = {(m["scene"], m["idx"]): m["file"] for m in meta}
    tl, total = build_timeline(durs)
    envs = {}
    for sc in tl:
        for ln in sc["lines"]:
            data, sr = sf.read(files[(sc["id"], ln["idx"])])
            hop = sr // ENV_HZ
            n = max(1, len(data) // hop)
            rms = np.sqrt(np.mean(data[: n * hop].reshape(n, hop) ** 2, axis=1))
            rms = np.convolve(rms, np.ones(3) / 3, mode="same")
            envs[(sc["id"], ln["idx"])] = np.clip(rms / (np.percentile(rms, 92) + 1e-6), 0, 1.2)
    return tl, total, envs


def local_lines(sc):
    return [dict(ln, start=ln["start"] - sc["start"], end=ln["end"] - sc["start"]) for ln in sc["lines"]]


class Talk:
    def __init__(self, sc_id, lines, envs):
        self.lines, self.envs, self.id = lines, envs, sc_id

    def __call__(self, spk, t):
        for ln in self.lines:
            if ln["spk"] == spk and ln["start"] <= t < ln["end"]:
                e = self.envs[(self.id, ln["idx"])]
                i = min(int((t - ln["start"]) * ENV_HZ), len(e) - 1)
                return float(min(1.0, e[i] * 0.85))
        return 0.0

    def speaking(self, spk, t, pad=0.15):
        return any(ln["spk"] == spk and ln["start"] - pad <= t < ln["end"] + pad for ln in self.lines)


def blink(t, seed):
    period = 3.1 + (seed * 1.37) % 2.3
    ph_ = (t + seed * 0.77) % period
    return 1.0 if ph_ < 0.11 else 0.0


def idle(t, seed, talk=None, spk=None):
    d = dict(breath=t * 1.5 + seed, blink=blink(t, seed), hair_lag=t * 1.3 + seed, hem_lag=t * 1.1 + seed)
    if talk is not None:
        m = talk(spk, t)
        d["mouth"] = m
        if talk.speaking(spk, t):
            d["nod"] = 2.0 * math.sin(t * 2.6 + seed) + 1.5 * m
    return d


def walk_path(t, t0, t1, p0, p1, stride=0.72):
    """Camina de p0=(x,z) a p1 entre t0 y t1 con arranque y frenada suaves. Devuelve x, z, fase|None."""
    u = (t - t0) / max(t1 - t0, 1e-3)
    u = min(1.0, max(0.0, u))
    # perfil de velocidad: aceleración/frenado (inercia)
    e = u * u * (3 - 2 * u) * 0.35 + u * 0.65
    x = p0[0] + (p1[0] - p0[0]) * e
    z = p0[1] + (p1[1] - p0[1]) * e
    dist = math.hypot(x - p0[0], z - p0[1])
    moving = t0 < t < t1
    return x, z, (dist / stride * math.pi if moving else None)


class Shots:
    """Lista de planos (t0, Lens). Devuelve la cámara activa; los cortes son instantáneos."""

    def __init__(self, shots, W, H):
        self.shots = sorted(shots, key=lambda s: s[0])
        self.W, self.H = W, H

    def __call__(self, t):
        cur = self.shots[0][1]
        for t0, lens in self.shots:
            if t >= t0:
                cur = lens
        return cur.eval(t, self.W, self.H)

    def cut_near(self, t, eps):
        return any(abs(t - t0) < eps for t0, _ in self.shots[1:])


def T(*keys, w=2.2, z=0.95):
    """Pista con inercia: T((t0, v0), (t1, v1), ...)."""
    return Track(list(keys), omega=w, zeta=z)


# ------------------------------------------------------------------ objetos
def branch_painter(state):
    def paint(ctx, t):
        x0, y0, ang, drop = state(t)
        ctx.save()
        ctx.translate(x0, y0)
        ctx.rotate(ang)
        setc(ctx, "#4e3c2c")
        ctx.set_line_width(0.028)
        ctx.set_line_cap(1)
        ctx.move_to(0, 0)
        ctx.curve_to(0.3, 0.05, 0.55, 0.12, 0.85, 0.2)
        ctx.stroke()
        ctx.set_line_width(0.014)
        for (bx, by, a) in ((0.4, 0.08, 0.6), (0.62, 0.13, -0.4), (0.75, 0.17, 0.7)):
            ctx.move_to(bx, by)
            ctx.line_to(bx + 0.18 * math.cos(a), by + 0.18 * math.sin(a))
        ctx.stroke()
        import random
        r = random.Random(3)
        tones = ["#3e5a2a", "#55752f", "#6f8f3e", "#8aa850"]
        for i in range(70):
            u = r.uniform(0.25, 1.0)
            x = 0.85 * u + r.uniform(-0.08, 0.12)
            y = 0.2 * u + r.uniform(-0.1, 0.14)
            setc(ctx, r.choice(tones))
            ellipse(ctx, x, y, 0.04, 0.02, r.uniform(0, 3))
            ctx.fill()
        ctx.restore()
    return paint


def doc_painter(ctx, t):
    """Página del expediente (inserto de la escena 4)."""
    import cairo
    setc(ctx, "#f2ede0")
    rrect(ctx, -0.16, 0.0, 0.32, 0.44, 0.004)
    ctx.fill()
    setc(ctx, "#000000", 0.08)
    ctx.rectangle(0.14, 0.0, 0.02, 0.44)
    ctx.fill()
    ctx.save()
    ctx.scale(1, -1)
    ctx.select_font_face("EB Garamond", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    ctx.set_font_size(0.016)
    setc(ctx, "#2a2a2a")
    ctx.move_to(-0.13, -0.41)
    ctx.show_text("SOLICITUD DE AYUDA FARMACÉUTICA")
    ctx.select_font_face("EB Garamond", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
    ctx.set_font_size(0.011)
    rows = ["Solicitante: Tomás R.   ·   Expediente 214/23",
            "Medicamento: tratamiento cardiológico (madre)",
            "Primera visita: 3 de marzo",
            "Segunda visita: 10 de marzo",
            "",
            "Resolución:"]
    y = -0.375
    for r in rows:
        ctx.move_to(-0.13, y)
        ctx.show_text(r)
        y += 0.02
    ctx.select_font_face("EB Garamond", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    ctx.set_font_size(0.013)
    setc(ctx, "#8a1a1a")
    ctx.move_to(-0.13, y + 0.004)
    ctx.show_text("DENEGADA — documentación incompleta")
    ctx.select_font_face("EB Garamond", cairo.FONT_SLANT_ITALIC, cairo.FONT_WEIGHT_NORMAL)
    ctx.set_font_size(0.011)
    setc(ctx, "#3a3a3a")
    ctx.move_to(-0.13, y + 0.03)
    ctx.show_text("«Vuelva con los documentos.»")
    for k in range(8):
        setc(ctx, "#9a9a9a", 0.6)
        ctx.rectangle(-0.13, y + 0.06 + k * 0.016, 0.22 - (k % 3) * 0.04, 0.003)
        ctx.fill()
    ctx.restore()
    setc(ctx, "#8a1a1a", 0.7)
    ctx.set_line_width(0.003)
    ellipse(ctx, 0.07, 0.06, 0.045, 0.03, 0.2)
    ctx.stroke()


def ball_painter(state):
    def paint(ctx, t):
        x, y, vis = state(t)
        if not vis:
            return
        setc(ctx, "#c8402a")
        ellipse(ctx, x, y, 0.1, 0.1)
        ctx.fill()
        setc(ctx, "#f0e0c0", 0.8)
        ctx.set_line_width(0.012)
        ellipse(ctx, x, y, 0.1, 0.035, t * 7)
        ctx.stroke()
    return paint


def glass_painter(t_break, wx0, wx1, wy0, wy1):
    import random
    r = random.Random(17)
    shards = []
    for i in range(70):
        sx, sy = r.uniform(wx0, wx1), r.uniform(wy0, wy1)
        shards.append((sx, sy, r.uniform(-1.6, 1.6), r.uniform(0.0, 1.5), r.uniform(0.02, 0.07), r.uniform(0, 6),
                       r.uniform(-12, 12)))

    def paint(ctx, t):
        if t < t_break:
            # cristal intacto con reflejo
            setc(ctx, "#cfe4f0", 0.35)
            ctx.rectangle(wx0, wy0, wx1 - wx0, wy1 - wy0)
            ctx.fill()
            setc(ctx, "#ffffff", 0.35)
            poly(ctx, [(wx0 + 0.1, wy1 - 0.05), (wx0 + 0.35, wy1 - 0.05), (wx0 + 0.05, wy0 + 0.3)])
            ctx.fill()
            return
        dt = t - t_break
        # marco con huecos y grietas
        setc(ctx, "#cfe4f0", 0.25)
        poly(ctx, [(wx0, wy0), (wx0 + 0.3, wy0), (wx0 + 0.15, wy0 + 0.5), (wx0, wy0 + 0.8)])
        ctx.fill()
        poly(ctx, [(wx1, wy1), (wx1 - 0.4, wy1), (wx1 - 0.2, wy1 - 0.4), (wx1, wy1 - 0.6)])
        ctx.fill()
        for (sx, sy, vx, vy, sz, a0, w) in shards:
            x = sx + vx * dt * 0.6
            y = sy + vy * dt * 0.6 - 4.9 * dt * dt
            if y < 0.02:
                y = 0.02
                x = sx + vx * 0.6 * math.sqrt(sy / 4.9)
            a = a0 + w * dt if y > 0.021 else a0
            glint = 0.5 + 0.5 * math.sin(a * 3 + dt * 20)
            setc(ctx, (0.85 + 0.15 * glint, 0.93 + 0.07 * glint, 1.0, 0.55 + 0.45 * glint))
            poly(ctx, [(x + sz * math.cos(a), y + sz * math.sin(a)),
                       (x + sz * 0.6 * math.cos(a + 2.2), y + sz * 0.6 * math.sin(a + 2.2)),
                       (x + sz * 0.8 * math.cos(a + 4.1), y + sz * 0.8 * math.sin(a + 4.1))])
            ctx.fill()
    return paint


def bag_painter(ctx, t):
    setc(ctx, "#c8a878")
    smooth_path(ctx, [(-0.18, 0.0), (-0.2, 0.3), (0.2, 0.32), (0.2, 0.0)], tension=0.3)
    ctx.fill()
    setc(ctx, "#a88858")
    ctx.set_line_width(0.015)
    ctx.move_to(-0.1, 0.3)
    ctx.curve_to(-0.1, 0.45, 0.1, 0.45, 0.1, 0.3)
    ctx.stroke()
    for i, c in enumerate(("#e8a040", "#d84a3a", "#8ab050")):
        setc(ctx, c)
        ellipse(ctx, 0.35 + i * 0.13, 0.05, 0.05, 0.05)
        ctx.fill()


# ------------------------------------------------------------------ escenas
class SceneDef:
    """Contiene el decorado (factoría), actores, objetos, planos y modificadores de un tramo."""

    def __init__(self, set_factory, actors, shots, set_key, post_mod=None, env_mod=None, switch=None):
        self.set_factory, self.actors, self.shots = set_factory, actors, shots
        self.set_key, self.post_mod, self.env_mod = set_key, post_mod, env_mod
        self.switch = switch  # (t, otra SceneDef) para cambiar de decorado dentro de la escena


def scene_defs(W, H, tl, envs):
    from sets.garden import Garden, TREE_X, TREE_Z
    from sets.court import Court
    from sets.interiors import Home, Office, Library
    from sets.plaza import Plaza

    D = {}
    by_id = {sc["id"]: sc for sc in tl}

    def ctx_for(i):
        sc = by_id[i]
        L = local_lines(sc)
        return sc, L, Talk(i, L, envs), sc["end"] - sc["start"]

    # ============================================================ 1 · El árbol (+ título)
    sc, L, talk, dur = ctx_for(1)
    a0, j0 = L[0], L[1]
    cut_t = 1.7
    branch_x = TREE_X + 0.05

    def branch_state(t):
        if t < cut_t:
            return branch_x, 1.72, 0.32, 0
        dt = t - cut_t
        y = max(0.03, 1.72 - 4.9 * dt * dt)
        ang = 0.32 - min(1.0, dt / 0.55) * 0.4
        x = branch_x + 0.25 * min(dt, 0.55)
        return x, y, ang, 1

    def gardener1(t):
        p = idle(t, 3, talk, "JA")
        snip = smoothstep(0.6, 1.0, t) * (1 - smoothstep(cut_t + 0.1, cut_t + 0.8, t))
        p.update(arm_f=(lerp(15, 128, snip) + 6 * math.sin(t * 18) * (1 if 1.2 < t < cut_t else 0), 8),
                 hold="shears", arm_b=(lerp(-5, 95, snip), 30), nod=-14 * snip + p.get("nod", 0))
        if t > j0["start"] - 0.4:
            p["nod"] = p.get("nod", 0) + 4
        return p

    def andres1(t):
        x, z, ph_ = walk_path(t, -6.0, 2.6, (-4.6, 6.0), (-1.45, 6.0))
        leave = a0["end"] > 0 and t > j0["end"] + 1.0
        if leave:
            x, z, ph_ = walk_path(t, j0["end"] + 1.0, dur + 1.5, (-1.45, 6.0), (-4.8, 6.4))
        return x, z, ph_

    andres = Actor(CAST["andres"], lambda t: andres1(t)[0], lambda t: andres1(t)[1],
                   lambda t: -1 if t > j0["end"] + 0.9 else 1,
                   lambda t: dict(idle(t, 1, talk, "AN"), walk=andres1(t)[2],
                                  arm_b=(-25, 45) if andres1(t)[2] is None else (-6, 14),
                                  arm_f=(-18, 50) if andres1(t)[2] is None else (8, 12),
                                  nod=(-9 if j0["end"] < t < j0["end"] + 1.0 else 0) + idle(t, 1, talk, "AN").get("nod", 0)))
    gard = Actor(CAST["jardinero"], 2.05, 6.75, -1, gardener1, group=0)
    branch = Prop(6.95, branch_painter(branch_state), group=0)
    title_cam = Lens(T((-6.0, -0.1), (-1.0, -0.3)), T((-6.0, 6.0), (-5.0, 2.0), w=0.9, z=1.0),
                     T((-6.0, -6.0), (-5.0, -3.0), w=0.8, z=1.0), mm=32, fstop=4.0,
                     focus=T((-6.0, 14.0), (-3.0, 9.5)), shift=(0, -90), shake=0.03)
    shots1 = [(-6.0, title_cam),
              (a0["start"] - 0.35, Lens(-1.2, 1.66, T((0, 3.2), (a0["start"], 3.4)), mm=75, fstop=2.0, focus=2.6,
                                        shake=0.01)),
              (j0["start"] - 0.2, Lens(1.76, 1.52, T((0, 3.5), (j0["start"], 3.7)), mm=60, fstop=2.0, focus=3.05,
                                       shake=0.01)),
              (j0["end"] + 0.5, Lens(T((0, -0.2), (j0["end"] + 0.6, -0.5)), 1.45, -2.4, mm=35, fstop=4.0,
                                     focus=T((0, 8.6), (j0["end"] + 1.5, 9.4)), shift=(0, -80), shake=0.02))]
    D[1] = SceneDef(lambda e: Garden(e, "morning"), [andres, gard, branch], shots1, "garden_morning")

    # ============================================================ 2 · El juicio
    sc, L, talk, dur = ctx_for(2)
    l0, l1, l2 = L

    def andres2(t):
        p = idle(t, 2, talk, "AN")
        close = smoothstep(l2["end"] + 0.6, l2["end"] + 1.3, t)
        p.update(sit=0.48, arm_f=(lerp(55, 85, close), lerp(30, 5, close)), arm_b=(40, 40), hold="folder",
                 brow=0.5)
        return p

    def tomas2(t):
        p = idle(t, 5, talk, "TO")
        down = smoothstep(l2["end"] - 0.2, l2["end"] + 0.6, t)
        p.update(nod=lerp(p.get("nod", 0), 18, down), arm_f=(6, 12), arm_b=(-4, 10), brow=-0.3 * (1 - down))
        return p

    actors2 = [Actor(CAST["andres_toga"], 0.75, 13.6, -1, andres2, y=0.5, group=1),
               Actor(CAST["tomas"], -1.55, 8.45, 1, tomas2, group=2)]
    shots2 = [(0.0, Lens(T((0, -0.3), (0.5, 0.1)), 1.7, T((0, -2.8), (0.3, -1.4), w=0.6, z=1.0), mm=28, fstop=4.0,
                         focus=11.0, shift=(0, -40), shake=0.02)),
              (l1["start"] - 0.25, Lens(-1.2, 1.56, T((0, 5.0), (l1["start"], 5.4), w=0.7), mm=60, fstop=2.0,
                                        focus=3.2, shake=0.01)),
              (l2["start"] - 0.2, Lens(0.46, 1.8, T((0, 9.6), (l2["start"], 9.9), w=0.6), mm=85, fstop=2.0,
                                       focus=3.75, shake=0.008)),
              (l2["end"] + 0.35, Lens(-0.9, 1.5, T((0, 2.8), (l2["end"] + 0.4, 3.6), w=0.5), mm=40, fstop=2.2,
                                      focus=T((0, 5.6), (l2["end"] + 1.0, 5.0), (l2["end"] + 1.6, 10.0)),
                                      shake=0.012))]
    D[2] = SceneDef(Court, actors2, shots2, "court")

    # ============================================================ 3 · La hija
    sc, L, talk, dur = ctx_for(3)
    e0, a1, e2, a3, e4 = L

    def elena3(t):
        x, z, ph_ = walk_path(t, e2["start"] - 0.9, e2["start"] + 0.2, (-1.35, 4.7), (-0.95, 4.55))
        return x, z, ph_

    actors3 = [Actor(CAST["andres"], 0.62, 4.5, -1,
                     lambda t: dict(idle(t, 4, talk, "AN"), sit=0.46, arm_f=(62, 28), arm_b=(55, 35),
                                    nod=lerp(idle(t, 4, talk, "AN").get("nod", 0), 12,
                                             smoothstep(e4["end"] + 0.4, e4["end"] + 1.2, t)),
                                    mouth=max(talk("AN", t), 0.25 * smoothstep(e4["end"] + 0.6, e4["end"] + 0.8, t)
                                              * (1 - smoothstep(e4["end"] + 1.6, e4["end"] + 1.8, t))),
                                    brow=0.6 * smoothstep(e4["start"], e4["end"] + 0.3, t)), group=1),
               Actor(CAST["elena"], lambda t: elena3(t)[0], lambda t: elena3(t)[1], 1,
                     lambda t: dict(idle(t, 7, talk, "EL"), walk=elena3(t)[2], arm_f=(15, 50), arm_b=(-5, 30)),
                     group=2)]
    shots3 = [(0.0, Lens(T((0, -0.4), (0.2, 0.0)), 1.45, T((0, -1.8), (0.2, -1.2), w=0.5), mm=30, fstop=2.4,
                         focus=6.0, shake=0.015)),
              (e0["start"] + 1.4, Lens(-1.12, 1.52, 2.0, mm=75, fstop=1.8, focus=2.65, shake=0.008)),
              (a1["start"] - 0.15, Lens(0.43, 1.31, 2.3, mm=75, fstop=1.8, focus=2.2, shake=0.008)),
              (e2["start"] - 0.95, Lens(T((0, -1.1), (e2["start"], -0.74)), 1.52, 2.0, mm=75, fstop=1.8,
                                        focus=T((0, 2.7), (e2["start"], 2.55)), shake=0.008)),
              (a3["start"] - 0.15, Lens(0.43, 1.31, 2.3, mm=75, fstop=1.8, focus=2.2, shake=0.008)),
              (e4["start"] - 0.1, Lens(-0.76, 1.52, 2.1, mm=85, fstop=1.8, focus=2.45, shake=0.008)),
              (e4["end"] + 0.35, Lens(0.47, 1.31, T((0, 2.3), (e4["end"] + 0.4, 2.9), w=0.35, z=1.0), mm=85,
                                      fstop=1.6, focus=T((0, 2.2), (e4["end"] + 0.4, 1.6), w=0.35, z=1.0),
                                      shake=0.006))]
    D[3] = SceneDef(Home, actors3, shots3, "home")

    # ============================================================ 4 · El expediente
    sc, L, talk, dur = ctx_for(4)
    q0, t1_, t2_ = L
    actors4 = [Actor(CAST["andres"], 0.92, 4.5, -1,
                     lambda t: dict(idle(t, 2, talk, "AN"), sit=0.5, arm_f=(70, 25), arm_b=(65, 30), brow=0.4,
                                    nod=lerp(4, 10, smoothstep(t2_["end"] + 0.2, t2_["end"] + 1.0, t))), group=1),
               Actor(CAST["tomas"], -1.45, 3.7, 1,
                     lambda t: dict(idle(t, 5, talk, "TO"), arm_f=(8, 14), arm_b=(-6, 12),
                                    nod=idle(t, 5, talk, "TO").get("nod", 0) + 6), group=2),
               Prop(1.3, lambda ctx, t: (ctx.save(), ctx.translate(0.36, 0.86), doc_painter(ctx, t), ctx.restore()),
                    group=3, visible=lambda t: t < q0["start"] - 0.1)]
    shots4 = [(0.0, Lens(0.42, 1.08, 0.2, mm=50, fstop=1.8,
                         focus=T((0, 1.1), (q0["start"] - 1.0, 1.1), (q0["start"] - 0.7, 3.6), w=3.0, z=1.0),
                         shake=0.006)),
              (q0["start"] - 0.1, Lens(0.74, 1.33, 2.4, mm=75, fstop=1.8, focus=2.1, shake=0.008)),
              (t1_["start"] - 0.2, Lens(-1.22, 1.6, T((0, 0.8), (t1_["start"], 1.5), w=0.3, z=1.0), mm=75, fstop=1.8,
                                        focus=T((0, 2.9), (t1_["start"], 2.2), w=0.3, z=1.0), shake=0.008)),
              (t2_["end"] + 0.3, Lens(0.2, 1.45, -1.4, mm=32, fstop=2.8, focus=5.6, shake=0.012))]
    D[4] = SceneDef(lambda e: Office(e, "day"), actors4, shots4, "office_day")

    # ============================================================ 5 · El maestro
    sc, L, talk, dur = ctx_for(5)
    m0, s1, s2 = L
    actors5 = [Actor(CAST["samuel"], 1.08, 4.4, -1,
                     lambda t: dict(idle(t, 9, talk, "SA"), sit=0.45, arm_f=(45, 35), arm_b=(40, 40), smile=0.2),
                     group=1),
               Actor(CAST["andres"], -1.15, 4.35, 1,
                     lambda t: dict(idle(t, 2, talk, "AN"), arm_f=(10 + 10 * smoothstep(m0["start"], m0["start"] + 0.5, t)
                                                                      * (1 - smoothstep(m0["end"], m0["end"] + 0.5, t)), 30),
                                    arm_b=(-8, 12),
                                    nod=idle(t, 2, talk, "AN").get("nod", 0) + 12 * smoothstep(s2["end"], s2["end"] + 0.8, t)),
                     group=2)]
    shots5 = [(0.0, Lens(T((0, 0.4), (0.2, 0.0)), 1.45, T((0, -1.8), (0.2, -1.3), w=0.5), mm=30, fstop=2.4,
                         focus=5.8, shake=0.015)),
              (m0["start"] + 0.6, Lens(-0.95, 1.6, 2.0, mm=75, fstop=1.8, focus=2.35, shake=0.008)),
              (s1["start"] - 0.2, Lens(T((0, 0.9), (s1["start"], 0.9)), 1.27, T((0, 2.0), (s2["start"], 2.6), w=0.25, z=1.0),
                                       mm=75, fstop=1.8, focus=T((0, 2.4), (s2["start"], 1.8), w=0.25, z=1.0),
                                       shake=0.006)),
              (s2["end"] + 0.25, Lens(-0.98, 1.62, T((0, 2.0), (s2["end"] + 0.3, 2.4), w=0.4), mm=85, fstop=1.6,
                                      focus=T((0, 2.35), (s2["end"] + 0.3, 1.95), w=0.4), shake=0.006))]
    D[5] = SceneDef(Library, actors5, shots5, "library")

    # ============================================================ 6 · La decisión
    sc, L, talk, dur = ctx_for(6)
    e0, a1, e2, a3 = L

    def elena6(t):
        return walk_path(t, 0.2, 2.2, (-3.6, 2.15), (-1.3, 3.5))

    actors6 = [Actor(CAST["andres_shirt"], 0.92, 4.5, -1,
                     lambda t: dict(idle(t, 2, talk, "AN"), sit=0.5,
                                    arm_f=(lerp(70, 30, smoothstep(0.6, 1.4, t) * (1 - smoothstep(a3["end"] + 0.4, a3["end"] + 1.2, t))), 25),
                                    arm_b=(65, 30), nod=4 - 6 * smoothstep(0.6, 1.3, t) * (1 - smoothstep(a3["end"] + 0.3, a3["end"] + 1.0, t))),
                     group=1),
               Actor(CAST["elena"], lambda t: elena6(t)[0], lambda t: elena6(t)[1], 1,
                     lambda t: dict(idle(t, 7, talk, "EL"), walk=elena6(t)[2], arm_f=(10, 40), arm_b=(-5, 25)),
                     group=2)]
    shots6 = [(0.0, Lens(T((0, 1.6), (0.2, 1.3)), 1.45, T((0, -1.6), (0.2, -1.1), w=0.5), mm=30, fstop=2.0,
                         focus=T((0, 5.6), (1.5, 4.5)), shake=0.015)),
              (a1["start"] - 0.2, Lens(0.73, 1.33, 2.3, mm=75, fstop=1.6, focus=2.2, shake=0.008)),
              (e2["start"] - 0.2, Lens(-1.14, 1.52, 1.6, mm=75, fstop=1.6, focus=1.9, shake=0.008)),
              (a3["start"] - 0.2, Lens(0.75, 1.33, T((0, 2.3), (a3["start"], 2.9), w=0.3, z=1.0), mm=75, fstop=1.6,
                                       focus=T((0, 2.2), (a3["start"], 1.6), w=0.3, z=1.0), shake=0.006))]
    D[6] = SceneDef(lambda e: Office(e, "night"), actors6, shots6, "office_night")

    # ============================================================ 7 · El recuerdo
    sc, L, talk, dur = ctx_for(7)
    r0, r1 = L
    t_in, t_out = r0["start"] + 1.0, r1["end"] - 0.6
    t_kick = t_in + 0.6
    t_hit = t_kick + 0.55
    WX0, WX1, WY0, WY1 = 1.2, 2.3, 0.95, 2.15

    def ball(t):
        if t < t_kick:
            return (-0.45, 0.1, True)
        u = (t - t_kick) / (t_hit - t_kick)
        if u <= 1:
            return (lerp(-0.45, 1.7, u), 0.1 + 1.45 * u + 1.2 * math.sin(u * math.pi) * 0.4, True)
        dt = t - t_hit
        return (1.7 - 0.6 * dt, max(0.1, 1.55 - 4.9 * dt * dt + 1.0 * dt), True)

    def child(t):
        kick = smoothstep(t_kick - 0.15, t_kick, t) * (1 - smoothstep(t_kick + 0.1, t_kick + 0.3, t))
        shock = smoothstep(t_hit, t_hit + 0.2, t)
        return dict(idle(t, 11), legs=None, arm_f=(lerp(10, 60, shock), lerp(20, 70, shock)),
                    arm_b=(lerp(-5, 50, shock), 60 * shock), crouch=0.05 * kick, nod=-8 * shock, brow=-0.6 * shock,
                    mouth=0.4 * shock)

    def young(t):
        x, z, ph_ = walk_path(t, t_hit + 0.6, t_hit + 2.0, (-3.6, 6.3), (-1.2, 6.3))
        return x, z, ph_

    flash_actors = [Actor(CAST["elena_nina"], -0.65, 6.4, 1, child, group=0),
                    Prop(6.38, ball_painter(ball), group=0),
                    Prop(8.98, glass_painter(t_hit, WX0, WX1, WY0, WY1), group=1),
                    Actor(CAST["andres_joven"], lambda t: young(t)[0], lambda t: young(t)[1], 1,
                          lambda t: dict(idle(t, 12), walk=young(t)[2],
                                         kneel=smoothstep(t_hit + 2.0, t_hit + 2.5, t),
                                         arm_f=(lerp(8, 80, smoothstep(t_hit + 2.4, t_hit + 2.9, t)), 20)), group=0)]
    flash_shots = [(t_in - 0.01, Lens(T((0, 0.0), (t_in, 0.0), (t_hit + 1.0, -0.4), w=0.5), 1.3,
                                      T((0, 1.2), (t_in, 1.2), (t_out, 2.0), w=0.25, z=1.0), mm=32, fstop=2.0,
                                      focus=5.2, shake=0.02))]

    def flash_post(post, t):
        p = dict(post)
        k = max(0.0, 1.0 - abs(t - t_in) / 0.35) + max(0.0, 1.0 - abs(t - t_out) / 0.35)
        p["flash"] = 1.2 * k
        return p
    flash = SceneDef(lambda e: Plaza(e, "memory"), flash_actors, flash_shots, "plaza_memory", post_mod=flash_post)

    actors7 = [Actor(CAST["elena"], -1.15, 4.3, 1,
                     lambda t: dict(idle(t, 7, talk, "EL"), sit=0.46, arm_f=(45, 50), arm_b=(40, 40)), group=2),
               Actor(CAST["andres"], 0.92, 4.5, -1,
                     lambda t: dict(idle(t, 2, talk, "AN"), sit=0.5, arm_f=(70, 25), arm_b=(65, 30),
                                    nod=16 * smoothstep(r1["end"] - 0.2, r1["end"] + 1.0, t),
                                    blink=1.0 if t > r1["end"] + 1.2 else blink(t, 2)), group=1)]
    shots7 = [(0.0, Lens(T((0, 0.5), (0.2, 0.3)), 1.4, T((0, -1.4), (0.2, -1.0), w=0.4), mm=32, fstop=2.2,
                         focus=5.0, shake=0.012)),
              (t_out - 0.01, Lens(0.74, 1.33, T((0, 2.4), (t_out, 2.4), (dur, 3.0), w=0.3, z=1.0), mm=85, fstop=1.6,
                                  focus=T((0, 2.1), (t_out, 2.1), (dur, 1.5), w=0.3, z=1.0), shake=0.006))]

    def office_post(post, t):
        p = dict(post)
        k = max(0.0, 1.0 - abs(t - t_in) / 0.35) + max(0.0, 1.0 - abs(t - t_out) / 0.35)
        p["flash"] = 1.2 * k
        return p
    D[7] = SceneDef(lambda e: Office(e, "memory"), actors7, shots7, "office_memory", post_mod=office_post,
                    switch=((t_in, t_out), flash))

    # ============================================================ 8 · La reputación
    sc, L, talk, dur = ctx_for(8)
    c0, a1, a2 = L
    crowd = []
    spots = [(-1.6, 10.6, 1), (-2.4, 11.4, 1), (-0.9, 12.4, 1), (2.0, 11.0, -1), (2.9, 11.9, -1), (1.4, 12.8, -1)]
    exits = [(-6.5, 12.0), (-7.0, 15.0), (-4.0, 18.0), (7.0, 12.0), (7.5, 15.5), (5.0, 19.0)]
    t_leave = a2["end"] + 0.4
    for i, ((x, z, f), ex) in enumerate(zip(spots, exits)):
        st = citizen(40 + i)
        spk = "CI" if i == 0 else None

        def pos(t, x=x, z=z, ex=ex, i=i):
            return walk_path(t, t_leave + 0.15 * i, t_leave + 3.4 + 0.2 * i, (x, z), ex)

        def pose(t, i=i, f=f, pos=pos):
            p = idle(t, 20 + i, talk, "CI" if i == 0 else "XX")
            ph_ = pos(t)[2]
            agit = 1.0 if i == 0 and talk.speaking("CI", t) else 0.0
            p.update(walk=ph_, arm_f=(lerp(10, 70, agit) + 10 * agit * math.sin(t * 4), 40 * agit), brow=0.6)
            return p
        face = (lambda t, f=f, ex=ex, x=x: f if t < t_leave else (-1 if ex[0] < x else 1))
        crowd.append(Actor(st, (lambda t, pos=pos: pos(t)[0]), (lambda t, pos=pos: pos(t)[1]), face, pose,
                           group=2))
    andres8 = Actor(CAST["andres"], 0.35, 11.6, -1,
                    lambda t: dict(idle(t, 2, talk, "AN"), arm_f=(12 + 25 * float(talk.speaking("AN", t)), 30),
                                   arm_b=(-6, 12), nod=idle(t, 2, talk, "AN").get("nod", 0)
                                   + 10 * smoothstep(t_leave + 2.5, t_leave + 3.5, t)), group=1)
    shots8 = [(0.0, Lens(T((0, 0.2), (0.3, 0.4)), 1.6, T((0, 3.0), (0.3, 4.0), w=0.4), mm=40, fstop=2.8, focus=7.6,
                         shift=(0, -60), shake=0.015)),
              (c0["start"] - 0.2, Lens(-1.38, 1.62, 8.0, mm=75, fstop=2.0, focus=2.7, shake=0.01)),
              (a1["start"] - 0.2, Lens(0.15, 1.66, T((0, 8.6), (a1["start"], 9.0), w=0.4), mm=85, fstop=1.8,
                                       focus=T((0, 3.0), (a1["start"], 2.6), w=0.4), shake=0.008)),
              (t_leave - 0.2, Lens(0.3, T((0, 1.6), (t_leave, 2.2), w=0.25, z=1.0),
                                   T((0, 4.0), (t_leave, -2.5), w=0.22, z=1.0), mm=35, fstop=4.0,
                                   focus=T((0, 7.5), (t_leave, 14.0), w=0.22, z=1.0), shift=(0, -110),
                                   shake=0.015))]
    D[8] = SceneDef(lambda e: Plaza(e, "steps"), [andres8] + crowd, shots8, "plaza_steps")

    # ============================================================ 9 · La rama
    sc, L, talk, dur = ctx_for(9)
    a0, j1 = L
    t_pick = j1["end"] + 0.6

    def andres9(t):
        x, z, ph_ = walk_path(t, -1.0, 1.8, (-3.6, 6.1), (-0.85, 6.1))
        if t > t_pick + 1.2:
            x, z, ph_ = walk_path(t, t_pick + 1.2, t_pick + 2.6, (-0.85, 6.1), (-2.2, 6.3))
        return x, z, ph_

    def branch9(t):
        if t < t_pick + 0.45:
            return (-0.55, 0.04, -0.12, 0)
        x, z, _ = andres9(t)
        if t < t_pick + 2.6:
            return (x - 0.55, 1.0, -0.25, 0)
        return (-3.3, 0.04, 0.05, 0)

    def pose9(t):
        p = idle(t, 2, talk, "AN")
        crouch = smoothstep(t_pick, t_pick + 0.4, t) * (1 - smoothstep(t_pick + 0.5, t_pick + 0.9, t))
        crouch2 = smoothstep(t_pick + 2.6, t_pick + 3.0, t)
        p.update(walk=andres9(t)[2], crouch=max(crouch, crouch2),
                 arm_f=(lerp(-10, 75, max(crouch, crouch2)), 25) if t < t_pick + 0.5 or t > t_pick + 2.6 else (55, 35),
                 arm_b=(-20, 40), nod=10 * max(crouch, crouch2) + p.get("nod", 0) + (-6 if a0["end"] < t < j1["end"] else 0))
        return p

    actors9 = [Actor(CAST["andres"], lambda t: andres9(t)[0], lambda t: andres9(t)[1],
                     lambda t: -1 if t > t_pick + 1.15 else 1, pose9, group=0),
               Actor(CAST["jardinero"], 1.95, 6.6, -1,
                     lambda t: dict(idle(t, 3, talk, "JA"), arm_f=(20, 50), arm_b=(-10, 30), hold="shears"), group=0),
               Prop(6.05, branch_painter(branch9), group=0)]
    shots9 = [(0.0, Lens(T((0, 0.3), (0.2, 0.0)), 1.35, T((0, -2.6), (0.2, -2.0), w=0.4), mm=32, fstop=2.8,
                         focus=8.3, shift=(0, -140), shake=0.015)),
              (a0["start"] - 0.2, Lens(-0.6, 1.66, 3.2, mm=75, fstop=1.8, focus=2.9, shake=0.008)),
              (j1["start"] - 0.2, Lens(1.7, 1.52, T((0, 3.4), (j1["start"], 3.8), w=0.3), mm=75, fstop=1.8,
                                       focus=T((0, 3.2), (j1["start"], 2.8), w=0.3), shake=0.008)),
              (j1["end"] + 0.3, Lens(T((0, -0.6), (j1["end"], -0.9)), 1.4, -1.6, mm=35, fstop=2.8,
                                     focus=T((0, 7.5), (t_pick + 1.5, 7.8)), shift=(0, -140), shake=0.015))]
    D[9] = SceneDef(lambda e: Garden(e, "evening"), actors9, shots9, "garden_evening")

    # ============================================================ 10 · Lo que queda
    sc, L, talk, dur = ctx_for(10)
    s0, a1, a2 = L
    t_up = a1["end"] + 0.4

    def andres10(t):
        if t < t_up + 0.5:
            return -0.3, 5.0, None
        x, z, ph_ = walk_path(t, t_up + 0.5, a2["start"] - 0.5, (-0.3, 5.0), (2.75, 11.3))
        return x, z, ph_

    def pose10(t):
        p = idle(t, 2, talk, "AN")
        x, z, ph_ = andres10(t)
        sit = t < t_up + 0.45
        p.update(walk=ph_, arm_f=(15 + 20 * float(talk.speaking("AN", t) and t > a2["start"] - 0.2), 30),
                 arm_b=(-6, 12))
        if sit:
            p.update(sit=0.45, arm_f=(45, 40), arm_b=(40, 40))
        if t > a2["start"] - 0.4:
            p["nod"] = p.get("nod", 0) + 6
        return p

    arguing = []
    for i, (x, f) in enumerate(((3.45, 1), (4.55, -1))):
        def ap(t, i=i):
            heated = 1.0 - smoothstep(a2["end"], a2["end"] + 1.0, t)
            p = idle(t, 30 + i)
            g = math.sin(t * (3.4 + i) + i * 2)
            speak = (t < a2["start"] - 0.3 and (int(t * 0.7 + i) % 2 == 0)) or (t > a2["end"] + 0.3 + i * 1.6 and
                                                                               t < a2["end"] + 1.9 + i * 1.6)
            p.update(arm_f=(lerp(20, 70, heated * (0.5 + 0.5 * g)) if speak else 15, 40 * heated),
                     mouth=(0.3 + 0.3 * abs(math.sin(t * 9 + i))) if speak else 0.0, brow=0.7 * heated)
            return p
        arguing.append(Actor(citizen(70 + i), x, 12.4 + i * 0.25, f, ap, group=2))
    actors10 = [Actor(CAST["samuel"], -1.3, 5.0, 1,
                      lambda t: dict(idle(t, 9, talk, "SA"), sit=0.45, arm_f=(45, 35), arm_b=(40, 40),
                                     smile=0.5 * smoothstep(t_up + 0.5, t_up + 1.5, t),
                                     nod=idle(t, 9, talk, "SA").get("nod", 0) + 8 * smoothstep(a1["end"], a1["end"] + 0.4, t)
                                     * (1 - smoothstep(a1["end"] + 0.6, a1["end"] + 1.0, t))), group=1),
                Actor(CAST["andres"], lambda t: andres10(t)[0], lambda t: andres10(t)[1],
                      lambda t: -1 if t < t_up + 0.45 else 1, pose10, group=1),
                Prop(12.3, lambda ctx, t: (ctx.save(), ctx.translate(4.0, 0.0), bag_painter(ctx, t), ctx.restore()),
                     group=2)] + arguing
    shots10 = [(0.0, Lens(T((0, -0.4), (0.2, -0.6)), 1.3, T((0, 1.0), (0.2, 1.4), w=0.4), mm=40, fstop=2.0,
                          focus=4.0, shake=0.012)),
               (s0["start"] - 0.2, Lens(-1.14, 1.24, 2.9, mm=85, fstop=1.8, focus=2.1, shake=0.008)),
               (a1["start"] - 0.2, Lens(-0.46, 1.27, 3.0, mm=85, fstop=1.8, focus=2.05, shake=0.008)),
               (t_up + 0.2, Lens(T((0, 0.0), (t_up + 0.3, 0.6), (a2["start"], 1.2), w=0.35, z=1.0),
                                 T((0, 1.5), (a2["end"], 1.6), (dur - 4.0, 3.6), w=0.2, z=1.0),
                                 T((0, -1.0), (t_up + 0.3, -0.5), (dur - 4.0, -5.5), w=0.2, z=1.0), mm=35, fstop=2.8,
                                 focus=T((0, 6.0), (t_up + 0.6, 7.2), (a2["start"] - 0.5, 10.5), (dur - 4.0, 13.0),
                                         w=0.5, z=1.0), shift=(0, -90), shake=0.015))]
    D[10] = SceneDef(lambda e: Plaza(e, "sunset"), actors10, shots10, "plaza_sunset")
    return D


def lerp(a, b, u):
    return a + (b - a) * u
