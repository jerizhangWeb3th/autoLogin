#!/usr/bin/env python3
"""
小红书扫码登录模块（状态机 + 二次认证 + 二维码过期自动刷新）

【流程】
  1. 访问首页 → 跳转登录页 → 提取登录二维码 → 发用户
  2. 用户扫码 → 可能直接成功，可能触发二次认证
  3. 二维码过期（超时/页面"失效"提示）→ 自动重新加载登录页 → 重新发码
  4. 保存 cookie（web_session = 登录成功标志）

【电脑端伪装】MAC_UA（macOS Chrome）+ 桌面 viewport + 持久化 Profile（环境自洽）
【默认扫码登录】不主动走手机号/验证码，除非用户明确要求
"""
import asyncio
import os
import sys
import time
import base64
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

# patchright（sau 安装目录）
_sau = str(Path.home() / ".local/share/uv/tools/social-auto-upload/lib/python3.11/site-packages")
if _sau not in sys.path:
    sys.path.insert(0, _sau)

from core.stealth import MAC_UA, LAUNCH_ARGS, find_chrome, ensure_display  # noqa: E402

QR_DIR = BASE_DIR / "qr"
COOKIE_DIR = BASE_DIR / "cookies"
PROFILE_DIR = BASE_DIR / "profile" / "xhs"
QR_DIR.mkdir(exist_ok=True)
COOKIE_DIR.mkdir(exist_ok=True)
PROFILE_DIR.mkdir(parents=True, exist_ok=True)

ACCOUNT_FILE = COOKIE_DIR / "xiaohongshu_hermes.json"
STATE_FILE = BASE_DIR / "login_state.txt"
QR_LATEST_FILE = BASE_DIR / "qr_latest.txt"

# 二维码有效期（秒）：小红书二维码约 2 分钟失效，留出用户扫码+确认时间
QR_TTL = 150


def ts() -> str:
    return time.strftime("%Y%m%d_%H%M%S")


def write_state(state: str, payload: str = ""):
    STATE_FILE.write_text(f"{state} {payload}".strip())
    print(f"STATE:{state} {payload}", flush=True)


def write_latest(path: str):
    """写最新二维码路径 + 清理旧码（只动 xhs_qr_*.png）"""
    try:
        for old in QR_DIR.glob("xhs_qr_*.png"):
            if str(old) != path:
                old.unlink(missing_ok=True)
    except Exception:
        pass
    QR_LATEST_FILE.write_text(path)
    print(f"📡 最新二维码: {path}", flush=True)


async def get_qr_src(page) -> str:
    """精确提取登录二维码 img.qrcode-img 的 src（不写文件）"""
    try:
        return await page.evaluate("""() => {
            const img = document.querySelector('img.qrcode-img');
            return img ? (img.src || '') : null;
        }""") or ""
    except Exception:
        return ""


def save_qr(src: str) -> str:
    """把二维码 base64 src 落盘，返回路径（空 src 返回空串）"""
    if not src or "," not in src:
        return ""
    out = str(QR_DIR / f"xhs_qr_{ts()}.png")
    try:
        with open(out, "wb") as f:
            f.write(base64.b64decode(src.split(",", 1)[1]))
        print(f"✅ 小红书二维码: {out} ({os.path.getsize(out)//1024}KB)", flush=True)
        return out
    except Exception as e:
        print(f"⚠️ 二维码解码失败: {str(e)[:60]}", flush=True)
        return ""


async def check_logged_in(page) -> bool:
    """检测真实登录：登录模态框消失 且 右上角无"登录"按钮"""
    try:
        return bool(await page.evaluate("""() => {
            // 1. 登录模态框必须关闭（不存在或隐藏）
            const modal = document.querySelector('.login-modal, [class*="login-modal"], .reds-modal-open');
            if (modal) {
                const s = getComputedStyle(modal);
                if (s.display !== 'none' && s.visibility !== 'hidden') return false;
            }
            // 2. 右上角 side-bar 不能还有"登录"按钮
            const loginBtns = [...document.querySelectorAll('[class*="side-bar"] [class*="login"], [class*="side-bar"] button')].filter(el => {
                const t = (el.textContent || '').trim();
                return t === '登录' && el.offsetParent !== null;
            });
            if (loginBtns.length > 0) return false;
            return true;
        }"""))
    except Exception:
        return False


