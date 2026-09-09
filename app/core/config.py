"""运行环境与外部二进制定位（支持 Windows / macOS / 打包态）。"""
from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class BinaryPaths:
    ffmpeg: str
    ffprobe: str
    yt_dlp: str
    whisper_cli: str

    @classmethod
    def detect(cls) -> "BinaryPaths":
        return cls(
            ffmpeg=os.environ.get("FFMPEG_PATH") or _find_tool("ffmpeg"),
            ffprobe=os.environ.get("FFPROBE_PATH") or _find_tool("ffprobe"),
            yt_dlp=os.environ.get("YTDLP_PATH") or _find_tool("yt-dlp"),
            whisper_cli=os.environ.get("WHISPER_CLI_PATH") or _find_tool("whisper-cli"),
        )


def _is_windows() -> bool:
    return sys.platform.startswith("win") or os.name == "nt"


def _exe_name(name: str) -> str:
    return name + (".exe" if _is_windows() else "")


def _project_root() -> Path:
    # app/core/config.py -> 项目根目录
    return Path(__file__).resolve().parents[2]


def _is_frozen() -> bool:
    return getattr(sys, "frozen", False) or hasattr(sys, "_MEIPASS")


def _bundled_dir() -> Path | None:
    """仅打包态使用随包 resources/bin；开发态直接使用系统/Homebrew 二进制。"""
    if _is_frozen():
        if hasattr(sys, "_MEIPASS"):
            bundled = Path(sys._MEIPASS) / "resources" / "bin"
            if bundled.exists():
                return bundled
        bundled = Path(__file__).resolve().parents[3] / "resources" / "bin"
        if bundled.exists():
            return bundled
    return None


def _find_tool(name: str) -> str:
    # 1. 打包态：优先使用随包二进制
    bundled = _bundled_dir()
    if bundled is not None:
        candidate = bundled / _exe_name(name)
        if candidate.is_file():
            return str(candidate)

    # 2. macOS Homebrew ffmpeg-full（带 libass，字幕烧录必需）
    if name in ("ffmpeg", "ffprobe") and not _is_windows():
        full = Path(f"/opt/homebrew/opt/ffmpeg-full/bin/{name}")
        if full.is_file():
            return str(full)

    # 3. PATH（开发态正常使用 Homebrew/system 原版）
    found = shutil.which(_exe_name(name)) or shutil.which(name)
    if not found:
        raise RuntimeError(f"找不到外部程序: {name}，请先安装或设置对应 *_PATH 环境变量")
    return found
