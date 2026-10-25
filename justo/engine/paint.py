"""Kit de ilustración digital sobre Cairo.

Los lienzos trabajan en metros (coordenadas de mundo, v hacia arriba) para que cada
plano de la escena se pinte a escala real. Las texturas de material se generan con
ruido fractal (numpy) y se usan como patrones de relleno de Cairo.
"""
import math
import random

import cairo
import numpy as np


# ------------------------------------------------------------------ color
def hx(h, a=1.0):
    h = h.lstrip("#")
    return (int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255, a)


def mix(c1, c2, u):
    a = hx(c1) if isinstance(c1, str) else c1
    b = hx(c2) if isinstance(c2, str) else c2
    return tuple(a[i] + (b[i] - a[i]) * u for i in range(4))


def shade(c, f, a=None):
    r, g, b, aa = hx(c) if isinstance(c, str) else c
    return (min(r * f, 1), min(g * f, 1), min(b * f, 1), aa if a is None else a)


def setc(ctx, c, a=None):
    r, g, b, aa = hx(c) if isinstance(c, str) else c
    ctx.set_source_rgba(r, g, b, aa if a is None else a)


def lin_grad(x0, y0, x1, y1, stops):
    g = cairo.LinearGradient(x0, y0, x1, y1)
    for o, c in stops:
        g.add_color_stop_rgba(o, *(hx(c) if isinstance(c, str) else c))
    return g


def rad_grad(x, y, r0, r1, stops, x1=None, y1=None):
    g = cairo.RadialGradient(x, y, r0, x if x1 is None else x1, y if y1 is None else y1, r1)
    for o, c in stops:
        g.add_color_stop_rgba(o, *(hx(c) if isinstance(c, str) else c))
    return g


# ------------------------------------------------------------------ geometría
def ellipse(ctx, x, y, rx, ry, ang=0.0):
    ctx.save()
    ctx.translate(x, y)
    ctx.rotate(ang)
    ctx.scale(max(rx, 1e-6), max(ry, 1e-6))
    ctx.new_sub_path()
    ctx.arc(0, 0, 1, 0, 2 * math.pi)
    ctx.restore()


def rrect(ctx, x, y, w, h, r):
    r = max(0.0, min(r, abs(w) / 2, abs(h) / 2))
    ctx.new_sub_path()
    ctx.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    ctx.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    ctx.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    ctx.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    ctx.close_path()


def poly(ctx, pts, close=True):
    ctx.move_to(*pts[0])
    for p in pts[1:]:
        ctx.line_to(*p)
    if close:
        ctx.close_path()


def smooth_path(ctx, pts, close=True, tension=0.5):
    """Curva Catmull-Rom que pasa por los puntos."""
    n = len(pts)
    if n < 3:
        poly(ctx, pts, close)
        return
    P = pts + pts[:3] if close else [pts[0]] + pts + [pts[-1]]
    ctx.move_to(*P[1] if close else P[1])
    rng = range(1, n + 1) if close else range(1, n)
    for i in rng:
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2] if i + 2 < len(P) else P[-1]
        c1 = (p1[0] + (p2[0] - p0[0]) * tension / 3, p1[1] + (p2[1] - p0[1]) * tension / 3)
        c2 = (p2[0] - (p3[0] - p1[0]) * tension / 3, p2[1] - (p3[1] - p1[1]) * tension / 3)
        ctx.curve_to(c1[0], c1[1], c2[0], c2[1], p2[0], p2[1])
    if close:
        ctx.close_path()


def stroke_line(ctx, pts, width, color, cap=cairo.LINE_CAP_ROUND):
    setc(ctx, color)
    ctx.set_line_width(width)
    ctx.set_line_cap(cap)
    ctx.set_line_join(cairo.LINE_JOIN_ROUND)
    ctx.move_to(*pts[0])
    for p in pts[1:]:
        ctx.line_to(*p)
    ctx.stroke()


def taper(ctx, pts, w0, w1, color):
    """Trazo con grosor variable (como un pincel que se afila)."""
    left, right = [], []
    n = len(pts)
    for i, p in enumerate(pts):
        a = pts[min(i + 1, n - 1)]
        b = pts[max(i - 1, 0)]
        dx, dy = a[0] - b[0], a[1] - b[1]
        L = math.hypot(dx, dy) or 1
        nx, ny = -dy / L, dx / L
        w = (w0 + (w1 - w0) * i / max(n - 1, 1)) / 2
        left.append((p[0] + nx * w, p[1] + ny * w))
        right.append((p[0] - nx * w, p[1] - ny * w))
    setc(ctx, color)
    poly(ctx, left + right[::-1])
    ctx.fill()


# ------------------------------------------------------------------ ruido / materiales
def value_noise(h, w, scale, seed=0, octaves=5, persistence=0.5, aspect=1.0):
    """Ruido fractal 2D (numpy), salida en [0, 1]."""
    rng = np.random.default_rng(seed)
    out = np.zeros((h, w), np.float32)
    amp, tot = 1.0, 0.0
    for o in range(octaves):
        sy = max(2, int(h / scale * (2 ** o)) + 2)
        sx = max(2, int(w / scale * (2 ** o) / aspect) + 2)
        g = rng.random((sy, sx)).astype(np.float32)
        ys = np.linspace(0, sy - 1.001, h)
        xs = np.linspace(0, sx - 1.001, w)
        y0, x0 = ys.astype(int), xs.astype(int)
        fy, fx = ys - y0, xs - x0
        fy = fy * fy * (3 - 2 * fy)
        fx = fx * fx * (3 - 2 * fx)
        a = g[y0][:, x0]
        b = g[y0][:, x0 + 1]
        c = g[y0 + 1][:, x0]
        d = g[y0 + 1][:, x0 + 1]
        top = a + (b - a) * fx[None, :]
        bot = c + (d - c) * fx[None, :]
        out += amp * (top + (bot - top) * fy[:, None])
        tot += amp
        amp *= persistence
    return out / tot


