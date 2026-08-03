"""闲鱼（Goofish）扫码登录 — 完整流程。

流程（用户验证过的 3 阶段）：
  阶段1: 打开登录页 → 切二维码 tab → 截二维码（用户扫码）
  阶段2: 检测扫码 → 等 10 秒 → 截人脸识别二维码（用户人脸识别）
  阶段3: 检测登录 → 等 20 秒 → 刷新 → 截全页 → 保存 cookie

关键经验：
  - 必须用 Xvfb 有头模式 + 完整 stealth 伪装（headless 会被风控拒绝）
  - 扫码后闲鱼要求新设备人脸识别（identity_verify），需二次扫码
  - cookies.json 只保留 .goofish.com 域 cookie（混入 .taobao.com 同名 cookie 会登录失效）
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path

# patchright（反检测 playwright）优先
for p in [
    str(Path.home() / ".local/share/uv/tools/patchright/lib/python3.11/site-packages"),
]:
    if p not in sys.path:
        sys.path.insert(0, p)

os.environ.setdefault("DISPLAY", ":99")

import config
import utils

SCAN_KEYWORDS = ["确认登录", "扫描成功", "已扫描", "扫码成功"]
FACE_QR_OUT = str(config.ASSETS_DIR / "goofish_face_qr.png")
FULL_OUT = str(config.ASSETS_DIR / "goofish_page.png")


async def extract_qr(page, out_path: str) -> bool:
    """尝试从页面提取二维码元素截图。"""
    qr_el = await page.query_selector("#qrcode-img") or await page.query_selector("canvas")
    if qr_el:
        await qr_el.screenshot(path=out_path)
        return True
    imgs = await page.query_selector_all("img")
    for img in imgs:
        src = await img.get_attribute("src") or ""
        if any(k in src.lower() for k in ["qr", "code", "login", "scan"]):
            try:
                await img.screenshot(path=out_path)
                return True
            except Exception:
                continue
    return False


async def _click_qr_tab(page) -> bool:
    """切换到二维码登录 tab。"""
    for sel in ["text=扫码", "text=二维码", "text=扫码登录", "text=二维码登录"]:
        try:
            el = await page.query_selector(sel)
            if el:
                await el.click()
                utils.log(f"✅ 点击 {sel}")
                await page.wait_for_timeout(3000)
                return True
        except Exception:
            continue
    try:
        r = await page.evaluate(
            """() => {
                for (const el of document.querySelectorAll('span,div,a,li,button')) {
                    if (el.textContent && el.textContent.includes('二维码') && el.offsetParent) {
                        el.click(); return true;
                    }
                }
                return false;
            }"""
        )
        utils.log(f"  JS点击: {r}")
        return bool(r)
    except Exception as e:
        utils.log(f"  JS点击失败: {e}")
        return False


async def run_login() -> None:
    """闲鱼扫码登录主流程。"""
    from patchright.async_api import async_playwright

    config.GOOFISH_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    utils.log("🚀 启动有头模式 Chrome（闲鱼）...")

    async with async_playwright() as pw:
        context = await pw.chromium.launch_persistent_context(
            user_data_dir=str(config.GOOFISH_PROFILE_DIR),
            **config.launch_kwargs(),
        )
        page = context.pages[0] if context.pages else await context.new_page()

        # ===== 阶段1: 登录页 + 初始二维码 =====
        utils.log("打开登录页...")
        await page.goto(config.GOOFISH_LOGIN_URL, wait_until="load", timeout=30000)
        await page.wait_for_timeout(3000)

        # 运行时 stealth 伪装（patchright add_init_script 在系统 Chrome 不生效）
        await utils.apply_stealth(page)
        await page.wait_for_timeout(5000)

        await _click_qr_tab(page)
        await page.reload(wait_until="load", timeout=30000)
        await page.wait_for_timeout(10000)

        qr_out = str(config.ASSETS_DIR / "goofish_qr_login.png")
        if await extract_qr(page, qr_out):
            utils.log(f"✅ 初始二维码: {qr_out} ({os.path.getsize(qr_out)//1024}KB)")
        await page.screenshot(path=FULL_OUT)
        print("QR_READY")  # 标记：二维码已就绪，可发给用户

        # ===== 阶段2: 等待扫码 → 等10秒 → 截人脸二维码 =====
        utils.log("🔍 等待扫码...")
        scan_detected = False
        start = time.time()
        while time.time() - start < 300:
            await page.wait_for_timeout(2000)
            try:
                body_text = await page.evaluate("document.body ? document.body.innerText : ''")
            except Exception:
                body_text = ""
            fresh = await utils.snap_cookies_async(context)

            hit = [k for k in SCAN_KEYWORDS if k in body_text]
            if hit:
                utils.log(f"🎯 检测到扫码: {hit}")
                scan_detected = True
                break
            if "unb" in fresh and "tracknick" in fresh:
                utils.log("🎯 检测到登录 cookie")
                scan_detected = True
                break

        if not scan_detected:
            print("NO_SCAN")
            await context.close()
            return

        # 等 10 秒（页面跳转人脸识别）
        utils.log("⏳ 等10秒（页面跳转人脸识别）...")
        await page.wait_for_timeout(10000)

        url_now = page.url
        utils.log(f"当前 URL: {url_now}")
        await page.screenshot(path=FULL_OUT, full_page=True)
        utils.log(f"✅ 当前页面: {FULL_OUT} ({os.path.getsize(FULL_OUT)//1024}KB)")

        got_face = await extract_qr(page, FACE_QR_OUT)
        if not got_face:
            await page.reload(wait_until="load", timeout=30000)
            await page.wait_for_timeout(8000)
            await page.screenshot(path=FULL_OUT, full_page=True)
            got_face = await extract_qr(page, FACE_QR_OUT)
        if got_face:
            utils.log(f"✅ 人脸二维码: {FACE_QR_OUT} ({os.path.getsize(FACE_QR_OUT)//1024}KB)")
        print("FACE_QR_READY")  # 标记：人脸识别二维码已就绪

        # ===== 阶段3: 等待人脸识别完成 → 等20秒 → 刷新 → 截图 =====
        utils.log("🔍 等待人脸识别完成...")
        logged_in = False
        start = time.time()
        while time.time() - start < 300:
            await page.wait_for_timeout(3000)
            fresh = await utils.snap_cookies_async(context)
            if "unb" in fresh and "tracknick" in fresh and "sgcookie" in fresh:
                utils.log(f"🎉 登录成功! unb={fresh['unb']} user={fresh['tracknick']}")
                logged_in = True
                break
            try:
                body_text = await page.evaluate("document.body ? document.body.innerText : ''")
                if "登录成功" in body_text or "欢迎" in body_text:
                    utils.log("🎉 检测到登录成功文字")
                    logged_in = True
                    break
            except Exception:
                pass

        utils.log("⏳ 等20秒...")
        await page.wait_for_timeout(20000)

        utils.log("🔄 刷新页面...")
        try:
            await page.goto("https://www.goofish.com", wait_until="load", timeout=30000)
        except Exception:
            await page.reload(wait_until="load", timeout=30000)
        await page.wait_for_timeout(10000)

        await page.screenshot(path=FULL_OUT, full_page=True)
        utils.log(f"✅ 最终截图: {FULL_OUT} ({os.path.getsize(FULL_OUT)//1024}KB)")

        # 抓取并保存 cookie（只保留 goofish 域）
        cookies = await context.cookies()
        fresh = {c["name"]: c["value"] for c in cookies if c.get("value")}
        utils.log(
            f"📊 cookie: {len(fresh)} | "
            f"unb={'✅' if 'unb' in fresh else '❌'} "
            f"tracknick={'✅' if 'tracknick' in fresh else '❌'} "
            f"sgcookie={'✅' if 'sgcookie' in fresh else '❌'}"
        )

        if "unb" in fresh and "tracknick" in fresh:
            # 只保留 .goofish.com 域的 cookie（关键！）
            goofish_cookies = {
                c["name"]: c["value"]
                for c in cookies
                if c.get("value") and "goofish.com" in c.get("domain", "")
            }
            if not goofish_cookies:
                goofish_cookies = fresh
            utils.write_goofish_cookies(goofish_cookies)
            print("LOGIN_SUCCESS")
        else:
            print("NOT_LOGGED_IN")

        print("SCREENSHOT_READY")
        await context.close()


if __name__ == "__main__":
    config.ensure_xvfb()
    asyncio.run(run_login())
