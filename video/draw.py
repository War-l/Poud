"""Primitivas de dibujo con Cairo: utilidades, personajes articulados y decorados."""
import math
import random

import cairo

W, H = 1920, 1080


# ---------------------------------------------------------------- utilidades
def hexc(h, a=1.0):
    h = h.lstrip("#")
    return (int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255, a)


def mix(c1, c2, u):
    a, b = hexc(c1) if isinstance(c1, str) else c1, hexc(c2) if isinstance(c2, str) else c2
    return tuple(a[i] + (b[i] - a[i]) * u for i in range(4))


def shade(c, f):
    r, g, b, a = hexc(c) if isinstance(c, str) else c
    return (r * f, g * f, b * f, a)


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def lerp(a, b, u):
    return a + (b - a) * u


def smooth(u):
    u = clamp(u)
    return u * u * (3 - 2 * u)


def ramp(t, t0, t1):
    """0 antes de t0, 1 después de t1, suavizado entre medias."""
    if t1 <= t0:
        return 1.0 if t >= t1 else 0.0
    return smooth((t - t0) / (t1 - t0))


def setc(ctx, c, a=None):
    r, g, b, aa = hexc(c) if isinstance(c, str) else c
    ctx.set_source_rgba(r, g, b, aa if a is None else a)


def ellipse(ctx, x, y, rx, ry):
    ctx.save()
    ctx.translate(x, y)
    ctx.scale(max(rx, 0.01), max(ry, 0.01))
    ctx.arc(0, 0, 1, 0, 2 * math.pi)
    ctx.restore()


def rrect(ctx, x, y, w, h, r):
    r = min(r, w / 2, h / 2)
    ctx.new_sub_path()
    ctx.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    ctx.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    ctx.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    ctx.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    ctx.close_path()


def vgrad(y0, y1, stops):
    g = cairo.LinearGradient(0, y0, 0, y1)
    for off, c in stops:
        g.add_color_stop_rgba(off, *(hexc(c) if isinstance(c, str) else c))
    return g


def rgrad(x, y, r0, r1, stops):
    g = cairo.RadialGradient(x, y, r0, x, y, r1)
    for off, c in stops:
        g.add_color_stop_rgba(off, *(hexc(c) if isinstance(c, str) else c))
    return g


# ---------------------------------------------------------------- personajes
# Unidades locales: altura total = 100, pies en (0, 0), mirando a +x.
STYLES = {
    "maestro": dict(robe="#7b5a3c", robe2="#5e4430", sash="#e2cfa6", skin="#d9a77a",
                    hair="bald", hair_c="#ece6dc", beard="#ece6dc", long=True, staff=True, legs="#4a3628"),
    "alumno": dict(robe="#3f6f9f", robe2="#2f557c", sash="#d8b56a", skin="#e2b48a",
                   hair="short", hair_c="#2b1d14", long=False, legs="#2c3646"),
    "joven": dict(robe="#c4533e", robe2="#97402f", sash="#f1d39a", skin="#d79c70",
                  hair="short", hair_c="#3a2416", long=False, legs="#3b3b4c"),
    "anciano": dict(robe="#7d7466", robe2="#5f574b", sash="#6b5b45", skin="#c78f63",
                    hair="grey", hair_c="#b8b2a8", beard="#b8b2a8", long=True, legs="#4b443b",
                    patches=True),
    "hombre": dict(robe="#4f7a5a", robe2="#3c5e45", sash="#c9a86a", skin="#cf9a6c",
                   hair="hat", hair_c="#5a4632", long=False, legs="#3a3226"),
    "mujer": dict(robe="#b8674a", robe2="#8e4f39", sash="#f0dfb8", skin="#e8bf96",
                  hair="bun", hair_c="#4a2c1c", long=True, legs="#5a3a2a"),
}


def crowd_style(seed):
    rnd = random.Random(seed)
    robes = ["#8a6d9e", "#5e8c8a", "#c08a3e", "#9a4f4f", "#4d6a8f", "#7f8f4e", "#a0705a", "#6a5a7a"]
    skins = ["#e8bf96", "#d9a77a", "#b98258", "#8d5a3b", "#f0c9a0"]
    hairs = ["short", "bun", "hat", "short", "bald"]
    r = rnd.choice(robes)
    return dict(robe=r, robe2=shade(r, 0.78), sash=rnd.choice(["#e9d6aa", "#3a3a3a", "#d4b06a"]),
                skin=rnd.choice(skins), hair=rnd.choice(hairs),
                hair_c=rnd.choice(["#2b1d14", "#4a2c1c", "#6d4b2b", "#1e1a18", "#8a7a6a"]),
                long=rnd.random() < 0.5, legs=rnd.choice(["#3a3226", "#2c3646", "#4b443b"]))


