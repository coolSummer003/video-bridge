"""配音视频合成辅助：用 Audio8 生成的音频替换视频原声。"""
from __future__ import annotations

import json
import os
import subprocess

from .config import BinaryPaths


def replace_video_audio(
    video_path: str,
    audio_path: str,
    output_path: str,
    *,
    binaries: BinaryPaths | None = None,
    on_status: callable | None = None,
) -> str:
    """用配音音频替换视频原声；若配音比视频短则自动补静音，比视频长则裁剪。"""
    bins = binaries or BinaryPaths.detect()
    probe = subprocess.run(
        [
            bins.ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            video_path,
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(probe.stdout)
    duration = float((data.get("format") or {}).get("duration") or 0)
    if duration <= 0:
        raise RuntimeError("无法读取视频时长，不能替换配音")

    os.makedirs(os.path.dirname(os.path.abspath(output_path)) or ".", exist_ok=True)
    if on_status:
        on_status("正在将配音替换到视频中...")

    cmd = [
        bins.ffmpeg,
        "-y",
        "-i",
        video_path,
        "-i",
        audio_path,
        "-filter_complex",
        "[1:a]apad[aout]",
        "-map",
        "0:v",
        "-map",
        "[aout]",
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-t",
        f"{duration:.3f}",
        "-movflags",
        "+faststart",
        output_path,
    ]
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert proc.stdout is not None
    for line in proc.stdout:
        line = line.rstrip("\n")
        if on_status:
            on_status(line)
    ret = proc.wait()
    if ret != 0:
        raise RuntimeError(f"替换配音失败，退出码 {ret}")
    if not os.path.isfile(output_path):
        raise RuntimeError("替换配音未生成输出文件")
    if on_status:
        on_status(f"配音视频完成: {output_path}")
    return output_path
