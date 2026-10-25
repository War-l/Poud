"""Sala del tribunal (escena 2)."""
import math
import random

import cairo
import numpy as np

from engine import physics as ph
from engine.gl import Particles
from engine.paint import (hx, mix, shade, setc, ellipse, smooth_path, poly, lin_grad, rad_grad, material,
                          fill_material, rrect)
from sets.common import foliage_cluster
from sets.room import Room, cut, window_frame, wood_panels

WIN = [(3.0, 4.8, 1.5, 6.2), (7.0, 8.8, 1.5, 6.2), (11.0, 12.8, 1.5, 6.2)]   # (z0, z1, y0, y1) en x=-7
GREENS = ["#2a3a24", "#3a4e2e", "#4e6a3a", "#6a8a48", "#8aa860"]


def scales_emblem(ctx, cx, cy, s, col="#c8a050"):
    setc(ctx, col)
    ctx.set_line_width(0.05 * s)
    ctx.move_to(cx, cy - 0.9 * s)
    ctx.line_to(cx, cy + 0.8 * s)
    ctx.stroke()
    ctx.move_to(cx - 0.8 * s, cy + 0.55 * s)
    ctx.line_to(cx + 0.8 * s, cy + 0.55 * s)
    ctx.stroke()
    for sx in (-1, 1):
        x = cx + sx * 0.8 * s
        ctx.set_line_width(0.015 * s)
        ctx.move_to(x, cy + 0.55 * s)
        ctx.line_to(x - 0.25 * s, cy + 0.05 * s)
        ctx.move_to(x, cy + 0.55 * s)
        ctx.line_to(x + 0.25 * s, cy + 0.05 * s)
        ctx.stroke()
        ctx.move_to(x - 0.3 * s, cy + 0.05 * s)
        ctx.curve_to(x - 0.2 * s, cy - 0.12 * s, x + 0.2 * s, cy - 0.12 * s, x + 0.3 * s, cy + 0.05 * s)
        ctx.close_path()
        ctx.fill()
    poly(ctx, [(cx - 0.3 * s, cy - 0.9 * s), (cx + 0.3 * s, cy - 0.9 * s), (cx + 0.15 * s, cy - 0.8 * s),
               (cx - 0.15 * s, cy - 0.8 * s)])
    ctx.fill()
    ellipse(ctx, cx, cy + 0.85 * s, 0.08 * s, 0.08 * s)
    ctx.fill()
    # corona de laurel
    for sx in (-1, 1):
        for i in range(9):
            a = math.pi * (0.15 + i * 0.08)
            x = cx + sx * math.cos(a) * 1.15 * s
            y = cy - 0.1 * s - math.sin(a) * 0.0 + (i - 4) * 0.0
            y = cy + math.sin(a - 0.5) * 1.0 * s - 0.2 * s
            ellipse(ctx, x, y, 0.09 * s, 0.035 * s, sx * a)
            ctx.fill()


