"""Renderiza los fotogramas con Cairo y los envía a ffmpeg.

Uso:
  python3 render.py                      # video completo -> build/video_mudo.mp4
  python3 render.py --stills 5 12.5 40   # PNGs de prueba en esos segundos
"""
import argparse
import json
import math
import subprocess
from pathlib import Path

import cairo
import numpy as np
import soundfile as sf

import scenes
from draw import W, H, clamp, ellipse, hexc, lerp, ramp, rgrad, setc, smooth, text, vgrad, vignette, wrap
from guion import SPEAKERS, TITLE, TITLE_DUR, TOTAL, build_timeline

ROOT = Path(__file__).resolve().parent
BUILD = ROOT / "build"
FPS = 30
FADE = 0.35
NAME_COLORS = {"M": "#f0c674", "A": "#8cc4f0", "J": "#f29a80"}
ROMAN = ["I", "II", "III", "IV", "V", "VI"]


def load_timeline():
    meta = json.loads((BUILD / "voz" / "lines.json").read_text())
    durs = {(m["scene"], m["idx"]): m["dur"] for m in meta}
    files = {(m["scene"], m["idx"]): m["file"] for m in meta}
    timeline, _ = build_timeline(durs)
    env = {}
    for sc in timeline:
        for ln in sc["lines"]:
            data, sr = sf.read(files[(sc["id"], ln["idx"])])
            if data.ndim > 1:
                data = data.mean(axis=1)
            hop = sr // FPS
            n = max(1, len(data) // hop)
            rms = np.sqrt(np.mean(data[: n * hop].reshape(n, hop) ** 2, axis=1))
            ref = np.percentile(rms, 90) + 1e-6
            env[id(ln)] = np.clip(rms / ref, 0, 1.2)
    return timeline, env


def make_talk(sc, env, t_abs):
    def talk(spk):
        for ln in sc["lines"]:
            if ln["spk"] == spk and ln["start"] <= t_abs < ln["end"]:
                e = env[id(ln)]
                i = min(int((t_abs - ln["start"]) * FPS), len(e) - 1)
                return float(clamp(e[i] * 0.9))
        return 0.0
    return talk


def to_local(sc):
    """Copia de la escena con tiempos de línea relativos al inicio de la escena."""
    loc = dict(sc)
    loc["lines"] = [dict(ln, start=ln["start"] - sc["start"], end=ln["end"] - sc["start"]) for ln in sc["lines"]]
    return loc


# --------------------------------------------------------------- cartelas
def covered_mirror_icon(ctx, x, y, s, a, reveal=0.0):
    ctx.save()
    ctx.translate(x, y)
    ctx.scale(s, s)
    setc(ctx, "#c9a36a", a)
    ctx.set_line_width(6)
    ellipse(ctx, 0, 0, 60, 90)
    ctx.stroke()
    setc(ctx, "#2a2230", a)
    ellipse(ctx, 0, 0, 56, 86)
    ctx.fill()
    setc(ctx, "#d6ccb8", a * (1 - reveal))
    ctx.move_to(-46, -100)
    ctx.curve_to(-20, -112, 20, -112, 46, -100)
    ctx.curve_to(70, -20, 82, 60, 78, 104)
    ctx.line_to(-78, 104)
    ctx.curve_to(-82, 60, -70, -20, -46, -100)
    ctx.fill()
    ctx.restore()


def title_card(ctx, t):
    ctx.set_source(vgrad(0, H, [(0, "#1f1913"), (1, "#0e0b09")]))
    ctx.paint()
    ctx.set_source(rgrad(W / 2, H * 0.45, 20, 700, [(0, hexc("#5a4230", 0.55)), (1, hexc("#5a4230", 0))]))
    ctx.paint()
    a = ramp(t, 0.1, 0.9) * (1 - ramp(t, TITLE_DUR - 0.45, TITLE_DUR))
    z = 1 + 0.03 * t / TITLE_DUR
    ctx.save()
    ctx.translate(W / 2, H / 2)
    ctx.scale(z, z)
    ctx.translate(-W / 2, -H / 2)
    covered_mirror_icon(ctx, W / 2, 380, 1.25, a)
    text(ctx, TITLE, W / 2, 660, 112, "#f1e4c8", alpha=a)
    text(ctx, "UN RELATO EN SEIS ESCENAS", W / 2, 735, 26, "#c9a36a", alpha=a * ramp(t, 0.6, 1.3), spacing=6)
    ctx.restore()


def end_card(ctx, t, dur):
    ctx.set_source(vgrad(0, H, [(0, "#1f1913"), (1, "#0e0b09")]))
    ctx.paint()
    a = ramp(t, 0.15, 0.9)
    covered_mirror_icon(ctx, W / 2, 400, 1.0, a * 0.9, reveal=ramp(t, 0.4, 1.6))
    text(ctx, "FIN", W / 2, 640, 110, "#f1e4c8", alpha=a, spacing=24)
    text(ctx, TITLE, W / 2, 712, 34, "#c9a36a", italic=True, alpha=a * ramp(t, 0.5, 1.1))
    setc(ctx, "#000000", ramp(t, dur - 0.5, dur))
    ctx.paint()


# --------------------------------------------------------------- superposiciones
def scene_label(ctx, sc, t):
    a = ramp(t, 0.25, 0.7) * (1 - ramp(t, 2.3, 2.8))
    if a <= 0:
        return
    x, y = 90, 110
    setc(ctx, "#000000", 0.35 * a)
    ctx.rectangle(x - 28, y - 58, 6, 92)
    ctx.fill()
    text(ctx, f"ESCENA {ROMAN[sc['id'] - 1]}", x, y - 20, 24, "#f6ead2", align="left", alpha=a, spacing=5,
         outline=("#000000", 4, 0.35))
    text(ctx, sc["name"], x, y + 28, 50, "#ffffff", italic=True, align="left", alpha=a,
         outline=("#000000", 5, 0.35))
    setc(ctx, "#f0c674", a)
    ctx.rectangle(x - 28, y - 58, 4, 92)
    ctx.fill()


def subtitles(ctx, sc_abs, t_abs):
    lines = sc_abs["lines"]
    for i, ln in enumerate(lines):
        nxt = lines[i + 1]["start"] if i + 1 < len(lines) else sc_abs["end"]
        t0, t1 = ln["start"] - 0.08, min(ln["end"] + 0.35, nxt - 0.02)
        if not (t0 <= t_abs <= t1):
            continue
        a = ramp(t_abs, t0, t0 + 0.12) * (1 - ramp(t_abs, t1 - 0.12, t1))
        ctx.set_source(vgrad(H - 260, H, [(0, hexc("#000000", 0)), (0.5, hexc("#000000", 0.45 * a)),
                                          (1, hexc("#000000", 0.6 * a))]))
        ctx.rectangle(0, H - 260, W, 260)
        ctx.fill()
        rows = wrap(ctx, ln["text"], 50, 1500)
        y = H - 70 - 60 * (len(rows) - 1)
        text(ctx, SPEAKERS[ln["spk"]]["name"].upper(), W / 2, y - 62, 24, NAME_COLORS[ln["spk"]],
             alpha=a, spacing=5, outline=("#000000", 4, 0.5))
        for r in rows:
            text(ctx, r, W / 2, y, 50, "#ffffff", alpha=a, outline=("#000000", 6, 0.55))
            y += 60


# --------------------------------------------------------------- fotograma
class Renderer:
    def __init__(self):
        self.timeline, self.env = load_timeline()
        self.local = [to_local(sc) for sc in self.timeline]
        self.vig = vignette(0.5)
        self.surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
        self.ctx = cairo.Context(self.surf)
        self.end_start = self.timeline[-1]["end"]

    def frame(self, t_abs):
        ctx = self.ctx
        ctx.set_source_rgb(0, 0, 0)
        ctx.paint()
        if t_abs < TITLE_DUR:
            title_card(ctx, t_abs)
            return self.surf
        if t_abs >= self.end_start:
            end_card(ctx, t_abs - self.end_start, TOTAL - self.end_start)
            return self.surf
        k = next(i for i, sc in enumerate(self.timeline) if sc["start"] <= t_abs < sc["end"])
        sc, loc = self.timeline[k], self.local[k]
        t = t_abs - sc["start"]
        T = sc["end"] - sc["start"]
        z0, z1, cx, cy = scenes.CAMERA[sc["set"]]
        z = lerp(z0, z1, smooth(t / T))
        ctx.save()
        ctx.translate(cx, cy)
        ctx.scale(z, z)
        ctx.translate(-cx, -cy)
        scenes.SETS[sc["set"]](ctx, t, loc, make_talk(sc, self.env, t_abs))
        ctx.restore()
        ctx.set_source_surface(self.vig, 0, 0)
        ctx.paint()
        scene_label(ctx, sc, t)
        subtitles(ctx, sc, t_abs)
        fade = max(1 - ramp(t, 0, FADE), ramp(t, T - FADE, T))
        if fade > 0:
            setc(ctx, "#000000", fade)
            ctx.paint()
        return self.surf


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stills", nargs="*", type=float)
    ap.add_argument("--out", default=str(BUILD / "video_mudo.mp4"))
    args = ap.parse_args()
    r = Renderer()
    if args.stills:
        d = BUILD / "stills"
        d.mkdir(parents=True, exist_ok=True)
        for s in args.stills:
            r.frame(s).write_to_png(str(d / f"t{s:05.2f}.png"))
            print("still", s)
        return
    n = int(round(TOTAL * FPS))
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "bgra", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
           "-pix_fmt", "yuv420p", "-movflags", "+faststart", args.out]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i in range(n):
        surf = r.frame(i / FPS)
        surf.flush()
        proc.stdin.write(bytes(surf.get_data()))
        if i % 150 == 0:
            print(f"fotograma {i}/{n}", flush=True)
    proc.stdin.close()
    proc.wait()
    print("video:", args.out)


if __name__ == "__main__":
    main()
