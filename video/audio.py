"""Banda sonora: voces + música sintetizada + ambientes + efectos -> build/audio.wav."""
import math

import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfilt

import scenes
from guion import TITLE_DUR, TOTAL
from render import BUILD, load_timeline

SR = 44100
N = int(TOTAL * SR)
rng = np.random.default_rng(5)


def note(n):
    """Frecuencia de una nota MIDI."""
    return 440.0 * 2 ** ((n - 69) / 12)


def filt(x, kind, f):
    sos = butter(2, f, btype=kind, fs=SR, output="sos")
    return sosfilt(sos, x)


def env_ad(n, attack, decay):
    t = np.arange(n) / SR
    return np.minimum(1, t / max(attack, 1e-4)) * np.exp(-t / decay)


def add(buf, sig, t0, gain=1.0):
    i0 = int(t0 * SR)
    if i0 >= len(buf):
        return
    sig = sig[: len(buf) - i0]
    buf[i0:i0 + len(sig)] += gain * sig


# ------------------------------------------------------------------ música
CHORDS = [  # (bajo, notas) en MIDI: Am F C G | Am Dm F E
    (45, [57, 60, 64]), (41, [57, 60, 65]), (48, [55, 60, 64]), (43, [55, 59, 62]),
    (45, [57, 60, 64]), (38, [57, 62, 65]), (41, [57, 60, 65]), (40, [56, 59, 64]),
]


def pad_tone(f, n):
    t = np.arange(n) / SR
    out = np.zeros(n)
    for det in (-0.12, 0.0, 0.12):  # coro suave
        ff = f * 2 ** (det / 12)
        lfo = 1 + 0.002 * np.sin(2 * math.pi * 0.3 * t + det * 10)
        ph = 2 * math.pi * ff * np.cumsum(lfo) / SR
        out += np.sin(ph) + 0.25 * np.sin(2 * ph) + 0.08 * np.sin(3 * ph)
    return out / 3


def music():
    buf = np.zeros(N)
    dur = 3.75
    xf = 1.2
    k = 0
    t0 = 0.0
    while t0 < TOTAL:
        bass, notes = CHORDS[k % len(CHORDS)]
        if TOTAL - t0 < dur + 0.5:  # acorde final: La menor
            bass, notes = 45, [57, 60, 64, 69]
            seg = int((TOTAL - t0) * SR)
        else:
            seg = int((dur + xf) * SR)
        sig = 0.55 * pad_tone(note(bass), seg) + sum(pad_tone(note(n_), seg) for n_ in notes) * 0.32
        e = np.ones(seg)
        a = int(xf * SR)
        e[:a] = np.linspace(0, 1, a) ** 1.5
        e[-a:] *= np.linspace(1, 0, a) ** 1.5
        add(buf, sig * e, t0)
        # caja de música: dos notas del acorde una octava arriba
        for j, off in enumerate((0.0, 1.875)):
            if t0 + off < TOTAL - 1.0 and t0 > 1.0:
                m = notes[(k + j) % len(notes)] + 12
                n_ = int(2.5 * SR)
                tt = np.arange(n_) / SR
                bell = (np.sin(2 * math.pi * note(m) * tt) + 0.3 * np.sin(2 * math.pi * note(m) * 2.01 * tt)
                        + 0.1 * np.sin(2 * math.pi * note(m) * 3.98 * tt)) * env_ad(n_, 0.005, 0.7)
                add(buf, bell, t0 + off, 0.22)
        t0 += dur
        k += 1
    buf = filt(buf, "lowpass", 2600)
    return buf / (np.max(np.abs(buf)) + 1e-9)


# ------------------------------------------------------------------ efectos
def noise(n):
    return rng.standard_normal(n)


def clink(freq):
    n = int(0.35 * SR)
    t = np.arange(n) / SR
    s = sum(np.sin(2 * math.pi * freq * r * t) * w for r, w in ((1, 1), (2.76, 0.5), (5.4, 0.25), (8.9, 0.12)))
    return s * env_ad(n, 0.001, 0.06)


def whoosh(dur, f0, f1):
    n = int(dur * SR)
    x = noise(n)
    out = np.zeros(n)
    blk = 1024
    for i in range(0, n, blk):
        u = i / n
        f = f0 + (f1 - f0) * u
        seg = filt(x[i:i + blk], "bandpass", [f * 0.7, f * 1.3])
        out[i:i + blk] = seg
    e = np.sin(np.linspace(0, math.pi, n)) ** 2
    return out * e


def thump(f=70, dur=0.35):
    n = int(dur * SR)
    t = np.arange(n) / SR
    fr = f * (1 + 1.5 * np.exp(-t * 30))
    return np.sin(2 * math.pi * np.cumsum(fr) / SR) * env_ad(n, 0.002, 0.08) + 0.3 * filt(noise(n), "lowpass", 900) * env_ad(n, 0.001, 0.03)


