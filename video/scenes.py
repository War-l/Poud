"""Coreografía de cada escena. Cada función recibe:

ctx  – contexto Cairo (ya con la cámara aplicada)
t    – tiempo local de la escena (s)
sc   – escena con sus líneas en tiempo local (start/end)
talk – talk(spk) -> apertura de boca 0..1 sincronizada con el audio
"""
import math
import random

from draw import (STYLES, W, H, bg_plaza, bg_workshop, corner_wall, crowd_style, ellipse, hexc,
                  lerp, person, ramp, rgrad, rrect, setc, shade, smooth, vgrad, clamp)

M, A, J = STYLES["maestro"], STYLES["alumno"], STYLES["joven"]
OLD, MAN, WOMAN = STYLES["anciano"], STYLES["hombre"], STYLES["mujer"]

_cache = {}


def bg(name):
    if name not in _cache:
        _cache[name] = bg_workshop() if name == "workshop" else bg_plaza(name, 4200 if name == "dusk" else 2200)
    return _cache[name]


def paint_bg(ctx, name, x=0.0):
    ctx.set_source_surface(bg(name), -x, 0)
    ctx.paint()


def line_at(sc, t, spk=None):
    for ln in sc["lines"]:
        if ln["start"] <= t <= ln["end"] and (spk is None or ln["spk"] == spk):
            return ln
    return None


def walk_x(t, t0, t1, x0, x1):
    """Posición y fase de paso para caminar de x0 a x1 entre t0 y t1 (velocidad constante)."""
    u = clamp((t - t0) / (t1 - t0)) if t1 > t0 else 1.0
    # arranque y frenada suaves pero casi lineales
    u2 = lerp(u, smooth(u), 0.35)
    x = lerp(x0, x1, u2)
    moving = t0 <= t <= t1
    return x, (abs(x - x0) * 0.042 if moving else None)


def draw_sorted(ctx, items):
    """items: lista de (y, callable). Dibuja de fondo a frente."""
    for _, fn in sorted(items, key=lambda it: it[0]):
        fn()


def walker(seed, t, y, h, speed, x_start, direction, period):
    """Transeúnte que cruza la pantalla en bucle."""
    span = W + 400
    x = (x_start + direction * speed * t)
    x = (x + 200) % span - 200 if direction > 0 else (x + 200) % span - 200
    return x, x * 0.045 * direction


# ------------------------------------------------------------------ escena 1
def _coin_paths():
    rnd = random.Random(11)
    coins = []
    ox, oy = 1170, 870
    for i in range(14):
        gy = rnd.uniform(930, 990)
        vx, vy = rnd.uniform(-330, 330), rnd.uniform(-620, -320)
        x, y, path, dt = ox, oy, [], 1 / 120
        tt = 0.0
        while tt < 3.0:
            vy += 2400 * dt
            x += vx * dt
            y += vy * dt
            if y > gy:
                y = gy
                vy = -vy * 0.32
                vx *= 0.6
                if abs(vy) < 40:
                    vy = 0
            path.append((x, y))
            tt += dt
        pick_by = "woman" if x > 1220 else "man"
        coins.append({"path": path, "pick": rnd.uniform(1.9, 3.9), "by": pick_by})
    return coins


COINS = _coin_paths()
DROP = 0.9


def coin_draw(ctx, x, y, spin, a=1.0, r=8.0):
    setc(ctx, "#000000", 0.18 * a)
    ellipse(ctx, x, y + 3, r * 1.1, 2.5)
    ctx.fill()
    setc(ctx, "#e2b437", a)
    ellipse(ctx, x, y - 2, r * max(0.25, abs(math.cos(spin))), r)
    ctx.fill()
    setc(ctx, "#fff0a0", 0.8 * a)
    ellipse(ctx, x - r * 0.25 * abs(math.cos(spin)), y - 4, r * 0.25 * abs(math.cos(spin)), r * 0.35)
    ctx.fill()


