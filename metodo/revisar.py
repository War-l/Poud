"""Observar y comparar: revisión del vídeo renderizado frente a su expediente.

Uso:
    python3 -m metodo.revisar EXPEDIENTE VIDEO [--salida DIR] [--render-s SEGUNDOS]

Genera en DIR (por defecto <carpeta del expediente>/revision/):

- cortes.png: último fotograma de cada plano junto al primero del siguiente, con mediciones;
- planos.png: un fotograma por plano, para comprobar que se entiende sin texto (REV-01);
- personaje_<id>.png: el personaje en todos sus planos, para compararlo con la biblia (REV-02);
- revision.json: mediciones y cortes marcados.

En la Puerta C, el verificador exige un veredicto para cada corte marcado.

Mediciones por corte (los «testigos» automáticos):

- exposición: diferencia de la luminosidad mediana (CIELAB L*), sin bandas negras. Es el testigo
  fiable de un salto de luz en escenas continuas;
- color de la luz: crominancia (a*, b*) del 10 % más brillante y del 10 % más oscuro. Depende del
  contenido del encuadre, así que solo marca errores groseros de balance de blancos;
- posición del corte: el cambio entre los dos fotogramas del corte debe destacar frente al cambio
  entre fotogramas vecinos. Si no destaca, el código y el expediente pueden estar desfasados.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import textwrap
from datetime import datetime
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .expediente import cargar, como_lista

# Umbrales calibrados con 27 cortes reales dentro de escena (ver metodo/CALIBRACION.md):
# - exposición: los 2 cortes incoherentes midieron |ΔL| 43 y 45; los coherentes, como máximo 23,
#   y los contraplanos dudosos, de 25 a 38;
# - color: el color de las luces no distingue cortes coherentes de incoherentes (los coherentes
#   llegan a ΔC 31 cuando el sol o el cielo entran en cuadro). Solo se marcan errores groseros de
#   balance de blancos, por encima de lo observado en cortes coherentes.
UMBRAL_CROMA = 40.0
UMBRAL_EXPOSICION = 40.0
FUENTE = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FUENTE_N = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def fuente(tam, negrita=False):
    try:
        return ImageFont.truetype(FUENTE_N if negrita else FUENTE, tam)
    except OSError:
        return ImageFont.load_default()


# ── medición técnica ────────────────────────────────────────────────────────────────────
def sondear(video: Path) -> dict:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(video)],
                       capture_output=True, text=True, check=True)
    info = json.loads(r.stdout)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    a = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
    num, den = (int(x) for x in v["r_frame_rate"].split("/"))
    out = dict(
        ancho=int(v["width"]), alto=int(v["height"]), fps=round(num / den, 3),
        duracion=round(float(info["format"]["duration"]), 3),
        codec=v.get("codec_name"), pix_fmt=v.get("pix_fmt"),
        color=dict(primarias=v.get("color_primaries"), transferencia=v.get("color_transfer"),
                   matriz=v.get("color_space"), rango=v.get("color_range")),
        audio=None, lufs=None, pico_dbtp=None,
    )
    if a:
        out["audio"] = dict(codec=a.get("codec_name"), muestreo=int(a.get("sample_rate", 0)), canales=a.get("channels"))
        out.update(sonoridad(video))
    return out


def sonoridad(video: Path) -> dict:
    """Sonoridad integrada (EBU R128) y pico real, medidos con ffmpeg."""
    r = subprocess.run(["ffmpeg", "-nostats", "-hide_banner", "-i", str(video), "-vn",
                        "-filter_complex", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True)
    s = r.stderr[r.stderr.rfind("Summary:"):]
    i = re.search(r"I:\s+(-?[\d.]+|-inf)\s+LUFS", s)
    p = re.search(r"True peak:\s+Peak:\s+(-?[\d.]+|-inf)\s+dBFS", s)
    f = lambda m: (None if m is None else (float("-inf") if m.group(1) == "-inf" else float(m.group(1))))
    return dict(lufs=f(i), pico_dbtp=f(p))


def leer_fotogramas(video: Path, indices, ancho: int, alto_src: int, ancho_src: int) -> dict:
    """Decodifica solo los fotogramas pedidos (una pasada) y los devuelve reducidos a `ancho`."""
    idx = sorted(set(int(i) for i in indices if i >= 0))
    if not idx:
        return {}
    alto = max(2, int(round(ancho * alto_src / ancho_src / 2)) * 2)
    expr = "+".join(f"eq(n\\,{i})" for i in idx)
    cmd = ["ffmpeg", "-v", "error", "-i", str(video), "-vf", f"select='{expr}',scale={ancho}:{alto}:flags=area",
           "-fps_mode", "passthrough", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    r = subprocess.run(cmd, capture_output=True, check=True)
    tam = ancho * alto * 3
    n = len(r.stdout) // tam
    marcos = np.frombuffer(r.stdout[: n * tam], np.uint8).reshape(n, alto, ancho, 3)
    return {i: marcos[k] for k, i in enumerate(idx[:n])}


def a_lab(rgb: np.ndarray) -> np.ndarray:
    c = rgb.astype(np.float64) / 255.0
    c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    m = np.array([[0.4124564, 0.3575761, 0.1804375],
                  [0.2126729, 0.7151522, 0.0721750],
                  [0.0193339, 0.1191920, 0.9503041]])
    xyz = c @ m.T / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > (6 / 29) ** 3, np.cbrt(xyz), xyz / (3 * (6 / 29) ** 2) + 4 / 29)
    L = 116 * f[..., 1] - 16
    a = 500 * (f[..., 0] - f[..., 1])
    b = 200 * (f[..., 1] - f[..., 2])
    return np.stack([L, a, b], -1)


def sin_bandas(rgb: np.ndarray, umbral: int = 12) -> np.ndarray:
    """Recorta las bandas negras del formato panorámico (filas enteras casi negras arriba y abajo).

    Sin este recorte, el 10 % más oscuro de un fotograma 2,39:1 en 16:9 serían las propias bandas
    y la medida de las sombras no diría nada de la imagen.
    """
    filas = np.flatnonzero(rgb.max(axis=(1, 2)) > umbral)
    if filas.size == 0:
        return rgb
    return rgb[filas[0]: filas[-1] + 1]


def metricas(rgb: np.ndarray) -> dict:
    lab = a_lab(sin_bandas(rgb)).reshape(-1, 3)
    L = lab[:, 0]
    p10, p90 = np.percentile(L, [10, 90])
    luces, sombras = lab[L >= p90], lab[L <= p10]
    return dict(
        L_mediana=float(np.median(L)),
        luces=[float(luces[:, 1].mean()), float(luces[:, 2].mean())] if p90 >= 10 else None,
        sombras=[float(sombras[:, 1].mean()), float(sombras[:, 2].mean())] if p90 >= 10 else None,
    )


def dif_media(a, b):
    return float(np.abs(a.astype(np.int16) - b.astype(np.int16)).mean())


# ── revisión ────────────────────────────────────────────────────────────────────────────
def revisar(ruta_exp, video, salida=None, render_s=None, ancho=480) -> dict:
    ex = cargar(ruta_exp)
    video = Path(video)
    salida = Path(salida) if salida else ex.carpeta / "revision"
    salida.mkdir(parents=True, exist_ok=True)
    tec = sondear(video)
    fps = ex.fps
    total = int(round(tec["duracion"] * tec["fps"]))
    if render_s is not None:
        tec["render_s"] = float(render_s)
        tec["ratio_render"] = round(float(render_s) / max(tec["duracion"], 1e-9), 3)

    # fotogramas necesarios
    medios, cortes_req = {}, []
    for i, p in enumerate(ex.planos):
        f0, f1 = ex.fotogramas(p)
        medios[p["id"]] = min(max((f0 + f1) // 2, 0), total - 1)
        if i > 0:
            cortes_req.append((i, f0 - 2, f0 - 1, f0))
    pedidos = list(medios.values()) + [f for c in cortes_req for f in c[1:]]
    fot = leer_fotogramas(video, [f for f in pedidos if f < total], ancho, tec["alto"], tec["ancho"])

    # cortes
    cortes = []
    for i, fa0, fa, fb in cortes_req:
        p, q = ex.planos[i - 1], ex.planos[i]
        c = dict(id=f"{p['id']}>{q['id']}", de=p["id"], a=q["id"], fotograma=fb, tiempo=round(fb / fps, 3),
                 continuo=ex.continuo_con_anterior(i), marcado=False, motivos=[])
        if fa not in fot or fb not in fot:
            c.update(marcado=True, motivos=["no se pudieron leer los fotogramas del corte (¿vídeo más corto que el plan?)"])
            cortes.append(c)
            continue
        ma, mb = metricas(fot[fa]), metricas(fot[fb])
        c["metricas"] = dict(antes=ma, despues=mb)
        if ma["luces"] and mb["luces"]:
            c["dC_luces"] = round(float(np.hypot(*np.subtract(ma["luces"], mb["luces"]))), 2)
            c["dC_sombras"] = round(float(np.hypot(*np.subtract(ma["sombras"], mb["sombras"]))), 2)
        c["dL_mediana"] = round(mb["L_mediana"] - ma["L_mediana"], 2)
        esc_q = ex.escena_de(q)
        primera = p.get("escena") != q.get("escena")
        tipo = ((esc_q.get("transicion") or {}).get("tipo") if primera else q.get("entrada")) or "corte"
        c["transicion"] = tipo
        if c["continuo"] and not q.get("cambio_luz"):
            if c.get("dC_luces", 0) > UMBRAL_CROMA:
                c["motivos"].append(f"el color de las luces cambia ΔC={c['dC_luces']} (> {UMBRAL_CROMA}) en escenas continuas")
            if c.get("dC_sombras", 0) > UMBRAL_CROMA:
                c["motivos"].append(f"el color de las sombras cambia ΔC={c['dC_sombras']} (> {UMBRAL_CROMA}) en escenas continuas")
            if abs(c["dL_mediana"]) > UMBRAL_EXPOSICION:
                c["motivos"].append(f"salto de exposición ΔL={c['dL_mediana']} (> {UMBRAL_EXPOSICION})")
        if tipo == "corte" and fa0 in fot:
            salto = dif_media(fot[fa], fot[fb])
            vecino = dif_media(fot[fa0], fot[fa])
            c["salto_corte"] = round(salto, 2)
            c["salto_vecino"] = round(vecino, 2)
            if salto < 1.5 * vecino + 1.0:
                c["motivos"].append("el corte no destaca en el fotograma previsto: ¿el código no sigue los tiempos del expediente?")
        c["marcado"] = bool(c["motivos"])
        cortes.append(c)

    # hojas
    hojas = {}
    if cortes:
        hojas["cortes"] = str(hoja_cortes(cortes, fot, salida / "cortes.png"))
    hojas["planos"] = str(hoja_planos(ex, medios, fot, salida / "planos.png"))
    for pid_, info in (ex.biblia.get("personajes") or {}).items():
        planos = [p for p in ex.planos if pid_ in (p.get("sujetos") or {})]
        if planos:
            hojas[f"personaje_{pid_}"] = str(hoja_planos(ex, medios, fot, salida / f"personaje_{pid_}.png",
                                                         planos=planos, titulo=f"{pid_}: {info.get('rasgos', '')}"))
    datos = dict(expediente=str(ruta_exp), video=str(video), fecha=datetime.now().isoformat(timespec="seconds"),
                 entrega=tec, cortes=cortes, hojas=hojas,
                 umbrales=dict(croma=UMBRAL_CROMA, exposicion=UMBRAL_EXPOSICION))
    (salida / "revision.json").write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
    return datos


# ── hojas de contacto ───────────────────────────────────────────────────────────────────
def _vacio(h, w):
    return np.full((h, w, 3), 40, np.uint8)


def hoja_cortes(cortes, fot, destino: Path) -> Path:
    alguno = next(iter(fot.values()))
    h, w = alguno.shape[:2]
    banda, marg = 44, 12
    hoja = Image.new("RGB", (2 * w + 3 * marg, len(cortes) * (h + banda + marg) + marg), (24, 24, 28))
    dr = ImageDraw.Draw(hoja)
    f1, f2 = fuente(15, True), fuente(12)
    y = marg
    for c in cortes:
        col = (235, 80, 70) if c["marcado"] else (120, 200, 140)
        cont = "continuo" if c["continuo"] else "salto de escena"
        med = ""
        if "dC_luces" in c:
            med = f"ΔC luces {c['dC_luces']} · ΔC sombras {c['dC_sombras']} · ΔL {c['dL_mediana']}"
        dr.text((marg, y), f"{c['de']} → {c['a']}   t={c['tiempo']} s   {cont}   {med}", font=f1, fill=col)
        if c["motivos"]:
            dr.text((marg, y + 21), "; ".join(c["motivos"])[:150], font=f2, fill=col)
        y += banda
        fa = c["fotograma"] - 1
        for k, f in enumerate((fa, c["fotograma"])):
            img = fot.get(f, _vacio(h, w))
            hoja.paste(Image.fromarray(img), (marg + k * (w + marg), y))
            if c["marcado"]:
                dr.rectangle([marg + k * (w + marg) - 2, y - 2, marg + k * (w + marg) + w + 1, y + h + 1], outline=col, width=2)
        y += h + marg
    hoja.save(destino)
    return destino


def hoja_planos(ex, medios, fot, destino: Path, planos=None, titulo=None, columnas=4) -> Path:
    planos = planos if planos is not None else ex.planos
    alguno = next(iter(fot.values()))
    h, w = alguno.shape[:2]
    banda, marg, cab = 52, 12, (34 if titulo else 0)
    filas = (len(planos) + columnas - 1) // columnas
    cols = min(columnas, len(planos))
    hoja = Image.new("RGB", (cols * (w + marg) + marg, cab + filas * (h + banda + marg) + marg), (24, 24, 28))
    dr = ImageDraw.Draw(hoja)
    f1, f2 = fuente(14, True), fuente(11)
    if titulo:
        dr.text((marg, 10), titulo[:150], font=fuente(15, True), fill=(230, 230, 230))
    for k, p in enumerate(planos):
        x = marg + (k % columnas) * (w + marg)
        y = cab + marg + (k // columnas) * (h + banda + marg)
        hoja.paste(Image.fromarray(fot.get(medios[p["id"]], _vacio(h, w))), (x, y))
        ini, fin = ex.inicio(p), ex.fin(p)
        dr.text((x, y + h + 4), f"{p['id']} · {p.get('tamano', '')} · {ini:.1f}–{fin:.1f} s · {p.get('escena', '')}",
                font=f1, fill=(230, 230, 230))
        lineas = textwrap.wrap(" ".join(str(p.get("muestra", "")).split()), width=max(20, w // 7))[:2]
        for j, l in enumerate(lineas):
            dr.text((x, y + h + 22 + 13 * j), l, font=f2, fill=(170, 170, 175))
    hoja.save(destino)
    return destino


def main(argv=None):
    ap = argparse.ArgumentParser(description="Observa y compara el vídeo renderizado con su expediente.")
    ap.add_argument("expediente")
    ap.add_argument("video")
    ap.add_argument("--salida")
    ap.add_argument("--render-s", type=float, help="segundos medidos del render completo (time)")
    ap.add_argument("--ancho", type=int, default=480)
    a = ap.parse_args(argv)
    d = revisar(a.expediente, a.video, a.salida, a.render_s, a.ancho)
    t = d["entrega"]
    print(f"Vídeo: {t['ancho']}×{t['alto']}, {t['fps']} fps, {t['duracion']} s, {t['codec']}/{t['pix_fmt']}")
    if t.get("audio"):
        print(f"Sonido: {t['audio']['codec']} {t['audio']['muestreo']} Hz × {t['audio']['canales']} · "
              f"{t['lufs']} LUFS integrados · pico real {t['pico_dbtp']} dBTP")
    if "render_s" in t:
        print(f"Render: {t['render_s']:.1f} s ({t['ratio_render']:.2f}× la duración)")
    marc = [c for c in d["cortes"] if c["marcado"]]
    print(f"Cortes: {len(d['cortes'])}, marcados: {len(marc)}")
    for c in marc:
        print(f"  ✗ {c['id']} ({c['tiempo']} s): {'; '.join(c['motivos'])}")
    for k, v in d["hojas"].items():
        print(f"Hoja {k}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
