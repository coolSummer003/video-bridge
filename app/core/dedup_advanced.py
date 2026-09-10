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
    ratio: int = 7,
    binaries: BinaryPaths | None = None,
    on_line: callable | None = None,
) -> str:
    """把素材 B 的帧稀疏插入内容 A，形成高帧率混合视频。

    A:B = ratio:1（默认 7:1，输出 240fps）。B 帧只占极小比例、
    每帧仅停留约 4ms，正常播放几乎不可感知；但文件数据特征与
    源视频完全不同。ratio=1(60fps)/3(120fps) 去重更强但闪烁可见。
    """
    bins = binaries or BinaryPaths.detect()
    info = probe_video(content_path, bins.ffprobe)
    if info["width"] <= 0 or info["height"] <= 0:
        raise RuntimeError("无法读取内容视频尺寸")
    width = info["width"] - (info["width"] % 2)
    height = info["height"] - (info["height"] % 2)
    if ratio not in (1, 3, 7):
        raise ValueError("ratio 只支持 1 / 3 / 7（分别输出 60 / 120 / 240fps）")
    output_fps = 30 * (ratio + 1)
    con_fps = 30 * ratio
    mat_fps = 30
    duration = info["duration"] or 0

    filter_complex = (
        f"[0:v]fps={con_fps},setsar=1,setpts=PTS-STARTPTS,format=yuv420p[v0];"
        f"[1:v]scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},fps={mat_fps},setsar=1,setpts=PTS-STARTPTS,"
        f"format=yuv420p,trim=duration={duration:.3f},setpts=PTS-STARTPTS[v1];"
        f"[v0][v1]interleave=2,format=yuv420p[vout]"
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
        "-t",
        f"{duration:.3f}",
        "-movflags",
        "+faststart",
        output_path,
    ]
    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError:
        raise RuntimeError("找不到 ffmpeg，请先安装或在设置中指定路径")
    log_tail = proc.stdout.strip().splitlines()[-25:] if proc.stdout else []
    if on_line:
        for line in log_tail:
            on_line(line)
    if proc.returncode != 0:
        detail = "\n".join(log_tail[-8:]) if log_tail else ""
        raise RuntimeError(f"抽帧混合失败，退出码 {proc.returncode}\n{detail}")
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
    opacity: float = 0.03,
    binaries: BinaryPaths | None = None,
    on_line: callable | None = None,
) -> str:
    """隐形双视频混合：素材 B 全屏等尺寸、极低透明度混入 A。

    opacity 默认 0.03（3%）：逐像素都被 B 轻微扰动，
    人眼几乎不可见；平台指纹/压缩数据却完全改变。
    opacity 上限 0.10，超过则开始能看出叠影。
    """
    bins = binaries or BinaryPaths.detect()
    if not 0.0 < opacity <= 0.10:
        raise ValueError("opacity 必须在 (0, 0.10] 之间")
    info = probe_video(video_path, bins.ffprobe)
    width = int(info.get("width") or 0)
    height = int(info.get("height") or 0)
    if width <= 0 or height <= 0:
        raise RuntimeError("无法读取视频尺寸，不能进行隐形混合")
    width -= width % 2
    height -= height % 2
    fps = int(info.get("fps") or 30)
    duration = float(info.get("duration") or 0)
    if duration <= 0:
        raise RuntimeError("无法读取视频时长，不能进行隐形混合")
    os.makedirs(os.path.dirname(os.path.abspath(output_path)) or ".", exist_ok=True)
    # blend 要求两路分辨率/格式/SAR/帧率完全一致，先把 B 严格对齐到 A
    filter_complex = (
        f"[0:v]scale={width}:{height},setsar=1,fps={fps},format=yuv420p[base];"
        f"[1:v]scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},setsar=1,fps={fps},format=yuv420p[ov0];"
        f"[base][ov0]blend=all_expr='A*{1.0 - opacity:.4f}+B*{opacity:.4f}',format=yuv420p[vout]"
    )
    cmd = [
        bins.ffmpeg,
        "-y",
        "-i",
        video_path,
        "-stream_loop",
        "-1",
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
        if on_line:
            on_line(line)
    ret = proc.wait()
    if ret != 0:
        raise RuntimeError(f"隐形混合失败，退出码 {ret}")
    if not os.path.isfile(output_path):
        raise RuntimeError("隐形混合未生成输出文件")
    return output_path


def dedup_structure_auto(
    video_path: str,
    output_path: str,
    *,
    segment_count: int = 3,
    transition: str = "fade",
    background_blur: bool = True,
    binaries: BinaryPaths | None = None,
    on_line: callable | None = None,
) -> str:
    """单遍自动处理：竖屏模糊拓边 + N 段转场拼接。

    - 竖屏视频（高大于宽）自动加 16:9 模糊背景。
    - 长视频自动切成 N 段，用 xfade 转场拼接（淡入淡出 / 闪白）。
    - 全部在一条 filter_complex 里单遍执行，音画同步。
    """
    bins = binaries or BinaryPaths.detect()
    info = probe_video(video_path, bins.ffprobe)
    width = int(info.get("width") or 0)
    height = int(info.get("height") or 0)
    duration = float(info.get("duration") or 0)
    if width <= 0 or height <= 0 or duration <= 0:
        raise RuntimeError("无法读取视频尺寸或时长，不能进行自动结构处理")
    audio = has_audio_stream(video_path, bins.ffprobe)

    os.makedirs(os.path.dirname(os.path.abspath(output_path)) or ".", exist_ok=True)
    count = max(1, min(6, int(segment_count)))
    trans = "fadewhite" if transition == "fadewhite" else "fade"
    trans_dur = min(0.6, duration / max(2, count) / 2)

    source_label = "src"
    filter_parts = []
    if background_blur and height > width:
        # 竖屏 -> 先生成 16:9 模糊背景并叠加前景
        filter_parts.append(
            f"[0:v]split[v1][v2];"
            f"[v1]scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720,boxblur=20:2[bg];"
            f"[v2]scale=720:-2,format=yuv420p[fg];"
            f"[bg][fg]overlay=(W-w)/2:(H-h)/2,format=yuv420p[{source_label}]"
        )
    else:
        filter_parts.append(f"[0:v]scale=trunc(iw/2)*2:trunc(ih/2)*2,format=yuv420p[{source_label}]")

    current_a = "0:a"
    pieces_v: list[str] = []
    pieces_a: list[str] = []
    # 中间滤镜输出只能被消费一次: split 出 N 路再分别 trim
    if count > 1:
        split_outs = "".join(f"[s{i}]" for i in range(count))
        filter_parts.append(f"[{source_label}]split={count}{split_outs}")
        src_ref = [f"s{i}" for i in range(count)]
    else:
        src_ref = [source_label]
    for i in range(count):
        start = duration * i / count
        end = duration * (i + 1) / count
        pieces_v.append(
            f"[{src_ref[i]}]trim=start={start:.3f}:end={end:.3f},setpts=PTS-STARTPTS[v{i}]"
        )
        if audio:
            pieces_a.append(
                f"[{current_a}]atrim=start={start:.3f}:end={end:.3f},asetpts=PTS-STARTPTS[a{i}]"
            )
    filter_parts += pieces_v + pieces_a

    if count == 1:
        v_out, a_out = f"[v0]", ("[a0]" if audio else None)
    else:
        for i in range(1, count):
            prev_v = "v0" if i == 1 else f"x{i - 1}"
            offset = i * (duration / count) - i * trans_dur
            filter_parts.append(
                f"[{prev_v}][v{i}]xfade=transition={trans}:"
                f"duration={trans_dur:.3f}:offset={offset:.3f}[x{i}]"
            )
            if audio:
                prev_a = "a0" if i == 1 else f"y{i - 1}"
                filter_parts.append(
                    f"[{prev_a}][a{i}]acrossfade=d={trans_dur:.3f}:c1=tri:c2=tri[y{i}]"
                )
        v_out = f"[x{count - 1}]"
        a_out = f"[y{count - 1}]" if audio else None

    cmd = [
        bins.ffmpeg,
        "-y",
        "-i",
        video_path,
        "-filter_complex",
        ";".join(filter_parts),
        "-map",
        v_out,
    ]
    if a_out:
        cmd += ["-map", a_out, "-c:a", "aac", "-b:a", "192k"]
    cmd += [
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "19",
        "-pix_fmt",
        "yuv420p",
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
        raise RuntimeError(f"自动结构处理失败，退出码 {ret}")
    if not os.path.isfile(output_path):
        raise RuntimeError("自动结构处理未生成输出文件")
    return output_path

