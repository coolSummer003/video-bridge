"""whisper.cpp 模型下载：默认从 hf-mirror / huggingface 下载。"""
from __future__ import annotations

import os
import urllib.request
from typing import Callable

MODEL_URLS = [
    "https://hf-mirror.com/ggerganov/whisper.cpp/resolve/main/{name}",
    "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/{name}",
]

ProgressCallback = Callable[[int, int | None], None]


def download_model(
    dest_path: str,
    model_name: str = "ggml-small.bin",
    on_progress: ProgressCallback | None = None,
    on_status: Callable[[str], None] | None = None,
) -> str:
    """下载 whisper.cpp 模型到 dest_path，支持进度回调与多源回退。"""
    dest_path = os.path.abspath(dest_path)
    os.makedirs(os.path.dirname(dest_path) or ".", exist_ok=True)
    tmp_path = dest_path + ".part"

    for url_template in MODEL_URLS:
        url = url_template.format(name=model_name)
        try:
            if on_status:
                on_status(f"开始下载: {url}")
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as resp, open(tmp_path, "wb") as f:
                total = int(resp.headers.get("Content-Length") or 0) or None
                downloaded = 0
                while True:
                    chunk = resp.read(256 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if on_progress:
                        on_progress(downloaded, total)
            if os.path.exists(tmp_path):
                os.replace(tmp_path, dest_path)
            if on_status:
                on_status("模型下载完成")
            return dest_path
        except Exception as exc:
            if on_status:
                on_status(f"下载源失败: {exc}")
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
            continue

    raise RuntimeError("所有模型下载源均失败")
