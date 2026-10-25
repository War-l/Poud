#!/usr/bin/env bash
# Construye «El espejo cubierto» de principio a fin.
set -euo pipefail
cd "$(dirname "$0")"
OUT="${1:-../el_espejo_cubierto.mp4}"

./fetch_voices.sh                 # 1. voces Piper en español
python3 tts.py                    # 2. diálogos -> build/voz/*.wav
python3 render.py                 # 3. fotogramas -> build/video_mudo.mp4
python3 audio.py                  # 4. voz + música + efectos -> build/audio.wav
# 5. unir imagen y sonido
ffmpeg -y -v error -i build/video_mudo.mp4 -i build/audio.wav \
  -c:v copy -c:a aac -b:a 192k -shortest -movflags +faststart "$OUT"
echo "Listo: $OUT"
