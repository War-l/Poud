"""Banda sonora: diálogo con acústica de cada sala, música original, ambientes, efectos y pasos.

Todo se sintetiza aquí (numpy/scipy) salvo las voces (Piper). Salida: build/audio.wav (48 kHz, estéreo).
"""
import json
import math

import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfilt, fftconvolve

import film
from guion import SCENES, TITLE_DUR, END_DUR

SR = 48000
rng = np.random.default_rng(11)


# ------------------------------------------------------------------ utilidades
def filt(x, kind, f, order=2):
    return sosfilt(butter(order, f, btype=kind, fs=SR, output="sos"), x)


def env_ar(n, a, r):
    t = np.arange(n) / SR
    return np.minimum(1, t / max(a, 1e-4)) * np.exp(-t / r)


def add(buf, sig, t0, gain=1.0, pan=0.0):
    """Suma una señal mono (o estéreo) en el instante t0 con paneo de potencia constante."""
    i0 = int(t0 * SR)
    if i0 >= len(buf) or i0 + len(sig) <= 0:
        return
    if i0 < 0:
        sig = sig[-i0:]
        i0 = 0
    sig = sig[: len(buf) - i0]
    if sig.ndim == 1:
        th = (pan + 1) * math.pi / 4
        buf[i0:i0 + len(sig), 0] += sig * gain * math.cos(th)
        buf[i0:i0 + len(sig), 1] += sig * gain * math.sin(th)
    else:
        buf[i0:i0 + len(sig)] += sig * gain


def noise(n):
    return rng.standard_normal(n)


def fade(x, a, b):
    na, nb = max(1, int(a * SR)), max(1, int(b * SR))
    x = x.copy()
    x[:na] *= np.linspace(0, 1, na)[:, None] if x.ndim > 1 else np.linspace(0, 1, na)
    x[-nb:] *= np.linspace(1, 0, nb)[:, None] if x.ndim > 1 else np.linspace(1, 0, nb)
    return x


def impulse_response(rt60, predelay=0.01, bright=6000, er=0.4, seed=0):
    """Respuesta de impulso sintética: reflexiones tempranas + cola exponencial decorrelada en estéreo."""
    r = np.random.default_rng(seed)
    n = int((rt60 * 1.2 + predelay) * SR)
    t = np.arange(n) / SR
    out = np.zeros((n, 2))
    decay = np.exp(-6.91 * t / rt60)
    for c in range(2):
        tail = r.standard_normal(n) * decay
        tail = filt(tail, "lowpass", bright)
        # la absorción del aire apaga antes los agudos: segundo filtro que cierra con el tiempo
        tail = tail * (1 - 0.5 * t / max(t[-1], 1e-3)) + filt(tail, "lowpass", bright * 0.4) * 0.5 * t / max(t[-1], 1e-3)
        ir = np.zeros(n)
        pd = int(predelay * SR)
        ir[pd:] = tail[: n - pd]
        for k in range(8):
            d = int((predelay + r.uniform(0.003, 0.04)) * SR)
            if d < n:
                ir[d] += r.uniform(-1, 1) * er
        out[:, c] = ir
    return out / np.sqrt((out ** 2).sum() / 2)


def reverb(x, ir, wet):
    y = np.zeros((len(x) + len(ir) - 1, 2))
    for c in range(2):
        y[:, c] = fftconvolve(x, ir[:, c])
    dry = np.zeros_like(y)
    dry[: len(x), 0] = x
    dry[: len(x), 1] = x
    return dry * (1 - wet * 0.3) + y * wet * 0.35


ROOMS = {  # rt60, wet, brillo
    "garden_morning": (0.35, 0.12, 7000), "garden_evening": (0.4, 0.14, 6000), "court": (1.7, 0.5, 5000),
    "home": (0.45, 0.18, 6000), "office_day": (0.5, 0.2, 6000), "office_night": (0.5, 0.2, 5500),
    "office_memory": (0.5, 0.2, 6000), "library": (0.7, 0.24, 4500), "plaza_steps": (0.9, 0.18, 6500),
    "plaza_sunset": (0.8, 0.15, 6500), "plaza_memory": (1.4, 0.45, 4000),
}


