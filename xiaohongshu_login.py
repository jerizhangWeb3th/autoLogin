"""小红书（Xiaohongshu）创作者中心扫码登录。

用户确认的流程：生成二维码直接发给用户扫码，扫完自动保存登录态。

关键经验：
  - creator 登录页默认短信登录；右上角 64x64 图标切到"APP扫一扫"
  - 页面 canvas 二维码（html2canvas）在自动化环境绘制失败，抓不到
  - 正确做法：从 qr-code 接口拿 qrCodeId/url，用 qrcode 库生成二维码
  - www.xiaohongshu.com 主站登录（web_session）≠ creator 登录（galaxy_creator_session_id）
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path

# social-auto-upload 自带 patchright
for p in [
    "/root/.local/share/uv/tools/social-auto-upload/lib/python3.11/site-packages",
    "/root/.local/share/uv/tools/social-auto-upload/lib/python3.11/site-packages/patchright",
]:
    if p not in sys.path:
        sys.path.insert(0, p)

os.environ.setdefault("DISPLAY", ":99")

import config
import utils

MAX_WAIT = 300


async def run_login() -> None:
    """小红书创作者中心扫码登录主流程。"""
    from patchright.async_api import async_playwright

    config.XHS_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    utils.log("🚀 启动有头模式 Chrome（小红书）...")

    async with async_playwright() as pw:
        context = await pw.chromium.launch_persistent_context(
            user_data_dir=str(config.XHS_PROFILE_DIR),
            **config.launch_kwargs(),
        )
        page = context.pages[0] if context.pages else await context.new_page()

        # 捕获 qr-code 接口响应
        qr_data = {}

        async def on_response(resp):
            if "qr-code" in resp.url or "qrcode" in resp.url:
                try:
                    body = await resp.json()
                    data = body.get("data") or {}
                    if data.get("url") or data.get("qrCodeId"):
                        qr_data.update(data)
                except Exception:
                    pass

        page.on("response", lambda r: asyncio.create_task(on_response(r)))

        await page.goto(
            "https://creator.xiaohongshu.com/login",
            wait_until="domcontentloaded", timeout=30000,
        )
        await page.wait_for_timeout(3000)

        # 运行时 stealth 伪装（patchright add_init_script 在系统 Chrome 不生效）
        await utils.apply_stealth(page)
        await page.wait_for_timeout(5000)

        # 点右上角扫码图标（64x64，位于登录框右上角）
        clicked = await page.evaluate(
            """() => {
                const imgs = document.querySelectorAll('img');
                for (const img of imgs) {
                    const r = img.getBoundingClientRect();
                    if (r.x > 1150 && r.y < 350 && r.width > 30 && r.width < 100) {
                        img.click(); return true;
                    }
                }
                return false;
            }"""
        )
        utils.log(f"✅ 点击扫码tab: {clicked}")

        # 等 qr-code 接口返回
        for _ in range(10):
            if qr_data:
                break
            await page.wait_for_timeout(1000)

        if not qr_data:
            utils.log("❌ 未捕获 qr-code 接口")
            await context.close()
            return

        qr_url = qr_data.get("url") or qr_data.get("qrCodeId", "")
        qr_id = qr_data.get("id") or qr_data.get("qrCodeId", "")
        utils.log(f"🎯 qrCodeId: {qr_id}")
        utils.log(f"🎯 二维码内容: {qr_url[:100]}")

        # 用 qrcode 库生成二维码（页面 canvas 抓不到，必须走接口）
        qr_out = str(config.ASSETS_DIR / "xiaohongshu_qr_login.png")
        if utils.generate_qr_png(qr_url, qr_out):
            utils.log(f"✅ 二维码: {qr_out} ({os.path.getsize(qr_out)//1024}KB)")
        print("QR_READY")  # 标记：二维码已生成，可发给用户

        # 等待扫码确认（页面跳转 / 登录 cookie 出现）
        utils.log(f"🔍 等待扫码确认 (最长 {MAX_WAIT}s)...")
        start = time.time()
        logged_in = False
        while time.time() - start < MAX_WAIT:
            await page.wait_for_timeout(5000)
            url = page.url
            if "creator.xiaohongshu.com" in url and "/login" not in url:
                utils.log(f"🎉 页面已跳转: {url}")
                logged_in = True
                break
            cookies = await context.cookies()
            names = {c["name"] for c in cookies}
            if "galaxy_creator_session_id" in names or "web_session" in names:
                utils.log("🎉 检测到登录 cookie!")
                logged_in = True
                break
            elapsed = int(time.time() - start)
            if elapsed % 30 == 0:
                utils.log(f"⏳ 等待中... {elapsed}s")

        if logged_in:
            await page.wait_for_timeout(3000)
            await utils.save_storage_state(context)
            # 跳到创作者主页截图确认
            await page.goto(
                "https://creator.xiaohongshu.com",
                wait_until="domcontentloaded", timeout=30000,
            )
            await page.wait_for_timeout(5000)
            shot = str(config.ASSETS_DIR / "xiaohongshu_logged_in.png")
            await page.screenshot(path=shot, full_page=True)
            utils.log(f"📸 登录后页面: {shot}")
            print("LOGIN_SUCCESS")
        else:
            print("TIMEOUT")

        await context.close()


if __name__ == "__main__":
    config.ensure_xvfb()
    asyncio.run(run_login())
