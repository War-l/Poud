"""Exteriores urbanos: escalinata del Palacio de Justicia (8), plaza al atardecer (10), calle del recuerdo (7)."""
import math
import random

import cairo
import numpy as np

from engine import physics as ph
from engine.gl import Particles
from engine.paint import (hx, mix, shade, setc, ellipse, smooth_path, poly, lin_grad, rad_grad, material,
                          fill_material, rrect)
from sets.common import SetBase, foliage_cluster, tree_round, flowers
from sets.room import window_frame

K2700 = ph.blackbody(2700)

FACADES = ["#e6cfa8", "#d8a882", "#efe0c4", "#c98f6a", "#e2bb8e", "#d7b894", "#b8c4b8", "#e8d8b8"]


def facade_row(ctx, rnd, x0, x1, base_y, hmin, hmax, emit=False, lit=0.0, dark=0.0, light=(0.6, 0.5),
               balconies=True):
    x = x0
    r2 = random.Random(int(x0 * 7 + hmin))
    while x < x1:
        w = r2.uniform(5.0, 9.0)
        h = r2.uniform(hmin, hmax)
        col = r2.choice(FACADES)
        if not emit:
            ctx.set_source(lin_grad(x, base_y, x + w, base_y, [(0, mix(col, "#2a2238", dark)),
                                                               (1, mix(shade(col, 0.88), "#2a2238", dark))]))
            ctx.rectangle(x, base_y, w, h)
            ctx.fill()
            setc(ctx, mix("#9a4a32", "#2a1a24", dark))
            ctx.rectangle(x - 0.2, base_y + h, w + 0.4, 0.35)
            ctx.fill()
            setc(ctx, mix("#f0e6d4", "#2a2238", dark), 0.7)
            ctx.rectangle(x, base_y + h - 0.25, w, 0.12)
            ctx.fill()
        cols = max(2, int(w / 1.6))
        rows = max(2, int((h - 1.0) / 2.8))
        for r in range(rows):
            for c in range(cols):
                wx = x + (c + 0.5) * w / cols - 0.45
                wy = base_y + 1.2 + r * 2.8
                if wy + 1.6 > base_y + h - 0.4:
                    continue
                is_lit = r2.random() < lit
                if emit:
                    if is_lit:
                        setc(ctx, r2.choice(["#ffcf80", "#ffb868", "#ffe0a8"]))
                        rrect(ctx, wx, wy, 0.9, 1.6, 0.08)
                        ctx.fill()
                    continue
                setc(ctx, mix("#4a3a30", "#120c14", dark) if not is_lit else "#e8b060")
                rrect(ctx, wx, wy, 0.9, 1.6, 0.08)
                ctx.fill()
                setc(ctx, mix("#5e7a6a", "#1a1a24", dark))
                ctx.rectangle(wx - 0.32, wy, 0.28, 1.6)
                ctx.rectangle(wx + 0.94, wy, 0.28, 1.6)
                ctx.fill()
                if balconies and r > 0 and r2.random() < 0.4:
                    setc(ctx, mix("#2a2420", "#0a0a10", dark))
                    ctx.rectangle(wx - 0.25, wy - 0.05, 1.4, 0.06)
                    ctx.fill()
                    for k in range(8):
                        ctx.rectangle(wx - 0.22 + k * 0.18, wy - 0.05, 0.025, 0.55)
                    ctx.fill()
                    ctx.rectangle(wx - 0.25, wy + 0.5, 1.4, 0.04)
                    ctx.fill()
                    if r2.random() < 0.6:
                        foliage_cluster(ctx, r2, wx + 0.45, wy + 0.6, 0.5, 0.18,
                                        ["#3a5a2a", "#5a7a3a", "#d8506a", "#e8c050"], light, n=60, leaf=0.06,
                                        ao=False)
        if not emit and r2.random() < 0.7:
            dx = x + r2.uniform(0.6, max(0.7, w - 1.8))
            setc(ctx, mix("#4a3020", "#100a10", dark))
            ctx.move_to(dx, base_y)
            ctx.line_to(dx, base_y + 2.0)
            ctx.arc(dx + 0.6, base_y + 2.0, 0.6, math.pi, 0)
            ctx.line_to(dx + 1.2, base_y)
            ctx.close_path()
            ctx.fill()
        x += w


