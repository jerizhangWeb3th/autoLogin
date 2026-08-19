#!/usr/bin/env python3
"""
小红书扫码登录模块（状态机 + 二次认证支持）

【流程】
  1. 访问首页 → 提取登录二维码 → 发用户
  2. 用户扫码 → 可能直接成功，可能触发二次认证
  3. 二次认证：直接弹出新二维码 → 提取 → 发用户 → 用户扫完成功
  4. 保存 cookie（web_session = 登录成功标志）

【电脑端伪装】MAC_UA（macOS Chrome）+ 桌面 viewport + 持久化 Profile（环境自洽）
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

from core.stealth import MAC_UA, LAUNCH_ARGS, STEALTH_SCRIPT, find_chrome, ensure_display, goto_with_stealth  # noqa: E402

QR_DIR = BASE_DIR / "qr"
COOKIE_DIR = BASE_DIR / "cookies"
PROFILE_DIR = BASE_DIR / "profile" / "xhs"
QR_DIR.mkdir(exist_ok=True)
COOKIE_DIR.mkdir(exist_ok=True)
PROFILE_DIR.mkdir(parents=True, exist_ok=True)

ACCOUNT_FILE = COOKIE_DIR / "xiaohongshu_hermes.json"
STATE_FILE = BASE_DIR / "login_state.txt"
QR_LATEST_FILE = BASE_DIR / "qr_latest.txt"


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


async def extract_qr(page) -> tuple:
    """提取最大的 data:image/png 二维码，返回 (路径, img_src)"""
    info = await page.evaluate("""() => {
        const candidates = [];
        document.querySelectorAll('img').forEach(img => {
            const src = img.src || '';
            if (src.startsWith('data:image/png')) {
                const r = img.getBoundingClientRect();
                candidates.push({src, w: Math.round(r.width || img.width || 0)});
            }
        });
        candidates.sort((a, b) => b.w - a.w);
        return candidates.length > 0 ? candidates[0] : null;
    }""")
    if info and isinstance(info, dict) and info.get("src"):
        out = str(QR_DIR / f"xhs_qr_{ts()}.png")
        try:
            with open(out, "wb") as f:
                f.write(base64.b64decode(info["src"].split(",", 1)[1]))
            print(f"✅ 小红书二维码: {out} ({os.path.getsize(out)//1024}KB)", flush=True)
            return out, info["src"]
        except Exception as e:
            print(f"⚠️ 二维码解码失败: {str(e)[:60]}", flush=True)
    return "", ""


async def check_logged_in(context) -> bool:
    """检测 web_session cookie（小红书登录成功标志）"""
    try:
        cookies = await context.cookies()
        return any(
            c.get("name") == "web_session" and len(c.get("value", "")) > 10
            for c in cookies
        )
    except Exception:
        return False


async def main():
    print("=" * 56)
    print("小红书 扫码登录（状态机 + 二次认证）")
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
        await context.add_init_script(STEALTH_SCRIPT)
        page = await context.new_page()

        state = "OPEN_LOGIN"
        last_qr_src = ""

        while state not in ("SUCCESS", "FAILED"):
            if state == "OPEN_LOGIN":
                write_state("OPEN_LOGIN")
                await goto_with_stealth(page, "https://www.xiaohongshu.com", timeout=30000)
                await asyncio.sleep(8)
                print("✅ stealth 已在页面脚本前注入", flush=True)
                state = "WAIT_QR"

            elif state == "WAIT_QR":
                write_state("WAIT_QR")
                qr_path, qr_src = await extract_qr(page)
                if qr_path:
                    write_latest(qr_path)
                    write_state("QR_READY", qr_path)
                    last_qr_src = qr_src
                    print(f"📱 请用小红书 APP 扫码: {qr_path}", flush=True)
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
                # 1. 登录成功（web_session 出现）
                if await check_logged_in(context):
                    print("✅ 登录成功! 检测到 web_session", flush=True)
                    state = "SUCCESS"
                    continue
                # 2. 检测二次认证（新二维码出现，src 变化）
                qr_path, qr_src = await extract_qr(page)
                if qr_path and qr_src and qr_src != last_qr_src:
                    write_latest(qr_path)
                    write_state("SECOND_QR_READY", qr_path)
                    last_qr_src = qr_src
                    print(f"🔒 检测到二次认证二维码: {qr_path}", flush=True)
                # 3. 每 3 秒检查
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
