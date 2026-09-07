#!/bin/bash
# 在 macOS (Apple Silicon) 上打包 VideoBridge.app 的示例脚本。
set -euo pipefail
cd "$(dirname "$0")/.."

PYTHON=${PYTHON:-python3.12}
APP_NAME="VideoBridge"

# 1. 依赖
"$PYTHON" -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e . pyinstaller

# 2. 将外部二进制复制到 app/resources/bin（打包时由 PyInstaller 收集）
mkdir -p resources/bin
for tool in ffmpeg ffprobe yt-dlp whisper-cli; do
  if [ "$tool" = "ffmpeg" ] || [ "$tool" = "ffprobe" ]; then
    # 优先使用带 libass 的 Homebrew ffmpeg-full，否则普通 ffmpeg 不支持字幕烧录
    src="/opt/homebrew/opt/ffmpeg-full/bin/$tool"
    [ -x "$src" ] || src=$(command -v "$tool" || true)
  else
    src=$(command -v "$tool" || true)
  fi
  if [ -n "$src" ]; then
    cp "$src" "resources/bin/$tool"
  else
    echo "缺少 $tool" >&2
    exit 1
  fi
done

# 3. PyInstaller 打包
pyinstaller \
  --noconfirm \
  --clean \
  --name "$APP_NAME" \
  --windowed \
  --add-data "resources/bin:resources/bin" \
  app/main.py

echo "打包完成: dist/$APP_NAME.app"
