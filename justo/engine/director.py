"""Cámara, actores y montaje de cada fotograma."""
import math

import cairo
import numpy as np

from .characters import Figure
from .physics import Track, fbm1

SENSOR_W_MM = 36.0  # formato completo


class Lens:
    """Cámara física: posición, focal (mm), diafragma (f/N), distancia de foco.

    Cada parámetro es una pista con inercia (Track) o un número.
    """

    def __init__(self, x, y, z, mm=40.0, fstop=2.8, focus=5.0, shift=(0.0, 0.0), shake=0.0, look=None):
        self.x, self.y, self.z = x, y, z
        self.mm, self.fstop, self.focus = mm, fstop, focus
        self.shift, self.shake = shift, shake

    @staticmethod
    def _v(p, t):
        return p(t) if callable(p) else p

    def eval(self, t, W, H):
        x, y, z = self._v(self.x, t), self._v(self.y, t), self._v(self.z, t)
        sh = self.shake
        if sh:
            x += sh * fbm1(t * 0.35, 1.0) * 0.6
            y += sh * fbm1(t * 0.4, 2.0) * 0.4
        mm = self._v(self.mm, t)
        N = self._v(self.fstop, t)
        S = max(self._v(self.focus, t), 0.2)
        f_px = mm / SENSOR_W_MM * W
        coc_inf_mm = mm * mm / (N * (S * 1000.0 - mm))
        coc_k = coc_inf_mm * W / SENSOR_W_MM
        shift = self._v(self.shift, t)
        return dict(cam=(x, y, z), f=f_px, focus=S, coc_k=coc_k, shift=shift)


class Shot:
    def __init__(self, t0, lens):
        self.t0, self.lens = t0, lens


class Actor:
    """Personaje situado en el mundo: x(t), z(t), orientación, pose(t)."""

    def __init__(self, style, x, z, facing=1, pose=None, y=0.0, group=0, visible=None, scale=1.0):
        self.fig = Figure(style)
        self.fig.H *= scale
        self.x, self.z, self.y = x, z, y
        self.facing = facing
        self.pose = pose or (lambda t: {})
        self.group = group
        self.visible = visible or (lambda t: True)

    def at(self, t):
        v = lambda p: p(t) if callable(p) else p
        return v(self.x), v(self.y), v(self.z), v(self.facing), self.pose(t)


class Prop:
    """Objeto animado pintado en metros sobre un plano vertical a profundidad z(t).

    painter(ctx, t) dibuja en coordenadas de mundo (x, y), con y hacia arriba.
    """

    def __init__(self, z, painter, group=0, visible=None, x=0.0):
        self.z, self.painter, self.group = z, painter, group
        self.visible = visible or (lambda t: True)
        self.x = x
        self.fig = None

    def at(self, t):
        z = self.z(t) if callable(self.z) else self.z
        return self.x, 0.0, z, 1, {}

    def draw_screen(self, ctx, t, cv, W, H):
        cam, f, shift = cv["cam"], cv["f"], cv["shift"]
        z = self.z(t) if callable(self.z) else self.z
        d = z - cam[2]
        if d <= 0.2:
            return
        k = f / d
        ctx.save()
        ctx.translate(W / 2 + shift[0] - cam[0] * k, H / 2 - shift[1] + cam[1] * k)
        ctx.scale(k, -k)
        self.painter(ctx, t)
        ctx.restore()


def project(cam, f, shift, W, H, X, Y, Z):
    d = Z - cam[2]
    sx = W / 2 + shift[0] + (X - cam[0]) * f / d
    sy_gl = H / 2 + shift[1] + (Y - cam[1]) * f / d
    return sx, H - sy_gl, f / d, d


