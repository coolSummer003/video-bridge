"""AI 配音：基于 edge-tts 的神经网络语音合成。"""
from __future__ import annotations

import asyncio
import os

import edge_tts

VOICES = [
    # 情感类
    ("晓晓（情感女声·温柔）", "zh-CN-XiaoxiaoNeural"),
    # 元气类
    ("晓伊（元气少女·甜美）", "zh-CN-XiaoyiNeural"),
    # 活力/青年
    ("云希（活力青年·阳光）", "zh-CN-YunxiNeural"),
    # 解说/激情
    ("云健（解说男声·激情）", "zh-CN-YunjianNeural"),
    # 磁性/沉稳/新闻
    ("云扬（磁性男声·沉稳）", "zh-CN-YunyangNeural"),
    # 少年/青涩
    ("云夏（少年音·清爽）", "zh-CN-YunxiaNeural"),
    # 特色方言
    ("小北（东北话·特色女声）", "zh-CN-liaoning-XiaobeiNeural"),
    ("小妮（陕西话·特色女声）", "zh-CN-shaanxi-XiaoniNeural"),
    # 多语种
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