async def check_expired(page) -> bool:
    """检测登录模态框内是否显示二维码已失效/过期提示（只盯登录框，避免误触发）"""
    try:
        return await page.evaluate("""() => {
            const modal = document.querySelector('.login-modal, [class*="login-modal"], .login-container');
            if (!modal) return false;
            const t = modal.innerText || '';
            return t.includes('已失效') || t.includes('已过期') || t.includes('二维码失效') || t.includes('点击刷新');
        }""")
    except Exception:
        return False


async def main():
    print("=" * 56)
    print("小红书 扫码登录（状态机 + 二次认证 + 过期自动刷新）")
    print("=" * 56)

    ensure_display()
    chrome = find_chrome()
    if chrome:
        print(f"Chrome: {chrome}")

    from patchright.async_api import async_playwright

    async with async_playwright() as pw:
        # 持久化 Profile（电脑端伪装，环境自洽）
        context = await pw.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=False,
            args=LAUNCH_ARGS,
            viewport={"width": 1440, "height": 900},
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
            device_scale_factor=2,
            user_agent=MAC_UA,
            executable_path=chrome,
        )
        # ★ 登录页不注入激进 stealth（70+ 检测点会干扰登录轮询 api/qrcode/userinfo）
        #   launch args 已含 --disable-blink-features=AutomationControlled + UA 伪装，登录足够
        page = await context.new_page()

        state = "OPEN_LOGIN"
        last_qr_src = ""
        qr_time = 0.0
        success_count = 0

        while state not in ("SUCCESS", "FAILED"):
            if state == "OPEN_LOGIN":
                write_state("OPEN_LOGIN")
                await page.goto("https://www.xiaohongshu.com", wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(8)
                state = "WAIT_QR"

            elif state == "WAIT_QR":
                write_state("WAIT_QR")
                qr_src = await get_qr_src(page)
                qr_path = save_qr(qr_src) if qr_src else ""
                if qr_path:
                    write_latest(qr_path)
                    write_state("QR_READY", qr_path)
                    last_qr_src = qr_src
                    qr_time = time.time()
                    success_count = 0
                    print(f"📱 请用小红书 APP 扫码（{QR_TTL}s 内有效）: {qr_path}", flush=True)
                    state = "WAIT_SCAN"
                else:
                    # fallback：整页截图
                    shot = str(QR_DIR / f"xhs_page_{ts()}.png")
                    await page.screenshot(path=shot, full_page=False)
                    write_latest(shot)
                    write_state("QR_READY", shot)
                    print(f"📸 页面截图(未找到二维码): {shot}", flush=True)
                    state = "WAIT_SCAN"

            elif state == "WAIT_SCAN":
                # 1. 登录成功（连续 3 次确认，避免页面加载瞬间误判）
                if await check_logged_in(page):
                    success_count += 1
                    if success_count >= 3:
                        print("✅ 登录成功! 检测到真实登录态", flush=True)
                        state = "SUCCESS"
                        continue
                else:
                    success_count = 0
                # 2. 二维码过期检测（超时 OR 页面失效提示）→ 重新加载登录页
                elapsed = time.time() - qr_time
                expired = elapsed > QR_TTL or await check_expired(page)
                if expired:
                    print(f"🔄 二维码过期（{int(elapsed)}s），重新加载登录页...", flush=True)
                    await page.goto("https://www.xiaohongshu.com", wait_until="domcontentloaded", timeout=30000)
                    await asyncio.sleep(5)
                    state = "WAIT_QR"
                    continue
                # 3. 检测二维码自动刷新（src 变化 = 新码）
                qr_src = await get_qr_src(page)
                if qr_src and qr_src != last_qr_src:
                    qr_path = save_qr(qr_src)
                    if qr_path:
                        write_latest(qr_path)
                        write_state("QR_READY", qr_path)
                        last_qr_src = qr_src
                        qr_time = time.time()
                        print(f"🔒 二维码已刷新: {qr_path}", flush=True)
                # 4. 每 3 秒检查一次
                await asyncio.sleep(3)

        # 保存 cookie
        if state == "SUCCESS":
            await asyncio.sleep(2)
            await context.storage_state(path=str(ACCOUNT_FILE))
            print(f"✅ cookie 已保存: {ACCOUNT_FILE}", flush=True)
            write_state("SUCCESS", str(ACCOUNT_FILE))
        else:
            write_state("FAILED")

        await context.close()


if __name__ == "__main__":
    asyncio.run(main())
