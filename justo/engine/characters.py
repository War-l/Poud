"""Personajes ilustrados con esqueleto articulado (perfil), en metros.

Coordenadas locales: pies en (0, 0), +x hacia donde mira, +y arriba.
Proporciones de un adulto de 7,5 cabezas. El sombreado se orienta con la
dirección de la luz principal (en espacio de pantalla) para que cada figura
quede iluminada de forma coherente con el decorado.
"""
import math

import cairo

from .paint import hx, mix, shade, setc, smooth_path, poly, ellipse, lin_grad


def rot(p, a, c=(0.0, 0.0)):
    s, co = math.sin(a), math.cos(a)
    x, y = p[0] - c[0], p[1] - c[1]
    return (c[0] + x * co - y * s, c[1] + x * s + y * co)


def add(a, b):
    return (a[0] + b[0], a[1] + b[1])


def polar(p, length, ang_from_down):
    """Punto a `length` desde p, ángulo medido desde la vertical hacia abajo (+ = adelante)."""
    return (p[0] + length * math.sin(ang_from_down), p[1] - length * math.cos(ang_from_down))


def ik2(a, b, l1, l2, bend_forward=True):
    dx, dy = b[0] - a[0], b[1] - a[1]
    d = math.hypot(dx, dy)
    d = min(d, l1 + l2 - 1e-4)
    if d < 1e-6:
        return a
    ca = (l1 * l1 + d * d - l2 * l2) / (2 * l1 * d)
    ca = max(-1.0, min(1.0, ca))
    ang = math.acos(ca)
    base = math.atan2(dy, dx)
    s = 1 if bend_forward else -1
    # rodilla/codo: girar hacia +x (adelante) o hacia atrás
    cand1 = (a[0] + l1 * math.cos(base + ang), a[1] + l1 * math.sin(base + ang))
    cand2 = (a[0] + l1 * math.cos(base - ang), a[1] + l1 * math.sin(base - ang))
    if s > 0:
        return cand1 if cand1[0] >= cand2[0] else cand2
    return cand1 if cand1[0] < cand2[0] else cand2


# ------------------------------------------------------------------ estilos
CAST = {
    "andres": dict(height=1.80, skin="#d9a582", skin_sh="#9c6150", hair="#3b322d", hair_hi="#8d8580",
                   hair_style="short_grey", face="male", brows="#2e2622",
                   outfit="suit", coat="#2e3440", coat_sh="#1a1e27", shirt="#e9e4da", tie="#6b2a2e",
                   trousers="#2a2f39", shoes="#1b1715"),
    "andres_toga": dict(height=1.80, skin="#d9a582", skin_sh="#9c6150", hair="#3b322d", hair_hi="#8d8580",
                        hair_style="short_grey", face="male", brows="#2e2622",
                        outfit="toga", coat="#16161b", coat_sh="#060609", shirt="#ece8df", tie="#ece8df",
                        trousers="#1e2028", shoes="#151210", lace="#f2efe6"),
    "andres_shirt": dict(height=1.80, skin="#d9a582", skin_sh="#9c6150", hair="#3b322d", hair_hi="#8d8580",
                         hair_style="short_grey", face="male", brows="#2e2622",
                         outfit="shirt", coat="#e6e1d6", coat_sh="#a9a294", shirt="#e6e1d6", tie="#5a2428",
                         trousers="#2a2f39", shoes="#1b1715", sleeves_rolled=True),
    "andres_joven": dict(height=1.80, skin="#dcaa86", skin_sh="#9c6150", hair="#2a211c", hair_hi="#5a4a40",
                         hair_style="short", face="male", brows="#2a211c",
                         outfit="shirt", coat="#8fa7c0", coat_sh="#5b7088", shirt="#8fa7c0", tie=None,
                         trousers="#4a4a52", shoes="#2a2420"),
    "elena": dict(height=1.66, skin="#e8bf9f", skin_sh="#b07a66", hair="#7a3a22", hair_hi="#c0683c",
                  hair_style="long", face="female", brows="#5a2a1a",
                  outfit="dress", coat="#2f6a68", coat_sh="#1b4443", shirt="#2f6a68", cardigan="#d9cbb0",
                  cardigan_sh="#a3937a", trousers="#2f6a68", shoes="#4a2e22", tie=None),
    "elena_nina": dict(height=1.18, skin="#efc8a8", skin_sh="#b98370", hair="#8a4428", hair_hi="#d0784a",
                       hair_style="ponytail", face="child", brows="#6a3420",
                       outfit="dress", coat="#e8b84a", coat_sh="#b8862a", shirt="#e8b84a", cardigan=None,
                       trousers="#e8b84a", shoes="#7a3a2a", tie=None),
    "tomas": dict(height=1.76, skin="#c99470", skin_sh="#8a5a44", hair="#1d1714", hair_hi="#4a3a30",
                  hair_style="curly", face="young", brows="#1d1714",
                  outfit="jacket", coat="#55613f", coat_sh="#333d24", shirt="#7c7f86", hood="#7c7f86",
                  trousers="#3b4a63", shoes="#3a342e", tie=None),
    "samuel": dict(height=1.72, skin="#deae90", skin_sh="#a2705e", hair="#ece8e2", hair_hi="#ffffff",
                   hair_style="bald_white", face="old", brows="#d8d2c8", beard="#e8e3db", glasses=True,
                   outfit="suit", coat="#7a5a3e", coat_sh="#4e3826", shirt="#e8dfcc", tie=None, vest="#5a4a3a",
                   trousers="#5a4c40", shoes="#2c221c", cane=True, stoop=7),
    "jardinero": dict(height=1.74, skin="#c68a62", skin_sh="#8a5238", hair="#6a6058", hair_hi="#9a9088",
                      hair_style="hat", face="weathered", brows="#4a4038", mustache="#8a8078",
                      outfit="work", coat="#5f7d98", coat_sh="#3e566e", shirt="#5f7d98", apron="#7a5638",
                      trousers="#4a4036", shoes="#3a2c22", tie=None, hat="#d8b878", hat_sh="#a8884a"),
}