def lamp_post(ctx, x, h=3.6):
    setc(ctx, "#1e1c1a")
    ctx.rectangle(x - 0.05, 0, 0.1, h)
    ctx.fill()
    ctx.rectangle(x - 0.14, 0, 0.28, 0.3)
    ctx.fill()
    poly(ctx, [(x - 0.2, h), (x + 0.2, h), (x + 0.14, h + 0.45), (x - 0.14, h + 0.45)])
    ctx.fill()
    setc(ctx, "#e8d8b0", 0.7)
    poly(ctx, [(x - 0.15, h + 0.04), (x + 0.15, h + 0.04), (x + 0.11, h + 0.4), (x - 0.11, h + 0.4)])
    ctx.fill()
    setc(ctx, "#1e1c1a")
    poly(ctx, [(x - 0.25, h + 0.45), (x + 0.25, h + 0.45), (x, h + 0.7)])
    ctx.fill()


def lamp_glass(ctx, x, h=3.6):
    setc(ctx, "#ffe2a8")
    poly(ctx, [(x - 0.15, h + 0.04), (x + 0.15, h + 0.04), (x + 0.11, h + 0.4), (x - 0.11, h + 0.4)])
    ctx.fill()


def paving(ctx, rnd, x0, x1, z0, z1, base, ppm, size=0.5):
    stone = material("stone", 512, 512, base, seed=3, scale=8)
    fill_material(ctx, stone, ppm)
    ctx.rectangle(x0, z0, x1 - x0, z1 - z0)
    ctx.fill()
    setc(ctx, "#000000", 0.22)
    ctx.set_line_width(0.02)
    z = z0
    row = 0
    while z < z1:
        off = (row % 2) * size * 0.5
        x = x0 - off
        while x < x1:
            rrect(ctx, x + 0.02, z + 0.02, size - 0.04, size * 0.7 - 0.04, 0.05)
            ctx.stroke()
            x += size
        z += size * 0.7
        row += 1


