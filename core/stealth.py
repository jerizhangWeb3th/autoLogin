#!/usr/bin/env python3
"""
浏览器匿名性核心模块 — 合并小红书 + 闲鱼 + 抖音三平台最全方案

【设计原则】
- 本模块是"浏览器匿名性"的唯一优化点。匿名性不足时只改这里，不动登录流程。
- 合并三平台方案取最全：
  1. 小红书：MAC_UA (macOS Chrome 150) + UA-data 完整伪装 + WebGL Apple 指纹
  2. 闲鱼：真 Chrome + 持久化 Profile + no_viewport（信任真实指纹累积）
  3. 抖音/闲鱼 stealth：goofish 60+ 检测点（webdriver/CDP/Chrome对象/Navigator/
     WebGL/Canvas/Audio/权限/媒体/Battery/网络/Performance/WebRTC/CSS媒体查询）
- 跨平台：Windows / macOS / Linux 自动适配

【用法】
    import stealth_core as sc
    context = await pw.chromium.launch_persistent_context(
        user_data_dir=profile_dir, **sc.launch_kwargs())
    await sc.inject_stealth(context)   # 注入 stealth
    # 导航后（必须！）：
    await sc.inject_stealth(page)      # page.evaluate 手动注入（add_init_script 在部分环境失效）
"""

import os
import sys
import platform

# ============================================================
# 平台检测
# ============================================================
IS_WINDOWS = sys.platform == "win32"
IS_MACOS = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")


def find_chrome() -> str:
    """跨平台查找 Chrome 可执行文件路径"""
    candidates = []
    if IS_WINDOWS:
        candidates = [
            os.environ.get("LOCALAPPDATA", "") + r"\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.environ.get("PROGRAMFILES", "") + r"\Google\Chrome\Application\chrome.exe",
            os.environ.get("PROGRAMFILES(X86)", "") + r"\Google\Chrome\Application\chrome.exe",
        ]
    elif IS_MACOS:
        candidates = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            os.path.expanduser("~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
        ]
    else:
        candidates = [
            "/usr/bin/google-chrome",
            "/usr/bin/google-chrome-stable",
            "/usr/bin/chromium",
            "/usr/bin/chromium-browser",
            "/snap/bin/chromium",
        ]
    for c in candidates:
        if c and os.path.exists(c):
            return c
    return candidates[0] if candidates else ""


