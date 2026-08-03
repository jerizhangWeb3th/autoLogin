"""闲鱼（Goofish）扫码登录 — 用户驱动的精确流程（实测验证版）。

流程（用户确认的交互模式）:
  1. 打开登录页 → 截二维码 → 发给用户扫码
  2. 用户扫码 → 用 cookie 检测登录态（unb+tracknick 出现即视为扫码成功）
  3. 检测是否需要人脸验证 → 提取人脸二维码 → 发给用户识别
  4. 等登录态完整（+sgcookie）→ 等 20 秒 → 打开主页截图确认 → 保存 cookie

关键经验（实测踩坑）:
  - 用 cookie 判断扫码，不要用页面跳转（扫码确认后 cookie 立即建立，
    但页面可能不自动跳转，仍停在 mini_login）
  - 不点任何按钮：二维码提取后页面停留，用户扫码后 cookie 自动建立
  - 扫码后闲鱼可能要求新设备人脸识别（identity_verify），需二次扫码
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

QR_OUT = str(config.ASSETS_DIR / "goofish_qr_login.png")
FACE_QR_OUT = str(config.ASSETS_DIR / "goofish_face_qr.png")
SHOT1 = str(config.ASSETS_DIR / "goofish_step1_login.png")
SHOT2 = str(config.ASSETS_DIR / "goofish_step2_face.png")
SHOT3 = str(config.ASSETS_DIR / "goofish_step3_home.png")

# 状态机标记（供外部解析，触发给用户发图/判断）
STATE_QR_READY = "STATE:QR_READY"        # 登录二维码已生成 → 发用户扫码
STATE_FACE_QR = "STATE:FACE_QR_READY"    # 人脸二维码已生成 → 发用户识别
STATE_SUCCESS = "STATE:LOGIN_SUCCESS"
STATE_TIMEOUT = "STATE:TIMEOUT"


def emit(tag: str, payload: str = "") -> None:
    print(f"{tag} {payload}".strip(), flush=True)


async def _snap(context) -> dict:
    cookies = await context.cookies()
    return {c["name"]: c["value"] for c in cookies if c.get("value")}


async def _page_text(page) -> str:
    try:
        return await page.evaluate("document.body ? document.body.innerText : ''")
    except Exception:
        return ""


async def extract_qr(page, out_path: str) -> bool:
    """提取页面二维码（#qrcode-img / canvas / data:image / img）。"""
    qr_el = await page.query_selector("#qrcode-img") or await page.query_selector("canvas")
    if qr_el:
        await qr_el.screenshot(path=out_path)
        return True
    b64 = await page.evaluate(
        """() => {
            const imgs = document.querySelectorAll('img');
            for (const img of imgs) {
                const src = img.src || '';
                const r = img.getBoundingClientRect();
                if (src.startsWith('data:image') && r.width > 50 && r.width < 300 && r.height > 50) return src;
            }
            return '';
        }"""
    )
    if b64:
        import base64
        data = base64.b64decode(b64.split(",")[1])
        with open(out_path, "wb") as f:
            f.write(data)
        return True
    imgs = await page.query_selector_all("img")
    for img in imgs:
        src = await img.get_attribute("src") or ""
        if any(k in src.lower() for k in ["qr", "code", "scan"]):
            try:
                await img.screenshot(path=out_path)
                return True
            except Exception:
                continue
    return False