# ------------------------------------------------------------------ instrumentos
NOTE = {n: i for i, n in enumerate(["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"])}
FLAT = {"Db": "C#", "Eb": "D#", "Gb": "F#", "Ab": "G#", "Bb": "A#"}


def midi(name):
    """'D4' -> 62."""
    n, o = name[:-1], int(name[-1])
    n = FLAT.get(n, n)
    return 12 * (o + 1) + NOTE[n]


def hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def piano(m, dur, vel=0.7):
    """Piano: parciales con inharmonicidad de cuerda rígida (B), caída más rápida en agudos, martillo."""
    f0 = hz(m)
    n = int((dur + 2.5) * SR)
    t = np.arange(n) / SR
    B = 0.0004 * (f0 / 261.6) ** 0.5
    out = np.zeros(n)
    for k in range(1, 14):
        fk = k * f0 * math.sqrt(1 + B * k * k)
        if fk > 16000:
            break
        amp = (1.0 / k ** 1.25) * (0.6 + 0.4 * vel) ** (k * 0.4)
        tau = 2.8 * (261.6 / f0) ** 0.6 / (1 + 0.35 * k)
        det = 1 + (rng.uniform(-1, 1) * 0.0004)
        out += amp * np.sin(2 * math.pi * fk * det * t + rng.uniform(0, 6.28)) * np.exp(-t / tau)
    # liberación de la tecla
    rel = np.ones(n)
    ir = int(dur * SR)
    if ir < n:
        rel[ir:] = np.exp(-(t[ir:] - dur) / 0.25)
    hammer = filt(noise(int(0.02 * SR)), "bandpass", [800, 4000]) * np.linspace(1, 0, int(0.02 * SR)) * 0.08
    out[: len(hammer)] += hammer
    out *= rel * np.minimum(1, t / 0.002)
    return out * vel * 0.35


