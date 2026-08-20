# 中国平台自动化运营项目（抖音 · 小红书 · 闲鱼）

三平台自动化运营统一项目。基于 **Patchright + 真 Chrome + stealth 匿名性核心 + human_behavior 真人行为**，
覆盖登录、发布、评论、选题全流程，分层架构，各平台独立演进。

## 功能总览

| 平台 | 功能 | 命令 | 说明 |
|:-----|:-----|:-----|:-----|
| 抖音 | 登录 | `python main.py douyin` | 创作者中心扫码登录（含刷脸二次验证）|
| 抖音 | 图文发布 | `python platforms/douyin/publish.py` | patchright + 真 Chrome 图文发布 |
| 小红书 | 登录 | `python main.py xiaohongshu` | 扫码登录 → 保存 cookie |
| 小红书 | 发布 | `python platforms/xiaohongshu/publish.py <图> --title ... --auto --ai-label` | 合规发布（AI 标识 + 原创声明 + 真人化节奏）|
| 小红书 | 评论 | `python platforms/xiaohongshu/comment.py <文件> --auto` | 合规评论（低频 + 真人化 + 内容过滤）|
| 小红书 | 推荐流 | `python platforms/xiaohongshu/feed.py` | 抓取推荐流（选题/评论参考）|
| 闲鱼 | 登录 | `python main.py goofish` | 扫码登录 → 人脸识别二次扫码 |
| 闲鱼 | 发布 | `python platforms/goofish/publish.py` | 发布商品（mtop 发布）|
| 闲鱼 | 每日发布 | `python platforms/goofish/daily_publish.py` | 按星期轮换主题 + 卡片生成 |
| 选题 | GitHub 抓取 | `python scripts/fetch_github_ai_projects.py` | 高 star AI 项目（小红书选题）|

## 项目结构（分层架构）

```
autoLogin/
├── main.py                      # CLI 统一入口（平台登录分发）
├── config.py                    # 全局配置（路径 / Xvfb / 常量）
├── utils.py                     # 通用工具（日志脱敏 / 二维码 / cookie 处理）
│
├── core/                        # 核心层（平台无关基础）
│   ├── stealth.py               # ★ 浏览器匿名性核心（70+ 检测点，唯一优化点）
│   └── human_behavior.py        # ★ 真人行为模块（随机延迟/逐字输入，降风控）
│
├── platforms/                   # 平台层（业务逻辑）
│   ├── xiaohongshu/
│   │   ├── login.py             # 登录（状态机 + 二次认证）
│   │   ├── publish.py           # 合规发布 v2
│   │   ├── comment.py           # 合规评论 v1（多 selector 兜底）
│   │   ├── feed.py              # 推荐流抓取
│   │   ├── cards.py             # 卡片生成（字号规范 + qiaomu 三风格）
│   │   ├── sign.py              # x-s/x-t 签名（API 直发，execjs + crypto-js）
│   │   ├── xhs_selectors.py     # selector 候选库（改版集中更新）
│   │   └── static/              # 签名 JS（xhs_creator/main/rap）
│   ├── douyin/
│   │   ├── login.py             # 登录模块
│   │   └── publish.py           # 图文发布
│   └── goofish/
│       ├── login.py             # 登录模块
│       ├── publish.py           # 发布模块
│       └── daily_publish.py     # 每日自动发布
│
├── scripts/                     # 独立脚本
│   ├── fetch_github_ai_projects.py  # GitHub 高 star AI 项目抓取
│   └── patch_goofish_cli.py         # goofish-cli 硬编码指纹补丁
│
├── tools/                       # 二维码/发码工具
│   ├── qr_tool.py / qr_to_hd.py / send_qr_now.py / send_latest.py
├── assets/                      # 输出（截图/二维码）
├── cookies/                     # cookie 保存目录（gitignore）
├── qr/                          # 二维码运行时目录（gitignore）
├── profile/                     # 持久化 Profile（gitignore）
└── requirements.txt             # 固定版本依赖
```

## 架构设计原则

1. **分层解耦** —— `core/`（匿名性 + 真人行为，平台无关）与 `platforms/`（各平台业务）分离，
   匿名性不足只改 `core/stealth.py`，行为风控只改 `core/human_behavior.py`。