class Plaza(SetBase):
    """mood: steps | sunset | memory"""

    def __init__(self, eng, mood="sunset"):
        super().__init__(eng)
        self.mood = mood
        rnd = random.Random(31)
        if mood == "steps":
            self.sun, self.haze = ph.sun_dir(38.0, 30.0), 7.0
        elif mood == "sunset":
            self.sun, self.haze = ph.sun_dir(4.5, 62.0), 1.8
        else:
            self.sun, self.haze = ph.sun_dir(24.0, -150.0), 3.0   # sol detrás de la cámara: fachada iluminada
        dusk = mood == "sunset"
        L = (0.8, 0.3) if dusk else ((-0.5, 0.7) if mood == "memory" else (0.2, 0.9))

        def far(ctx, cv):
            facade_row(ctx, rnd, -120, 120, 0, 10, 22, light=L, balconies=False)
            setc(ctx, "#b8a890")
            for x in (-60, 40):
                ctx.rectangle(x, 0, 6, 34)
                ctx.fill()
                poly(ctx, [(x - 1, 34), (x + 3, 42), (x + 7, 34)])
                ctx.fill()
        self.plane(2, 160.0, (-130, 130, -1, 45), 14, far, flat=0.7)

        if mood == "steps":
            stone = material("stone", 512, 512, "#cfc4b0", seed=7, scale=40)

            def court(ctx, cv):
                fill_material(ctx, stone, 150)
                ctx.rectangle(-16, 0, 32, 13)
                ctx.fill()
                # escalinata
                for k in range(9):
                    y = k * 0.2
                    setc(ctx, mix("#d8ccb8", "#a89c88", (k % 2) * 0.4))
                    ctx.rectangle(-9 + k * 0.15, y, 18 - k * 0.3, 0.2)
                    ctx.fill()
                    setc(ctx, "#000000", 0.2)
                    ctx.rectangle(-9 + k * 0.15, y, 18 - k * 0.3, 0.025)
                    ctx.fill()
                # puertas de bronce
                setc(ctx, "#3a2e22")
                ctx.rectangle(-1.2, 1.8, 2.4, 4.0)
                ctx.fill()
                setc(ctx, "#6a5434")
                for xx in (-1.1, 0.05):
                    ctx.rectangle(xx, 1.9, 1.05, 3.8)
                    ctx.fill()
                # columnas estriadas
                for i in range(6):
                    x = -6.25 + i * 2.5
                    ctx.set_source(lin_grad(x - 0.45, 0, x + 0.45, 0, [(0, "#f0e8d8"), (0.4, "#e0d6c2"),
                                                                       (1, "#a89c86")]))
                    ctx.rectangle(x - 0.42, 1.8, 0.84, 7.0)
                    ctx.fill()
                    setc(ctx, "#000000", 0.12)
                    ctx.set_line_width(0.03)
                    for k in range(5):
                        ctx.move_to(x - 0.32 + k * 0.16, 2.1)
                        ctx.line_to(x - 0.32 + k * 0.16, 8.5)
                    ctx.stroke()
                    setc(ctx, "#e8dcc6")
                    ctx.rectangle(x - 0.55, 8.75, 1.1, 0.25)
                    ctx.rectangle(x - 0.5, 1.8, 1.0, 0.2)
                    ctx.fill()
                # entablamento e inscripción
                setc(ctx, "#ddd2bc")
                ctx.rectangle(-8, 9.0, 16, 1.4)
                ctx.fill()
                ctx.save()
                ctx.select_font_face("EB Garamond", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
                ctx.set_font_size(0.62)
                txt = "PALACIO DE JUSTICIA"
                ext = ctx.text_extents(txt)
                ctx.move_to(-ext.width / 2, 9.48)
                ctx.scale(1, -1)
                setc(ctx, "#5a5040")
                ctx.show_text(txt)
                ctx.restore()
                setc(ctx, "#e6dcc8")
                poly(ctx, [(-8.3, 10.4), (8.3, 10.4), (0, 13.2)])
                ctx.fill()
                setc(ctx, "#b8ac98")
                poly(ctx, [(-7.2, 10.6), (7.2, 10.6), (0, 12.7)])
                ctx.fill()
                # alas laterales con ventanas
                for sx in (-1, 1):
                    for r in range(2):
                        for c in range(3):
                            x = sx * (9.5 + c * 2.0)
                            setc(ctx, "#3a3440")
                            rrect(ctx, x - 0.5, 2.6 + r * 3.6, 1.0, 2.2, 0.1)
                            ctx.fill()
                            window_frame(ctx, x - 0.5, 2.6 + r * 3.6, 1.0, 2.2, "#e8e0d0", mull=2, lw=0.05)
                # banderas
                for x, c in ((-9.4, "#c8102e"), (9.4, "#2a4aa8")):
                    setc(ctx, "#4a4a4a")
                    ctx.rectangle(x, 10.4, 0.06, 3.5)
                    ctx.fill()
                    setc(ctx, c)
                    smooth_path(ctx, [(x + 0.06, 13.8), (x + 1.2, 13.65), (x + 2.1, 13.7), (x + 2.0, 12.8),
                                      (x + 1.1, 12.85), (x + 0.06, 12.9)], tension=0.4)
                    ctx.fill()
            self.plane(2, 24.0, (-16, 16, -0.1, 15), 120, court, flat=0.4)

            def lamps(ctx, cv):
                for x in (-6.5, 6.5):
                    lamp_post(ctx, x)
                for x in (-10.5, 10.5):
                    setc(ctx, "#8a8070")
                    ctx.rectangle(x - 0.7, 0, 1.4, 0.7)
                    ctx.fill()
                    tree_round(ctx, rnd, x, 0.7, 4.5, 3.2, ["#2a3a22", "#3e5230", "#56703e", "#7a9050"],
                               light=L, leaf=0.07, n=900)
            self.plane(2, 16.0, (-13, 13, -0.1, 6), 200, lamps, inflate=(12.0, 1.4, 0.5))

            self.leaves = Particles(eng, 4000, (-10, 0.05, 3), (10, 4, 20), seed=5, drift=(1.4, -0.25, 0.1),
                                    turb=0.4, size_m=0.03, color=(0.55, 0.4, 0.22), gain=0.06, bright_pow=0.5)
            self.add_particles(9.0, self.leaves)

        if mood == "sunset":
            def houses(ctx, cv):
                facade_row(ctx, rnd, -40, 40, 0, 9, 15, light=L)

            def houses_e(ctx, cv):
                facade_row(ctx, rnd, -40, 40, 0, 9, 15, emit=True, lit=0.3)
            self.plane(2, 40.0, (-40, 40, -0.1, 18), 90, houses, emit=houses_e, emit_gain=1.6, flat=0.0)

            def trees(ctx, cv):
                for x in (-14, -6.5, 7.5, 15):
                    setc(ctx, "#4a3a2c")
                    ctx.rectangle(x - 0.15, 0, 0.3, 3.5)
                    ctx.fill()
                    tree_round(ctx, rnd, x, 2.0, 6.5, 5.0, ["#3a4a22", "#56692e", "#86903e", "#c8b054", "#e8c870"],
                               light=L, leaf=0.12, n=1400)
            self.plane(2, 26.0, (-18, 18, -0.1, 9), 140, trees, flat=1.0, inflate=(18.0, 1.6, 0.6))

            def fountain(ctx, cv):
                st = "#c8baa2"
                ctx.set_source(lin_grad(-3, 0, 3, 0, [(0, shade(st, 0.7)), (0.6, st), (1, shade(st, 1.08))]))
                poly(ctx, [(-3.0, 0), (-3.0, 0.7), (3.0, 0.7), (3.0, 0)])
                ctx.fill()
                setc(ctx, shade(st, 1.1))
                ctx.rectangle(-3.15, 0.66, 6.3, 0.12)
                ctx.fill()
                ctx.set_source(lin_grad(-0.3, 0, 0.3, 0, [(0, shade(st, 0.7)), (1, shade(st, 1.05))]))
                ctx.rectangle(-0.25, 0.7, 0.5, 1.6)
                ctx.fill()
                ellipse(ctx, 0, 2.3, 1.2, 0.18)
                ctx.fill()
                ctx.rectangle(-0.12, 2.3, 0.24, 0.8)
                ctx.fill()
                setc(ctx, "#cfe8f0", 0.55)
                ctx.set_line_width(0.035)
                for sx in (-1, 1):
                    for k in range(3):
                        ctx.move_to(0, 3.1)
                        ctx.curve_to(sx * (0.5 + k * 0.2), 3.6, sx * (1.0 + k * 0.25), 3.0, sx * (1.15 + k * 0.1), 2.35)
                        ctx.stroke()
                        ctx.move_to(sx * 1.2, 2.3)
                        ctx.curve_to(sx * 1.6, 2.2, sx * 2.0, 1.4, sx * (2.2 + k * 0.2), 0.75)
                        ctx.stroke()
            self.plane(2, 18.0, (-3.3, 3.3, -0.05, 3.8), 260, fountain, inflate=(8.0, 1.2, 0.4))

            def lamps(ctx, cv):
                for x in (-7.0, 6.0):
                    lamp_post(ctx, x)

            def lamps_e(ctx, cv):
                for x in (-7.0, 6.0):
                    lamp_glass(ctx, x)
            self.plane(2, 13.0, (-8, 8, -0.1, 4.4), 220, lamps, emit=lamps_e, emit_gain=10.0)

            def bench(ctx, cv):
                wood = "#7a5236"
                setc(ctx, "#2a2420")
                for x in (-1.5, 0.3):
                    ctx.rectangle(x, 0, 0.06, 0.45)
                    ctx.fill()
                setc(ctx, wood)
                for k in range(3):
                    ctx.rectangle(-1.7, 0.42 + k * 0.03, 2.2, 0.025)
                    ctx.fill()
                for k in range(3):
                    ctx.rectangle(-1.7, 0.55 + k * 0.12, 2.2, 0.07)
                    ctx.fill()
            self.plane(2, 5.35, (-1.8, 0.6, -0.05, 0.95), 450, bench, inflate=(6.0, 1.0, 0.3))
            self.pollen = Particles(eng, 1_200_000, (-8, 0, 2), (8, 5, 30), seed=9, drift=(-0.06, 0.02, 0),
                                    turb=0.15, size_m=0.0012, color=(1.0, 0.8, 0.5), gain=0.08, bright_pow=5.0)
            self.pollen.phase = 0.7
            self.add_particles(8.0, self.pollen)

        if mood == "memory":
            def house(ctx, cv):
                wall = material("plaster", 512, 512, "#f2e8d8", seed=2, scale=60)
                fill_material(ctx, wall, 160)
                ctx.rectangle(-9, 0, 18, 7)
                ctx.fill()
                setc(ctx, "#b0603e")
                ctx.rectangle(-9.3, 7.0, 18.6, 0.4)
                ctx.fill()
                setc(ctx, "#c8b8a0")
                ctx.rectangle(-9, 0, 18, 0.35)
                ctx.fill()
                for x in (-4.0, 1.2, 5.6):
                    setc(ctx, "#3a4a5a")
                    rrect(ctx, x, 0.95, 1.1, 1.2, 0.04)
                    ctx.fill()
                    setc(ctx, "#2e5a6a")
                    ctx.rectangle(x - 0.35, 0.95, 0.3, 1.2)
                    ctx.rectangle(x + 1.15, 0.95, 0.3, 1.2)
                    ctx.fill()
                    setc(ctx, "#b0603e")
                    ctx.rectangle(x - 0.1, 0.85, 1.3, 0.12)
                    ctx.fill()
                    flowers(ctx, rnd, x, x + 1.1, 0.95, 1.1, ["#e04a6a", "#f0a040", "#f4ece0"], n=20, size=0.04)
                setc(ctx, "#5a3a24")
                ctx.rectangle(-1.6, 0.35, 1.2, 2.3)
                ctx.fill()
                for x in (-4.0, 1.2, 5.6):
                    setc(ctx, "#3a4a5a")
                    rrect(ctx, x, 3.8, 1.1, 1.6, 0.04)
                    ctx.fill()
                foliage_cluster(ctx, rnd, -7.0, 4.5, 1.6, 2.4, ["#3a5a2a", "#5a7a3a", "#c83a7a", "#e050a0"], L,
                                n=900, leaf=0.08)
            self.plane(2, 9.0, (-9.5, 9.5, -0.05, 7.6), 220, house, inflate=(10.0, 1.0, 0.4))
            self.motes = Particles(eng, 900_000, (-6, 0, 2), (6, 5, 9), seed=19, drift=(0.03, 0.01, 0), turb=0.1,
                                   size_m=0.0014, color=(1.0, 0.85, 0.6), gain=0.1, bright_pow=5.0)
            self.motes.phase = 0.7
            self.add_particles(5.0, self.motes)

        # suelo empedrado
        def ground_near(ctx, cv):
            paving(ctx, rnd, -30, 30, -2.0, 24, "#b0a490" if mood != "memory" else "#c8b8a0", 120, size=0.45)
        self.plane(1, 0.0, (-30, 30, -2.0, 24.0), 120, ground_near, detail=(0.18, 6.0, 1.0), key=24.5)

        def ground_far(ctx, cv):
            stone = material("stone", 512, 512, "#a89c88", seed=4, scale=6)
            fill_material(ctx, stone, 30)
            ctx.paint()
        self.plane(1, 0.0, (-150, 150, 24.0, 400), 12, ground_far, detail=(0.12, 1.5, 1.0), key=500)
        self.cast_shadows = mood != "steps"

    def env(self, t):
        s = self.sun
        sun_col = ph.sun_radiance_at_ground(s, self.haze)
        if not hasattr(self, "_amb"):
            self._amb = ph.sky_ambient(s, self.haze)
        amb, hz = self._amb
        rho = np.array([0.3, 0.27, 0.22])
        sigma = np.array([5.8, 13.5, 33.1]) * 1e-6 * 160 + 21e-6 * 80 * self.haze
        lights = []
        sun_on = 1.0
        if self.mood == "steps":
            sun_on = 0.12        # sol tapado por las nubes: domina la luz difusa
            amb = amb * 2.4
        if self.mood == "sunset":
            lights = [((-7.0, 3.8, 13.0), 0.2, K2700 * 25.0), ((6.0, 3.8, 13.0), 0.2, K2700 * 25.0)]
        e = dict(amb_top=amb, amb_bot=rho * (sun_col * max(s[1], 0) * sun_on + amb), sun_col=sun_col * sun_on,
                 sun_dir=s, lights=lights, sigma=sigma, fog=hz * 0.6, fog_sun=sun_col * 0.05 * self.haze,
                 rim_col=sun_col * 0.03, rim_dir=(-4.0 * np.sign(s[0]), 2.0))
        return e

    def sky(self, t):
        if self.mood == "steps":
            return dict(sun_dir=self.sun, haze=self.haze, disk=0.0, gain=1.0)
        return dict(sun_dir=self.sun, haze=self.haze, disk=1.0)

    def post(self, t):
        if self.mood == "steps":
            return dict(exposure=0.75, wb=(0.97, 1.0, 1.05), sat=0.82, contrast=1.04, bloom=0.04, bloom_thresh=4.0,
                        lift=(0.02, 0.022, 0.028), shadow_tint=(-0.004, 0.0, 0.012), high_tint=(0.0, 0.0, 0.0),
                        vignette=0.45, grain=0.024)
        if self.mood == "sunset":
            return dict(exposure=1.6, wb=(0.98, 1.0, 1.08), sat=1.08, contrast=1.08, bloom=0.08, bloom_thresh=2.5,
                        lift=(0.02, 0.012, 0.024), shadow_tint=(0.0, -0.004, 0.02), high_tint=(0.03, 0.01, -0.02),
                        vignette=0.5, grain=0.022, rays=dict(thresh=3.0, decay=0.97, density=1.0, weight=0.4))
        return dict(exposure=0.9, wb=(1.0, 1.0, 0.98), sat=0.85, contrast=0.94, bloom=0.16, bloom_thresh=1.5,
                    lift=(0.05, 0.04, 0.03), shadow_tint=(0.01, 0.0, -0.005), high_tint=(0.03, 0.02, 0.0),
                    vignette=0.9, grain=0.03, rays=dict(thresh=3.0, decay=0.97, density=1.0, weight=0.5))

    def light_screen(self):
        s = self.sun
        v = np.array([s[0], s[1] + 0.25])
        return tuple(v / np.linalg.norm(v))
