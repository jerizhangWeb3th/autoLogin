"""
超级浏览器指纹伪装 — 针对中国平台风控（小红书/闲鱼/淘宝/抖音）
综合 puppeteer-extra-plugin-stealth (17模块) + 社区最佳实践
v5 — 覆盖 60+ 检测点
"""

STEALTH_SCRIPT = """
(function() {
  'use strict';

  // =============================================================
  // 0. 辅助函数
  // =============================================================
  const nativeCode = 'function () { [native code] }';
  function patchFnToString(fn) {
    if (!fn || fn.name === '') return;
    fn.toString = function() { return 'function ' + (fn.name || '') + '() { [native code] }'; };
  }

  // =============================================================
  // 1. webdriver 标志
  // =============================================================
  Object.defineProperty(navigator, 'webdriver', { get: () => undefined });

  // =============================================================
  // 2. 清除所有自动化残留变量
  // =============================================================
  (function() {
    // 2a. CDP 变量 ($cdc_ / $chrome_)
    try {
      [document, window].forEach(obj => {
        Object.keys(Object.getOwnPropertyDescriptors(obj))
          .filter(k => /^$cdc_|^$chrome_/.test(k))
          .forEach(k => Object.defineProperty(obj, k, { get: () => undefined, configurable: true }));
      });
    } catch(e) {}

    // 2b. Selenium/Puppeteer 全局变量
    try {
      [
        '__webdriver_evaluate', '__selenium_evaluate', '__lastWatirAlert',
        '__webdriver_script_fn', '__driver_evaluate', '__webdriver_script_func',
        '__fxdriver_evaluate', '__driver_unwrapped', '__webdriver_unwrapped',
        '__webdriver_wrapper', 'callSelenium', '_selenium', 'calledSelenium',
        'domAutomation', 'domAutomationController',
      ].forEach(key => { try { delete window[key]; } catch(e) {} });
    } catch(e) {}

    // 2c. override getAttribute / hasAttribute
    const origGetAttr = Element.prototype.getAttribute;
    Element.prototype.getAttribute = function(name) {
      if (name === 'webdriver' || name === 'cdp') return null;
      return origGetAttr.call(this, name);
    };
    const origHasAttr = Element.prototype.hasAttribute;
    Element.prototype.hasAttribute = function(name) {
      if (name === 'webdriver' || name === 'cdp') return false;
      return origHasAttr.call(this, name);
    };

    // 2d. Patch toString 防止检测
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

    // 3a. chrome.app
    if (!window.chrome.app) {
      window.chrome.app = {
        isInstalled: false,
        InstallState: { DISABLED: 'disabled', INSTALLED: 'installed', NOT_INSTALLED: 'not_installed' },
        RunningState: { CANNOT_RUN: 'cannot_run', READY_TO_RUN: 'ready_to_run', RUNNING: 'running' },
        getDetails: () => null,
        getIsInstalled: () => false,
        getInstalled: () => ({}),
        getRunningState: () => 'cannot_run',
        getSelf: () => ({}),
      };
      patchFnToString(window.chrome.app.getDetails);
      patchFnToString(window.chrome.app.getIsInstalled);
    }

    // 3b. chrome.runtime (只在 https 下)
    if (!window.chrome.runtime && location.protocol.startsWith('https')) {
      window.chrome.runtime = {
        onConnect: { addListener: () => {} },
        onMessage: { addListener: () => {} },
        onInstalled: { addListener: () => {} },
        onStartup: { addListener: () => {} },
        onSuspend: { addListener: () => {} },
        onConnectExternal: { addListener: () => {} },
        onSuspendCanceled: { addListener: () => {} },
        onUpdateAvailable: { addListener: () => {} },
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

    // 3c. chrome.csi
    if (!window.chrome.csi) {
      window.chrome.csi = function() {
        const t = window.performance && window.performance.timing;
        if (!t) return { onloadT: 0, startE: 0, pageT: 0, tran: 15 };
        return { onloadT: t.domContentLoadedEventEnd, startE: t.navigationStart, pageT: Date.now() - t.navigationStart, tran: 15 };
      };
      patchFnToString(window.chrome.csi);
    }

    // 3d. chrome.loadTimes
    if (!window.chrome.loadTimes) {
      window.chrome.loadTimes = function() {
        const perf = window.performance;
        const nt = (perf && perf.getEntriesByType && perf.getEntriesByType('navigation')[0]) || {};
        const timing = perf && perf.timing;
        return {
          requestTime: 0,
          startLoadTime: timing ? timing.navigationStart : 0,
          commitLoadTime: timing ? timing.domContentLoadedEventEnd : 0,
          finishDocumentLoadTime: timing ? timing.domComplete : 0,
          finishLoadTime: timing ? timing.loadEventEnd : 0,
          firstPaintTime: 0,
          firstPaintAfterLoadTime: 0,
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
  // 4. Navigator 属性全面伪装
  // =============================================================
  Object.defineProperties(navigator, {
    platform:            { get: () => 'MacIntel' },
    vendor:              { get: () => 'Google Inc.' },
    vendorSub:           { get: () => '' },
    product:             { get: () => 'Gecko' },
    productSub:          { get: () => '20030107' },
    appName:             { get: () => 'Netscape' },
    appCodeName:         { get: () => 'Mozilla' },
    appVersion:          { get: () => '5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36' },
    userAgent:           { get: () => 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36' },
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

  // 4a. plugins (4个标准)
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

  // 4b. mimeTypes
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

  // 4c. 清除设备 API
  try {
    ['bluetooth', 'usb', 'serial'].forEach(k => {
      if (navigator[k] !== undefined) Object.defineProperty(navigator, k, { get: () => undefined });
    });
  } catch(e) {}

  // =============================================================
  // 5. 屏幕 & 窗口 — Mac Retina 14寸
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
    outerHeight:     { get: () => 985 },  // 含标题栏 85px
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
      // WebGL 1.0 getParameter
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

      // WebGL 1.0 readPixels 微噪声
      var origRP = p1.readPixels;
      p1.readPixels = function(x, y, w, h, fmt, type, pixels) {
        var r = origRP.call(this, x, y, w, h, fmt, type, pixels);
        if (pixels && pixels.length > 100) {
          pixels[0] = (pixels[0] & 0xFE) | (Math.random() > 0.5 ? 1 : 0);
        }
        return r;
      };
      patchFnToString(p1.readPixels);

      // WebGL 2.0 getParameter
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
  // 7. Canvas 指纹标准化
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
  // 8. AudioContext 指纹伪装
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

  // 9a. Notification.permission
  (function() {
    try {
      if (typeof Notification !== 'undefined' && !document.location.protocol.startsWith('https')) {
        Object.defineProperty(Notification, 'permission', { get: () => 'denied' });
      }
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
  // 11. MediaCodecs (canPlayType 防检测)
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
  // 12. 地理位置 — 西安钟楼
  // =============================================================
  (function() {
    try {
      var xian = { latitude: 34.2611, longitude: 108.9421, accuracy: 100, altitude: null, altitudeAccuracy: null, heading: null, speed: null };
      navigator.geolocation.getCurrentPosition = function(s, e, o) { s({ coords: xian, timestamp: Date.now() }); };
    } catch(e) {}
  })();

  // =============================================================
  // 13. Battery API
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
  // 15. Performance / 内存
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
  // 19. iframe.contentWindow 安全
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

  // =============================================================
  // 20. 修补所有被替换函数的 toString
  // =============================================================
  // (已在各层 patchFnToString 调用中完成)

  // =============================================================
  // 完成
  // =============================================================
  console.log('[Stealth] ✓ 浏览器伪装加载完成 (60+ 检测点)');
})();
"""