def citizen(seed):
    import random
    r = random.Random(seed)
    coats = ["#5a4a6a", "#4a6a6a", "#8a5a3a", "#6a3a3a", "#3e4e6e", "#6e6a4a", "#7a6a5a", "#3a3a40", "#8a7a6a"]
    skins = [("#e8bf9f", "#b07a66"), ("#d9a582", "#9c6150"), ("#b98260", "#7a4a36"), ("#8d5a3b", "#5a3420"),
             ("#f0cdb0", "#c08a74")]
    hairs = ["#1d1714", "#3b2a20", "#6a4a30", "#8a7a6a", "#d8d2c8", "#2a2a2a"]
    sk = r.choice(skins)
    female = r.random() < 0.5
    c = r.choice(coats)
    return dict(height=r.uniform(1.6, 1.68) if female else r.uniform(1.68, 1.85), skin=sk[0], skin_sh=sk[1],
                hair=r.choice(hairs), hair_hi="#a09080",
                hair_style=r.choice(["bob", "long", "bun"] if female else ["short", "short", "bald_white", "cap"]),
                face="female" if female else "male", brows="#3a2a20",
                outfit="dress" if female and r.random() < 0.5 else "coat", coat=c, coat_sh=shade(c, 0.62),
                shirt=r.choice(["#e9e4da", "#c9b89a", "#8a9aa8"]), cardigan=None,
                trousers=r.choice(["#2a2f39", "#4a4036", "#3a3a40"]), shoes="#221a16", tie=None,
                hat=r.choice(["#3a3a40", "#6a5040"]), hat_sh="#202024")


# ------------------------------------------------------------------ pose
DEFAULT_POSE = dict(
    walk=None, stride=1.0, lean=0.0, chest=0.0, nod=0.0, crouch=0.0, sit=None,
    arm_f=(8.0, 12.0), arm_b=(-6.0, 14.0), hand_f="relax", hand_b="relax",
    legs=None, mouth=0.0, smile=0.0, brow=0.0, blink=0.0, look=0.0,
    breath=0.0, hold=None, hold_b=None, hair_lag=0.0, hem_lag=0.0, kneel=0.0,
)


