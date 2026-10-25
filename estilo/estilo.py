"""Estudio de estilo «El hombre que quería ser justo» — render en tiempo real.

Contraluz de atardecer: un hombre junto a un árbol joven atado a su tutor, en lo alto de una
colina; cordilleras que se funden en la bruma, nubes iluminadas desde abajo, viento que ondula
la hierba, hojas, semillas y pájaros.

Presupuesto: el tiempo total de render (pintado + fotogramas + codificación + sonido) no supera
la duración del vídeo. Para lograrlo:
  * todo lo caro se pinta UNA vez al inicio (numpy/Cairo/un pase de GPU para el cielo);
  * cada fotograma es UN shader que compone capas de delante hacia atrás con salida temprana,
    más pases diminutos a baja resolución (rayos de sol, bloom) y partículas;
  * la codificación x264 corre en paralelo en otro proceso.

Uso:  python3 estilo.py [--res 1920x1080] [--stills 4 12 25] [--out estilo.mp4]
"""
import argparse
import math
import os
import subprocess
import sys
import time

import cairo
import moderngl
import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage

T0 = time.time()
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "..", "justo"))
from engine import physics as ph  # noqa: E402  (atmósfera y cuerpo negro ya verificados)

FPS = 24
DUR = 32.0
LOOK = dict(exposure=0.34, rays_thresh=6.0, rays_k=0.35, grad=0.8)
ASPECT = 2.39


# ====================================================================== utilidades numéricas
def fbm2(h, w, scale, octaves=5, seed=0, persistence=0.5, aspect=1.0):
    """Ruido fractal 2D en [0,1]: rejillas aleatorias ampliadas con interpolación cúbica."""
    rng = np.random.default_rng(seed)
    out = np.zeros((h, w), np.float32)
    amp, tot = 1.0, 0.0
    for o in range(octaves):
        gh = max(4, int(h / scale * 2 ** o) + 4)
        gw = max(4, int(w / (scale * aspect) * 2 ** o) + 4)
        g = rng.random((gh, gw)).astype(np.float32)
        z = ndimage.zoom(g, (h / (gh - 3), w / (gw - 3)), order=3 if o < 2 else 1, mode="wrap")[:h, :w]
        out += amp * z
        tot += amp
        amp *= persistence
    out /= tot
    lo, hi = np.percentile(out, 1), np.percentile(out, 99)
    return np.clip((out - lo) / (hi - lo + 1e-6), 0, 1)


def fbm1(n, scale, octaves=6, seed=0, ridged=False):
    rng = np.random.default_rng(seed)
    x = np.arange(n, dtype=np.float32)
    out = np.zeros(n, np.float32)
    amp, tot = 1.0, 0.0
    for o in range(octaves):
        step = scale / 2 ** o
        k = int(n / step) + 3
        pts = rng.random(k).astype(np.float32)
        v = np.interp(x / step, np.arange(k), pts)
        # suavizado tipo smoothstep entre puntos de control
        if ridged:
            v = 1 - np.abs(v * 2 - 1)
        out += amp * v
        tot += amp
        amp *= 0.5
    return out / tot


def smoothstep(a, b, x):
    u = np.clip((x - a) / (b - a), 0, 1)
    return u * u * (3 - 2 * u)


def srgb_to_lin(c):
    c = np.asarray(c, np.float32)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def hexl(h):
    h = h.lstrip("#")
    return srgb_to_lin([int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)])


_LUT = srgb_to_lin(np.arange(256) / 255.0).astype(np.float32)


