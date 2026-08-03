"""中国电商/社交平台扫码登录 — 共享配置。

设计原则（重要）：
  **减少伪装、提高一致性** — 真 Chrome + 持久化 Profile + Patchright 原生能力，
  不做大量硬编码指纹伪造。原因：
  1. 实际环境是 Linux+Xvfb，却声明 macOS/Retina/Chrome126 等会产生大量矛盾信号
  2. Patchright 官方建议：真 Chrome、持久化上下文、no_viewport=True，
     不要自定义 UA 或 headers
  3. 硬编码伪装（Canvas/WebGL/Audio 改写）比原生浏览器更醒目，且可能破坏页面
  4. 持久化 Profile 积累的真实指纹就是最好的伪装

  Patchright 已处理 --disable-blink-features=AutomationControlled，无需重复设置。
"""

import os
import subprocess
from pathlib import Path

# ============================================================
# 浏览器启动参数（收敛到最少，信任真 Chrome 原生指纹）
# ============================================================
def launch_kwargs() -> dict:
    """统一的 launch_persistent_context 参数。

    只保留部署环境确实需要的最小集合：
      - channel="chrome"      真 Chrome（非 bundled chromium）
      - headless=False        Patchright 反检测在 headful 才完整
      - no_viewport=True      窗口尺寸由系统真实产生，不伪造
      - locale/timezone       部署环境匹配（中国大陆）
    """
    kwargs = {
        "channel": "chrome",
        "headless": False,
        "no_viewport": True,
        "locale": "zh-CN",
        "timezone_id": "Asia/Shanghai",
    }

    # 容器/root 环境需要 --no-sandbox；普通桌面环境应移除
    if os.geteuid() == 0 or os.environ.get("CONTAINER"):
        kwargs["args"] = ["--no-sandbox"]

    return kwargs


# ============================================================
# 路径
# ============================================================
HOME = Path.home()

# Xvfb 虚拟显示器（无显示器的服务器环境必需）
DISPLAY = ":99"

# 闲鱼 — 每个平台/账号使用独立且长期稳定的 user_data_dir（不随机）
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

# stealth 伪装脚本 — 保留但默认禁用（不再接入运行流程）
# 参考: 大量 JS 改写（Canvas/WebGL/Audio/Chrome API）可检测且可能破坏页面
STEALTH_PATH = Path(__file__).parent / "stealth.py"
STEALTH_ENABLED = False


def ensure_xvfb() -> bool:
    """确保 Xvfb :99 虚拟显示器在运行（无显示器的服务器环境）。"""
    r = subprocess.run(
        ["pgrep", "-f", f"Xvfb {DISPLAY}"], capture_output=True, text=True
    )
    if r.returncode == 0:
        return True
    subprocess.Popen(
        ["Xvfb", DISPLAY, "-screen", "0", "1440x900x24"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    os.environ["DISPLAY"] = DISPLAY
    return True