def draw_actors(actors, t, cam, W, H, light_screen, sun=None, shadow_surf=None, subframes=(0.0,),
                shutter=1 / 48):
    """Devuelve {grupo: [bytes por subfotograma]}, profundidad media por grupo.

    Cada subfotograma se dibuja en un instante distinto dentro del obturador:
    al promediarlos en la GPU se obtiene desenfoque de movimiento real.
    """
    groups = {}
    depths = {}
    for a in actors:
        if not a.visible(t):
            continue
        groups.setdefault(a.group, []).append(a)
    out = {}
    for g, acts in groups.items():
        frames = []
        dsum = []
        for k, sf in enumerate(subframes):
            tt = t + sf * shutter
            surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
            ctx = cairo.Context(surf)
            ctx.set_antialias(cairo.ANTIALIAS_BEST)
            cv = cam(tt)
            order = sorted(acts, key=lambda a: -a.at(tt)[2])
            for a in order:
                if isinstance(a, Prop):
                    a.draw_screen(ctx, tt, cv, W, H)
                    if k == 0:
                        dsum.append(a.at(tt)[2])
                    continue
                X, Y, Z, facing, pose = a.at(tt)
                sx, sy, ppm, d = project(cv["cam"], cv["f"], cv["shift"], W, H, X, Y, Z)
                if d <= 0.3:
                    continue
                a.fig.draw(ctx, sx, sy, ppm, facing, pose, light=light_screen)
                if k == 0:
                    dsum.append(d + cv["cam"][2])
            surf.flush()
            frames.append(bytes(surf.get_data()))
        out[g] = frames
        depths[g] = float(np.mean(dsum)) if dsum else 5.0
    return out, depths


def draw_shadows(actors, t, cv, W, H, sun_dir, strength=0.8):
    """Sombras proyectadas sobre el suelo (y=0) en espacio de pantalla.

    La silueta se transforma con la dirección del sol y se linealiza la proyección
    en perspectiva alrededor de los pies (transformación afín local).
    """
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    ctx = cairo.Context(surf)
    cam, f, shift = cv["cam"], cv["f"], cv["shift"]
    sdx, sdy, sdz = sun_dir
    sdy = max(sdy, 0.12)
    gx, gz = -sdx / sdy, -sdz / sdy   # avance de la sombra por metro de altura
    for a in actors:
        if not a.visible(t) or isinstance(a, Prop):
            continue
        X, Y, Z, facing, pose = a.at(t)
        if Y > 0.05:
            continue
        sx, sy, ppm, d = project(cam, f, shift, W, H, X, 0.0, Z)
        if d <= 0.3:
            continue
        dydz = (cam[1] - 0.0) * f / (d * d)   # px de pantalla por metro de profundidad (hacia arriba)
        # sombra de contacto (oclusión ambiental bajo los pies)
        ctx.save()
        ctx.translate(sx, sy)
        g = cairo.RadialGradient(0, 0, 0, 0, 0, 0.45 * ppm)
        g.add_color_stop_rgba(0, 0, 0, 0, 0.55)
        g.add_color_stop_rgba(1, 0, 0, 0, 0)
        ctx.scale(1.0, max(dydz / ppm, 0.08))
        ctx.set_source(g)
        ctx.arc(0, 0, 0.45 * ppm, 0, 2 * math.pi)
        ctx.fill()
        ctx.restore()
        # silueta proyectada
        # x' = facing*ppm*lx + gx*ppm*ly ;  y' = -gz*dydz*ly   (ly = altura local -> avance sobre el suelo)
        m = cairo.Matrix(facing * ppm, 0.0, gx * ppm, -gz * dydz, sx, sy)
        ctx.save()
        ctx.set_matrix(m)
        ctx.scale(1, -1)
        a.fig.draw(ctx, 0, 0, 1.0, 1, pose, light=(0, 1))
        ctx.restore()
    surf.flush()
    arr = np.ndarray((H, surf.get_stride() // 4, 4), np.uint8, surf.get_data())[:, :W, 3]
    arr = (arr.astype(np.float32) * strength).astype(np.uint8)
    return np.ascontiguousarray(arr[::-1])  # origen abajo para OpenGL