def _knee(hip, foot, l1, l2):
    dx, dy = foot[0] - hip[0], foot[1] - hip[1]
    d = math.hypot(dx, dy)
    if d >= l1 + l2 - 0.01:
        return ((hip[0] + foot[0]) / 2, (hip[1] + foot[1]) / 2)
    a = (l1 * l1 - l2 * l2 + d * d) / (2 * d)
    hh = math.sqrt(max(l1 * l1 - a * a, 0))
    mx, my = hip[0] + a * dx / d, hip[1] + a * dy / d
    px, py = -dy / d, dx / d
    if px < 0:  # rodilla hacia delante
        px, py = -px, -py
    return (mx + hh * px, my + hh * py)


def _limb(ctx, pts, width, color):
    setc(ctx, color)
    ctx.set_line_width(width)
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    ctx.set_line_join(cairo.LINE_JOIN_ROUND)
    ctx.move_to(*pts[0])
    for p in pts[1:]:
        ctx.line_to(*p)
    ctx.stroke()


def _arm(sh, a1, a2, l1=17, l2=16):
    r1 = math.radians(a1)
    el = (sh[0] + l1 * math.sin(r1), sh[1] + l1 * math.cos(r1))
    r2 = math.radians(a1 + a2)
    ha = (el[0] + l2 * math.sin(r2), el[1] + l2 * math.cos(r2))
    return el, ha


