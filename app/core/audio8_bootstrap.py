"""Audio8 首次自动下载 + 本地服务启动管理。"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

from .audio8 import is_audio8_available

AUDIO8_REPO = "https://github.com/Audio8-AI/Audio8_TTS.git"
AUDIO8_MODEL_REPO = "Audio8/audio8-TTS-0.1B-ONNX-INT8"
AUDIO8_MODEL_BASE_URL = "https://modelscope.cn/models/Audio8/audio8-TTS-0.1B-ONNX-INT8/resolve/master"
AUDIO8_MODEL_FILES = [
    "runtime_manifest.json",
    "slow_ar_int8.onnx",
    "slow_ar_int8.onnx.data",
    "fast_ar_int8.onnx",
    "fast_ar_int8.onnx.data",
    "codec_decoder_fp16.onnx",
    "codec_decoder_fp16.onnx.data",
    "tokenizer/tokenizer.json",
    "reference_codes.npy",
    "registration/codec_encoder_fp16.onnx",
    "registration/codec_encoder_fp16.onnx.data",
    "registration/registration_manifest.json",
]

_ROOT = Path(__file__).resolve().parents[2] / "models" / "audio8"
_RUNTIME_DIR = _ROOT / "onnx_runtime_0_1b_int8"
_MODEL_DIR = _RUNTIME_DIR / "model"


def _status(on_status):
    def _log(msg):
        if on_status:
            on_status(msg)
    return _log


def ensure_runtime_downloaded(on_status=None) -> Path:
    log = _status(on_status)
    if (_RUNTIME_DIR / "start_server.sh").exists():
        _patch_run_server()
        _ensure_runtime_setup(on_status=on_status)
        return _RUNTIME_DIR

    log("首次使用：正在下载 Audio8 ONNX Runtime 服务...")
    _ROOT.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="audio8_runtime_"))
    try:
        subprocess.run(
            [
                "git",
                "-c",
                "http.version=HTTP/1.1",
                "clone",
                "--depth",
                "1",
                AUDIO8_REPO,
                str(tmp / "repo"),
            ],
            check=True,
            capture_output=True,
        )
        src = tmp / "repo" / "onnx_runtime_0_1b_int8"
        if not src.exists():
            raise RuntimeError("Audio8 仓库中未找到 onnx_runtime_0_1b_int8 目录")
        shutil.copytree(src, _RUNTIME_DIR)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    _patch_run_server()
    _ensure_runtime_setup(on_status=on_status)
    log("Audio8 ONNX Runtime 下载完成")
    return _RUNTIME_DIR


def _download_model_file(rel_path: str, log):
    dest = _MODEL_DIR / rel_path
    if dest.exists() and dest.stat().st_size > 0:
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    url = f"{AUDIO8_MODEL_BASE_URL}/{rel_path}"
    log(f"下载模型文件: {rel_path}")
    tmp = str(dest) + ".part"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as resp, open(tmp, "wb") as f:
        while True:
            chunk = resp.read(512 * 1024)
            if not chunk:
                break
            f.write(chunk)
    os.replace(tmp, dest)


def _patch_run_server():
    """把 run_server.sh 里的固定 int4 改为可由环境变量覆盖。"""
    script = _RUNTIME_DIR / "run_server.sh"
    if not script.exists():
        return
    text = script.read_text(encoding="utf-8")
    text = text.replace(
        'export ARKTTS_PRECISION="int4"',
        'export ARKTTS_PRECISION="${ARKTTS_PRECISION:-int4}"',
    )
    script.write_text(text, encoding="utf-8")


def _ensure_runtime_setup(on_status=None):
    """确保 Audio8 Runtime 的 Python 虚拟环境和依赖已安装。"""
    log = _status(on_status)
    venv_python = _RUNTIME_DIR / ".venv" / "bin" / "python"
    if venv_python.exists() and (_RUNTIME_DIR / ".venv" / "bin" / "uvicorn").exists():
        return
    log("首次使用：正在安装 Audio8 运行依赖，请耐心等待...")
    import sys
    env = os.environ.copy()
    env["PYTHON_BIN"] = sys.executable
    result = subprocess.run(
        ["bash", "setup.sh"],
        cwd=str(_RUNTIME_DIR),
        env=env,
        capture_output=True,
        text=True,
        timeout=600,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Audio8 依赖安装失败: {result.stderr[-800:]}")
    log("Audio8 运行依赖安装完成")


def ensure_model_downloaded(on_status=None) -> Path:
    log = _status(on_status)
    if _model_ready():
        return _MODEL_DIR

    ensure_runtime_downloaded(on_status=on_status)
    # 如果已有模型目录但版本不对（例如旧 0.6B int4），只清理旧 manifest 和 int4 文件
    manifest_path = _MODEL_DIR / "runtime_manifest.json"
    if manifest_path.exists():
        try:
            manifest_text = manifest_path.read_text(encoding="utf-8")
            if "0.1b" not in manifest_text.lower() or "int8" not in manifest_text.lower():
                for old_name in (
                    "slow_ar_int4.onnx", "slow_ar_int4.onnx.data",
                    "fast_ar_int4.onnx", "fast_ar_int4.onnx.data",
                    "runtime_manifest.json",
                ):
                    old_file = _MODEL_DIR / old_name
                    if old_file.exists():
                        old_file.unlink()
        except OSError:
            pass
    _MODEL_DIR.mkdir(parents=True, exist_ok=True)
    log("首次使用：正在从 ModelScope 下载 Audio8 0.1B 模型，请耐心等待...")
    for rel in AUDIO8_MODEL_FILES:
        _download_model_file(rel, log)
    if not _model_ready():
        raise RuntimeError("Audio8 模型下载不完整")
    log("Audio8 模型下载完成")
    return _MODEL_DIR


def _model_ready() -> bool:
    manifest_path = _MODEL_DIR / "runtime_manifest.json"
    if not manifest_path.exists():
        return False
    try:
        manifest_text = manifest_path.read_text(encoding="utf-8")
    except OSError:
        return False
    # 只接受 0.1B INT8 模型清单；避免旧 0.6B int4 被误判为已下载
    if "0.1b" not in manifest_text.lower() and "int8" not in manifest_text.lower():
        return False
    return all((_MODEL_DIR / name).exists() for name in AUDIO8_MODEL_FILES)


def ensure_default_voice(on_status=None):
    """使用模型自带的 reference_codes 自动创建内置默认音色 default。"""
    log = _status(on_status)
    manifest_path = _MODEL_DIR / "runtime_manifest.json"
    if not manifest_path.exists():
        raise RuntimeError("Audio8 模型清单不存在，无法创建默认音色")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    reference_codes_name = manifest.get("reference_codes") or "reference_codes.npy"
    reference_text = manifest.get("reference_text") or ""
    fingerprint = manifest.get("model_fingerprint") or ""
    if not reference_text:
        raise RuntimeError("Audio8 模型没有内置 reference_text，无法创建默认音色")

    voice_dir = _RUNTIME_DIR / "voices" / "default"
    meta_path = voice_dir / "meta.json"
    if meta_path.exists():
        try:
            old_meta = json.loads(meta_path.read_text(encoding="utf-8"))
            if old_meta.get("model_fingerprint") == fingerprint:
                return "default"
        except (OSError, json.JSONDecodeError):
            pass

    source_codes = _MODEL_DIR / reference_codes_name
    if not source_codes.exists():
        raise RuntimeError("Audio8 模型缺少内置 reference_codes.npy")
    voice_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source_codes, voice_dir / "codes.npy")
    meta = {
        "name": "default",
        "reference_text": reference_text,
        "dtype": "uint16",
        "sample_rate": int(manifest.get("sample_rate") or 44100),
        "model_fingerprint": fingerprint,
        "source_kind": "builtin_default",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (voice_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    log("已创建 Audio8 内置默认音色 default")
    return "default"


def start_local_service(on_status=None) -> str:
    log = _status(on_status)
    url = "http://127.0.0.1:8024"
    if is_audio8_available(url):
        return url

    runtime = ensure_runtime_downloaded(on_status=on_status)
    ensure_model_downloaded(on_status=on_status)
    ensure_default_voice(on_status=on_status)

    log("正在启动 Audio8 本地服务...")
    env = os.environ.copy()
    env.setdefault("ARKTTS_MODEL_DIR", str(_MODEL_DIR))
    env.setdefault("ARKTTS_PRECISION", "int8")
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
        # 服务已运行时，补齐注册所需模型文件，并确保内置 default 音色存在
        if (_MODEL_DIR / "runtime_manifest.json").exists():
            ensure_model_downloaded(on_status=on_status)
            ensure_default_voice(on_status=on_status)
        return url
    return start_local_service(on_status=on_status)
