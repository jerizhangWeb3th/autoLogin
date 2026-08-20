# autoLogin + social-auto-upload 融合说明

> 融合日期：2026-08-20　·　按阿里巴巴代码规范（PEP8 + 分层 + 命名 + docstring + 显式异常 + 统一日志 + 类型注解）

## 一、融合概览

以 **social-auto-upload（sau）** 为主体，保留其全部能力（13 平台登录/上传 + sau CLI + Flask 后端 + Vue 前端 + tests + skills），
融入 **autoLogin** 的深度运营增强能力，形成统一的社交平台自动化运营框架。

| 来源 | 贡献 |
|:-----|:-----|
| sau（主体） | 13 平台 uploader、sau_cli、sau_backend(Flask)、sau_frontend(Vue)、examples、tests、skills |
| autoLogin | core/stealth（70+ 检测点）、core/human_behavior（真人行为）、小红书 sign/cards/comment/feed/api_login、闲鱼 goofish、跨平台 config |

## 二、项目结构（融合后）

```
social-auto-upload-dreammis/
├── sau_cli.py               # CLI 入口（sau douyin/xiaohongshu/... login|upload-video|upload-note）
├── sau_backend.py           # Flask 后端
├── sau_frontend/            # Vue 前端
├── conf.py                  # ★ 全局配置（整合 autoLogin 的 goofish/xhs/QR 常量）
│
├── core/                    # ★ 核心层（autoLogin 融入，平台无关）
│   ├── stealth.py           #   70+ 检测点匿名性核心（find_chrome/ensure_display/STEALTH_SCRIPT）
│   └── human_behavior.py    #   真人行为（逐字输入/随机延迟/预热浏览）
│
├── uploader/                # 平台层（13 平台 + 闲鱼）
│   ├── base_video.py        #   上传基类（文件校验/定时校验）
│   ├── base_login.py        # ★ 登录公共基类（format_msg/build_login_result/emit_qrcode_callback/
│   │                        #     build_launch_kwargs/resolve_account_file，消除 13 平台重复）
│   ├── douyin_uploader/     # 抖音（视频 + 图文）
│   ├── kuaishou_uploader/   # 快手（ks_uploader）
│   ├── xiaohongshu_uploader/# ★ 小红书（增强）
│   │   ├── main.py          #   上传
│   │   ├── sign.py          #   ★ x-s/x-t 签名（execjs + crypto-js，autoLogin 融入）
│   │   ├── cards.py         #   ★ 卡片生成（四风格，字体自包含）
│   │   ├── comment.py       #   ★ 合规评论（低频 + 真人化 + 内容过滤）
│   │   ├── feed.py          #   ★ 推荐流抓取
│   │   ├── api_login.py     #   ★ xhs SDK 纯 API 扫码登录
│   │   ├── xhs_selectors.py #   ★ selector 候选库（改版集中更新）
│   │   └── static/          #   签名 JS（xhs_creator/main/rap）
│   ├── goofish_uploader/    # ★ 闲鱼（autoLogin 独有，新增）
│   │   ├── login.py         #   扫码登录（含人脸二次验证）
│   │   ├── publish.py       #   发布商品（依赖 goofish-cli）
│   │   ├── daily_publish.py #   每日按星期轮换发布
│   │   └── utils.py         #   日志脱敏/cookie 处理
│   ├── bilibili_uploader/   # B站
│   ├── tencent_uploader/    # 腾讯（视频号）
│   ├── weibo_uploader/      # 微博
│   ├── baijiahao_uploader/  # 百家号
│   ├── alipay_uploader/     # 支付宝生活号
│   ├── hupu_uploader/       # 虎扑
│   ├── tk_uploader/         # TikTok
│   └── youtube_uploader/    # YouTube
│
├── utils/                   # 工具层（sau 原有：base_social_media/login_qrcode/log/stealth.min.js）
├── examples/  tests/  skills/  docs/  myUtils/
└── node_modules/crypto-js   # 小红书签名依赖（autoLogin 融入）
```

## 三、新增能力（autoLogin → sau）

1. **小红书签名** `sign.py` —— x-s/x-t/x-s-common 本地生成（execjs + Node + crypto-js），API 直发不依赖浏览器。
2. **小红书卡片** `cards.py` —— 四风格（classic/magazine/artistic/morandi），字号铁律（主标题 128px）。
3. **小红书评论** `comment.py` —— 合规评论（单次 ≤5 条、真人化输入、违规词过滤、公开可见性验证）。
4. **小红书推荐流** `feed.py` —— 抓取推荐流供选题。
5. **小红书 SDK 登录** `api_login.py` —— xhs SDK 纯 API 扫码登录，绕开浏览器自动化。
6. **闲鱼** `goofish_uploader/` —— 扫码登录（含人脸验证）+ 商品发布 + 每日轮换发布。
7. **匿名性核心** `core/stealth.py` —— 70+ 检测点，作为可选增强（默认仍用 sau 的 stealth.min.js，符合"减少伪装"偏好）。
8. **真人行为** `core/human_behavior.py` —— 逐字输入、随机延迟、预热浏览，降低风控。

## 四、阿里巴巴规范落地

- **DRY**：抽取 `base_login.py`，删除 9 个平台重复的 `_msg`/`_emit_qrcode_callback`/`_build_login_result`（共 -705 行 / +513 行）。
- **分层**：core（平台无关）↔ uploader（平台业务）↔ utils（工具）。
- **命名**：snake_case 函数/变量、CamelCase 类、UPPER_CASE 常量。
- **docstring**：公共模块/函数均有 Google 风格 docstring。
- **类型注解**：`from __future__ import annotations` + 参数/返回值注解。
- **显式异常**：明确异常类型，删除未使用 import。
- **统一日志**：loguru logger（sau 原有）。

## 五、验证结果

- **import 验证**：全部 13 平台 uploader + core + goofish + sau_cli 均 import 通过。
- **CLI 验证**：`sau --help` 正常（douyin/kuaishou/xiaohongshu/bilibili/tencent/youtube）。
- **签名验证**：`sign.available() == True`，x-s/x-t 正常生成。
- **测试**：45 项测试，38 通过；7 失败均为 dreammis 项目原有技术债（融合前即失败，`git stash` 验证确认非融合引入）。

## 六、待办（渐进优化）

- `_build_launch_kwargs` / `_resolve_account_file` 仍为各平台本地定义（因参数差异暂未迁移，可后续精细处理）。
- hupu / youtube 的 `_build_login_result` 为"缺 qrcode"变体，保留本地定义。