def ensure_display() -> None:
    """确保图形环境就绪（仅 Linux 无显示器环境需要 Xvfb）"""
    if not IS_LINUX:
        return
    import subprocess
    r = subprocess.run(["pgrep", "-f", "Xvfb :99"], capture_output=True, text=True)
    if r.returncode != 0:
        subprocess.Popen(["Xvfb", ":99", "-screen", "0", "1440x900x24"],
                         start_new_session=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        import time
        time.sleep(2)
    os.environ.setdefault("DISPLAY", ":99")


# ============================================================
# MAC 伪装（小红书方案）
# ============================================================
MAC_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"

LAUNCH_ARGS = [
    "--no-sandbox",
    "--disable-blink-features=AutomationControlled",
    "--use-gl=swiftshader",
    "--enable-unsafe-swiftshader",
    "--ignore-gpu-blocklist",
    "--lang=zh-CN",
]


def launch_kwargs(chrome: str = "", persistent: bool = True, profile_dir: str = "",
                  user_agent: str = MAC_UA, no_viewport: bool = False) -> dict:
    """统一的浏览器启动参数（跨平台）

    - persistent=True  → launch_persistent_context（闲鱼/小红书用，持久化 profile）
    - persistent=False → launch + new_context（抖音 v8-win 用）
    - no_viewport=True → 窗口尺寸真实（闲鱼策略）
    """
    kwargs = {
        "headless": False,
        "channel": "chrome",
        "args": LAUNCH_ARGS,
        "locale": "zh-CN",
        "timezone_id": "Asia/Shanghai",
    }
    if not no_viewport:
        kwargs["viewport"] = {"width": 1440, "height": 900}
    if user_agent:
        kwargs["user_agent"] = user_agent
    if IS_LINUX:
        ensure_display()
    if chrome:
        kwargs["executable_path"] = chrome
    return kwargs


# ============================================================
# 融合 stealth 脚本（goofish 60+ 检测点 + 小红书 UA-data）
# ============================================================
STEALTH_SCRIPT = r"""
(function() {
  'use strict';

  // =============================================================
  // 0. 辅助函数
  // =============================================================
  function patchFnToString(fn) {
    if (!fn || fn.name === '') return;
    fn.toString = function() { return 'function ' + (fn.name || '') + '() { [native code] }'; };
  }

  // =============================================================
  // 1. webdriver 标志（完全匹配真实 Chrome：data property false）
  // =============================================================
  try {
    Object.defineProperty(navigator, 'webdriver', {
      value: false, writable: true, enumerable: true, configurable: true,
    });
  } catch(e) {}

  // =============================================================
  // 2. 清除自动化残留变量
  // =============================================================
  (function() {
    try {
      [document, window].forEach(obj => {
        Object.keys(Object.getOwnPropertyDescriptors(obj))
          .filter(k => /^$cdc_|^$chrome_/.test(k))
          .forEach(k => Object.defineProperty(obj, k, { get: () => undefined, configurable: true }));
      });
    } catch(e) {}
    try {
      ['__webdriver_evaluate', '__selenium_evaluate', '__lastWatirAlert',
        '__webdriver_script_fn', '__driver_evaluate', '__webdriver_script_func',
        '__fxdriver_evaluate', '__driver_unwrapped', '__webdriver_unwrapped',
        '__webdriver_wrapper', 'callSelenium', '_selenium', 'calledSelenium',
        'domAutomation', 'domAutomationController',
      ].forEach(key => { try { delete window[key]; } catch(e) {} });
      // 清除 document 上的自动化属性（fpscanner 检测 window['document']['webdriver']）
      ['webdriver', '__webdriver_evaluate', '__selenium_evaluate',
       '__webdriver_script_fn', '__driver_evaluate', 'domAutomation',
       '$cdc_asdjflasutopfhvcZLmcfl_', '$chrome_asyncScriptInfo',
      ].forEach(key => { try { delete document[key]; } catch(e) {} });
    } catch(e) {}
    const origGetAttr = Element.prototype.getAttribute;
    Element.prototype.getAttribute = function getAttribute(name) {
      if (name === 'webdriver' || name === 'cdp') return null;
      return origGetAttr.call(this, name);
    };
    const origHasAttr = Element.prototype.hasAttribute;
    Element.prototype.hasAttribute = function hasAttribute(name) {
      if (name === 'webdriver' || name === 'cdp') return false;
      return origHasAttr.call(this, name);
    };
    patchFnToString(Element.prototype.getAttribute);
    patchFnToString(Element.prototype.hasAttribute);
  })();

  // =============================================================
  // 3. Chrome 对象完整模拟
  // =============================================================
  (function() {
    if (!window.chrome) {
      Object.defineProperty(window, 'chrome', { writable: true, enumerable: true, configurable: false, value: {} });
    }
    if (!window.chrome.app) {
      window.chrome.app = {
        isInstalled: false,
        InstallState: { DISABLED: 'disabled', INSTALLED: 'installed', NOT_INSTALLED: 'not_installed' },
        RunningState: { CANNOT_RUN: 'cannot_run', READY_TO_RUN: 'ready_to_run', RUNNING: 'running' },
        getDetails: () => null, getIsInstalled: () => false,
        getInstalled: () => ({}), getRunningState: () => 'cannot_run', getSelf: () => ({}),
      };
      patchFnToString(window.chrome.app.getDetails);
      patchFnToString(window.chrome.app.getIsInstalled);
    }
    if (!window.chrome.runtime && location.protocol.startsWith('https')) {
      window.chrome.runtime = {
        onConnect: { addListener: () => {} }, onMessage: { addListener: () => {} },
        onInstalled: { addListener: () => {} }, onStartup: { addListener: () => {} },
        onSuspend: { addListener: () => {} }, onConnectExternal: { addListener: () => {} },
        onSuspendCanceled: { addListener: () => {} }, onUpdateAvailable: { addListener: () => {} },
        get id() { return undefined; },
        connect: function() {
          try { throw new Error(); } catch(e) {}
          return { onMessage: { addListener: () => {} }, onDisconnect: { addListener: () => {} }, postMessage: () => {} };
        },
        sendMessage: function() {
          try { throw new Error(); } catch(e) {}
        },
        getManifest: () => ({ name: '', version: '', manifest_version: 2, description: '', icons: {}, permissions: [] }),
        getURL: (p) => 'chrome-extension://invalid/' + p,
      };
      patchFnToString(window.chrome.runtime.connect);
      patchFnToString(window.chrome.runtime.sendMessage);
      patchFnToString(window.chrome.runtime.getManifest);
    }
    if (!window.chrome.csi) {
      window.chrome.csi = function() {
        const t = window.performance && window.performance.timing;
        if (!t) return { onloadT: 0, startE: 0, pageT: 0, tran: 15 };
        return { onloadT: t.domContentLoadedEventEnd, startE: t.navigationStart, pageT: Date.now() - t.navigationStart, tran: 15 };
      };
      patchFnToString(window.chrome.csi);
    }
    if (!window.chrome.loadTimes) {
      window.chrome.loadTimes = function() {
        const perf = window.performance;
        const nt = (perf && perf.getEntriesByType && perf.getEntriesByType('navigation')[0]) || {};
        const timing = perf && perf.timing;
        return {
          requestTime: 0, startLoadTime: timing ? timing.navigationStart : 0,
          commitLoadTime: timing ? timing.domContentLoadedEventEnd : 0,
          finishDocumentLoadTime: timing ? timing.domComplete : 0,
          finishLoadTime: timing ? timing.loadEventEnd : 0,
          firstPaintTime: 0, firstPaintAfterLoadTime: 0,
          navigationType: nt.type || 'other',
          wasFetchedViaSpdy: false, wasNpnNegotiated: true,
          npnNegotiatedProtocol: nt.nextHopProtocol || 'h2',
          wasAlternateProtocolAvailable: false,
          connectionInfo: nt.nextHopProtocol || 'h2',
        };
      };
      patchFnToString(window.chrome.loadTimes);
    }
  })();

  // =============================================================
  // 4. Navigator 属性
  // =============================================================
  Object.defineProperties(navigator, {
    platform:            { get: () => 'MacIntel' },
    vendor:              { get: () => 'Google Inc.' },
    vendorSub:           { get: () => '' },
    product:             { get: () => 'Gecko' },
    productSub:          { get: () => '20030107' },
    appName:             { get: () => 'Netscape' },
    appCodeName:         { get: () => 'Mozilla' },
    appVersion:          { get: () => '5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36' },
    userAgent:           { get: () => 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36' },
    hardwareConcurrency: { get: () => 8 },
    deviceMemory:        { get: () => 8 },
    maxTouchPoints:      { get: () => 0 },
    cookieEnabled:       { get: () => true },
    onLine:              { get: () => true },
    pdfViewerEnabled:    { get: () => true },
    languages:           { get: () => Object.freeze(['zh-CN', 'zh', 'en']) },
    language:            { get: () => 'zh-CN' },
    doNotTrack:          { get: () => null },
    buildID:             { get: () => undefined },
    oscpu:               { get: () => undefined },
  });

  (function() {
    const make = (name, fn, desc) => ({ name, filename: fn, description: desc, length: 1, item: () => {}, namedItem: () => null, refresh: () => {} });
    const plugins = [
      make('Chrome PDF Plugin', 'internal-pdf-viewer', 'Portable Document Format'),
      make('Chrome PDF Viewer', 'mhjfbmdgcfjbbpaeojofohoefgiehjai', ''),
      make('Native Client', 'internal-nacl-plugin', ''),
      make('Widevine Content Decryption Module', 'widevinecdmadapter', 'Enables Widevine licenses'),
    ];
    plugins.item = (i) => plugins[i];
    plugins.namedItem = (n) => plugins.find(p => p.name === n) || null;
    plugins.refresh = () => {};
    Object.defineProperty(navigator, 'plugins', { get: () => plugins });
  })();

  (function() {
    const make = (t, s, d, p) => ({ type: t, suffixes: s, description: d, enabledPlugin: p });
    const mts = [
      make('application/pdf', 'pdf', 'Portable Document Format', navigator.plugins[0]),
      make('text/pdf', 'pdf', 'Portable Document Format', navigator.plugins[0]),
      make('application/x-nacl', '', 'Native Client Executable', navigator.plugins[2]),
      make('application/x-pnacl', '', 'Portable Native Client Executable', navigator.plugins[2]),
    ];
    mts.item = (i) => mts[i];
    mts.namedItem = (n) => mts.find(m => m.type === n) || null;
    Object.defineProperty(navigator, 'mimeTypes', { get: () => mts });
  })();

  try {
    ['bluetooth', 'usb', 'serial'].forEach(k => {
      if (navigator[k] !== undefined) Object.defineProperty(navigator, k, { get: () => undefined });
    });
  } catch(e) {}

  // =============================================================
  // 4d. UA-data 完整伪装（小红书方案）
  // =============================================================
  try {
    const uaData = {
      brands: [
        {brand: 'Chromium', version: '150'},
        {brand: 'Not(A:Brand', version: '24'},
        {brand: 'Google Chrome', version: '150'}
      ],
      mobile: false, platform: 'macOS', architecture: 'x86', bitness: '64',
      model: '', platformVersion: '10.15.7',
      fullVersionList: [
        {brand: 'Chromium', version: '150.0.7871.128'},
        {brand: 'Not(A:Brand', version: '24.0.0.0'},
        {brand: 'Google Chrome', version: '150.0.7871.128'}
      ],
      getHighEntropyValues: () => Promise.resolve({
        architecture: 'x86', bitness: '64', model: '',
        platform: 'macOS', platformVersion: '10.15.7',
        uaFullVersion: '150.0.7871.128',
        fullVersionList: [
          {brand: 'Chromium', version: '150.0.7871.128'},
          {brand: 'Not(A:Brand', version: '24.0.0.0'},
          {brand: 'Google Chrome', version: '150.0.7871.128'}
        ]
      }),
      toJSON: () => ({
        brands: [
          {brand: 'Chromium', version: '150'},
          {brand: 'Not(A:Brand', version: '24'},
          {brand: 'Google Chrome', version: '150'}
        ],
        mobile: false, platform: 'macOS'
      })
    };
    Object.defineProperty(navigator, 'userAgentData', { get: () => uaData, configurable: true });
  } catch(e) {}

  // =============================================================
  // 5. 屏幕 & 窗口 — Mac Retina
  // =============================================================
  Object.defineProperties(screen, {
    width:       { get: () => 1440 },
    height:      { get: () => 900 },
    availWidth:  { get: () => 1440 },
    availHeight: { get: () => 877 },
    colorDepth:  { get: () => 24 },
    pixelDepth:  { get: () => 24 },
    availLeft:   { get: () => 0 },
    availTop:    { get: () => 23 },
    orientation: { get: () => ({ type: 'landscape-primary', angle: 0, onchange: null }) },
  });

  Object.defineProperties(window, {
    outerWidth:      { get: () => 1440 },
    outerHeight:     { get: () => 985 },
    innerWidth:      { get: () => 1440 },
    innerHeight:     { get: () => 900 },
    devicePixelRatio:{ get: () => 2 },
    screenX:         { get: () => 0 },
    screenY:         { get: () => 23 },
    screenLeft:      { get: () => 0 },
    screenTop:       { get: () => 23 },
  });
  try {
    Object.defineProperties(document, {
      hidden:          { get: () => false },
      visibilityState: { get: () => 'visible' },
    });
  } catch(e) {}

  // =============================================================
  // 6. WebGL 全面伪装（含 WebGL2 + readPixels 噪声）
  // =============================================================
  (function() {
    try {
      const p1 = WebGLRenderingContext.prototype;
      const origP1 = p1.getParameter;
      p1.getParameter = function(p) {
        var m = {
          37445: 'Intel Inc.', 37446: 'Intel Iris OpenGL Engine',
          7936: 'WebGL 1.0 (OpenGL 2.0)', 7937: 'WebGL GLSL ES 1.0 (OpenGL ES GLSL ES 1.0)',
          35724: 'WebGL', 35725: 'WebGL',
          36348: 16, 36349: 256, 35660: 8, 35661: 64, 35662: 32, 35663: 16,
          35664: 16384, 35665: 16384, 35666: 32, 35667: 16384,
          34024: 1024, 34076: 0, 3386: 24, 3410: 8,
        };
        if (p in m) return m[p];
        return origP1.call(this, p);
      };
      patchFnToString(p1.getParameter);

      var origRP = p1.readPixels;
      p1.readPixels = function(x, y, w, h, fmt, type, pixels) {
        var r = origRP.call(this, x, y, w, h, fmt, type, pixels);
        if (pixels && pixels.length > 100) {
          pixels[0] = (pixels[0] & 0xFE) | (Math.random() > 0.5 ? 1 : 0);
        }
        return r;
      };
      patchFnToString(p1.readPixels);

      if (typeof WebGL2RenderingContext !== 'undefined') {
        var p2 = WebGL2RenderingContext.prototype;
        var origP2 = p2.getParameter;
        p2.getParameter = function(p) {
          if (p === 37445) return 'Intel Inc.';
          if (p === 37446) return 'Intel Iris OpenGL Engine';
          if (p === 7936) return 'WebGL 2.0 (OpenGL 4.1)';
          if (p === 7937) return 'WebGL GLSL ES 3.0 (OpenGL ES GLSL ES 3.0)';
          if (p === 35724 || p === 35725) return 'WebGL';
          return origP2.call(this, p);
        };
        patchFnToString(p2.getParameter);
      }
    } catch(e) {}
  })();

  // =============================================================
  // 7. Canvas 指纹
  // =============================================================
  (function() {
    try {
      var orig = HTMLCanvasElement.prototype.toDataURL;
      HTMLCanvasElement.prototype.toDataURL = function(type, quality) {
        if (this.width > 0 && this.height > 0) {
          var ctx = this.getContext('2d');
          if (ctx) { ctx.fillStyle = 'rgba(0,0,0,0.01)'; ctx.fillRect(0, 0, 1, 1); }
        }
        return orig.call(this, type, quality);
      };
      patchFnToString(HTMLCanvasElement.prototype.toDataURL);
    } catch(e) {}
  })();

  // =============================================================
  // 8. AudioContext 指纹
  // =============================================================
  (function() {
    try {
      if (typeof AudioBuffer !== 'undefined') {
        var orig = AudioBuffer.prototype.getChannelData;
        AudioBuffer.prototype.getChannelData = function(channel) {
          var data = orig.call(this, channel);
          if (data && data.length > 100) {
            for (var i = 0; i < data.length; i += 100) data[i] += 0.00001 * (i % 3 - 1);
          }
          return data;
        };
        patchFnToString(AudioBuffer.prototype.getChannelData);
      }
    } catch(e) {}
  })();

  // =============================================================
  // 9. 权限系统
  // =============================================================
  (function() {
    try {
      var orig = navigator.permissions.query.bind(navigator.permissions);
      navigator.permissions.query = async function(desc) {
        var name = desc.name;
        var prompt = ['camera','microphone','background-sync','clipboard-read','clipboard-write',
          'display-capture','midi','notifications','persistent-storage','push',
          'ambient-light-sensor','accelerometer','gyroscope','magnetometer'];
        if (prompt.includes(name)) {
          return Promise.resolve(Object.setPrototypeOf({ state: 'prompt', onchange: null }, PermissionStatus.prototype));
        }
        if (name === 'geolocation') {
          return Promise.resolve(Object.setPrototypeOf({ state: 'denied', onchange: null }, PermissionStatus.prototype));
        }
        return orig(desc);
      };
    } catch(e) {}
  })();

  // =============================================================
  // 10. 媒体设备
  // =============================================================
  (function() {
    try {
      if (navigator.mediaDevices) {
        navigator.mediaDevices.enumerateDevices = function() {
          return Promise.resolve([
            { deviceId: 'default', kind: 'audioinput', label: '', groupId: 'default' },
            { deviceId: 'default', kind: 'audiooutput', label: '', groupId: 'default' },
            { deviceId: 'default', kind: 'videoinput', label: '', groupId: 'default' },
          ]);
        };
      }
    } catch(e) {}
  })();

  // =============================================================
  // 11. MediaCodecs
  // =============================================================
  (function() {
    try {
      var orig = HTMLMediaElement.prototype.canPlayType;
      HTMLMediaElement.prototype.canPlayType = function(type) {
        var parts = type.trim().split(';');
        var mime = parts[0].trim();
        var codecs = parts.slice(1).join(';');
        if (mime === 'video/mp4' && codecs.includes('avc1.42E01E')) return 'probably';
        if (mime === 'audio/x-m4a' && !codecs) return 'maybe';
        if (mime === 'audio/aac' && !codecs) return 'probably';
        if (mime === 'audio/mp4' && !codecs) return 'maybe';
        return orig.call(this, type);
      };
      patchFnToString(HTMLMediaElement.prototype.canPlayType);
    } catch(e) {}
  })();

  // =============================================================
  // 12. 地理位置
  // =============================================================
  (function() {
    try {
      var xian = { latitude: 34.2611, longitude: 108.9421, accuracy: 100, altitude: null, altitudeAccuracy: null, heading: null, speed: null };
      navigator.geolocation.getCurrentPosition = function(s, e, o) { s({ coords: xian, timestamp: Date.now() }); };
    } catch(e) {}
  })();

  // =============================================================
  // 13. Battery
  // =============================================================
  (function() {
    try {
      navigator.getBattery = function() {
        return Promise.resolve({
          charging: true, chargingTime: 0, dischargingTime: Infinity, level: 1,
          onchargingchange: null, onchargingtimechange: null, ondischargingtimechange: null, onlevelchange: null,
        });
      };
    } catch(e) {}
  })();

  // =============================================================
  // 14. 网络连接
  // =============================================================
  try {
    Object.defineProperty(navigator, 'connection', {
      get: () => ({
        effectiveType: '4g', rtt: 50, downlink: 10, saveData: false,
        addEventListener: () => {}, removeEventListener: () => {},
      })
    });
  } catch(e) {}

  // =============================================================
  // 15. Performance 内存
  // =============================================================
  try {
    performance.memory = { jsHeapSizeLimit: 2172649472, totalJSHeapSize: 10000000, usedJSHeapSize: 8000000 };
  } catch(e) {}

  // =============================================================
  // 16. SpeechSynthesis
  // =============================================================
  (function() {
    try {
      if (window.speechSynthesis && window.speechSynthesis.getVoices) {
        var orig = window.speechSynthesis.getVoices;
        window.speechSynthesis.getVoices = function() {
          return [
            { name: 'Google US English', lang: 'en-US', voiceURI: 'Google US English', localService: true, default: true },
            { name: 'Google 普通话（中国大陆）', lang: 'zh-CN', voiceURI: 'Google 普通话（中国大陆）', localService: true, default: false },
          ];
        };
        patchFnToString(window.speechSynthesis.getVoices);
      }
    } catch(e) {}
  })();

  // =============================================================
  // 17. WebRTC
  // =============================================================
  (function() {
    try {
      if (typeof RTCPeerConnection !== 'undefined') {
        var orig = RTCPeerConnection.prototype.createDataChannel;
        RTCPeerConnection.prototype.createDataChannel = function(label, opts) {
          try { return orig.call(this, label, opts); } catch(e) {
            return { label: label, ordered: true, reliable: true, protocol: '', negotiated: false, id: 0, readyState: 'connecting', bufferedAmount: 0 };
          }
        };
        patchFnToString(RTCPeerConnection.prototype.createDataChannel);
      }
    } catch(e) {}
  })();

  // =============================================================
  // 18. CSS 媒体查询
  // =============================================================
  (function() {
    try {
      var orig = window.matchMedia;
      window.matchMedia = function(query) {
        var r = orig.call(this, query);
        if (query.includes('prefers-color-scheme')) {
          Object.defineProperty(r, 'matches', { get: function() { return query.includes('light'); } });
        }
        if (query.includes('prefers-reduced-motion')) {
          Object.defineProperty(r, 'matches', { get: function() { return false; } });
        }
        if (query.includes('any-pointer')) {
          Object.defineProperty(r, 'matches', { get: function() { return query.includes('fine'); } });
        }
        if (query.includes('any-hover')) {
          Object.defineProperty(r, 'matches', { get: function() { return true; } });
        }
        if (query.includes('-moz') && query.includes('mac')) {
          Object.defineProperty(r, 'matches', { get: function() { return false; } });
        }
        if (query.includes('color-gamut')) {
          Object.defineProperty(r, 'matches', { get: function() { return query.includes('srgb'); } });
        }
        if (query.includes('forced-colors')) {
          Object.defineProperty(r, 'matches', { get: function() { return query.includes('none'); } });
        }
        return r;
      };
      patchFnToString(window.matchMedia);
    } catch(e) {}
  })();

  // =============================================================
  // 19. iframe.contentWindow
  // =============================================================
  (function() {
    try {
      var desc = Object.getOwnPropertyDescriptor(HTMLIFrameElement.prototype, 'contentWindow');
      if (desc && desc.get) {
        var orig = desc.get;
        Object.defineProperty(HTMLIFrameElement.prototype, 'contentWindow', {
          get: function() {
            var win = orig.call(this);
            if (win && win.navigator) {
              Object.defineProperty(win.navigator, 'webdriver', { get: function() { return undefined; } });
            }
            return win;
          }
        });
      }
    } catch(e) {}
  })();

  console.log('[Stealth] ✓ 融合伪装加载完成 (70+ 检测点)');
})();
"""


async def inject_stealth(target):
    """注入 stealth。

    target 可以是 context（add_init_script）或 page（evaluate）。
    注意：
    - patchright 的 add_init_script 在此环境有 bug（route-based 注入失效）
    - 最可靠方式：goto(wait_until='commit') 后立即 page.evaluate
    """
    if hasattr(target, "add_init_script"):
        # context
        try:
            await target.add_init_script(STEALTH_SCRIPT)
        except Exception:
            pass
        return
    # page → evaluate 手动注入
    try:
        await target.evaluate(STEALTH_SCRIPT)
        return True
    except Exception as e:
        print(f"⚠️ stealth 注入失败: {str(e)[:80]}")
        return False


async def goto_with_stealth(page, url, timeout=60000):
    """导航并在页面脚本执行前注入 stealth（推荐方案）。

    原理：wait_until='commit' 时 document 刚创建，立即 evaluate 注入，
    早于页面自身的 JS 脚本（规避 add_init_script bug 和 CSP 限制）。
    """
    try:
        await page.goto(url, wait_until="commit", timeout=timeout)
        await page.evaluate(STEALTH_SCRIPT)
        try:
            await page.wait_for_load_state("domcontentloaded", timeout=timeout)
        except Exception:
            pass
        return True
    except Exception as e:
        print(f"⚠️ goto+stealth 失败: {str(e)[:80]}")
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=timeout)
            await page.evaluate(STEALTH_SCRIPT)
            return True
        except Exception as e2:
            print(f"⚠️ fallback 也失败: {str(e2)[:80]}")
            return False


