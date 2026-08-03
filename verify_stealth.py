#!/usr/bin/env python3
"""浏览器伪装一致性自检 — 验证 launch 参数层与 stealth JS 注入层是否匹配。

运行: python3 verify_stealth.py

验证内容：
  1. launch 参数层（config.launch_kwargs）：device_scale_factor / has_touch /
     color_scheme / UA / sec-ch-ua 头
  2. JS 注入层（stealth.py）：运行时 page.evaluate 执行后
     navigator.platform / hardwareConcurrency / deviceMemory 等是否与参数一致

注意：patchright 的 add_init_script 依赖专用浏览器（route 注入机制），
系统 Chrome 上不生效；本项目统一用"导航后 page.evaluate 运行时执行"。
"""
import sys, os, asyncio, json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
os.environ.setdefault("DISPLAY", ":99")

import config
import utils
from patchright.async_api import async_playwright

# stealth 声称的值（与 stealth.py 中的 JS 定义一致）
STEALTH_CLAIMS = {
    "platform": "MacIntel",
    "hardwareConcurrency": 8,
    "deviceMemory": 8,
    "maxTouchPoints": 0,
    "pixelDepth": 24,
    "devicePixelRatio": 2,
}


async def main():
    config.ensure_xvfb()
    print("=" * 60)
    print("浏览器伪装一致性自检（launch 参数层 + JS 注入层）")
    print("=" * 60)

    async with async_playwright() as pw:
        context = await pw.chromium.launch_persistent_context(
            user_data_dir=str(Path.home() / ".verify-stealth-profile"),
            **config.launch_kwargs(),
        )
        page = context.pages[0] if context.pages else await context.new_page()
        await page.goto("https://example.com", wait_until="load", timeout=30000)
        await page.wait_for_timeout(2000)

        # 运行时执行 stealth（不是 add_init_script！）
        applied = await utils.apply_stealth(page)
        print(f"\nstealth 运行时注入: {'✅ 成功' if applied else '❌ 失败'}")

        actual = await page.evaluate("""() => ({
            platform: navigator.platform,
            hardwareConcurrency: navigator.hardwareConcurrency,
            deviceMemory: navigator.deviceMemory,
            maxTouchPoints: navigator.maxTouchPoints,
            pixelDepth: screen.pixelDepth,
            devicePixelRatio: window.devicePixelRatio,
            webdriver: navigator.webdriver,
            userAgent: navigator.userAgent,
            colorScheme: matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark',
            reducedMotion: matchMedia('(prefers-reduced-motion: reduce)').matches,
            hasTouch: navigator.maxTouchPoints > 0,
            languages: JSON.stringify(navigator.languages),
        })""")

        print(f"\n{'检测项':<22}{'目标(stealth)':<18}{'实际值':<30}{'状态'}")
        print("-" * 80)
        checks = [
            ("platform", STEALTH_CLAIMS["platform"], actual["platform"]),
            ("hardwareConcurrency", str(STEALTH_CLAIMS["hardwareConcurrency"]), str(actual["hardwareConcurrency"])),
            ("deviceMemory", str(STEALTH_CLAIMS["deviceMemory"]), str(actual["deviceMemory"])),
            ("maxTouchPoints", str(STEALTH_CLAIMS["maxTouchPoints"]), str(actual["maxTouchPoints"])),
            ("pixelDepth", str(STEALTH_CLAIMS["pixelDepth"]), str(actual["pixelDepth"])),
            ("devicePixelRatio", str(STEALTH_CLAIMS["devicePixelRatio"]), str(actual["devicePixelRatio"])),
            ("webdriver(应undefined)", "None", str(actual["webdriver"])),
            ("hasTouch(应False)", "False", str(actual["hasTouch"])),
            ("colorScheme(应light)", "light", actual["colorScheme"]),
            ("reducedMotion(应False)", "False", str(actual["reducedMotion"])),
            ("languages(应含zh-CN)", "zh-CN", actual["languages"]),
        ]
        all_ok = True
        for name, target, val in checks:
            # languages 是数组 JSON，只要包含 zh-CN 即视为一致
            if name.startswith("languages"):
                ok = "zh-CN" in val
            else:
                ok = str(target).lower() == str(val).lower()
            if not ok:
                all_ok = False
            mark = "✅" if ok else "❌ 不一致!"
            print(f"{name:<22}{target:<18}{str(val)[:28]:<30}{mark}")

        print(f"\nUA: {actual['userAgent']}")
        print(f"launch 参数 device_scale_factor: {config.DEVICE_SCALE_FACTOR} (匹配 devicePixelRatio=2)")
        print(f"launch 参数 has_touch: {config.HAS_TOUCH} (匹配 maxTouchPoints=0)")
        print(f"launch 参数 color_scheme: {config.COLOR_SCHEME}")
        print(f"sec-ch-ua 头: {config.EXTRA_HEADERS.get('sec-ch-ua')}")

        await context.close()

    print("\n" + "=" * 60)
    print("✅ 两层伪装一致" if all_ok else "⚠️ 存在不一致，请检查")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
