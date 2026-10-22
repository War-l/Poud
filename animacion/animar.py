# Anima la imagen del escriba: llama parpadeante, resplandor cálido y zoom lento.
import math, random, subprocess, os
import numpy as np
from PIL import Image, ImageFilter

FPS, SEG = 30, 8
W, H = 1376, 768
base = Image.open("escriba.jpg").convert("RGB")
FLAMA = (992, 548, 1028, 602)          # caja de la llama
BASE_Y, CX = 602, 1010                  # punto de anclaje (mecha)
flama = base.crop(FLAMA)
fondo = base.copy()
fondo.paste((0, 0, 0), (FLAMA[0], FLAMA[1], FLAMA[2], 598))

yy, xx = np.mgrid[0:H, 0:W]
dist = np.sqrt((xx - CX) ** 2 + ((yy - 580) * 1.2) ** 2)
random.seed(3)
os.makedirs("frames", exist_ok=True)
n = FPS * SEG
for i in range(n):
    t = i / FPS
    f = 1 + 0.12 * math.sin(t * 9) + 0.07 * math.sin(t * 23 + 1) + random.uniform(-0.04, 0.04)
    sx = 1 - 0.3 * (f - 1)
    fw, fh = flama.size
    nf = flama.resize((max(1, int(fw * sx)), max(1, int(fh * f))), Image.LANCZOS)
    nf = nf.rotate(4 * math.sin(t * 5), resample=Image.BICUBIC, expand=True)
    img = fondo.copy()
    mask = nf.convert("L").point(lambda v: 255 if v > 60 else 0).filter(ImageFilter.GaussianBlur(0.6))
    img.paste(nf, (CX - nf.size[0] // 2, BASE_Y - nf.size[1]), mask)

    a = np.asarray(img).astype(np.float32) / 255
    # tono cálido de vela
    warm = np.array([1.0, 0.9, 0.72])
    a = a * warm
    glow = np.exp(-dist / (260 * f)) * (0.55 + 0.25 * (f - 1) * 3)
    a += glow[..., None] * np.array([1.0, 0.6, 0.2]) * 0.6
    # luz general suave que respira
    a *= 0.92 + 0.08 * math.sin(t * 1.2)
    img = Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8))

    # zoom lento hacia el escriba
    z = 1 + 0.08 * (i / (n - 1))
    cw, ch = W / z, H / z
    cx0, cy0 = 640, 380
    l = min(max(cx0 - cw / 2, 0), W - cw); u = min(max(cy0 - ch / 2, 0), H - ch)
    img = img.resize((W, H), Image.LANCZOS, box=(l, u, l + cw, u + ch))
    img.save(f"frames/{i:04d}.png")

subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", "frames/%04d.png",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "escriba_animado.mp4"], check=True)
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", "escriba_animado.mp4", "-vf",
                "fps=15,scale=688:-1:flags=lanczos,split[a][b];[a]palettegen[p];[b][p]paletteuse",
                "escriba_animado.gif"], check=True)
