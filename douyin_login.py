#!/usr/bin/env python3
"""
抖音创作者中心扫码登录模块

【匿名性】来自 stealth_core.py（浏览器匿名性核心模块，独立优化点）
【流程】本模块只管抖音登录操作流程，不涉及匿名性细节
   1. 打开 creator.douyin.com → 点「我是创作者」
   2. 提取二维码（base64）→ 保存到 qr/ 目录（自动清旧码）
   3. 用户扫码 → 保持页面等待登录成功（不 reload 避免打断）
   4. 检测到 #uc-second-verify 二次校验 → 自动点「手机刷脸验证」→ 提取人脸二维码
   5. 登录成功（URL 跳转 creator-micro 或出现「退出」按钮）→ 保存 cookie

【用法】
   python douyin_login.py
   或: python main.py douyin
"""
import asyncio
import os
import sys
import time
import base64
import hashlib
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

ACCOUNT_FILE = COOKIE_DIR / "douyin_douyin_main.json"
QR_LATEST_FILE = BASE_DIR / "qr_latest.txt"
STATE_FILE = BASE_DIR / "login_state.txt"


def ts() -> str:
    """完整时间序列命名（年月日_时分秒，保证字典序=时间序）"""
    return time.strftime("%Y%m%d_%H%M%S")


def latest_qr() -> str:
    """取二维码目录中最新时间序列的一张"""
    files = sorted(QR_DIR.glob("douyin_qr_*.png"), key=lambda f: f.name, reverse=True)
    return str(files[0]) if files else ""


def latest_page_shot() -> str:
    """取页面截图中最新时间序列的一张"""
    files = sorted(QR_DIR.glob("douyin_page_*.png"), key=lambda f: f.name, reverse=True)
    return str(files[0]) if files else ""


async def save_page_shot(page) -> str:
    """截取登录卡区域（含二维码）+ 同步提取配对二维码，时间序列命名。

    关键：先快速截图，再立即提取二维码（同时间戳配对），
    避免截图慢导致内容滞后于二维码刷新。返回 (截图路径, 二维码路径)。
    """
    stamp = ts()
    out = str(QR_DIR / f"douyin_page_{stamp}.png")
    try:
        # 1. 快速截图（viewport，不整页长图；登录卡优先）
        shot_ok = False
        try:
            el = page.locator("#douyin_login_comp_scan_code")
            if await el.count() > 0:
                # 快速截图容器（timeout 短，避免等待太久滞后）
                await el.screenshot(path=out, timeout=5000)
                if os.path.getsize(out) > 10 * 1024:
                    shot_ok = True
        except Exception:
            pass
        if not shot_ok:
            await page.screenshot(path=out, full_page=False)
        print(f"📸 登录卡截图: {os.path.basename(out)}", flush=True)
        return out
    except Exception as e:
        print(f"⚠️ 页面截图失败: {str(e)[:80]}", flush=True)
        return ""


def write_latest(path: str):
    """写最新二维码路径 + 清理旧码"""
    try:
        for old in QR_DIR.glob("douyin_qr_*.png"):
            if str(old) != path:
                old.unlink(missing_ok=True)
        print("🧹 已清除旧二维码文件", flush=True)
    except Exception:
        pass
    QR_LATEST_FILE.write_text(path)
    print(f"📡 最新二维码: {path}", flush=True)


def write_state(state: str, payload: str = ""):
    STATE_FILE.write_text(f"{state} {payload}".strip())
    print(f"STATE:{state} {payload}", flush=True)


