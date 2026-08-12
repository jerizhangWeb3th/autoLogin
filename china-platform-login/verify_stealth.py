#!/usr/bin/env python3
"""
匿名性验证脚本 — 检查 stealth_core 在真实 Chrome 中的生效情况

用法: python verify_stealth.py
"""
import asyncio
import json
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(BASE_DIR))

# patchright（sau 安装目录）
_sau = str(Path.home() / ".local/share/uv/tools/social-auto-upload/lib/python3.11/site-packages")
if _sau not in sys.path:
    sys.path.insert(0, _sau)

from stealth_core import MAC_UA, LAUNCH_ARGS, STEALTH_SCRIPT, find_chrome, ensure_display  # noqa: E402

CHECK_JS = """() => {
    const out = {};
    out.webdriver = String(navigator.webdriver);
    out.platform = navigator.platform;
    out.userAgent = navigator.userAgent.slice(0, 60);
    out.languages = JSON.stringify(navigator.languages);
    out.hardwareConcurrency = navigator.hardwareConcurrency;
    out.deviceMemory = navigator.deviceMemory;
    out.maxTouchPoints = navigator.maxTouchPoints;
    out.pluginsLen = navigator.plugins.length;
    out.chromeApp = !!(window.chrome && window.chrome.app);
    out.chromeRuntime = !!(window.chrome && window.chrome.runtime);
    out.screenW = screen.width;
    out.screenH = screen.height;
    out.dpr = window.devicePixelRatio;
    out.uaDataPlatform = (navigator.userAgentData || {}).platform;
    out.uaDataBrands = JSON.stringify((navigator.userAgentData || {}).brands);
    try {
        const c = document.createElement('canvas');
        const gl = c.getContext('webgl');
        out.webglVendor = gl ? gl.getParameter(gl.VENDOR) : null;
        out.webglRenderer = gl ? gl.getParameter(gl.RENDERER) : null;
    } catch(e) { out.webgl = 'ERR'; }
    const cdp = Object.keys(window).filter(k => k.startsWith('$cdc_') || k.startsWith('$chrome_'));
    out.cdpVars = cdp.length;
    return out;
}"""


async def main():
    ensure_display()
    chrome = find_chrome()
    print(f"Chrome: {chrome or '未找到(用内置)'}")

    from patchright.async_api import async_playwright

    async with async_playwright() as pw:
        launch_kwargs = dict(headless=False, args=LAUNCH_ARGS)
        if chrome:
            launch_kwargs["executable_path"] = chrome

        browser = await pw.chromium.launch(**launch_kwargs)
        context = await browser.new_context(
            viewport={"width": 1440, "height": 900}, locale="zh-CN",
            timezone_id="Asia/Shanghai", device_scale_factor=2,
            user_agent=MAC_UA,
        )
        page = await context.new_page()
        # 模拟真实登录流程：goto → evaluate stealth
        await page.goto("https://creator.douyin.com/", wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(4)
        await page.evaluate(STEALTH_SCRIPT)
        await asyncio.sleep(2)

        result = await page.evaluate(CHECK_JS)
        print(json.dumps(result, indent=2, ensure_ascii=False))

        # 判定
        passed = 0
        total = 0
        for k, expect in [
            ("platform", "MacIntel"),
            ("chromeApp", True),
            ("chromeRuntime", True),
            ("uaDataPlatform", "macOS"),
            ("webdriver", "false"),
            ("cdpVars", 0),
        ]:
            total += 1
            v = result.get(k)
            ok = (v == expect)
            if ok:
                passed += 1
            print(f"  {'✅' if ok else '❌'} {k} = {v} (期望 {expect})")
        print(f"\n结果: {passed}/{total} 通过")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