def bed(kind, dur):
    n = int(dur * SR)
    t = np.arange(n) / SR
    if kind == "crowd":
        x = filt(noise(n), "bandpass", [180, 900])
        mod = 0.6 + 0.4 * np.sin(2 * math.pi * 0.23 * t) * np.sin(2 * math.pi * 0.71 * t + 1)
        return x * mod * 0.5
    if kind == "water":
        x = filt(noise(n), "bandpass", [900, 6000])
        mod = 0.75 + 0.25 * np.abs(filt(noise(n), "lowpass", 8))
        return x * mod * 0.6
    if kind == "room":
        return filt(noise(n), "lowpass", 300) * 0.25
    if kind == "night":
        x = filt(noise(n), "lowpass", 400) * 0.3  # viento
        cr = np.sin(2 * math.pi * 4300 * t) * (np.sin(2 * math.pi * 28 * t) > 0.3) * \
            (np.sin(2 * math.pi * 0.9 * t) > 0.2) * 0.05  # grillos
        return x + cr
    return np.zeros(n)


def bird(t0, buf):
    n = int(0.12 * SR)
    t = np.arange(n) / SR
    for k in range(3):
        f = 3200 + 1400 * np.sin(np.linspace(0, math.pi, n))
        s = np.sin(2 * math.pi * np.cumsum(f) / SR) * np.sin(np.linspace(0, math.pi, n))
        add(buf, s, t0 + k * 0.16, 0.05)


def fade(x, a, b):
    na, nb = int(a * SR), int(b * SR)
    x[:na] *= np.linspace(0, 1, na)
    x[-nb:] *= np.linspace(1, 0, nb)
    return x


def main():
    timeline, _ = load_timeline()
    voice = np.zeros(N)
    vmask = np.zeros(N)
    sfx = np.zeros(N)
    meta_files = {}
    import json
    for m in json.loads((BUILD / "voz" / "lines.json").read_text()):
        meta_files[(m["scene"], m["idx"])] = m["file"]

    for sc in timeline:
        s0, s1 = sc["start"], sc["end"]
        dur = s1 - s0
        for ln in sc["lines"]:
            data, sr = sf.read(meta_files[(sc["id"], ln["idx"])])
            assert sr == SR
            add(voice, data, ln["start"])
            i0, i1 = int(ln["start"] * SR), int(ln["end"] * SR)
            vmask[i0:i1] = 1
        # ambientes por decorado
        amb = {"coins": ("crowd", 0.10), "beggar": ("crowd", 0.12), "fountain": ("water", 0.07),
               "mirror": ("room", 0.06), "sit": ("crowd", 0.03), "dusk": ("night", 0.10)}[sc["set"]]
        add(sfx, fade(bed(amb[0], dur), 0.4, 0.4), s0, amb[1])
        if sc["set"] == "fountain":
            add(sfx, fade(bed("crowd", dur), 0.4, 0.4), s0, 0.05)
        if sc["set"] == "coins":
            # monedas: un tintineo por cada bote
            for c in scenes.COINS:
                path = c["path"]
                for i in range(2, len(path)):
                    vy1 = path[i - 1][1] - path[i - 2][1]
                    vy2 = path[i][1] - path[i - 1][1]
                    if vy1 > 0.5 and vy2 <= 0:
                        tb = scenes.DROP + i / 120
                        add(sfx, clink(rng.uniform(2600, 4800)), s0 + tb, 0.10 * min(1, vy1 / 4))
            add(sfx, thump(110, 0.25), s0 + scenes.DROP + 0.2, 0.25)  # bolsa
            for c in scenes.COINS[::3]:
                add(sfx, clink(rng.uniform(3500, 5000)), s0 + c["pick"], 0.03)
        if sc["set"] == "mirror":
            add(sfx, whoosh(1.0, 500, 2200), s0 + 0.4, 0.35)
        if sc["set"] == "sit":
            for tb in (0.8, 4.6, 7.4):
                bird(s0 + tb, sfx)
        if sc["set"] == "dusk":
            trip = sc["lines"][-1]["end"] - s0 + 0.25
            add(sfx, thump(60, 0.4), s0 + trip + 0.3, 0.45)
            for k in range(4):
                add(sfx, thump(150 + 40 * k, 0.2), s0 + trip + 0.4 + 0.1 * k, 0.18)

    # cartela inicial: campana suave
    n_ = int(4 * SR)
    tt = np.arange(n_) / SR
    for m, g in ((57, 1), (64, 0.6), (69, 0.4)):
        add(sfx, np.sin(2 * math.pi * note(m) * tt) * env_ad(n_, 0.01, 1.4), 0.25, 0.07 * g)

    # música con ducking bajo la voz
    mus = music()
    duck = filt(vmask, "lowpass", 3.0)
    mus_gain = 0.20 * (1 - 0.55 * np.clip(duck, 0, 1))
    mix = voice * 0.95 + mus * mus_gain + sfx
    mix = fade(mix, 0.05, 1.2)
    peak = np.max(np.abs(mix))
    mix = mix / peak * 0.89
    stereo = np.stack([mix, mix], axis=1)
    out = BUILD / "audio.wav"
    sf.write(out, stereo, SR)
    print("audio:", out)


if __name__ == "__main__":
    main()