2. **平台独立演进** —— 各平台是独立包，互不影响、各自维护。
3. **合规优先** —— 发布/评论带 AI 标识、原创声明、低频控制、内容过滤、人工确认。
4. **统一入口** —— `main.py` 按平台分发；各脚本也可直接运行。
5. **跨平台** —— Windows / macOS / Linux 自动适配（Chrome 路径 / DISPLAY / 伪装策略）。

## 匿名性方案（core/stealth）

- **注入方式**：`goto(wait_until='commit')` 后立即 `page.evaluate(STEALTH)`，
  赶在页面脚本执行前完成伪装（绕过 patchright add_init_script bug + 抖音 CSP）。
- **检测覆盖**：webdriver / CDP 残留 / Chrome 对象 / Navigator / UA-CH / WebGL /
  Canvas / Audio / 权限 / 媒体 / Battery / 网络 / Performance 等 70+ 检测点。

## 签名方案（platforms/xiaohongshu/sign）

合并自 creatorhub 的小红书 x-s/x-t 签名（execjs + Node + crypto-js），可 API 直发
（评论/发布/搜索），不依赖浏览器前端，改版时更新 `static/*.js` 即可。

- `generate_xs_xs_common(a1, api, data)` → x-s / x-t / x-s-common（创作者签名）
- `generate_xsc_main(a1, api, data, method)` → 网页主签名（www/edith 带参 GET）
- `cos_signature(...)` → 上传文件 COS 签名（HMAC-SHA1，纯 Python）

依赖：`pip install PyExecJS` + `npm install crypto-js`（项目根目录 node_modules）。

## 卡片设计（platforms/xiaohongshu/cards）

整合 xiaohongshu-card-design skill 规范 + qiaomu 三风格，字体自包含（`assets/fonts/`，不依赖 /tmp）。

**字号铁律**（小红书手机端，小字根本看不清，skill 硬规则）：

| 层级 | 字号 |
|:---|:---|
| 主标题 | 128px |
| 副标题 | 64px |
| 卡片标题 | 52px |
| 正文 | 38px |
| 标签 | 42px |

Golden rule：**If in doubt, make it bigger.** 小字 = 被划走的笔记。

**四风格**（随机选，无需确认）：
- `classic` — 米白杂志标准（#f5f3ed / #1a1a1a / #8b5e3c）
- `magazine` — 精致编辑（交替行背景 + 圆角）
- `artistic` — 实验暗色（#0A0615 / #C77DFF 紫 accent）
- `morandi` — 莫兰迪柔和（#f5ece6 / #3d3a38 / #b08d8d，圆角卡片）

另有 **AI 生成类风格**（baoyu-infographic 21 布局×21 风格 + baoyu-comic 6 风格×7 色调），
依赖 `image_generate` 工具（当前环境不可用），定义见 `references/card-styles.md`。

用法：
```python
from platforms.xiaohongshu.cards import generate_cards
paths = generate_cards(cards=[...], style="random", out_dir="/root/xhs_hermes_cards")
```

## 两层登录模型（小红书）

小红书有**两层独立登录**，发布/评论需要两层都有效：

| 层 | 域名 | 登录方式 | 用途 |
|:---|:-----|:-----|:-----|
| ① 网页版 | www.xiaohongshu.com | 扫码 | 浏览/看内容（web_session）|
| ② 创作者中心 | creator.xiaohongshu.com | 短信/扫码 | 发布/评论（customerClientId）|

- 网页版登录：`python main.py xiaohongshu`
- 创作者中心登录：访问 creator.xiaohongshu.com/login，点右上角二维码图标切换扫码
- 发布/评论需同时具备 `web_session` + `customerClientId`

## 安装

```bash
pip install -r requirements.txt
# patchright 浏览器（真 Chrome 走系统，无需额外安装）
```

## 注意事项

- 每个平台/账号使用独立且长期稳定的 Profile，不要每次随机。
- 版本固定（`requirements.txt` 用 `==`），人工控制升级。
- 闲鱼发布依赖 goofish-cli（`scripts/patch_goofish_cli.py` 修复其硬编码指纹）。
- 频繁脚本访问会触发平台风控（web_session 失效、评论 -104 等），需冷却期恢复。
