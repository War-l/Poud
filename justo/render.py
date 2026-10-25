"""Renderiza la película completa (o fotogramas sueltos) con el motor GPU.

  python3 render.py                       # película completa -> build/video.mp4 (2560x1440, 24 fps)
  python3 render.py --res 1280x720        # versión de prueba
  python3 render.py --stills 10 25.5      # PNG de comprobación
  python3 render.py --from 40 --to 60     # tramo
"""
import argparse
import math
import subprocess
import time
from pathlib import Path

import cairo
import numpy as np

import film
from engine import frame as fr
from engine.gl import Engine
from engine.paint import setc
from guion import SPEAKERS, TITLE, TITLE_DUR, END_DUR

ROOT = Path(__file__).resolve().parent
BUILD = ROOT / "build"
FPS = 24
ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"]
NAME_COL = {"AN": (0.86, 0.74, 0.52), "EL": (0.62, 0.82, 0.78), "TO": (0.74, 0.8, 0.62), "SA": (0.86, 0.78, 0.68),
            "JA": (0.8, 0.84, 0.6), "CI": (0.78, 0.76, 0.82)}
ASPECT = 2.39


def smooth(a, b, x):
    if b == a:
        return 1.0 if x >= b else 0.0
    u = min(1.0, max(0.0, (x - a) / (b - a)))
    return u * u * (3 - 2 * u)


def text(ctx, s, x, y, size, rgb, a=1.0, italic=False, bold=False, spacing=0.0, align="c", family="EB Garamond",
         shadow=0.0):
    ctx.select_font_face(family, cairo.FONT_SLANT_ITALIC if italic else cairo.FONT_SLANT_NORMAL,
                         cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL)
    ctx.set_font_size(size)
    adv = [ctx.text_extents(ch).x_advance + spacing for ch in s]
    w = sum(adv) - spacing if s else 0
    x0 = x - w / 2 if align == "c" else (x - w if align == "r" else x)
    for pass_ in ((1, 0) if shadow else (0,)):
        cx = x0
        for ch, ad in zip(s, adv):
            if pass_ == 1:
                ctx.move_to(cx + size * 0.03, y + size * 0.04)
                ctx.set_source_rgba(0, 0, 0, a * shadow)
            else:
                ctx.move_to(cx, y)
                ctx.set_source_rgba(*rgb, a)
            ctx.show_text(ch)
            cx += ad
    return w


def wrap(ctx, s, size, maxw, italic=False):
    ctx.select_font_face("EB Garamond", cairo.FONT_SLANT_ITALIC if italic else cairo.FONT_SLANT_NORMAL,
                         cairo.FONT_WEIGHT_NORMAL)
    ctx.set_font_size(size)
    out, cur = [], ""
    for w in s.split():
        t = (cur + " " + w).strip()
        if ctx.text_extents(t).x_advance > maxw and cur:
            out.append(cur)
            cur = w
        else:
            cur = t
    if cur:
        out.append(cur)
    return out