async def extract_qr(page) -> str:
    """提取二维码 PNG（抖音新版：Lottie 动画渲染）"""
    stamp = ts()
    out = str(QR_DIR / f"douyin_qr_{stamp}.png")
    # 等二维码渲染完成（Lottie 动画约需 15 秒）
    await page.wait_for_timeout(15000)
    # 截图二维码容器
    el = page.locator("#default_scan_code_guide")
    if await el.count() > 0:
        await el.screenshot(path=out, timeout=5000)
        if os.path.getsize(out) > 5 * 1024:
            print(f"✅ 二维码(容器截图): {out}", flush=True)
            return out
    # 旧版：找 img data:image（仅 png/jpeg，跳过 svg+xml 避免损坏）
    info = await page.evaluate("""() => {
        const scan = document.querySelector('#douyin_login_comp_scan_code');
        if (scan) {
            const img = scan.querySelector('img');
            if (img && (img.src.startsWith('data:image/png') || img.src.startsWith('data:image/jpeg'))) return img.src;
        }
        const imgs = document.querySelectorAll('img');
        for (const img of imgs) {
            const src = String(img.src || '');
            if ((src.startsWith('data:image/png') || src.startsWith('data:image/jpeg')) && img.getBoundingClientRect().width > 100) return src;
        }
        return '';
    }""")
    if info.startswith("data:image"):
        b64 = info.split(",", 1)[1]
        with open(out, "wb") as f:
            f.write(base64.b64decode(b64))
        print(f"✅ 二维码(base64): {out}", flush=True)
        return out
    # 3. 最后 fallback：截图整个登录卡容器
    try:
        el2 = page.locator("#douyin_login_comp_scan_code")
        if await el2.count() > 0:
            await el2.screenshot(path=out, timeout=5000)
            print(f"✅ 二维码(登录卡截图): {out}", flush=True)
            return out
    except Exception:
        pass
    await page.screenshot(path=out, clip={"x": 737, "y": 282, "width": 329, "height": 305})
    print(f"✅ 二维码(裁剪): {out}", flush=True)
    return out


async def goto_login(page):
    """进入我是创作者登录页（commit 时注入 stealth，早于页面脚本）"""
    await goto_with_stealth(page, "https://creator.douyin.com/")
    await page.wait_for_timeout(3000)
    print("✅ stealth 已在页面脚本前注入", flush=True)
    if "creator-micro" in page.url:
        return "ALREADY_LOGGED"
    try:
        await page.get_by_text("我是创作者", exact=True).first.click(timeout=10000)
        print("✅ 点击「我是创作者」", flush=True)
    except Exception as e:
        print(f"⚠️ 点击失败(继续尝试): {str(e)[:60]}", flush=True)
    # ★ 抖音新版二维码是 SVG 渲染，需等待 ~10 秒才渲染完成
    for _ in range(12):
        await page.wait_for_timeout(2000)
        has_qr = await page.evaluate("""() => {
            // 新版：SVG 二维码容器
            const guide = document.querySelector('#default_scan_code_guide');
            if (guide && guide.querySelector('svg[viewBox="0 0 800 926"]')) return true;
            // 旧版：img data:image
            const scan = document.querySelector('#douyin_login_comp_scan_code');
            if (scan) {
                const img = scan.querySelector('img');
                if (img && img.src.startsWith('data:image')) return true;
            }
            return false;
        }""")
        if has_qr:
            return "QR_READY"
    return "NO_QR"


async def check_logged_in(page) -> bool:
    """检查是否已登录成功"""
    url = page.url
    if "creator-micro" in url:
        return True
    try:
        logout_btn = await page.query_selector("text=退出")
        if logout_btn:
            return True
    except Exception:
        pass
    return False


async def save_login_success(page, context, browser) -> str:
    """登录成功后保存 cookie 和截图"""
    print(f"🎉 登录成功! URL={page.url[:80]}", flush=True)
    await page.wait_for_timeout(3000)
    await context.storage_state(path=str(ACCOUNT_FILE))
    print(f"✅ cookie 已保存: {ACCOUNT_FILE}", flush=True)
    stamp = ts()
    shot = str(QR_DIR.parent / f"douyin_logged_{stamp}.png")
    try:
        await page.screenshot(path=shot, full_page=False)
        print(f"📸 登录成功截图: {shot}", flush=True)
    except Exception:
        pass
    write_state("SUCCESS", f"cookie={ACCOUNT_FILE}")
    await context.close()
    await browser.close()
    return "SUCCESS"