async def run_login() -> None:
    """闲鱼扫码登录主流程（用户驱动：二维码 → 扫码 → 人脸 → 完成）。"""
    from patchright.async_api import async_playwright

    config.GOOFISH_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    utils.log("🚀 启动真 Chrome（闲鱼）...")

    async with async_playwright() as pw:
        context = await pw.chromium.launch_persistent_context(
            user_data_dir=str(config.GOOFISH_PROFILE_DIR),
            **config.launch_kwargs(),
        )
        page = context.pages[0] if context.pages else await context.new_page()

        # ===== 1. 打开登录页 → 截二维码 =====
        await page.goto(config.GOOFISH_LOGIN_URL, wait_until="load", timeout=30000)
        await page.wait_for_timeout(10000)
        await page.screenshot(path=SHOT1, full_page=True)
        utils.log(f"📸 登录页: {SHOT1}")
        if await extract_qr(page, QR_OUT):
            utils.log(f"✅ 登录二维码: {QR_OUT} ({os.path.getsize(QR_OUT)//1024}KB)")
        emit(STATE_QR_READY, QR_OUT)  # → 发二维码给用户

        # ===== 2. 等待扫码（用 cookie 判断，不依赖页面跳转） =====
        utils.log("⏳ 等待扫码（最长300s）...")
        scanned = False
        start = time.time()
        while time.time() - start < 300:
            await page.wait_for_timeout(3000)
            fresh = await _snap(context)
            if "unb" in fresh and "tracknick" in fresh:
                utils.log(f"🎯 检测到扫码登录 cookie (unb={fresh['unb'][:4]}****)")
                scanned = True
                break
            elapsed = int(time.time() - start)
            if elapsed % 30 == 0:
                utils.log(f"  [{elapsed}s] 等待扫码中...")

        if not scanned:
            utils.log("❌ 等待扫码超时")
            emit(STATE_TIMEOUT, "scan")
            await context.close()
            return

        # 等页面可能跳转（人脸验证）
        await page.wait_for_timeout(8000)
        url = page.url
        text = await _page_text(page)
        await page.screenshot(path=SHOT2, full_page=True)
        utils.log(f"📸 扫码后: {SHOT2} | url={url[:80]}")

        # ===== 3. 检测是否需要人脸验证 → 提取人脸二维码 =====
        need_face = (
            "identity" in url or "verify" in url
            or any(k in text for k in ["人脸", "身份验证", "确认身份", "扫一扫"])
        )
        if need_face:
            utils.log("⚠️ 需要人脸验证，提取人脸二维码...")
            face_ok = await extract_qr(page, FACE_QR_OUT)
            if not face_ok:
                await page.reload(wait_until="load", timeout=30000)
                await page.wait_for_timeout(8000)
                await page.screenshot(path=SHOT2, full_page=True)
                face_ok = await extract_qr(page, FACE_QR_OUT)
            if face_ok:
                utils.log(f"✅ 人脸二维码: {FACE_QR_OUT} ({os.path.getsize(FACE_QR_OUT)//1024}KB)")
                emit(STATE_FACE_QR, FACE_QR_OUT)  # → 发人脸二维码给用户
            else:
                utils.log("⚠️ 未提取到人脸二维码，发送全页")
                emit(STATE_FACE_QR, SHOT2)

            # ===== 4. 等待人脸识别完成（登录态完整） =====
            utils.log("⏳ 等待人脸识别完成（最长300s）...")
            start = time.time()
            while time.time() - start < 300:
                await page.wait_for_timeout(3000)
                fresh = await _snap(context)
                if "unb" in fresh and "tracknick" in fresh and "sgcookie" in fresh:
                    utils.log("🎉 人脸完成，登录态完整")
                    break
                text = await _page_text(page)
                if "登录成功" in text or "欢迎" in text:
                    utils.log("🎉 检测到登录成功")
                    break
                elapsed = int(time.time() - start)
                if elapsed % 30 == 0:
                    utils.log(f"  [{elapsed}s] 等待人脸完成...")

        # ===== 5. 等 20 秒稳定 → 打开主页确认 → 保存 cookie =====
        utils.log("⏳ 等 20 秒稳定会话...")
        await page.wait_for_timeout(20000)

        try:
            await page.goto("https://www.goofish.com", wait_until="load", timeout=30000)
            await page.wait_for_timeout(8000)
        except Exception:
            pass
        await page.screenshot(path=SHOT3, full_page=True)
        utils.log(f"📸 主页: {SHOT3} ({os.path.getsize(SHOT3)//1024}KB)")

        # 主页文字确认登录（显示用户名）
        home_text = await _page_text(page)
        utils.log(f"主页文字: {home_text[:80]}")

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
            emit(STATE_SUCCESS)
        else:
            utils.log("⚠️ 登录态未完全建立")
            emit("STATE:NOT_LOGGED_IN")

        await context.close()


if __name__ == "__main__":
    config.ensure_xvfb()
    asyncio.run(run_login())