def scene_coins(ctx, t, sc, talk):
    paint_bg(ctx, "day", 120)
    lA, lJ, lM = sc["lines"]
    items = []

    # fondo lejano: dos paseantes pequeños
    for k, (sd, y0, sp, xs, d) in enumerate([(31, 760, 60, 300, 1), (32, 775, 50, 1500, -1)]):
        x, ph = walker(sd, t, y0, 150, sp, xs, d, 0)
        items.append((y0, lambda x=x, ph=ph, sd=sd, y0=y0, d=d:
                      person(ctx, x, y0, 150, crowd_style(sd), facing=d, walk=ph)))

    # maestro y alumno entran caminando
    xm, phm = walk_x(t, 0.0, 1.9, -160, 300)
    xa, pha = walk_x(t, 0.0, 1.9, -40, 470)
    face_a = -1 if lA["start"] - 0.2 <= t <= lA["end"] + 0.2 else 1
    items.append((950, lambda: person(ctx, xm, 950, 345, M, walk=phm, mouth=talk("M"),
                                      tilt=-4 if t > lM["start"] else 0)))
    items.append((975, lambda: person(ctx, xa, 975, 310, A, walk=pha, facing=face_a, mouth=talk("A"),
                                      armF=(35, 40) if face_a < 0 else None)))

    # hombre con la bolsa
    if t < DROP:
        xh, phh = walk_x(t, -0.4, DROP, 1500, 1200)
        hman = dict(walk=phh, facing=-1, hold="bag")
    elif t < 4.4:
        xh = 1200
        c = ramp(t, 1.15, 1.45) * (1 - ramp(t, 3.9, 4.25))
        recv = ramp(t, 3.55, 3.75) * (1 - ramp(t, 4.0, 4.2))
        hman = dict(facing=1 if t > 3.2 else -1, crouch=c,
                    armF=(lerp(20, 70, max(c, recv)), lerp(20, 10, recv)))
        if t > 3.9:
            hman["smile"] = 1.0
    else:
        xh, phh = walk_x(t, 4.6, 7.6, 1200, 2150)
        hman = dict(walk=phh, facing=1, hold="bag", smile=1.0)
    items.append((935, lambda: person(ctx, xh, 935, 315, MAN, **hman)))
    # bolsa caída
    if DROP <= t < 4.4:
        u = ramp(t, DROP, DROP + 0.2)
        bx, by = 1185, lerp(880, 940, u)
        items.append((938, lambda: (setc(ctx, "#8a6a3e"), ellipse(ctx, bx, by - 14, 18, 16), ctx.fill(),
                                    setc(ctx, "#6a4e2c"), ellipse(ctx, bx, by - 28, 8, 5), ctx.fill())))

    # mujer
    if t < 4.6:
        xw, phw = walk_x(t, 1.0, 1.7, 1460, 1320)
        cw = ramp(t, 1.75, 2.05) * (1 - ramp(t, 4.0, 4.3))
        items.append((955, lambda: person(ctx, xw, 955, 300, WOMAN, walk=phw, facing=-1, crouch=cw,
                                          armF=(lerp(20, 65, cw), 15))))
    else:
        xw, phw = walk_x(t, 4.8, 8.5, 1320, 2150)
        items.append((955, lambda: person(ctx, xw, 955, 300, WOMAN, walk=phw, facing=1)))

    # amigos del joven
    claps = ramp(t, lJ["start"] + 1.2, lJ["start"] + 1.5)
    for k, (fx, sd) in enumerate([(640, 41), (745, 42)]):
        arm = None
        if claps > 0:
            wave = math.sin((t - lJ["start"]) * 9 + k)
            arm = (lerp(20, 130 + 15 * wave, claps), 30)
        items.append((905, lambda fx=fx, sd=sd, arm=arm:
                      person(ctx, fx, 905, 275, crowd_style(sd), facing=1, armF=arm,
                             smile=claps)))

    # joven: recoge la moneda, la devuelve y presume
    if t < 2.9:
        xj, phj = 880, None
        cj = ramp(t, 2.0, 2.3) * (1 - ramp(t, 2.6, 2.9))
        jpose = dict(facing=1, crouch=cj, armF=(lerp(20, 60, cj), 15),
                     hold="coin" if t > 2.45 else None)
    elif t < 4.3:
        xj, phj = walk_x(t, 2.9, 3.45, 880, 1060)
        give = ramp(t, 3.45, 3.7) * (1 - ramp(t, 4.0, 4.3))
        jpose = dict(facing=1, walk=phj, armF=(lerp(20, 75, give), 5), hold="coin" if t < 3.8 else None)
    else:
        xj, phj = walk_x(t, 4.6, 5.5, 1060, 860)
        brag = ramp(t, lJ["start"], lJ["start"] + 0.3)
        jpose = dict(facing=-1, walk=phj, mouth=talk("J"), smile=1.0 if t > lJ["end"] else 0.4,
                     armF=(lerp(20, 150, brag * (0.5 + 0.5 * abs(math.sin(t * 3)))), 40) if brag else None)
    items.append((945, lambda: person(ctx, xj, 945, 300, J, **jpose)))

    # monedas
    if t >= DROP:
        tt = t - DROP
        for i, c in enumerate(COINS):
            if t > c["pick"] + 0.15:
                continue
            idx = min(int(tt * 120), len(c["path"]) - 1)
            x, y = c["path"][idx]
            a = 1 - ramp(t, c["pick"], c["pick"] + 0.15)
            items.append((y, lambda x=x, y=y, a=a, i=i: coin_draw(ctx, x, y, tt * 9 + i, a)))
        # la moneda que rueda hasta los pies del joven
        if t < 2.45:
            u = ramp(t, DROP, DROP + 1.1)
            x = lerp(1170, 905, 1 - (1 - u) ** 2)
            y = lerp(880, 975, ramp(t, DROP, DROP + 0.3)) - 18 * abs(math.sin(u * math.pi * 2)) * (1 - u)
            items.append((975, lambda: coin_draw(ctx, x, y, t * 14, 1.0, 9)))
    draw_sorted(ctx, items)