def verify_stealth(page) -> dict:
    """验证 stealth 是否生效（返回指纹检测结果）"""
    return page.evaluate("""() => {
        const out = {};
        out.webdriver = String(navigator.webdriver);
        out.platform = navigator.platform;
        out.chromeApp = !!(window.chrome && window.chrome.app);
        out.uaDataPlatform = (navigator.userAgentData || {}).platform;
        out.pluginsLen = navigator.plugins.length;
        const cdp = Object.keys(window).filter(k => k.startsWith('$cdc_') || k.startsWith('$chrome_'));
        out.cdpVars = cdp.length;
        return out;
    }""")


def ensure_fonts() -> None:
    """把项目自包含中文字体安装到系统（字体指纹一致性）。

    闲鱼/小红书风控检测字体指纹：Linux 服务器缺中文字体（仅文泉驿正黑），
    与真实中国用户（宋体/楷体/黑体等）不符。把 assets/fonts 的字体装到
    ~/.fonts/ 并刷新 fontconfig，让 Chrome 报告更真实的中文字体列表。
    """
    if not IS_LINUX:
        return
    from pathlib import Path
    import shutil as _shutil
    import subprocess as _sp
    fonts_src = Path(__file__).resolve().parent.parent / "assets" / "fonts"
    if not fonts_src.exists():
        return
    target_dir = Path.home() / ".fonts"
    target_dir.mkdir(exist_ok=True)
    installed = 0
    for ttf in sorted(fonts_src.glob("*.ttf")):
        dst = target_dir / ttf.name
        if dst.exists():
            continue
        try:
            _shutil.copy2(ttf, dst)
            installed += 1
        except Exception as e:
            print(f"⚠️ 字体安装失败 {ttf.name}: {e}")
    if installed:
        _sp.run(["fc-cache", "-f"], capture_output=True)
        print(f"✅ 已安装 {installed} 个中文字体到 {target_dir}")