async def click_face_verify(page) -> bool:
    """自动点击「手机刷脸验证」（#uc-second-verify 二次校验）"""
    print("🔍 检测 #uc-second-verify 验证方式选择...", flush=True)
    try:
        el = page.locator("#uc-second-verify").locator("text=手机刷脸验证").first
        if await el.count() > 0 and await el.is_visible():
            await el.click(timeout=5000)
            print("✅ 已点击「手机刷脸验证」", flush=True)
            write_state("FACE_CLICKED", "已选择手机刷脸验证")
            return True
    except Exception:
        pass
    try:
        container = page.locator("#uc-second-verify")
        if await container.count() > 0 and await container.is_visible():
            items = container.locator("div, span, a, button, li, p, label")
            count = await items.count()
            for i in range(count):
                item = items.nth(i)
                text = await item.text_content()
                if text and ("刷脸" in text or "人脸" in text):
                    await item.click(timeout=3000)
                    print(f"✅ 已点击「{text.strip()}」", flush=True)
                    write_state("FACE_CLICKED", "已选择刷脸验证")
                    return True
    except Exception:
        pass
    try:
        clicked = await page.evaluate("""() => {
            const container = document.querySelector('#uc-second-verify');
            const all = (container ? container.querySelectorAll('*') : document.querySelectorAll('*'));
            for (const el of all) {
                const text = el.innerText || el.textContent || '';
                if ((text.includes('手机刷脸') || text.includes('刷脸验证') ||
                     text.includes('人脸识别') || text.includes('扫脸验证')) &&
                     el.offsetParent !== null && el.children.length === 0) {
                    el.click();
                    return true;
                }
            }
            return false;
        }""")
        if clicked:
            print("✅ 已点击「手机刷脸验证」(JS fallback)", flush=True)
            write_state("FACE_CLICKED", "已选择刷脸验证")
            return True
    except Exception:
        pass
    return False


async def extract_face_qr(page) -> str:
    """提取人脸验证二维码截图"""
    print("⏳ 等待人脸验证二维码出现...", flush=True)
    await page.wait_for_timeout(15000)
    stamp = ts()
    out = str(QR_DIR / f"douyin_face_qr_{stamp}.png")
    info = await page.evaluate("""() => {
        const imgs = document.querySelectorAll('img');
        for (const img of imgs) {
            const src = String(img.src || '');
            if (src.startsWith('data:image') && img.getBoundingClientRect().width > 80) return src;
        }
        return '';
    }""")
    if info.startswith("data:image"):
        b64 = info.split(",", 1)[1]
        with open(out, "wb") as f:
            f.write(base64.b64decode(b64))
        print(f"✅ 人脸验证二维码(base64): {out}", flush=True)
    else:
        await page.screenshot(path=out, clip={"x": 570, "y": 180, "width": 300, "height": 300})
        print(f"✅ 人脸验证二维码(截图): {out}", flush=True)
    write_latest(out)
    write_state("FACE_QR_READY", out)
    return out


