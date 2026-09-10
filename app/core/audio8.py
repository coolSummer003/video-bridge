"""Audio8 TTS 本地 HTTP 服务调用。"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import urllib.error
import urllib.request

from .config import BinaryPaths


def is_audio8_available(base_url: str = "http://127.0.0.1:8024") -> bool:
    """检测 Audio8 ONNX Runtime 本地服务是否已启动。"""
    try:
        with urllib.request.urlopen(base_url, timeout=2) as resp:
            return resp.status == 200
    except Exception:
        return False


def text_to_speech_audio8(
    text: str,
    output_path: str,
    *,
    base_url: str = "http://127.0.0.1:8024",
    voice_name: str = "",
    max_new_tokens: int = 512,
    on_status: callable | None = None,
) -> str:
    """调用 Audio8 /api/tts 生成 WAV 音频。"""
    text = (text or "").strip()
    if not text:
        raise ValueError("配音文本不能为空")
    if not is_audio8_available(base_url):
        raise RuntimeError(
            "Audio8 本地服务未启动，请先运行 Audio8_TTS/onnx_runtime 的 start_server.sh"
        )

    payload: dict = {
        "text": text,
        "voice_name": voice_name or "default",
        "max_new_tokens": max_new_tokens,
    }

    if on_status:
        on_status("正在请求 Audio8 本地配音服务...")
    req = urllib.request.Request(
        base_url.rstrip("/") + "/api/tts",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            data = resp.read()
    except urllib.error.HTTPError as exc:
        try:
            detail = exc.read().decode("utf-8", errors="replace")
        except Exception:
            detail = ""
        raise RuntimeError(f"Audio8 请求失败 HTTP {exc.code}: {detail[:500]}") from exc

    if not data:
        raise RuntimeError("Audio8 返回空音频")
    os.makedirs(os.path.dirname(os.path.abspath(output_path)) or ".", exist_ok=True)

    # Audio8 返回 WAV；如果用户要求 .mp3，则先生成临时 wav 再转码
    if output_path.lower().endswith(".mp3"):
        fd, tmp_wav = tempfile.mkstemp(prefix="vb_audio8_", suffix=".wav")
        os.close(fd)
        try:
            with open(tmp_wav, "wb") as f:
                f.write(data)
            bins = BinaryPaths.detect()
            proc = subprocess.run(
                [
                    bins.ffmpeg,
                    "-y",
                    "-i",
                    tmp_wav,
                    "-codec:a",
                    "libmp3lame",
                    "-qscale:a",
                    "4",
                    output_path,
                ],
                capture_output=True,
                text=True,
            )
            if proc.returncode != 0:
                raise RuntimeError(f"Audio8 转 MP3 失败: {proc.stderr[-300:]}")
        finally:
            if os.path.exists(tmp_wav):
                try:
                    os.remove(tmp_wav)
                except OSError:
                    pass
    else:
        with open(output_path, "wb") as f:
            f.write(data)

    if on_status:
        on_status(f"Audio8 配音完成: {output_path}")
    return output_path