# ------------------------------------------------------------------ escena 2
PASSERS = [  # (semilla, y, altura, velocidad, x inicial, dirección, gesto)
    (51, 905, 280, 150, 1900, -1, "look"), (52, 990, 330, 190, -200, 1, "away"),
    (53, 930, 300, 130, 700, 1, "away"), (54, 1010, 340, 210, 2300, -1, "look"),
    (55, 915, 285, 160, 300, -1, "away"), (56, 960, 315, 175, 1200, 1, "look"),
    (57, 900, 270, 120, 2000, 1, "away"),
]


def scene_beggar(ctx, t, sc, talk, mood="day"):
    paint_bg(ctx, mood, 60)
    l1, l2, l3, l4 = sc["lines"]
    items = []
    # mendigo sentado contra la esquina
    shake = math.sin(t * 2.0) * 3
    items.append((955, lambda: person(ctx, 1240, 955, 300, OLD, sit=True, facing=-1, lean=18,
                                      tilt=22 + shake * 0.3, armF=(75 + shake, -5))))
    items.append((960, lambda: (setc(ctx, "#6a5a48"), ellipse(ctx, 1130, 955, 26, 9), ctx.fill(),
                                setc(ctx, "#3a2e24"), ellipse(ctx, 1130, 951, 20, 5), ctx.fill())))
    # transeúntes
    for sd, y, h, sp, xs, d, g in PASSERS:
        x = xs + d * sp * t
        if -250 < x < W + 250:
            near = 1 - clamp(abs(x - 1180) / 260)
            tilt = (-10 if g == "look" else 18) * near
            items.append((y, lambda x=x, y=y, h=h, sd=sd, d=d, tilt=tilt:
                          person(ctx, x, y, h, crowd_style(sd), facing=d, walk=x * 0.045 * d, tilt=tilt)))
    # maestro y alumno observan
    a_face = -1 if l2["start"] - 0.1 <= t <= l3["end"] + 0.2 else 1
    a_tilt = 8 * ramp(t, l3["start"], l3["start"] + 0.4) + 14 * ramp(t, l4["end"] - 0.6, l4["end"] + 0.3)
    items.append((950, lambda: person(ctx, 300, 950, 345, M, mouth=talk("M"))))
    items.append((975, lambda: person(ctx, 470, 975, 310, A, facing=a_face, mouth=talk("A"), tilt=a_tilt)))
    draw_sorted(ctx, items)
    corner_wall(ctx, 1330, mood)  # en primer plano


