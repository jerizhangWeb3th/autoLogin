"""小红书主站扫码登录（获取 web_session — 评论功能必需）。

跨平台：Windows / macOS / Ubuntu 自动适配（Chrome 路径 / DISPLAY / cookie 目录）。
依赖：patchright + 真 Chrome + sau 的 macOS 伪装补丁（uploader 模块）。

用法：
    python xiaohongshu_main_login.py [账号名]
    默认账号: autoContent
"""
import os
import sys
import asyncio
import json
import base64
import argparse

# 确保 sau site-packages 可导入（含 uploader 模块的 MAC_UA / MAC_OVERRIDE_SCRIPT）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config  # noqa: E402

config.ensure_display()
config.ensure_sau_importable()

from patchright.async_api import async_playwright  # noqa: E402
from uploader.xiaohongshu_uploader.main import MAC_UA, MAC_OVERRIDE_SCRIPT, _LAUNCH_ARGS  # noqa: E402

QR_OUT = "/tmp/xhs_main_qrcode_v4.png"


def get_web_session(cookie_file):
    try:
        with open(cookie_file) as f:
            c = json.load(f)
        for x in c["cookies"]:
            if x["name"] == "web_session":
                return x["value"]
    except Exception:
        pass
    return None


async def safe_eval(page, script, retries=3, delay=4):
    for i in range(retries):
        try:
            return await page.evaluate(script)
        except Exception as e:
            if i < retries - 1:
                await asyncio.sleep(delay)
            else:
                return {"error": str(e)[:100]}


async def main():
    parser = argparse.ArgumentParser(description="小红书主站扫码登录")
    parser.add_argument("account", nargs="?", default="autoContent")
    args = parser.parse_args()

    cookie_file = str(config.xhs_cookie_file(args.account))
    os.makedirs(os.path.dirname(cookie_file), exist_ok=True)
    print(f"账号: {args.account} cookie: {cookie_file}")

    old_ws = get_web_session(cookie_file)
    print(f"OLD_WS:{old_ws[:8] if old_ws else 'None'}")

    chrome_path = config.find_chrome()
    print(f"Chrome: {chrome_path}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, executable_path=chrome_path, args=_LAUNCH_ARGS)
        context = await browser.new_context(
            user_agent=MAC_UA, locale="zh-CN", timezone_id="Asia/Shanghai",
            viewport={"width": 1440, "height": 900}, device_scale_factor=2,
            storage_state=cookie_file,
        )
        await context.add_init_script("(" + MAC_OVERRIDE_SCRIPT + ")()")
        page = await context.new_page()

        await page.goto("https://www.xiaohongshu.com", wait_until="domcontentloaded", timeout=30000)
        await page.evaluate(MAC_OVERRIDE_SCRIPT)
        await asyncio.sleep(8)

        # 立即保存二维码（不等用户）
        qr = await safe_eval(page, """() => {
            const candidates = [];
            document.querySelectorAll('img').forEach(img => {
                const src = img.src || '';
                if (src.startsWith('data:image/png')) candidates.push({src, w: img.width});
            });
            candidates.sort((a, b) => b.w - a.w);
            return candidates.length > 0 ? candidates[0].src : null;
        }""")
        if qr and isinstance(qr, str) and qr.startswith("data:image/png"):
            with open(QR_OUT, "wb") as f:
                f.write(base64.b64decode(qr.split(",", 1)[1]))
            print(f"QR_READY:{QR_OUT}")
        else:
            print("QR_NOT_FOUND")

        # 快速轮询检测（每 3 秒，最多 4 分钟）
        detected = False
        for i in range(80):
            await asyncio.sleep(3)
            state = await safe_eval(page, """() => {
                const text = document.body.innerText;
                return {hasLoginModal: text.includes('手机号登录') || text.includes('登录后推荐')};
            }""", retries=1)
            if isinstance(state, dict) and not state.get("hasLoginModal", True):
                print(f"LOGIN_OK at {i*3}s")
                detected = True
                break
            if i % 10 == 9:
                print(f"  ...{i*3}s")

        await asyncio.sleep(2)
        await context.storage_state(path=cookie_file)
        new_ws = get_web_session(cookie_file)
        changed = bool(new_ws) and new_ws != old_ws
        print(f"RESULT: detected={detected} ws_changed={changed}")
        if new_ws:
            print(f"NEW_WS:{new_ws[:8]}")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
