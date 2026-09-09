"""Audio8 首次自动下载 + 本地服务启动管理。"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

from .audio8 import is_audio8_available

AUDIO8_REPO = "https://github.com/Audio8-AI/Audio8_TTS.git"
AUDIO8_MODEL_REPO = "Audio8/Audio8-TTS-Preview-0.6B-ONNX-INT4"
AUDIO8_MODEL_FILES = ["slow_ar_int4.onnx", "fast_ar_int4.onnx", "codec_decoder_fp16.onnx"]

_ROOT = Path(__file__).resolve().parents[2] / "models" / "audio8"
_RUNTIME_DIR = _ROOT / "onnx_runtime"
_MODEL_DIR = _RUNTIME_DIR / "model"


def _status(on_status):
    def _log(msg):
        if on_status:
            on_status(msg)
    return _log


def ensure_runtime_downloaded(on_status=None) -> Path:
    log = _status(on_status)
    if (_RUNTIME_DIR / "start_server.sh").exists():
        return _RUNTIME_DIR

    log("首次使用：正在下载 Audio8 ONNX Runtime 服务...")
    _ROOT.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="audio8_runtime_"))
    try:
        subprocess.run(
            ["git", "clone", "--depth", "1", AUDIO8_REPO, str(tmp / "repo")],
            check=True,
            capture_output=True,
        )
        src = tmp / "repo" / "onnx_runtime"
        if not src.exists():
            raise RuntimeError("Audio8 仓库中未找到 onnx_runtime 目录")
        shutil.copytree(src, _RUNTIME_DIR)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    log("Audio8 ONNX Runtime 下载完成")
    return _RUNTIME_DIR


def ensure_model_downloaded(on_status=None) -> Path:
    log = _status(on_status)
    if _model_ready():
        return _MODEL_DIR

    ensure_runtime_downloaded(on_status=on_status)
    _MODEL_DIR.mkdir(parents=True, exist_ok=True)
    log("首次使用：正在下载 Audio8 模型（约 600MB~1GB），请耐心等待...")
    try:
        from huggingface_hub import snapshot_download
        snapshot_download(
            repo_id=AUDIO8_MODEL_REPO,
            local_dir=str(_MODEL_DIR),
        )
    except Exception:
        # 尝试通过 hf-mirror
        os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
        from huggingface_hub import snapshot_download
        snapshot_download(
            repo_id=AUDIO8_MODEL_REPO,
            local_dir=str(_MODEL_DIR),
        )
    if not _model_ready():
        raise RuntimeError("Audio8 模型下载不完整")
    log("Audio8 模型下载完成")
    return _MODEL_DIR


def _model_ready() -> bool:
    return all((_MODEL_DIR / name).exists() for name in AUDIO8_MODEL_FILES)


def start_local_service(on_status=None) -> str:
    log = _status(on_status)
    url = "http://127.0.0.1:8024"
    if is_audio8_available(url):
        return url

    runtime = ensure_runtime_downloaded(on_status=on_status)
    ensure_model_downloaded(on_status=on_status)

    log("正在启动 Audio8 本地服务...")
    env = os.environ.copy()
    env.setdefault("ARKTTS_MODEL_DIR", str(_MODEL_DIR))
    env.setdefault("HOST", "127.0.0.1")
    env.setdefault("PORT", "8024")

    log_file = open(_ROOT / "audio8_server.log", "a", encoding="utf-8")
    proc = subprocess.Popen(
        ["bash", "start_server.sh"],
        cwd=str(runtime),
        env=env,
        stdout=log_file,
        stderr=log_file,
    )

    deadline = time.time() + 180
    while time.time() < deadline:
        if is_audio8_available(url):
            log("Audio8 本地服务已就绪")
            return url
        if proc.poll() is not None:
            break
        time.sleep(1)

    raise RuntimeError("Audio8 本地服务启动超时，请查看日志 models/audio8/audio8_server.log")


def ensure_audio8_ready(on_status=None) -> str:
    """确保 Audio8 本地服务可用：自动下载模型并启动。"""
    url = "http://127.0.0.1:8024"
    if is_audio8_available(url):
        return url
    return start_local_service(on_status=on_status)
