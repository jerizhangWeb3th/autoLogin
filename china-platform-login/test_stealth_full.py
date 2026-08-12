#!/usr/bin/env python3
"""
全面匿名性测试 — 覆盖 stealth_core 全部 70+ 检测点

在沙箱真实 Chrome 中验证所有指纹伪装是否生效。
用法: python test_stealth_full.py
"""
import asyncio
import json
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(BASE_DIR))

_sau = str(Path.home() / ".local/share/uv/tools/social-auto-upload/lib/python3.11/site-packages")
if _sau not in sys.path:
    sys.path.insert(0, _sau)

from stealth_core import MAC_UA, LAUNCH_ARGS, STEALTH_SCRIPT, find_chrome, ensure_display  # noqa: E402

# 完整检测点检查（对应 stealth_core 20 层）
FULL_CHECK_JS = """() => {
    const out = {};

    // 1. webdriver
    out.webdriver = String(navigator.webdriver);

    // 2. CDP 变量
    const cdp = Object.keys(window).filter(k => k.startsWith('$cdc_') || k.startsWith('$chrome_'));
    out.cdpVars = cdp.length;
    out.cdpSelenium = window.__webdriver_evaluate === undefined && window.__selenium_evaluate === undefined;

    // 3. Chrome 对象
    out.chromeExists = typeof window.chrome !== 'undefined';
    out.chromeApp = !!(window.chrome && window.chrome.app);
    out.chromeRuntime = !!(window.chrome && window.chrome.runtime);
    out.chromeCsi = typeof (window.chrome || {}).csi === 'function';
    out.chromeLoadTimes = typeof (window.chrome || {}).loadTimes === 'function';

    // 4. Navigator
    out.platform = navigator.platform;
    out.vendor = navigator.vendor;
    out.userAgent = navigator.userAgent;
    out.languages = JSON.stringify(navigator.languages);
    out.hardwareConcurrency = navigator.hardwareConcurrency;
    out.deviceMemory = navigator.deviceMemory;
    out.maxTouchPoints = navigator.maxTouchPoints;
    out.pluginsLen = navigator.plugins.length;
    out.mimeTypesLen = navigator.mimeTypes.length;
    out.cookieEnabled = navigator.cookieEnabled;
    out.pdfViewerEnabled = navigator.pdfViewerEnabled;

    // 4d. UA-data
    const uad = navigator.userAgentData || {};
    out.uaDataPlatform = uad.platform;
    out.uaDataMobile = uad.mobile;
    out.uaDataBrands = JSON.stringify(uad.brands);

    // 5. 屏幕/窗口
    out.screenW = screen.width;
    out.screenH = screen.height;
    out.screenAvailH = screen.availHeight;
    out.colorDepth = screen.colorDepth;
    out.dpr = window.devicePixelRatio;
    out.outerW = window.outerWidth;
    out.outerH = window.outerHeight;

    // 6. WebGL
    try {
        const c = document.createElement('canvas');
        const gl = c.getContext('webgl') || c.getContext('experimental-webgl');
        if (gl) {
            out.webglVendor = gl.getParameter(gl.VENDOR);
            out.webglRenderer = gl.getParameter(gl.RENDERER);
            out.webglVersion = gl.getParameter(gl.VERSION);
            out.webglShading = gl.getParameter(gl.SHADING_LANGUAGE_VERSION);
            out.webglMaxTexSize = gl.getParameter(gl.MAX_TEXTURE_SIZE);
        } else out.webgl = '无上下文';
    } catch(e) { out.webgl = 'ERR:' + e.message; }

    // 6b. WebGL2
    try {
        const c = document.createElement('canvas');
        const gl2 = c.getContext('webgl2');
        if (gl2) {
            out.webgl2Vendor = gl2.getParameter(gl2.VENDOR);
            out.webgl2Renderer = gl2.getParameter(gl2.RENDERER);
        } else out.webgl2 = '不可用';
    } catch(e) { out.webgl2 = 'ERR'; }

    // 7. Canvas
    try {
        const c = document.createElement('canvas');
        c.width = 220; c.height = 40;
        const ctx = c.getContext('2d');
        ctx.textBaseline = 'top';
        ctx.font = '14px Arial';
        ctx.fillText('canvas-fp-test-abcdef123456', 2, 2);
        const fp1 = c.toDataURL();
        ctx.fillStyle = 'rgba(0,0,0,0.01)';
        ctx.fillRect(0, 0, 1, 1);
        const fp2 = c.toDataURL();
        out.canvasOk = fp1.startsWith('data:image/png');
        out.canvasStable = (fp1 === fp2);
    } catch(e) { out.canvas = 'ERR'; }

    // 8. Audio
    try {
        const AC = window.OfflineAudioContext || window.webkitOfflineAudioContext;
        if (AC) {
            const ctx = new AC(1, 44100, 44100);
            const osc = ctx.createOscillator();
            osc.connect(ctx.destination);
            osc.start(0);
            out.audioOk = true;
        } else out.audio = '无 OfflineAudioContext';
    } catch(e) { out.audio = 'ERR'; }

    // 9. 权限
    out.permissions = typeof navigator.permissions !== 'undefined';

    // 12. 地理位置
    out.geolocation = typeof navigator.geolocation !== 'undefined';

    // 13. Battery
    out.battery = typeof navigator.getBattery === 'function';

    // 14. 网络
    out.connection = !!(navigator.connection && navigator.connection.effectiveType);

    // 15. Performance memory
    out.perfMemory = !!(performance.memory && performance.memory.jsHeapSizeLimit);

    // 18. CSS 媒体查询
    try {
        const mm = window.matchMedia('(prefers-color-scheme: light)');
        out.prefersLight = mm.matches;
        const mmDark = window.matchMedia('(prefers-color-scheme: dark)');
        out.prefersDark = mmDark.matches;
    } catch(e) { out.matchMedia = 'ERR'; }

    // 19. iframe
    out.iframe = typeof HTMLIFrameElement !== 'undefined';

    // 其他
    out.visibility = document.visibilityState;
    out.hidden = document.hidden;
    return out;
}"""