class Court(Room):
    def __init__(self, eng):
        super().__init__(eng, 7.0, 7.0, 16.0, 8.0, near=-3.0)
        self.sun = ph.sun_dir(30.0, -68.0)
        rnd = random.Random(12)
        plaster = material("plaster", 512, 512, "#cdb592", seed=4, scale=90)

        # exterior visto por las ventanas: copas de árboles bajo el sol
        def outside(ctx, cv):
            for i in range(14):
                cz = rnd.uniform(-2, 20)
                foliage_cluster(ctx, rnd, cz, rnd.uniform(4.0, 9.0), rnd.uniform(1.5, 3.0), rnd.uniform(1.2, 2.4),
                                GREENS, (0.4, 0.7), n=700, leaf=0.12)
        self.plane(0, -16.0, (-4, 24, 0, 14), 60, outside, key=40, flat=1.0)

        def left(ctx, cv):
            fill_material(ctx, plaster, 160)
            ctx.paint()
            wood_panels(ctx, -3, 16, 0, 2.3, "#6a5038", seed=1, panel_w=1.1, ppm=160)
            for (z0, z1, y0, y1) in WIN:
                # derrame (grosor del muro) y marco
                setc(ctx, "#b8a07c")
                ctx.rectangle(z0 - 0.25, y0 - 0.25, (z1 - z0) + 0.5, (y1 - y0) + 0.25)
                ctx.fill()
                cut(ctx, z0, y0, z1 - z0, y1 - y0, arch=True)
                window_frame(ctx, z0, y0, z1 - z0, y1 - y0, "#3a2a1e", mull=2,
                             transom=[y0 + k * 0.8 for k in range(1, 6)], lw=0.07, arch=True)
            # pilastras
            for z in (1.2, 5.9, 9.9, 14.4):
                setc(ctx, "#bfa47e")
                ctx.rectangle(z - 0.3, 2.3, 0.6, 5.7)
                ctx.fill()
                setc(ctx, "#000000", 0.12)
                ctx.rectangle(z + 0.18, 2.3, 0.12, 5.7)
                ctx.fill()
            setc(ctx, "#8a6a48")
            ctx.rectangle(-3, 7.2, 19, 0.25)
            ctx.fill()
        self.wall_left(left, ppm=180)

        def right(ctx, cv):
            fill_material(ctx, plaster, 160)
            ctx.paint()
            wood_panels(ctx, -3, 16, 0, 3.0, "#6a5038", seed=2, panel_w=1.0, ppm=160)
            for z in (4.0, 9.0):
                setc(ctx, "#a8844a")
                ctx.rectangle(z - 0.7, 3.8, 1.4, 1.8)
                ctx.fill()
                setc(ctx, "#3a3028")
                ctx.rectangle(z - 0.6, 3.9, 1.2, 1.6)
                ctx.fill()
                setc(ctx, "#6a5a4a")
                ellipse(ctx, z, 4.9, 0.25, 0.32)
                ctx.fill()
            setc(ctx, "#3a2418")
            ctx.rectangle(12.5, 0, 1.6, 2.8)
            ctx.fill()
        self.wall_right(right, ppm=150)

        def back(ctx, cv):
            fill_material(ctx, plaster, 200)
            ctx.paint()
            wood_panels(ctx, -7, 7, 0, 2.6, "#5e4630", seed=3, panel_w=1.2, ppm=200)
            # dosel de madera tras el estrado
            setc(ctx, "#4a3422")
            poly(ctx, [(-3.2, 2.6), (-3.2, 5.0), (0, 5.3), (3.2, 5.0), (3.2, 2.6)])
            ctx.fill()
            wood_panels(ctx, -3.0, 3.0, 2.6, 4.8, "#6e5238", seed=5, panel_w=1.0, ppm=200)
            scales_emblem(ctx, 0.0, 6.6, 0.5)
            # inscripción
            ctx.save()
            ctx.select_font_face("EB Garamond", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
            ctx.set_font_size(0.34)
            txt = "LA LEY ES IGUAL PARA TODOS"
            ext = ctx.text_extents(txt)
            ctx.move_to(-ext.width / 2 - 0.1, 5.55)
            ctx.scale(1, -1)
            setc(ctx, "#d6b066")
            ctx.show_text(txt)
            ctx.restore()
            # puertas laterales
            for x in (-5.6, 4.4):
                setc(ctx, "#2e1e14")
                ctx.rectangle(x, 0, 1.2, 2.9)
                ctx.fill()
                setc(ctx, "#5a3a24")
                ctx.rectangle(x + 0.08, 0, 0.5, 2.8)
                ctx.rectangle(x + 0.62, 0, 0.5, 2.8)
                ctx.fill()
            # reloj
            setc(ctx, "#2a1e16")
            ellipse(ctx, 5.0, 5.6, 0.42, 0.42)
            ctx.fill()
            setc(ctx, "#efe6d0")
            ellipse(ctx, 5.0, 5.6, 0.35, 0.35)
            ctx.fill()
            setc(ctx, "#1a1410")
            ctx.set_line_width(0.03)
            ctx.move_to(5.0, 5.6)
            ctx.line_to(5.0, 5.86)
            ctx.move_to(5.0, 5.6)
            ctx.line_to(5.17, 5.52)
            ctx.stroke()
            setc(ctx, "#8a6a48")
            ctx.rectangle(-7, 7.2, 14, 0.25)
            ctx.fill()
        self.wall_back(back, ppm=230)

        def floor(ctx, cv):
            wood = material("wood", 512, 1024, "#7a5a3e", seed=7, grain=50, aspect=0.12)
            fill_material(ctx, wood, 220)
            ctx.paint()
            setc(ctx, "#000000", 0.25)
            ctx.set_line_width(0.01)
            x = -7.0
            while x < 7:
                ctx.move_to(x, -3)
                ctx.line_to(x, 16)
                x += 0.16
            ctx.stroke()
            # alfombra del pasillo central
            setc(ctx, "#6a1e1e")
            ctx.rectangle(-0.9, -3, 1.8, 15.0)
            ctx.fill()
            setc(ctx, "#c8a050", 0.6)
            ctx.set_line_width(0.04)
            ctx.rectangle(-0.82, -3, 1.64, 15.0)
            ctx.stroke()
        self.floor(floor, ppm=200, detail=(0.12, 8.0, 0.2))

        def ceiling(ctx, cv):
            setc(ctx, "#b8a07a")
            ctx.paint()
            setc(ctx, "#8a7050")
            ctx.set_line_width(0.15)
            for x in range(-7, 8, 2):
                ctx.move_to(x, -3)
                ctx.line_to(x, 16)
            for z in range(-3, 17, 2):
                ctx.move_to(-7, z)
                ctx.line_to(7, z)
            ctx.stroke()
        self.ceiling(ceiling)

        # estrado del juez (tarima 0,5 m + mesa de 0,75 m)
        def bench(ctx, cv):
            setc(ctx, "#3a2a1c")
            ctx.rectangle(-3.6, 0, 7.2, 0.5)
            ctx.fill()
            wood_panels(ctx, -3.4, 3.4, 0.5, 1.22, "#6e5034", seed=8, panel_w=1.13, ppm=260)
            setc(ctx, "#8a6440")
            ctx.rectangle(-3.5, 1.2, 7.0, 0.06)
            ctx.fill()
            for x, h, c in ((-2.6, 0.12, "#c8b48a"), (-2.4, 0.08, "#8a5a32"), (2.2, 0.15, "#d8c8a0"),
                            (2.45, 0.1, "#5a6a7a")):
                setc(ctx, c)
                ctx.rectangle(x, 1.26, 0.35, h)
                ctx.fill()
            setc(ctx, "#2a5a3a")
            ellipse(ctx, -1.6, 1.58, 0.17, 0.08)
            ctx.fill()
            setc(ctx, "#b8984a")
            ctx.rectangle(-1.62, 1.26, 0.04, 0.32)
            ctx.fill()
            setc(ctx, "#c8a050")
            rrect(ctx, -0.5, 0.85, 1.0, 0.16, 0.02)
            ctx.fill()
        self.plane(2, 13.0, (-3.7, 3.7, -0.05, 1.8), 300, bench, inflate=(6.0, 1.0, 0.4))

        # banquillo del acusado
        def dock(ctx, cv):
            setc(ctx, "#5a3a22")
            ctx.rectangle(-2.6, 0.95, 1.9, 0.08)
            ctx.fill()
            for x in np.arange(-2.55, -0.7, 0.18):
                setc(ctx, "#4a2e1a")
                ctx.rectangle(x, 0, 0.05, 0.95)
                ctx.fill()
            setc(ctx, "#4a2e1a")
            ctx.rectangle(-2.6, 0, 0.08, 1.0)
            ctx.rectangle(-0.78, 0, 0.08, 1.0)
            ctx.fill()
        self.plane(2, 8.0, (-2.8, -0.5, -0.05, 1.1), 400, dock)

        # mesas de las partes
        def tables(ctx, cv):
            for x0 in (-6.2, 2.4):
                setc(ctx, "#5a3a22")
                ctx.rectangle(x0, 0.72, 3.4, 0.08)
                ctx.fill()
                setc(ctx, "#4a2e1a")
                ctx.rectangle(x0 + 0.1, 0, 3.2, 0.72)
                ctx.fill()
                for k in range(3):
                    setc(ctx, rnd.choice(["#d8c8a0", "#c8b48a", "#8a5a32"]))
                    ctx.rectangle(x0 + 0.4 + k * 0.9, 0.8, 0.4, 0.04 + k * 0.02)
                    ctx.fill()
        self.plane(2, 10.0, (-6.4, 6.0, -0.05, 1.0), 300, tables)

        # bancos del público con algunos asistentes (de espaldas)
        def pews(z, seed):
            def p(ctx, cv):
                r2 = random.Random(seed)
                for x0, x1 in ((-6.5, -1.0), (1.0, 6.5)):
                    setc(ctx, "#3e2616")
                    ctx.rectangle(x0, 0, x1 - x0, 1.05)
                    ctx.fill()
                    wood_panels(ctx, x0, x1, 0.1, 1.0, "#5a3820", seed=seed, panel_w=0.9, ppm=300)
                    setc(ctx, "#6a4428")
                    ctx.rectangle(x0, 1.0, x1 - x0, 0.06)
                    ctx.fill()
                    for i in range(r2.randint(1, 3)):
                        x = r2.uniform(x0 + 0.4, x1 - 0.4)
                        c = r2.choice(["#3a3a44", "#5a4a3a", "#2a3a4a", "#6a5a4a"])
                        setc(ctx, c)
                        smooth_path(ctx, [(x - 0.24, 1.0), (x - 0.22, 1.32), (x, 1.4), (x + 0.22, 1.32),
                                          (x + 0.24, 1.0)])
                        ctx.fill()
                        setc(ctx, r2.choice(["#1d1714", "#3b2a20", "#8a7a6a", "#c8c0b8"]))
                        ellipse(ctx, x, 1.55, 0.11, 0.13)
                        ctx.fill()
            return p
        self.plane(2, 4.6, (-6.6, 6.6, -0.05, 1.7), 280, pews(4.6, 1), inflate=(10.0, 1.5, 0.4))
        self.plane(2, 2.8, (-6.6, 6.6, -0.05, 1.7), 220, pews(2.8, 2), inflate=(10.0, 1.5, 0.4))

        # polvo en suspensión: solo visible dentro de los haces de sol
        self.dust = Particles(eng, 2_000_000, (-6.9, 0.0, 0.0), (6.9, 7.5, 15.5), seed=3, drift=(0.0, -0.01, 0.0),
                              turb=0.08, size_m=0.0011, color=(1.0, 0.93, 0.82), gain=0.35, bright_pow=6.0)
        self.dust.win_mode = True
        self.add_volume(dict(sigma_s=0.022, sigma_t=0.012, g=0.65, box=((-7, 0, -3), (7, 8, 16)), steps=32, noise=0.6),
                        [16.0, 12.9, 8.6, 4.5, 2.7, -3.0])
        self.add_particles(9.0, self.dust)
        self.windows = dict(axis=0, value=-7.0, rects=WIN, blinds=(1.25, 0.06, 1.0, 2.0))
        self.char_rim = 0.4

    def env(self, t):
        e = self.interior_env(self.sun, 1.0, self.windows, [], amb_col=(0.62, 0.66, 0.74), amb_k=1.1,
                              bounce_col=(0.85, 0.7, 0.55), haze_sigma=0.012, fog_col=(0.035, 0.03, 0.025))
        return e

    def sky(self, t):
        return dict(sun_dir=self.sun, haze=1.0, disk=1.0)

    def post(self, t):
        return dict(exposure=7.5, wb=(0.98, 1.0, 1.03), sat=0.96, contrast=1.08, bloom=0.06, bloom_thresh=0.35,
                    lift=(0.01, 0.008, 0.012), shadow_tint=(0.0, 0.004, 0.014), high_tint=(0.025, 0.012, -0.012),
                    vignette=0.5, grain=0.022, rays=dict(thresh=0.5, decay=0.975, density=1.0, weight=0.12))
