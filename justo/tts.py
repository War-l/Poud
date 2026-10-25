"""Sintetiza cada línea con Piper y la ajusta por personaje (tono, velocidad, limpieza)."""
import json
import subprocess
import sys
from pathlib import Path

from guion import SCENES, SPEAKERS

ROOT = Path(__file__).resolve().parent
VOICES = ROOT / "assets" / "voices"
OUT = ROOT / "build" / "voz"
SR = 48000


def native_sr(voice):
    return json.loads((VOICES / f"{voice}.onnx.json").read_text())["audio"]["sample_rate"]


def duration(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                        str(path)], capture_output=True, text=True, check=True)
    return float(r.stdout)


def synth(text, spk, dest):
    cfg = SPEAKERS[spk]
    raw = dest.with_suffix(".raw.wav")
    subprocess.run([sys.executable, "-m", "piper", "-m", str(VOICES / f"{cfg['voice']}.onnx"),
                    "-s", str(cfg["sid"]), "--length-scale", f"{1 / cfg['speed']:.3f}",
                    "--sentence-silence", "0.25", "-f", str(raw)],
                   input=text.encode(), check=True, capture_output=True)
    sr, p = native_sr(cfg["voice"]), cfg["pitch"]
    af = (f"asetrate={int(sr * p)},aresample={SR}:resampler=soxr,atempo={1 / p:.5f},"
          "silenceremove=start_periods=1:start_threshold=-50dB,"
          "areverse,silenceremove=start_periods=1:start_threshold=-50dB,areverse,"
          "highpass=f=75,lowpass=f=11000,"
          "acompressor=threshold=-20dB:ratio=2.5:attack=8:release=120,"
          "loudnorm=I=-18:TP=-2:LRA=7")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(raw), "-af", af, "-ar", str(SR), "-ac", "1",
                    str(dest)], check=True)
    raw.unlink()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    meta = []
    for sc in SCENES:
        for i, (spk, text, _w) in enumerate(sc["lines"]):
            dest = OUT / f"s{sc['id']:02d}_{i}.wav"
            synth(text, spk, dest)
            d = duration(dest)
            meta.append({"scene": sc["id"], "idx": i, "spk": spk, "text": text, "file": str(dest), "dur": d})
            print(f"{dest.name} {d:5.2f}s [{spk}] {text}")
    (OUT / "lines.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1))
    print(f"voz total {sum(m['dur'] for m in meta):.1f}s")


if __name__ == "__main__":
    main()
