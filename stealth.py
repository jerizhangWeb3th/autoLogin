"""环境自洽指纹伪装 — 只隐藏自动化痕迹，不伪造系统特征。

设计原则（v6 — 修复硬编码矛盾信号）:
  之前版本硬编码 macOS/Retina/Chrome126 指纹，但实际环境是 Linux+Xvfb。
  UA-CH、系统字体、GPU(WebGL/llvmpipe)、WebGPU、TLS 指纹全部暴露真实 Linux，
  与伪造的 MacIntel 交叉比对立刻识破 — 这种伪装反而有害。

  正确做法：
    1. 不伪造 platform/UA/screen/DPR — 由真 Chrome 原生产生（Linux 自洽）
    2. 只隐藏「自动化痕迹」— webdriver 标志、CDP 变量、原生函数 toString
    3. 保留真实 GPU/字体/WebGL — 与 UA-CH 一致（都是真实 Linux Chrome）
    4. Patchright 已处理 webdriver / --disable-blink-features 等，本脚本为兜底

  启用方式：config.STEALTH_ENABLED=True（默认 False，真 Chrome+patchright 已足够）
"""

STEALTH_SCRIPT = r"""
(function() {
  'use strict';

  // =============================================================
  // 1. webdriver 标志（Patchright 已处理，兜底）
  // =============================================================
  try {
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
  } catch(e) {}

  // =============================================================
  // 2. CDP 自动化变量清除（$cdc_ / $chrome_）
  // =============================================================
  try {
    [document, window].forEach(obj => {
      Object.keys(Object.getOwnPropertyDescriptors(obj))
        .filter(k => /^$cdc_|^$chrome_/.test(k))
        .forEach(k => Object.defineProperty(obj, k, { get: () => undefined, configurable: true }));
    });
  } catch(e) {}

  // =============================================================
  // 3. 自动化残留全局变量清除
  // =============================================================
  try {
    [
      '__webdriver_evaluate', '__selenium_evaluate', '__lastWatirAlert',
      '__webdriver_script_fn', '__driver_evaluate', '__webdriver_script_func',
      '__fxdriver_evaluate', '__driver_unwrapped', '__webdriver_unwrapped',
      '__webdriver_wrapper', 'callSelenium', '_selenium', 'calledSelenium',
      'domAutomation', 'domAutomationController',
    ].forEach(key => { try { delete window[key]; } catch(e) {} });
  } catch(e) {}

  // =============================================================
  // 4. getAttribute/hasAttribute 隐藏 webdriver 属性（兜底）
  // =============================================================
  try {
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
    // 保留原生 toString 外观（函数被替换后 toString 会暴露）
    const nativeStr = 'function () { [native code] }';
    [Element.prototype.getAttribute, Element.prototype.hasAttribute].forEach(fn => {
      fn.toString = function() { return nativeStr; };
    });
  } catch(e) {}

  // =============================================================
  // 5. Chrome 对象 — 只在缺失时补充（真 Chrome 原生已有）
  // =============================================================
  try {
    if (!window.chrome) {
      Object.defineProperty(window, 'chrome', { writable: true, enumerable: true, configurable: false, value: {} });
    }
    // 注意：真 Chrome 的 chrome.csi / chrome.loadTimes 原生存在，不覆盖
  } catch(e) {}

  // =============================================================
  // 6. iframe.contentWindow webdriver 兜底
  // =============================================================
  try {
    const desc = Object.getOwnPropertyDescriptor(HTMLIFrameElement.prototype, 'contentWindow');
    if (desc && desc.get) {
      const orig = desc.get;
      Object.defineProperty(HTMLIFrameElement.prototype, 'contentWindow', {
        get: function() {
          const win = orig.call(this);
          if (win && win.navigator) {
            Object.defineProperty(win.navigator, 'webdriver', { get: function() { return undefined; } });
          }
          return win;
        }
      });
    }
  } catch(e) {}

  // =============================================================
  // 完成 — 不再伪造 platform/UA/screen/DPR/WebGL/Canvas/Audio
  // 这些由真 Chrome 在 Linux 环境原生产生，天然自洽
  // =============================================================
  console.log('[Stealth] ✓ 自动化痕迹已隐藏（指纹保持真实 Chrome 原生值）');
})();
"""