def person(ctx, x, y, h, style, facing=1, walk=None, stride=1.0, crouch=0.0, sit=False,
           lean=0.0, tilt=0.0, armF=None, armB=None, mouth=0.0, smile=0.0, alpha=1.0,
           hold=None, shadow=True, eyes_closed=False):
    """Dibuja una persona. Devuelve la posición (en píxeles) de la mano delantera."""
    st = style
    s = h / 100.0
    if shadow:
        setc(ctx, "#000000", 0.18 * alpha)
        ellipse(ctx, x + (12 * s * facing if sit else 0), y, (34 if sit else 22) * s, 4.5 * s)
        ctx.fill()

    ctx.save()
    ctx.translate(x, y)
    ctx.scale(s * facing, s)
    if alpha < 1:
        ctx.push_group()

    # ---- esqueleto
    bob = 0.0
    if walk is not None:
        bob = -1.6 * abs(math.cos(walk)) * stride
    if sit:
        hip = (-6.0, -13.0)
        lean_t = lean
    else:
        hip = (0.0, -46.0 + 21.0 * crouch + bob)
        lean_t = lean + 28.0 * crouch
    rl = math.radians(lean_t)
    torso = 31.0
    sh = (hip[0] + torso * math.sin(rl), hip[1] - torso * math.cos(rl))

    # pies
    feet = []
    for i in (0, 1):
        if sit:
            feet.append((22.0 + 4 * i, -1.0))
        elif walk is not None:
            ph = walk + i * math.pi
            fx = 10.0 * stride * math.sin(ph)
            lift = max(0.0, math.cos(ph)) * 5.0 * stride
            feet.append((fx, -lift))
        elif crouch > 0:
            feet.append((-6.0 + 14.0 * i * crouch + (i * 3), 0.0))
        else:
            feet.append((-3.0 + 7.0 * i, 0.0))

    legc = st.get("legs", "#333333")

    def draw_legs():
        for i in (1, 0):
            f = feet[i]
            hp = (hip[0] + (1.5 if i else -1.5), hip[1])
            if sit:
                kn = (hp[0] + 17, hp[1] - 13 + 3 * i)
                col = st["robe"] if st.get("long") else legc
                _limb(ctx, [hp, kn], 11.0, shade(col, 0.85 if i else 1.0))
                _limb(ctx, [kn, f], 7.0, shade(legc, 0.8 if i else 1.0))
            else:
                kn = _knee(hp, f, 24.0, 23.0)
                _limb(ctx, [hp, kn, f], 7.0, shade(legc, 0.8 if i else 1.0))
            setc(ctx, "#2a201a")
            ellipse(ctx, f[0] + 3.0, f[1] - 1.5, 5.5, 2.6)
            ctx.fill()

    if not sit:
        draw_legs()

    # brazo trasero
    swing = 0.0 if walk is None else 24.0 * math.sin(walk) * stride
    aB = armB if armB is not None else (lean_t * 0.4 - swing, 18)
    shB = (sh[0] - 2, sh[1] + 2)
    elB, haB = _arm(shB, aB[0], aB[1])
    _limb(ctx, [shB, elB, haB], 7.5, st["robe2"])
    setc(ctx, shade(st["skin"], 0.88))
    ctx.arc(haB[0], haB[1], 3.6, 0, 2 * math.pi)
    ctx.fill()

    # cuerpo / túnica
    skirt = 40.0 if st.get("long") else 18.0
    perp = (math.cos(rl), math.sin(rl))
    hem_y = min(hip[1] + skirt, -1.0)
    if sit:
        hem_y = -1.0
    hem_cx = hip[0] + (6 if sit else 2) + (1.5 * math.sin(walk) if walk is not None else 0)
    hw = 16.0 if st.get("long") else 13.5
    if sit:
        hw = 14.0
        hem_cx = hip[0] - 2
    shw = 10.5
    p_sl = (sh[0] - shw * perp[0], sh[1] - shw * perp[1])
    p_sr = (sh[0] + shw * perp[0], sh[1] + shw * perp[1])
    p_hl = (hem_cx - hw, hem_y)
    p_hr = (hem_cx + hw, hem_y)
    setc(ctx, st["robe"])
    ctx.move_to(*p_sl)
    ctx.curve_to(p_sl[0] - 4, p_sl[1] + 12, p_hl[0] + 2, p_hl[1] - 14, *p_hl)
    ctx.curve_to(p_hl[0] + 8, p_hl[1] + 2, p_hr[0] - 8, p_hr[1] + 2, *p_hr)
    ctx.curve_to(p_hr[0] - 2, p_hr[1] - 14, p_sr[0] + 4, p_sr[1] + 12, *p_sr)
    ctx.curve_to(p_sr[0] - 3, p_sr[1] - 4, p_sl[0] + 3, p_sl[1] - 4, *p_sl)
    ctx.close_path()
    ctx.fill_preserve()
    setc(ctx, "#000000", 0.10)
    ctx.set_line_width(1.2)
    ctx.stroke()
    # pliegue de sombra
    setc(ctx, st["robe2"], 0.55)
    ctx.move_to(hip[0] - 3, hip[1])
    ctx.line_to(hem_cx - 5, hem_y - 1)
    ctx.line_to(hem_cx + 1, hem_y - 1)
    ctx.close_path()
    ctx.fill()
    # cinturón
    bx, by = hip[0] + 6 * math.sin(rl), hip[1] - 6 * math.cos(rl)
    _limb(ctx, [(bx - 10 * perp[0], by - 10 * perp[1]), (bx + 10 * perp[0], by + 10 * perp[1])],
          3.2, st["sash"])
    if st.get("patches"):
        setc(ctx, "#9a8f7c")
        rrect(ctx, hip[0] + 3, hip[1] + 6, 7, 6, 1.5)
        ctx.fill()
        setc(ctx, "#5a5246")
        rrect(ctx, sh[0] - 6, sh[1] + 10, 6, 7, 1.5)
        ctx.fill()

    if sit:
        draw_legs()

    # cabeza
    rt = math.radians(lean_t * 0.5 + tilt)
    neck = (sh[0] + 3.0 * math.sin(rl), sh[1] - 3.0 * math.cos(rl))
    hc = (neck[0] + 10.5 * math.sin(rt), neck[1] - 10.5 * math.cos(rt))
    _limb(ctx, [sh, neck], 6.0, shade(st["skin"], 0.85))
    ctx.save()
    ctx.translate(*hc)
    ctx.rotate(rt)
    R = 10.5
    hair, hcol = st.get("hair"), st.get("hair_c", "#222222")
    if hair == "bun":
        setc(ctx, hcol)
        ctx.arc(-9, -6, 5.2, 0, 2 * math.pi)
        ctx.fill()
    setc(ctx, st["skin"])
    ctx.arc(0, 0, R, 0, 2 * math.pi)
    ctx.fill()
    # oreja
    setc(ctx, shade(st["skin"], 0.9))
    ellipse(ctx, -2.0, 0.5, 2.2, 3.2)
    ctx.fill()
    # nariz
    setc(ctx, st["skin"])
    ctx.move_to(9.2, -2.5)
    ctx.line_to(12.6, 1.8)
    ctx.line_to(9.0, 2.8)
    ctx.close_path()
    ctx.fill()
    # pelo
    setc(ctx, hcol)
    if hair in ("short", "bun"):
        ctx.arc(0, 0, R + 1.3, math.pi * 0.98, math.pi * 1.93)
        ctx.line_to(4, -6.5)
        ctx.curve_to(-1, -5, -5, -2, -6.5, 4)
        ctx.line_to(-R - 1.0, 3)
        ctx.close_path()
        ctx.fill()
    elif hair == "bald":
        ctx.move_to(-R - 0.8, -2)
        ctx.curve_to(-R - 2.5, 4, -6, 8, -2, 7)
        ctx.curve_to(-5, 3, -6, -1, -R - 0.8, -2)
        ctx.fill()
    elif hair == "grey":
        ctx.arc(0, 0, R + 1.6, math.pi * 0.95, math.pi * 1.9)
        ctx.curve_to(2, -7, -4, -3, -7, 6)
        ctx.line_to(-R - 1.6, 4)
        ctx.close_path()
        ctx.fill()
        for k in range(4):
            ctx.move_to(-6 + 3 * k, -R - 0.5)
            ctx.line_to(-7 + 3 * k, -R - 3.5)
        ctx.set_line_width(1.2)
        ctx.stroke()
    elif hair == "hat":
        ctx.arc(0, 0, R + 0.5, math.pi * 1.0, math.pi * 1.9)
        ctx.close_path()
        ctx.fill()
        setc(ctx, shade(hcol, 0.8))
        rrect(ctx, -9, -R - 9, 17, 10, 2.5)
        ctx.fill()
        ellipse(ctx, 0, -R + 0.5, 15, 2.6)
        ctx.fill()
    # barba
    if st.get("beard"):
        setc(ctx, st["beard"])
        ctx.move_to(-3.5, 2)
        ctx.curve_to(-2, 12, 4, 17, 6.5, 17)
        ctx.curve_to(9, 13, 11, 8, 10.4, 3.5)
        ctx.curve_to(7, 5.5, 2, 5.5, -3.5, 2)
        ctx.fill()
    # ojo
    setc(ctx, "#1d1612")
    if eyes_closed:
        ctx.set_line_width(1.1)
        ctx.move_to(3.5, -1.5)
        ctx.line_to(7.0, -1.2)
        ctx.stroke()
    else:
        ellipse(ctx, 5.6, -1.6, 1.25, 1.6)
        ctx.fill()
    # ceja
    ctx.set_line_width(1.1)
    setc(ctx, shade(hcol if hair != "bald" else "#8a7d70", 0.9))
    ctx.move_to(3.2, -5.0)
    ctx.line_to(8.0, -4.6 - smile * 0.6)
    ctx.stroke()
    # boca
    mx, my = 6.8, 5.6
    if st.get("beard"):
        my = 6.2
    setc(ctx, "#5a2a22")
    if mouth > 0.05:
        ellipse(ctx, mx, my, 1.8, 0.4 + 2.4 * mouth)
        ctx.fill()
    else:
        ctx.set_line_width(1.0)
        ctx.move_to(mx - 1.8, my)
        ctx.curve_to(mx - 0.5, my + 1.4 * smile, mx + 0.6, my + 1.4 * smile, mx + 1.9, my - 0.3 * smile)
        ctx.stroke()
    ctx.restore()

    # bastón
    aF = armF if armF is not None else (lean_t * 0.4 + swing, 22)
    shF = (sh[0] + 2, sh[1] + 2)
    elF, haF = _arm(shF, aF[0], aF[1])
    if st.get("staff"):
        _limb(ctx, [(haF[0] + 1, haF[1] - 26), (haF[0] + 3, 0)], 2.6, "#6b4a2a")
    # objeto en mano
    if hold == "coin":
        setc(ctx, "#f2cf4a")
        ellipse(ctx, haF[0] + 3, haF[1] - 1, 3.0, 3.0)
        ctx.fill()
    elif hold == "bread":
        setc(ctx, "#c98b46")
        ellipse(ctx, haF[0] + 3, haF[1] - 1, 7.0, 3.6)
        ctx.fill()
    elif hold == "bag":
        setc(ctx, "#8a6a3e")
        ellipse(ctx, haF[0] + 1, haF[1] + 6, 6, 7)
        ctx.fill()
    _limb(ctx, [shF, elF, haF], 7.5, st["robe"])
    setc(ctx, st["skin"])
    ctx.arc(haF[0], haF[1], 3.6, 0, 2 * math.pi)
    ctx.fill()

    if alpha < 1:
        ctx.pop_group_to_source()
        ctx.paint_with_alpha(alpha)
    ctx.restore()
    return (x + haF[0] * s * facing, y + haF[1] * s)


