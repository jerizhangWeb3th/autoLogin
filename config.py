"""中国电商/社交平台扫码登录 — 共享配置（跨平台：Windows / macOS / Ubuntu）。

设计原则（重要）：
  **减少伪装、提高一致性** — 真 Chrome + 持久化 Profile + Patchright 原生能力，
  不做大量硬编码指纹伪造。原因：
  1. 实际环境是 Linux+Xvfb，却声明 macOS/Retina/Chrome126 等会产生大量矛盾信号
  2. Patchright 官方建议：真 Chrome、持久化上下文、no_viewport=True，
     不要自定义 UA 或 headers
  3. 硬编码伪装（Canvas/WebGL/Audio 改写）比原生浏览器更醒目，且可能破坏页面
  4. 持久化 Profile 积累的真实指纹就是最好的伪装

  Patchright 已处理 --disable-blink-features=AutomationControlled，无需重复设置。

平台兼容（2026-08-07 新增）：
  自动检测 Windows / macOS / Linux(Ubuntu)：
    - Chrome 可执行文件路径
    - DISPLAY / Xvfb（仅 Linux 无显示器环境需要）
    - patchright site-packages 位置（sau 安装目录）
    - cookie 目录（按平台区分）
"""

import os
import sys
import platform
import subprocess
from pathlib import Path

# ============================================================
# 平台检测
# ============================================================
IS_WINDOWS = sys.platform == "win32"
IS_MACOS = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")

# 系统位数判断（macOS 常见）
IS_MAC_ARM = IS_MACOS and platform.machine() in ("arm64", "aarch64")


def find_chrome() -> str:
    """跨平台查找 Chrome 可执行文件路径。"""
    candidates = []
    if IS_WINDOWS:
        candidates = [
            os.environ.get("LOCALAPPDATA", "") + r"\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ]
    elif IS_MACOS:
        candidates = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            os.path.expanduser("~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
        ]
    else:  # Linux
        candidates = [
            "/usr/bin/google-chrome",
            "/usr/bin/google-chrome-stable",
            "/usr/bin/chromium",
            "/usr/bin/chromium-browser",
        ]
    for c in candidates:
        if c and os.path.exists(c):
            return c
    return candidates[0] if candidates else ""


def find_patchright_path() -> str:
    """跨平台查找 patchright site-packages（sau 安装目录）。

    优先用环境变量 SAU_SITE_PACKAGES，否则按平台猜测常见位置。
    """
    env = os.environ.get("SAU_SITE_PACKAGES")
    if env and os.path.isdir(env):
        return env
    home = str(Path.home())
    candidates = []
    if IS_WINDOWS:
        candidates = [
            os.path.join(home, ".local", "share", "uv", "tools", "social-auto-upload", "Lib", "site-packages"),
            os.path.join(home, "AppData", "Roaming", "uv", "tools", "social-auto-upload", "Lib", "site-packages"),
        ]
    elif IS_MACOS:
        candidates = [
            os.path.join(home, ".local", "share", "uv", "tools", "social-auto-upload", "lib", "python3.11", "site-packages"),
        ]
    else:  # Linux
        candidates = [
            os.path.join(home, ".local", "share", "uv", "tools", "social-auto-upload", "lib", "python3.11", "site-packages"),
        ]
    for c in candidates:
        if os.path.isdir(c):
            return c
    return candidates[0] if candidates else ""


def ensure_sau_importable() -> bool:
    """把 sau 的 site-packages 加入 sys.path（含 uploader 模块）。"""
    try:
        import patchright  # noqa: F401
        return True
    except ImportError:
        p = find_patchright_path()
        if p and os.path.isdir(p):
            if p not in sys.path:
                sys.path.insert(0, p)
            return True
    return False


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
    args = []
    if IS_LINUX and (os.geteuid() == 0 or os.environ.get("CONTAINER")):
        args.append("--no-sandbox")
    if args:
        kwargs["args"] = args

    return kwargs


# ============================================================
# 路径
# ============================================================
HOME = Path.home()

# Xvfb 虚拟显示器（仅 Linux 无显示器环境必需；Windows/macOS 有原生桌面）
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
XHS_COOKIE_DIR = (
    HOME
    / ".local/share/uv/tools/social-auto-upload/lib/python3.11/site-packages"
    / "cookies"
)
XHS_COOKIE_FILE = XHS_COOKIE_DIR / "xiaohongshu_hermes.json"


def xhs_cookie_file(account: str) -> Path:
    """按账号名返回小红书 cookie 文件路径（跨平台）。

    Windows/macOS 下优先用项目内 cookies/ 目录（避免权限问题），
    Linux 下用 sau 的 site-packages/cookies（sau CLI 兼容）。
    """
    if IS_WINDOWS or IS_MACOS:
        local = Path(__file__).parent / "cookies"
        local.mkdir(exist_ok=True)
        return local / f"xiaohongshu_{account}.json"
    return XHS_COOKIE_DIR / f"xiaohongshu_{account}.json"

# 截图输出
ASSETS_DIR = Path(__file__).parent / "assets"
ASSETS_DIR.mkdir(exist_ok=True)

# 二维码生成（qrcode 库所在 python）
QR_PYTHON = "/tmp/qrenv/bin/python"


def ensure_display() -> None:
    """确保图形环境就绪。

    - Windows/macOS：原生桌面，无需处理
    - Linux 无显示器：启动 Xvfb :99 虚拟显示器
    """
    if not IS_LINUX:
        return
    ensure_xvfb()


def ensure_xvfb() -> bool:
    """确保 Xvfb :99 虚拟显示器在运行（仅 Linux 无显示器环境）。"""
    if not IS_LINUX:
        return True
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