def cairo_to_premult(surf):
    """Superficie Cairo (sRGB premultiplicado, origen arriba) -> float32 lineal premultiplicado, origen abajo.
    Se despremultiplica en enteros y se decodifica con una tabla (rápido y exacto a 8 bits)."""
    surf.flush()
    h, w = surf.get_height(), surf.get_width()
    a8 = np.ndarray((h, surf.get_stride() // 4, 4), np.uint8, surf.get_data())[::-1, :w]
    al = a8[..., 3].astype(np.uint16)
    out = np.empty((h, w, 4), np.float32)
    alpha = al.astype(np.float32) / 255
    safe = np.maximum(al, 1)
    for i, ch in enumerate((2, 1, 0)):
        st = np.minimum((a8[..., ch].astype(np.uint16) * 255 + safe // 2) // safe, 255)
        out[..., i] = _LUT[st] * alpha
    out[..., 3] = alpha
    return out


def rim_light(alpha, sun_xy, origin, color, strength, falloff, width=1.6):
    """Luz de contorno: borde de la silueta orientado hacia el sol (normal desde el gradiente de la
    cobertura), más intensa cerca del sol (dispersión hacia delante). Solo se calcula en las filas con bordes."""
    h, w = alpha.shape
    rows = np.where((alpha > 0.02).any(1) & (alpha < 0.98).any(1))[0]
    out = np.zeros((h, w, 3), np.float32)
    if len(rows) == 0:
        return out
    r0, r1 = max(rows[0] - 4, 0), min(rows[-1] + 5, h)
    a = ndimage.gaussian_filter(alpha[r0:r1], width)
    gy, gx = np.gradient(a)
    mag = np.sqrt(gx * gx + gy * gy) + 1e-6
    px = (np.arange(w, dtype=np.float32) + origin[0])[None, :]
    py = (np.arange(r0, r1, dtype=np.float32) + origin[1])[:, None]
    dx, dy = sun_xy[0] - px, sun_xy[1] - py
    dist = np.sqrt(dx * dx + dy * dy) + 1e-3
    facing = np.clip((-gx * dx - gy * dy) / (mag * dist), 0, 1)
    k = (np.clip(mag * 3.0, 0, 1) * facing * np.sqrt(facing) * strength / (1 + (dist / falloff) ** 2)) * alpha[r0:r1]
    out[r0:r1] = k[..., None] * np.asarray(color, np.float32)[None, None, :]
    return out


def downblur(img, f, sigma):
    """Reduce por f (media por bloques) y desenfoca: la GPU lo amplía con filtrado bilineal."""
    h, w = img.shape[:2]
    h2, w2 = h // f * f, w // f * f
    small = img[:h2, :w2].reshape(h2 // f, f, w2 // f, f, -1).mean((1, 3))
    return np.stack([ndimage.gaussian_filter(small[..., c], sigma / f, mode="nearest") for c in range(small.shape[2])],
                    -1).astype(np.float32)


# ====================================================================== composición del plano
class Shot:
    def __init__(self, W, H):
        self.W, self.H = W, H
        self.k = W / 1920.0                      # todo se diseña en píxeles de 1920 y se escala
        self.F = 2667.0 * self.k                 # 50 mm en formato completo
        self.YH = -150.0 * self.k                # horizonte (px desde el centro, y hacia arriba)
        self.SUN = np.array([318.0, 92.0]) * self.k
        self.bar = int(round((H - W / ASPECT) / 2))
        # sol físico: elevación y acimut desde su posición en pantalla
        sx, sy = self.SUN
        d = np.array([sx, sy - self.YH, self.F])
        self.sun_dir = d / np.linalg.norm(d)
        self.haze = 0.85
        self.sun_col = ph.sun_radiance_at_ground(self.sun_dir, self.haze)
        # cielo del cenit (ilumina las caras en sombra de nubes y siluetas)
        zd = np.array([self.sun_dir[0] * 0.3, 0.85, self.sun_dir[2] * 0.4])
        self.zenith = ph.sky_radiance(zd / np.linalg.norm(zd), self.sun_dir, self.haze, 12, 6)


# ====================================================================== shaders
VS = """#version 330
in vec2 in_pos; void main(){ gl_Position = vec4(in_pos, 0.0, 1.0); }
"""

SKY_FS = """#version 330
out vec4 frag;
uniform vec2 uSize; uniform vec2 uRes; uniform float uF; uniform float uYH; uniform vec3 uSunDir; uniform float uHaze;
const float RE = 6360e3, RA = 6420e3, HR = 7994.0, HM = 1200.0;
const vec3 BR = vec3(5.8e-6, 13.5e-6, 33.1e-6);
const float BM = 21e-6;
vec2 rs(vec3 o, vec3 d, float r){ float b = dot(o,d); float c = dot(o,o)-r*r; float h = b*b-c; if(h<0.0) return vec2(-1.0); h = sqrt(h); return vec2(-b-h, -b+h); }
void main(){
  vec2 p = (gl_FragCoord.xy/uSize - 0.5)*uRes;            // px de pantalla desde el centro
  vec3 v = normalize(vec3(p.x, p.y - uYH, uF));
  vec3 o = vec3(0.0, RE + 300.0, 0.0);                    // observador en lo alto de la colina
  vec3 vv = v; vv.y = max(vv.y, 0.002); vv = normalize(vv);
  float t1 = rs(o, vv, RA).y;
  const int N = 24, NL = 10;
  float ds = t1/float(N);
  float mu = dot(vv, uSunDir);
  float pr = 3.0/(16.0*3.14159265)*(1.0+mu*mu);
  float g = 0.76;
  float pm = 3.0/(8.0*3.14159265)*((1.0-g*g)*(1.0+mu*mu))/((2.0+g*g)*pow(1.0+g*g-2.0*g*mu, 1.5));
  vec3 sr = vec3(0), sm = vec3(0); float odr = 0.0, odm = 0.0;
  for(int i=0;i<N;i++){
    vec3 q = o + vv*(ds*(float(i)+0.5));
    float h = length(q) - RE;
    float hr = exp(-h/HR)*ds, hm = exp(-h/HM)*ds;
    odr += hr; odm += hm;
    float tl = rs(q, uSunDir, RA).y; float dl = tl/float(NL); float lr=0.0, lm=0.0; bool ok = true;
    for(int j=0;j<NL;j++){ vec3 s = q + uSunDir*(dl*(float(j)+0.5)); float hh = length(s)-RE; if(hh<0.0){ok=false;break;} lr += exp(-hh/HR)*dl; lm += exp(-hh/HM)*dl; }
    if(ok){ vec3 tau = BR*(odr+lr) + BM*1.1*(odm+lm)*uHaze; vec3 att = exp(-tau); sr += att*hr; sm += att*hm; }
  }
  frag = vec4(20.0*(sr*BR*pr + sm*BM*uHaze*pm), 1.0);
}
"""

COMMON = """
uniform vec2 uRes; uniform float uF; uniform vec3 uCam; uniform float uTime; uniform float uK;
uniform vec2 uSun; uniform float uYH;
// rectángulos de las capas en px de pantalla en reposo: (x0, y0, ancho, alto)
uniform vec4 rGrass, rSubj, rCloud;
uniform float dGrass, dSubj;
uniform sampler2D tGrass, tGrassB, tSubj, tSubjB, tSubjW, tCloud;
uniform sampler2D tCols;     // por columna de pantalla: viento hierba, viento colina, techo hierba, techo colina
uniform float uFocus;        // 0 = foco en la hierba, 1 = foco en el hombre y el árbol
uniform float uCloudDrift;

vec2 toLayer(vec2 p, float d){ float s = d/(d - uCam.z); return p/s + uCam.xy*uF/d; }
vec2 uvOf(vec2 q, vec4 r){ return (q - r.xy)/r.zw; }

// viento: ráfagas que viajan por el mundo (metros) y oscilación de la vegetación.
float gust(float xw, float t){ float g = 0.5 + 0.5*sin(0.31*xw + 1.05*t); g *= 0.62 + 0.38*sin(0.13*xw + 0.41*t + 1.7); return g*g; }
float sway(float xw, float t){
  float g = gust(xw, t);
  return 0.9*g + (0.3 + 0.7*g)*(0.55*sin(2.3*t + 1.7*xw) + 0.3*sin(4.1*t + 3.1*xw) + 0.15*sin(7.3*t + 5.3*xw));
}
uniform vec4 uScale;   // escala HDR de las capas codificadas en 8 bits: hierba, colina, lejanas, cielo
vec4 S(sampler2D t, vec2 uv){ return texture(t, uv); }   // capas con borde transparente + clamp
vec4 Dec(vec4 e, float k){ return vec4(e.rgb*e.rgb*k, e.a); }

vec4 colsAt(vec2 p){ return texelFetch(tCols, ivec2(clamp(int(p.x/uK*0.5 + 0.5*uRes.x/uK*0.5), 0, 959), 0), 0); }
vec4 grassAt(vec2 p, vec4 cw, bool blurOnly){
  if(p.y > cw.z) return vec4(0.0);
  vec2 q = toLayer(p, dGrass);
  float h = clamp((q.y - rGrass.y)/(rGrass.w*0.85), 0.0, 1.0);
  q.x += uK*cw.x*h*h;
  vec2 uv = uvOf(q, rGrass);
  if(blurOnly || uFocus >= 0.999) return Dec(S(tGrassB, uv), uScale.x);
  if(uFocus <= 0.001) return Dec(S(tGrass, uv), uScale.x);
  return Dec(mix(S(tGrass, uv), S(tGrassB, uv), uFocus), uScale.x);
}
vec4 subjAt(vec2 p, vec4 cw){
  if(p.y > cw.w) return vec4(0.0);
  vec2 q = toLayer(p, dSubj);
  float w = S(tSubjW, uvOf(q, rSubj)).r;
  q.x += uK*w*cw.y;
  vec2 uv = uvOf(q, rSubj);
  if(uFocus >= 0.999) return Dec(S(tSubj, uv), uScale.y);
  if(uFocus <= 0.001) return Dec(S(tSubjB, uv), uScale.y);
  return Dec(mix(S(tSubjB, uv), S(tSubj, uv), uFocus), uScale.y);
}
uniform sampler2D tBg;     // fondo precompuesto: cielo + sol + cordilleras (alfa = cobertura de las montañas)
vec4 cloudAt(vec2 p){ if(p.y < rCloud.y) return vec4(0.0); return Dec(S(tCloud, uvOf(p + vec2(uCloudDrift, 0.0), rCloud)), uScale.z); }
vec4 bgAt(vec2 p){ vec4 e = texture(tBg, (p + 0.5*uRes)/uRes); return vec4(e.rgb*e.rgb*uScale.w, e.a); }
"""

BG_FS = """#version 330
out vec4 frag;
uniform vec2 uRes; uniform float uF; uniform vec2 uSun; uniform vec3 uSunCol; uniform float uK;
uniform sampler2D tSkyF, tDist; uniform vec4 rSky, rDist; uniform float uFarScale, uSkyScale;
void main(){
  vec2 p = gl_FragCoord.xy - 0.5*uRes;
  vec3 sky = texture(tSkyF, (p - rSky.xy)/rSky.zw).rgb;
  float r = length(p - uSun)/uF;
  float limb = sqrt(max(0.0, 1.0 - (r/0.0056)*(r/0.0056)));
  sky += uSunCol*90.0*(0.55 + 0.45*limb)*smoothstep(0.0058, 0.0052, r);
  vec4 m = texture(tDist, (p - rDist.xy)/rDist.zw);
  m.rgb = m.rgb*m.rgb*uFarScale;
  vec3 c = m.rgb + (1.0 - m.a)*sky;
  frag = vec4(sqrt(clamp(c/uSkyScale, 0.0, 1.0)), m.a);
}
"""

# pase de luz: radiancia del cielo y el sol que no está tapada (para rayos y bloom), 1/4 de resolución
LIGHT_FS = """#version 330
out vec4 frag;
uniform vec2 uSize; uniform vec3 uSunCol;
""" + COMMON + """
void main(){
  vec2 p = (gl_FragCoord.xy/uSize - 0.5)*uRes;
  float T = 1.0;
  vec4 cw = colsAt(p);
  T *= 1.0 - grassAt(p, cw, true).a;
  T *= 1.0 - subjAt(p, cw).a;
  vec4 bg = bgAt(p);
  T *= 1.0 - bg.a;
  vec4 c = cloudAt(p);
  vec3 L = bg.rgb*(1.0 - c.a) + c.rgb;
  float r = length(p - uSun)/uF;
  L += uSunCol*90.0*smoothstep(0.0062, 0.0050, r);
  frag = vec4(L*T, 1.0);
}
"""

# rayos crepusculares: dispersión en espacio de pantalla (integral radial hacia el sol), 1/8 de resolución
RAYS_FS = """#version 330
out vec4 frag;
uniform sampler2D tLight; uniform vec2 uSize; uniform vec2 uSunUV; uniform float uTime; uniform float uThresh;
uniform float uRaysK; uniform float uGlowScale;
float hash(vec2 p){ return fract(sin(dot(p, vec2(12.9898, 78.233)))*43758.5453); }
void main(){
  vec2 uv = gl_FragCoord.xy/uSize;
  vec2 delta = (uv - uSunUV)/24.0*0.92;
  vec2 q = uv - delta*0.5;
  vec3 acc = vec3(0); float w = 1.0;
  for(int i=0;i<24;i++){
    vec3 c = textureLod(tLight, q, 0.0).rgb;
    float lum = dot(c, vec3(0.2126, 0.7152, 0.0722));
    acc += c*max(lum - uThresh, 0.0)/max(lum, 1e-3)*w;
    w *= 0.928; q -= delta;
  }
  vec3 glow = acc/24.0*uRaysK + textureLod(tLight, uv, 0.5).rgb*0.004 + textureLod(tLight, uv, 2.0).rgb*0.014;
  frag = vec4(sqrt(clamp(glow/uGlowScale, 0.0, 1.0)), 1.0);
}
"""

FINAL_FS = """#version 330
out vec4 frag;
uniform sampler2D tLight, tRays;
uniform vec3 uSunCol; uniform vec2 uSunUV; uniform float uExposure; uniform float uFade; uniform float uBar;
uniform float uFlare; uniform float uGlowScale; uniform float uGrad; uniform sampler3D tGrade;
uniform sampler2D tGrain; uniform vec2 uGrainOff;
""" + COMMON + """
float hash(vec2 p){ vec3 p3 = fract(vec3(p.xyx)*0.1031); p3 += dot(p3, p3.yzx + 33.33); return fract((p3.x + p3.y)*p3.z); }
const mat3 ACESIn = mat3(0.59719, 0.07600, 0.02840, 0.35458, 0.90834, 0.13383, 0.04823, 0.01566, 0.83777);
const mat3 ACESOut = mat3(1.60475, -0.10208, -0.00327, -0.53108, 1.10813, -0.07276, -0.07367, -0.00605, 1.07602);
vec3 RRTODT(vec3 v){ vec3 a = v*(v + 0.0245786) - 0.000090537; vec3 b = v*(0.983729*v + 0.4329510) + 0.238081; return a/b; }
void main(){
  vec2 fc = gl_FragCoord.xy;
  if(fc.y < uBar || fc.y > uRes.y - uBar){ frag = vec4(0.0, 0.0, 0.0, 1.0); return; }
  vec2 p = fc - 0.5*uRes;
  // composición de delante hacia atrás (premultiplicada), con salida temprana
  vec3 C = vec3(0); float T = 1.0;
  vec4 cw = colsAt(p);
  vec4 l = grassAt(p, cw, false); C += l.rgb; T *= 1.0 - l.a;
  if(T > 0.003){ l = subjAt(p, cw); C += T*l.rgb; T *= 1.0 - l.a; }
  if(T > 0.003){ l = cloudAt(p); C += T*l.rgb; T *= 1.0 - l.a; }
  if(T > 0.003){ C += T*bgAt(p).rgb; }
  vec2 uv = fc/uRes;
  // luz que se suma: rayos crepusculares, halo (bloom) y reflejos internos de la lente
  vec3 ge = texture(tRays, uv).rgb;
  C += ge*ge*uGlowScale;
  float asp = uRes.x/uRes.y;
  vec3 fl = vec3(0);
  vec2 ds = (uv - uSunUV)*vec2(asp, 1.0);
  if(abs(ds.y) < 0.03){
    float vis = clamp(textureLod(tLight, uSunUV, 2.0).r*0.004, 0.0, 1.0);
    fl += vec3(1.0, 0.7, 0.42)*0.006*vis*exp(-abs(ds.y)*160.0)*exp(-abs(ds.x)*4.0);
  }
  C += fl*uFlare;
  // filtro degradado (como en fotografía de paisaje): enfría y oscurece la parte alta del cielo
  float gtop = smoothstep(0.45, 1.0, (fc.y - uBar)/(uRes.y - 2.0*uBar));
  C *= mix(vec3(1.0), vec3(0.55, 0.72, 1.22), gtop*uGrad);
  // exposición -> conformador sqrt -> LUT 3D (balance de blancos, ACES, saturación, virado, gamma sRGB)
  vec3 lc = sqrt(clamp(C*uExposure/16.0, 0.0, 1.0));
  C = texture(tGrade, lc*(32.0/33.0) + 0.5/33.0).rgb;
  float lu = dot(C, vec3(0.2126, 0.7152, 0.0722));
  // viñeteado
  vec2 v = (uv - 0.5)*vec2(1.0, 0.75);
  C *= 1.0 - 0.32*smoothstep(0.18, 0.62, dot(v, v)*2.2);
  // grano de película y tramado
  // grano de película: textura con tamaño de grano real (~1,3 px a 1080p), desplazada al azar en cada
  // fotograma, más visible en los medios tonos (como en el negativo copiado a positivo)
  float n = texture(tGrain, fc/256.0 + uGrainOff).r - 0.5;
  C += n*0.036*(0.25 + 3.0*lu*(1.0 - lu));
  frag = vec4(C*uFade, 1.0);
}
"""

PART_VS = """#version 330
in vec4 in_p;   // x, y (px desde el centro), tamaño (px), brillo
in vec4 in_c;   // color, y w = 1 si depende de que el sol se vea (reflejos de la lente)
uniform vec2 uRes; uniform sampler2D tLight; uniform vec2 uSunUV;
out float vB; out float vS; out vec3 vC;
void main(){
  gl_Position = vec4(in_p.xy/(0.5*uRes), 0.0, 1.0); gl_PointSize = in_p.z; vS = in_p.z; vC = in_c.rgb;
  float vis = in_c.w > 0.5 ? clamp(textureLod(tLight, uSunUV, 3.0).r*0.004, 0.0, 1.0) : 1.0;
  vB = in_p.w*vis;
}
"""
PART_FS = """#version 330
in float vB; in float vS; in vec3 vC; out vec4 frag; uniform float uFade;
void main(){
  vec2 q = gl_PointCoord*2.0 - 1.0; float r = length(q);
  float a = vS > 6.0 ? smoothstep(1.0, 0.8, r)*(0.8 + 0.3*smoothstep(0.4, 0.95, r)) : exp(-r*r*3.5);
  frag = vec4(vC*vB*a*uFade, 0.0);
}
"""

SHAPE_VS = """#version 330
in vec2 in_pos; in vec2 in_uv; in vec4 in_col; uniform vec2 uRes;
out vec2 vUV; out vec4 vCol;
void main(){ gl_Position = vec4(in_pos/(0.5*uRes), 0.0, 1.0); vUV = in_uv; vCol = in_col; }
"""
SHAPE_FS = """#version 330
in vec2 vUV; in vec4 vCol; out vec4 frag; uniform float uFade;
void main(){
  // hoja: almendra con punta; vUV.y = 9 marca un ala de pájaro (triángulo lleno)
  float a = 1.0;
  if(vUV.y < 5.0){
    vec2 q = vUV*2.0 - 1.0;
    float w = 1.0 - q.x*q.x;
    float d = abs(q.y) - 0.62*w*(1.0 - 0.25*q.x);
    a = smoothstep(vCol.a, -vCol.a, d);
  }
  frag = vec4(vCol.rgb*uFade, a*uFade);
}
"""

# RGB (sRGB) -> YUV 4:2:0 planar (I420), BT.709 rango limitado, ya en orden de memoria (fila superior primero)
YUV_FS = """#version 330
out float frag;
uniform sampler2D tRGB; uniform vec2 uRes;
const vec3 KY = vec3(0.2126, 0.7152, 0.0722);
vec3 px(int x, int y){ return texelFetch(tRGB, ivec2(x, int(uRes.y) - 1 - y), 0).rgb; }
void main(){
  int W = int(uRes.x), H = int(uRes.y);
  int x = int(gl_FragCoord.x), r = int(gl_FragCoord.y);
  if(r < H){ frag = (16.0 + 219.0*dot(px(x, r), KY))/255.0; return; }
  int m = r - H; int q = H/4;
  bool isV = m >= q; if(isV) m -= q;
  int row = 2*m + (x >= W/2 ? 1 : 0);
  int cx = x - (x >= W/2 ? W/2 : 0);
  vec3 c = 0.25*(px(2*cx, 2*row) + px(2*cx+1, 2*row) + px(2*cx, 2*row+1) + px(2*cx+1, 2*row+1));
  float Y = dot(c, KY);
  float ch = isV ? (c.r - Y)/1.5748 : (c.b - Y)/1.8556;
  frag = (128.0 + 224.0*ch)/255.0;
}
"""

TEXT_VS = """#version 330
in vec2 in_pos; in vec2 in_uv; uniform vec2 uRes; out vec2 vUV;
void main(){ gl_Position = vec4(in_pos/(0.5*uRes), 0.0, 1.0); vUV = in_uv; }
"""
TEXT_FS = """#version 330
in vec2 vUV; out vec4 frag; uniform sampler2D tText; uniform float uA;
void main(){ vec4 c = texture(tText, vUV); frag = vec4(c.bgr, c.a)*uA; }
"""


# ====================================================================== pintado de capas
def paint_layers(sh, sky_lut, lut_rect, zenith, parts=("cloud", "dist", "mist", "subj", "grass")):
    """Devuelve dict de capas: nombre -> (array lineal premultiplicado HxWx4 origen abajo, rect)."""
    k, W, H, F, YH = sh.k, sh.W, sh.H, sh.F, sh.YH
    SUN = sh.SUN
    sun_col = sh.sun_col
    out = {}

    def sky_at(xs, ys):
        """Radiancia del cielo (LUT) en coordenadas de pantalla."""
        lh, lw = sky_lut.shape[:2]
        u = np.clip((xs - lut_rect[0]) / lut_rect[2] * (lw - 1), 0, lw - 1)
        v = np.clip((ys - lut_rect[1]) / lut_rect[3] * (lh - 1), 0, lh - 1)
        return ndimage.map_coordinates(sky_lut[..., 0], [v, u], order=1), \
            ndimage.map_coordinates(sky_lut[..., 1], [v, u], order=1), \
            ndimage.map_coordinates(sky_lut[..., 2], [v, u], order=1)

    if "cloud" in parts:
        # ------------------------------------------------------------------ nubes (media resolución)
        cx0, cy0, cw, chh = -1300 * k, -120 * k, 2600 * k, 760 * k
        nh, nw = int(380 * k), int(1300 * k)
        s = cw / nw
        ys, xs = np.mgrid[0:nh, 0:nw].astype(np.float32)
        Y = cy0 + ys * s
        X = cx0 + xs * s
        warp = (fbm2(nh, nw, 140, 4, seed=3) - 0.5) * 70
        base = fbm2(nh, nw, 110, 6, seed=4, persistence=0.55)
        base = ndimage.map_coordinates(base, [np.clip(ys + warp * 0.5, 0, nh - 1), np.clip(xs + warp, 0, nw - 1)],
                                       order=1)
        base2 = fbm2(nh, nw, 70, 6, seed=8, persistence=0.55)
        streak = fbm2(nh, nw, 60, 5, seed=5, aspect=7.0)
        hy = (Y - YH) / k
        dsun = np.sqrt((X - SUN[0]) ** 2 + (Y - SUN[1]) ** 2) / k
        clear = smoothstep(150, 420, dsun)
        # cúmulos con base plana (nivel de condensación) que ondula suavemente, cimas abultadas
        bl = 122 + 30 * (fbm1(nw, 260, 4, seed=31) - 0.5)
        cu = np.clip((base - 0.54) * 4.2, 0, 1) * smoothstep(bl[None, :], bl[None, :] + 14, hy) \
            * (1 - smoothstep(240, 330, hy))
        alto = np.clip((base2 - 0.64) * 4.5, 0, 1) * smoothstep(320, 390, hy) * (1 - smoothstep(560, 680, hy))
        cirr = np.clip((streak - 0.56) * 2.6, 0, 1) * smoothstep(470, 560, hy)
        D = np.clip((cu * 1.15 + alto * 0.8 + cirr * 0.45) * clear, 0, 1).astype(np.float32)
        Ds = ndimage.gaussian_filter(D, 1.6)
        # luz solar desde abajo (sol por debajo de la base): densidad acumulada con peso exponencial
        # hacia arriba desde la base de cada columna -> transmitancia de Beer, sin bandas
        from scipy.signal import lfilter
        below = lfilter([1.0], [1.0, -0.94], Ds, axis=0)
        Tb = np.exp(-below * 0.16)
        # borde plateado: contorno orientado al sol, muy intenso cerca de él (dispersión hacia delante)
        gy, gx = np.gradient(Ds)
        mag = np.sqrt(gx * gx + gy * gy) + 1e-6
        ddx, ddy = (SUN[0] - X), (SUN[1] - Y)
        dd = np.sqrt(ddx * ddx + ddy * ddy) + 1e-3
        facing = np.clip((-gx * ddx - gy * ddy) / (mag * dd), 0, 1)
        rim = np.clip(mag * 5.0, 0, 1) * facing / (1 + (dsun / 380.0) ** 2)
        theta = dsun * k / F
        g = 0.72
        hg = (1 - g * g) / (1 + g * g - 2 * g * np.cos(theta)) ** 1.5 / (4 * math.pi)
        sr, sg, sb = sky_at(X, Y)
        # cara en sombra: luz solar enrojecida dispersada muchas veces dentro de la nube + cielo azul (malva)
        ms = sun_col[None, None, :] * np.array([0.05, 0.022, 0.03], np.float32) \
            + np.asarray(zenith, np.float32)[None, None, :] * np.array([1.4, 0.9, 2.6], np.float32)
        shadow = np.stack([sr, sg, sb], -1) * 0.16 + ms * (0.85 + 0.3 * (1 - Ds))[..., None]
        lit = sun_col[None, None, :] * (Tb * (0.10 + 0.45 * hg) + rim * 1.4)[..., None]
        col = shadow + lit
        alpha = 1 - np.exp(-D * 3.6)
        cl = np.concatenate([col * alpha[..., None], alpha[..., None]], -1).astype(np.float32)
        out["cloud"] = (cl, (cx0, cy0, cw, chh))   # fila 0 = abajo, como espera OpenGL

    if "dist" in parts:
        # ------------------------------------------------------------------ cordilleras (sin paralaje: muy lejanas)
        dx0, dy0 = -1150 * k, -480 * k
        dw, dh = int(2300 * k), int(640 * k)
        ys, xs = np.mgrid[0:dh, 0:dw].astype(np.float32)
        X = dx0 + xs
        Y = dy0 + ys
        # color del horizonte (cielo a 1,5° sobre el horizonte) en cada x
        hr_, hg_, hb_ = sky_at(dx0 + np.arange(dw, dtype=np.float32), np.full(dw, YH + 26 * k, np.float32))
        horizon = np.stack([hr_, hg_, hb_], -1)
        ranges = [  # distancia (km), altura base y amplitud (px sobre el horizonte), escala, semilla
            (45.0, 16, 70, 520, 11), (20.0, -6, 58, 340, 12), (8.0, -34, 46, 260, 13), (3.0, -78, 52, 210, 14),
        ]
        acc = np.zeros((dh, dw, 3), np.float32)
        A = np.zeros((dh, dw), np.float32)
        obj = hexl("#0c1014") * 0.6
        tree_mask_surf = cairo.ImageSurface(cairo.FORMAT_A8, dw, dh)
        tctx = cairo.Context(tree_mask_surf)
        rng = np.random.default_rng(7)
        for i, (dkm, base_px, amp_px, scl, sd) in enumerate(ranges):
            ridge = fbm1(dw, scl * k, 7, seed=sd, ridged=True)
            ridge = ndimage.gaussian_filter1d(ridge, 2.0)
            crest = YH + (base_px + amp_px * (ridge - 0.35) * 1.8) * k
            cover = np.clip(crest[None, :] - Y + 0.5, 0, 1)
            if i >= 2:
                # siluetas de árboles sobre la cresta de las colinas más cercanas
                tctx.set_operator(cairo.OPERATOR_CLEAR)
                tctx.paint()
                tctx.set_operator(cairo.OPERATOR_OVER)
                tctx.set_source_rgba(0, 0, 0, 1)
                nt = 340 if i == 3 else 520
                hscale = 1.0 if i == 3 else 0.45
                for j in range(nt):
                    xi = rng.integers(0, dw)
                    cy = dh - (crest[xi] - dy0)   # en coordenadas Cairo (y hacia abajo)
                    th = rng.uniform(5, 14) * k * hscale
                    if rng.random() < 0.6:   # conífera
                        tctx.move_to(xi - th * 0.28, cy + 2)
                        tctx.line_to(xi, cy - th)
                        tctx.line_to(xi + th * 0.28, cy + 2)
                        tctx.close_path()
                    else:
                        tctx.arc(xi, cy - th * 0.45, th * 0.42, 0, 2 * math.pi)
                    tctx.fill()
                tree_mask_surf.flush()
                tm = np.ndarray((dh, tree_mask_surf.get_stride()), np.uint8, tree_mask_surf.get_data())[:, :dw]
                tm = tm[::-1].astype(np.float32) / 255
                cover = np.maximum(cover, tm)
            Tr = math.exp(-dkm / 11.0)
            # perspectiva atmosférica: el objeto se apaga y el aire iluminado se suma
            col = obj[None, None, :] * Tr + horizon[None, :, :] * (1 - Tr) * 1.02
            # bruma en los valles: más densa cuanto más bajo respecto a la cresta
            depth_below = (crest[None, :] - Y) / k
            fogA = np.clip(depth_below / (55 + 25 * i), 0, 1) ** 0.9 * (0.75 - 0.12 * i)
            col = col * (1 - fogA[..., None]) + horizon[None, :, :] * 1.12 * fogA[..., None]
            # borde de la cresta encendido cerca del sol
            near_sun = np.exp(-np.abs(X - SUN[0]) / (260 * k))
            crest_glow = np.exp(-np.maximum(depth_below, 0) / 2.0) * near_sun * (0.4 + 0.2 * i)
            col = col + sun_col[None, None, :] * 0.02 * crest_glow[..., None]
            acc = acc * (1 - cover[..., None]) + col * cover[..., None]
            A = A + (1 - A) * cover
        out["dist"] = (np.concatenate([acc, A[..., None]], -1).astype(np.float32), (dx0, dy0, dw, dh))

    if "mist" in parts:
        # ------------------------------------------------------------------ bruma que deriva (baja resolución)
        mx0, my0, mw, mh = -1250 * k, YH - 260 * k, 2500 * k, 300 * k
        nh, nw = int(150 * k), int(1250 * k)
        m = fbm2(nh, nw, 90, 5, seed=21, aspect=5.0)
        yy = np.linspace(0, 1, nh, dtype=np.float32)[:, None]
        prof = np.exp(-((yy - 0.55) / 0.2) ** 2) * np.sin(np.pi * yy) ** 2
        xx = np.linspace(0, 1, nw, dtype=np.float32)[None, :]
        prof = prof * np.sqrt(np.clip(np.sin(np.pi * xx), 0, 1))
        ma = np.clip((m - 0.35) * 1.6, 0, 1) * prof * 0.42
        xsm = mx0 + np.arange(nw, dtype=np.float32) * (mw / nw)
        hr_, hg_, hb_ = sky_at(np.clip(xsm, -900 * k, 900 * k), np.full(nw, YH + 18 * k, np.float32))
        mcol = np.stack([hr_, hg_, hb_], -1)[None, :, :] * 1.15
        out["mist"] = (np.concatenate([mcol * ma[..., None], ma[..., None]], -1).astype(np.float32),
                       (mx0, my0, mw, mh))

    if "subj" in parts:
        # ------------------------------------------------------------------ colina, árbol y hombre (Cairo)
        sx0, sy0 = -1150 * k, -470 * k
        sw, shh = int(2300 * k), int(840 * k)
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, sw, shh)
        c = cairo.Context(surf)
        c.set_antialias(cairo.ANTIALIAS_BEST)
        # coordenadas de pantalla en reposo -> Cairo
        c.translate(-sx0, shh + sy0)
        c.scale(1, -1)
        c.scale(k, k)
        rnd = np.random.default_rng(3)
        hill_col = (0.055, 0.045, 0.06)

        def crest_y(x):
            # ladera que sube hacia la derecha hasta la cima donde está el árbol
            return -275 + 150 / (1 + math.exp(-(x - 40) / 170)) + 8 * math.sin(x * 0.011) + 4 * math.sin(x * 0.037)

        c.set_source_rgb(*hill_col)
        c.move_to(-1160, -480)
        for x in range(-1160, 1170, 6):
            c.line_to(x, crest_y(x))
        c.line_to(1160, -480)
        c.close_path()
        c.fill()
        # hierba fina sobre la cresta (silueta detallada)
        for i in range(5200):
            x = rnd.uniform(-1160, 1160)
            y0 = crest_y(x) - 1
            hgt = rnd.uniform(3, 13) * (1.25 if rnd.random() < 0.1 else 1.0)
            lean = rnd.uniform(-0.5, 0.25) * hgt
            c.move_to(x - 0.7, y0)
            c.curve_to(x - 0.4, y0 + hgt * 0.5, x + lean * 0.5, y0 + hgt * 0.9, x + lean, y0 + hgt)
            c.curve_to(x + lean * 0.4, y0 + hgt * 0.8, x + 0.4, y0 + hgt * 0.5, x + 0.7, y0)
            c.close_path()
            c.fill()
        # rama cortada en el suelo, junto al árbol
        tree_x = 330.0
        ty = crest_y(tree_x)
        c.set_line_cap(cairo.LINE_CAP_ROUND)
        c.set_line_width(2.2)
        c.move_to(tree_x - 70, crest_y(tree_x - 70) + 2)
        c.line_to(tree_x - 22, crest_y(tree_x - 22) + 5)
        c.stroke()
        c.set_line_width(1.2)
        for (a, b, e, f) in ((-58, 3, -64, 12), (-44, 4, -40, 13), (-33, 5, -38, 12)):
            c.move_to(tree_x + a, crest_y(tree_x + a) + b)
            c.line_to(tree_x + e, crest_y(tree_x + e) + f)
            c.stroke()
        # árbol joven: tronco recto, tutor, atadura y copa con huecos (por donde pasa el sol)
        c.set_line_width(5.4)
        c.move_to(tree_x, ty)
        c.curve_to(tree_x + 1, ty + 90, tree_x - 1, ty + 160, tree_x + 1, ty + 225)
        c.stroke()
        c.set_line_width(2.2)
        c.move_to(tree_x - 9, ty - 2)
        c.line_to(tree_x - 9, ty + 150)
        c.stroke()
        c.set_line_width(1.6)
        for yy_ in (ty + 60, ty + 120):
            c.move_to(tree_x - 10, yy_)
            c.line_to(tree_x + 2, yy_ + 2)
            c.stroke()
        leaves = []

        def branch(x, y, ang, ln, wd, depth):
            ex, ey = x + math.sin(ang) * ln, y + math.cos(ang) * ln
            c.set_line_width(wd)
            c.move_to(x, y)
            c.curve_to((x + ex) / 2 + rnd.uniform(-3, 3), (y + ey) / 2, (x + ex) / 2, (y + ey) / 2, ex, ey)
            c.stroke()
            if depth == 0:
                leaves.append((ex, ey))
                return
            if depth <= 2:
                leaves.append((ex, ey))
            for _ in range(int(rnd.choice([2, 2, 3]))):
                branch(ex, ey, (ang + rnd.uniform(-0.62, 0.62)) * 0.82, ln * rnd.uniform(0.62, 0.78), wd * 0.66,
                       depth - 1)

        for a, y_off in ((-1.0, 175), (-0.55, 195), (-0.2, 215), (0.35, 200), (0.8, 180), (1.1, 210)):
            branch(tree_x, ty + y_off, a, 46, 2.2, 3)
        branch(tree_x, ty + 220, 0.05, 70, 2.6, 3)
        for (lx, ly) in leaves:
            for j in range(int(rnd.integers(26, 46))):
                r = rnd.uniform(0, 1) ** 0.6 * 24
                a = rnd.uniform(0, 2 * math.pi)
                px, py = lx + math.cos(a) * r, ly + math.sin(a) * r * 0.8
                c.save()
                c.translate(px, py)
                c.rotate(rnd.uniform(0, math.pi))
                c.scale(rnd.uniform(2.2, 3.6), rnd.uniform(1.0, 1.6))
                c.arc(0, 0, 1, 0, 2 * math.pi)
                c.restore()
                c.fill()
        # el hombre: abrigo largo, manos a la espalda, mira hacia el árbol y el sol
        man_x = 205.0
        gy = crest_y(man_x)
        Hm = 168.0
        u = Hm / 100.0

        def P(x, y):
            return (man_x + x * u, gy + y * u)

        c.set_source_rgb(*hill_col)
        # piernas y zapatos
        for (x0, x1) in ((-4.5, -3.0), (2.5, 4.5)):
            c.move_to(*P(x0 - 2.6, 47))
            c.curve_to(*P(x0 - 2.8, 30), *P(x0 - 2.2, 12), *P(x0 - 1.6, 1.5))
            c.line_to(*P(x0 + 5.8, 0.0))
            c.line_to(*P(x0 + 5.6, 1.6))
            c.line_to(*P(x0 + 1.4, 2.4))
            c.curve_to(*P(x0 + 1.9, 14), *P(x0 + 2.6, 30), *P(x0 + 2.8, 47))
            c.close_path()
            c.fill()
        # abrigo (hasta la rodilla, con vuelo trasero)
        c.move_to(*P(-3.0, 83))
        c.curve_to(*P(-9.0, 80), *P(-11.0, 66), *P(-10.0, 54))
        c.curve_to(*P(-10.0, 46), *P(-12.5, 36), *P(-13.5, 29))
        c.curve_to(*P(-6.0, 26.5), *P(3.0, 26.5), *P(9.0, 28.5))
        c.curve_to(*P(8.0, 38), *P(7.6, 50), *P(8.6, 60))
        c.curve_to(*P(9.4, 70), *P(8.0, 79), *P(4.5, 83))
        c.close_path()
        c.fill()
        # brazos a la espalda (codo visible)
        c.move_to(*P(-5.5, 80))
        c.curve_to(*P(-11.5, 72), *P(-12.5, 62), *P(-9.0, 55))
        c.line_to(*P(-5.0, 56))
        c.curve_to(*P(-8.0, 62), *P(-7.5, 70), *P(-2.0, 76))
        c.close_path()
        c.fill()
        # cuello, cabeza y nariz
        c.move_to(*P(-1.5, 82))
        c.line_to(*P(-1.8, 88.5))
        c.line_to(*P(2.8, 88.5))
        c.line_to(*P(3.4, 82))
        c.close_path()
        c.fill()
        c.save()
        c.translate(*P(0.9, 93.6))
        c.scale(5.4 * u, 6.4 * u)
        c.arc(0, 0, 1, 0, 2 * math.pi)
        c.restore()
        c.fill()
        c.move_to(*P(5.9, 94.5))
        c.line_to(*P(7.6, 91.4))
        c.line_to(*P(5.8, 90.6))
        c.close_path()
        c.fill()
        # cuello del abrigo subido
        c.move_to(*P(-3.6, 82))
        c.line_to(*P(-3.2, 87.5))
        c.line_to(*P(-0.5, 84))
        c.close_path()
        c.fill()

        subj = cairo_to_premult(surf)
        # luz de relleno del cielo en la cara frontal (azulada, muy suave) y contorno dorado
        a = subj[..., 3]
        sky_fill = hexl("#4a5a8a") * 0.03
        subj[..., :3] += sky_fill[None, None, :] * a[..., None]
        rim = rim_light(a, SUN, (sx0, sy0), sun_col, 0.26, 460 * k, width=1.4 * k)
        subj[..., :3] += rim
        out["subj"] = (subj, (sx0, sy0, sw, shh))
        # versión desenfocada (para el cambio de foco) y mapa de balanceo con el viento
        out["subjB"] = (downblur(subj, 2, 3.2 * k), (sx0, sy0, sw, shh))
        wmap = np.zeros((shh, sw), np.float32)
        ys, xs = np.mgrid[0:shh, 0:sw].astype(np.float32)
        Xs, Ys = (xs + sx0) / k, (ys + sy0) / k
        cr = np.array([crest_y(x) for x in Xs[0]], np.float32)[None, :]
        h_above = Ys - cr
        wmap += np.clip(h_above / 14.0, 0, 1) * (h_above < 18) * 0.35            # hierba de la cresta
        tree_w = smoothstep(ty + 120, ty + 300, Ys) * np.exp(-((Xs - tree_x) / 120) ** 2)
        wmap = np.maximum(wmap, tree_w)
        coat = smoothstep(37, 28, (Ys - gy) / u) * np.exp(-((Xs - man_x - 0) / 16) ** 2) * 0.25
        wmap = np.maximum(wmap, coat)
        out["subjW"] = (wmap, (sx0, sy0, sw, shh))
        # techo de la silueta por columna (en px de capa), dilatado por el balanceo y el desenfoque
        rows_any = subj[..., 3] > 0.004
        top = np.where(rows_any.any(0), shh - 1 - np.argmax(rows_any[::-1], 0), -1).astype(np.float32)
        top = ndimage.maximum_filter1d(top, int(30 * k) | 1)
        out["subj_top"] = (top + sy0 + 12 * k, (sx0, sw))
        out["tree_xy"] = (tree_x * k, (ty + 220) * k)

    if "grass" in parts:
        # ------------------------------------------------------------------ hierba en primer plano (Cairo)
        gx0, gy0 = -1500 * k, -545 * k
        gw, gh = int(3000 * k), int(760 * k)
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, gw, gh)
        c = cairo.Context(surf)
        c.set_antialias(cairo.ANTIALIAS_BEST)
        c.translate(-gx0, gh + gy0)
        c.scale(1, -1)
        c.scale(k, k)
        rnd = np.random.default_rng(9)
        base_y = -545
        # masa de base y miles de briznas; espigas y algún diente de león
        c.set_source_rgb(0.018, 0.016, 0.02)
        c.rectangle(-1500, base_y, 3000, 70)
        c.fill()
        for i in range(3600):
            x = rnd.uniform(-1500, 1500)
            tall = rnd.random()
            side = smoothstep(560, 900, abs(x))
            hgt = 70 + 230 * tall ** 1.7 + 230 * side * tall ** 0.8
            lean = rnd.uniform(-0.28, 0.18) * hgt
            wd = rnd.uniform(1.6, 3.6)
            shade_ = rnd.uniform(0.012, 0.03)
            c.set_source_rgb(shade_ * 1.1, shade_, shade_ * 1.2)
            y0 = base_y + rnd.uniform(0, 50)
            c.move_to(x - wd, y0)
            c.curve_to(x - wd * 0.6, y0 + hgt * 0.45, x + lean * 0.4, y0 + hgt * 0.85, x + lean, y0 + hgt)
            c.curve_to(x + lean * 0.35, y0 + hgt * 0.8, x + wd * 0.4, y0 + hgt * 0.45, x + wd, y0)
            c.close_path()
            c.fill()
            if rnd.random() < 0.07:   # espiga
                tx, tyy = x + lean, y0 + hgt
                for j in range(9):
                    c.save()
                    c.translate(tx - lean * 0.02 * j, tyy - j * 4.2)
                    c.rotate(0.5 if j % 2 else -0.5)
                    c.scale(4.2, 1.8)
                    c.arc(0, 0, 1, 0, 2 * math.pi)
                    c.restore()
                    c.fill()
            elif rnd.random() < 0.012:  # diente de león (vilanos que luego vuelan)
                tx, tyy = x + lean, y0 + hgt
                c.set_line_width(0.9)
                for j in range(26):
                    a2 = j / 26 * 2 * math.pi
                    c.move_to(tx, tyy)
                    c.line_to(tx + math.cos(a2) * 15, tyy + math.sin(a2) * 15)
                c.stroke()
        grass = cairo_to_premult(surf)
        a = grass[..., 3]
        rim = rim_light(a, SUN, (gx0, gy0), sun_col, 0.55, 520 * k, width=1.2 * k)
        grass[..., :3] += rim + hexl("#33405a")[None, None, :] * 0.012 * a[..., None]
        out["grass"] = (grass, (gx0, gy0, gw, gh))
        out["grassB"] = (downblur(grass, 4, 13.0 * k), (gx0, gy0, gw, gh))
        rows_any = grass[..., 3] > 0.004
        top = np.where(rows_any.any(0), gh - 1 - np.argmax(rows_any[::-1], 0), -1).astype(np.float32)
        top = ndimage.maximum_filter1d(top, int(110 * k) | 1)
        out["grass_top"] = (top + gy0 + 45 * k, (gx0, gw))
    return out




# ====================================================================== animación (CPU, ligera)
def ease(u):
    u = min(1.0, max(0.0, u))
    return u * u * (3 - 2 * u)


def camera(t, k):
    """Trayectoria con inercia: avance lento, desplazamiento lateral que descubre el sol y leve subida."""
    u = ease(t / DUR)
    x = -0.18 + 0.48 * u
    y = 0.02 + 0.10 * ease((t - 4) / 24)
    z = 0.55 * u
    # cámara en mano: ruido de baja frecuencia (milímetros)
    x += 0.004 * math.sin(t * 0.9) + 0.002 * math.sin(t * 2.3 + 1)
    y += 0.003 * math.sin(t * 1.1 + 2) + 0.0015 * math.sin(t * 2.9)
    return x, y, z


def gust_np(xw, t):
    g = 0.5 + 0.5 * np.sin(0.31 * xw + 1.05 * t)
    g = g * (0.62 + 0.38 * np.sin(0.13 * xw + 0.41 * t + 1.7))
    return g * g


def sway_np(xw, t):
    g = gust_np(xw, t)
    return 0.9 * g + (0.3 + 0.7 * g) * (0.55 * np.sin(2.3 * t + 1.7 * xw) + 0.3 * np.sin(4.1 * t + 3.1 * xw)
                                          + 0.15 * np.sin(7.3 * t + 5.3 * xw))


class Motes:
    """Vilanos y polen flotando entre la cámara y el árbol (3D), con bokeh según la distancia."""

    def __init__(self, n=700, seed=5):
        r = np.random.default_rng(seed)
        self.z = r.uniform(1.6, 40.0, n)
        self.x0 = r.uniform(-1, 1, n) * self.z * 0.45 + 6.0
        self.y0 = r.uniform(-0.55, 0.25, n) * self.z * 0.35
        self.ph = r.uniform(0, 6.28, n)
        self.b = r.random(n) ** 3
        self.v = r.uniform(0.25, 0.7, n)

    def frame(self, t, cam, F, k, focus_d, coc_inf):
        x = self.x0 - self.v * t * (0.8 + 0.6 * gust_np(self.x0 * 0.3, t)) + 0.08 * np.sin(t * 0.7 + self.ph)
        y = self.y0 + 0.05 * np.sin(t * 0.5 + self.ph * 1.3) + 0.012 * t
        span = self.z * 0.9 + 4
        x = (x + span) % (2 * span) - span
        d = self.z - cam[2]
        sx = (x - cam[0]) * F / d
        sy = (y - cam[1]) * F / d
        coc = coc_inf * np.abs(1 - focus_d / d)
        core = np.maximum(1.4 * k, 0.004 * F / d)
        size = np.minimum(np.maximum(core, coc), 70 * k)
        energy = (core / size) ** 2
        # dispersión hacia delante: brillan más cerca de la dirección del sol
        bright = self.b * energy * (0.35 + 1.6 * np.exp(-((sx - 300 * k) ** 2 + (sy - 44 * k) ** 2) / (520 * k) ** 2))
        col = np.tile(np.array([1.0, 0.82, 0.55, 0.0], np.float32), (len(sx), 1))
        return np.concatenate([np.stack([sx, sy, size, bright * 2.2], -1), col], -1).astype(np.float32)


class Leaves:
    """Hojas que el viento arranca del árbol y caen girando; algunas pasan cerca de la cámara."""

    def __init__(self, n=26, seed=8):
        r = np.random.default_rng(seed)
        self.t0 = np.sort(r.uniform(2.0, DUR - 4, n))
        self.z = np.where(r.random(n) < 0.1, r.uniform(7, 12, n), r.uniform(29, 33, n))
        self.vx = r.uniform(0.6, 1.4, n)
        self.vy = r.uniform(0.25, 0.5, n)
        self.spin = r.uniform(2, 6, n) * r.choice([-1, 1], n)
        self.ox = r.uniform(-0.6, 0.6, n)
        self.oy = r.uniform(-0.4, 0.5, n)

    def frame(self, t, cam, F, k, tree_xy, focus_d, coc_inf):
        verts = []
        for i in range(len(self.t0)):
            dt = t - self.t0[i]
            if dt < 0 or dt > 9:
                continue
            z = self.z[i]
            # nacen en la copa (llevadas a la profundidad de cada hoja)
            X0 = tree_xy[0] * 32.0 / F + self.ox[i]
            Y0 = tree_xy[1] * 32.0 / F + self.oy[i]
            if z < 20:
                X0 = (tree_xy[0] + 200 * k) * z / F + 1.0
                Y0 = 0.6 + self.oy[i]
            X = X0 - self.vx[i] * dt * (1.6 if z < 20 else 1.0)
            Y = Y0 - self.vy[i] * dt + 0.15 * math.sin(dt * 2.1 + i)
            d = z - cam[2]
            sx, sy = (X - cam[0]) * F / d, (Y - cam[1]) * F / d
            size = 0.05 * F / d
            ang = self.spin[i] * dt
            flip = abs(math.cos(dt * 3.1 + i)) * 0.6 + 0.4
            coc = coc_inf * abs(1 - focus_d / d)
            soft = min(0.9, 0.08 + coc / max(size, 1.0) * 0.5)
            col = (0.035, 0.03, 0.04, soft)
            ca, sa = math.cos(ang), math.sin(ang)
            hx, hy = size, size * 0.45 * flip
            pts = [(-hx, -hy), (hx, -hy), (hx, hy), (-hx, hy)]
            uvs = [(0, 0), (1, 0), (1, 1), (0, 1)]
            P = [(sx + px * ca - py * sa, sy + px * sa + py * ca) for px, py in pts]
            for tri in ((0, 1, 2), (0, 2, 3)):
                for j in tri:
                    verts.append([*P[j], *uvs[j], *col])
        return verts


class Birds:
    """Bandada lejana que cruza delante del sol (aleteo y planeo)."""

    def __init__(self, n=9, seed=4):
        r = np.random.default_rng(seed)
        self.dx = r.uniform(-14, 14, n)
        self.dy = r.uniform(-4, 4, n)
        self.ph = r.uniform(0, 6.28, n)
        self.n = n

    def frame(self, t, cam, F, k, haze_col):
        verts = []
        t0, t1 = 9.0, 26.0
        if not (t0 < t < t1):
            return verts
        u = (t - t0) / (t1 - t0)
        for i in range(self.n):
            z = 140.0 + self.dx[i] * 2
            X = 70 - 150 * u + self.dx[i]
            Y = 14 + self.dy[i] + 2.0 * math.sin(u * 3 + i)
            d = z - cam[2]
            sx, sy = (X - cam[0]) * F / d, (Y - cam[1]) * F / d
            span = 0.9 * F / d
            flap = math.sin(t * 9.0 + self.ph[i])
            glide = 0.5 + 0.5 * math.sin(t * 0.8 + i)
            wing = flap * (1 - glide * 0.8)
            col = (*haze_col, 0.0)
            for s in (-1, 1):
                tip = (sx + s * span, sy + wing * span * 0.55)
                mid = (sx + s * span * 0.45, sy + 0.12 * span + wing * span * 0.2)
                root = (sx, sy)
                body = (sx + 0.08 * span * s, sy - 0.06 * span)
                for p_ in (root, mid, tip, root, body, mid):
                    verts.append([p_[0], p_[1], 0.5, 9.0, *col])
        return verts


# ====================================================================== audio (sincronizado con el viento)
def make_audio(path, dur, sr=48000, seed=2):
    """Viento cuyas ráfagas siguen la misma función que mueve la hierba, piano y cuerdas."""
    from scipy.signal import butter, sosfilt, fftconvolve
    rng = np.random.default_rng(seed)
    n = int(dur * sr)
    t = np.arange(n) / sr

    def filt(x, kind, f):
        return sosfilt(butter(2, f, btype=kind, fs=sr, output="sos"), x)

    gust = np.array([gust_np(np.linspace(-15, 15, 9), tt).mean() for tt in np.arange(0, dur, 0.05)])
    g = np.interp(t, np.arange(0, dur, 0.05), gust)
    wind_l = filt(rng.standard_normal(n), "bandpass", [180, 1400]) * (0.15 + 0.9 * g)
    wind_r = filt(rng.standard_normal(n), "bandpass", [180, 1400]) * (0.15 + 0.9 * np.roll(g, int(0.12 * sr)))
    hiss = filt(rng.standard_normal(n), "highpass", 3500) * (0.02 + 0.12 * g ** 2)
    out = np.stack([wind_l + hiss, wind_r + hiss], -1) * 0.22

    def hz(m):
        return 440 * 2 ** ((m - 69) / 12)

    def piano(m, d, vel):
        f0 = hz(m)
        nn = int((d + 3) * sr)
        tt = np.arange(nn) / sr
        B = 0.0004
        s = np.zeros(nn)
        for kk in range(1, 11):
            fk = kk * f0 * math.sqrt(1 + B * kk * kk)
            s += (1 / kk ** 1.3) * np.sin(2 * math.pi * fk * tt) * np.exp(-tt / (2.6 * (261.6 / f0) ** 0.6 / (1 + 0.4 * kk)))
        return s * vel * 0.25 * np.minimum(1, tt / 0.003)

    def strings(ms, d, att=3.0):
        nn = int((d + 2) * sr)
        tt = np.arange(nn) / sr
        s = np.zeros(nn)
        for m in ms:
            for det in (-0.07, 0.0, 0.08):
                ph_ = np.cumsum(hz(m) * 2 ** (det / 12) * (1 + 0.003 * np.sin(2 * math.pi * 5.2 * tt))) / sr
                s += 2 * (ph_ % 1) - 1
        s = filt(s, "lowpass", 1600)
        e = np.minimum(1, tt / att) * np.where(tt > d, np.exp(-(tt - d) / 0.8), 1)
        return s * e / (len(ms) * 3) * 0.16

    def put(sig, t0, gain=1.0, pan=0.0):
        i = int(t0 * sr)
        if i >= n:
            return
        sig = sig[: n - i]
        th = (pan + 1) * math.pi / 4
        out[i:i + len(sig), 0] += sig * gain * math.cos(th)
        out[i:i + len(sig), 1] += sig * gain * math.sin(th)

    # re menor -> si bemol -> fa -> la sus, y resolución en re mayor con el título
    prog = [([50, 57, 62, 65], 5.0), ([46, 53, 58, 62], 5.0), ([41, 48, 57, 60], 5.0), ([45, 50, 57, 64], 5.0),
            ([50, 57, 62, 66], 7.0), ([43, 50, 59, 62], 5.0)]
    tt0 = 1.5
    for ms, d in prog:
        st = strings(ms[1:], d)
        put(st, tt0, 1.0, -0.4)
        put(st, tt0 + 0.011, 1.0, 0.4)
        put(piano(ms[0] - 12, d, 0.55), tt0, 1.0, -0.2)
        for j, m in enumerate([ms[1], ms[2], ms[3], ms[2] + 12]):
            put(piano(m + 12, 2.0, 0.42 if j else 0.5), tt0 + j * d / 4, 1.0, (j - 1.5) * 0.25)
        tt0 += d
    # reverberación de sala grande (respuesta de impulso sintética)
    rn = int(2.4 * sr)
    ir = rng.standard_normal((rn, 2)) * np.exp(-6.9 * np.arange(rn) / sr / 2.4)[:, None]
    ir = np.stack([filt(ir[:, 0], "lowpass", 5000), filt(ir[:, 1], "lowpass", 5000)], -1)
    ir /= np.sqrt((ir ** 2).sum() / 2)
    wet = np.stack([fftconvolve(out[:, c], ir[:, c])[:n] for c in range(2)], -1)
    out = out * 0.8 + wet * 0.18
    fade = np.ones(n)
    fade[: int(2 * sr)] = np.linspace(0, 1, int(2 * sr))
    fade[-int(2.5 * sr):] = np.linspace(1, 0, int(2.5 * sr))
    out *= fade[:, None]
    out /= np.max(np.abs(out)) + 1e-9
    out *= 0.8
    import soundfile as sf
    sf.write(path, out.astype(np.float32), sr)


# ====================================================================== LUT de gradación
def grade_lut(n=33):
    """Tabla 3D: entrada = sqrt(radiancia*exposición/16); salida = sRGB final (antes de viñeta y grano)."""
    g = np.linspace(0, 1, n, dtype=np.float64)
    b, gg, r = np.meshgrid(g, g, g, indexing="ij")          # orden de textura: x=r, y=g, z=b
    C = np.stack([r, gg, b], -1) ** 2 * 16.0
    C = C * np.array([1.0, 0.9, 0.84])                       # balance de blancos de atardecer
    M_in = np.array([[0.59719, 0.35458, 0.04823], [0.07600, 0.90834, 0.01566], [0.02840, 0.13383, 0.83777]])
    M_out = np.array([[1.60475, -0.53108, -0.07367], [-0.10208, 1.10813, -0.00605], [-0.00327, -0.07276, 1.07602]])
    v = C @ M_in.T
    v = (v * (v + 0.0245786) - 0.000090537) / (v * (0.983729 * v + 0.4329510) + 0.238081)
    C = np.clip(v @ M_out.T, 0, 1)
    lu = (C * [0.2126, 0.7152, 0.0722]).sum(-1, keepdims=True)
    C = lu + (C - lu) * 1.12
    sh_ = 1 - np.clip(lu / 0.5, 0, 1) ** 2 * (3 - 2 * np.clip(lu / 0.5, 0, 1))
    u = np.clip((lu - 0.55) / 0.45, 0, 1)
    hi = u * u * (3 - 2 * u)
    C = C + np.array([-0.010, 0.006, 0.026]) * sh_ + np.array([0.020, 0.010, -0.014]) * hi
    C = np.clip(C, 0, 1)
    C = np.where(C <= 0.0031308, C * 12.92, 1.055 * C ** (1 / 2.4) - 0.055)
    return C.astype(np.float32)


# ====================================================================== render
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--res", default="1920x1080")
    ap.add_argument("--stills", nargs="*", type=float)
    ap.add_argument("--out", default=os.path.join(ROOT, "estilo.mp4"))
    ap.add_argument("--look", default="")
    args = ap.parse_args()
    W, H = map(int, args.res.split("x"))
    for kv in filter(None, args.look.split(",")):
        kk, vv = kv.split("=")
        LOOK[kk] = float(vv)
    sh = Shot(W, H)

    # el sonido se sintetiza en paralelo mientras se pinta y se renderiza
    audio_path = os.path.join(ROOT, "estilo_audio.wav")
    audio_proc = None
    if not args.stills:
        import multiprocessing as mp
        audio_proc = mp.Process(target=make_audio, args=(audio_path, DUR))
        audio_proc.start()

    ctx = moderngl.create_standalone_context(backend="egl")
    quad = ctx.buffer(np.array([-1, -1, 3, -1, -1, 3], "f4"))

    def prog(fs, vs=VS):
        p = ctx.program(vertex_shader=vs, fragment_shader=fs)
        return p, ctx.vertex_array(p, [(quad, "2f", "in_pos")])

    def setu(p, **kw):
        for kk, v in kw.items():
            if kk in p:
                p[kk].value = v

    # --- cielo físico (Rayleigh + Mie) en un solo pase de GPU a 1/4 de resolución
    lw, lh = W // 8 + 8, H // 8 + 8
    lut_rect = (-W / 2 - 16 * sh.k, -H / 2 - 16 * sh.k, W + 32 * sh.k, H + 32 * sh.k)
    p_sky, v_sky = prog(SKY_FS)
    tex_sky = ctx.texture((lw, lh), 4, dtype="f4")
    fb = ctx.framebuffer([tex_sky])
    fb.use()
    ctx.viewport = (0, 0, lw, lh)
    setu(p_sky, uSize=(lw, lh), uRes=(lut_rect[2], lut_rect[3]), uF=sh.F, uYH=sh.YH,
         uSunDir=tuple(sh.sun_dir), uHaze=sh.haze)
    v_sky.render()
    sky_lut = np.frombuffer(tex_sky.read(), np.float32).reshape(lh, lw, 4)[..., :3].copy()
    tex_sky.filter = (moderngl.LINEAR, moderngl.LINEAR)
    t_sky = time.time()

    import multiprocessing as mp
    jobs = [("cloud",), ("dist",), ("mist", "subj"), ("grass",)]
    with mp.get_context("fork").Pool(4) as pool:
        res = pool.starmap(paint_layers, [(sh, sky_lut, lut_rect, sh.zenith, j) for j in jobs])
    layers = {}
    for r_ in res:
        layers.update(r_)
    t_paint = time.time()

    def enc8(arr, scale):
        """HDR lineal premultiplicado -> 8 bits: rgb = sqrt(c/escala), alfa lineal (lectura rápida en GPU)."""
        out = np.empty(arr.shape[:2] + (4,), np.uint8)
        out[..., :3] = np.round(np.sqrt(np.clip(arr[..., :3] / scale, 0, 1)) * 255)
        out[..., 3] = np.round(np.clip(arr[..., 3], 0, 1) * 255) if arr.shape[2] > 3 else 255
        # borde transparente de 1 px: con «clamp to edge» fuera de la capa se lee 0 sin comprobar límites
        out[0, :] = out[-1, :] = 0
        out[:, 0] = out[:, -1] = 0
        return out

    def upload8(arr8):
        h, w = arr8.shape[:2]
        t = ctx.texture((w, h), arr8.shape[2], np.ascontiguousarray(arr8).tobytes())
        t.filter = (moderngl.LINEAR, moderngl.LINEAR)
        t.repeat_x = t.repeat_y = False
        return t

    SCALES = dict(grass=4.0, subj=4.0, far=16.0, sky=24.0)
    # nubes + bruma en una sola textura que deriva (ocupan franjas verticales distintas)
    cl, (cx0, cy0, cw_, ch_) = layers["cloud"]
    mi, (mx0, my0, mw_, mh_) = layers["mist"]
    tx = cw_ / cl.shape[1]
    y0 = min(cy0, my0)
    rows = int(round((cy0 + ch_ - y0) / tx))
    merged = np.zeros((rows, cl.shape[1], 4), np.float32)
    r0 = int(round((cy0 - y0) / tx))
    merged[r0:r0 + cl.shape[0]] = cl
    mr0, mc0 = int(round((my0 - y0) / tx)), int(round((mx0 - cx0) / tx))
    mi_r = ndimage.zoom(mi, (mh_ / tx / mi.shape[0], mw_ / tx / mi.shape[1], 1), order=1)
    hh, ww = min(mi_r.shape[0], rows - mr0), min(mi_r.shape[1], cl.shape[1] - mc0)
    sl = merged[mr0:mr0 + hh, mc0:mc0 + ww]
    sl[:] = sl + mi_r[:hh, :ww] * (1 - sl[..., 3:4])
    layers["cloud"] = (merged, (cx0, y0, cw_, rows * tx))
    tex = {}
    for name, sc_ in (("grass", "grass"), ("grassB", "grass"), ("subj", "subj"), ("subjB", "subj"), ("cloud", "far")):
        tex[name] = upload8(enc8(layers[name][0], SCALES[sc_]))
    # fondo precompuesto en GPU (una vez): cielo físico + disco solar + cordilleras
    t_dist = upload8(enc8(layers["dist"][0], SCALES["far"]))
    p_bg, v_bg = prog(BG_FS)
    t_bg = ctx.texture((W, H), 4)
    t_bg.filter = (moderngl.LINEAR, moderngl.LINEAR)
    fb_bg = ctx.framebuffer([t_bg])
    fb_bg.use()
    ctx.viewport = (0, 0, W, H)
    tex_sky.use(0)
    t_dist.use(1)
    setu(p_bg, uRes=(float(W), float(H)), uF=sh.F, uSun=tuple(sh.SUN), uSunCol=tuple(sh.sun_col), uK=sh.k,
         tSkyF=0, tDist=1, rSky=tuple(float(x) for x in lut_rect), rDist=tuple(float(x) for x in layers["dist"][1]),
         uFarScale=SCALES["far"], uSkyScale=SCALES["sky"])
    v_bg.render()
    t_dist.release()
    fb_bg.release()
    wm = layers["subjW"][0]
    wm_small = ndimage.zoom(wm, 0.5, order=1)
    tex["subjW"] = upload8(np.round(np.clip(wm_small, 0, 1) * 255).astype(np.uint8)[..., None])
    tex["bg"] = t_bg

    # --- programas por fotograma
    p_light, v_light = prog(LIGHT_FS)
    p_rays, v_rays = prog(RAYS_FS)
    p_final, v_final = prog(FINAL_FS)
    p_part = ctx.program(vertex_shader=PART_VS, fragment_shader=PART_FS)
    p_shape = ctx.program(vertex_shader=SHAPE_VS, fragment_shader=SHAPE_FS)
    p_text = ctx.program(vertex_shader=TEXT_VS, fragment_shader=TEXT_FS)
    LW, LH = W // 8, H // 8
    RW, RH = W // 8, H // 8
    t_light = ctx.texture((LW, LH), 4, dtype="f2")
    t_light.filter = (moderngl.LINEAR_MIPMAP_LINEAR, moderngl.LINEAR)
    fb_light = ctx.framebuffer([t_light])
    t_rays = ctx.texture((RW, RH), 4)
    t_rays.filter = (moderngl.LINEAR, moderngl.LINEAR)
    fb_rays = ctx.framebuffer([t_rays])
    t_out = ctx.texture((W, H), 3)
    fb_out = ctx.framebuffer([t_out])
    ctx.enable(moderngl.PROGRAM_POINT_SIZE)
    p_yuv, v_yuv = prog(YUV_FS)
    t_yuv = ctx.texture((W, H * 3 // 2), 1)
    fb_yuv = ctx.framebuffer([t_yuv])
    t_out.filter = (moderngl.NEAREST, moderngl.NEAREST)

    units = {"tGrass": "grass", "tGrassB": "grassB", "tSubj": "subj", "tSubjB": "subjB", "tSubjW": "subjW",
             "tCloud": "cloud", "tBg": "bg"}
    rects = {"rGrass": layers["grass"][1], "rSubj": layers["subj"][1], "rCloud": layers["cloud"][1]}
    for i, (u_, nm) in enumerate(units.items()):
        tex[nm].use(i)
    t_light.use(10)
    t_rays.use(11)
    for p in (p_light, p_final):
        for i, u_ in enumerate(units):
            setu(p, **{u_: i})
        setu(p, **{kk: tuple(float(x) for x in v) for kk, v in rects.items()})
        setu(p, uRes=(float(W), float(H)), uF=sh.F, uK=sh.k, uYH=sh.YH, uSun=tuple(sh.SUN),
             dGrass=3.0, dSubj=32.0, uSunCol=tuple(sh.sun_col))
    setu(p_final, tLight=10, tRays=11, uBar=float(sh.bar))
    setu(p_rays, tLight=10, uSize=(float(RW), float(RH)), uGlowScale=8.0)
    for p in (p_light, p_final):
        setu(p, uScale=(SCALES["grass"], SCALES["subj"], SCALES["far"], SCALES["sky"]))
    setu(p_final, uGlowScale=8.0)
    setu(p_light, uSize=(float(LW), float(LH)))

    # título (Cairo, una vez)
    TWt, THt = int(1100 * sh.k), int(220 * sh.k)
    ts = cairo.ImageSurface(cairo.FORMAT_ARGB32, TWt, THt)
    tc = cairo.Context(ts)
    tc.select_font_face("EB Garamond", cairo.FONT_SLANT_ITALIC, cairo.FONT_WEIGHT_NORMAL)
    tc.set_font_size(78 * sh.k)
    txt = "El hombre que quería ser justo"
    e = tc.text_extents(txt)
    tc.move_to((TWt - e.x_advance) / 2, 100 * sh.k)
    tc.set_source_rgba(0.98, 0.95, 0.88, 1)
    tc.show_text(txt)
    tc.select_font_face("EB Garamond", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
    tc.set_font_size(21 * sh.k)
    sub = "E S T U D I O   D E   E S T I L O"
    e2 = tc.text_extents(sub)
    tc.move_to((TWt - e2.x_advance) / 2, 158 * sh.k)
    tc.set_source_rgba(0.93, 0.78, 0.52, 1)
    tc.show_text(sub)
    ts.flush()
    t_text = ctx.texture((TWt, THt), 4, bytes(ts.get_data()))
    t_text.filter = (moderngl.LINEAR, moderngl.LINEAR)
    tcx, tcy = -400 * sh.k, 255 * sh.k
    tq = np.array([[tcx - TWt / 2, tcy - THt / 2, 0, 1], [tcx + TWt / 2, tcy - THt / 2, 1, 1],
                   [tcx + TWt / 2, tcy + THt / 2, 1, 0], [tcx - TWt / 2, tcy - THt / 2, 0, 1],
                   [tcx + TWt / 2, tcy + THt / 2, 1, 0], [tcx - TWt / 2, tcy + THt / 2, 0, 0]], "f4")
    text_vbo = ctx.buffer(tq.tobytes())
    text_vao = ctx.vertex_array(p_text, [(text_vbo, "2f 2f", "in_pos", "in_uv")])
    p_text["uRes"].value = (float(W), float(H))
    p_text["tText"].value = 12
    t_text.use(12)

    motes, leaves, birds = Motes(), Leaves(), Birds()
    part_vbo = ctx.buffer(reserve=800 * 32)
    part_vao = ctx.vertex_array(p_part, [(part_vbo, "4f 4f", "in_p", "in_c")])
    p_part["uRes"].value = (float(W), float(H))
    setu(p_part, tLight=10)
    # reflejos internos de la lente: fantasmas sobre el eje sol-centro (posición, radio relativo a H, tinte)
    GHOSTS = [(-0.42, 0.018, (1.0, 0.75, 0.45)), (-0.78, 0.045, (0.35, 0.8, 0.7)), (0.28, 0.010, (1.0, 0.75, 0.45)),
              (-1.15, 0.07, (0.6, 0.5, 1.0)), (0.55, 0.028, (1.0, 0.75, 0.45))]
    lut = grade_lut()
    t_grade = ctx.texture3d((33, 33, 33), 4, np.concatenate([np.round(lut * 255), np.full(lut.shape[:3] + (1,), 255)],
                                                           -1).astype(np.uint8).tobytes())
    t_grade.filter = (moderngl.LINEAR, moderngl.LINEAR)
    t_grade.repeat_x = t_grade.repeat_y = t_grade.repeat_z = False
    t_grade.use(14)
    setu(p_final, tGrade=14)
    grain = ndimage.gaussian_filter(np.random.default_rng(1).standard_normal((256, 256)), 0.65, mode="wrap")
    grain = np.clip(0.5 + grain / (4 * grain.std()), 0, 1)
    t_grain = ctx.texture((256, 256), 1, np.round(grain * 255).astype(np.uint8).tobytes())
    t_grain.repeat_x = t_grain.repeat_y = True
    t_grain.filter = (moderngl.LINEAR, moderngl.LINEAR)
    t_grain.use(15)
    setu(p_final, tGrain=15)
    grng = np.random.default_rng(9)
    cols_texs = [ctx.texture((960, 1), 4, dtype="f4") for _ in range(2)]
    for ct in cols_texs:
        ct.filter = (moderngl.NEAREST, moderngl.NEAREST)
    frame_no = [0]
    for p in (p_light, p_final):
        setu(p, tCols=13)
    xcol = ((np.arange(960, dtype=np.float32) * 2 - 960 + 1) * sh.k)
    gtop, (gtx0, gtw) = layers["grass_top"]
    stop_, (stx0, stw) = layers["subj_top"]

    def columns(t, cam):
        out = np.empty((960, 4), np.float32)
        for (dd, ch, amp, fine, tops, tx0, ctop) in ((3.0, 0, 26.0, 3.0, gtop, gtx0, 2), (32.0, 1, 5.0, 1.0, stop_, stx0, 3)):
            s_ = dd / (dd - cam[2])
            qx = xcol / s_ + cam[0] * sh.F / dd
            xw = qx * dd / sh.F
            fq = 0.011 if ch == 0 else 0.02
            ft = 5.7 if ch == 0 else 6.0
            out[:, ch] = amp * sway_np(xw, t) + fine * np.sin(t * ft + qx * fq)
            idx = np.clip((qx - tx0).astype(np.int32), 0, len(tops) - 1)
            out[:, ctop] = (tops[idx] - cam[1] * sh.F / dd) * s_
        return out
    shape_vbo = ctx.buffer(reserve=4000 * 32)
    shape_vao = ctx.vertex_array(p_shape, [(shape_vbo, "2f 2f 4f", "in_pos", "in_uv", "in_col")])
    p_shape["uRes"].value = (float(W), float(H))
    haze_bird = tuple(float(x) for x in np.clip(sky_lut[lh // 2 + 20, lw // 2] * 0.0 + np.array([0.09, 0.075, 0.1]), 0, 1))

    sun_uv = ((sh.SUN[0] + W / 2) / W, (sh.SUN[1] + H / 2) / H)
    # lente: 50 mm f/2.8; CoC en px de un punto en el infinito con foco a S metros
    def coc_inf(S):
        return 50 * 50 / (2.8 * (S * 1000 - 50)) * W / 36

    def render_frame(t, yuv=False):
        cam = camera(t, sh.k)
        focus = ease((t - 2.6) / 3.0)
        focus_d = 3.0 + (32.0 - 3.0) * focus
        fade = ease(t / 2.2) * (1 - ease((t - (DUR - 1.6)) / 1.6))
        common = dict(uCam=tuple(cam), uTime=t, uFocus=focus, uCloudDrift=-t * 4.0 * sh.k)
        ct = cols_texs[frame_no[0] % 2]
        frame_no[0] += 1
        ct.write(columns(t, cam).tobytes())
        ct.use(13)
        # luz y rayos (baja resolución)
        fb_light.use()
        ctx.viewport = (0, 0, LW, LH)
        setu(p_light, **common)
        v_light.render()
        t_light.build_mipmaps()
        fb_rays.use()
        ctx.viewport = (0, 0, RW, RH)
        setu(p_rays, uSunUV=sun_uv, uTime=t, uThresh=LOOK["rays_thresh"], uRaysK=LOOK["rays_k"])
        v_rays.render()
        # composición final
        fb_out.use()
        ctx.viewport = (0, 0, W, H)
        flare = 0.6 + 0.8 * ease((t - 8) / 14)
        setu(p_final, uGrainOff=(float(grng.random()), float(grng.random())))
        setu(p_final, **common, uSunUV=sun_uv, uExposure=LOOK["exposure"], uFade=fade, uFlare=flare,
             uGrad=LOOK["grad"])
        v_final.render()
        ctx.scissor = (0, sh.bar, W, H - 2 * sh.bar)
        ctx.enable(moderngl.BLEND)
        # hojas y pájaros (siluetas)
        verts = leaves.frame(t, cam, sh.F, sh.k, layers["tree_xy"], focus_d, coc_inf(focus_d)) + \
            birds.frame(t, cam, sh.F, sh.k, haze_bird)
        if verts:
            arr = np.array(verts, "f4")
            shape_vbo.orphan(arr.nbytes)
            shape_vbo.write(arr.tobytes())
            ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA
            p_shape["uFade"].value = fade
            shape_vao.render(moderngl.TRIANGLES, vertices=len(arr))
        # polen y vilanos (luz que se suma)
        pts = motes.frame(t, cam, sh.F, sh.k, focus_d, coc_inf(focus_d))
        gh_ = np.array([[sh.SUN[0] * g_[0], sh.SUN[1] * g_[0], 2 * g_[1] * H, 0.05 * flare, *g_[2], 1.0]
                        for g_ in GHOSTS], np.float32)
        pts = np.concatenate([pts, gh_])
        part_vbo.write(pts.tobytes())
        ctx.blend_func = moderngl.ONE, moderngl.ONE
        p_part["uFade"].value = fade
        setu(p_part, uSunUV=sun_uv)
        part_vao.render(moderngl.POINTS, vertices=len(pts))
        # título
        ta = ease((t - 20.5) / 2.2) * (1 - ease((t - 29.0) / 1.8))
        if ta > 0:
            ctx.blend_func = moderngl.ONE, moderngl.ONE_MINUS_SRC_ALPHA
            p_text["uA"].value = ta
            text_vao.render()
        ctx.disable(moderngl.BLEND)
        ctx.scissor = None
        if yuv:
            fb_yuv.use()
            ctx.viewport = (0, 0, W, H * 3 // 2)
            t_out.use(16)
            setu(p_yuv, tRGB=16, uRes=(float(W), float(H)))
            v_yuv.render()
            return fb_yuv.read(components=1, alignment=1)
        return fb_out.read(components=3, alignment=1)

    if args.stills:
        for s in args.stills:
            img = render_frame(s)
            Image.frombytes("RGB", (W, H), img).transpose(Image.FLIP_TOP_BOTTOM).save(
                os.path.join(ROOT, f"still_{s:05.1f}.png"))
        print(f"cielo {t_sky - T0:.2f}s  pintado {t_paint - t_sky:.2f}s  total {time.time() - T0:.2f}s")
        return

    video_tmp = os.path.join(ROOT, "estilo_mudo.mp4")
    enc = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "yuv420p", "-s", f"{W}x{H}",
                            "-r", str(FPS), "-color_range", "tv", "-colorspace", "bt709", "-i", "-",
                            "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
                            "-color_range", "tv", "-c:v", "libx264", "-preset", "ultrafast",
                            "-crf", "18", "-tune", "film", "-threads", "1", "-pix_fmt", "yuv420p", video_tmp], stdin=subprocess.PIPE)
    n = int(DUR * FPS)
    t_frames = time.time()
    for i in range(n):
        enc.stdin.write(render_frame(i / FPS, yuv=True))
    enc.stdin.close()
    enc.wait()
    t_enc = time.time()
    audio_proc.join()
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", video_tmp, "-i", audio_path, "-c:v", "copy", "-c:a", "aac",
                    "-b:a", "192k", "-shortest", "-movflags", "+faststart", args.out], check=True)
    os.remove(video_tmp)
    total = time.time() - T0
    print(f"cielo {t_sky - T0:.2f}s | pintado {t_paint - t_sky:.2f}s | fotogramas+codificación "
          f"{t_enc - t_frames:.2f}s ({(t_enc - t_frames) / n * 1000:.1f} ms/f) | TOTAL {total:.2f}s "
          f"para {DUR:.0f}s de vídeo ({total / DUR:.2f}x)")


if __name__ == "__main__":
    main()
