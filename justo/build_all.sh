#!/usr/bin/env bash
# Render completo y reanudable: tramos de 12 s -> concatenación -> mezcla con el audio.
set -euo pipefail
cd "$(dirname "$0")"
RES="${RES:-2560x1440}"
mkdir -p build/chunks
TOTAL=$(python3 -c "import film; print(film.load_timeline()[1])")
STEP=12
N=$(python3 -c "import math; print(math.ceil($TOTAL/$STEP))")
for ((k=0; k<N; k++)); do
  out=build/chunks/c$(printf %03d $k).mp4
  [ -f "$out" ] && continue
  t0=$(python3 -c "print($k*$STEP)"); t1=$(python3 -c "print(min(($k+1)*$STEP, $TOTAL))")
  echo "== tramo $k: $t0 - $t1"
  python3 render.py --res "$RES" --from "$t0" --to "$t1" --out build/chunks/tmp.mp4
  mv build/chunks/tmp.mp4 "$out"
done
ls build/chunks/c*.mp4 | sed "s/^build\/chunks\//file '/; s/$/'/" > build/chunks/list.txt
ffmpeg -y -v error -f concat -safe 0 -i build/chunks/list.txt -c copy build/video_mudo.mp4
python3 audio.py
ffmpeg -y -v error -i build/audio_raw.wav -af loudnorm=I=-16:TP=-1.5:LRA=11 -ar 48000 build/audio.wav
ffmpeg -y -v error -i build/video_mudo.mp4 -i build/audio.wav -c:v copy -c:a aac -b:a 256k -shortest \
  -movflags +faststart ../el_hombre_que_queria_ser_justo.mp4
echo "LISTO"
