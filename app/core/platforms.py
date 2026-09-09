"""视频平台识别与下载参数适配。"""
from __future__ import annotations

import re

PLATFORM_NAMES = {
    "auto": "自动检测",
    "douyin": "抖音",
    "bilibili": "Bilibili",
    "youtube": "YouTube",
    "other": "其他平台",
}

DOUYIN_PATTERNS = [
    re.compile(r"douyin\.com", re.I),
    re.compile(r"iesdouyin\.com", re.I),
    re.compile(r"v\.douyin\.com", re.I),
]

BILIBILI_PATTERNS = [
    re.compile(r"bilibili\.com", re.I),
    re.compile(r"b23\.tv", re.I),
]

YOUTUBE_PATTERNS = [
    re.compile(r"youtube\.com", re.I),
    re.compile(r"youtu\.be", re.I),
]


def detect_platform(url: str) -> str:
    """根据链接识别平台，返回 douyin / bilibili / youtube / other。"""
    if not url:
        return "other"
    for pat in DOUYIN_PATTERNS:
        if pat.search(url):
            return "douyin"
    for pat in BILIBILI_PATTERNS:
        if pat.search(url):
            return "bilibili"
    for pat in YOUTUBE_PATTERNS:
        if pat.search(url):
            return "youtube"
    return "other"


def platform_name(platform: str) -> str:
    return PLATFORM_NAMES.get(platform, platform)


URL_PATTERN = re.compile(r'https?://[^\s<>"\']+')


def extract_video_url(text: str) -> str | None:
    """从抖音/B站等分享文本中提取第一个可识别的视频链接。"""
    if not text:
        return None
    text = text.strip()
    # 如果用户直接粘贴了纯链接，直接返回
    if text.startswith(("http://", "https://")):
        return text
    for raw in URL_PATTERN.findall(text):
        url = raw.rstrip(".,;:!?，。；：！？、\"'")
        if detect_platform(url) != "other":
            return url
    return None


def platform_options() -> list[tuple[str, str]]:
    return [
        ("自动检测", "auto"),
        ("抖音", "douyin"),
        ("Bilibili", "bilibili"),
        ("YouTube", "youtube"),
        ("其他平台", "other"),
    ]