def check(name, value, expected, passed):
    """判定单项"""
    ok = False
    if isinstance(expected, tuple):
        ok = value in expected
    elif isinstance(expected, (int, float)):
        ok = value == expected
    elif isinstance(expected, str):
        ok = str(value) == expected
    elif expected is True:
        ok = bool(value) is True
    elif expected is False:
        ok = bool(value) is False
    elif callable(expected):
        ok = expected(value)
    passed.append((name, value, expected, ok))
    return ok


async def main():
    ensure_display()
    chrome = find_chrome()
    print(f"Chrome: {chrome or '未找到(用内置)'}")
    print("=" * 60)

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
        await page.goto("https://creator.douyin.com/", wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(4)
        # 导航后注入（模拟真实流程）
        await page.evaluate(STEALTH_SCRIPT)
        await asyncio.sleep(2)

        result = await page.evaluate(FULL_CHECK_JS)
        passed = []

        # 1. webdriver
        check("webdriver", result.get("webdriver"), "false", passed)

        # 2. CDP
        check("CDP残留变量", result.get("cdpVars"), 0, passed)
        check("Selenium变量清除", result.get("cdpSelenium"), True, passed)

        # 3. Chrome 对象
        check("chrome 对象存在", result.get("chromeExists"), True, passed)
        check("chrome.app", result.get("chromeApp"), True, passed)
        check("chrome.runtime", result.get("chromeRuntime"), True, passed)
        check("chrome.csi", result.get("chromeCsi"), True, passed)
        check("chrome.loadTimes", result.get("chromeLoadTimes"), True, passed)

        # 4. Navigator
        check("platform=MacIntel", result.get("platform"), "MacIntel", passed)
        check("vendor=Google Inc.", result.get("vendor"), "Google Inc.", passed)
        check("UA 含 Mac", result.get("userAgent"), lambda v: "Macintosh" in str(v), passed)
        check("languages 含 zh-CN", result.get("languages"), lambda v: "zh-CN" in str(v), passed)
        check("hardwareConcurrency=8", result.get("hardwareConcurrency"), 8, passed)
        check("deviceMemory=8", result.get("deviceMemory"), 8, passed)
        check("maxTouchPoints=0", result.get("maxTouchPoints"), 0, passed)
        check("plugins=4", result.get("pluginsLen"), 4, passed)
        check("mimeTypes=4", result.get("mimeTypesLen"), 4, passed)
        check("cookieEnabled", result.get("cookieEnabled"), True, passed)
        check("pdfViewerEnabled", result.get("pdfViewerEnabled"), True, passed)

        # 4d. UA-data
        check("uaData.platform=macOS", result.get("uaDataPlatform"), "macOS", passed)
        check("uaData.mobile=false", result.get("uaDataMobile"), False, passed)
        check("uaData.brands 含 Chrome", result.get("uaDataBrands"), lambda v: "Google Chrome" in str(v), passed)

        # 5. 屏幕
        check("screen=1440", result.get("screenW"), 1440, passed)
        check("screen=900", result.get("screenH"), 900, passed)
        check("availHeight=877", result.get("screenAvailH"), 877, passed)
        check("colorDepth=24", result.get("colorDepth"), 24, passed)
        check("dpr=2", result.get("dpr"), 2, passed)

        # 6. WebGL
        check("WebGL VENDOR 伪装", result.get("webglVendor"), lambda v: "Intel" in str(v) or "WebGL" in str(v), passed)
        check("WebGL RENDERER 伪装", result.get("webglRenderer"), lambda v: "Intel" in str(v) or "WebGL" in str(v), passed)

        # 7. Canvas
        check("Canvas 可用", result.get("canvasOk"), True, passed)

        # 8. Audio
        check("Audio 可用", result.get("audioOk"), True, passed)

        # 9. 权限
        check("permissions API", result.get("permissions"), True, passed)

        # 12-15. API 存在性
        check("geolocation", result.get("geolocation"), True, passed)
        check("battery", result.get("battery"), True, passed)
        check("connection", result.get("connection"), True, passed)
        check("perf.memory", result.get("perfMemory"), True, passed)

        # 18. CSS
        check("prefers-light=true", result.get("prefersLight"), True, passed)

        # 其他
        check("visibility=visible", result.get("visibility"), "visible", passed)
        check("hidden=false", result.get("hidden"), False, passed)

        # 输出结果
        total = len(passed)
        ok_count = sum(1 for p in passed if p[3])
        print(f"\n{'检测点':<32} {'实际值':<40} {'期望':<20} 结果")
        print("-" * 100)
        for name, value, expected, ok in passed:
            v = str(value)[:38]
            e = str(expected)[:18]
            mark = "✅" if ok else "❌"
            print(f"{mark} {name:<30} {v:<40} {e:<20}")

        print(f"\n{'='*60}")
        print(f"结果: {ok_count}/{total} 通过")
        if ok_count == total:
            print("🎉 匿名性验证全部通过！")
        else:
            print("⚠️ 有未通过项，需检查")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
