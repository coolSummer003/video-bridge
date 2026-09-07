"""高级去重：双视频抽帧混合 / BGM 叠加。"""
from __future__ import annotations

import json
import os
import subprocess

from .config import BinaryPaths


def probe_video(path: str, ffprobe_bin: str) -> dict:
    cmd = [
        ffprobe_bin,
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height,avg_frame_rate,has_b_frames",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        path,
    ]
    proc = subprocess.run(cmd, check=True, capture_output=True, text=True)
    data = json.loads(proc.stdout)
    stream = (data.get("streams") or [{}])[0]
    fmt = data.get("format") or {}
    fps = 30
    avg = stream.get("avg_frame_rate") or "0/0"
    try:
        num, den = avg.split("/")
        if int(den) > 0:
            fps = round(int(num) / int(den))
            fps = max(1, min(120, fps))
    except Exception:
        fps = 30
    return {
        "width": int(stream.get("width") or 0),
        "height": int(stream.get("height") or 0),
        "fps": fps,
        "duration": float(fmt.get("duration") or 0),
        "has_audio": bool(stream.get("has_audio")),
    }


def has_audio_stream(path: str, ffprobe_bin: str) -> bool:
    cmd = [
        ffprobe_bin,
        "-v",
        "error",
        "-select_streams",
        "a",
        "-show_entries",
        "stream=index",
        "-of",
        "csv=p=0",
        path,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return bool(proc.stdout.strip())


def dedup_frame_mix(
    content_path: str,
    material_path: str,
    output_path: str,
    *,
    binaries: BinaryPaths | None = None,
    on_line: callable | None = None,
) -> str:
    """把素材 B 的帧交错插入内容 A，形成高帧率混合视频。

    类似 AB-Video-Deduplicator 的抽帧混合思路：在相同时间内，
    A/B 两路帧交替出现，输出帧率约为 A 的两倍。
    """
    bins = binaries or BinaryPaths.detect()
    info = probe_video(content_path, bins.ffprobe)
    if info["width"] <= 0 or info["height"] <= 0:
        raise RuntimeError("无法读取内容视频尺寸")
    width = info["width"] - (info["width"] % 2)
    height = info["height"] - (info["height"] % 2)
    source_fps = info["fps"] or 30
    target_fps = max(20, min(30, source_fps)) if source_fps <= 30 else 30
    output_fps = target_fps * 2
    duration = info["duration"] or 0

    filter_complex = (
        f"[0:v]fps={target_fps},setpts=PTS-STARTPTS[v0];"
        f"[1:v]scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},fps={target_fps},setpts=PTS-STARTPTS,"
        f"trim=duration={duration:.3f},setpts=PTS-STARTPTS[v1];"
        f"[v0][v1]interleave=2[vout]"
    )
    os.makedirs(os.path.dirname(os.path.abspath(output_path)) or ".", exist_ok=True)
    cmd = [
        bins.ffmpeg,
        "-y",
        "-i",
        content_path,
        "-stream_loop",
        "-1",
        "-i",
        material_path,
        "-filter_complex",
        filter_complex,
        "-map",
        "[vout]",
        "-map",
        "0:a?",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "19",
        "-r",
        str(output_fps),
        "-c:a",
        "aac",
        "-b:a",
        "192k",
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
        if on_line:
            on_line(line)
    ret = proc.wait()
    if ret != 0:
        raise RuntimeError(f"抽帧混合失败，退出码 {ret}")
    if not os.path.isfile(output_path):
        raise RuntimeError("抽帧混合未生成输出文件")
    return output_path


def add_background_music(
    video_path: str,
    bgm_path: str,
    output_path: str,
    *,
    volume: float = 0.18,
    binaries: BinaryPaths | None = None,
    on_line: callable | None = None,
) -> str:
    """在保留原声的同时叠加入口 BGM（音量较低）。"""
    bins = binaries or BinaryPaths.detect()
    os.makedirs(os.path.dirname(os.path.abspath(output_path)) or ".", exist_ok=True)
    filter_complex = (
        f"[0:a]volume=1.0[a0];"
        f"[1:a]volume={volume:.3f}[a1];"
        f"[a0][a1]amix=inputs=2:duration=first:dropout_transition=0[aout]"
    )
    cmd = [
        bins.ffmpeg,
        "-y",
        "-i",
        video_path,
        "-i",
        bgm_path,
        "-filter_complex",
        filter_complex,
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
        if on_line:
            on_line(line)
    ret = proc.wait()
    if ret != 0:
        raise RuntimeError(f"BGM 叠加失败，退出码 {ret}")
    if not os.path.isfile(output_path):
        raise RuntimeError("BGM 叠加未生成输出文件")
    return output_path


def dedup_random_segments(
    video_path: str,
    output_path: str,
    *,
    segment_count: int = 3,
    shuffle: bool = True,
    binaries: BinaryPaths | None = None,
    on_line: callable | None = None,
) -> str:
    """把视频切成 N 段，按随机顺序重新拼接，改变内容排列结构。"""
    bins = binaries or BinaryPaths.detect()
    info = probe_video(video_path, bins.ffprobe)
    duration = info["duration"]
    if duration <= 0:
        raise RuntimeError("无法读取视频时长，不能进行片段重排")
    count = max(2, min(8, int(segment_count)))
    seg_duration = duration / count
    indices = list(range(count))
    if shuffle:
        import random
        random.shuffle(indices)

    has_audio = has_audio_stream(video_path, bins.ffprobe)
    parts_v = []
    parts_a = []
    for i, seg_idx in enumerate(indices):
        start = seg_idx * seg_duration
        end = min(duration, (seg_idx + 1) * seg_duration)
        parts_v.append(
            f"[0:v]trim=start={start:.3f}:end={end:.3f},setpts=PTS-STARTPTS[v{i}]"
        )
        if has_audio:
            parts_a.append(
                f"[0:a]atrim=start={start:.3f}:end={end:.3f},asetpts=PTS-STARTPTS[a{i}]"
            )

    filter_parts = parts_v + parts_a
    v_labels = "".join(f"[v{i}]" for i in range(count))
    filter_parts.append(f"{v_labels}concat=n={count}:v=1:a=0[vout]")
    if has_audio:
        a_labels = "".join(f"[a{i}]" for i in range(count))
        filter_parts.append(f"{a_labels}concat=n={count}:v=0:a=1[aout]")
    filter_complex = ";".join(filter_parts)

    os.makedirs(os.path.dirname(os.path.abspath(output_path)) or ".", exist_ok=True)
    cmd = [
        bins.ffmpeg,
        "-y",
        "-i",
        video_path,
        "-filter_complex",
        filter_complex,
        "-map",
        "[vout]",
    ]
    if has_audio:
        cmd += ["-map", "[aout]", "-c:a", "aac", "-b:a", "192k"]
    cmd += [
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "19",
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
        if on_line:
            on_line(line)
    ret = proc.wait()
    if ret != 0:
        raise RuntimeError(f"片段重排失败，退出码 {ret}")
    if not os.path.isfile(output_path):
        raise RuntimeError("片段重排未生成输出文件")
    return output_path


def dedup_pip(
    video_path: str,
    overlay_path: str,
    output_path: str,
    *,
    overlay_scale: float = 0.25,
    binaries: BinaryPaths | None = None,
    on_line: callable | None = None,
) -> str:
    """在视频右下角叠加另一个小画面（画中画），改变画面结构。"""
    bins = binaries or BinaryPaths.detect()
    os.makedirs(os.path.dirname(os.path.abspath(output_path)) or ".", exist_ok=True)
    w = f"iw*{overlay_scale:.4f}"
    filter_complex = (
        f"[1:v]scale={w}:-2[ov];"
        f"[0:v][ov]overlay=W-w-20:H-h-20[vout]"
    )
    cmd = [
        bins.ffmpeg,
        "-y",
        "-i",
        video_path,
        "-i",
        overlay_path,
        "-filter_complex",
        filter_complex,
        "-map",
        "[vout]",
        "-map",
        "0:a?",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "19",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
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
        if on_line:
            on_line(line)
    ret = proc.wait()
    if ret != 0:
        raise RuntimeError(f"画中画叠加失败，退出码 {ret}")
    if not os.path.isfile(output_path):
        raise RuntimeError("画中画叠加未生成输出文件")
    return output_path

