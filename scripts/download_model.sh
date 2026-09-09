#!/bin/bash
# 下载 whisper.cpp 模型到 models/，默认 small（约 500MB）。
# 国内优先走 ModelScope，失败后回退 hf-mirror / HuggingFace。
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p models

MODEL_NAME="${1:-ggml-small.bin}"
DEST="models/$MODEL_NAME"
if [ -f "$DEST" ]; then
  echo "模型已存在: $DEST"
  exit 0
fi

URLS=(
  "https://modelscope.cn/models/iceCream2025/whisper.cpp/resolve/master/$MODEL_NAME"
  "https://hf-mirror.com/ggerganov/whisper.cpp/resolve/main/$MODEL_NAME"
  "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/$MODEL_NAME"
)

for url in "${URLS[@]}"; do
  echo "尝试下载: $url"
  if curl -L --fail --progress-bar -o "$DEST.tmp" "$url"; then
    mv "$DEST.tmp" "$DEST"
    echo "完成: $DEST"
    exit 0
  else
    echo "下载失败，尝试下一个源"
    rm -f "$DEST.tmp"
  fi
done

echo "所有下载源均失败" >&2
exit 1
