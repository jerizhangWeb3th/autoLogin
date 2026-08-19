# 中国平台自动化运营项目（抖音 · 小红书 · 闲鱼）

三平台自动化运营统一项目。基于 **Patchright + 真 Chrome + stealth_core 匿名性核心**，
覆盖登录、发布、评论、选题全流程，登录与匿名性伪装解耦，各平台独立维护。

## 功能总览

| 平台 | 功能 | 命令 | 说明 |
|:-----|:-----|:-----|:-----|
| 抖音 | 登录 | `python main.py douyin` | 创作者中心扫码登录（含刷脸二次验证）|
| 抖音 | 图文发布 | `python douyin_note_publish_v1.py` | patchright + 真 Chrome 图文发布 |
| 小红书 | 登录 | `python main.py xiaohongshu` | 扫码登录 → 保存 cookie |
| 小红书 | 发布 | `python xiaohongshu_safe_publish.py` | 合规发布（AI 标识 + 原创声明 + 真人化节奏）|
| 小红书 | 评论 | `python xiaohongshu_safe_comment.py` | 合规评论（低频 + 真人化 + 内容过滤）|
| 小红书 | 推荐流 | `python xhs_fetch_feed.py` | 抓取推荐流（选题/评论参考）|
| 闲鱼 | 登录 | `python main.py goofish` | 扫码登录 → 人脸识别二次扫码 |
| 闲鱼 | 发布 | `python goofish_publish.py` | 发布商品（mtop 发布）|
| 闲鱼 | 每日发布 | `python goofish_daily_publish.py` | 按星期轮换主题 + 卡片生成 |
| 选题 | GitHub 抓取 | `python fetch_github_ai_projects.py` | 高 star AI 项目（小红书选题）|

## 项目结构

```
autoLogin/
├── main.py                      # CLI 统一入口（douyin / xiaohongshu / goofish）
├── stealth_core.py              # ★ 浏览器匿名性核心（70+ 检测点）
├── human_behavior.py            # ★ 真人行为模块（随机延迟/逐字输入，降风控）
├── config.py                    # 共享配置（路径 / Xvfb / 常量）
├── utils.py                     # 共享工具（日志脱敏 / 二维码 / cookie 处理）
│
├── xiaohongshu_login.py         # 小红书登录（状态机 + 二次认证）
├── xiaohongshu_safe_publish.py  # 小红书合规发布 v2
├── xiaohongshu_safe_comment.py  # 小红书合规评论 v1
├── xhs_fetch_feed.py            # 小红书推荐流抓取
│
├── douyin_login.py              # 抖音登录模块
├── douyin_note_publish_v1.py    # 抖音图文发布
│
├── goofish_login.py             # 闲鱼登录模块
├── goofish_publish.py           # 闲鱼发布模块
├── goofish_daily_publish.py     # 闲鱼每日自动发布
├── patch_goofish_cli.py         # goofish-cli 硬编码指纹补丁
│
├── fetch_github_ai_projects.py  # GitHub 高 star AI 项目抓取（选题）
├── tools/                       # 二维码/发码工具
│   ├── qr_tool.py               #   取最新二维码/截图
│   ├── qr_to_hd.py              #   二维码高清放大（2048×2048，防微信压缩模糊）
│   ├── send_qr_now.py           #   发送工具（md5 验证防发旧码）
│   └── send_latest.py           #   新鲜截图助手
├── assets/                      # 输出（截图/二维码）
├── cookies/                     # cookie 保存目录（gitignore）
├── qr/                          # 二维码运行时目录（gitignore）
└── requirements.txt             # 固定版本依赖
```

## 架构设计原则

1. **匿名性单独拎出** —— `stealth_core.py` 是浏览器匿名性唯一核心，
   匿名性不足时只改这一个文件；登录模块不混入伪装细节。
2. **真人行为单独拎出** —— `human_behavior.py` 是行为层反检测唯一核心，
   用随机性（不是固定 sleep）模拟真人操作节奏。
3. **登录流程解耦** —— 各平台登录是独立操作流程，互不影响、各自演进。
4. **合规优先** —— 发布/评论带 AI 标识、原创声明、低频控制、内容过滤、人工确认。
5. **统一入口** —— `main.py` 按平台参数分发到对应登录模块。
6. **跨平台** —— Windows / macOS / Linux 自动适配（Chrome 路径 / DISPLAY / 伪装策略）。

## 匿名性方案（stealth_core）

- **注入方式**：`goto(wait_until='commit')` 后立即 `page.evaluate(STEALTH)`，
  赶在页面脚本执行前完成伪装（绕过 patchright add_init_script bug + 抖音 CSP）。
- **检测覆盖**：webdriver / CDP 残留 / Chrome 对象 / Navigator / UA-CH / WebGL /
  Canvas / Audio / 权限 / 媒体 / Battery / 网络 / Performance 等 70+ 检测点。
- **验证**：第三方 bot.incolumitas.com 26/28（2 FAIL 为 WebWorker 独立线程不继承主线程伪装，可接受）。

## 两层登录模型（小红书）

小红书有**两层独立登录**，发布/评论需要两层都有效：

| 层 | 域名 | 登录方式 | 用途 |
|:---|:-----|:-----|:-----|
| ① 网页版 | www.xiaohongshu.com | 扫码 | 浏览/看内容（web_session）|
| ② 创作者中心 | creator.xiaohongshu.com | 短信/扫码 | 发布/评论（customerClientId）|

- 网页版登录：`python xiaohongshu_login.py`
- 创作者中心登录：访问 creator.xiaohongshu.com/login，点右上角二维码图标切换扫码
- 发布/评论需同时具备 `web_session` + `customerClientId`

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
- 频繁脚本访问会触发平台风控（web_session 失效、评论 -104 等），需冷却期恢复。
