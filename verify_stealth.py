#!/usr/bin/env python3
"""原生浏览器指纹检查 — 验证"减少伪装"后的真实指纹一致性。

设计原则（与 README 一致）：
  真 Chrome + 持久化 Profile + Patchright 原生能力，不做硬编码指纹伪造。
  本脚本检查：
  1. launch 参数收敛：只用了 channel/headless/no_viewport/locale/timezone
  2. 浏览器环境自洽：webdriver 应为 false（Patchright 已处理）、
     devicePixelRatio 与真实显示器一致、无自相矛盾的特征
  3. 不输出 Cookie 值/账号标识等敏感信息

运行: python3 verify_stealth.py
"""
import sys, os, asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
# patchright 安装路径（uv tool 安装位置）
for p in [
    str(Path.home() / ".local/share/uv/tools/patchright/lib/python3.11/site-packages"),
]:
    if p not in sys.path:
        sys.path.insert(0, p)
os.environ.setdefault("DISPLAY", ":99")

import config
from patchright.async_api import async_playwright


async def main():
    config.ensure_xvfb()
    print("=" * 60)
    print("原生浏览器指纹检查（减少伪装 / 提高一致性）")
    print("=" * 60)

    kwargs = config.launch_kwargs()
    print(f"\nlaunch 参数: {kwargs}")

    # 1. 参数收敛检查
    print("\n【1】参数收敛检查")
    allowed = {"channel", "headless", "no_viewport", "locale", "timezone_id", "args"}
    extra = set(kwargs) - allowed
    if extra:
        print(f"  ⚠️ 存在非常规参数: {extra}")
    else:
        print(f"  ✅ 参数已收敛到最小集合")
    if "user_agent" in kwargs or "extra_http_headers" in kwargs:
        print("  ❌ 不应自定义 UA / headers")
    else:
        print("  ✅ 未自定义 UA / headers（Patchright 官方建议）")

    async with async_playwright() as pw:
        context = await pw.chromium.launch_persistent_context(
            user_data_dir=str(Path.home() / ".verify-native-profile"),
            **kwargs,
        )
        page = context.pages[0] if context.pages else await context.new_page()
        await page.goto("https://example.com", wait_until="load", timeout=30000)
        await page.wait_for_timeout(2000)

        # 2. 真实指纹自洽性检查
        print("\n【2】浏览器环境自洽性")
        actual = await page.evaluate("""() => ({
            webdriver: navigator.webdriver,
            userAgent: navigator.userAgent,
            platform: navigator.platform,
            dpr: window.devicePixelRatio,
            innerW: window.innerWidth,
            innerH: window.innerHeight,
            outerH: window.outerHeight,
            colorDepth: screen.colorDepth,
            lang: navigator.language,
        })""")

        checks = [
            ("webdriver (应 false)", actual["webdriver"] is False, str(actual["webdriver"])),
            ("UA 含 Headless (应否)", "Headless" not in actual["userAgent"], actual["userAgent"][:60]),
            ("platform 与真实一致", actual["platform"] in ("Linux x86_64", "MacIntel"), actual["platform"]),
            ("colorDepth (应 24)", actual["colorDepth"] == 24, str(actual["colorDepth"])),
            ("语言 zh-CN", actual["lang"].startswith("zh"), actual["lang"]),
            ("outerHeight 非 0 (有头)", actual["outerH"] > 0, str(actual["outerH"])),
        ]
        for name, ok, val in checks:
            mark = "✅" if ok else "❌"
            print(f"  {mark} {name:<28} {val}")

        # 3. 窗口尺寸关系（no_viewport=True 下真实产生）
        print(f"\n  inner: {actual['innerW']}x{actual['innerH']}  outer: {actual['outerH']}  dpr: {actual['dpr']}")
        if actual["outerH"] >= actual["innerH"]:
            print("  ✅ outer >= inner（真实窗口关系）")
        else:
            print("  ⚠️ outer < inner（可能异常）")

        await context.close()

    print("\n" + "=" * 60)
    print("检查完成（本脚本不输出任何 Cookie / 账号标识）")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