def surface_from_rgba(rgb, alpha=None):
    """rgb float [0,1] (h,w,3) -> ImageSurface ARGB32 (premultiplicado)."""
    h, w = rgb.shape[:2]
    a = np.ones((h, w), np.float32) if alpha is None else alpha.astype(np.float32)
    data = np.empty((h, w, 4), np.uint8)
    data[..., 0] = np.clip(rgb[..., 2] * a * 255, 0, 255)
    data[..., 1] = np.clip(rgb[..., 1] * a * 255, 0, 255)
    data[..., 2] = np.clip(rgb[..., 0] * a * 255, 0, 255)
    data[..., 3] = np.clip(a * 255, 0, 255)
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    stride = surf.get_stride()
    buf = surf.get_data()
    arr = np.ndarray((h, stride // 4, 4), np.uint8, buf)
    arr[:, :w] = data
    surf.mark_dirty()
    return surf


def material(kind, w, h, base, seed=0, **kw):
    """Textura de material como ImageSurface (en píxeles)."""
    b = np.array(hx(base)[:3], np.float32)
    if kind == "wood":
        n = value_noise(h, w, kw.get("grain", 40), seed, 5, 0.55, aspect=kw.get("aspect", 8.0))
        rings = 0.5 + 0.5 * np.sin(n * 40.0)
        f = 0.78 + 0.22 * rings * (0.6 + 0.4 * value_noise(h, w, 200, seed + 1, 3))
    elif kind == "plaster":
        n = value_noise(h, w, kw.get("scale", 120), seed, 6, 0.6)
        f = 0.9 + 0.12 * (n - 0.5) * 2
        fine = value_noise(h, w, 6, seed + 3, 2)
        f = f + 0.04 * (fine - 0.5)
    elif kind == "stone":
        n = value_noise(h, w, kw.get("scale", 60), seed, 6, 0.6)
        f = 0.82 + 0.3 * (n - 0.5)
    elif kind == "grass":
        n = value_noise(h, w, kw.get("scale", 50), seed, 6, 0.62)
        streak = value_noise(h, w, 8, seed + 5, 2, aspect=0.25)
        f = 0.75 + 0.35 * (n - 0.5) + 0.25 * (streak - 0.5)
    elif kind == "fabric":
        n = value_noise(h, w, kw.get("scale", 30), seed, 4, 0.5)
        f = 0.92 + 0.12 * (n - 0.5)
    else:
        f = np.ones((h, w), np.float32)
    rgb = np.clip(b[None, None, :] * f[..., None], 0, 1)
    if "tint_noise" in kw:  # variación de matiz
        t = value_noise(h, w, kw["tint_noise"], seed + 9, 3)
        tc = np.array(hx(kw.get("tint", base))[:3], np.float32)
        rgb = rgb * (1 - 0.5 * t[..., None]) + tc * f[..., None] * 0.5 * t[..., None]
    return surface_from_rgba(rgb)


def fill_material(ctx, surf, px_per_unit, offset=(0, 0)):
    """Usa una textura (en píxeles) como fuente, escalada al espacio de mundo actual."""
    pat = cairo.SurfacePattern(surf)
    pat.set_extend(cairo.EXTEND_REPEAT)
    pat.set_filter(cairo.FILTER_GOOD)
    m = cairo.Matrix()
    m.scale(px_per_unit, -px_per_unit)
    m.translate(-offset[0], -offset[1])
    pat.set_matrix(m)
    ctx.set_source(pat)


# ------------------------------------------------------------------ lienzo
class Canvas:
    """Lienzo en metros: (u0..u1) x (v0..v1), con v hacia arriba."""

    def __init__(self, u0, u1, v0, v1, ppm, max_px=4096):
        self.u0, self.u1, self.v0, self.v1 = u0, u1, v0, v1
        w, h = (u1 - u0) * ppm, (v1 - v0) * ppm
        k = min(1.0, max_px / max(w, h))
        self.ppm = ppm * k
        self.w, self.h = max(4, int(w * k)), max(4, int(h * k))
        self.surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, self.w, self.h)
        self.ctx = cairo.Context(self.surf)
        self.ctx.set_matrix(cairo.Matrix(self.ppm, 0, 0, -self.ppm, -u0 * self.ppm, v1 * self.ppm))
        self.ctx.set_antialias(cairo.ANTIALIAS_BEST)

    @property
    def ext(self):
        return (self.u0, self.u1, self.v0, self.v1)

    def px(self, meters):
        return meters * self.ppm

    def array(self):
        self.surf.flush()
        s = self.surf.get_stride() // 4
        return np.ndarray((self.h, s, 4), np.uint8, self.surf.get_data())[:, :self.w].copy()


def screen_canvas(W, H):
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    ctx = cairo.Context(surf)
    ctx.set_antialias(cairo.ANTIALIAS_BEST)
    return surf, ctx


def surf_array(surf):
    surf.flush()
    h, w = surf.get_height(), surf.get_width()
    s = surf.get_stride() // 4
    return np.ndarray((h, s, 4), np.uint8, surf.get_data())[:, :w]


def scatter(rnd, n, x0, x1, y0, y1):
    return [(rnd.uniform(x0, x1), rnd.uniform(y0, y1)) for _ in range(n)]
