#!/usr/bin/env python3
"""
小红书扫码登录模块

【匿名性】来自 stealth_core.py（浏览器匿名性核心模块，独立优化点）
【流程】本模块只管小红书登录操作流程
   1. 打开 xiaohongshu.com → 提取登录二维码
   2. 用户扫码 → 轮询检测登录模态框消失
   3. 保存 cookie
"""
import asyncio
import os
import sys
import time
import base64
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(BASE_DIR))

# patchright（sau 安装目录）
_sau = str(Path.home() / ".local/share/uv/tools/social-auto-upload/lib/python3.11/site-packages")
if _sau not in sys.path:
    sys.path.insert(0, _sau)

from stealth_core import MAC_UA, LAUNCH_ARGS, STEALTH_SCRIPT, find_chrome, ensure_display, goto_with_stealth  # noqa: E402

QR_DIR = BASE_DIR / "qr"
COOKIE_DIR = BASE_DIR / "cookies"
QR_DIR.mkdir(exist_ok=True)
COOKIE_DIR.mkdir(exist_ok=True)

ACCOUNT_FILE = COOKIE_DIR / "xiaohongshu_hermes.json"
STATE_FILE = BASE_DIR / "login_state.txt"
QR_OUT = str(QR_DIR / "xhs_qr_login.png")


def write_state(state: str, payload: str = ""):
    STATE_FILE.write_text(f"{state} {payload}".strip())
    print(f"STATE:{state} {payload}", flush=True)


async def extract_qr(page) -> str:
    """提取小红书登录二维码（data:image/png 最大的）"""
    info = await page.evaluate("""() => {
        const candidates = [];
        document.querySelectorAll('img').forEach(img => {
            const src = img.src || '';
            if (src.startsWith('data:image/png')) candidates.push({src, w: img.width});
        });
        candidates.sort((a, b) => b.w - a.w);
        return candidates.length > 0 ? candidates[0].src : null;
    }""")
    if info and isinstance(info, str) and info.startswith("data:image"):
        with open(QR_OUT, "wb") as f:
            f.write(base64.b64decode(info.split(",", 1)[1]))
        print(f"✅ 小红书二维码: {QR_OUT} ({os.path.getsize(QR_OUT)//1024}KB)", flush=True)
        return QR_OUT
    print("❌ 二维码未找到", flush=True)
    return ""


async def main():
    print("=" * 56)
    print("小红书 扫码登录")
    print("=" * 56)

    ensure_display()
    chrome = find_chrome()
    if chrome:
        print(f"Chrome: {chrome}")

    from patchright.async_api import async_playwright

    async with async_playwright() as pw:
        launch_kwargs = dict(
            headless=False,
            args=LAUNCH_ARGS,
        )
        if chrome:
            launch_kwargs["executable_path"] = chrome

        browser = await pw.chromium.launch(**launch_kwargs)
        context = await browser.new_context(
            viewport={"width": 1440, "height": 900},
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
            device_scale_factor=2,
            user_agent=MAC_UA,
        )
        await context.add_init_script(STEALTH_SCRIPT)
        page = await context.new_page()

        await goto_with_stealth(page, "https://www.xiaohongshu.com", timeout=30000)
        await asyncio.sleep(8)
        print("✅ stealth 已在页面脚本前注入", flush=True)

        qr_path = await extract_qr(page)
        if qr_path:
            write_state("QR_READY", qr_path)
            print(f"📱 请用小红书 APP 扫码: {qr_path}", flush=True)
        else:
            # fallback: 整页截图（二维码可能在页面上）
            shot = str(QR_DIR / "xhs_login_page.png")
            await page.screenshot(path=shot, full_page=False)
            print(f"📸 页面截图: {shot}", flush=True)
            write_state("QR_READY", shot)

        # 轮询检测登录（登录模态框消失 = 登录成功）
        detected = False
        for i in range(80):
            await asyncio.sleep(3)
            try:
                state = await page.evaluate("""() => {
                    const text = document.body.innerText;
                    return {hasLoginModal: text.includes('手机号登录') || text.includes('登录后推荐')};
                }""")
                if isinstance(state, dict) and not state.get("hasLoginModal", True):
                    print(f"✅ 登录成功! ({i*3}s)", flush=True)
                    detected = True
                    break
            except Exception:
                pass

        await asyncio.sleep(2)
        await context.storage_state(path=str(ACCOUNT_FILE))
        print(f"✅ cookie 已保存: {ACCOUNT_FILE}", flush=True)
        write_state("SUCCESS" if detected else "UNKNOWN", str(ACCOUNT_FILE))

        await context.close()
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
