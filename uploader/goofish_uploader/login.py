#!/usr/bin/env python3
"""
闲鱼（Goofish）扫码登录 —— 最终完善版

完整登录状态机（每步输出 STATE:<状态> <payload>，供外部读取状态文件）：
  1. QR_READY       二维码就绪，等待用户扫码
  2. SCANNED        用户已扫码（首页 cookie 发生变化）
  3. FACE_QR_READY  触发人脸/身份验证，已自动截取人脸识别二维码
  4. SUCCESS        登录成功（三件套 + 可选 sgcookie 齐 + 首页 iframe 消失）
  5. TIMEOUT        超时

【登录路径】www.goofish.com 首页 → 触发 #alibaba-login-box iframe
            → iframe 内 .qrcode-login canvas 是真二维码 → 截图发用户
【环境自洽】真实 Linux UA + 系统 Chrome + 干净 tmp profile + 最小 stealth
            （只隐藏 webdriver，不做 macOS/Canvas/WebGL/Audio 指纹伪造——
             避免 Linux+Xvfb 与 MacIntel 矛盾信号触发风控）
【扫码判定】① 首页代码检测：#alibaba-login-box iframe 消失 + 首页跳转
           ② cookie 三件套 _m_h5_tk + unb + cookie2 齐
【人脸验证】扫码确认后若出现 ivActionType cookie 或"人脸/身份验证"文本，
            等 10 秒让人脸验证二维码生成，扫描所有 frame 截取清晰二维码自动发送
"""
import asyncio
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

# playwright/patchright（sau 安装目录）
_sau = str(Path.home() / ".local/share/uv/tools/social-auto-upload/lib/python3.11/site-packages")
if _sau not in sys.path:
    sys.path.insert(0, _sau)

from core.stealth import find_chrome, ensure_display  # noqa: E402

QR_DIR = BASE_DIR / "qr"
COOKIE_DIR = BASE_DIR / "cookies"
QR_DIR.mkdir(exist_ok=True)
COOKIE_DIR.mkdir(exist_ok=True)

ACCOUNT_FILE = COOKIE_DIR / "goofish_cookies.json"
GOOFISH_CLI_COOKIE = Path.home() / ".goofish-cli" / "cookies.json"
STATE_FILE = BASE_DIR / "login_state.txt"
QR_OUT = str(QR_DIR / "goofish_qr_login.png")
FACE_QR_OUT = str(QR_DIR / "goofish_face_qr.png")
STATUS_SHOT = str(QR_DIR / "goofish_status.png")
HOME_URL = "https://www.goofish.com"

# 扫码 + 手机确认后下发的完整 session 三件套（对齐 goofish-cli）
_REQUIRED = ("_m_h5_tk", "unb", "cookie2")
# 人脸验证完成后的标志 cookie
_FACE_COOKIE = "sgcookie"
# 触发人脸验证的 cookie 标志（identity verify action type）
_FACE_TRIGGER_COOKIE = "ivActionType"
# 人脸验证触发文本关键词
_FACE_KEYWORDS = ("人脸", "身份验证", "identity_verify", "安全验证", "扫脸")
# 总超时（秒）
_TIMEOUT = 600


def _detect_platform() -> str:
    """真实平台 — 不硬编码 macOS，避免 Linux+Xvfb vs MacIntel 矛盾信号。"""
    return "X11; Linux x86_64"


def _detect_chrome_version() -> str:
    """检测真实 Chrome 版本。"""
    for exe in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        p = shutil.which(exe)
        if p:
            try:
                out = subprocess.run([p, "--version"], capture_output=True, text=True, timeout=10).stdout
                m = re.search(r"Chrome[/ ](\d+\.\d+\.\d+\.\d+)", out)
                if m:
                    return m.group(1)
            except Exception:
                pass
    return "150.0.0.0"


USER_AGENT = (
    f"Mozilla/5.0 ({_detect_platform()}) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    f"Chrome/{_detect_chrome_version()} Safari/537.36"
)


def write_state(state: str, payload: str = ""):
    """写状态文件 + 打印（供外部进程/平台读取登录进度）。"""
    STATE_FILE.write_text(f"{state} {payload}".strip())
    print(f"STATE:{state} {payload}", flush=True)


async def _snap_cookies(context) -> dict:
    """当前 context 的全部非空 cookie → {name: value}。"""
    return {c["name"]: c["value"] for c in await context.cookies() if c.get("value")}


