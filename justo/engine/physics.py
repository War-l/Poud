"""Física de la luz y del movimiento, en Python puro/numpy.

- Color de cuerpo negro: ley de Planck integrada con las funciones de igualación de
  color CIE 1931 (ajuste analítico de Wyman, Sloan y Shirley, 2013) -> XYZ -> sRGB lineal.
- Atmósfera: dispersión simple Rayleigh + Mie (modelo de Nishita), la misma que evalúa
  el shader del cielo, para obtener el color del sol que llega al suelo y la luz ambiente.
- Movimiento: respuesta analítica de un oscilador amortiguado (muelle) a una serie de
  objetivos. Se puede evaluar en cualquier instante, lo que permite submuestrear el
  obturador para el desenfoque de movimiento sin simular paso a paso.
"""
import math

import numpy as np

# ------------------------------------------------------------------ color
XYZ_TO_SRGB = np.array([[3.2404542, -1.5371385, -0.4985314],
                        [-0.9692660, 1.8760108, 0.0415560],
                        [0.0556434, -0.2040259, 1.0572252]])


def _g(x, mu, s1, s2):
    s = np.where(x < mu, s1, s2)
    return np.exp(-0.5 * ((x - mu) / s) ** 2)


def cie_cmf(lam_nm):
    """Funciones CIE 1931 2° (ajuste multi-lóbulo de Wyman et al. 2013)."""
    x = 1.056 * _g(lam_nm, 599.8, 37.9, 31.0) + 0.362 * _g(lam_nm, 442.0, 16.0, 26.7) \
        - 0.065 * _g(lam_nm, 501.1, 20.4, 26.2)
    y = 0.821 * _g(lam_nm, 568.8, 46.9, 40.5) + 0.286 * _g(lam_nm, 530.9, 16.3, 31.1)
    z = 1.217 * _g(lam_nm, 437.0, 11.8, 36.0) + 0.681 * _g(lam_nm, 459.0, 26.0, 13.8)
    return x, y, z


def blackbody(kelvin):
    """Color lineal sRGB (luminancia Y = 1) de un cuerpo negro a `kelvin`."""
    lam = np.linspace(380, 780, 401)
    l_m = lam * 1e-9
    h, c, k = 6.62607015e-34, 2.99792458e8, 1.380649e-23
    spd = (2 * h * c * c / l_m ** 5) / (np.exp(h * c / (l_m * k * kelvin)) - 1)
    x, y, z = cie_cmf(lam)
    X, Y, Z = (spd * x).sum(), (spd * y).sum(), (spd * z).sum()
    rgb = XYZ_TO_SRGB @ np.array([X / Y, 1.0, Z / Y])
    return np.clip(rgb, 0, None)


def srgb_to_linear(c):
    c = np.asarray(c, dtype=np.float64)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def hex_lin(h):
    h = h.lstrip("#")
    return srgb_to_linear([int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)])


# ------------------------------------------------------------------ atmósfera
R_EARTH, R_ATMO = 6360e3, 6420e3
BETA_R = np.array([5.8e-6, 13.5e-6, 33.1e-6])   # Rayleigh al nivel del mar (1/m), λ = 680, 550, 440 nm
BETA_M = 21e-6                                  # Mie
H_R, H_M = 7994.0, 1200.0
SUN_I = 20.0


def sun_dir(elev_deg, azim_deg):
    """Dirección hacia el sol. Azimut 0 = delante de la cámara (+z), 90 = derecha (+x)."""
    e, a = math.radians(elev_deg), math.radians(azim_deg)
    return np.array([math.cos(e) * math.sin(a), math.sin(e), math.cos(e) * math.cos(a)])


def _ray_sphere(o, d, r):
    b = np.dot(o, d)
    c = np.dot(o, o) - r * r
    disc = b * b - c
    if disc < 0:
        return None
    s = math.sqrt(disc)
    return -b - s, -b + s


def optical_depth(o, d, n=24):
    hit = _ray_sphere(o, d, R_ATMO)
    if hit is None:
        return 0.0, 0.0
    t1 = hit[1]
    ds = t1 / n
    odr = odm = 0.0
    for i in range(n):
        p = o + d * (ds * (i + 0.5))
        h = np.linalg.norm(p) - R_EARTH
        if h < 0:
            return 1e9, 1e9
        odr += math.exp(-h / H_R) * ds
        odm += math.exp(-h / H_M) * ds
    return odr, odm


def sun_radiance_at_ground(sdir, haze=1.0):
    """Irradiancia solar que llega al suelo (transmitancia de la atmósfera)."""
    o = np.array([0.0, R_EARTH + 2.0, 0.0])
    odr, odm = optical_depth(o, sdir)
    tau = BETA_R * odr + BETA_M * 1.1 * odm * haze
    return SUN_I * np.exp(-tau)


