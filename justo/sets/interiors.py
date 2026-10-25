"""Interiores: casa (escena 3), despacho (4, 6, 7) y biblioteca de Samuel (5)."""
import math
import random

import cairo
import numpy as np

from engine import physics as ph
from engine.gl import Particles, Rain
from engine.paint import (hx, mix, shade, setc, ellipse, smooth_path, poly, lin_grad, rad_grad, material,
                          fill_material, rrect, value_noise, surface_from_rgba)
from sets.common import foliage_cluster
from sets.room import Room, cut, window_frame, wood_panels, bookshelf

K2700 = ph.blackbody(2700)
K2200 = ph.blackbody(2200)
K1900 = ph.blackbody(1900)
K3200 = ph.blackbody(3200)


def wallpaper(w, h, base, motif, seed=0):
    """Papel pintado con motivo de damasco sutil."""
    n = value_noise(h, w, 80, seed, 4)
    b = np.array(hx(base)[:3], np.float32)
    m = np.array(hx(motif)[:3], np.float32)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    pat = (np.sin(xx / w * 2 * np.pi * 4) * np.sin(yy / h * 2 * np.pi * 6)) ** 2
    pat = np.clip((pat - 0.55) * 4, 0, 1) * 0.5
    stripes = (np.sin(xx / w * 2 * np.pi * 16) > 0.92).astype(np.float32) * 0.3
    k = np.clip(pat + stripes, 0, 1)[..., None]
    rgb = b * (0.94 + 0.08 * n[..., None]) * (1 - k) + m * k
    return surface_from_rgba(rgb)


def city_skyline(ctx, rnd, x0, x1, base_col, win_lit, roof_col="#3a3240", seed=0, emit=False, lit_frac=0.5,
                 hmin=6, hmax=22):
    x = x0
    r2 = random.Random(seed)
    while x < x1:
        w = r2.uniform(4, 9)
        h = r2.uniform(hmin, hmax)
        if not emit:
            setc(ctx, mix(base_col, roof_col, r2.uniform(0, 0.4)))
            ctx.rectangle(x, 0, w, h)
            ctx.fill()
            if r2.random() < 0.5:
                setc(ctx, roof_col)
                poly(ctx, [(x - 0.3, h), (x + w / 2, h + r2.uniform(1.5, 3)), (x + w + 0.3, h)])
                ctx.fill()
        cols = int(w / 1.4)
        rows = int((h - 1.5) / 2.2)
        for r in range(rows):
            for c in range(cols):
                wx, wy = x + 0.6 + c * 1.4, 1.2 + r * 2.2
                lit = r2.random() < lit_frac
                if emit:
                    if lit:
                        setc(ctx, r2.choice(win_lit))
                        ctx.rectangle(wx, wy, 0.7, 1.1)
                        ctx.fill()
                else:
                    setc(ctx, "#1a1820" if not lit else r2.choice(win_lit))
                    ctx.rectangle(wx, wy, 0.7, 1.1)
                    ctx.fill()
        x += w + r2.uniform(0.0, 0.8)


def side_chair(ctx, x, seat_h, back_side, wood="#4a2e1c", depth=0.45, back_h=0.95):
    """Silla de perfil: asiento centrado en x; respaldo en el lado back_side (+1 derecha, -1 izquierda)."""
    x0, x1 = x - depth / 2, x + depth / 2
    setc(ctx, wood)
    ctx.rectangle(x0, seat_h - 0.05, depth, 0.05)
    ctx.fill()
    for xx in (x0 + 0.02, x1 - 0.05):
        ctx.rectangle(xx, 0, 0.035, seat_h)
        ctx.fill()
    bx = x1 - 0.04 if back_side > 0 else x0
    ctx.rectangle(bx, seat_h, 0.04, back_h - seat_h)
    ctx.fill()
    ctx.rectangle(min(bx, bx - 0.02 * back_side), back_h - 0.12, 0.06, 0.12)
    ctx.fill()


