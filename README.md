# 中国平台登录项目（抖音 · 小红书 · 闲鱼）

三平台扫码登录统一项目。基于 **Patchright + 真 Chrome + stealth_core 匿名性核心**，
登录流程与匿名性伪装解耦，各平台独立维护。

## 功能

| 平台 | 命令 | 说明 |
|:-----|:-----|:-----|
| 抖音 | `python main.py douyin` | 创作者中心扫码登录（含刷脸二次验证） |
| 小红书 | `python main.py xiaohongshu` | 扫码登录 → 保存 cookie |
| 闲鱼 | `python main.py goofish` | 扫码登录 → 人脸识别二次扫码 → 保存 cookie |
| 闲鱼发布 | `python goofish_publish.py` | 发布商品（登录态检查 → 上传图片 → mtop 发布） |

## 项目结构

```
autoLogin/
├── main.py               # CLI 统一入口（douyin / xiaohongshu / goofish）
├── stealth_core.py       # ★ 浏览器匿名性核心（独立优化点，70+ 检测点）
├── douyin_login.py       # 抖音登录模块
├── xiaohongshu_login.py  # 小红书登录模块
├── goofish_login.py      # 闲鱼登录模块
├── goofish_publish.py    # 闲鱼发布模块
├── patch_goofish_cli.py  # goofish-cli 硬编码指纹补丁（一键应用）
├── config.py             # 共享配置（路径 / Xvfb / 常量）
├── utils.py              # 共享工具（日志脱敏 / 二维码 / cookie 处理）
├── verify_stealth.py     # 匿名性验证（6 项自检）
├── test_stealth_full.py  # 匿名性完整测试（39 项）
├── tools/                # 二维码/发码工具
│   ├── qr_tool.py        #   取最新二维码/截图
│   ├── qr_to_hd.py       #   二维码高清放大（2048×2048，防微信压缩模糊）
│   ├── send_qr_now.py    #   发送工具（md5 验证防发旧码）
│   └── send_latest.py    #   新鲜截图助手
├── assets/               # 输出（截图/二维码）
├── cookies/              # cookie 保存目录（gitignore）
├── qr/                   # 二维码运行时目录（gitignore）
└── requirements.txt      # 固定版本依赖
```

## 架构设计原则

1. **匿名性单独拎出** —— `stealth_core.py` 是浏览器匿名性唯一核心，
   匿名性不足时只改这一个文件；登录模块不混入伪装细节。
2. **登录流程解耦** —— 各平台登录是独立操作流程，互不影响、各自演进。
3. **统一入口** —— `main.py` 按平台参数分发到对应登录模块。
4. **跨平台** —— Windows / macOS / Linux 自动适配（Chrome 路径 / DISPLAY / 伪装策略）。

## 匿名性方案（stealth_core）

- **注入方式**：`goto(wait_until='commit')` 后立即 `page.evaluate(STEALTH)`，
  赶在页面脚本执行前完成伪装（绕过 patchright add_init_script bug + 抖音 CSP）。
- **检测覆盖**：webdriver / CDP 残留 / Chrome 对象 / Navigator / UA-CH / WebGL /
  Canvas / Audio / 权限 / 媒体 / Battery / 网络 / Performance 等 70+ 检测点。
- **验证**：本地 `test_stealth_full.py` 39/39 通过；第三方 bot.incolumitas.com 26/28。

## 抖音登录要点

- 二维码按时间序列命名（`YYYYMMDD_HHMMSS`），每 30s 检测刷新。
- **扫码确认期间绝不自动 reload 页面**（否则二维码换新 → 手机确认的旧码作废）。
- 发送二维码用 `tools/qr_to_hd.py` 放大到 2048×2048（微信压缩后仍可扫）。
- 发送前用 `tools/send_qr_now.py` 验证 md5（源 == 发送），防发旧码。

## 安装

```bash
pip install -r requirements.txt
# patchright 浏览器（真 Chrome 走系统，无需额外安装）
```

## 注意事项

- 每个平台/账号使用独立且长期稳定的 Profile，不要每次随机。
- 版本固定（`requirements.txt` 用 `==`），人工控制升级。
- 闲鱼发布依赖 goofish-cli（`patch_goofish_cli.py` 修复其硬编码指纹）。