class Figure:
    def __init__(self, style):
        self.st = dict(style)
        self.H = self.st["height"]

    # -------------------------------------------------------------- esqueleto
    def skeleton(self, pose):
        H = self.H
        P = dict(DEFAULT_POSE)
        P.update(pose)
        thigh, shin = 0.245 * H, 0.25 * H
        uarm, farm = 0.186 * H, 0.15 * H
        bob = 0.0
        sk = {}
        if P["sit"] is not None:
            seat = P["sit"]
            hip = (-0.02 * H, seat + 0.04 * H)
            knee = (hip[0] + thigh * 0.98, hip[1] + 0.01 * H)
            foot_f = (knee[0] + 0.03 * H, 0.0)
            foot_b = (knee[0] - 0.01 * H, 0.0)
            knee_b = (knee[0] - 0.03 * H, knee[1] + 0.005)
            sk.update(hip=hip, knee_f=knee, foot_f=foot_f, knee_b=knee_b, foot_b=foot_b)
            lean = math.radians(P["lean"] - 4)
        else:
            if P["walk"] is not None:
                ph = P["walk"]
                bob = -0.018 * H * abs(math.cos(ph)) * P["stride"] + 0.009 * H
            hip_h = 0.53 * H - 0.21 * H * P["crouch"] - 0.25 * H * P["kneel"] + bob
            hip = (0.0, hip_h)
            feet = []
            for i in (0, 1):
                if P["walk"] is not None:
                    ph = P["walk"] + i * math.pi
                    fx = 0.17 * H * P["stride"] * math.sin(ph)
                    lift = max(0.0, math.cos(ph)) * 0.05 * H * P["stride"]
                    feet.append((fx, 0.035 * H + lift * 0.8))
                elif P["legs"] is not None:
                    feet.append(P["legs"][i])
                elif P["kneel"] > 0:
                    feet.append(((0.16 * H if i == 0 else -0.28 * H) * P["kneel"], 0.035 * H))
                elif P["crouch"] > 0:
                    feet.append(((0.08 if i == 0 else -0.06) * H * P["crouch"] + (0.04 if i == 0 else -0.02) * H,
                                 0.035 * H))
                else:
                    feet.append(((0.035 if i == 0 else -0.04) * H, 0.035 * H))
            knee_f = ik2(hip, feet[0], thigh, shin, True)
            knee_b = ik2(hip, feet[1], thigh, shin, True)
            sk.update(hip=hip, knee_f=knee_f, foot_f=feet[0], knee_b=knee_b, foot_b=feet[1])
            lean = math.radians(P["lean"] + 32 * P["crouch"] + 6 * P["kneel"] + self.st.get("stoop", 0))
        # columna en dos tramos (lumbar y torácico) para una curva natural
        breath = 0.004 * H * math.sin(P["breath"])
        spine1 = polar(sk["hip"], 0.11 * H, math.pi + lean * 0.6)
        chest_ang = lean + math.radians(P["chest"])
        neck = polar(spine1, 0.19 * H + breath, math.pi + chest_ang)
        shoulder = polar(spine1, 0.165 * H + breath, math.pi + chest_ang)
        shoulder = (shoulder[0] - 0.015 * H, shoulder[1])
        head_ang = chest_ang * 0.4 + math.radians(P["nod"])
        head_c = polar(neck, 0.062 * H if self.st["face"] != "child" else 0.09 * H, math.pi + head_ang * 0.6)
        head_c = (head_c[0] + 0.014 * H, head_c[1] + 0.012 * H)
        sk.update(spine=spine1, neck=neck, shoulder=shoulder, head=head_c, head_ang=head_ang, lean=lean,
                  chest_ang=chest_ang)
        # brazos
        swing = 0.0 if P["walk"] is None else 22 * math.sin(P["walk"]) * P["stride"]
        for side, key in (("f", "arm_f"), ("b", "arm_b")):
            a1, a2 = P[key]
            if P["walk"] is not None and key == "arm_f":
                a1 += swing
            if P["walk"] is not None and key == "arm_b":
                a1 -= swing
            sh = shoulder if side == "f" else (shoulder[0] - 0.01 * H, shoulder[1] + 0.005 * H)
            el = polar(sh, uarm, math.radians(a1) + chest_ang * 0.5)
            wr = polar(el, farm, math.radians(a1 + a2) + chest_ang * 0.5)
            sk["sh_" + side], sk["el_" + side], sk["wr_" + side] = sh, el, wr
            sk["fa_ang_" + side] = math.radians(a1 + a2) + chest_ang * 0.5
        sk["P"] = P
        return sk

    # -------------------------------------------------------------- dibujo
    def draw(self, ctx, x, y, ppm, facing=1, pose=None, light=(-0.6, 0.8), lightcol=None, shadow_ctx=None,
             sun_shear=None):
        """Dibuja en espacio de pantalla. (x, y): pies en px; ppm: píxeles por metro."""
        pose = pose or {}
        sk = self.skeleton(pose)
        ctx.save()
        ctx.translate(x, y)
        ctx.scale(ppm * facing, -ppm)
        # la luz en coordenadas locales (x local se invierte si mira a la izquierda)
        lx, ly = light[0] * facing, light[1]
        self.lightdir = (lx, ly)
        self.lw = 1.0 / ppm  # 1 px en metros
        st = self.st
        P = sk["P"]
        self._back_arm(ctx, sk)
        self._leg(ctx, sk, "b")
        self._torso(ctx, sk)
        self._leg(ctx, sk, "f")
        self._garment_over(ctx, sk)
        self._head(ctx, sk)
        self._front_arm(ctx, sk)
        if st.get("cane"):
            w = sk["wr_f"]
            self._stroke(ctx, [(w[0] + 0.02, w[1] + 0.03), (w[0] + 0.07, 0.0)], 0.022, "#3a2618")
            self._stroke(ctx, [(w[0] - 0.03, w[1] + 0.03), (w[0] + 0.03, w[1] + 0.04)], 0.024, "#3a2618")
        ctx.restore()
        return sk

    # -------------------------------------------------------------- utilidades de dibujo
    def _stroke(self, ctx, pts, w, col):
        setc(ctx, col)
        ctx.set_line_width(w)
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        ctx.set_line_join(cairo.LINE_JOIN_ROUND)
        ctx.move_to(*pts[0])
        for p in pts[1:]:
            ctx.line_to(*p)
        ctx.stroke()

    def _shade_fill(self, ctx, base, dark, bbox, outline=True, strength=1.0):
        """Rellena la ruta actual con su color y un degradado de sombra orientado a la luz."""
        path = ctx.copy_path()
        setc(ctx, base)
        ctx.fill_preserve()
        x0, y0, x1, y1 = bbox
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        r = max(x1 - x0, y1 - y0) * 0.6 + 1e-3
        lx, ly = self.lightdir
        ctx.save()
        ctx.clip_preserve()
        g = cairo.LinearGradient(cx + lx * r, cy + ly * r, cx - lx * r, cy - ly * r)
        d = hx(dark) if isinstance(dark, str) else dark
        g.add_color_stop_rgba(0.0, 1, 1, 1, 0.0)
        g.add_color_stop_rgba(0.42, d[0], d[1], d[2], 0.0)
        g.add_color_stop_rgba(0.62, d[0], d[1], d[2], 0.38 * strength)
        g.add_color_stop_rgba(1.0, d[0], d[1], d[2], 0.6 * strength)
        ctx.set_source(g)
        ctx.paint()
        ctx.restore()
        if outline:
            ctx.new_path()
            ctx.append_path(path)
            o = shade(d, 0.7)
            setc(ctx, o, 0.22)
            ctx.set_line_width(self.lw * 1.2)
            ctx.stroke()
        ctx.new_path()

    def _limb_path(self, ctx, pts, widths):
        left, right = [], []
        n = len(pts)
        for i, p in enumerate(pts):
            a = pts[min(i + 1, n - 1)]
            b = pts[max(i - 1, 0)]
            dx, dy = a[0] - b[0], a[1] - b[1]
            L = math.hypot(dx, dy) or 1
            nx, ny = -dy / L, dx / L
            w = widths[i] / 2
            left.append((p[0] + nx * w, p[1] + ny * w))
            right.append((p[0] - nx * w, p[1] - ny * w))
        smooth_path(ctx, left + right[::-1], close=True, tension=0.6)

    def _limb(self, ctx, pts, widths, base, dark):
        """Extremidad con contorno anatómico (anchuras por articulación)."""
        left, right = [], []
        n = len(pts)
        for i, p in enumerate(pts):
            a = pts[min(i + 1, n - 1)]
            b = pts[max(i - 1, 0)]
            dx, dy = a[0] - b[0], a[1] - b[1]
            L = math.hypot(dx, dy) or 1
            nx, ny = -dy / L, dx / L
            w = widths[i] / 2
            left.append((p[0] + nx * w, p[1] + ny * w))
            right.append((p[0] - nx * w, p[1] - ny * w))
        smooth_path(ctx, left + right[::-1], close=True, tension=0.6)
        xs = [p[0] for p in left + right]
        ys = [p[1] for p in left + right]
        self._shade_fill(ctx, base, dark, (min(xs), min(ys), max(xs), max(ys)))

    # -------------------------------------------------------------- piernas
    def _leg(self, ctx, sk, side):
        st, H = self.st, self.H
        hip = (sk["hip"][0] + (0.012 if side == "f" else -0.012) * H, sk["hip"][1])
        knee, foot = sk["knee_" + side], sk["foot_" + side]
        k = 0.82 if side == "b" else 1.0
        tr = shade(st["trousers"], k)
        trd = shade(st.get("coat_sh", "#000000"), 0.9)
        if st["outfit"] in ("dress",):
            # pierna con media/piel bajo la falda
            self._limb(ctx, [knee, foot], [0.05 * H, 0.034 * H], shade(st["skin"], k * 0.95), st["skin_sh"])
        elif st["outfit"] == "toga":
            self._limb(ctx, [hip, knee, foot], [0.09 * H, 0.065 * H, 0.05 * H], tr, "#000000")
        else:
            mid = ((hip[0] + knee[0]) / 2 + 0.006 * H, (hip[1] + knee[1]) / 2)
            self._limb(ctx, [hip, mid, knee, foot], [0.095 * H, 0.08 * H, 0.06 * H, 0.05 * H], tr,
                       shade(st["trousers"], 0.45))
        # zapato
        fx, fy = foot
        ang = 0.0
        if sk["P"].get("walk") is not None:
            ang = -0.25 * math.sin(sk["P"]["walk"] + (0 if side == "f" else math.pi))
        ctx.save()
        ctx.translate(fx, fy - 0.03 * H)
        ctx.rotate(ang)
        L = 0.15 * H
        smooth_path(ctx, [(-0.035 * H, 0.03 * H), (-0.04 * H, -0.005 * H), (L * 0.75, -0.005 * H),
                          (L * 0.82, 0.012 * H), (L * 0.55, 0.035 * H), (0.0, 0.045 * H)], tension=0.5)
        self._shade_fill(ctx, shade(st["shoes"], k), "#000000", (-0.04 * H, -0.01, L, 0.05 * H))
        ctx.restore()

    # -------------------------------------------------------------- torso
    def _torso(self, ctx, sk):
        st, H, P = self.st, self.H, sk["P"]
        hip, sp, sh, nk = sk["hip"], sk["spine"], sk["shoulder"], sk["neck"]
        lean = sk["chest_ang"]
        fw = lambda p, d, w: (p[0] + w * math.cos(d), p[1] + w * math.sin(d))
        # perfil de pecho y espalda (anchuras del cuerpo en perfil)
        ax = lean  # perpendicular a la columna = adelante
        front = lambda p, w: (p[0] + w * math.cos(ax), p[1] - w * math.sin(ax) * 0.3)
        back = lambda p, w: (p[0] - w * math.cos(ax), p[1] + w * math.sin(ax) * 0.3)
        female = st["face"] in ("female", "child")
        chest_w = 0.112 * H if not female else 0.1 * H
        belly_w = 0.098 * H if not female else 0.082 * H
        hip_w = 0.09 * H if not female else 0.1 * H
        outfit = st["outfit"]
        # longitud de la prenda
        hem_drop = {"suit": 0.17, "coat": 0.33, "toga": 0.48, "jacket": 0.09, "shirt": 0.03,
                    "work": 0.05, "dress": 0.3}[outfit] * H
        if st.get("cardigan"):
            hem_drop = max(hem_drop, 0.26 * H)
        hp = hip
        if P["sit"] is not None:
            hem_drop = min(hem_drop, 0.08 * H)
        sway = 0.02 * H * math.sin(P["hem_lag"])
        knee_mid = ((sk["knee_f"][0] + sk["knee_b"][0]) / 2, (sk["knee_f"][1] + sk["knee_b"][1]) / 2)
        hem_y = hp[1] - hem_drop
        if P["sit"] is not None:
            hem_front = (sk["knee_f"][0] - 0.05 * H, sk["knee_f"][1] + 0.03 * H)
        else:
            hem_front = (max(hp[0] + hip_w * 0.9, knee_mid[0] + 0.06 * H) + sway, max(hem_y, 0.02))
        hem_back = (hp[0] - hip_w * 0.85 + sway * 0.6 - (0.03 * H if outfit == "toga" else 0),
                    max(hem_y + 0.01 * H, 0.02))
        sh_top_b = back(sh, chest_w * 0.55)
        sh_top_f = front(sh, chest_w * 0.35)
        pts = [
            (nk[0] - 0.035 * H, nk[1] - 0.01 * H),
            sh_top_b,
            back(sp, belly_w * 0.62),
            back(hp, hip_w * 0.75),
            hem_back,
            hem_front,
            front(hp, hip_w * 0.8),
            front(sp, belly_w * 0.62),
            front((sh[0], sh[1] - 0.09 * H), chest_w * 0.62),
            sh_top_f,
            (nk[0] + 0.03 * H, nk[1] - 0.02 * H),
        ]
        base = st["coat"] if outfit not in ("shirt",) else st["shirt"]
        smooth_path(ctx, pts, tension=0.55)
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        bbox = (min(xs), min(ys), max(xs), max(ys))
        self._shade_fill(ctx, base, st.get("coat_sh", shade(base, 0.6)), bbox)
        # pliegues
        setc(ctx, shade(st.get("coat_sh", base), 0.9), 0.35)
        ctx.set_line_width(self.lw * 2.0)
        for k in (0.3, 0.6):
            a = (hp[0] + (hem_front[0] - hp[0]) * k - 0.02 * H, hp[1] - 0.02 * H)
            b = (hem_back[0] + (hem_front[0] - hem_back[0]) * (0.3 + k * 0.5), hem_front[1] + 0.02 * H)
            ctx.move_to(*a)
            ctx.curve_to(a[0] + 0.01, (a[1] + b[1]) / 2, b[0] - 0.01, (a[1] + b[1]) / 2, *b)
            ctx.stroke()
        # camisa, corbata, solapas
        neck_f = (nk[0] + 0.03 * H, nk[1] - 0.02 * H)
        if outfit in ("suit", "toga", "coat", "jacket", "work"):
            v_bottom = front((sh[0], sh[1] - 0.13 * H), chest_w * 0.55)
            setc(ctx, st["shirt"] if outfit != "jacket" else st.get("hood", st["shirt"]))
            poly(ctx, [neck_f, (neck_f[0] - 0.03 * H, neck_f[1]), (v_bottom[0] - 0.005 * H, v_bottom[1]),
                       (v_bottom[0] + 0.004 * H, v_bottom[1] + 0.01 * H)])
            ctx.fill()
            if st.get("tie"):
                setc(ctx, st["tie"])
                tie_top = (neck_f[0] - 0.006 * H, neck_f[1] - 0.008 * H)
                poly(ctx, [tie_top, (tie_top[0] - 0.012 * H, tie_top[1] - 0.012 * H),
                           (v_bottom[0] - 0.008 * H, v_bottom[1] + 0.01 * H), (v_bottom[0] + 0.002 * H, v_bottom[1]),
                           (tie_top[0] + 0.004 * H, tie_top[1] - 0.012 * H)])
                ctx.fill()
            if st.get("vest"):
                setc(ctx, st["vest"])
                poly(ctx, [(v_bottom[0] - 0.004 * H, v_bottom[1] + 0.03 * H), (v_bottom[0], v_bottom[1]),
                           front(sp, belly_w * 0.6), (sp[0] + 0.02 * H, sp[1] - 0.03 * H)])
                ctx.fill()
            # solapa
            setc(ctx, shade(base, 0.75 if outfit != "toga" else 1.6))
            ctx.set_line_width(self.lw * 3)
            ctx.move_to(*neck_f)
            ctx.line_to(v_bottom[0] - 0.012 * H, v_bottom[1] + 0.02 * H)
            ctx.stroke()
            if outfit == "toga":
                # cuello blanco (golilla) y brillo de la tela
                setc(ctx, st["lace"])
                ellipse(ctx, neck_f[0] - 0.012 * H, neck_f[1] - 0.004 * H, 0.03 * H, 0.012 * H, -0.3)
                ctx.fill()
                setc(ctx, "#ffffff", 0.07)
                ctx.set_line_width(self.lw * 6)
                ctx.move_to(sh_top_b[0] + 0.02 * H, sh_top_b[1] - 0.05 * H)
                ctx.curve_to(sh_top_b[0], hp[1], hem_back[0] + 0.05 * H, hem_back[1] + 0.2 * H,
                             hem_back[0] + 0.06 * H, hem_back[1] + 0.02 * H)
                ctx.stroke()
            if outfit == "jacket":
                # capucha sobre la espalda
                setc(ctx, st.get("hood", "#777777"))
                hb = (nk[0] - 0.06 * H, nk[1] - 0.005 * H)
                smooth_path(ctx, [hb, (hb[0] - 0.035 * H, hb[1] - 0.04 * H), (hb[0] + 0.01 * H, hb[1] - 0.08 * H),
                                  (hb[0] + 0.04 * H, hb[1] - 0.02 * H)])
                self._shade_fill(ctx, st.get("hood"), "#2a2a30", (hb[0] - 0.05, hb[1] - 0.1, hb[0] + 0.05, hb[1]))
        if outfit == "work" and st.get("apron"):
            ap = [front((sh[0], sh[1] - 0.12 * H), chest_w * 0.6), front(hp, hip_w * 0.85),
                  (hem_front[0] + 0.01 * H, hem_front[1] - 0.12 * H), (hp[0] + 0.01 * H, hem_front[1] - 0.12 * H),
                  (sp[0] + 0.02 * H, sp[1])]
            smooth_path(ctx, ap, tension=0.3)
            self._shade_fill(ctx, st["apron"], "#2a1a10", (hp[0], hem_front[1] - 0.15, hem_front[0], sh[1]))
        if outfit == "dress" and st.get("cardigan"):
            cd = [(nk[0] - 0.035 * H, nk[1] - 0.012 * H), sh_top_b, back(sp, belly_w * 0.7),
                  back(hp, hip_w * 0.85), (hem_back[0] + 0.03 * H, hp[1] - 0.24 * H),
                  (hp[0] + 0.02 * H, hp[1] - 0.24 * H), front(sp, belly_w * 0.4),
                  front((sh[0], sh[1] - 0.06 * H), chest_w * 0.4), (nk[0] + 0.02 * H, nk[1] - 0.03 * H)]
            smooth_path(ctx, cd, tension=0.5)
            self._shade_fill(ctx, st["cardigan"], st["cardigan_sh"], (hem_back[0], hp[1] - 0.25, hp[0] + 0.1, nk[1]))
        sk["torso_front"] = front(sp, belly_w * 0.62)

    def _garment_over(self, ctx, sk):
        pass

    # -------------------------------------------------------------- brazos
    def _arm(self, ctx, sk, side):
        st, H, P = self.st, self.H, sk["P"]
        sh, el, wr = sk["sh_" + side], sk["el_" + side], sk["wr_" + side]
        k = 1.0 if side == "f" else 0.8
        sleeve = st["coat"] if st["outfit"] not in ("shirt", "dress") else st["shirt"]
        if st["outfit"] == "dress":
            sleeve = st.get("cardigan") or st["shirt"]
        sl_sh = st.get("coat_sh", shade(sleeve, 0.6)) if st["outfit"] != "dress" else (
            st.get("cardigan_sh") or shade(sleeve, 0.6))
        rolled = st.get("sleeves_rolled")
        if st["outfit"] == "toga":
            # manga ancha de toga
            mid = ((el[0] + wr[0]) / 2, (el[1] + wr[1]) / 2)
            self._limb(ctx, [sh, el, mid], [0.07 * H, 0.075 * H, 0.1 * H], shade(sleeve, k), sl_sh)
            # puñeta de encaje
            setc(ctx, st["lace"], 0.95)
            ellipse(ctx, mid[0], mid[1], 0.03 * H, 0.018 * H, sk["fa_ang_" + side] + math.pi / 2)
            ctx.fill()
        elif rolled:
            self._limb(ctx, [sh, el], [0.06 * H, 0.05 * H], shade(sleeve, k), sl_sh)
            self._limb(ctx, [el, wr], [0.042 * H, 0.032 * H], shade(st["skin"], k), st["skin_sh"])
            setc(ctx, shade(sleeve, 0.85 * k))
            ellipse(ctx, el[0], el[1], 0.04 * H, 0.025 * H, sk["fa_ang_" + side])
            ctx.fill()
        else:
            self._limb(ctx, [sh, el, wr], [0.06 * H, 0.05 * H, 0.04 * H], shade(sleeve, k), sl_sh)
            setc(ctx, st["shirt"] if st["outfit"] in ("suit", "coat") else shade(sleeve, 0.8))
            ellipse(ctx, wr[0], wr[1], 0.022 * H, 0.012 * H, sk["fa_ang_" + side] + math.pi / 2)
            ctx.fill()
        self._hand(ctx, wr, sk["fa_ang_" + side], P["hand_" + side], k,
                   P["hold"] if side == "f" else P["hold_b"])

    def _back_arm(self, ctx, sk):
        self._arm(ctx, sk, "b")

    def _front_arm(self, ctx, sk):
        self._arm(ctx, sk, "f")

    def _hand(self, ctx, wr, ang, kind, k, hold):
        st, H = self.st, self.H
        ctx.save()
        ctx.translate(*wr)
        ctx.rotate(ang)
        s = H / 1.8
        # mano en coordenadas: el antebrazo apunta hacia -y local tras rotar (ángulo desde abajo)
        skin = shade(st["skin"], k)
        if kind == "open":
            pts = [(-0.025, 0.0), (0.03, -0.01), (0.045, -0.06), (0.03, -0.11), (0.0, -0.115), (-0.025, -0.06)]
        elif kind == "fist" or hold:
            pts = [(-0.028, 0.0), (0.028, -0.005), (0.035, -0.05), (0.02, -0.075), (-0.02, -0.075), (-0.032, -0.04)]
        elif kind == "point":
            pts = [(-0.028, 0.0), (0.028, -0.005), (0.035, -0.05), (0.02, -0.15), (0.008, -0.15), (-0.02, -0.075),
                   (-0.032, -0.04)]
        else:
            pts = [(-0.025, 0.0), (0.028, -0.008), (0.035, -0.055), (0.02, -0.1), (-0.005, -0.105), (-0.03, -0.055)]
        pts = [(x * s, y * s) for x, y in pts]
        smooth_path(ctx, pts, tension=0.6)
        self._shade_fill(ctx, skin, st["skin_sh"], (-0.04 * s, -0.12 * s, 0.05 * s, 0.0), strength=0.7)
        # pulgar
        setc(ctx, shade(skin, 0.95))
        ellipse(ctx, 0.03 * s, -0.035 * s, 0.012 * s, 0.024 * s, 0.4)
        ctx.fill()
        if hold:
            self._held(ctx, hold, s)
        ctx.restore()

    def _held(self, ctx, hold, s):
        if hold == "folder":
            setc(ctx, "#8a5a32")
            poly(ctx, [(-0.02 * s, -0.04 * s), (0.25 * s, -0.04 * s), (0.25 * s, -0.08 * s), (-0.02 * s, -0.08 * s)])
            ctx.fill()
        elif hold == "branch":
            pts = [(0, -0.05 * s), (0.25 * s, -0.12 * s), (0.6 * s, -0.12 * s), (0.9 * s, -0.2 * s)]
            setc(ctx, "#5a4028")
            ctx.set_line_width(0.025 * s)
            ctx.move_to(*pts[0])
            for p in pts[1:]:
                ctx.line_to(*p)
            ctx.stroke()
            for i, (lx, ly) in enumerate([(0.35, -0.1), (0.55, -0.16), (0.7, -0.12), (0.85, -0.22), (0.45, -0.15)]):
                setc(ctx, ["#5c7a3a", "#6f8f45", "#4f6a30"][i % 3])
                ellipse(ctx, lx * s, ly * s, 0.06 * s, 0.025 * s, 0.6 * (i % 2 * 2 - 1))
                ctx.fill()
        elif hold == "shears":
            setc(ctx, "#4a4a4a")
            ctx.set_line_width(0.015 * s)
            ctx.move_to(0, -0.05 * s)
            ctx.line_to(0.02 * s, -0.25 * s)
            ctx.stroke()
            setc(ctx, "#b8b8b8")
            poly(ctx, [(0.01 * s, -0.24 * s), (0.04 * s, -0.36 * s), (0.025 * s, -0.24 * s)])
            ctx.fill()
        elif hold == "cup":
            setc(ctx, "#e8e0d0")
            rrect_local(ctx, -0.03 * s, -0.09 * s, 0.07 * s, 0.07 * s)
            ctx.fill()
        elif hold == "ball":
            setc(ctx, "#c8402a")
            ellipse(ctx, 0.0, -0.1 * s, 0.06 * s, 0.06 * s)
            ctx.fill()

    # -------------------------------------------------------------- cabeza
    def _head(self, ctx, sk):
        st, H, P = self.st, self.H, sk["P"]
        hc = sk["head"]
        hs = 0.132 * H if st["face"] != "child" else 0.19 * H  # barbilla-coronilla: 1/7.5 de la altura
        ang = -sk["head_ang"]
        face = st["face"]
        # cuello
        nk = sk["neck"]
        self._limb(ctx, [nk, (hc[0] - 0.008 * H, hc[1] - 0.035 * H)], [0.055 * H, 0.046 * H], st["skin"], st["skin_sh"])
        # sombra de la mandíbula sobre el cuello (oclusión)
        chin = rot((0.1 * hs, -0.42 * hs), ang)
        g = cairo.RadialGradient(hc[0] + chin[0], hc[1] + chin[1] - 0.02 * H, 0, hc[0] + chin[0],
                                 hc[1] + chin[1] - 0.02 * H, 0.06 * H)
        dd = hx(st["skin_sh"])
        g.add_color_stop_rgba(0, dd[0] * 0.7, dd[1] * 0.6, dd[2] * 0.6, 0.6)
        g.add_color_stop_rgba(1, dd[0], dd[1], dd[2], 0.0)
        ctx.save()
        self._limb_path(ctx, [nk, (hc[0] - 0.008 * H, hc[1] - 0.035 * H)], [0.055 * H, 0.046 * H])
        ctx.clip()
        ctx.set_source(g)
        ctx.paint()
        ctx.restore()
        ctx.save()
        ctx.translate(*hc)
        ctx.rotate(ang)
        ctx.scale(hs, hs)
        lw = self.lw / hs
        # pelo largo detrás de la cabeza
        lag = 0.04 * math.sin(P["hair_lag"])
        if st["hair_style"] in ("long",):
            setc(ctx, shade(st["hair"], 0.8))
            smooth_path(ctx, [(0.1, 0.48), (-0.42, 0.35), (-0.5 + lag, -0.2), (-0.42 + lag, -0.95),
                              (-0.1 + lag, -0.98), (-0.12, -0.3), (0.05, 0.0)], tension=0.5)
            ctx.fill()
        if st["hair_style"] == "ponytail":
            setc(ctx, st["hair"])
            smooth_path(ctx, [(-0.38, 0.32), (-0.62 + lag, 0.2), (-0.7 + lag * 2, -0.25), (-0.55 + lag * 2, -0.35),
                              (-0.5, 0.0), (-0.38, 0.15)], tension=0.5)
            ctx.fill()
        # perfil de la cara
        mo = P["mouth"]
        jaw = mo * 0.07
        if face == "female":
            prof = [(0.0, 0.5), (0.3, 0.38), (0.37, 0.14), (0.35, 0.06), (0.44, -0.08), (0.36, -0.14),
                    (0.38, -0.21), (0.34, -0.25 - jaw * 0.6), (0.37, -0.31 - jaw), (0.31, -0.42 - jaw),
                    (0.17, -0.48 - jaw * 0.5), (-0.05, -0.36), (-0.3, -0.2), (-0.42, 0.08), (-0.34, 0.36)]
        elif face == "child":
            prof = [(0.0, 0.5), (0.32, 0.36), (0.38, 0.1), (0.36, 0.02), (0.42, -0.1), (0.35, -0.15),
                    (0.36, -0.22), (0.33, -0.25 - jaw * 0.6), (0.35, -0.3 - jaw), (0.28, -0.4 - jaw),
                    (0.12, -0.44 - jaw * 0.5), (-0.1, -0.34), (-0.36, -0.15), (-0.46, 0.1), (-0.36, 0.38)]
        else:
            nose = 0.5 if face in ("male", "old", "weathered") else 0.47
            prof = [(0.0, 0.5), (0.31, 0.38), (0.4, 0.14), (0.37, 0.07), (nose, -0.1), (0.39, -0.16),
                    (0.4, -0.23), (0.36, -0.27 - jaw * 0.6), (0.39, -0.32 - jaw), (0.35, -0.44 - jaw),
                    (0.2, -0.5 - jaw * 0.5), (-0.05, -0.38), (-0.3, -0.24), (-0.43, 0.06), (-0.35, 0.36)]
        smooth_path(ctx, prof, tension=0.55)
        self._shade_fill(ctx, st["skin"], st["skin_sh"], (-0.45, -0.5, 0.5, 0.5), strength=0.8)
        # rubor/calidez en mejilla
        setc(ctx, "#d06a5a", 0.12 if face in ("female", "child") else 0.07)
        ellipse(ctx, 0.2, -0.12, 0.1, 0.07)
        ctx.fill()
        # boca abierta
        if mo > 0.05:
            setc(ctx, "#4a1e1e")
            ellipse(ctx, 0.345, -0.27 - jaw * 0.5, 0.035, 0.012 + jaw * 0.45)
            ctx.fill()
        else:
            setc(ctx, shade(st["skin_sh"], 0.8), 0.9)
            ctx.set_line_width(lw * 2.2)
            ctx.move_to(0.3, -0.27 + 0.01 * P["smile"])
            ctx.curve_to(0.33, -0.275, 0.36, -0.272, 0.385, -0.268 - 0.015 * P["smile"])
            ctx.stroke()
        # oreja
        setc(ctx, st["skin"])
        ellipse(ctx, -0.08, -0.02, 0.075, 0.12, 0.15)
        ctx.fill()
        setc(ctx, st["skin_sh"], 0.7)
        ctx.set_line_width(lw * 2)
        ellipse(ctx, -0.075, -0.02, 0.045, 0.085, 0.15)
        ctx.stroke()
        # ojo: esclerótica, iris, párpado, brillo
        ex, ey = 0.26, 0.04
        bl = max(P["blink"], 0.0)
        look = P["look"] * 0.03
        setc(ctx, "#f4efe8")
        smooth_path(ctx, [(ex - 0.06, ey + 0.005), (ex + 0.0, ey + 0.035 * (1 - bl)), (ex + 0.075, ey + 0.012),
                          (ex + 0.005, ey - 0.03 * (1 - bl))], tension=0.6)
        ctx.fill_preserve()
        ctx.save()
        ctx.clip()
        setc(ctx, {"male": "#4a3626", "female": "#3e6a4a", "child": "#3e6a4a", "young": "#2e2018",
                   "old": "#5a7a8a", "weathered": "#4a3a2a"}[face])
        ellipse(ctx, ex + 0.035, ey + 0.003 + look, 0.03, 0.034)
        ctx.fill()
        setc(ctx, "#0e0a08")
        ellipse(ctx, ex + 0.045, ey + 0.003 + look, 0.014, 0.017)
        ctx.fill()
        setc(ctx, "#ffffff", 0.9)
        ellipse(ctx, ex + 0.052, ey + 0.016 + look, 0.007, 0.007)
        ctx.fill()
        ctx.restore()
        # párpado superior y pestañas
        setc(ctx, shade(st["skin_sh"], 0.6))
        ctx.set_line_width(lw * (3.5 if face in ("female", "child") else 2.5))
        ctx.move_to(ex - 0.06, ey + 0.006)
        ctx.curve_to(ex - 0.01, ey + 0.04 * (1 - bl), ex + 0.04, ey + 0.035 * (1 - bl), ex + 0.078, ey + 0.012)
        ctx.stroke()
        if bl > 0.5:
            setc(ctx, st["skin"])
            smooth_path(ctx, [(ex - 0.06, ey + 0.006), (ex + 0.0, ey + 0.04), (ex + 0.078, ey + 0.012),
                              (ex + 0.0, ey - 0.005)], tension=0.6)
            ctx.fill()
        # ceja (expresión: brow>0 fruncida, <0 alzada)
        br = P["brow"]
        setc(ctx, st["brows"])
        ctx.set_line_width(lw * (5 if face not in ("female", "child") else 3.5))
        ctx.move_to(ex - 0.07, ey + 0.085 + 0.02 * (-br))
        ctx.curve_to(ex - 0.01, ey + 0.115 - 0.015 * br, ex + 0.05, ey + 0.11 - 0.03 * br, ex + 0.1,
                     ey + 0.085 - 0.035 * br)
        ctx.stroke()
        # arrugas (edad)
        if face in ("old", "weathered"):
            setc(ctx, st["skin_sh"], 0.6)
            ctx.set_line_width(lw * 1.6)
            for dy in (0.0, 0.035):
                ctx.move_to(0.18, 0.22 + dy)
                ctx.curve_to(0.24, 0.235 + dy, 0.3, 0.23 + dy, 0.35, 0.215 + dy)
            ctx.move_to(0.34, -0.15)
            ctx.curve_to(0.3, -0.2, 0.28, -0.25, 0.27, -0.3)
            ctx.move_to(ex + 0.08, ey)
            ctx.line_to(ex + 0.11, ey - 0.03)
            ctx.stroke()
        elif face == "male":
            setc(ctx, st["skin_sh"], 0.35)
            ctx.set_line_width(lw * 1.4)
            ctx.move_to(0.36, -0.15)
            ctx.curve_to(0.32, -0.2, 0.3, -0.24, 0.29, -0.27)
            ctx.stroke()
        # barba / bigote
        if st.get("beard"):
            setc(ctx, st["beard"])
            smooth_path(ctx, [(-0.05, -0.08), (0.12, -0.16), (0.3, -0.2), (0.42, -0.22), (0.41, -0.36 - jaw),
                              (0.33, -0.5 - jaw), (0.14, -0.58 - jaw * 0.5), (-0.06, -0.42), (-0.12, -0.18)],
                        tension=0.5)
            ctx.fill()
            setc(ctx, "#4a1e1e" if mo > 0.05 else shade(st["beard"], 0.6))
            ellipse(ctx, 0.36, -0.27 - jaw * 0.5, 0.04, 0.01 + jaw * 0.4)
            ctx.fill()
        if st.get("mustache"):
            setc(ctx, st["mustache"])
            smooth_path(ctx, [(0.27, -0.19), (0.4, -0.18), (0.42, -0.23), (0.3, -0.245), (0.24, -0.23)], tension=0.5)
            ctx.fill()
        # pelo
        self._hair(ctx, st, lw, lag)
        # gafas
        if st.get("glasses"):
            setc(ctx, "#2a2420")
            ctx.set_line_width(lw * 3)
            ellipse(ctx, ex + 0.03, ey, 0.075, 0.06)
            ctx.stroke()
            ctx.move_to(ex - 0.045, ey + 0.01)
            ctx.line_to(-0.06, 0.02)
            ctx.stroke()
            setc(ctx, "#ffffff", 0.15)
            ellipse(ctx, ex + 0.04, ey + 0.02, 0.05, 0.03)
            ctx.fill()
        ctx.restore()

    def _hair(self, ctx, st, lw, lag):
        hs = st["hair_style"]
        hc, hh = st["hair"], st.get("hair_hi", st["hair"])
        if hs in ("short", "short_grey", "curly", "bob", "long", "bun", "ponytail"):
            if hs == "curly":
                pts = [(0.32, 0.36), (0.25, 0.52), (0.0, 0.6), (-0.3, 0.52), (-0.46, 0.25), (-0.45, -0.05),
                       (-0.3, -0.15), (-0.2, 0.05), (-0.04, 0.12), (0.12, 0.25), (0.28, 0.3)]
            elif hs in ("long", "bob", "ponytail", "bun"):
                pts = [(0.33, 0.33), (0.22, 0.5), (-0.05, 0.56), (-0.36, 0.45), (-0.46, 0.15), (-0.44, -0.18),
                       (-0.28, -0.1), (-0.18, 0.08), (0.02, 0.2), (0.2, 0.26), (0.32, 0.25)]
            else:
                pts = [(0.31, 0.36), (0.2, 0.5), (-0.05, 0.54), (-0.34, 0.44), (-0.45, 0.18), (-0.43, -0.12),
                       (-0.3, -0.18), (-0.24, 0.0), (-0.12, 0.1), (0.05, 0.2), (0.22, 0.28)]
            smooth_path(ctx, pts, tension=0.55)
            self._shade_fill(ctx, hc, shade(hc, 0.45), (-0.46, -0.2, 0.33, 0.6), outline=False)
            # brillo especular del pelo (banda suave) y sombra inferior
            setc(ctx, hh, 0.28)
            ctx.set_line_width(lw * 10)
            ctx.move_to(0.18, 0.47)
            ctx.curve_to(0.0, 0.56, -0.25, 0.5, -0.36, 0.33)
            ctx.stroke()
            setc(ctx, hh, 0.18)
            ctx.set_line_width(lw * 3)
            for i in range(5):
                x0 = 0.2 - i * 0.12
                ctx.move_to(x0, 0.52 - i * 0.02)
                ctx.curve_to(x0 - 0.06, 0.45, x0 - 0.1, 0.35, x0 - 0.13, 0.22)
            ctx.stroke()
            if hs == "short_grey":
                # sal y pimienta: canas en sienes y nuca, fundidas
                ctx.save()
                smooth_path(ctx, pts, tension=0.55)
                ctx.clip()
                ctx.set_source(lin_grad(0.1, 0.3, -0.45, -0.1, [(0, (0.6, 0.58, 0.55, 0.0)),
                                                                (1, (0.72, 0.7, 0.67, 0.75))]))
                ctx.paint()
                ctx.restore()
            if hs == "curly":
                for i in range(22):
                    a = i / 22 * math.pi * 1.25 - 0.05
                    r = 0.47 + 0.03 * math.sin(i * 2.3)
                    cx_, cy_ = -0.06 + r * math.cos(a), 0.05 + r * math.sin(a) * 0.95
                    setc(ctx, hc)
                    ellipse(ctx, cx_, cy_, 0.07, 0.065)
                    ctx.fill()
                    setc(ctx, hh, 0.45)
                    ellipse(ctx, cx_ + 0.01, cy_ + 0.02, 0.03, 0.02)
                    ctx.fill()
            if hs == "bun":
                setc(ctx, hc)
                ellipse(ctx, -0.38, 0.4, 0.15, 0.13)
                ctx.fill()
            if hs == "bob":
                setc(ctx, hc)
                smooth_path(ctx, [(-0.44, 0.2), (-0.5, -0.25), (-0.2, -0.32), (-0.18, 0.0)])
                ctx.fill()
        elif hs == "bald_white":
            setc(ctx, hc)
            smooth_path(ctx, [(-0.2, 0.18), (-0.4, 0.3), (-0.47, 0.05), (-0.38, -0.18), (-0.22, -0.1), (-0.15, 0.05)])
            ctx.fill()
            setc(ctx, "#ffffff", 0.25)
            ellipse(ctx, 0.05, 0.42, 0.14, 0.05, -0.2)
            ctx.fill()
        elif hs in ("hat", "cap"):
            setc(ctx, hc)
            smooth_path(ctx, [(-0.2, 0.15), (-0.42, 0.25), (-0.46, 0.0), (-0.36, -0.15), (-0.22, -0.05)])
            ctx.fill()
            hat, hat_sh = st.get("hat", "#c8a868"), st.get("hat_sh", "#8a6a3a")
            if hs == "hat":
                smooth_path(ctx, [(-0.75, 0.3), (0.62, 0.36), (0.66, 0.4), (0.0, 0.45), (-0.76, 0.36)], tension=0.4)
                self._shade_fill(ctx, hat, hat_sh, (-0.76, 0.28, 0.66, 0.46), strength=0.6)
                smooth_path(ctx, [(-0.38, 0.38), (-0.34, 0.72), (0.02, 0.8), (0.3, 0.7), (0.32, 0.4)], tension=0.5)
                self._shade_fill(ctx, hat, hat_sh, (-0.38, 0.38, 0.32, 0.8), strength=0.6)
                setc(ctx, "#6a4a2a")
                poly(ctx, [(-0.36, 0.4), (0.32, 0.43), (0.32, 0.49), (-0.36, 0.47)])
                ctx.fill()
            else:
                smooth_path(ctx, [(-0.44, 0.22), (-0.3, 0.55), (0.1, 0.6), (0.33, 0.42), (0.58, 0.36), (0.3, 0.3)],
                            tension=0.5)
                self._shade_fill(ctx, hat, hat_sh, (-0.44, 0.22, 0.58, 0.6))


def rrect_local(ctx, x, y, w, h):
    ctx.rectangle(x, y, w, h)
