#!/usr/bin/env python3
"""
闲鱼（Goofish）扫码登录模块

【匿名性】来自 stealth_core.py（浏览器匿名性核心模块，独立优化点）
【流程】本模块只管闲鱼登录操作流程
   1. 打开 passport.goofish.com/mini_login → 提取二维码
   2. 用户扫码 → 用 cookie 检测登录态（unb+tracknick 出现 = 扫码成功）
   3. 检测是否需要人脸验证 → 提取人脸二维码
   4. 登录态完整（+sgcookie）→ 保存 cookie
"""
import asyncio
import os
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

# patchright（sau 安装目录）
_sau = str(Path.home() / ".local/share/uv/tools/social-auto-upload/lib/python3.11/site-packages")
if _sau not in sys.path:
    sys.path.insert(0, _sau)

from core.stealth import MAC_UA, LAUNCH_ARGS, STEALTH_SCRIPT, find_chrome, ensure_display, goto_with_stealth  # noqa: E402

QR_DIR = BASE_DIR / "qr"
COOKIE_DIR = BASE_DIR / "cookies"
QR_DIR.mkdir(exist_ok=True)
COOKIE_DIR.mkdir(exist_ok=True)

ACCOUNT_FILE = COOKIE_DIR / "goofish_cookies.json"
STATE_FILE = BASE_DIR / "login_state.txt"
QR_OUT = str(QR_DIR / "goofish_qr_login.png")
FACE_QR_OUT = str(QR_DIR / "goofish_face_qr.png")
LOGIN_URL = "https://passport.goofish.com/mini_login.htm?lang=zh_cn&appName=xianyu&appEntrance=web"


def write_state(state: str, payload: str = ""):
    STATE_FILE.write_text(f"{state} {payload}".strip())
    print(f"STATE:{state} {payload}", flush=True)


async def _snap(context) -> dict:
    cookies = await context.cookies()
    return {c["name"]: c["value"] for c in cookies if c.get("value")}


async def extract_qr(page) -> bool:
    """提取闲鱼登录二维码"""
    qr_el = await page.query_selector("#qrcode-img") or await page.query_selector("canvas")
    if qr_el:
        await qr_el.screenshot(path=QR_OUT)
        return True
    b64 = await page.evaluate("""() => {
        const imgs = document.querySelectorAll('img');
        for (const img of imgs) {
            const src = img.src || '';
            const r = img.getBoundingClientRect();
            if (src.startsWith('data:image') && r.width > 50 && r.width < 300 && r.height > 50) return src;
        }
        return '';
    }""")
    if b64:
        import base64
        with open(QR_OUT, "wb") as f:
            f.write(base64.b64decode(b64.split(",")[1]))
        return True
    return False


async def main():
    print("=" * 56)
    print("闲鱼（Goofish）扫码登录")
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

        # 1. 打开登录页 → 截二维码（commit 时注入 stealth）
        await goto_with_stealth(page, LOGIN_URL, timeout=30000)
        await page.wait_for_timeout(10000)
        print("✅ stealth 已在页面脚本前注入", flush=True)

        if await extract_qr(page):
            print(f"✅ 登录二维码: {QR_OUT} ({os.path.getsize(QR_OUT)//1024}KB)", flush=True)
            write_state("QR_READY", QR_OUT)
        else:
            shot = str(QR_DIR / "goofish_login_page.png")
            await page.screenshot(path=shot, full_page=True)
            print(f"📸 登录页截图: {shot}", flush=True)
            write_state("QR_READY", shot)

        # 2. 等待扫码（用 cookie 判断）
        print("⏳ 等待扫码（最长300s）...", flush=True)
        scanned = False
        start = time.time()
        while time.time() - start < 300:
            await page.wait_for_timeout(3000)
            fresh = await _snap(context)
            if "unb" in fresh and "tracknick" in fresh:
                print(f"🎯 检测到扫码登录 cookie (unb={fresh['unb'][:4]}****)", flush=True)
                scanned = True
                break

        if not scanned:
            print("❌ 等待扫码超时", flush=True)
            write_state("TIMEOUT", "scan")
            await context.close()
            await browser.close()
            return

        # 3. 检查人脸验证
        face_done = False
        for _ in range(10):
            await page.wait_for_timeout(3000)
            fresh = await _snap(context)
            if "sgcookie" in fresh:
                face_done = True
                break
            # 检测人脸验证弹窗
            page_text = await page.evaluate("document.body ? document.body.innerText : ''")
            if "identity_verify" in page_text or "人脸" in page_text or "验证" in page_text:
                if await extract_qr(page):
                    write_state("FACE_QR_READY", QR_OUT)
                    print(f"📱 请扫码完成人脸验证: {QR_OUT}", flush=True)

        # 4. 保存 cookie
        await asyncio.sleep(5)
        await context.storage_state(path=str(ACCOUNT_FILE))
        print(f"✅ cookie 已保存: {ACCOUNT_FILE}", flush=True)
        write_state("SUCCESS", str(ACCOUNT_FILE))

        await context.close()
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
