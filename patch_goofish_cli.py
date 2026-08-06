#!/usr/bin/env python3
"""修复 goofish-cli 硬编码矛盾指纹 — 一键应用补丁。

问题（2026-08-06 发现）:
  goofish-cli 的 session.py/mtop.py 硬编码 macOS 指纹:
    - USER_AGENT: "Macintosh; Intel Mac OS X 10_15_7 Chrome/146"
    - sec-ch-ua-platform: '"macOS"'
    - sec-ch-ua: v="146"
  但实际运行环境是 Linux+Xvfb + Chrome/150，UA-CH 头、TLS 指纹、系统字体
  全部暴露真实 Linux，与伪造的 MacIntel 交叉比对立刻识破 — 矛盾信号。

修复:
  session.py: 新增 _detect_platform()/ _detect_chrome_version() 动态检测
  mtop.py:    sec-ch-ua / sec-ch-ua-platform 动态取真实平台与版本

运行: python3 patch_goofish_cli.py
"""
import sys
from pathlib import Path

SITE_PKG = Path.home() / ".local/share/uv/tools/goofish-cli/lib/python3.11/site-packages"
SESSION_PY = SITE_PKG / "goofish_cli" / "core" / "session.py"
MTOP_PY = SITE_PKG / "goofish_cli" / "core" / "mtop.py"


def patch_file(path: Path, old: str, new: str, desc: str) -> bool:
    if not path.exists():
        print(f"❌ {path} 不存在")
        return False
    text = path.read_text()
    if new.splitlines()[1] in text:
        print(f"✅ 已打过补丁: {desc}")
        return True
    if old not in text:
        print(f"⚠️ 未找到目标文本: {desc}")
        return False
    path.write_text(text.replace(old, new))
    print(f"✅ 已修复: {desc}")
    return True


def main() -> None:
    print(f"🔧 修复 goofish-cli 硬编码指纹 ({SESSION_PY.parent})")

    # 1. session.py — UA 动态化
    old_ua = '''DEVICE_CACHE_PATH = Path.home() / ".goofish-cli" / "device.json"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/146.0.0.0 Safari/537.36"
)'''
    new_ua = '''DEVICE_CACHE_PATH = Path.home() / ".goofish-cli" / "device.json"


def _detect_platform() -> str:
    """检测真实平台 — 避免硬编码 macOS 造成矛盾信号（Linux+Xvfb vs MacIntel）。"""
    import platform as _p
    sysname = _p.system().lower()
    if sysname == "darwin":
        return "Macintosh; Intel Mac OS X 10_15_7"
    if sysname == "windows":
        return "Windows NT 10.0; Win64; x64"
    return "X11; Linux x86_64"


def _detect_chrome_version() -> str:
    """检测真实 Chrome 版本 — 避免硬编码 146 vs 实际 150。"""
    import re, shutil, subprocess
    for exe in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        path = shutil.which(exe)
        if path:
            try:
                out = subprocess.run([path, "--version"], capture_output=True, text=True, timeout=10).stdout
                # Chrome 输出格式: "Google Chrome 150.0.7871.128"（空格分隔）
                m = re.search(r"Chrome[/ ](\\d+\\.\\d+\\.\\d+\\.\\d+)", out)
                if m:
                    return m.group(1)
            except Exception:
                pass
    return "146.0.0.0"


_PLATFORM = _detect_platform()
_CHROME_VER = _detect_chrome_version()
USER_AGENT = (
    f"Mozilla/5.0 ({_PLATFORM}) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    f"Chrome/{_CHROME_VER} Safari/537.36"
)'''
    patch_file(SESSION_PY, old_ua, new_ua, "session.py USER_AGENT 动态化")

    # 2. mtop.py — import 动态变量
    old_imp = "from goofish_cli.core.session import USER_AGENT, Session"
    new_imp = "from goofish_cli.core.session import USER_AGENT, _CHROME_VER, _PLATFORM, Session"
    patch_file(MTOP_PY, old_imp, new_imp, "mtop.py import 动态变量")

    # 3. mtop.py — sec-ch-ua 动态化
    old_hdr = '''def default_headers() -> dict[str, str]:
    return {
        "accept": "application/json",
        "accept-language": "en,zh-CN;q=0.9,zh;q=0.8,zh-TW;q=0.7,ja;q=0.6",
        "cache-control": "no-cache",
        "content-type": "application/x-www-form-urlencoded",
        "origin": "https://www.goofish.com",
        "pragma": "no-cache",
        "priority": "u=1, i",
        "referer": "https://www.goofish.com/",
        "sec-ch-ua": '"Chromium";v="146", "Not-A.Brand";v="24", "Google Chrome";v="146"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"macOS"','''
    new_hdr = '''def default_headers() -> dict[str, str]:
    # sec-ch-ua 动态取真实 Chrome 版本（与 USER_AGENT 一致，避免矛盾信号）
    _v = _CHROME_VER.split(".")[0]
    return {
        "accept": "application/json",
        "accept-language": "en,zh-CN;q=0.9,zh;q=0.8,zh-TW;q=0.7,ja;q=0.6",
        "cache-control": "no-cache",
        "content-type": "application/x-www-form-urlencoded",
        "origin": "https://www.goofish.com",
        "pragma": "no-cache",
        "priority": "u=1, i",
        "referer": "https://www.goofish.com/",
        "sec-ch-ua": f'"Chromium";v="{_v}", "Not.A/Brand";v="24", "Google Chrome";v="{_v}"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": f'"{"macOS" if "Macintosh" in _PLATFORM else "Windows" if "Windows" in _PLATFORM else "Linux"}"','''
    patch_file(MTOP_PY, old_hdr, new_hdr, "mtop.py sec-ch-ua 动态化")

    print("\n完成。验证: python3 -c \"from goofish_cli.core.session import USER_AGENT; print(USER_AGENT)\"")


if __name__ == "__main__":
    main()
