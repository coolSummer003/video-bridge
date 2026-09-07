"""视频去重/二创：基于 FFmpeg 的可配置滤镜链（升级版）。"""
from __future__ import annotations

import math
import os
import random
import subprocess
from dataclasses import dataclass

from .config import BinaryPaths


@dataclass
class DedupOptions:
    mirror: bool = True
    saturation: float = 1.05
    contrast: float = 1.03
    brightness: float = 0.0
    rotate_degrees: float = 0.0
    scale: float = 1.0
    zoom: float = 1.0
    noise_strength: int = 0
    blur_sigma: float = 0.0
    hue_degrees: float = 0.0
    video_bitrate_k: str = "4000k"
    audio_bitrate: str = "192k"
    crf: int = 23

    def build_filter(self) -> str:
        parts: list[str] = []
        if self.mirror:
            parts.append("hflip")
        if abs(self.rotate_degrees) > 0.001:
            rad = math.radians(self.rotate_degrees)
            parts.append(f"rotate={rad:.6f}:ow=iw:oh=ih")
        if abs(self.zoom - 1.0) > 0.001:
            z = self.zoom
            parts.append(
                f"scale=floor(iw*{z:.6f}/2)*2:floor(ih*{z:.6f}/2)*2,"
                f"crop=floor(iw/{z:.6f}/2)*2:floor(ih/{z:.6f}/2)*2"
            )
        if abs(self.scale - 1.0) > 0.001:
            w = f"ceil(iw*{self.scale}/2)*2"
            h = f"ceil(ih*{self.scale}/2)*2"
            parts.append(f"scale={w}:{h}")
        if (
            abs(self.saturation - 1.0) > 0.001
            or abs(self.contrast - 1.0) > 0.001
            or abs(self.brightness) > 0.001
        ):
            parts.append(
                f"eq=saturation={self.saturation:.4f}:"
                f"contrast={self.contrast:.4f}:"
                f"brightness={self.brightness:.4f}"
            )
        if abs(self.hue_degrees) > 0.001:
            parts.append(f"hue=h={self.hue_degrees:.4f}")
        if self.noise_strength > 0:
            parts.append(f"noise=alls={self.noise_strength}:allf=t")
        if self.blur_sigma > 0.001:
            parts.append(f"gblur=sigma={self.blur_sigma:.4f}")
        return ",".join(parts)


def options_from_strength(
    strength: str,
    *,
    mirror: bool = True,
    saturation: float = 1.05,
    contrast: float = 1.03,
    randomize: bool = False,
) -> DedupOptions:
    """根据档位生成去重参数；randomize 时每次生成略不同变体。"""
    strength = strength or "中度"
    if strength == "轻度":
        opts = DedupOptions(
            mirror=mirror,
            saturation=saturation,
            contrast=contrast,
            brightness=0.0,
            rotate_degrees=0.0,
            zoom=1.0,
            noise_strength=0,
            blur_sigma=0.0,
            hue_degrees=0.0,
        )
    elif strength == "中度":
        opts = DedupOptions(
            mirror=mirror,
            saturation=saturation,
            contrast=contrast,
            brightness=0.01,
            rotate_degrees=0.0,
            zoom=1.02,
            noise_strength=4,
            blur_sigma=0.2,
            hue_degrees=0.5,
        )
    else:  # 重度
        opts = DedupOptions(
            mirror=mirror,
            saturation=saturation,
            contrast=contrast,
            brightness=0.015,
            rotate_degrees=0.8,
            zoom=1.04,
            noise_strength=8,
            blur_sigma=0.4,
            hue_degrees=1.5,
        )

    if randomize:
        opts.saturation = round(max(0.85, min(1.4, opts.saturation + random.uniform(-0.05, 0.08))), 4)
        opts.contrast = round(max(0.85, min(1.4, opts.contrast + random.uniform(-0.04, 0.06))), 4)
        opts.brightness = round(max(-0.05, min(0.08, opts.brightness + random.uniform(-0.01, 0.02))), 4)
        opts.hue_degrees = round(max(-5.0, min(5.0, opts.hue_degrees + random.uniform(-1.0, 1.0))), 4)
        if opts.zoom > 1.0:
            opts.zoom = round(max(1.0, min(1.08, opts.zoom + random.uniform(-0.01, 0.02))), 4)
        if opts.noise_strength > 0:
            opts.noise_strength = max(1, min(12, opts.noise_strength + random.randint(-2, 3)))
        if opts.blur_sigma > 0.0:
            opts.blur_sigma = round(max(0.0, min(0.8, opts.blur_sigma + random.uniform(-0.1, 0.15))), 4)
    return opts


def dedup_video(
    input_path: str,
    output_path: str,
    options: DedupOptions | None = None,
    *,
    binaries: BinaryPaths | None = None,
    on_line: callable | None = None,
) -> str:
    bins = binaries or BinaryPaths.detect()
    opts = options or DedupOptions()
    os.makedirs(os.path.dirname(os.path.abspath(output_path)) or ".", exist_ok=True)
    filters = opts.build_filter()
    cmd = [
        bins.ffmpeg,
        "-y",
        "-i",
        input_path,
        "-vf",
        filters,
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        str(opts.crf),
        "-maxrate",
        opts.video_bitrate_k,
        "-bufsize",
        "8000k",
        "-c:a",
        "aac",
        "-b:a",
        opts.audio_bitrate,
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
        raise RuntimeError(f"ffmpeg 处理失败，退出码 {ret}")
    if not os.path.isfile(output_path):
        raise RuntimeError("ffmpeg 未生成输出文件")
    return output_path