class Film:
    def __init__(self, W, H):
        self.W, self.H = W, H
        self.eng = Engine(W, H)
        self.tl, self.total, self.envs = film.load_timeline()
        self.defs = film.scene_defs(W, H, self.tl, self.envs)
        self.sets = {}
        self.bar = int(round((H - W / ASPECT) / 2))

    def get_set(self, sd):
        if sd.set_key not in self.sets:
            t0 = time.time()
            self.sets[sd.set_key] = sd.set_factory(self.eng)
            print(f"  decorado {sd.set_key}: {time.time() - t0:.1f}s", flush=True)
        return self.sets[sd.set_key]

    def keep_only(self, keys):
        for k in list(self.sets):
            if k not in keys:
                self.sets[k].release()
                del self.sets[k]

    def segment(self, t_abs):
        if t_abs < TITLE_DUR:
            return "title", self.tl[0], t_abs - self.tl[0]["start"]
        for sc in self.tl:
            if sc["start"] <= t_abs < sc["end"]:
                return "scene", sc, t_abs - sc["start"]
        return "end", None, t_abs - self.tl[-1]["end"]

    # --------------------------------------------------------- superposición
    def overlay(self, kind, sc, t, t_abs):
        W, H, bar = self.W, self.H, self.bar
        k = W / 2560
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
        ctx = cairo.Context(surf)
        ctx.set_antialias(cairo.ANTIALIAS_BEST)
        # bandas de formato panorámico 2,39:1
        ctx.set_source_rgba(0, 0, 0, 1)
        ctx.rectangle(0, 0, W, bar)
        ctx.rectangle(0, H - bar, W, bar)
        ctx.fill()
        if kind == "title":
            a = smooth(1.4, 2.6, t_abs) * (1 - smooth(TITLE_DUR - 1.0, TITLE_DUR - 0.2, t_abs))
            text(ctx, TITLE, W / 2, H * 0.47, 104 * k, (0.97, 0.93, 0.85), a, italic=True, shadow=0.35)
            text(ctx, "UN RELATO EN DIEZ ESCENAS", W / 2, H * 0.47 + 70 * k, 24 * k, (0.86, 0.72, 0.45),
                 a * smooth(2.2, 3.0, t_abs), spacing=7 * k, shadow=0.3)
        elif kind == "scene":
            a = smooth(0.5, 1.1, t) * (1 - smooth(3.0, 3.8, t))
            if a > 0:
                x, y = 120 * k, bar + 110 * k
                ctx.set_source_rgba(0.86, 0.72, 0.45, a)
                ctx.rectangle(x - 26 * k, y - 62 * k, 3 * k, 86 * k)
                ctx.fill()
                text(ctx, f"ESCENA {ROMAN[sc['id'] - 1]}", x, y - 30 * k, 22 * k, (0.92, 0.88, 0.8), a,
                     spacing=6 * k, align="l", shadow=0.4)
                text(ctx, sc["name"], x, y + 18 * k, 50 * k, (1, 1, 1), a, italic=True, align="l", shadow=0.4)
            # subtítulos en la banda inferior
            lines = sc["lines"]
            for i, ln in enumerate(lines):
                nxt = lines[i + 1]["start"] if i + 1 < len(lines) else sc["end"]
                t0, t1 = ln["start"] - 0.1, min(ln["end"] + 0.45, nxt - 0.05)
                if not (t0 <= t_abs <= t1):
                    continue
                a = smooth(t0, t0 + 0.15, t_abs) * (1 - smooth(t1 - 0.15, t1, t_abs))
                rows = wrap(ctx, ln["text"], 44 * k, W * 0.78)
                base = H - bar + (bar - 46 * k * len(rows)) / 2 + 40 * k
                if len(rows) == 1:
                    text(ctx, SPEAKERS[ln["spk"]]["name"].upper(), W / 2, base - 48 * k, 19 * k,
                         NAME_COL[ln["spk"]], a, spacing=6 * k)
                for r in rows:
                    text(ctx, r, W / 2, base + (8 * k if len(rows) == 1 else 0), 44 * k, (0.96, 0.95, 0.92), a)
                    base += 48 * k
        elif kind == "end":
            a = smooth(0.4, 1.6, t)
            text(ctx, "FIN", W / 2, H * 0.47, 92 * k, (0.95, 0.9, 0.8), a, spacing=34 * k)
            text(ctx, TITLE, W / 2, H * 0.47 + 72 * k, 34 * k, (0.86, 0.72, 0.45), a * smooth(1.0, 2.0, t),
                 italic=True)
            text(ctx, "Imagen, luz, voces y música generadas íntegramente por código", W / 2, H - bar - 60 * k,
                 20 * k, (0.7, 0.68, 0.64), a * smooth(1.6, 2.6, t), spacing=3 * k)
        surf.flush()
        return bytes(surf.get_data())

    # --------------------------------------------------------- fotograma
    def frame(self, t_abs):
        kind, sc, t = self.segment(t_abs)
        if kind == "end":
            f = dict(t=t_abs, cam=(0, 1.5, 0), f=1000.0, shift=(0, 0), focus=5.0, coc_k=0.0,
                     env=dict(amb_top=(0, 0, 0), amb_bot=(0, 0, 0)), sky=None, items=[], post=dict(fade=0.0))
            f["overlay"] = self.overlay(kind, sc, t, t_abs)
            return self.eng.render(f)
        sd = self.defs[sc["id"]]
        active = sd
        if sd.switch and sd.switch[0][0] <= t < sd.switch[0][1]:
            active = sd.switch[1]
        needed = {sd.set_key} | ({sd.switch[1].set_key} if sd.switch else set())
        self.keep_only(needed)
        aset = self.get_set(active)
        shots = film.Shots(active.shots, self.W, self.H)
        f = fr.build(self.eng, aset, active.actors, shots, t, post_mod=active.post_mod)
        # cortes: sin estela de movimiento entre planos
        if shots.cut_near(t, fr.SHUTTER):
            f["cam_vel"] = (0.0, 0.0, 0.0)
        dur = sc["end"] - sc["start"]
        post = f["post"]
        fade = 1.0
        if kind == "title":
            fade = smooth(0.0, 2.2, t_abs)
        else:
            if sc["id"] != 1:
                fade *= smooth(0.0, 0.45, t)
            fade *= 1 - smooth(dur - 0.45, dur, t)
        post["fade"] = post.get("fade", 1.0) * fade
        f["overlay"] = self.overlay(kind, sc, t, t_abs)
        return self.eng.render(f)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--res", default="2560x1440")
    ap.add_argument("--stills", nargs="*", type=float)
    ap.add_argument("--from", dest="t0", type=float, default=0.0)
    ap.add_argument("--to", dest="t1", type=float, default=None)
    ap.add_argument("--out", default=str(BUILD / "video_mudo.mp4"))
    args = ap.parse_args()
    W, H = map(int, args.res.split("x"))
    fm = Film(W, H)
    print(f"duración total {fm.total:.2f}s", flush=True)
    if args.stills:
        d = BUILD / "stills"
        d.mkdir(parents=True, exist_ok=True)
        from PIL import Image
        for s in args.stills:
            img = fm.frame(s)
            Image.frombytes("RGB", (W, H), img).transpose(Image.FLIP_TOP_BOTTOM).save(d / f"t{s:06.2f}.png")
            print("still", s, flush=True)
        return
    n0 = int(round(args.t0 * FPS))
    n1 = int(round((args.t1 if args.t1 is not None else fm.total) * FPS))
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-vf", "vflip", "-c:v", "libx264", "-preset", "slow", "-crf", "14", "-tune", "film",
           "-pix_fmt", "yuv420p", "-movflags", "+faststart", args.out]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    t_start = time.time()
    for i in range(n0, n1):
        proc.stdin.write(fm.frame(i / FPS))
        if (i - n0) % 24 == 0:
            el = time.time() - t_start
            done = i - n0 + 1
            eta = el / done * (n1 - n0 - done)
            print(f"fotograma {i}/{n1}  {el / done:.2f}s/f  quedan {eta / 60:.1f} min", flush=True)
    proc.stdin.close()
    proc.wait()
    print("video:", args.out, flush=True)


if __name__ == "__main__":
    main()
