"""配音视频合成辅助：用 Audio8 生成的音频替换视频原声。"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile

from .audio8 import text_to_speech_audio8
from .config import BinaryPaths
from .subtitle import parse_srt


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


def dub_srt_to_video(
    srt_path: str,
    video_path: str,
    output_path: str,
    *,
    voice_name: str = "default",
    base_url: str = "http://127.0.0.1:8024",
    binaries: BinaryPaths | None = None,
    on_status: callable | None = None,
) -> str:
    """按 SRT 时间轴逐句生成配音，再与原视频对齐合成。"""
    bins = binaries or BinaryPaths.detect()
    cues = parse_srt(srt_path)
    if not cues:
        raise RuntimeError("字幕文件没有可用字幕内容")

    # 读取视频时长
    probe = subprocess.run(
        [bins.ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "json", video_path],
        capture_output=True,
        text=True,
        check=True,
    )
    duration = float((json.loads(probe.stdout).get("format") or {}).get("duration") or 0)
    if duration <= 0:
        raise RuntimeError("无法读取视频时长，不能同步配音")

    tmpdir = tempfile.mkdtemp(prefix="vb_dub_srt_")
    try:
        segments: list[tuple[str, float]] = []
        for idx, cue in enumerate(cues):
            seg_path = os.path.join(tmpdir, f"seg_{idx:04d}.wav")
            if on_status:
                on_status(f"正在生成第 {idx + 1}/{len(cues)} 句配音...")
            text_to_speech_audio8(
                cue.text,
                seg_path,
                base_url=base_url,
                voice_name=voice_name,
                on_status=None,
            )
            segments.append((seg_path, cue.start))

        timeline = os.path.join(tmpdir, "timeline.wav")
        cmd = [
            bins.ffmpeg,
            "-y",
            "-f",
            "lavfi",
            "-t",
            f"{duration:.3f}",
            "-i",
            "anullsrc=channel_layout=mono:sample_rate=44100",
        ]
        for seg_path, _start in segments:
            cmd += ["-i", seg_path]

        filter_parts = ["[0:a]anull[base]"]
        mix_labels = ["[base]"]
        for idx, (seg_path, start) in enumerate(segments, start=1):
            delay_ms = max(0, int(start * 1000))
            filter_parts.append(f"[{idx}:a]adelay={delay_ms}:all=1[s{idx}]")
            mix_labels.append(f"[s{idx}]")
        filter_parts.append(
            "".join(mix_labels)
            + f"amix=inputs={len(mix_labels)}:duration=first:dropout_transition=0:normalize=0[aout]"
        )
        cmd += [
            "-filter_complex",
            ";".join(filter_parts),
            "-map",
            "[aout]",
            "-t",
            f"{duration:.3f}",
            "-c:a",
            "pcm_s16le",
            timeline,
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(f"字幕时间轴合成失败: {proc.stderr[-500:]}")

        return replace_video_audio(
            video_path,
            timeline,
            output_path,
            binaries=bins,
            on_status=on_status,
        )
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

