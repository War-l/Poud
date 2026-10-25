"""Base de interiores: caja de paredes con ventanas por las que entra el sol."""
import math
import random

import cairo
import numpy as np

from engine import physics as ph
from engine.paint import (hx, mix, shade, setc, ellipse, smooth_path, poly, lin_grad, rad_grad, material,
                          fill_material, rrect)
from sets.common import SetBase


def cut(ctx, x, y, w, h, arch=False):
    """Recorta un hueco (ventana/puerta) dejando ver lo que hay detrás."""
    ctx.save()
    ctx.set_operator(cairo.OPERATOR_CLEAR)
    if arch:
        ctx.move_to(x, y)
        ctx.line_to(x, y + h - w / 2)
        ctx.arc_negative(x + w / 2, y + h - w / 2, w / 2, math.pi, 0) if False else ctx.arc(x + w / 2, y + h - w / 2,
                                                                                               w / 2, math.pi, 0)
        ctx.line_to(x + w, y)
        ctx.close_path()
    else:
        ctx.rectangle(x, y, w, h)
    ctx.fill()
    ctx.restore()


def window_frame(ctx, x, y, w, h, col="#e8e2d6", mull=2, transom=None, lw=0.06, arch=False):
    setc(ctx, col)
    ctx.set_line_width(lw)
    if arch:
        ctx.move_to(x, y)
        ctx.line_to(x, y + h - w / 2)
        ctx.arc(x + w / 2, y + h - w / 2, w / 2, math.pi, 0)
        ctx.line_to(x + w, y)
        ctx.close_path()
    else:
        ctx.rectangle(x, y, w, h)
    ctx.stroke()
    ctx.set_line_width(lw * 0.6)
    for i in range(1, mull):
        ctx.move_to(x + w * i / mull, y)
        ctx.line_to(x + w * i / mull, y + h)
    for yy in (transom or [y + h * 0.5]):
        ctx.move_to(x, yy)
        ctx.line_to(x + w, yy)
    ctx.stroke()


def wood_panels(ctx, x0, x1, y0, y1, base, seed=0, panel_w=0.9, ppm=200):
    wood = material("wood", 512, 512, base, seed=seed, grain=60, aspect=10)
    fill_material(ctx, wood, ppm)
    ctx.rectangle(x0, y0, x1 - x0, y1 - y0)
    ctx.fill()
    x = x0
    while x < x1:
        setc(ctx, "#000000", 0.22)
        ctx.set_line_width(0.012)
        rrect(ctx, x + 0.06, y0 + 0.08, panel_w - 0.12, (y1 - y0) - 0.16, 0.02)
        ctx.stroke()
        setc(ctx, "#ffffff", 0.06)
        ctx.move_to(x + 0.065, y1 - 0.09)
        ctx.line_to(x + panel_w - 0.065, y1 - 0.09)
        ctx.stroke()
        x += panel_w
    setc(ctx, shade(base, 0.6))
    ctx.rectangle(x0, y1 - 0.06, x1 - x0, 0.06)
    ctx.fill()


def bookshelf(ctx, rnd, x0, x1, y0, y1, shelf_h=0.36, wood="#4a3020"):
    setc(ctx, shade(wood, 0.55))
    ctx.rectangle(x0, y0, x1 - x0, y1 - y0)
    ctx.fill()
    cols = ["#6a2a22", "#2a3a5a", "#3a5a3a", "#8a6a3a", "#5a2a4a", "#a88a5a", "#2a2a2a", "#7a4a2a", "#b8a888",
            "#4a5a6a", "#8a3a2a"]
    y = y0 + 0.04
    while y + shelf_h < y1:
        x = x0 + 0.03
        while x < x1 - 0.05:
            w = rnd.uniform(0.025, 0.06)
            h = shelf_h * rnd.uniform(0.6, 0.92)
            if rnd.random() < 0.06:
                x += rnd.uniform(0.05, 0.15)
                continue
            c = rnd.choice(cols)
            lean = 0.0 if rnd.random() > 0.08 else rnd.uniform(-0.15, 0.15)
            ctx.save()
            ctx.translate(x + w / 2, y)
            ctx.rotate(lean)
            setc(ctx, c)
            ctx.rectangle(-w / 2, 0, w, h)
            ctx.fill()
            setc(ctx, "#e8d8a8", 0.5)
            ctx.rectangle(-w / 2, h * 0.75, w, 0.008)
            ctx.rectangle(-w / 2, h * 0.2, w, 0.006)
            ctx.fill()
            setc(ctx, "#000000", 0.25)
            ctx.rectangle(w / 2 - w * 0.25, 0, w * 0.25, h)
            ctx.fill()
            ctx.restore()
            x += w + 0.002
        y += shelf_h
        setc(ctx, wood)
        ctx.rectangle(x0, y - 0.03, x1 - x0, 0.03)
        ctx.fill()
    setc(ctx, wood)
    ctx.rectangle(x0, y0, 0.05, y1 - y0)
    ctx.rectangle(x1 - 0.05, y0, 0.05, y1 - y0)
    ctx.rectangle(x0, y1 - 0.06, x1 - x0, 0.06)
    ctx.fill()


class Room(SetBase):
    """Habitación: paredes izquierda (x=-wl), derecha (x=wr), fondo (z=depth), suelo y techo."""

    def __init__(self, eng, wl, wr, depth, height, near=-2.0):
        super().__init__(eng)
        self.wl, self.wr, self.depth, self.height, self.near = wl, wr, depth, height, near

    def wall_left(self, painter, ppm=180, **kw):
        return self.plane(0, -self.wl, (self.near, self.depth + 0.01, 0, self.height), ppm, painter,
                          key=self.depth + 2, **kw)

    def wall_right(self, painter, ppm=180, **kw):
        return self.plane(0, self.wr, (self.near, self.depth + 0.01, 0, self.height), ppm, painter,
                          key=self.depth + 2, **kw)

    def wall_back(self, painter, ppm=220, **kw):
        return self.plane(2, self.depth, (-self.wl - 0.01, self.wr + 0.01, 0, self.height), ppm, painter,
                          key=self.depth + 1, **kw)

    def floor(self, painter, ppm=220, **kw):
        return self.plane(1, 0.0, (-self.wl - 0.01, self.wr + 0.01, self.near, self.depth + 0.01), ppm, painter,
                          key=self.depth + 3, **kw)

    def ceiling(self, painter, ppm=60, **kw):
        return self.plane(1, self.height, (-self.wl - 0.01, self.wr + 0.01, self.near, self.depth + 0.01), ppm,
                          painter, key=self.depth + 3, **kw)

    def interior_env(self, sun, sun_scale, windows, lights, amb_col, amb_k, bounce_col, haze_sigma, fog_col,
                     rim_k=0.03):
        sun_col = ph.sun_radiance_at_ground(sun) * sun_scale
        return dict(amb_top=np.array(amb_col) * amb_k, amb_bot=np.array(bounce_col) * amb_k,
                    sun_col=sun_col, sun_dir=sun, windows=windows, lights=lights,
                    sigma=np.array([haze_sigma] * 3), fog=np.array(fog_col), fog_sun=sun_col * 0.0,
                    rim_col=sun_col * rim_k, rim_dir=(-4.0 * np.sign(sun[0]), 2.0), clear=(0, 0, 0))

    def light_screen(self):
        s = self.sun
        v = np.array([s[0], s[1] + 0.2])
        return tuple(v / np.linalg.norm(v))