# ------------------------------------------------------------------ escena 3
def fountain(ctx, x, y, t):
    # pila
    setc(ctx, "#000000", 0.15)
    ellipse(ctx, x, y + 8, 250, 28)
    ctx.fill()
    ctx.set_source(vgrad(y - 90, y, [(0, "#d8c8b0"), (1, "#a8957c")]))
    ctx.move_to(x - 240, y - 70)
    ctx.line_to(x - 240, y)
    ctx.curve_to(x - 240, y + 30, x + 240, y + 30, x + 240, y)
    ctx.line_to(x + 240, y - 70)
    ctx.close_path()
    ctx.fill()
    setc(ctx, "#e8dcc6")
    ellipse(ctx, x, y - 70, 240, 30)
    ctx.fill()
    setc(ctx, "#7fb3c9")
    ellipse(ctx, x, y - 68, 222, 22)
    ctx.fill()
    for k in range(3):  # ondas
        r = ((t * 60 + k * 70) % 210)
        setc(ctx, "#ffffff", 0.35 * (1 - r / 210))
        ctx.set_line_width(2)
        ellipse(ctx, x, y - 68, r, r * 0.1)
        ctx.stroke()
    # columna y taza
    setc(ctx, "#cdbda4")
    ctx.rectangle(x - 22, y - 250, 44, 185)
    ctx.fill()
    setc(ctx, "#e2d5bd")
    ellipse(ctx, x, y - 250, 95, 18)
    ctx.fill()
    setc(ctx, "#bcab90")
    ctx.move_to(x - 95, y - 250)
    ctx.curve_to(x - 80, y - 215, x + 80, y - 215, x + 95, y - 250)
    ctx.fill()
    setc(ctx, "#cdbda4")
    ctx.rectangle(x - 9, y - 320, 18, 70)
    ctx.fill()
    # chorros
    for side in (-1, 1):
        for k in range(12):
            u = ((t * 1.6 + k / 12) % 1.0)
            px = x + side * (10 + 150 * u)
            py = y - 325 + (-90 * u + 330 * u * u)
            if py < y - 70:
                setc(ctx, "#cfe8f2", 0.75)
                ctx.arc(px, py, 4.5, 0, 2 * math.pi)
                ctx.fill()
        ctx.set_line_width(4)
        setc(ctx, "#cfe8f2", 0.45)
        ctx.move_to(x, y - 325)
        for k in range(20):
            u = k / 19
            ctx.line_to(x + side * (10 + 150 * u), y - 325 - 90 * u + 330 * u * u)
        ctx.stroke()


def scene_fountain(ctx, t, sc, talk):
    paint_bg(ctx, "day", 260)
    l1, l2 = sc["lines"]
    items = []
    # al fondo, el anciano se aleja con pan
    xo, pho = walk_x(t, 0, 6.5, 330, 120)
    items.append((800, lambda: person(ctx, xo, 800, 190, OLD, facing=-1, walk=pho, stride=0.6, hold="bread",
                                      armF=(55, 30))))
    items.append((880, lambda: fountain(ctx, 1080, 880, t)))
    xa, pha = walk_x(t, 0.0, 1.15, -120, 690)
    proud = ramp(t, l1["start"] + 0.2, l1["start"] + 0.5) * (1 - ramp(t, l1["end"], l1["end"] + 0.4))
    stuck = ramp(t, l2["end"] + 0.15, l2["end"] + 0.35)
    items.append((975, lambda: person(ctx, xa, 975, 310, A, walk=pha, mouth=max(talk("A"), 0.55 * stuck),
                                      armF=(lerp(20, 150, proud), 30) if proud else None,
                                      smile=0.8 * proud, tilt=-5 * proud)))
    items.append((960, lambda: person(ctx, 1450, 960, 345, M, facing=-1, mouth=talk("M"))))
    draw_sorted(ctx, items)


