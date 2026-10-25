"""Genera un WAV por línea de diálogo con Piper y lo ajusta por personaje.

Voces: davefx (maestro) y sharvard (alumno, joven). El tono se ajusta por
personaje con asetrate + atempo en ffmpeg.
"""
import json
import subprocess
import sys
from pathlib import Path

from guion import SCENES, SPEAKERS

ROOT = Path(__file__).resolve().parent
VOICES = ROOT / "assets" / "voices"
OUT = ROOT / "build" / "voz"
SR = 22050


def duration(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", str(path)], capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


def synth(text, spk, dest):
    raw = dest.with_suffix(".raw.wav")
    cfg = SPEAKERS[spk]
    subprocess.run([sys.executable, "-m", "piper", "-m", str(VOICES / (cfg["voice"] + ".onnx")),
                    "-s", str(cfg["sid"]), "-f", str(raw),
                    "--length-scale", str(1.0 / cfg["speed"])],
                   input=text.encode(), check=True, capture_output=True)
    p = cfg["pitch"]
    # Cambia el tono sin cambiar la duración, recorta silencios y normaliza.
    af = (f"asetrate={int(SR * p)},aresample=44100,atempo={1 / p:.4f},"
          "silenceremove=start_periods=1:start_threshold=-45dB,"
          "areverse,silenceremove=start_periods=1:start_threshold=-45dB,areverse,"
          "highpass=f=70,loudnorm=I=-17:TP=-2")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(raw), "-af", af,
                    "-ar", "44100", "-ac", "1", str(dest)], check=True)
    raw.unlink()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    meta = []
    for sc in SCENES:
        for i, (spk, text, _w) in enumerate(sc["lines"]):
            dest = OUT / f"s{sc['id']}_{i}.wav"
            synth(text, spk, dest)
            d = duration(dest)
            meta.append({"scene": sc["id"], "idx": i, "spk": spk, "text": text,
                         "file": str(dest), "dur": d})
            print(f"{dest.name}: {d:.2f}s  {text}")
    (OUT / "lines.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1))
    print("total voz:", round(sum(m["dur"] for m in meta), 2), "s")


if __name__ == "__main__":
    main()
