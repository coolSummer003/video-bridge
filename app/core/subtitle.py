"""字幕生成：ffmpeg 抽音频 + whisper.cpp 转写为 SRT。"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile

from .config import BinaryPaths


def extract_audio(
    video_path: str,
    wav_path: str,
    *,
    ffmpeg_bin: str | None = None,
) -> str:
    bins = ffmpeg_bin or BinaryPaths.detect().ffmpeg
    os.makedirs(os.path.dirname(wav_path), exist_ok=True)
    cmd = [
        bins,
        "-y",
        "-i",
        video_path,
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
        wav_path,
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    return wav_path


def generate_srt(
    video_path: str,
    *,
    model_path: str,
    output_dir: str | None = None,
    language: str = "auto",
    binaries: BinaryPaths | None = None,
    on_line: callable | None = None,
) -> str:
    """从视频生成 SRT 字幕，返回 SRT 文件路径。"""
    bins = binaries or BinaryPaths.detect()
    out_dir = output_dir or os.path.dirname(os.path.abspath(video_path))
    os.makedirs(out_dir, exist_ok=True)
    stem = os.path.splitext(os.path.basename(video_path))[0]
    tmp_wav = os.path.join(out_dir, f".{stem}.tmp.wav")
    output_base = os.path.join(out_dir, f"{stem}.sub")
    try:
        extract_audio(video_path, tmp_wav, ffmpeg_bin=bins.ffmpeg)
        cmd = [
            bins.whisper_cli,
            "-m",
            model_path,
            "-f",
            tmp_wav,
            "-osrt",
            "-of",
            output_base,
            "-l",
            language,
            "-pp",
            "-np",
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
            raise RuntimeError(f"whisper-cli 字幕生成失败，退出码 {ret}")
        srt_path = output_base + ".srt"
        if not os.path.isfile(srt_path):
            raise RuntimeError("whisper-cli 未生成 SRT 文件")
        return srt_path
    finally:
        if os.path.exists(tmp_wav):
            try:
                os.remove(tmp_wav)
            except OSError:
                pass


def _escape_filter_path(path: str) -> str:
    """转义 FFmpeg filter 中 subtitles 文件名里的特殊字符。"""
    return (
        path.replace("\\", "\\\\")
        .replace("'", "\\'")
        .replace(":", "\\:")
        .replace(",", "\\,")
        .replace("[", "\\[")
        .replace("]", "\\]")
        .replace(";", "\\;")
    )


def burn_subtitles(
    video_path: str,
    srt_path: str,
    output_path: str | None = None,
    *,
    ffmpeg_bin: str | None = None,
    on_line: callable | None = None,
) -> str:
    """将 SRT 字幕烧录到视频画面，返回输出视频路径。"""
    if not os.path.isfile(video_path):
        raise FileNotFoundError(video_path)
    if not os.path.isfile(srt_path):
        raise FileNotFoundError(srt_path)
    bins = ffmpeg_bin or BinaryPaths.detect().ffmpeg
    out_dir = os.path.dirname(os.path.abspath(video_path))
    if not output_path:
        stem = os.path.splitext(os.path.basename(video_path))[0]
        output_path = os.path.join(out_dir, f"{stem}.subbed.mp4")
    os.makedirs(os.path.dirname(os.path.abspath(output_path)) or ".", exist_ok=True)
    # 校验字幕内容：空 SRT 或无效 SRT 会让 ffmpeg 报 Invalid data
    with open(srt_path, "r", encoding="utf-8-sig", errors="replace") as _f:
        srt_text = _f.read()
    if "-->" not in srt_text:
        raise RuntimeError("字幕文件为空或格式不正确，无法烧录；可能视频中没有识别到清晰人声")

    # 复制到临时安全路径，避免中文/空格/单引号/逗号等路径转义问题
    fd, tmp_srt = tempfile.mkstemp(prefix="vb_subtitle_", suffix=".srt")
    os.close(fd)
    try:
        shutil.copyfile(srt_path, tmp_srt)
        escaped = _escape_filter_path(tmp_srt)
        vf = f"subtitles=filename='{escaped}'"
        cmd = [
            bins,
            "-y",
            "-i",
            video_path,
            "-vf",
            vf,
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "20",
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
            raise RuntimeError(f"字幕烧录失败，退出码 {ret}")
        if not os.path.isfile(output_path):
            raise RuntimeError("字幕烧录未生成输出文件")
        return output_path
    finally:
        if os.path.exists(tmp_srt):
            try:
                os.remove(tmp_srt)
            except OSError:
                pass


def extract_subtitle_text(srt_path: str) -> str:
    """从 SRT 字幕文件中提取纯文本内容，去掉序号和时间轴。"""
    lines = []
    with open(srt_path, "r", encoding="utf-8-sig", errors="replace") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            if line.isdigit():
                continue
            if "-->" in line:
                continue
            lines.append(line)
    return "\n".join(lines).strip()

