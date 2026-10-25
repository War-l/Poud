#!/usr/bin/env bash
# Descarga las voces Piper en español (empaquetadas por sherpa-onnx en GitHub).
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)/assets/voices"
mkdir -p "$DIR"
BASE=https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models
for v in es_ES-davefx-medium es_ES-sharvard-medium es_ES-carlfm-x_low; do
  if [ ! -f "$DIR/$v.onnx" ]; then
    echo "Descargando $v..."
    curl -sSLf "$BASE/vits-piper-$v.tar.bz2" | tar xj -C "$DIR" "vits-piper-$v/$v.onnx" "vits-piper-$v/$v.onnx.json"
    mv "$DIR/vits-piper-$v/$v.onnx"* "$DIR/" && rmdir "$DIR/vits-piper-$v"
  fi
done