def sky_radiance(view, sdir, haze=1.0, n=16, nl=8):
    o = np.array([0.0, R_EARTH + 2.0, 0.0])
    hit = _ray_sphere(o, view, R_ATMO)
    t1 = hit[1]
    g = _ray_sphere(o, view, R_EARTH)
    if g is not None and g[0] > 0:
        t1 = g[0]
    ds = t1 / n
    mu = float(np.dot(view, sdir))
    pr = 3 / (16 * math.pi) * (1 + mu * mu)
    gg = 0.76
    pm = 3 / (8 * math.pi) * ((1 - gg * gg) * (1 + mu * mu)) / ((2 + gg * gg) * (1 + gg * gg - 2 * gg * mu) ** 1.5)
    sr, sm = np.zeros(3), np.zeros(3)
    odr = odm = 0.0
    for i in range(n):
        p = o + view * (ds * (i + 0.5))
        h = np.linalg.norm(p) - R_EARTH
        hr, hm = math.exp(-h / H_R) * ds, math.exp(-h / H_M) * ds
        odr += hr
        odm += hm
        lr, lm = optical_depth(p, sdir, nl)
        tau = BETA_R * (odr + lr) + BETA_M * 1.1 * (odm + lm) * haze
        att = np.exp(-tau)
        sr += att * hr
        sm += att * hm
    return SUN_I * (sr * BETA_R * pr + sm * BETA_M * haze * pm)


def sky_ambient(sdir, haze=1.0):
    """Irradiancia del cielo sobre una superficie horizontal y su promedio en el horizonte."""
    acc, hz = np.zeros(3), np.zeros(3)
    wsum = 0.0
    for el in (5, 20, 40, 65, 85):
        for az in range(0, 360, 45):
            v = sun_dir(el, az)
            w = math.sin(math.radians(el)) * math.cos(math.radians(el))
            acc += sky_radiance(v, sdir, haze, 8, 4) * w
            wsum += w
    for az in range(0, 360, 30):
        hz += sky_radiance(sun_dir(3, az), sdir, haze, 8, 4)
    # irradiancia = pi * radiancia media ponderada por coseno
    return math.pi * acc / wsum, hz / 12


# ------------------------------------------------------------------ movimiento
def spring_step(tau, omega=8.0, zeta=0.7):
    """Respuesta al escalón de un oscilador amortiguado (0 -> 1)."""
    if tau <= 0:
        return 0.0
    if zeta >= 1.0:
        return 1 - math.exp(-omega * tau) * (1 + omega * tau)
    wd = omega * math.sqrt(1 - zeta * zeta)
    return 1 - math.exp(-zeta * omega * tau) * (math.cos(wd * tau) + zeta * omega / wd * math.sin(wd * tau))


class Track:
    """Valor animado por objetivos sucesivos; cada cambio se alcanza con inercia de muelle.

    keys: [(t, valor), ...]; el primer valor es el estado inicial.
    omega controla la rapidez (rad/s); zeta < 1 produce un ligero sobrepaso.
    """

    def __init__(self, keys, omega=6.0, zeta=0.85):
        self.keys = sorted(keys, key=lambda k: k[0])
        self.omega, self.zeta = omega, zeta

    def __call__(self, t):
        v = self.keys[0][1]
        prev = v
        out = v
        for i, (tk, val) in enumerate(self.keys):
            if i == 0:
                continue
            d = val - prev
            out = out + d * spring_step(t - tk, self.omega, self.zeta)
            prev = val
        return out


def smoothstep(a, b, x):
    if b == a:
        return 1.0 if x >= b else 0.0
    u = min(1.0, max(0.0, (x - a) / (b - a)))
    return u * u * (3 - 2 * u)


def fbm1(t, seed=0.0, octaves=4):
    """Ruido 1D suave y determinista (cámara en mano, viento)."""
    v, amp, f = 0.0, 0.5, 1.0
    for o in range(octaves):
        x = t * f + seed * 17.13 + o * 3.7
        i = math.floor(x)
        fr = x - i
        a = math.sin(i * 127.1 + seed * 311.7) * 43758.5453
        b = math.sin((i + 1) * 127.1 + seed * 311.7) * 43758.5453
        a, b = a - math.floor(a), b - math.floor(b)
        u = fr * fr * (3 - 2 * fr)
        v += amp * ((a + (b - a) * u) * 2 - 1)
        amp *= 0.5
        f *= 2.03
    return v


if __name__ == "__main__":
    for k in (1900, 2700, 3200, 4000, 5500, 6500, 10000):
        print(k, np.round(blackbody(k) / blackbody(k).max(), 3))
    for el in (45, 10, 3):
        s = sun_dir(el, 30)
        print("elev", el, "sol", np.round(sun_radiance_at_ground(s), 3), "amb",
              [np.round(x, 3) for x in sky_ambient(s)])