# ---------------------------------------------------------------- decorados
def _buildings(ctx, width, horizon, rnd, palette, roof, win, shutter, lit=0.0, dark=0.0):
    x = -40
    while x < width + 40:
        bw = rnd.randint(170, 320)
        bh = rnd.randint(230, 420)
        col = rnd.choice(palette)
        top = horizon - bh
        setc(ctx, mix(col, "#2a2238", dark))
        ctx.rectangle(x, top, bw, bh + 4)
        ctx.fill()
        # sombra lateral
        setc(ctx, "#000000", 0.08 + 0.1 * dark)
        ctx.rectangle(x + bw - 14, top, 14, bh + 4)
        ctx.fill()
        # tejado
        setc(ctx, mix(roof, "#2a1a24", dark))
        if rnd.random() < 0.5:
            ctx.move_to(x - 10, top)
            ctx.line_to(x + bw / 2, top - rnd.randint(40, 70))
            ctx.line_to(x + bw + 10, top)
            ctx.close_path()
        else:
            ctx.rectangle(x - 8, top - 16, bw + 16, 18)
        ctx.fill()
        # ventanas
        cols = max(2, bw // 80)
        rows = max(2, (bh - 90) // 95)
        for r in range(rows):
            for c in range(cols):
                wx = x + (c + 0.5) * bw / cols - 16
                wy = top + 40 + r * 95
                if wy + 50 > horizon - 50:
                    continue
                if rnd.random() < lit:
                    setc(ctx, "#ffd27a")
                    rrect(ctx, wx, wy, 32, 50, 12)
                    ctx.fill()
                    g = rgrad(wx + 16, wy + 25, 2, 60, [(0, hexc("#ffcc66", 0.35)), (1, hexc("#ffcc66", 0))])
                    ctx.set_source(g)
                    ctx.arc(wx + 16, wy + 25, 60, 0, 2 * math.pi)
                    ctx.fill()
                else:
                    setc(ctx, mix(win, "#141020", dark))
                    rrect(ctx, wx, wy, 32, 50, 12)
                    ctx.fill()
                    if shutter and dark < 0.5:
                        setc(ctx, shutter)
                        ctx.rectangle(wx - 9, wy + 4, 7, 46)
                        ctx.rectangle(wx + 34, wy + 4, 7, 46)
                        ctx.fill()
        # puerta / arco
        if rnd.random() < 0.6:
            dx = x + rnd.randint(20, max(21, bw - 80))
            setc(ctx, mix("#5a3d2a", "#120c14", dark))
            ctx.move_to(dx, horizon)
            ctx.line_to(dx, horizon - 70)
            ctx.arc(dx + 28, horizon - 70, 28, math.pi, 2 * math.pi)
            ctx.line_to(dx + 56, horizon)
            ctx.close_path()
            ctx.fill()
        x += bw + rnd.randint(-6, 6)


def _ground(ctx, width, horizon, c_far, c_near, line, rnd, lines_alpha=0.18):
    ctx.set_source(vgrad(horizon, H, [(0, c_far), (1, c_near)]))
    ctx.rectangle(0, horizon, width, H - horizon)
    ctx.fill()
    # adoquines con perspectiva
    y = horizon + 6
    hrow = 10
    row = 0
    while y < H:
        setc(ctx, line, lines_alpha)
        ctx.set_line_width(1.0 + row * 0.12)
        off = rnd.uniform(0, hrow * 4)
        sw = hrow * 4.2
        xx = -off
        while xx < width:
            rrect(ctx, xx + 2, y + 1, sw - 4, hrow - 2, hrow * 0.35)
            ctx.stroke()
            xx += sw
        y += hrow
        hrow *= 1.12
        row += 1


def bg_plaza(mood="day", width=2200):
    """Plaza. mood: morning | day | dusk."""
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, H)
    ctx = cairo.Context(surf)
    rnd = random.Random(7)
    horizon = 690
    if mood == "dusk":
        sky = [(0, "#26244a"), (0.45, "#6b3f6e"), (0.8, "#e0835a"), (1, "#f4b46e")]
    elif mood == "morning":
        sky = [(0, "#8fbfdc"), (0.6, "#f2d7b0"), (1, "#f8e6c4")]
    else:
        sky = [(0, "#79b4dc"), (0.7, "#cfe5ee"), (1, "#f1e6cf")]
    ctx.set_source(vgrad(0, horizon, sky))
    ctx.rectangle(0, 0, width, horizon)
    ctx.fill()
    # sol
    if mood == "dusk":
        sx, sy, sr, sc = width * 0.62, horizon - 70, 95, "#ffb36b"
    elif mood == "morning":
        sx, sy, sr, sc = width * 0.25, 210, 60, "#fff1c9"
    else:
        sx, sy, sr, sc = width * 0.7, 150, 55, "#fffbe8"
    ctx.set_source(rgrad(sx, sy, sr * 0.6, sr * 5, [(0, hexc(sc, 0.55)), (1, hexc(sc, 0))]))
    ctx.rectangle(0, 0, width, horizon)
    ctx.fill()
    setc(ctx, sc)
    ctx.arc(sx, sy, sr, 0, 2 * math.pi)
    ctx.fill()
    # nubes
    for _ in range(7):
        cx, cy = rnd.uniform(0, width), rnd.uniform(70, 330)
        cc = "#ffffff" if mood != "dusk" else "#f0a07a"
        for k in range(5):
            setc(ctx, cc, 0.55 if mood != "dusk" else 0.35)
            ellipse(ctx, cx + k * 38 - 80, cy + rnd.uniform(-12, 12), rnd.uniform(50, 80), rnd.uniform(18, 30))
            ctx.fill()
    # torre de iglesia lejana
    tx = width * 0.45
    setc(ctx, mix("#c9a27c", "#3a2a40", 0.75 if mood == "dusk" else 0.0))
    ctx.rectangle(tx, horizon - 560, 110, 560)
    ctx.fill()
    ctx.move_to(tx - 12, horizon - 560)
    ctx.line_to(tx + 55, horizon - 680)
    ctx.line_to(tx + 122, horizon - 560)
    ctx.close_path()
    ctx.fill()
    setc(ctx, "#3a2a22" if mood != "dusk" else "#ffd27a")
    ctx.arc(tx + 55, horizon - 470, 26, math.pi, 2 * math.pi)
    ctx.line_to(tx + 81, horizon - 420)
    ctx.line_to(tx + 29, horizon - 420)
    ctx.close_path()
    ctx.fill()
    dark = 0.72 if mood == "dusk" else 0.0
    _buildings(ctx, width, horizon, rnd,
               ["#e9c89b", "#d9a77c", "#efd9b4", "#c98f6a", "#e4b98d", "#d7b38f"],
               "#a8553a", "#5a4636", "#6f8f7a", lit=0.45 if mood == "dusk" else 0.0, dark=dark)
    # árboles
    for tx2 in (width * 0.15, width * 0.8):
        setc(ctx, "#5a3d2a" if mood != "dusk" else "#2a1a20")
        ctx.rectangle(tx2 - 9, horizon - 120, 18, 125)
        ctx.fill()
        for k in range(6):
            setc(ctx, mix("#6f9a55" if k % 2 else "#5d8648", "#1f1a2c", dark * 0.9))
            ctx.arc(tx2 + rnd.uniform(-60, 60), horizon - 170 + rnd.uniform(-60, 30), rnd.uniform(45, 70), 0,
                    2 * math.pi)
            ctx.fill()
    if mood == "dusk":
        _ground(ctx, width, horizon, "#5a4050", "#2c2232", "#000000", rnd, 0.25)
    elif mood == "morning":
        _ground(ctx, width, horizon, "#d9c19a", "#bfa07a", "#6b5236", rnd)
    else:
        _ground(ctx, width, horizon, "#d2bb96", "#b49675", "#6b5236", rnd)
    # bruma de horizonte
    hz = "#f4c08a" if mood == "dusk" else "#ffffff"
    ctx.set_source(vgrad(horizon - 60, horizon + 40,
                         [(0, hexc(hz, 0)), (0.6, hexc(hz, 0.22)), (1, hexc(hz, 0))]))
    ctx.rectangle(0, horizon - 60, width, 100)
    ctx.fill()
    return surf


def corner_wall(ctx, x0, mood="day"):
    """Esquina de un edificio en primer plano, a la derecha (escenas 2 y 5)."""
    base = "#d6ac83" if mood == "day" else "#e3b98b"
    ctx.set_source(vgrad(0, 1000, [(0, base), (1, shade(base, 0.82))]))
    ctx.move_to(x0, -20)
    ctx.line_to(W + 300, -20)
    ctx.line_to(W + 300, H + 40)
    ctx.line_to(x0, H + 40)
    ctx.close_path()
    ctx.fill()
    # cara lateral (esquina)
    setc(ctx, shade(base, 0.7))
    ctx.move_to(x0, -20)
    ctx.line_to(x0 + 40, -20)
    ctx.line_to(x0 + 40, H + 40)
    ctx.line_to(x0, H + 40)
    ctx.close_path()
    ctx.fill()
    # zócalo de piedra
    setc(ctx, "#9a8b78")
    ctx.rectangle(x0, 880, W + 300 - x0, H - 840)
    ctx.fill()
    setc(ctx, "#000000", 0.15)
    ctx.set_line_width(2)
    for i in range(12):
        ctx.move_to(x0 + i * 90, 880)
        ctx.line_to(x0 + i * 90, H + 40)
    ctx.move_to(x0, 940)
    ctx.line_to(W + 300, 940)
    ctx.stroke()
    # puerta y ventana
    setc(ctx, "#5a3a26")
    ctx.move_to(x0 + 260, 880)
    ctx.line_to(x0 + 260, 640)
    ctx.arc(x0 + 340, 640, 80, math.pi, 2 * math.pi)
    ctx.line_to(x0 + 420, 880)
    ctx.close_path()
    ctx.fill()
    setc(ctx, "#3f2a1c")
    ctx.set_line_width(4)
    for i in range(1, 4):
        ctx.move_to(x0 + 260 + i * 40, 600)
        ctx.line_to(x0 + 260 + i * 40, 880)
    ctx.stroke()
    setc(ctx, "#4b3a2e")
    rrect(ctx, x0 + 120, 250, 90, 140, 40)
    ctx.fill()
    setc(ctx, "#6f8f7a")
    ctx.rectangle(x0 + 96, 260, 20, 130)
    ctx.rectangle(x0 + 214, 260, 20, 130)
    ctx.fill()
    # macetas
    for k in range(3):
        setc(ctx, "#b5552f")
        ctx.rectangle(x0 + 118 + k * 32, 392, 26, 22)
        ctx.fill()
        setc(ctx, "#d94a4a" if k != 1 else "#f2c14a")
        ctx.arc(x0 + 131 + k * 32, 386, 12, 0, 2 * math.pi)
        ctx.fill()


def bg_workshop():
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W + 200, H)
    ctx = cairo.Context(surf)
    rnd = random.Random(3)
    w = W + 200
    floor_y = 860
    # pared de tablones
    ctx.set_source(vgrad(0, floor_y, [(0, "#4a3426"), (1, "#6b4c36")]))
    ctx.rectangle(0, 0, w, floor_y)
    ctx.fill()
    x = 0
    while x < w:
        pw = rnd.randint(90, 140)
        setc(ctx, "#000000", rnd.uniform(0.04, 0.14))
        ctx.rectangle(x, 0, pw, floor_y)
        ctx.fill()
        setc(ctx, "#2a1c14", 0.6)
        ctx.set_line_width(3)
        ctx.move_to(x, 0)
        ctx.line_to(x, floor_y)
        ctx.stroke()
        x += pw
    # ventana con luz
    setc(ctx, "#2e2018")
    ctx.rectangle(220, 170, 260, 300)
    ctx.fill()
    ctx.set_source(vgrad(180, 460, [(0, "#ffe9b8"), (1, "#f2c27a")]))
    ctx.rectangle(236, 186, 228, 268)
    ctx.fill()
    setc(ctx, "#2e2018")
    ctx.set_line_width(10)
    ctx.move_to(350, 186)
    ctx.line_to(350, 454)
    ctx.move_to(236, 320)
    ctx.line_to(464, 320)
    ctx.stroke()
    # estanterías
    for sy in (260, 430):
        setc(ctx, "#3a281c")
        ctx.rectangle(1450, sy, 420, 16)
        ctx.fill()
        xx = 1465
        while xx < 1850:
            kind = rnd.random()
            c = rnd.choice(["#8a5a3a", "#5d7a6a", "#a8834e", "#6a4e6e", "#9a9a8a"])
            setc(ctx, c)
            if kind < 0.4:
                hh = rnd.randint(40, 80)
                rrect(ctx, xx, sy - hh, 34, hh, 8)
            elif kind < 0.7:
                ctx.arc(xx + 20, sy - 22, 22, 0, 2 * math.pi)
            else:
                ctx.rectangle(xx, sy - 30, 60, 30)
            ctx.fill()
            xx += rnd.randint(50, 80)
    # herramientas colgadas
    for k in range(4):
        tx = 640 + k * 70
        setc(ctx, "#2a1c14")
        ctx.set_line_width(5)
        ctx.move_to(tx, 230)
        ctx.line_to(tx, 330 + k * 12)
        ctx.stroke()
        setc(ctx, "#8a8a8a")
        ctx.rectangle(tx - 12, 320 + k * 12, 24, 14)
        ctx.fill()
    # suelo de tablas
    ctx.set_source(vgrad(floor_y, H, [(0, "#7a5638"), (1, "#5a3c26")]))
    ctx.rectangle(0, floor_y, w, H - floor_y)
    ctx.fill()
    setc(ctx, "#2a1a10", 0.35)
    ctx.set_line_width(2)
    for k in range(-20, 40):
        ctx.move_to(w / 2 + k * 60, floor_y)
        ctx.line_to(w / 2 + k * 160, H)
    ctx.stroke()
    # haz de luz
    ctx.set_source(vgrad(186, 1000, [(0, hexc("#ffe6b0", 0.20)), (1, hexc("#ffe6b0", 0.0))]))
    ctx.move_to(236, 186)
    ctx.line_to(464, 186)
    ctx.line_to(980, 1040)
    ctx.line_to(520, 1040)
    ctx.close_path()
    ctx.fill()
    return surf