def strings(ms, dur, att=1.5, rel=1.8, bright=1800):
    """Sección de cuerda: dientes de sierra desafinados (ensemble) con vibrato lento, filtrados."""
    n = int((dur + rel) * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    for m in ms:
        for d in (-0.08, 0.0, 0.07, 0.13):
            f = hz(m) * 2 ** (d / 12)
            vib = 1 + 0.003 * np.sin(2 * math.pi * (5.1 + d) * t + d * 10)
            ph = np.cumsum(f * vib) / SR
            out += 2 * (ph % 1.0) - 1
    out = filt(out, "lowpass", bright, 2)
    e = np.minimum(1, t / att)
    ir = int(dur * SR)
    e[ir:] *= np.exp(-(t[ir:] - dur) / (rel / 3))
    return out * e / (len(ms) * 4) * 0.5


def bell(m, dur=2.5, vel=0.5):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = hz(m)
    s = sum(a * np.sin(2 * math.pi * f * r * t) * np.exp(-t / (dur * d))
            for r, a, d in ((1, 1, 0.45), (2.76, 0.4, 0.2), (5.4, 0.2, 0.1), (8.93, 0.1, 0.06)))
    return s * vel * 0.3 * np.minimum(1, t / 0.002)


CHORDS = {
    "Dm": ["D3", "F3", "A3", "D4"], "Bb": ["A#2", "D3", "F3", "A#3"], "F": ["F2", "C3", "F3", "A3"],
    "C": ["C3", "E3", "G3", "C4"], "Gm": ["G2", "D3", "G3", "A#3"], "A": ["A2", "E3", "A3", "C#4"],
    "Eb": ["D#3", "G3", "A#3", "D#4"], "D": ["D3", "F#3", "A3", "D4"], "G": ["G2", "D3", "G3", "B3"],
    "Bm": ["B2", "F#3", "B3", "D4"], "Asus": ["A2", "D3", "E3", "A3"], "Am": ["A2", "E3", "A3", "C4"],
    "Dsus": ["D3", "G3", "A3", "D4"],
}

# por escena: (acordes, segundos por acorde, estilo)
SCORE = {
    0: (["Dm", "Bb", "F", "Asus"], 1.5, "piano_motif"),
    1: (["Dm", "Bb", "F", "C"], 3.2, "arp"),
    2: (["Dm", "Gm", "Dm", "A"], 3.7, "drone"),
    3: (["Bb", "F", "Gm", "Dm"], 4.1, "arp_soft"),
    4: (["Dm", "Am", "Bb", "A"], 3.8, "pulse"),
    5: (["Gm", "Eb", "Bb", "F"], 4.4, "strings"),
    6: (["Dm", "Bb", "Gm", "A"], 3.2, "sparse"),
    7: (["F", "C", "Bb", "F"], 3.2, "bells"),
    8: (["Dm", "Gm", "A", "Dm"], 4.0, "drone"),
    9: (["Dm", "Bb", "F", "Asus"], 3.2, "arp_soft"),
    10: (["Bb", "F", "G", "D"], 4.6, "resolve"),
    11: (["D"], 6.0, "final"),
}


def music(total, tl):
    buf = np.zeros((int(total * SR) + SR * 4, 2))
    segs = [(0, 0.0, TITLE_DUR)] + [(sc["id"], sc["start"], sc["end"]) for sc in tl] + [(11, tl[-1]["end"], total)]
    for sid, t0, t1 in segs:
        chords, cdur, style = SCORE[sid]
        t = t0
        k = 0
        while t < t1 - 0.2:
            ch = CHORDS[chords[k % len(chords)]]
            ms = [midi(n) for n in ch]
            d = min(cdur, t1 - t)
            if style in ("arp", "arp_soft", "piano_motif", "resolve", "final", "pulse", "sparse"):
                step = {"arp": cdur / 6, "arp_soft": cdur / 4, "piano_motif": cdur / 3, "resolve": cdur / 6,
                        "final": 0.6, "pulse": cdur / 8, "sparse": cdur / 2}[style]
                pat = {"arp": [0, 1, 2, 3, 2, 1], "arp_soft": [0, 2, 1, 3], "piano_motif": [3, 2, 1],
                       "resolve": [0, 1, 2, 3, 2, 1], "final": [0, 1, 2, 3, 3], "pulse": [1] * 8,
                       "sparse": [0, 3]}[style]
                vel = {"arp": 0.5, "arp_soft": 0.42, "piano_motif": 0.5, "resolve": 0.5, "final": 0.55,
                       "pulse": 0.3, "sparse": 0.42}[style]
                for i, p in enumerate(pat):
                    tt = t + i * step
                    if tt >= t1 - 0.1 or tt >= t + d:
                        break
                    m = ms[p] + (12 if style in ("piano_motif", "sparse") else 0)
                    add(buf, piano(m, step * 1.6, vel * (1.0 if i == 0 else 0.85)), tt, 1.0, pan=(p - 1.5) * 0.25)
                add(buf, piano(ms[0] - 12, d, vel * 0.8), t, 0.8, pan=-0.3)
            if style in ("drone", "strings", "resolve", "final", "arp_soft", "bells", "sparse"):
                g = {"drone": 0.9, "strings": 1.0, "resolve": 0.7, "final": 0.9, "arp_soft": 0.35, "bells": 0.4,
                     "sparse": 0.4}[style]
                lo = [ms[0] - 12, ms[0]] if style == "drone" else ms[1:]
                st = strings(lo, d, att=min(1.5, d * 0.4), rel=1.5, bright=1400 if style == "drone" else 2200)
                add(buf, st, t, g * 0.8, pan=-0.35)
                add(buf, st, t + 0.013, g * 0.8, pan=0.35)
            if style == "bells":
                for i, p in enumerate([3, 2, 1, 2]):
                    add(buf, bell(ms[p] + 24, 2.5, 0.35), t + i * cdur / 4, 1.0, pan=0.3 * (i % 2 * 2 - 1))
            t += cdur
            k += 1
    return buf


# ------------------------------------------------------------------ efectos y ambientes
def chirp_bird(dur=0.12, f0=3200, f1=5200):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = f0 + (f1 - f0) * np.sin(np.linspace(0, math.pi, n))
    return np.sin(2 * math.pi * np.cumsum(f) / SR) * np.sin(np.linspace(0, math.pi, n)) ** 2


def bed(kind, dur):
    n = int(dur * SR)
    t = np.arange(n) / SR
    if kind == "room":
        return filt(noise(n), "lowpass", 250) * 0.2
    if kind == "wind":
        mod = 0.6 + 0.4 * np.abs(filt(noise(n), "lowpass", 0.6)) * 4
        return filt(noise(n), "bandpass", [150, 1200]) * mod * 0.25
    if kind == "crowd":
        x = filt(noise(n), "bandpass", [200, 1000])
        return x * (0.6 + 0.4 * np.sin(2 * math.pi * 0.21 * t) * np.sin(2 * math.pi * 0.67 * t + 1)) * 0.4
    if kind == "rain":
        x = filt(noise(n), "bandpass", [700, 8000]) * 0.35
        drops = np.zeros(n)
        idx = rng.integers(0, n, int(dur * 220))
        drops[idx] = rng.uniform(0.2, 1.0, len(idx))
        return x + filt(drops, "bandpass", [1500, 6000]) * 0.8
    if kind == "fire":
        x = filt(noise(n), "lowpass", 600) * 0.3
        cr = np.zeros(n)
        idx = rng.integers(0, n, int(dur * 25))
        cr[idx] = rng.uniform(0.3, 1.0, len(idx))
        return x + filt(cr, "highpass", 1500) * 1.2
    if kind == "water":
        return filt(noise(n), "bandpass", [600, 7000]) * (0.8 + 0.2 * np.abs(filt(noise(n), "lowpass", 6))) * 0.4
    if kind == "crickets":
        return np.sin(2 * math.pi * 4400 * t) * (np.sin(2 * math.pi * 30 * t) > 0.4) * \
            (np.sin(2 * math.pi * 0.8 * t) > -0.1) * 0.05
    if kind == "traffic":
        return filt(noise(n), "lowpass", 300) * (0.7 + 0.3 * np.sin(2 * math.pi * 0.07 * t)) * 0.35
    if kind == "clock":
        x = np.zeros(n)
        for k in range(int(dur)):
            i = int(k * SR)
            m = min(400, n - i)
            if m > 0:
                x[i:i + m] += filt(noise(400), "bandpass", [2000, 6000])[:m] * np.exp(-np.arange(m) / 60) * 0.6
        return x
    return np.zeros(n)


def footstep(surface):
    n = int(0.18 * SR)
    t = np.arange(n) / SR
    if surface == "gravel":
        x = filt(noise(n), "bandpass", [800, 5000]) * np.exp(-t / 0.05)
    elif surface == "wood":
        x = filt(noise(n), "bandpass", [150, 1500]) * np.exp(-t / 0.025) + np.sin(2 * math.pi * 110 * t) * np.exp(-t / 0.03) * 0.5
    else:
        x = filt(noise(n), "bandpass", [400, 4000]) * np.exp(-t / 0.02) + np.sin(2 * math.pi * 90 * t) * np.exp(-t / 0.02) * 0.4
    return x * 0.35


def thud(f=80, dur=0.3):
    n = int(dur * SR)
    t = np.arange(n) / SR
    return np.sin(2 * math.pi * f * t * (1 + np.exp(-t * 30))) * np.exp(-t / 0.07) + \
        filt(noise(n), "lowpass", 800) * np.exp(-t / 0.03) * 0.4


def snip():
    n = int(0.08 * SR)
    t = np.arange(n) / SR
    return (filt(noise(n), "highpass", 3000) * np.exp(-t / 0.008) + np.sin(2 * math.pi * 3800 * t) * np.exp(-t / 0.02) * 0.4)


def shatter():
    n = int(1.6 * SR)
    t = np.arange(n) / SR
    x = filt(noise(n), "highpass", 2500) * np.exp(-t / 0.12)
    for k in range(40):
        f = rng.uniform(3000, 9000)
        t0 = rng.uniform(0, 1.1)
        i = int(t0 * SR)
        m = int(0.15 * SR)
        if i + m < n:
            x[i:i + m] += np.sin(2 * math.pi * f * np.arange(m) / SR) * np.exp(-np.arange(m) / SR / 0.03) * rng.uniform(0.1, 0.4)
    return x * 0.6


def paper():
    n = int(0.35 * SR)
    t = np.arange(n) / SR
    return filt(noise(n), "bandpass", [1500, 7000]) * np.exp(-t / 0.1) * (0.5 + 0.5 * np.sin(t * 90)) * 0.4


AMB = {
    "garden_morning": [("wind", 0.08), ("birds", 1.0)], "garden_evening": [("wind", 0.06), ("crickets", 1.0)],
    "court": [("room", 0.25), ("crowd", 0.03)], "home": [("room", 0.2), ("clock", 0.12)],
    "office_day": [("room", 0.2), ("traffic", 0.12), ("clock", 0.08)],
    "office_night": [("rain", 0.22), ("room", 0.15)], "office_memory": [("room", 0.2), ("clock", 0.08)],
    "library": [("fire", 0.22), ("clock", 0.1)], "plaza_steps": [("crowd", 0.12), ("wind", 0.12)],
    "plaza_sunset": [("water", 0.1), ("crowd", 0.05), ("wind", 0.04)], "plaza_memory": [("birds", 0.8), ("wind", 0.05)],
}
SURF = {"garden_morning": "gravel", "garden_evening": "gravel", "plaza_steps": "stone", "plaza_sunset": "stone",
        "plaza_memory": "stone"}


def scene_sfx(buf, key, t0, t1, actors, cam_for, tlocal0):
    dur = t1 - t0
    for kind, g in AMB.get(key, []):
        if kind == "birds":
            for k in range(int(dur * 0.9)):
                tt = t0 + rng.uniform(0, dur)
                for j in range(rng.integers(2, 5)):
                    add(buf, chirp_bird(0.08 + rng.uniform(0, 0.06), rng.uniform(2500, 3800), rng.uniform(4200, 6500)),
                        tt + j * 0.11, 0.05 * g, pan=rng.uniform(-0.8, 0.8))
            continue
        x = bed(kind, dur)
        x = fade(x, 0.3, 0.3)
        add(buf, x, t0, g * 0.6, pan=-0.2)
        add(buf, np.roll(x, SR // 7), t0, g * 0.6, pan=0.2)
    # pasos: cuando la fase de marcha cruza múltiplos de pi
    surf = SURF.get(key, "wood")
    for a in actors:
        if not hasattr(a, "fig") or a.fig is None:
            continue
        prev = None
        for i in range(int(dur * 100)):
            tt = tlocal0 + i / 100
            try:
                if not a.visible(tt):
                    continue
                ph_ = a.at(tt)[4].get("walk")
            except Exception:
                ph_ = None
            if ph_ is not None and prev is not None:
                if math.floor(ph_ / math.pi) != math.floor(prev / math.pi):
                    X, Y, Z = a.at(tt)[:3]
                    cv = cam_for(tt)
                    d = max(Z - cv["cam"][2], 0.5)
                    pan = max(-1, min(1, (X - cv["cam"][0]) / (d * 0.5)))
                    add(buf, footstep(surf), t0 + i / 100, min(1.0, 2.5 / d) * 0.5, pan=pan)
            prev = ph_


def main():
    tl, total, envs = film.load_timeline()
    W, H = 2560, 1440
    defs = film.scene_defs(W, H, tl, envs)
    meta = {(m["scene"], m["idx"]): m for m in json.loads((film.ROOT / "build" / "voz" / "lines.json").read_text())}
    N = int(total * SR) + SR * 4
    dlg = np.zeros((N, 2))
    sfx = np.zeros((N, 2))
    vmask = np.zeros(N)

    def cam_fn(sd):
        return film.Shots(sd.shots, W, H)

    # -- título: forma parte del decorado del jardín
    sd1 = defs[1]
    scene_sfx(sfx, "garden_morning", 0.0, TITLE_DUR, sd1.actors, cam_fn(sd1), -TITLE_DUR)
    for sc in tl:
        sd = defs[sc["id"]]
        key = sd.set_key
        dur = sc["end"] - sc["start"]
        cam = cam_fn(sd)
        # acústica de la sala para el diálogo
        rt, wet, br = ROOMS[key]
        ir = impulse_response(rt, bright=br, seed=sc["id"])
        for ln in sc["lines"]:
            x, sr = sf.read(meta[(sc["id"], ln["idx"])]["file"])
            assert sr == SR
            tl_mid = (ln["start"] + ln["end"]) / 2 - sc["start"]
            # paneo según la posición del personaje que habla en el plano activo
            pan = 0.0
            name = {"AN": "andres", "EL": "elena", "TO": "tomas", "SA": "samuel", "JA": "jardinero"}.get(ln["spk"])
            cv = cam(tl_mid)
            spk_actor = None
            for a in sd.actors:
                fig = getattr(a, "fig", None)
                if fig is not None and name and any(fig.st == film.CAST[k] for k in film.CAST if k.startswith(name)):
                    spk_actor = a
                    break
            if spk_actor is not None:
                X, Y, Z = spk_actor.at(tl_mid)[:3]
                d = max(Z - cv["cam"][2], 0.5)
                pan = max(-0.6, min(0.6, (X - cv["cam"][0]) / (d * 0.6)))
            y = reverb(x, ir, wet)
            th = (pan + 1) * math.pi / 4
            y[:, 0] *= math.cos(th) * 1.41
            y[:, 1] *= math.sin(th) * 1.41
            add(dlg, y, ln["start"], 0.9)
            vmask[int(ln["start"] * SR):int(ln["end"] * SR)] = 1
        scene_sfx(sfx, key, sc["start"], sc["end"], sd.actors, cam, 0.0)
        if sd.switch:
            (ta, tb), fsd = sd.switch
            scene_sfx(sfx, fsd.set_key, sc["start"] + ta, sc["start"] + tb, fsd.actors, cam_fn(fsd), ta)
        # efectos puntuales
        s0 = sc["start"]
        if sc["id"] == 1:
            add(sfx, snip(), s0 + 1.25, 0.5, 0.2)
            add(sfx, snip(), s0 + 1.5, 0.5, 0.2)
            add(sfx, snip(), s0 + 1.7, 0.7, 0.2)
            add(sfx, filt(noise(int(0.5 * SR)), "bandpass", [600, 4000]) * np.linspace(1, 0, int(0.5 * SR)) * 0.3,
                s0 + 1.75, 0.6, 0.25)
            add(sfx, thud(140, 0.25), s0 + 2.3, 0.25, 0.25)
        if sc["id"] == 2:
            add(sfx, paper(), s0 + sc["lines"][2]["end"] - s0 + 0.7, 0.8, 0.2)
            add(sfx, thud(120, 0.2), s0 + sc["lines"][2]["end"] - s0 + 1.2, 0.35, 0.2)
        if sc["id"] == 6:
            for k in range(2):
                add(sfx, filt(noise(int(3 * SR)), "lowpass", 120) * env_ar(int(3 * SR), 0.3, 0.9) * 0.8,
                    s0 + 4.0 + k * 5.2, 0.3)
            add(sfx, paper(), sc["lines"][3]["end"] + 0.5, 0.6, 0.2)
        if sc["id"] == 7:
            ta, tb = sd.switch[0]
            t_kick = sc["start"] + ta + 0.6
            add(sfx, thud(180, 0.12), t_kick, 0.4, -0.2)
            add(sfx, shatter(), t_kick + 0.55, 0.7, 0.35)
            for tt in (ta, tb):  # destellos de memoria: barrido
                sw = filt(noise(int(1.2 * SR)), "bandpass", [2000, 9000]) * np.sin(np.linspace(0, math.pi, int(1.2 * SR))) ** 2
                add(sfx, sw, sc["start"] + tt - 0.6, 0.12)
        if sc["id"] == 10:
            # campanas de iglesia al final
            for k in range(3):
                add(sfx, bell(midi("D3"), 5.0, 0.6) + bell(midi("A3"), 5.0, 0.3), sc["end"] - 4.5 + k * 2.0, 0.5, -0.4)

    mus = music(total, tl)[:N]
    # la música baja bajo el diálogo (con transición suave)
    duck = filt(vmask, "lowpass", 2.0)
    mg = 0.32 * (1 - 0.5 * np.clip(duck, 0, 1))
    mix = dlg + sfx * 0.9 + mus * mg[:, None]
    mix = mix[: int(total * SR)]
    mix = fade(mix, 0.5, 2.5)
    mix /= np.max(np.abs(mix)) + 1e-9
    mix *= 0.9
    out = film.ROOT / "build" / "audio_raw.wav"
    sf.write(out, mix.astype(np.float32), SR)
    print("audio:", out, f"{len(mix) / SR:.2f}s")


if __name__ == "__main__":
    main()
