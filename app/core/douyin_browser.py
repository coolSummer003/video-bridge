"""抖音专用下载：用 Playwright 打开视频页，拦截真实视频流并保存。"""
from __future__ import annotations

import os
import re
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

_ILLEGAL = re.compile(r'[\\/:*?"<>|\r\n\t]+')


def _safe_name(text: str, fallback: str) -> str:
    text = _ILLEGAL.sub(" ", text or "").strip()
    text = re.sub(r"\s+", " ", text)
    return (text[:80] or fallback).strip()


_LAUNCH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--autoplay-policy=no-user-gesture-required",
]


def _launch_browser(p, log):
    """按优先级启动浏览器：内置 Chromium → 系统 Chrome → 系统 Edge。

    打包版通常不带 Playwright Chromium，此时回退到系统浏览器。
    """
    attempts = [
        ("内置 Chromium", {}),
        ("系统 Chrome", {"channel": "chrome"}),
        ("系统 Edge", {"channel": "msedge"}),
    ]
    last_error = None
    for label, extra in attempts:
        try:
            browser = p.chromium.launch(headless=True, args=_LAUNCH_ARGS, **extra)
            log(f"使用浏览器: {label}")
            return browser
        except Exception as exc:
            last_error = exc
            log(f"{label} 启动失败，尝试下一个...")
    raise RuntimeError(f"无法启动浏览器（需要 Chromium / Chrome / Edge）：{last_error}")


def download_douyin_video(
    url: str,
    output_dir: str,
    *,
    on_status: callable | None = None,
    timeout_seconds: int = 45,
) -> str:
    """打开抖音视频页，拦截浏览器真实加载的视频流并保存为 MP4。"""
    os.makedirs(output_dir, exist_ok=True)
    log = on_status or (lambda _m: None)

    with sync_playwright() as p:
        browser = _launch_browser(p, log)
        try:
            ctx = browser.new_context(user_agent=UA, viewport={"width": 1280, "height": 800})
            page = ctx.new_page()
            candidates: dict[str, int] = {}

            def on_response(resp):
                try:
                    headers = resp.headers or {}
                    ctype = headers.get("content-type", "")
                    if "video" not in ctype:
                        return
                    # 只接受真实视频 CDN，排除抖音静态占位资源
                    if "douyinvod.com" not in resp.url:
                        return
                    size = int(headers.get("content-length", "0") or 0)
                    candidates[resp.url] = max(size, candidates.get(resp.url, 0))
                except Exception:
                    pass

            page.on("response", on_response)
            log("正在打开抖音视频页...")
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            log("等待视频流加载...")
            _try_trigger_playback(page)

            deadline = time.time() + timeout_seconds
            first_seen = None
            while time.time() < deadline:
                page.wait_for_timeout(1000)
                if not candidates:
                    continue
                if first_seen is None:
                    first_seen = time.time()
                best_size = max(candidates.values())
                waited = time.time() - first_seen
                # 大文件出现后可提前结束，否则多等几秒收集全部候选
                if best_size >= 1_000_000 and waited >= 3:
                    break
                if waited >= 8:
                    break
            if not candidates:
                _try_trigger_playback(page, scroll=True)
                deadline = time.time() + 15
                while time.time() < deadline and not candidates:
                    page.wait_for_timeout(1000)

            if not candidates:
                raise RuntimeError("未能捕获抖音视频流，可能是私密/已删除/需要登录的视频")

            best_url = max(candidates, key=lambda u: candidates[u])
            log(f"已捕获视频流（{candidates[best_url] or '未知'} 字节），开始下载...")
            resp = ctx.request.get(
                best_url,
                headers={"Referer": "https://www.douyin.com/"},
                timeout=180000,
            )
            if resp.status != 200:
                raise RuntimeError(f"视频流下载失败，HTTP {resp.status}")
            data = resp.body()
            if len(data) < 10000:
                raise RuntimeError("视频流数据异常，文件过小")

            title = _safe_name(page.title() or "", "douyin_video")
            video_id = ""
            m = re.search(r"/video/(\d+)", page.url)
            if m:
                video_id = m.group(1)
            filename = f"{title} [{video_id}].mp4" if video_id else f"{title}.mp4"
            path = os.path.join(output_dir, filename)
            with open(path, "wb") as f:
                f.write(data)
            log(f"抖音视频下载完成: {path}")
            return path
        finally:
            browser.close()


def _try_trigger_playback(page, scroll: bool = False):
    try:
        page.evaluate("() => { const v = document.querySelector('video'); if (v) { v.muted = true; v.play && v.play().catch(()=>{}); } }")
    except Exception:
        pass
    try:
        page.mouse.click(640, 400)
    except Exception:
        pass
    if scroll:
        try:
            page.mouse.wheel(0, 600)
            page.wait_for_timeout(1500)
            page.mouse.wheel(0, 900)
        except Exception:
            pass