# ------------------------------------------------------------------ escena 4
MIR = (1000, 520, 150, 230)  # centro x, y, radio x, radio y del cristal


def mirror_frame(ctx):
    cx, cy, rx, ry = MIR
    setc(ctx, "#000000", 0.25)
    ellipse(ctx, cx, 935, 170, 18)
    ctx.fill()
    setc(ctx, "#4a2e1a")
    ctx.set_line_width(14)
    ctx.move_to(cx - 90, 930)
    ctx.line_to(cx - 40, cy + ry)
    ctx.move_to(cx + 90, 930)
    ctx.line_to(cx + 40, cy + ry)
    ctx.stroke()
    ctx.set_source(vgrad(cy - ry, cy + ry, [(0, "#b98a4a"), (0.5, "#8a5a2a"), (1, "#6a4020")]))
    ellipse(ctx, cx, cy, rx + 26, ry + 26)
    ctx.fill()
    setc(ctx, "#e0b56a", 0.5)
    ctx.set_line_width(3)
    ellipse(ctx, cx, cy, rx + 14, ry + 14)
    ctx.stroke()


def mirror_glass(ctx, t, a_pose, dim):
    cx, cy, rx, ry = MIR
    ctx.save()
    ellipse(ctx, cx, cy, rx, ry)
    ctx.clip()
    ctx.set_source(vgrad(cy - ry, cy + ry, [(0, "#8a8278"), (1, "#4e463e")]))
    ctx.paint()
    # reflejo de la pared del taller
    setc(ctx, "#5a4030", 0.5)
    ctx.rectangle(cx - rx, cy + 120, 2 * rx, ry)
    ctx.fill()
    # reflejo del alumno (mirando hacia fuera del espejo)
    person(ctx, cx + 20, cy + 255, 330, A, facing=-1, shadow=False, **a_pose)
    # tinte del cristal
    setc(ctx, "#a8c4d8", 0.18)
    ctx.paint()
    setc(ctx, "#000000", 0.35 * dim)
    ctx.paint()
    # brillos
    setc(ctx, "#ffffff", 0.18)
    ctx.move_to(cx - rx, cy - 60)
    ctx.line_to(cx - rx + 70, cy - ry)
    ctx.line_to(cx - rx + 120, cy - ry)
    ctx.line_to(cx - rx, cy + 20)
    ctx.close_path()
    ctx.fill()
    ctx.restore()


def cloth(ctx, u):
    """Tela: u=0 cubre el espejo, u=1 caída en el suelo a la derecha."""
    cx, cy, rx, ry = MIR
    e = smooth(u)
    # puntos de la tela cubriendo (arriba más estrecho) → montón en el suelo
    top_y = lerp(cy - ry - 40, 905, e)
    bot_y = lerp(cy + ry + 60, 935, e)
    xc = lerp(cx, 1210, e)
    half_top = lerp(110, 70, e)
    half_bot = lerp(200, 110, e)
    lift = math.sin(e * math.pi) * 120
    setc(ctx, "#d6ccb8")
    ctx.move_to(xc - half_top, top_y - lift)
    ctx.curve_to(xc - half_top * 0.3, top_y - 40 * (1 - e) - lift, xc + half_top * 0.3, top_y - 40 * (1 - e) - lift,
                 xc + half_top, top_y - lift)
    ctx.curve_to(xc + half_bot * 0.9, lerp(top_y, bot_y, 0.5), xc + half_bot * 1.1, bot_y - 30, xc + half_bot, bot_y)
    for k in range(5, -1, -1):
        ctx.line_to(xc - half_bot + k * (2 * half_bot / 5), bot_y + (10 if k % 2 else -4))
    ctx.curve_to(xc - half_bot * 1.1, bot_y - 30, xc - half_bot * 0.9, lerp(top_y, bot_y, 0.5),
                 xc - half_top, top_y - lift)
    ctx.close_path()
    ctx.fill()
    setc(ctx, "#a89c86", 0.7)
    ctx.set_line_width(3)
    for k in (-2, -1, 1, 2):
        ctx.move_to(xc + k * half_top * 0.35, top_y + 20 - lift)
        ctx.curve_to(xc + k * half_bot * 0.3, lerp(top_y, bot_y, 0.4), xc + k * half_bot * 0.45,
                     lerp(top_y, bot_y, 0.7), xc + k * half_bot * 0.4, bot_y - 6)
    ctx.stroke()