async def wait_for_login(page, context, browser) -> str:
    """等待登录完成，自动处理验证流程"""
    face_clicked = False
    face_qr_saved = False
    face_scan_wait_start = 0
    last_qr_hash = None
    last_qr_check = time.monotonic()  # 初始化为当前时间，避免首次循环立即触发

    while True:
        if await check_logged_in(page):
            return await save_login_success(page, context, browser)

        # ★ 持续监控二维码刷新：抖音码约每 30 秒刷新一次，
        #   检测到内容变化就自动提取保存（时间序列命名），保证最新
        now = time.monotonic()
        if now - last_qr_check >= 30:
            last_qr_check = now
            try:
                new_qr = await extract_qr(page)
                if new_qr and os.path.exists(new_qr):
                    with open(new_qr, "rb") as f:
                        h = hashlib.md5(f.read()).hexdigest()
                    if h != last_qr_hash:
                        last_qr_hash = h
                        write_latest(new_qr)
                        write_state("QR_READY", new_qr)
                        print(f"🔄 二维码已刷新(新时间序列): {os.path.basename(new_qr)}", flush=True)
                # ★ 无条件截图（每30秒都截最新的，保证发送时总有新鲜截图）
                await save_page_shot(page)
            except Exception as e:
                print(f"⚠️ 二维码刷新检测失败: {str(e)[:60]}", flush=True)

        try:
            uc_verify =  page.locator("#uc-second-verify")
            if await uc_verify.count() > 0:
                print("🔒 检测到 #uc-second-verify 二次校验!", flush=True)
                clicked = await click_face_verify(page)
                face_clicked = True
        except Exception:
            pass

        if face_clicked and not face_qr_saved:
            face_qr_path = await extract_face_qr(page)
            face_qr_saved = True
            face_scan_wait_start = time.monotonic()
            print(f"📱 请用抖音 APP 扫描人脸验证二维码: {face_qr_path}", flush=True)

        if face_qr_saved and face_scan_wait_start > 0:
            elapsed = time.monotonic() - face_scan_wait_start
            if elapsed >= 10:
                if await check_logged_in(page):
                    return await save_login_success(page, context, browser)
                if elapsed >= 120:
                    print("⚠️ 人脸验证超时，需要重新扫码", flush=True)
                    write_state("FACE_TIMEOUT", "人脸验证超时")
                    return "RETRY"

        try:
            expired = await page.evaluate("""() => {
                const scan = document.querySelector('#douyin_login_comp_scan_code');
                if (!scan) return false;
                const text = scan.innerText || '';
                return text.includes('二维码已过期') || text.includes('二维码失效') ||
                       text.includes('验证失败') || text.includes('验证过期');
            }""")
            if expired:
                print("⚠️ 二维码已过期或验证失败，需要重新扫码!", flush=True)
                write_state("EXPIRED", "二维码过期")
                return "RETRY"
        except Exception:
            pass

        # ★ 页面禁止自动 reload（用户扫码确认期间绝不能刷新页面，
        #   否则二维码换新会导致用户手机确认的旧码作废 → 登录失败）。
        #   只有页面明确显示「二维码已过期/失效」才返回 RETRY 重试。
        #   需要新码时由外部重启进程（重启=新页面新码）。
        await page.wait_for_timeout(3000)


async def main():
    print("=" * 56)
    print("抖音创作者中心 扫码登录")
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
        # 匿名性注入（stealth_core）
        await context.add_init_script(STEALTH_SCRIPT)
        page = await context.new_page()

        while True:
            state = await goto_login(page)
            if state == "ALREADY_LOGGED":
                print("🎉 已登录！", flush=True)
                await context.storage_state(path=str(ACCOUNT_FILE))
                write_state("SUCCESS", str(ACCOUNT_FILE))
                await context.close()
                await browser.close()
                return
            if state != "QR_READY":
                print("⚠️ 二维码未出现，重载", flush=True)
                await page.wait_for_timeout(3000)
                continue

            qr_path = await extract_qr(page)
            write_latest(qr_path)
            write_state("QR_READY", qr_path)
            # ★ 首次即截完整页面（含二维码）
            # await save_page_shot(page)
            print(f"⏳ 等待扫码...（不自动 reload，避免打断登录确认）", flush=True)
            print(f"   📱 用抖音 APP 扫一扫二维码: {qr_path}", flush=True)
            print(f"   💡 提示: 扫码后请在手机上点「确认登录」", flush=True)
            login_result = await wait_for_login(page, context, browser)
            if login_result == "SUCCESS":
                return
            print("⚠️ 验证未通过，重新获取二维码...", flush=True)
            await page.wait_for_timeout(3000)

        await context.close()
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
