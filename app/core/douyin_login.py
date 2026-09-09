"""抖音扫码登录：用户扫码后自动保存登录 Cookie。"""
from __future__ import annotations

import os
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

from .douyin_cookie import save_cookies_netscape

LOGIN_COOKIE_NAMES = ("sessionid", "sessionid_ss", "sid_tt", "sid_guard")


def douyin_login(output_path: str | None = None, timeout_seconds: int = 180) -> str:
    """打开抖音网页登录窗口，等待用户扫码登录后保存 Cookie。

    注意：会弹出一个真实 Chromium 窗口，用户需要用手机抖音扫码。
    """
    output_path = output_path or str(Path(__file__).resolve().parents[2] / "models" / "douyin_login_cookies.txt")
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )
        try:
            ctx = browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
                viewport={"width": 1280, "height": 860},
            )
            page = ctx.new_page()
            page.goto("https://www.douyin.com/", wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(2000)

            # 尝试点击右上角“登录”，打开扫码弹窗
            try:
                page.get_by_text("登录", exact=True).first.click(timeout=6000)
                page.wait_for_timeout(3000)
            except Exception:
                pass

            deadline = time.time() + timeout_seconds
            logged_in = False
            while time.time() < deadline:
                cookies = ctx.cookies()
                if any(
                    c.get("name") in LOGIN_COOKIE_NAMES and c.get("value")
                    for c in cookies
                ):
                    save_cookies_netscape(cookies, output_path)
                    logged_in = True
                    break
                page.wait_for_timeout(2000)

            if not logged_in:
                raise TimeoutError("等待抖音扫码登录超时，未检测到登录 Cookie")
        finally:
            browser.close()

    return output_path
