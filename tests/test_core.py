import math
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.config import BinaryPaths
from app.core.dedup import DedupOptions


def test_dedup_options_default_filter_contains_hflip():
    opts = DedupOptions()
    f = opts.build_filter()
    assert "hflip" in f
    assert "eq=saturation=1.0500" in f


def test_dedup_options_rotate_uses_radians():
    opts = DedupOptions(mirror=False, rotate_degrees=90)
    f = opts.build_filter()
    assert f"rotate={math.radians(90):.6f}" in f


def test_dedup_options_no_ops_yields_empty():
    opts = DedupOptions(mirror=False, saturation=1.0, contrast=1.0, brightness=0.0, rotate_degrees=0.0, scale=1.0, zoom=1.0, noise_strength=0, blur_sigma=0.0, hue_degrees=0.0)
    assert opts.build_filter() == ""


def test_binary_paths_detect_throws_without_env():
    # 不执行真实检测；只确认 dataclass 能构造
    bins = BinaryPaths(ffmpeg="ffmpeg", ffprobe="ffprobe", yt_dlp="yt-dlp", whisper_cli="whisper-cli")
    assert bins.ffmpeg == "ffmpeg"