def scene_mirror(ctx, t, sc, talk):
    paint_bg(ctx, "workshop", 100)
    l1, l2, l3 = sc["lines"]
    # lámpara con resplandor
    sw = math.sin(t * 1.3) * 6
    setc(ctx, "#2a1c14")
    ctx.set_line_width(3)
    ctx.move_to(1000, 0)
    ctx.line_to(1000 + sw, 150)
    ctx.stroke()
    ctx.set_source(rgrad(1000 + sw, 170, 10, 520, [(0, hexc("#ffd890", 0.35)), (1, hexc("#ffd890", 0))]))
    ctx.paint()
    setc(ctx, "#3a2a1c")
    ctx.move_to(960 + sw, 170)
    ctx.line_to(1040 + sw, 170)
    ctx.line_to(1015 + sw, 140)
    ctx.line_to(985 + sw, 140)
    ctx.close_path()
    ctx.fill()
    setc(ctx, "#ffe6a8")
    ellipse(ctx, 1000 + sw, 174, 18, 8)
    ctx.fill()

    reveal = ramp(t, 0.45, 1.35)
    look_down = 10 * ramp(t, l3["end"] - 0.2, l3["end"] + 0.6)
    frown = ramp(t, l3["start"] + 0.5, l3["start"] + 1.0)
    a_pose = dict(mouth=talk("A"), tilt=look_down - 3 * frown)
    mirror_frame(ctx)
    if reveal > 0:
        mirror_glass(ctx, t, a_pose, dim=0.5 * ramp(t, l3["start"], l3["end"] + 0.6))
    # maestro tira de la tela
    pull = ramp(t, 0.2, 0.5) * (1 - ramp(t, 1.2, 1.6))
    person(ctx, 1380, 950, 345, M, facing=-1, mouth=talk("M"), armF=(lerp(20, 110, pull), lerp(20, 0, pull)),
           lean=8 * pull)
    cloth(ctx, reveal)
    # alumno de espaldas a cámara, mirando al espejo
    person(ctx, 610, 975, 320, A, **a_pose)


# ------------------------------------------------------------------ escena 5
def scene_sit(ctx, t, sc, talk):
    paint_bg(ctx, "morning", 60)
    l1, l2 = sc["lines"]
    items = []
    help_ = ramp(t, l2["end"] + 0.25, l2["end"] + 0.7)
    tremble = math.sin(t * 38) * 4 * (ramp(t, l2["end"] - 0.6, l2["end"]) * (1 - help_ * 0.7))
    items.append((955, lambda: person(ctx, 1240, 955, 300, OLD, sit=True, facing=-1, lean=12, tilt=8,
                                      armF=(150 + tremble, 40), armB=(140 - tremble, 40))))
    # alumno sentado a su lado: mira al maestro mientras hablan, luego ayuda al anciano
    a_face = -1 if t < l2["end"] + 0.25 else 1
    reach = (lerp(20, 95, help_), lerp(20, 10, help_)) if help_ > 0 else None
    items.append((960, lambda: person(ctx, 1030, 960, 300, A, sit=True, facing=a_face, mouth=talk("A"),
                                      armF=reach, lean=10 * help_, tilt=-4 if a_face < 0 else 6)))
    xm, phm = walk_x(t, 0.0, 1.0, 380, 690)
    items.append((950, lambda: person(ctx, xm, 950, 345, M, walk=phm, mouth=talk("M"),
                                      smile=ramp(t, l1["end"], l1["end"] + 0.4))))
    draw_sorted(ctx, items)
    corner_wall(ctx, 1330, "morning")


