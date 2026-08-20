# autoLogin

社交平台自动化运营框架 —— 融合 [social-auto-upload](https://github.com/dreammis/social-auto-upload) 的多平台上传能力与 autoLogin 的深度运营增强（反检测、签名、卡片、评论、闲鱼）。

## 简介

本项目以 [social-auto-upload](https://github.com/dreammis/social-auto-upload) 为主体，集成其 13 个平台的视频/图文上传能力（`sau` CLI + Flask 后端 + Vue 前端），并融入 autoLogin 的中国平台深度运营能力：

- **匿名性核心** `core/stealth.py` —— 70+ 检测点反检测（可选增强）
- **真人行为** `core/human_behavior.py` —— 逐字输入、随机延迟、预热浏览，降低风控
- **小红书增强** —— x-s/x-t 签名、卡片生成、合规评论、推荐流抓取、SDK 纯 API 登录
- **闲鱼** —— 扫码登录（含人脸验证）、商品发布、每日轮换发布

## 功能特性

| 平台 | 登录 | 视频 | 图文 | 定时 | CLI | 说明 |
| --- | --- | --- | --- | --- | --- | --- |
| 抖音 | ✅ | ✅ | ✅ | ✅ | ✅ | 含短信二次验证 |
| 快手 | ✅ | ✅ | ✅ | ✅ | ✅ | 浏览器自动化 |
| 小红书 | ✅ | ✅ | ✅ | ✅ | ✅ | ★ 增强：签名/卡片/评论/SDK 登录 |
| Bilibili | ✅ | ✅ | ❌ | ✅ | ✅ | 自动准备 biliup |
| 视频号 | ✅ | ✅ | ❌ | ✅ | ✅ | 对应 tencent_uploader |
| 百家号 | ✅ | ✅ | ❌ | ❌ | ✅ | 浏览器自动化 |
| 支付宝生活号 | ✅ | ✅ | ❌ | ❌ | ✅ | 浏览器自动化 |
| 微博 | ✅ | ✅ | ❌ | ❌ | ✅ | 标题最多 30 字 |
| 虎扑 | ✅ | ✅ | ❌ | ❌ | ✅ | 标题 4–40 字 |
| 闲鱼 | ✅ | ✅ | ❌ | ❌ | — | ★ autoLogin 独有（goofish_uploader） |
| TikTok | ✅ | ✅ | ❌ | ✅ | ❌ | Chrome 版实现 |
| YouTube | ✅ | ✅ | ❌ | ❌ | ✅ | 交互式登录（Studio） |

## 项目结构

```
autoLogin/
├── sau_cli.py               # CLI 入口（sau <平台> login|check|upload-video|upload-note）
├── sau_backend.py           # Flask 后端
├── sau_frontend/            # Vue 前端
├── conf.py                  # 全局配置（Chrome 路径 / goofish / 小红书 cookie / QR）
│
├── core/                    # 核心层（平台无关）
│   ├── stealth.py           #   70+ 检测点匿名性核心
│   └── human_behavior.py    #   真人行为模块
│
├── uploader/                # 平台层
│   ├── base_video.py        #   上传基类（文件/定时校验）
│   ├── base_login.py        #   登录公共基类（DRY，消除各平台重复代码）
│   ├── douyin_uploader/     # 抖音（视频 + 图文）
│   ├── ks_uploader/         # 快手
│   ├── xiaohongshu_uploader/# 小红书（sign/cards/comment/feed/api_login）
│   ├── goofish_uploader/    # 闲鱼（login/publish/daily_publish）
│   ├── bilibili_uploader/   # B站
│   ├── tencent_uploader/    # 视频号
│   ├── weibo_uploader/      # 微博
│   ├── baijiahao_uploader/  # 百家号
│   ├── alipay_uploader/     # 支付宝生活号
│   ├── hupu_uploader/       # 虎扑
│   ├── tk_uploader/         # TikTok
│   └── youtube_uploader/    # YouTube
│
├── utils/                   # 工具层（stealth 脚本 / 二维码 / 日志）
├── examples/                # 示例脚本（获取 cookie / 上传）
├── tests/                   # 测试
└── skills/                  # Agent skill（douyin/kuaishou/xiaohongshu/bilibili）
```

## 安装

```bash
# 推荐使用 uv 安装
uv pip install -e .

# 小红书签名依赖（可选，仅 API 直发需要）
npm install crypto-js
pip install PyExecJS
```

## 快速开始

### 登录

```bash
sau douyin login --account <账号名>
sau xiaohongshu login --account <账号名>
sau kuaishou login --account <账号名>
sau bilibili login --account <账号名>
# ... 其他平台类似
```

### 发布

```bash
# 视频
sau douyin upload-video --account <账号名> --file videos/demo.mp4 --title "标题" --desc "简介"

# 图文
sau xiaohongshu upload-note --account <账号名> --images 1.png 2.png 3.png --title "标题" --note "正文"
```

> 一个 `account_name` 对应一个账号 cookie 文件，可准备多个账号，也可按账号名并发执行。

## 增强能力（autoLogin 融入）

### 小红书签名（API 直发）

`uploader/xiaohongshu_uploader/sign.py` 提供 x-s / x-t / x-s-common 本地签名（execjs + Node + crypto-js），可 API 直发（评论/发布/搜索），不依赖浏览器前端。改版时更新 `static/*.js` 即可。

### 小红书卡片生成

`cards.py` 四风格（classic / magazine / artistic / morandi），字号铁律（主标题 128px），字体自包含于 `assets/fonts/`。

### 小红书合规评论

`comment.py` 低频控制（单次 ≤5 条）+ 真人化输入 + 违规词过滤 + 公开可见性验证。

### 小红书 SDK 登录

`api_login.py` 基于 xhs SDK 纯 API 扫码登录（`get_qrcode` → 生成二维码 → `check_qrcode` 轮询），绕开浏览器自动化。

### 闲鱼（goofish）

`goofish_uploader/` 扫码登录（含人脸二次验证）+ 商品发布 + 每日按星期轮换发布。

## 详细文档

- [CLI 使用说明](./docs/CLI.md)
- [安装说明](./docs/install.md)
- [融合说明](./docs/autoLogin-fusion.md)

## 鸣谢

本项目融合并深度改造自 [social-auto-upload](https://github.com/dreammis/social-auto-upload)，感谢原作者及全部贡献者。

Bilibili 上传能力基于 [biliup](https://github.com/biliup/biliup) 接入封装。

## 许可证

本项目采用 [MIT License](LICENSE) 开源许可证。
