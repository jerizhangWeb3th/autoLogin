"""中国电商/社交平台扫码登录 — 共享配置。

统一管理浏览器指纹伪装参数、路径、常量。
所有平台共用同一套 stealth 伪装 + Xvfb 有头模式。

⚠️ 一致性原则（重要）：
  伪装分两层，必须互相匹配，否则风控一比对就露馅：
  1. launch 参数层（本文件的 launch_kwargs）
  2. JS 注入层（stealth.py）
  例：stealth 声明 devicePixelRatio=2 / platform=MacIntel / maxTouchPoints=0，
      这里的 device_scale_factor / UA / has_touch 必须与之一致。
"""

import os
from pathlib import Path

# ============================================================
# 浏览器指纹（完整伪装，防止被阿里/小红书风控识别）
# 与 stealth.py 中的 JS 伪装保持一致！
# ============================================================
VIEWPORT = {"width": 1440, "height": 900}
DEVICE_SCALE_FACTOR = 2          # 匹配 stealth devicePixelRatio=2（Retina Mac）
HAS_TOUCH = False                # 匹配 stealth maxTouchPoints=0（Mac 无触屏）
IS_MOBILE = False
COLOR_SCHEME = "light"           # 匹配 stealth prefers-color-scheme
REDUCED_MOTION = "no-preference" # 匹配 stealth prefers-reduced-motion
FORCED_COLORS = "none"
LOCALE = "zh-CN"
TIMEZONE = "Asia/Shanghai"
GEOLOCATION = {"latitude": 34.2611, "longitude": 108.9421}  # 西安
PERMISSIONS = ["geolocation", "notifications"]
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
# sec-ch-ua 系列头必须与 UA 版本(Chrome 126)匹配
EXTRA_HEADERS = {
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "sec-ch-ua": '"Not/A)Brand";v="8", "Chromium";v="126", "Google Chrome";v="126"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
}
LAUNCH_ARGS = [
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-blink-features=AutomationControlled",
    "--window-size=1440,900",
    "--lang=zh-CN",
    "--force-color-profile=srgb",
    "--disable-dev-shm-usage",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-extensions",
    "--disable-background-networking",
    "--disable-sync",
]

# ============================================================
# 路径
# ============================================================
HOME = Path.home()

# Xvfb 虚拟显示器（有头模式必需）
DISPLAY = ":99"

# 闲鱼
GOOFISH_PROFILE_DIR = HOME / ".goofish-cli" / "browser-profile"
GOOFISH_COOKIE_FILE = HOME / ".goofish-cli" / "cookies.json"
GOOFISH_LOGIN_URL = (
    "https://passport.goofish.com/mini_login.htm"
    "?lang=zh_cn&appName=xianyu&appEntrance=web"
)

# 小红书
XHS_PROFILE_DIR = HOME / ".social-auto-upload" / "profiles" / "xhs-login"
XHS_COOKIE_FILE = (
    HOME
    / ".local/share/uv/tools/social-auto-upload/lib/python3.11/site-packages"
    / "cookies"
    / "xiaohongshu_hermes.json"
)

# 截图输出
ASSETS_DIR = Path(__file__).parent / "assets"
ASSETS_DIR.mkdir(exist_ok=True)

# 二维码生成（qrcode 库所在 python）
QR_PYTHON = "/tmp/qrenv/bin/python"

# stealth 伪装脚本（与 config.py 同目录）
STEALTH_PATH = Path(__file__).parent / "stealth.py"


def launch_kwargs() -> dict:
    """统一的 launch_persistent_context 参数（与 stealth.py 保持一致）。"""
    return {
        "channel": "chrome",
        "headless": False,
        "viewport": VIEWPORT,
        "device_scale_factor": DEVICE_SCALE_FACTOR,  # 匹配 stealth devicePixelRatio=2
        "has_touch": HAS_TOUCH,                      # 匹配 stealth maxTouchPoints=0
        "is_mobile": IS_MOBILE,
        "color_scheme": COLOR_SCHEME,
        "reduced_motion": REDUCED_MOTION,
        "forced_colors": FORCED_COLORS,
        "locale": LOCALE,
        "timezone_id": TIMEZONE,
        "geolocation": GEOLOCATION,
        "permissions": PERMISSIONS,
        "user_agent": USER_AGENT,
        "extra_http_headers": EXTRA_HEADERS,
        "args": LAUNCH_ARGS,
    }


def ensure_xvfb() -> bool:
    """确保 Xvfb :99 虚拟显示器在运行。"""
    import subprocess

    r = subprocess.run(["pgrep", "-f", f"Xvfb {DISPLAY}"], capture_output=True, text=True)
    if r.returncode == 0:
        return True
    subprocess.Popen(
        ["Xvfb", DISPLAY, "-screen", "0", "1440x900x24"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    os.environ["DISPLAY"] = DISPLAY
    return True
