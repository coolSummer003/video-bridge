"""AI 配音：基于 edge-tts 的神经网络语音合成。"""
from __future__ import annotations

import asyncio
import os

import edge_tts

VOICES = [
    ("晓晓（中文女声）", "zh-CN-XiaoxiaoNeural"),
    ("云希（中文男声）", "zh-CN-YunxiNeural"),
    ("云扬（中文男声·新闻）", "zh-CN-YunyangNeural"),
    ("晓伊（中文女声·甜）", "zh-CN-XiaoyiNeural"),
    ("Aria（英文女声）", "en-US-AriaNeural"),
    ("Guy（英文男声）", "en-US-GuyNeural"),
    ("Nanami（日文女声）", "ja-JP-NanamiNeural"),
]

RATES = ["-50%", "-25%", "+0%", "+25%", "+50%"]


def voice_options() -> list[tuple[str, str]]:
    return list(VOICES)


def text_to_speech(
    text: str,
    output_path: str,
    *,
    voice: str = "zh-CN-XiaoxiaoNeural",
    rate: str = "+0%",
    on_status: callable | None = None,
) -> str:
    """使用 Edge-TTS 将文本合成为 MP3 音频。"""
    text = (text or "").strip()
    if not text:
        raise ValueError("配音文本不能为空")
    output_path = os.path.abspath(output_path)
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    if on_status:
        on_status("正在连接 Edge-TTS 语音服务...")
    asyncio.run(_run_tts(text, output_path, voice=voice, rate=rate))

    if not os.path.isfile(output_path):
        raise RuntimeError("配音生成失败：未生成音频文件")
    if on_status:
        on_status(f"配音完成: {output_path}")
    return output_path


async def _run_tts(text: str, output_path: str, *, voice: str, rate: str) -> None:
    communicate = edge_tts.Communicate(text, voice=voice, rate=rate)
    await communicate.save(output_path)