async def _find_face_qr(page, frame) -> object:
    """扫描主页面 + 原 iframe + 所有子 frame，找人脸验证二维码元素。"""
    selectors = ("canvas", "img[src*='qr']", "img[src*='code']", ".qrcode-login img")
    # 1. 原 iframe（含 .qrcode-login canvas）
    try:
        for sel in (".qrcode-login canvas", *selectors):
            el = await frame.query_selector(sel)
            if el:
                return el
    except Exception:
        pass
    # 2. 主页面
    try:
        for sel in selectors:
            el = await page.query_selector(sel)
            if el:
                return el
    except Exception:
        pass
    # 3. 所有子 frame（人脸验证可能在新的 iframe）
    try:
        for f in page.frames:
            if f == page.main_frame:
                continue
            for sel in selectors:
                el = await f.query_selector(sel)
                if el:
                    return el
    except Exception:
        pass
    return None


async def _check_home_logged_in(page, frame) -> bool:
    """首页代码检测：passport iframe 消失 且 首页不再跳转登录 = 已登录。"""
    try:
        iframe_exists = await page.query_selector("#alibaba-login-box") is not None
        if not iframe_exists:
            return True
    except Exception:
        pass
    return False


async def main():
    print("=" * 56)
    print("闲鱼（Goofish）扫码登录 — 最终完善版")
    print("=" * 56)

    ensure_display()
    chrome = find_chrome()
    print(f"Chrome: {chrome}", flush=True)
    print(f"UA: {USER_AGENT}", flush=True)

    try:
        from playwright.async_api import async_playwright
        _ENGINE = "playwright"
    except ImportError:
        from patchright.async_api import async_playwright
        _ENGINE = "patchright"
    print(f"引擎: {_ENGINE}", flush=True)

    # 干净 tmp profile —— 避免残留登录态导致首页不触发 iframe
    profile_dir = tempfile.mkdtemp(prefix="goofish-", dir="/tmp")

    async with async_playwright() as pw:
        launch_kwargs = dict(
            user_data_dir=profile_dir,
            headless=False,
            viewport={"width": 1440, "height": 900},
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
            user_agent=USER_AGENT,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-default-browser-check",
                "--no-first-run",
                "--no-sandbox",
            ],
        )
        if chrome:
            launch_kwargs["executable_path"] = chrome

        context = await pw.chromium.launch_persistent_context(**launch_kwargs)
        # 最小 stealth：只隐藏 webdriver 标志（不做指纹伪造）
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        )
        page = context.pages[0] if context.pages else await context.new_page()

        # 1. 首页 → 触发 passport iframe
        await page.goto(HOME_URL, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(2000)

        # 2. 等 #alibaba-login-box iframe
        try:
            iframe_el = await page.wait_for_selector("#alibaba-login-box", timeout=15000)
        except Exception as e:
            print(f"⚠️ 未检测到 passport iframe: {e}", flush=True)
            shot = str(QR_DIR / "goofish_home.png")
            await page.screenshot(path=shot, full_page=True)
            print(f"📸 首页截图: {shot}", flush=True)
            write_state("IFRAME_MISSING", shot)
            await context.close()
            shutil.rmtree(profile_dir, ignore_errors=True)
            return

        frame = await iframe_el.content_frame()
        if not frame:
            print("⚠️ iframe content_frame 未就绪", flush=True)
            write_state("IFRAME_MISSING", "")
            await context.close()
            shutil.rmtree(profile_dir, ignore_errors=True)
            return
        await frame.wait_for_load_state("domcontentloaded", timeout=5000)

        # 3. 等 .qrcode-login canvas 渲染 → 截二维码
        try:
            qr_el = await frame.wait_for_selector(".qrcode-login canvas", timeout=15000)
        except Exception as e:
            print(f"⚠️ 二维码 canvas 未渲染: {e}", flush=True)
            shot = str(QR_DIR / "goofish_iframe.png")
            await frame.screenshot(path=shot)
            print(f"📸 iframe 截图: {shot}", flush=True)
            write_state("QR_MISSING", shot)
            await context.close()
            shutil.rmtree(profile_dir, ignore_errors=True)
            return

        await qr_el.screenshot(path=QR_OUT)
        size = os.path.getsize(QR_OUT)
        print(f"✅ 登录二维码: {QR_OUT} ({size // 1024}KB)", flush=True)
        write_state("QR_READY", QR_OUT)

        # 4. 轮询：首页代码检测 + cookie 检测 → 判定扫码/人脸验证/登录成功
        print(f"⏳ 等待扫码（最长{_TIMEOUT}s）...", flush=True)
        deadline = time.monotonic() + _TIMEOUT
        logged_in = False
        face_qr_sent = False
        scanned_once = False
        tick = 0
        last_names = {c["name"] for c in await context.cookies()}

        while time.monotonic() < deadline:
            await asyncio.sleep(1.0)
            tick += 1
            cookies = await _snap_cookies(context)
            names_now = set(cookies.keys())

            # 登录成功判定：三件套齐（人脸验证后 sgcookie 也会齐）
            if all(k in cookies for k in _REQUIRED):
                print(f"🎯 登录成功（unb={cookies['unb'][:4]}****）", flush=True)
                await page.screenshot(path=STATUS_SHOT, full_page=True)
                print(f"📸 登录成功截图: {STATUS_SHOT}", flush=True)
                write_state("SUCCESS_SHOT", STATUS_SHOT)
                logged_in = True
                break

            # 首页代码检测：扫码成功（cookie 变化）或登录成功（iframe 消失）
            if names_now != last_names:
                new = names_now - last_names
                print(f"🔔 cookie 变化（新增 {sorted(new)}）", flush=True)
                await page.screenshot(path=STATUS_SHOT, full_page=True)
                print(f"📸 扫码后页面截图: {STATUS_SHOT}", flush=True)
                write_state("SCANNED", STATUS_SHOT)
                last_names = names_now
                scanned_once = True

            if scanned_once and await _check_home_logged_in(page, frame):
                # 首页 iframe 已消失 = 已登录（但可能还没下发完整三件套，继续等）
                print("🔔 首页 passport iframe 已消失（登录态已建立）", flush=True)

            # 人脸验证检测：扫码确认后触发二次人脸验证
            if not face_qr_sent:
                triggered = _FACE_TRIGGER_COOKIE in names_now
                if not triggered:
                    texts = []
                    try:
                        texts.append(await page.evaluate("document.body ? document.body.innerText : ''"))
                    except Exception:
                        pass
                    try:
                        texts.append(await frame.evaluate("document.body ? document.body.innerText : ''"))
                    except Exception:
                        pass
                    combined = " ".join(texts)
                    triggered = any(k in combined for k in _FACE_KEYWORDS)

                if triggered:
                    # 等待人脸验证二维码生成（约 10 秒）
                    print("🔔 检测到身份验证，等待二维码生成...", flush=True)
                    await asyncio.sleep(10)
                    face_qr = await _find_face_qr(page, frame)
                    if face_qr:
                        await face_qr.screenshot(path=FACE_QR_OUT)
                        print(f"📱 请扫码完成人脸验证: {FACE_QR_OUT}", flush=True)
                        write_state("FACE_QR_READY", FACE_QR_OUT)
                    else:
                        await page.screenshot(path=FACE_QR_OUT, full_page=True)
                        print(f"📱 人脸验证页整页截图: {FACE_QR_OUT}", flush=True)
                        write_state("FACE_QR_READY", FACE_QR_OUT)
                    face_qr_sent = True

            # 定期静默截图（每 5 秒，供用户扫码后查看最新页面状态）
            if tick % 5 == 0:
                try:
                    await page.screenshot(path=STATUS_SHOT, full_page=True)
                except Exception:
                    pass

        if not logged_in:
            print("❌ 等待扫码超时", flush=True)
            write_state("TIMEOUT", "scan")
            await context.close()
            shutil.rmtree(profile_dir, ignore_errors=True)
            return

        # 5. 保存 cookie（两种格式）
        await asyncio.sleep(3)
        cookies = await _snap_cookies(context)

        # playwright storage_state（autoLogin 项目用）
        await context.storage_state(path=str(ACCOUNT_FILE))
        # goofish-cli cookies.json（Chrome 扩展格式）
        GOOFISH_CLI_COOKIE.parent.mkdir(parents=True, exist_ok=True)
        GOOFISH_CLI_COOKIE.write_text(
            json.dumps([{"name": k, "value": v} for k, v in cookies.items()],
                       ensure_ascii=False, indent=2)
        )
        GOOFISH_CLI_COOKIE.chmod(0o600)

        has_face = _FACE_COOKIE in cookies
        print(f"✅ cookie 已保存: {ACCOUNT_FILE} ({len(cookies)} 项)", flush=True)
        print(f"✅ goofish-cli: {GOOFISH_CLI_COOKIE}", flush=True)
        print(f"{'✅' if has_face else '⚠️'} 人脸验证 sgcookie: {'已下发' if has_face else '未下发（可能无需人脸）'}", flush=True)
        write_state("SUCCESS", str(ACCOUNT_FILE))

        await context.close()
        shutil.rmtree(profile_dir, ignore_errors=True)


if __name__ == "__main__":
    asyncio.run(main())