# ====================================================================== casa
class Home(Room):
    def __init__(self, eng):
        super().__init__(eng, 3.6, 3.6, 6.0, 2.8, near=-2.0)
        self.sun = ph.sun_dir(0.6, 175.0)   # sol tras la cámara, rozando el horizonte: crepúsculo
        rnd = random.Random(3)
        WX0, WX1, WY0, WY1 = -2.3, 0.3, 0.85, 2.35
        self.win_rect = (WX0, WX1, WY0, WY1)

        def far(ctx, cv):
            setc(ctx, "#3a4258")
            pts = [(-120, 0)] + [(-120 + i * 8, 6 + 5 * math.sin(i * 0.7) + 3 * math.sin(i * 1.9)) for i in range(31)] + [(120, 0)]
            poly(ctx, pts)
            ctx.fill()
        self.plane(2, 300.0, (-130, 130, -1, 30), 10, far, flat=1.0)

        def city(ctx, cv):
            city_skyline(ctx, rnd, -40, 40, "#4a4a5e", ["#f2c070", "#e8a860", "#f4d090"], seed=5, lit_frac=0.0,
                         hmin=3, hmax=9)
        def city_e(ctx, cv):
            city_skyline(ctx, rnd, -40, 40, "#4a4a5e", ["#ffcf80", "#ffb060", "#ffe0a0"], seed=5, emit=True,
                         lit_frac=0.35, hmin=3, hmax=9)
        self.plane(2, 45.0, (-40, 40, -1, 26), 60, city, emit=city_e, flat=1.0, emit_gain=2.2)

        paper = wallpaper(512, 512, "#c9a77e", "#b48e66", seed=2)

        def back(ctx, cv):
            fill_material(ctx, paper, 220)
            ctx.paint()
            setc(ctx, "#e8dcc6")
            ctx.rectangle(-3.6, 0, 7.2, 0.12)
            ctx.fill()
            # ventana con cortinas
            setc(ctx, "#e8e0d0")
            ctx.rectangle(WX0 - 0.1, WY0 - 0.1, (WX1 - WX0) + 0.2, (WY1 - WY0) + 0.2)
            ctx.fill()
            cut(ctx, WX0, WY0, WX1 - WX0, WY1 - WY0)
            window_frame(ctx, WX0, WY0, WX1 - WX0, WY1 - WY0, "#efe8da", mull=3, transom=[WY0 + 0.95], lw=0.05)
            for cx, sgn in ((WX0 - 0.15, 1), (WX1 + 0.15, -1)):
                for k in range(6):
                    setc(ctx, mix("#8a3a2e", "#5a2420", (k % 2) * 0.5))
                    x = cx + sgn * (-0.25 + k * 0.08)
                    poly(ctx, [(x - 0.06, 0.3), (x + 0.06, 0.3), (x + 0.05, 2.55), (x - 0.05, 2.55)])
                    ctx.fill()
            setc(ctx, "#5a4030")
            ctx.rectangle(WX0 - 0.6, 2.52, (WX1 - WX0) + 1.2, 0.05)
            ctx.fill()
            # estantería
            bookshelf(ctx, rnd, 1.2, 3.4, 0.0, 2.3, shelf_h=0.38, wood="#5a3a24")
            # cuadros
            for (x, y, w, h, c) in ((0.55, 1.45, 0.45, 0.6, "#6a7a5a"), (-3.3, 1.3, 0.7, 0.5, "#8a6a4a")):
                setc(ctx, "#c8a868")
                ctx.rectangle(x - 0.04, y - 0.04, w + 0.08, h + 0.08)
                ctx.fill()
                ctx.set_source(lin_grad(x, y, x, y + h, [(0, c), (1, shade(c, 1.4))]))
                ctx.rectangle(x, y, w, h)
                ctx.fill()
        self.wall_back(back, ppm=300)

        def left(ctx, cv):
            fill_material(ctx, paper, 220)
            ctx.paint()
            setc(ctx, "#4a3020")
            ctx.rectangle(1.0, 0, 0.95, 2.1)
            ctx.fill()
            setc(ctx, "#e8dcc6")
            ctx.rectangle(-2, 0, 8, 0.12)
            ctx.fill()
        self.wall_left(left, ppm=150)
        self.wall_right(left, ppm=150)

        def floor(ctx, cv):
            wood = material("wood", 512, 1024, "#7a5236", seed=3, grain=40, aspect=0.12)
            fill_material(ctx, wood, 300)
            ctx.paint()
            setc(ctx, "#000000", 0.25)
            ctx.set_line_width(0.008)
            x = -3.6
            while x < 3.6:
                ctx.move_to(x, -2)
                ctx.line_to(x, 6)
                x += 0.14
            ctx.stroke()
            # alfombra
            setc(ctx, "#6a2a26")
            rrect(ctx, -1.7, 2.6, 3.6, 2.6, 0.05)
            ctx.fill()
            setc(ctx, "#c8a068", 0.7)
            ctx.set_line_width(0.05)
            rrect(ctx, -1.55, 2.75, 3.3, 2.3, 0.05)
            ctx.stroke()
            for i in range(14):
                setc(ctx, "#2a3a5a", 0.6)
                ellipse(ctx, -1.2 + (i % 7) * 0.45, 3.3 + (i // 7) * 1.2, 0.12, 0.08)
                ctx.fill()
        self.floor(floor, ppm=260, detail=(0.1, 10.0, 0.2))

        def ceil(ctx, cv):
            setc(ctx, "#e8dcc8")
            ctx.paint()
        self.ceiling(ceil)

        # mesa con té
        def table(ctx, cv):
            setc(ctx, "#5a3a24")
            ctx.rectangle(-0.9, 0.72, 2.0, 0.05)
            ctx.fill()
            for x in (-0.82, 1.0):
                ctx.rectangle(x, 0, 0.06, 0.72)
                ctx.fill()
            setc(ctx, "#4a2e1c")
            ctx.rectangle(-0.85, 0.6, 1.9, 0.12)
            ctx.fill()
            # tetera, tazas, libro
            setc(ctx, "#e8e2d4")
            ellipse(ctx, -0.35, 0.85, 0.11, 0.09)
            ctx.fill()
            ctx.rectangle(-0.46, 0.77, 0.22, 0.06)
            ctx.fill()
            setc(ctx, "#c8b8a0")
            ctx.move_to(-0.24, 0.86)
            ctx.line_to(-0.13, 0.92)
            ctx.set_line_width(0.02)
            ctx.stroke()
            for x in (0.2, 0.62):
                setc(ctx, "#f0ebe0")
                poly(ctx, [(x - 0.045, 0.77), (x + 0.045, 0.77), (x + 0.05, 0.85), (x - 0.05, 0.85)])
                ctx.fill()
                setc(ctx, "#d8d0c0")
                ellipse(ctx, x, 0.77, 0.07, 0.008)
                ctx.fill()
            setc(ctx, "#2a4a6a")
            ctx.rectangle(0.85, 0.77, 0.22, 0.04)
            ctx.fill()
        self.plane(2, 4.2, (-1.0, 1.2, -0.05, 1.0), 500, table, inflate=(6.0, 1.0, 0.3))

        def chair(ctx, cv):
            side_chair(ctx, 0.62, 0.46, +1, wood="#4a2e1c")
        self.plane(2, 4.75, (0.2, 1.1, -0.05, 1.1), 400, chair, inflate=(6.0, 1.0, 0.3))

        # lámpara de pie y lámpara colgante (emisivas)
        def lamps(ctx, cv):
            setc(ctx, "#2a2420")
            ctx.rectangle(2.38, 0, 0.04, 1.45)
            ctx.fill()
            ellipse(ctx, 2.4, 0.01, 0.15, 0.02)
            ctx.fill()
            setc(ctx, "#e8d4a8")
            poly(ctx, [(2.22, 1.42), (2.58, 1.42), (2.5, 1.7), (2.3, 1.7)])
            ctx.fill()
            # colgante sobre la mesa
            setc(ctx, "#2a2420")
            ctx.rectangle(0.09, 2.0, 0.015, 0.8)
            ctx.fill()
            setc(ctx, "#3a5a48")
            poly(ctx, [(-0.12, 1.85), (0.32, 1.85), (0.2, 2.02), (0.0, 2.02)])
            ctx.fill()

        def lamps_e(ctx, cv):
            setc(ctx, "#ffd9a0")
            poly(ctx, [(2.22, 1.42), (2.58, 1.42), (2.5, 1.7), (2.3, 1.7)])
            ctx.fill()
            setc(ctx, "#fff0c8")
            ellipse(ctx, 0.1, 1.84, 0.12, 0.03)
            ctx.fill()
        self.plane(2, 4.6, (-0.3, 2.8, -0.05, 2.8), 300, lamps, emit=lamps_e, emit_gain=6.0)

        # vapor del té
        self.steam = Particles(eng, 120_000, (0.18, 0.86, 4.18), (0.22, 1.25, 4.22), seed=4, drift=(0.0, 0.12, 0.0),
                               turb=0.035, size_m=0.002, color=(1.0, 0.92, 0.8), gain=0.012, bright_pow=2.0)
        self.add_particles(4.15, self.steam)
        self.add_volume(dict(sigma_s=0.05, sigma_t=0.02, g=0.3, box=((-3.6, 0, -2), (3.6, 2.8, 6)), steps=16,
                             noise=0.0, light_k=1.0), [6.0, 4.4, -2.0])
        self.char_rim = 0.0

    def env(self, t):
        flick = 1.0 + 0.01 * math.sin(t * 13.0)
        lights = [((2.4, 1.55, 4.6), 0.15, K2700 * 9.0 * flick),
                  ((0.1, 1.82, 4.2), 0.1, K2700 * 2.5)]
        sky_amb = np.array([0.10, 0.14, 0.26])
        return dict(amb_top=sky_amb * 0.6, amb_bot=K2700 * 0.25, sun_col=np.zeros(3), sun_dir=self.sun,
                    lights=lights, sigma=np.array([0.004] * 3), fog=np.array([0.004, 0.003, 0.002]),
                    fog_sun=np.zeros(3), rim_col=np.zeros(3), rim_dir=(0, 0), clear=(0, 0, 0))

    def sky(self, t):
        return dict(sun_dir=self.sun, haze=1.0, disk=0.0, gain=0.6)

    def post(self, t):
        return dict(exposure=3.2, wb=(0.92, 1.0, 1.12), sat=1.05, contrast=1.06, bloom=0.08, bloom_thresh=1.2,
                    lift=(0.01, 0.01, 0.025), shadow_tint=(-0.004, 0.0, 0.02), high_tint=(0.02, 0.008, -0.012),
                    vignette=0.6, grain=0.024)

    def light_screen(self):
        return (0.85, 0.5)


# ====================================================================== despacho
class Office(Room):
    """mood: day | night | memory"""

    def __init__(self, eng, mood="day"):
        super().__init__(eng, 3.0, 3.4, 6.5, 3.0, near=-2.0)
        self.mood = mood
        rnd = random.Random(8)
        night = mood == "night"
        WX0, WX1, WY0, WY1 = -0.5, 2.5, 0.9, 2.55
        self.WIN = (WX0, WX1, WY0, WY1)
        if mood == "day":
            self.sun = ph.sun_dir(38.0, 160.0) * np.array([1, 1, 1])
            self.sun = np.array([0.35, 0.62, 0.7])
            self.sun = self.sun / np.linalg.norm(self.sun)   # el sol entra por la ventana del fondo
        elif mood == "memory":
            self.sun = np.array([0.5, 0.45, 0.74])
            self.sun = self.sun / np.linalg.norm(self.sun)
        else:
            self.sun = ph.sun_dir(-10.0, 0.0)

        def city(ctx, cv):
            city_skyline(ctx, rnd, -30, 30, "#8a8478" if not night else "#2a2a36",
                         ["#c8d0d8"] if not night else ["#ffcf80"], seed=11, lit_frac=0.0, hmin=8, hmax=26,
                         roof_col="#6a5a50" if not night else "#1a1a24")

        def city_e(ctx, cv):
            city_skyline(ctx, rnd, -30, 30, "#2a2a36", ["#ffcf80", "#ffb868", "#ffe2a8", "#a8c8ff"], seed=11,
                         emit=True, lit_frac=0.45, hmin=8, hmax=26)
        self.plane(2, 34.0, (-30, 30, -1, 30), 60, city, emit=city_e if night else None, flat=1.0,
                   emit_gain=3.0)

        plaster = material("plaster", 512, 512, "#b9b2a2" if mood != "memory" else "#c4b8a2", seed=9, scale=80)

        def back(ctx, cv):
            fill_material(ctx, plaster, 220)
            ctx.paint()
            wood_panels(ctx, -3.0, 3.4, 0, 0.9, "#5a4232", seed=4, panel_w=0.8, ppm=260)
            setc(ctx, "#e0dccf")
            ctx.rectangle(WX0 - 0.08, WY0 - 0.08, (WX1 - WX0) + 0.16, (WY1 - WY0) + 0.16)
            ctx.fill()
            cut(ctx, WX0, WY0, WX1 - WX0, WY1 - WY0)
            # persiana veneciana (lamas entreabiertas)
            y = WY0 + 0.02
            while y < WY1 - 0.02:
                setc(ctx, "#d8d0bc" if not night else "#8a8478", 0.92)
                ctx.rectangle(WX0, y, WX1 - WX0, 0.022)
                ctx.fill()
                y += 0.05
            window_frame(ctx, WX0, WY0, WX1 - WX0, WY1 - WY0, "#e8e4d8", mull=2, transom=[], lw=0.05)
            # diploma y estante
            setc(ctx, "#3a2a1c")
            ctx.rectangle(-2.4, 1.5, 0.75, 0.55)
            ctx.fill()
            setc(ctx, "#efe8d6")
            ctx.rectangle(-2.34, 1.56, 0.63, 0.43)
            ctx.fill()
            setc(ctx, "#8a6a3a")
            ctx.set_line_width(0.006)
            for k in range(5):
                ctx.move_to(-2.25, 1.65 + k * 0.06)
                ctx.line_to(-1.8, 1.65 + k * 0.06)
            ctx.stroke()
            # archivador
            setc(ctx, "#5a5a58")
            ctx.rectangle(2.7, 0, 0.6, 1.3)
            ctx.fill()
            for k in range(3):
                setc(ctx, "#4a4a48")
                ctx.rectangle(2.74, 0.1 + k * 0.42, 0.52, 0.36)
                ctx.fill()
                setc(ctx, "#b8b8b0")
                ctx.rectangle(2.95, 0.3 + k * 0.42, 0.1, 0.03)
                ctx.fill()
        self.wall_back(back, ppm=300)

        def left(ctx, cv):
            fill_material(ctx, plaster, 200)
            ctx.paint()
            wood_panels(ctx, -2, 6.5, 0, 0.9, "#5a4232", seed=5, panel_w=0.8, ppm=200)
            # puerta (z 1.6-2.6)
            setc(ctx, "#3a2a1c")
            ctx.rectangle(1.5, 0, 1.2, 2.25)
            ctx.fill()
            cut(ctx, 1.6, 0, 1.0, 2.15)
        self.wall_left(left, ppm=170)

        def right(ctx, cv):
            fill_material(ctx, plaster, 200)
            ctx.paint()
            bookshelf(ctx, rnd, 0.5, 6.4, 0.0, 2.5, shelf_h=0.36, wood="#4a3020")
        self.wall_right(right, ppm=200)

        # pasillo iluminado tras la puerta
        def hall(ctx, cv):
            setc(ctx, "#d8c8a8")
            ctx.paint()
            setc(ctx, "#b8a888")
            ctx.rectangle(-1, 0, 6, 0.1)
            ctx.fill()
        self.plane(0, -4.2, (0.5, 4.0, 0, 3.0), 80, hall, key=7.0)

        def floor(ctx, cv):
            wood = material("wood", 512, 1024, "#5a3e2a", seed=6, grain=40, aspect=0.12)
            fill_material(ctx, wood, 300)
            ctx.paint()
            setc(ctx, "#000000", 0.25)
            ctx.set_line_width(0.008)
            for i in range(60):
                x = -3 + i * 0.12
                ctx.move_to(x, -2)
                ctx.line_to(x, 6.5)
            ctx.stroke()
            setc(ctx, "#3a4a5a")
            rrect(ctx, -1.6, 2.4, 3.6, 3.0, 0.03)
            ctx.fill()
            setc(ctx, "#8a7a5a", 0.6)
            ctx.set_line_width(0.04)
            rrect(ctx, -1.45, 2.55, 3.3, 2.7, 0.03)
            ctx.stroke()
        self.floor(floor, ppm=260, detail=(0.1, 10.0, 0.2))

        def ceil(ctx, cv):
            setc(ctx, "#d8d2c4")
            ctx.paint()
        self.ceiling(ceil)

        # escritorio con expedientes y lámpara de banquero
        def desk(ctx, cv):
            wood = material("wood", 512, 256, "#5e3e26", seed=7, grain=50, aspect=10)
            fill_material(ctx, wood, 500)
            ctx.rectangle(-1.0, 0.0, 2.7, 0.74)
            ctx.fill()
            setc(ctx, "#000000", 0.25)
            ctx.set_line_width(0.01)
            for x0 in (-0.95, 0.75):
                rrect(ctx, x0, 0.08, 0.85, 0.56, 0.01)
                ctx.stroke()
            setc(ctx, "#6e4a2e")
            ctx.rectangle(-1.05, 0.74, 2.8, 0.05)
            ctx.fill()
            for (x, h, c) in ((-0.8, 0.14, "#c8b48a"), (-0.78, 0.08, "#d8c8a0"), (0.0, 0.04, "#efe8d8"),
                              (0.4, 0.1, "#8a5a32"), (0.45, 0.06, "#c8b48a")):
                setc(ctx, c)
                ctx.rectangle(x, 0.79 + (0 if h > 0.05 else 0.0), 0.36, h)
                ctx.fill()
            # lámpara de banquero
            setc(ctx, "#b8984a")
            ctx.rectangle(1.28, 0.79, 0.03, 0.3)
            ctx.fill()
            ellipse(ctx, 1.295, 0.8, 0.1, 0.02)
            ctx.fill()
            setc(ctx, "#1e5a3a")
            poly(ctx, [(1.1, 1.05), (1.5, 1.05), (1.45, 1.15), (1.15, 1.15)])
            ctx.fill()

        def desk_e(ctx, cv):
            if night:
                setc(ctx, "#fff0c0")
                ctx.rectangle(1.12, 1.03, 0.36, 0.025)
                ctx.fill()
        self.plane(2, 4.0, (-1.1, 1.8, -0.05, 1.3), 500, desk, emit=desk_e if night else None, emit_gain=12.0,
                   inflate=(6.0, 1.0, 0.3))

        def ochair(ctx, cv):
            side_chair(ctx, 0.95, 0.5, +1, wood="#2a1e18", back_h=1.25)
        self.plane(2, 4.75, (0.5, 1.4, -0.05, 1.35), 400, ochair, inflate=(6.0, 1.0, 0.3))
        if mood == "memory":
            def vchair(ctx, cv):
                side_chair(ctx, -1.17, 0.46, -1, wood="#3a2a1e")
            self.plane(2, 4.45, (-1.6, -0.7, -0.05, 1.1), 400, vchair, inflate=(6.0, 1.0, 0.3))

        if night:
            self.rain = Rain(eng, 50_000, (-4, -2, 7.5), (6, 12, 30), vel=(0.5, -8.0, 0.0), color=(0.25, 0.27, 0.3))
            self.add_rain(30.0, self.rain)
            self.add_volume(dict(sigma_s=0.04, sigma_t=0.02, g=0.3, box=((-3, 0, -2), (3.4, 3, 6.5)), steps=16,
                                 noise=0.0), [6.5, 4.1, -2.0])
        else:
            self.dust = Particles(eng, 1_500_000, (-3, 0, -1), (3.4, 3, 6.4), seed=9, drift=(0, -0.005, 0),
                                  turb=0.06, size_m=0.001, color=(1, 0.95, 0.85), gain=0.3, bright_pow=6.0)
            self.dust.win_mode = True
            self.add_particles(4.5, self.dust)
            self.add_volume(dict(sigma_s=0.02, sigma_t=0.01, g=0.6, box=((-3, 0, -2), (3.4, 3, 6.5)), steps=28,
                                 noise=0.5), [6.5, 4.1, 2.0, -2.0])
        self.windows = dict(axis=2, value=6.5, rects=[(WX0, WX1, WY0, WY1)], blinds=(20.0, 0.45, 0.85, 0.0)) \
            if not night else None
        self.char_rim = 0.3

    def env(self, t):
        if self.mood == "night":
            lights = [((1.3, 1.0, 3.95), 0.12, K2700 * 1.1),           # lámpara de banquero
                      ((-3.6, 1.9, 2.1), 0.3, K3200 * 2.2)]            # pasillo
            return dict(amb_top=np.array([0.02, 0.03, 0.06]), amb_bot=K2700 * 0.03, sun_col=np.zeros(3),
                        sun_dir=self.sun, lights=lights, windows=None, sigma=np.array([0.004] * 3),
                        fog=np.array([0.002, 0.002, 0.003]), fog_sun=np.zeros(3), rim_col=np.zeros(3),
                        rim_dir=(0, 0), clear=(0, 0, 0))
        k = 1.0 if self.mood == "day" else 0.55
        e = self.interior_env(self.sun, 1.0, self.windows, [], amb_col=(0.6, 0.66, 0.78), amb_k=1.3 * k,
                              bounce_col=(0.8, 0.68, 0.55), haze_sigma=0.01, fog_col=(0.02, 0.02, 0.02))
        e["sun_col"] = ph.sun_radiance_at_ground(ph.sun_dir(38, 0)) * k
        return e

    def sky(self, t):
        if self.mood == "night":
            return dict(sun_dir=ph.sun_dir(-2.0, 0.0), haze=2.0, disk=0.0, gain=0.03)
        return dict(sun_dir=self.sun, haze=1.4, disk=0.0)

    def post(self, t):
        if self.mood == "night":
            return dict(exposure=5.0, wb=(0.9, 1.0, 1.18), sat=1.0, contrast=1.1, bloom=0.08, bloom_thresh=0.5,
                        lift=(0.006, 0.008, 0.02), shadow_tint=(-0.006, 0.0, 0.022), high_tint=(0.02, 0.006, -0.02),
                        vignette=0.7, grain=0.03)
        if self.mood == "memory":
            return dict(exposure=6.0, wb=(1.0, 1.0, 1.02), sat=0.9, contrast=1.0, bloom=0.08, bloom_thresh=0.5,
                        lift=(0.02, 0.018, 0.02), shadow_tint=(0.0, 0.0, 0.01), high_tint=(0.02, 0.01, -0.01),
                        vignette=0.5, grain=0.022, rays=dict(thresh=0.6, decay=0.97, density=0.9, weight=0.08))
        return dict(exposure=6.5, wb=(0.98, 1.0, 1.03), sat=0.95, contrast=1.06, bloom=0.06, bloom_thresh=0.5,
                    lift=(0.01, 0.01, 0.014), shadow_tint=(0.0, 0.003, 0.012), high_tint=(0.02, 0.012, -0.01),
                    vignette=0.5, grain=0.022, rays=dict(thresh=0.6, decay=0.97, density=0.9, weight=0.1))

    def light_screen(self):
        if self.mood == "night":
            return (0.9, 0.4)
        return (0.5, 0.85)


# ====================================================================== biblioteca
class Library(Room):
    def __init__(self, eng):
        super().__init__(eng, 3.6, 4.0, 6.0, 3.2, near=-2.0)
        self.sun = ph.sun_dir(14.0, -72.0)
        rnd = random.Random(21)
        WIN = [(1.0, 2.4, 0.8, 2.7), (3.4, 4.8, 0.8, 2.7)]
        self.windows = dict(axis=0, value=-3.6, rects=WIN, blinds=(1.6, 0.05, 1.0, 2.0))

        def outside(ctx, cv):
            for i in range(10):
                foliage_cluster(ctx, rnd, rnd.uniform(-2, 10), rnd.uniform(2, 6), rnd.uniform(1.5, 2.5),
                                rnd.uniform(1.0, 2.0), ["#3a4a24", "#55692e", "#7a8a3a", "#b8a848"], (0.0, 0.8),
                                n=600, leaf=0.1)
        self.plane(0, -12.0, (-4, 14, 0, 9), 60, outside, key=30, flat=1.0)

        plaster = material("plaster", 512, 512, "#a89070", seed=12, scale=80)

        def back(ctx, cv):
            fill_material(ctx, plaster, 200)
            ctx.paint()
            bookshelf(ctx, rnd, -3.6, 1.3, 0.0, 3.2, shelf_h=0.4, wood="#3e2818")
            # chimenea
            setc(ctx, "#8a7a68")
            ctx.rectangle(1.6, 0, 1.9, 1.35)
            ctx.fill()
            setc(ctx, "#a8987e")
            ctx.rectangle(1.45, 1.3, 2.2, 0.12)
            ctx.fill()
            setc(ctx, "#1a1210")
            ctx.move_to(2.0, 0)
            ctx.line_to(2.0, 0.75)
            ctx.arc(2.55, 0.75, 0.55, math.pi, 0)
            ctx.line_to(3.1, 0)
            ctx.close_path()
            ctx.fill()
            # leños
            setc(ctx, "#3a2418")
            for k in range(3):
                ellipse(ctx, 2.35 + k * 0.2, 0.08, 0.16, 0.05, 0.1 * k)
                ctx.fill()
            # cuadro sobre la chimenea
            setc(ctx, "#b8944a")
            ctx.rectangle(1.9, 1.75, 1.3, 0.95)
            ctx.fill()
            ctx.set_source(lin_grad(1.95, 1.8, 1.95, 2.65, [(0, "#4a5a3a"), (0.6, "#8a9a7a"), (1, "#c8b88a")]))
            ctx.rectangle(1.96, 1.81, 1.18, 0.83)
            ctx.fill()
            for k in range(3):
                setc(ctx, "#e8dcc0")
                ctx.rectangle(1.75 + k * 0.6, 1.42, 0.06, 0.18)
                ctx.fill()

        def back_e(ctx, cv):
            ctx.set_source(rad_grad(2.55, 0.2, 0.0, 0.5, [(0, "#fff0b0"), (0.3, "#ffb050"), (1, (1, 0.4, 0.1, 0))]))
            ctx.move_to(2.0, 0)
            ctx.line_to(2.0, 0.75)
            ctx.arc(2.55, 0.75, 0.55, math.pi, 0)
            ctx.line_to(3.1, 0)
            ctx.close_path()
            ctx.fill()
            for k in range(7):
                setc(ctx, "#ffd070")
                x = 2.2 + k * 0.1
                poly(ctx, [(x - 0.05, 0.1), (x, 0.3 + 0.12 * (k % 3)), (x + 0.05, 0.1)])
                ctx.fill()
        self.wall_back(back, emit=back_e, ppm=320, emit_gain=4.0)

        def left(ctx, cv):
            fill_material(ctx, plaster, 200)
            ctx.paint()
            wood_panels(ctx, -2, 6, 0, 0.8, "#4a3020", seed=3, panel_w=0.7, ppm=200)
            for (z0, z1, y0, y1) in WIN:
                setc(ctx, "#c8b08a")
                ctx.rectangle(z0 - 0.12, y0 - 0.12, (z1 - z0) + 0.24, (y1 - y0) + 0.24)
                ctx.fill()
                cut(ctx, z0, y0, z1 - z0, y1 - y0)
                window_frame(ctx, z0, y0, z1 - z0, y1 - y0, "#4a3424", mull=2,
                             transom=[y0 + k * 0.62 for k in range(1, 4)], lw=0.05)
        self.wall_left(left, ppm=200)

        def right(ctx, cv):
            fill_material(ctx, plaster, 200)
            ctx.paint()
            bookshelf(ctx, rnd, -1.5, 6.0, 0.0, 3.2, shelf_h=0.4, wood="#3e2818")
        self.wall_right(right, ppm=180)

        def floor(ctx, cv):
            wood = material("wood", 512, 1024, "#5a3a26", seed=4, grain=40, aspect=0.12)
            fill_material(ctx, wood, 300)
            ctx.paint()
            # alfombra persa
            setc(ctx, "#7a2a22")
            rrect(ctx, -2.2, 2.4, 4.6, 3.0, 0.03)
            ctx.fill()
            setc(ctx, "#1e2a4a")
            ctx.set_line_width(0.12)
            rrect(ctx, -2.0, 2.6, 4.2, 2.6, 0.03)
            ctx.stroke()
            for i in range(40):
                x, z = rnd.uniform(-1.8, 2.0), rnd.uniform(2.8, 5.0)
                setc(ctx, rnd.choice(["#c8a058", "#1e2a4a", "#e8d8b0", "#4a1a18"]), 0.8)
                ellipse(ctx, x, z, 0.08, 0.05, rnd.uniform(0, 3))
                ctx.fill()
        self.floor(floor, ppm=260, detail=(0.1, 10.0, 0.2))

        def ceil(ctx, cv):
            setc(ctx, "#c8b89a")
            ctx.paint()
        self.ceiling(ceil)

        # sillón de Samuel y mesita
        def chair(ctx, cv):
            leather = "#5a2a1e"
            m = lambda pts: [(2.0 - x, y) for x, y in pts]   # espejo: respaldo a la derecha
            setc(ctx, shade(leather, 0.8))
            smooth_path(ctx, m([(0.35, 0.0), (0.3, 1.25), (0.5, 1.35), (0.62, 1.2), (0.62, 0.42), (1.5, 0.42),
                                (1.55, 0.7), (1.68, 0.72), (1.7, 0.0)]), tension=0.3)
            ctx.fill()
            setc(ctx, leather)
            smooth_path(ctx, m([(0.62, 0.42), (1.5, 0.42), (1.55, 0.7), (1.68, 0.72), (1.7, 0.2), (0.6, 0.2)]),
                        tension=0.3)
            ctx.fill()
            setc(ctx, "#c8a058", 0.8)
            for k in range(8):
                ellipse(ctx, 1.64, 0.2 + k * 0.13, 0.012, 0.012)
                ctx.fill()
            # mesita con lámpara, gafas y taza
            setc(ctx, "#3a2418")
            ctx.rectangle(-0.45, 0, 0.05, 0.62)
            ctx.rectangle(-0.05, 0, 0.05, 0.62)
            ctx.rectangle(-0.55, 0.62, 0.65, 0.04)
            ctx.fill()
            setc(ctx, "#e8e0d0")
            ctx.rectangle(-0.42, 0.66, 0.08, 0.08)
            ctx.fill()
            setc(ctx, "#b8984a")
            ctx.rectangle(-0.16, 0.66, 0.03, 0.4)
            ctx.fill()
            setc(ctx, "#d8c8a0")
            poly(ctx, [(-0.3, 1.0), (0.02, 1.0), (-0.03, 1.2), (-0.25, 1.2)])
            ctx.fill()

        def chair_e(ctx, cv):
            setc(ctx, "#ffe0a8")
            poly(ctx, [(-0.3, 1.0), (0.02, 1.0), (-0.03, 1.2), (-0.25, 1.2)])
            ctx.fill()
        self.plane(2, 4.5, (-0.7, 1.9, -0.05, 1.5), 450, chair, emit=chair_e, emit_gain=3.0,
                   inflate=(10.0, 1.4, 0.4))

        self.dust = Particles(eng, 1_600_000, (-3.6, 0, -1), (4, 3.2, 6), seed=12, drift=(0.0, -0.004, 0.0),
                              turb=0.06, size_m=0.001, color=(1, 0.9, 0.75), gain=0.3, bright_pow=6.0)
        self.dust.win_mode = True
        self.add_particles(4.0, self.dust)
        self.embers = Particles(eng, 6000, (2.15, 0.2, 5.85), (2.95, 1.25, 5.95), seed=13, drift=(0.0, 0.35, 0.0),
                                turb=0.04, size_m=0.004, color=(1.0, 0.45, 0.12), gain=12.0, bright_pow=2.0)
        self.add_particles(5.9, self.embers)
        self.add_volume(dict(sigma_s=0.025, sigma_t=0.012, g=0.6, box=((-3.6, 0, -2), (4, 3.2, 6)), steps=28,
                             noise=0.5, light_k=0.5), [6.0, 4.4, 2.0, -2.0])
        self.char_rim = 0.4

    def env(self, t):
        from engine.physics import fbm1
        fire = 1.0 + 0.25 * fbm1(t * 3.0, 3.0) + 0.1 * math.sin(t * 17.0)
        lights = [((2.55, 0.45, 5.6), 0.25, K1900 * 5.0 * fire), ((-0.15, 1.1, 4.4), 0.1, K2700 * 1.2)]
        e = self.interior_env(self.sun, 1.0, self.windows, lights, amb_col=(0.55, 0.58, 0.68), amb_k=0.8,
                              bounce_col=(0.85, 0.65, 0.45), haze_sigma=0.01, fog_col=(0.02, 0.016, 0.012))
        return e

    def sky(self, t):
        return dict(sun_dir=self.sun, haze=1.5, disk=1.0)

    def post(self, t):
        return dict(exposure=7.0, wb=(1.0, 1.0, 1.0), sat=1.0, contrast=1.08, bloom=0.07, bloom_thresh=0.45,
                    lift=(0.012, 0.01, 0.012), shadow_tint=(0.0, 0.002, 0.014), high_tint=(0.03, 0.014, -0.014),
                    vignette=0.55, grain=0.024, rays=dict(thresh=0.5, decay=0.975, density=1.0, weight=0.1))
