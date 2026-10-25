"""Jardín: escenas 1 (mañana) y 9 (atardecer)."""
import math
import random

import numpy as np

from engine import physics as ph
from engine.gl import Particles
from engine.paint import (hx, mix, shade, setc, ellipse, smooth_path, poly, lin_grad, rad_grad, material,
                          fill_material, value_noise, surface_from_rgba)
from sets.common import SetBase, foliage_cluster, tree_round, cypress, grass_tufts, flowers, fill_rect_grad

GREENS = ["#24361c", "#33502a", "#47683a", "#5f8446", "#7da257", "#a8c46c"]
GREENS_DARK = ["#1c2a18", "#25381f", "#30482a", "#3e5a32", "#4f6e3c"]
TREE_X, TREE_Z = 0.9, 7.0


class Garden(SetBase):
    def __init__(self, eng, mood="morning"):
        super().__init__(eng)
        self.mood = mood
        if mood == "morning":
            self.sun = ph.sun_dir(24.0, 128.0)   # sol de mañana lateral, detrás de la cámara a la derecha
            self.haze = 1.0
        else:
            self.sun = ph.sun_dir(3.2, -7.0)
            self.haze = 2.4
        rnd = random.Random(4)
        L = (0.5, 0.6) if mood == "morning" else (-0.6, 0.4)   # luz en el plano (para pintar volúmenes)
        evening = mood != "morning"

        # colinas lejanas
        def hills(ctx, cv):
            for k, (yb, amp, col) in enumerate([(30, 22, "#6f8a70"), (18, 16, "#5b7a58"), (8, 10, "#4b6a46")]):
                pts = [(-260, 0)]
                for i in range(80):
                    x = -260 + i * 520 / 79
                    y = yb + amp * (0.5 + 0.5 * math.sin(x * 0.013 + k * 2) * math.sin(x * 0.031 + k))
                    pts.append((x, y))
                pts.append((260, 0))
                setc(ctx, col)
                poly(ctx, pts)
                ctx.fill()
                r2 = random.Random(k)
                for i in range(260):
                    x = r2.uniform(-260, 260)
                    y = yb + amp * (0.5 + 0.5 * math.sin(x * 0.013 + k * 2) * math.sin(x * 0.031 + k))
                    setc(ctx, shade(col, r2.uniform(0.8, 1.1)))
                    ellipse(ctx, x, y - r2.uniform(0, 3), r2.uniform(2, 5), r2.uniform(2, 4))
                    ctx.fill()
        self.plane(2, 420.0, (-300, 300, -2, 80), 7, hills, flat=1.0)

        # arboleda
        def treeline(ctx, cv):
            r2 = random.Random(9)
            for i in range(70):
                x = r2.uniform(-95, 95)
                if r2.random() < 0.3:
                    cypress(ctx, r2, x, 0, r2.uniform(12, 20), r2.uniform(2.5, 3.5), GREENS_DARK, L)
                else:
                    tree_round(ctx, r2, x, 0, r2.uniform(8, 15), r2.uniform(7, 12), GREENS_DARK[1:], light=L,
                               leaf=0.5, n=500)
        self.plane(2, 140.0, (-100, 100, -1, 26), 20, treeline, flat=1.0)

        # casa de campo y invernadero
        def manor(ctx, cv):
            wall = material("plaster", 512, 512, "#d9c3a0", seed=3, scale=60)
            fill_material(ctx, wall, 40)
            poly(ctx, [(-14, 0), (-14, 7.5), (2, 7.5), (2, 0)])
            ctx.fill()
            setc(ctx, "#9a4a32")
            poly(ctx, [(-15, 7.4), (-6, 11.5), (3, 7.4)])
            ctx.fill()
            for i in range(30):
                setc(ctx, "#7a3a26", 0.5)
                ctx.set_line_width(0.06)
                ctx.move_to(-15 + i * 0.6, 7.4)
                ctx.line_to(-6 + (i * 0.6 - 9) * 0.05, 11.4)
                ctx.stroke()
            for wx in (-12, -8.5, -5, -1.5):
                for wy in (1.2, 4.5):
                    setc(ctx, "#3a3028")
                    ctx.rectangle(wx, wy, 1.4, 2.0)
                    ctx.fill()
                    setc(ctx, "#5e7a6a")
                    ctx.rectangle(wx - 0.5, wy, 0.45, 2.0)
                    ctx.rectangle(wx + 1.45, wy, 0.45, 2.0)
                    ctx.fill()
            # hiedra
            foliage_cluster(ctx, rnd, -13, 3, 1.8, 3.2, GREENS[:4], L, n=600, leaf=0.18)
            # invernadero
            setc(ctx, "#cfdde0", 0.55)
            poly(ctx, [(6, 0), (6, 3.2), (11, 5.2), (16, 3.2), (16, 0)])
            ctx.fill()
            setc(ctx, "#f4f2ea", 0.9)
            ctx.set_line_width(0.08)
            for i in range(11):
                ctx.move_to(6 + i, 0)
                ctx.line_to(6 + i, 3.2 + (2.0 * (1 - abs(i - 5) / 5)))
            ctx.move_to(6, 1.6)
            ctx.line_to(16, 1.6)
            ctx.stroke()
            for i in range(6):
                tree_round(ctx, rnd, -24 + i * 8 + (20 if i > 2 else 0), 0, rnd.uniform(6, 9), rnd.uniform(5, 7),
                           GREENS[1:5], light=L, leaf=0.25, n=500)
        self.plane(2, 55.0, (-30, 30, -0.5, 16), 68, manor, flat=0.6)

        # seto con arco
        def hedge(ctx, cv):
            setc(ctx, "#1f3018")
            poly(ctx, [(-18, 0), (-18, 2.5), (18, 2.5), (18, 0)])
            ctx.fill()
            for i in range(9000):
                x, y = rnd.uniform(-18, 18), rnd.uniform(0, 2.55)
                top = 1.0 - (2.55 - y) / 2.55
                u = min(0.999, max(0, 0.35 + 0.5 * top * (1 if not evening else 0.6) + rnd.uniform(-0.25, 0.25)))
                setc(ctx, GREENS[int(u * (len(GREENS) - 1))])
                ellipse(ctx, x, y, 0.06, 0.035, rnd.uniform(0, 3.14))
                ctx.fill()
            # arco de paso (vano al fondo)
            ctx.save()
            ctx.set_operator(0)  # CLEAR
            ctx.move_to(-4.6, 0)
            ctx.line_to(-4.6, 1.5)
            ctx.arc(-3.9, 1.5, 0.7, math.pi, 0)
            ctx.line_to(-3.2, 0)
            ctx.close_path()
            ctx.fill()
            ctx.restore()
            # banco de piedra
            setc(ctx, "#b8ab96")
            ctx.rectangle(3.0, 0.42, 2.2, 0.12)
            ctx.fill()
            setc(ctx, "#8a7f6c")
            ctx.rectangle(3.2, 0, 0.3, 0.42)
            ctx.rectangle(4.7, 0, 0.3, 0.42)
            ctx.fill()
        self.plane(2, 20.0, (-18, 18, 0, 2.6), 113, hedge, flat=1.0, inflate=(30.0, 1.5, 0.6))

        # macizos de flores intermedios
        def beds(ctx, cv):
            r2 = random.Random(21)
            for cx in (-6.5, -3.0, 4.2, 7.5):
                foliage_cluster(ctx, r2, cx, 0.45, 1.4, 0.55, GREENS[1:], L, n=900, leaf=0.05)
                flowers(ctx, r2, cx - 1.2, cx + 1.2, 0.3, 0.95,
                        ["#e8c8d8", "#d88aa8", "#f2efe6", "#c8a8e0"] if cx < 0 else ["#f0d070", "#e89060", "#f4ece0"],
                        n=90, size=0.035)
            # lavanda
            for i in range(500):
                x = r2.uniform(5.0, 9.0)
                h = r2.uniform(0.35, 0.6)
                setc(ctx, "#5a6a48")
                ctx.set_line_width(0.012)
                ctx.move_to(x, 0)
                ctx.line_to(x + r2.uniform(-0.05, 0.05), h)
                ctx.stroke()
                setc(ctx, r2.choice(["#8a78b8", "#9c88c8", "#7a68a8"]))
                ellipse(ctx, x, h, 0.015, 0.05)
                ctx.fill()
        self.plane(2, 12.5, (-9.5, 9.5, 0, 1.4), 215, beds, flat=1.0, inflate=(20.0, 1.8, 0.6))

        # el árbol joven con tutor: copa irregular por ramificación recursiva (con huecos para la luz)
        def tree(ctx, cv):
            x = TREE_X
            r2 = random.Random(5 if not evening else 6)
            bark = material("wood", 256, 512, "#6a5442", seed=2, grain=30, aspect=0.2)
            tones = GREENS[1:] if not evening else ["#26361c", "#3a4e26", "#566c2e", "#8a9a48", "#d2c060"]
            # tutor y ataduras
            setc(ctx, "#8a6e4e")
            ctx.rectangle(x - 0.2, 0, 0.055, 2.2)
            ctx.fill()
            ends = []

            def branch(px, py, ang, length, width, depth):
                ex = px + math.sin(ang) * length
                ey = py + math.cos(ang) * length
                mx = (px + ex) / 2 + r2.uniform(-0.05, 0.05)
                my = (py + ey) / 2
                setc(ctx, "#4e3c2c")
                ctx.set_line_width(width)
                ctx.set_line_cap(1)
                ctx.move_to(px, py)
                ctx.curve_to(mx, my, mx, my, ex, ey)
                ctx.stroke()
                if depth == 0:
                    ends.append((ex, ey))
                    return
                if depth == 1:
                    ends.append((ex, ey))
                for k in range(r2.choice((2, 2, 3))):
                    na = ang + r2.uniform(-0.6, 0.6)
                    na = na * 0.8  # tendencia a crecer hacia arriba (fototropismo)
                    branch(ex, ey, na, length * r2.uniform(0.6, 0.75), width * 0.62, depth - 1)

            # tronco
            fill_material(ctx, bark, 900)
            poly(ctx, [(x - 0.08, 0), (x - 0.045, 2.5), (x + 0.045, 2.5), (x + 0.085, 0)])
            ctx.fill()
            ctx.set_source(lin_grad(x - 0.09, 0, x + 0.09, 0, [(0, (0, 0, 0, 0.45)), (0.55, (0, 0, 0, 0.0)),
                                                                 (1, (1, 0.9, 0.7, 0.18))]))
            poly(ctx, [(x - 0.08, 0), (x - 0.045, 2.5), (x + 0.045, 2.5), (x + 0.085, 0)])
            ctx.fill()
            for yy in (0.8, 1.7):
                setc(ctx, "#c8b08a")
                ctx.rectangle(x - 0.21, yy, 0.3, 0.035)
                ctx.fill()
            # ramas podadas: muñones con el corte claro
            for yy in (1.05, 1.35, 2.0):
                setc(ctx, "#4e3c2c")
                poly(ctx, [(x + 0.05, yy), (x + 0.2, yy + 0.08), (x + 0.21, yy + 0.04), (x + 0.05, yy - 0.04)])
                ctx.fill()
                setc(ctx, "#e0c8a0")
                ellipse(ctx, x + 0.205, yy + 0.06, 0.013, 0.025)
                ctx.fill()
            for ang, yy in ((-0.95, 2.35), (-0.55, 2.6), (-0.25, 2.9), (0.3, 2.75), (0.7, 2.45), (1.0, 2.9)):
                branch(x, yy, ang, 0.5, 0.042, 3)
            branch(x, 2.4, 0.05, 0.9, 0.055, 3)
            # copa: racimos de hojas en los extremos (con huecos entre ellos)
            for (ex, ey) in ends:
                foliage_cluster(ctx, r2, ex, ey, r2.uniform(0.2, 0.32), r2.uniform(0.16, 0.26), tones, L,
                                n=260, leaf=0.045, ao=True)
            # hojas sueltas en el borde
            for (ex, ey) in ends[::2]:
                foliage_cluster(ctx, r2, ex + r2.uniform(-0.2, 0.2), ey + 0.15, 0.2, 0.14, tones[1:], L, n=90,
                                leaf=0.045, ao=False)
            setc(ctx, "#3a2a1e")
            ellipse(ctx, x, 0.0, 0.8, 0.05)
            ctx.fill()
        self.plane(2, TREE_Z, (-1.6, 3.4, -0.1, 5.6), 700, tree, flat=1.0, rim=0.0, inflate=(24.0, 2.0, 0.5))

        # suelo cercano: césped con franjas de cortacésped y camino de grava
        def ground_near(ctx, cv):
            grass = material("grass", 1024, 1024, "#5f8a3e", seed=1, scale=40, tint_noise=60, tint="#7a8a3a")
            fill_material(ctx, grass, 220)
            ctx.paint()
            for i in range(-10, 10):
                setc(ctx, "#ffffff" if i % 2 else "#000000", 0.05)
                poly(ctx, [(i * 1.2, -3.5), (i * 1.2 + 1.2, -3.5), (i * 1.2 + 1.2, 16), (i * 1.2, 16)])
                ctx.fill()
            gravel = material("stone", 512, 512, "#c8b89a", seed=5, scale=6)
            fill_material(ctx, gravel, 300)
            ctx.move_to(-3.6, -3.5)
            ctx.curve_to(-2.0, 3.0, -0.3, 4.5, 0.2, 6.2)
            ctx.line_to(0.0, 16)
            ctx.line_to(-1.2, 16)
            ctx.curve_to(-1.4, 6.5, -2.6, 4.5, -5.6, -3.5)
            ctx.close_path()
            ctx.fill()
            # alcorque circular
            setc(ctx, "#3a2a1e")
            ellipse(ctx, TREE_X, TREE_Z, 0.85, 0.85)
            ctx.fill()
            setc(ctx, "#4a3828")
            for i in range(300):
                a, r = rnd.uniform(0, 6.28), 0.85 * math.sqrt(rnd.random())
                ellipse(ctx, TREE_X + math.cos(a) * r, TREE_Z + math.sin(a) * r, 0.03, 0.02)
                ctx.fill()
        self.plane(1, 0.0, (-10, 10, -3.5, 16.0), 204, ground_near, detail=(0.18, 6.0, 1.0), key=16.5)

        def ground_far(ctx, cv):
            grass = material("grass", 512, 512, "#557e38", seed=2, scale=30)
            fill_material(ctx, grass, 20)
            ctx.paint()
            gravel = material("stone", 256, 256, "#c0b090", seed=6, scale=6)
            fill_material(ctx, gravel, 30)
            ctx.rectangle(-1.2, 16, 1.2, 4)
            ctx.fill()
        self.plane(1, 0.0, (-160, 160, 16.0, 500.0), 18, ground_far, detail=(0.15, 1.5, 1.0), key=600)

        # hierba en primer plano (desenfocada) para dar profundidad
        def fg(ctx, cv):
            r2 = random.Random(31)
            tones = ["#2c4220", "#3a5828", "#4e7032", "#6a8a40"]
            grass_tufts(ctx, r2, -4, -1.0, 0, 0.55, tones, n=1400, w=0.012)
            grass_tufts(ctx, r2, 2.0, 4.5, 0, 0.45, tones, n=1100, w=0.012)
            flowers(ctx, r2, -3.6, -1.6, 0.25, 0.5, ["#f2efe6", "#e8d070"], n=25, size=0.03)
        self.plane(2, 2.3, (-4.5, 4.5, -0.05, 0.62), 450, fg, flat=1.0, rim=1.0)

        # polen / polvo iluminado (dispersión Mie: brilla a contraluz)
        n = 1_600_000
        self.pollen = Particles(eng, n, (-7, 0.0, 1.5), (7, 5.0, 22), seed=7, drift=(0.05, 0.02, 0.0), turb=0.12,
                                size_m=0.0012, color=(1.0, 0.85, 0.55), gain=0.12, bright_pow=5.0)
        self.pollen.phase = 0.75
        self.add_particles(6.5, self.pollen)

    # ------------------------------------------------------------- iluminación del decorado
    def env(self, t):
        s = self.sun
        sun_col = ph.sun_radiance_at_ground(s, self.haze)
        amb, hz = ph.sky_ambient(s, self.haze) if not hasattr(self, "_amb") else self._amb
        self._amb = (amb, hz)
        # radiosidad del suelo (césped, albedo ~0.2, verdoso): irradiancia sobre superficies que miran abajo
        ground_rho = np.array([0.16, 0.22, 0.10])
        bounce = ground_rho * (sun_col * max(s[1], 0.0) + amb)
        sigma = np.array([5.8, 13.5, 33.1]) * 1e-6 * 220 + 21e-6 * 90 * self.haze
        fill = 1.0 if self.mood == "morning" else 2.6   # rebote/reflector a contraluz
        return dict(
            amb_top=amb * fill, amb_bot=bounce * fill,
            sun_col=sun_col, sun_dir=s,
            canopy=(TREE_X, TREE_Z, 1.1, 3.6),
            sigma=sigma, fog=hz * 0.55, fog_sun=sun_col * 0.06 * self.haze,
            rim_col=sun_col * 0.045, rim_dir=(-np.sign(s[0]) * 4.0 if abs(s[0]) > 0.05 else 0.0, 3.0),
        )

    def sky(self, t):
        return dict(sun_dir=self.sun, haze=self.haze, disk=1.0)

    def post(self, t):
        if self.mood == "morning":
            return dict(exposure=0.55, wb=(0.96, 1.0, 1.06), sat=1.06, contrast=1.04, bloom=0.05,
                        bloom_thresh=6.0, lift=(0.012, 0.014, 0.02), shadow_tint=(-0.006, 0.0, 0.012),
                        high_tint=(0.02, 0.012, -0.01), vignette=0.35, grain=0.018,
                        rays=dict(thresh=9.0, decay=0.968, density=0.95, weight=0.55))
        return dict(exposure=0.9, wb=(0.98, 1.0, 1.08), sat=1.1, contrast=1.06, bloom=0.07, bloom_thresh=5.0,
                    lift=(0.02, 0.012, 0.02), shadow_tint=(0.0, -0.004, 0.018), high_tint=(0.03, 0.01, -0.02),
                    vignette=0.45, grain=0.02, rays=dict(thresh=5.0, decay=0.972, density=1.0, weight=0.8))

    def light_screen(self):
        """Dirección de la luz principal en pantalla, para el sombreado de los personajes."""
        s = self.sun
        v = np.array([s[0], s[1] + 0.25])
        return tuple(v / np.linalg.norm(v))
