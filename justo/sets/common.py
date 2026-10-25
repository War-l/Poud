"""Utilidades comunes de los decorados."""
import math
import random

import cairo

from engine.gl import Plane, Particles, Rain
from engine.paint import Canvas, hx, mix, shade, setc, ellipse, smooth_path, poly, lin_grad, rad_grad


class SetBase:
    """Un decorado: planos pintados (con su profundidad de ordenación) + partículas + entorno."""

    def __init__(self, eng):
        self.eng = eng
        self.items = []   # (clave de profundidad, item)

    def plane(self, axis, value, ext, ppm, painter, key=None, emit=None, max_px=4096, **kw):
        cv = Canvas(*ext, ppm, max_px=max_px)
        painter(cv.ctx, cv)
        tex = self.eng.texture_from_cairo(cv.array())
        etex = None
        if emit:
            ce = Canvas(*ext, ppm * 0.5, max_px=2048)
            emit(ce.ctx, ce)
            etex = self.eng.texture_from_cairo(ce.array())
        detail = kw.pop("detail", None)
        inflate = kw.pop("inflate", None)
        pl = Plane(axis, value, ext, tex, etex, **kw)
        if detail:
            pl.detail = detail
        if inflate:
            pl.inflate = inflate
        if key is None:
            key = value if axis == 2 else (ext[3] if axis == 1 else ext[1])
        self.items.append((key, ("plane", pl)))
        return pl

    def add_particles(self, key, ps, **ov):
        self.items.append((key, ("particles", ps, ov)))
        return ps

    def add_volume(self, vol, cuts):
        """Luz volumétrica en rodajas: cuts = profundidades z (de lejos a cerca) que separan las rodajas."""
        for z1, z0 in zip(cuts[:-1], cuts[1:]):
            self.items.append((z1 - 1e-3, ("volume", vol, (z0, z1))))

    def add_rain(self, key, rn):
        self.items.append((key, ("rain", rn)))
        return rn

    def release(self):
        """Libera la memoria de GPU del decorado."""
        for _, it in self.items:
            if it[0] == "plane":
                it[1].albedo.tex.release()
                if it[1].emit:
                    it[1].emit.tex.release()
            elif it[0] in ("particles", "rain"):
                it[1].vbo.release()
                it[1].vao.release()

    def compose(self, chars, extra=()):
        """chars: [(profundidad, item)]. Devuelve la lista de dibujo de atrás hacia delante."""
        allit = list(self.items) + list(chars) + list(extra)
        allit.sort(key=lambda k: -k[0])
        return [it for _, it in allit]


# ------------------------------------------------------------------ pintura vegetal
def foliage_cluster(ctx, rnd, cx, cy, rx, ry, tones, light=(0.6, 0.5), n=400, leaf=0.06, ao=True, dense=1.0):
    """Masa de hojas: sombra interior, hojas en varios tonos y bordes iluminados del lado de la luz."""
    lx, ly = light
    if ao:
        setc(ctx, shade(tones[0], 0.55), 0.95)
        ellipse(ctx, cx, cy, rx * 0.92, ry * 0.88)
        ctx.fill()
    for i in range(int(n * dense)):
        a = rnd.uniform(0, 2 * math.pi)
        r = math.sqrt(rnd.random())
        x = cx + math.cos(a) * rx * r
        y = cy + math.sin(a) * ry * r
        # cuánto mira hacia la luz este punto del volumen
        facing = (math.cos(a) * lx + math.sin(a) * ly) * r
        u = max(0.0, min(1.0, 0.5 + 0.6 * facing + rnd.uniform(-0.2, 0.2)))
        idx = min(len(tones) - 1, int(u * len(tones)))
        setc(ctx, tones[idx], rnd.uniform(0.85, 1.0))
        s = leaf * rnd.uniform(0.6, 1.4)
        ellipse(ctx, x, y, s, s * 0.55, rnd.uniform(0, math.pi))
        ctx.fill()


def tree_round(ctx, rnd, x, base, h, w, tones, trunk="#4a3a2c", light=(0.6, 0.5), leaf=0.12, n=900):
    setc(ctx, trunk)
    poly(ctx, [(x - w * 0.05, base), (x - w * 0.025, base + h * 0.45), (x + w * 0.025, base + h * 0.45),
               (x + w * 0.05, base)])
    ctx.fill()
    for k in range(5):
        cx = x + rnd.uniform(-0.25, 0.25) * w
        cy = base + h * rnd.uniform(0.5, 0.75)
        foliage_cluster(ctx, rnd, cx, cy, w * rnd.uniform(0.32, 0.45), h * rnd.uniform(0.22, 0.32), tones, light,
                        n=n // 5, leaf=leaf)


def cypress(ctx, rnd, x, base, h, w, tones, light=(0.6, 0.5)):
    for i in range(int(h * 30)):
        u = rnd.random()
        y = base + h * u
        half = w * 0.5 * math.sin(math.pi * min(1.0, u * 1.05 + 0.02)) ** 0.8 * (1 - u * 0.35)
        xx = x + rnd.uniform(-half, half)
        side = (xx - x) / max(half, 1e-3)
        t = max(0, min(len(tones) - 1, int((0.5 + 0.5 * side * light[0] + rnd.uniform(-0.2, 0.2)) * len(tones))))
        setc(ctx, tones[t])
        ellipse(ctx, xx, y, w * 0.12, w * 0.18, rnd.uniform(-0.5, 0.5))
        ctx.fill()


def grass_tufts(ctx, rnd, x0, x1, y0, h, tones, n=2000, lean=0.15, w=0.012):
    for i in range(n):
        x = rnd.uniform(x0, x1)
        hh = h * rnd.uniform(0.4, 1.0)
        l = rnd.uniform(-lean, lean) * hh
        setc(ctx, rnd.choice(tones))
        ctx.move_to(x - w, y0)
        ctx.curve_to(x - w * 0.5, y0 + hh * 0.5, x + l * 0.5, y0 + hh * 0.9, x + l, y0 + hh)
        ctx.curve_to(x + l * 0.4, y0 + hh * 0.85, x + w * 0.5, y0 + hh * 0.5, x + w, y0)
        ctx.close_path()
        ctx.fill()


def flowers(ctx, rnd, x0, x1, y0, y1, colors, n=200, size=0.03):
    for i in range(n):
        x, y = rnd.uniform(x0, x1), rnd.uniform(y0, y1)
        c = rnd.choice(colors)
        for k in range(5):
            a = k / 5 * 2 * math.pi
            setc(ctx, c)
            ellipse(ctx, x + math.cos(a) * size * 0.6, y + math.sin(a) * size * 0.6, size * 0.55, size * 0.4, a)
            ctx.fill()
        setc(ctx, "#f0d060")
        ellipse(ctx, x, y, size * 0.3, size * 0.3)
        ctx.fill()


def fill_rect_grad(ctx, x0, y0, x1, y1, stops, vertical=True):
    ctx.set_source(lin_grad(x0, y0, x0 if vertical else x1, y1 if vertical else y0, stops))
    ctx.rectangle(x0, y0, x1 - x0, y1 - y0)
    ctx.fill()