def vignette(strength=0.55):
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    ctx = cairo.Context(surf)
    g = cairo.RadialGradient(W / 2, H / 2, H * 0.35, W / 2, H / 2, H * 1.05)
    g.add_color_stop_rgba(0, 0, 0, 0, 0)
    g.add_color_stop_rgba(1, 0, 0, 0, strength)
    ctx.set_source(g)
    ctx.paint()
    return surf


def text(ctx, s, x, y, size, color, family="Liberation Serif", italic=False, bold=False,
         align="center", outline=None, alpha=1.0, spacing=0.0):
    ctx.select_font_face(family, cairo.FONT_SLANT_ITALIC if italic else cairo.FONT_SLANT_NORMAL,
                         cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL)
    ctx.set_font_size(size)
    if spacing:
        widths = [ctx.text_extents(ch).x_advance + spacing for ch in s]
        tw = sum(widths) - spacing
    else:
        tw = ctx.text_extents(s).x_advance
    x0 = x - tw / 2 if align == "center" else (x - tw if align == "right" else x)
    ctx.new_path()
    if spacing:
        cx = x0
        for ch, wd in zip(s, widths):
            ctx.move_to(cx, y)
            ctx.text_path(ch)
            cx += wd
    else:
        ctx.move_to(x0, y)
        ctx.text_path(s)
    if outline:
        setc(ctx, outline[0], outline[2] * alpha if len(outline) > 2 else alpha)
        ctx.set_line_width(outline[1])
        ctx.set_line_join(cairo.LINE_JOIN_ROUND)
        ctx.stroke_preserve()
    setc(ctx, color, alpha)
    ctx.fill()
    return tw


def wrap(ctx, s, size, maxw, family="Liberation Serif", italic=False):
    ctx.select_font_face(family, cairo.FONT_SLANT_ITALIC if italic else cairo.FONT_SLANT_NORMAL,
                         cairo.FONT_WEIGHT_NORMAL)
    ctx.set_font_size(size)
    words, lines, cur = s.split(), [], ""
    for w_ in words:
        t = (cur + " " + w_).strip()
        if ctx.text_extents(t).x_advance > maxw and cur:
            lines.append(cur)
            cur = w_
        else:
            cur = t
    if cur:
        lines.append(cur)
    return lines
