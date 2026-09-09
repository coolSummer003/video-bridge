"""视频下载：基于 yt-dlp CLI。"""
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass

from .config import BinaryPaths
from .platforms import detect_platform, platform_name


@dataclass
class DownloadResult:
    source_url: str
    filepath: str
    title: str = ""
    webpage_url: str = ""


def download_video(
    url: str,
    output_dir: str,
    *,
    platform: str | None = None,
    cookies_file: str | None = None,
    cookies_from_browser: str | None = None,
    binaries: BinaryPaths | None = None,
    format_selector: str = "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/bv*+ba/b",
    on_line: callable | None = None,
) -> DownloadResult:
    """下载单个公开视频。

    使用 yt-dlp 的 after_move print 输出最终文件绝对路径。
    """
    if not url:
        raise ValueError("URL 不能为空")
    detected = platform or detect_platform(url)
    if on_line:
        on_line(f"平台识别: {platform_name(detected)}")
    os.makedirs(output_dir, exist_ok=True)
    bins = binaries or BinaryPaths.detect()
    output_template = os.path.join(output_dir, "%(title).100B [%(id)s].%(ext)s")
    cmd = [
        bins.yt_dlp,
        "--no-playlist",
        "--newline",
        "--no-warnings",
    ]
    if cookies_file:
        if not os.path.isfile(cookies_file):
            raise FileNotFoundError(f"Cookie 文件不存在: {cookies_file}")
        cmd += ["--cookies", cookies_file]
    if cookies_from_browser:
        cmd += ["--cookies-from-browser", cookies_from_browser]
    cmd += [
        "-f",
        format_selector,
        "-o",
        output_template,
        "--print",
        "after_move:filepath",
        "--",
        url,
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
    last_path: str | None = None
    for line in proc.stdout:
        line = line.rstrip("\n")
        if on_line:
            on_line(line)
        if line and os.path.exists(line):
            last_path = line
    ret = proc.wait()
    if ret != 0:
        raise RuntimeError(f"yt-dlp 下载失败，退出码 {ret}")
    if not last_path or not os.path.isfile(last_path):
        raise RuntimeError("yt-dlp 执行完成但没有得到输出文件路径")
    return DownloadResult(source_url=url, filepath=last_path)
