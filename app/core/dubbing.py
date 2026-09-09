"""本地配音：基于 Piper TTS 的离线神经网络语音合成。"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from piper.download_voices import download_voice

from .config import BinaryPaths

# Piper 中文语音模型
VOICES = [
    ("huayan（中文·推荐）", "zh_CN-huayan-medium"),
    ("chaowen（中文男声·播报感）", "zh_CN-chaowen-medium"),
    ("xiao_ya（中文女声·柔和）", "zh_CN-xiao_ya-medium"),
    ("huayan-x_low（中文·轻量低配）", "zh_CN-huayan-x_low"),
]

RATES = ["-50%", "-25%", "+0%", "+25%", "+50%"]


def voice_options() -> list[tuple[str, str]]:
    return list(VOICES)


def _model_dir() -> Path:
    """Piper 模型统一存放在项目 models/piper 目录。"""
    root = Path(__file__).resolve().parents[2]
    return root / "models" / "piper"


def _ensure_voice(voice: str) -> tuple[Path, Path]:
    """确保模型已下载，返回 (onnx 路径, json 配置路径)。"""
    model_dir = _model_dir()
    model_dir.mkdir(parents=True, exist_ok=True)
    onnx_path = model_dir / f"{voice}.onnx"
    config_path = model_dir / f"{voice}.onnx.json"
    if not onnx_path.exists() or not config_path.exists():
        download_voice(voice, model_dir)
    if not onnx_path.exists():
        raise RuntimeError(f"Piper 模型下载失败: {voice}")
    return onnx_path, config_path


def _rate_to_length_scale(rate: str) -> float:
    """把 +0% 这类语速值粗略映射到 Piper length_scale。"""
    rate_map = {
        "-50%": 1.5,
        "-25%": 1.25,
        "+0%": 1.0,
        "+25%": 0.85,
        "+50%": 0.72,
    }
    return rate_map.get(rate, 1.0)


def text_to_speech(
    text: str,
    output_path: str,
    *,
    voice: str = "zh_CN-huayan-medium",
    rate: str = "+0%",
    on_status: callable | None = None,
) -> str:
    """使用 Piper TTS 将文本合成为音频（支持 .wav/.mp3）。"""
    text = (text or "").strip()
    if not text:
        raise ValueError("配音文本不能为空")
    output_path = os.path.abspath(output_path)
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    if on_status:
        on_status(f"检查 Piper 语音模型: {voice}")
    onnx_path, config_path = _ensure_voice(voice)

    # Piper 输出 WAV；若用户要 mp3，则先生成临时 wav 再转码
    need_mp3 = output_path.lower().endswith(".mp3")
    wav_path = output_path
    if need_mp3:
        fd, wav_path = tempfile.mkstemp(prefix="vb_piper_", suffix=".wav")
        os.close(fd)

    try:
        if on_status:
            on_status("正在使用本地 Piper 模型合成语音...")
        with tempfile.NamedTemporaryFile(
            "w", suffix=".txt", encoding="utf-8", delete=False
        ) as tmp_text:
            tmp_text.write(text)
            tmp_text_path = tmp_text.name

        try:
            cmd = [
                "piper",
                "-m",
                str(onnx_path),
                "-c",
                str(config_path),
                "-i",
                tmp_text_path,
                "-f",
                str(wav_path),
                "--length-scale",
                str(_rate_to_length_scale(rate)),
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
            if proc.returncode != 0:
                raise RuntimeError(f"Piper 合成失败: {proc.stderr[-500:]}")
        finally:
            try:
                os.remove(tmp_text_path)
            except OSError:
                pass

        if not os.path.isfile(wav_path) or os.path.getsize(wav_path) == 0:
            raise RuntimeError("Piper 未生成有效音频文件")

        if need_mp3:
            bins = BinaryPaths.detect()
            convert = subprocess.run(
                [
                    bins.ffmpeg,
                    "-y",
                    "-i",
                    wav_path,
                    "-codec:a",
                    "libmp3lame",
                    "-qscale:a",
                    "4",
                    output_path,
                ],
                capture_output=True,
                text=True,
                timeout=180,
            )
            if convert.returncode != 0:
                raise RuntimeError(f"音频转 MP3 失败: {convert.stderr[-300:]}")
    finally:
        if need_mp3 and wav_path != output_path and os.path.exists(wav_path):
            try:
                os.remove(wav_path)
            except OSError:
                pass

    if on_status:
        on_status(f"配音完成: {output_path}")
    return output_path
