# 中国平台登录大项目

统一管理**抖音 / 小红书 / 闲鱼**三平台扫码登录，浏览器匿名性单独解耦。

## 🏗️ 架构

```
china-platform-login/
├── stealth_core.py          # ★ 浏览器匿名性核心（独立优化点！）
├── main.py                  # 统一入口
├── douyin_login.py          # 抖音登录模块（独立流程）
├── xiaohongshu_login.py     # 小红书登录模块（独立流程）
├── goofish_login.py         # 闲鱼登录模块（独立流程）
├── verify_stealth.py        # 匿名性验证脚本
├── qr/                      # 二维码输出（自动清旧码）
├── cookies/                 # cookie 输出
└── login_state.txt          # 登录状态标记
```

## 🎯 设计原则

1. **浏览器匿名性单独拎出** → `stealth_core.py`
   - 合并三平台最全方案：小红书 MAC 伪装 + 闲鱼持久化策略 + 抖音/闲鱼 60+ 检测点
   - **匿名性不足时只优化这一个文件**，登录流程完全不受影响
2. **登录模块各自独立** → 每个平台是一个操作流程，互不影响
3. **跨平台** → Windows / macOS / Linux 自动适配 Chrome 路径 / Xvfb / cookie 目录

## 📦 安装

```bash
pip install patchright
patchright install chrome   # 或安装 Google Chrome
```

## 🚀 用法

```bash
# 统一入口
python main.py douyin
python main.py xiaohongshu
python main.py goofish

# 或直接运行各模块
python douyin_login.py
python xiaohongshu_login.py
python goofish_login.py

# 验证匿名性
python verify_stealth.py
```

## 🔒 匿名性覆盖（stealth_core.py · 70+ 检测点）

| 层 | 检测点 |
|:--:|--------|
| 1 | webdriver 标志 |
| 2 | CDP 残留变量清除 + getAttribute 拦截 |
| 3 | Chrome 对象完整模拟（app/runtime/csi/loadTimes） |
| 4 | Navigator（UA/languages/plugins/mimeTypes/硬件） |
| 4d | **UA-data 完整伪装**（小红书方案：macOS/Chromium 150） |
| 5 | 屏幕窗口（Mac Retina 1440x900@2x） |
| 6 | WebGL + WebGL2（20+ 参数 + readPixels 噪声） |
| 7 | Canvas 指纹标准化 |
| 8 | AudioContext 指纹 |
| 9 | 权限系统 |
| 10 | 媒体设备 |
| 11 | MediaCodecs |
| 12 | 地理位置 |
| 13 | Battery API |
| 14 | 网络连接 |
| 15 | Performance 内存 |
| 16 | SpeechSynthesis |
| 17 | WebRTC |
| 18 | CSS 媒体查询 |
| 19 | iframe.contentWindow |

## ⚠️ 已知坑

- **add_init_script 在部分环境失效** → 导航后必须 `page.evaluate(STEALTH_SCRIPT)` 重新注入
- **抖音二维码有效期短** → 每 30s hash 变化，200s 整页 reload 刷新
- **扫码后不 reload** → 避免打断登录确认流程
- **登录判定**：抖音=URL 含 creator-micro 或「退出」按钮；闲鱼=cookie unb+tracknick；小红书=登录模态框消失

## 📁 Cookie 输出

| 平台 | 文件 |
|:---|:---|
| 抖音 | `cookies/douyin_douyin_main.json` |
| 小红书 | `cookies/xiaohongshu_hermes.json` |
| 闲鱼 | `cookies/goofish_cookies.json` |

cookie 是 Playwright `storage_state` 格式，可直接用于 sau/dy-mcp 等上传工具。