# ------------------------------------------------------------------ escena 6
def lantern(ctx, x, y):
    setc(ctx, "#1c1620")
    ctx.rectangle(x - 5, y, 10, 260)
    ctx.fill()
    ctx.set_source(rgrad(x, y - 20, 4, 120, [(0, hexc("#ffcf73", 0.55)), (1, hexc("#ffcf73", 0))]))
    ctx.arc(x, y - 20, 120, 0, 2 * math.pi)
    ctx.fill()
    setc(ctx, "#ffdd8a")
    rrect(ctx, x - 14, y - 44, 28, 40, 6)
    ctx.fill()
    setc(ctx, "#1c1620")
    ctx.rectangle(x - 18, y - 50, 36, 8)
    ctx.fill()


def scene_dusk(ctx, t, sc, talk):
    scroll = 40 * t
    paint_bg(ctx, "dusk", 400 + scroll)
    for k in range(6):
        lx = (k * 520 - scroll * 1.0) % (W + 600) - 200
        lantern(ctx, lx, 690)
    l1, l2 = sc["lines"]
    T = sc["end"] - sc["start"]
    trip_t = l2["end"] + 0.25
    items = []
    # maestro: camina sin detenerse
    xm = 640 + 22 * t + max(0, t - trip_t) * 40
    items.append((950, lambda: person(ctx, xm, 950, 345, M, walk=t * 4.2 * 1.0, mouth=talk("M"))))
    # alumno: camina a su lado y corre a ayudar
    if t < trip_t + 0.2:
        xa = 820 + 22 * t
        items.append((975, lambda: person(ctx, xa, 975, 310, A, walk=t * 4.4)))
    else:
        x0 = 820 + 22 * (trip_t + 0.2)
        u = ramp(t, trip_t + 0.2, trip_t + 1.3)
        xa = lerp(x0, 1395, u)
        if u < 1:
            items.append((975, lambda: person(ctx, xa, 975, 310, A, walk=t * 9, stride=1.4, lean=10)))
        else:
            c = ramp(t, trip_t + 1.3, trip_t + 1.6)
            items.append((975, lambda: person(ctx, xa, 975, 310, A, crouch=c, armF=(lerp(20, 70, c), 15))))
    # transeúnte que tropieza a lo lejos
    st = crowd_style(77)
    if t < trip_t:
        xp = 1750 - 30 * t
        items.append((930, lambda: person(ctx, xp, 930, 280, st, facing=-1, walk=t * 4, hold="bag")))
    else:
        xp = 1750 - 30 * trip_t
        f = ramp(t, trip_t, trip_t + 0.35)
        items.append((930, lambda: person(ctx, xp, 930, 280, st, facing=-1, crouch=f, lean=35 * f,
                                          armF=(lerp(20, 80, f), 0), armB=(lerp(-10, 70, f), 0))))
        # pertenencias por el suelo
        for k, (dx, col) in enumerate([(-90, "#e08a2e"), (-130, "#e08a2e"), (-60, "#c9b27a"), (-170, "#e08a2e")]):
            u = ramp(t, trip_t + 0.05 * k, trip_t + 0.5 + 0.05 * k)
            ox, oy = xp - 20 + dx * u, lerp(870, 965, u) - 40 * math.sin(u * math.pi)
            items.append((oy, lambda ox=ox, oy=oy, col=col, k=k:
                          (setc(ctx, col), (ctx.rectangle(ox - 12, oy - 18, 24, 18) if k == 2 else
                                            ctx.arc(ox, oy - 9, 9, 0, 2 * math.pi)), ctx.fill())))
    draw_sorted(ctx, items)
    # oscurecer hacia el final
    setc(ctx, "#0d0a14", 0.25 * ramp(t, T - 2.0, T))
    ctx.paint()


SETS = {
    "coins": scene_coins, "beggar": scene_beggar, "fountain": scene_fountain,
    "mirror": scene_mirror, "sit": scene_sit, "dusk": scene_dusk,
}

# Cámara: (zoom inicial, zoom final, centro x, centro y) por decorado
CAMERA = {
    "coins": (1.00, 1.05, 900, 700), "beggar": (1.04, 1.10, 800, 760), "fountain": (1.0, 1.06, 900, 700),
    "mirror": (1.0, 1.18, 960, 560), "sit": (1.06, 1.12, 1000, 760), "dusk": (1.03, 1.0, 960, 700),
}
