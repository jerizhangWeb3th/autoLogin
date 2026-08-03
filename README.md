# 中国平台扫码登录工具（闲鱼 + 小红书）

把闲鱼（Goofish）和小红书（Xiaohongshu）的扫码登录流程融合为一个项目。
通过 Xvfb 虚拟显示器 + 有头模式 Chrome + 60+ 检测点 stealth 伪装，
绕过中国平台（阿里风控 / 小红书风控）对无头浏览器的识别。

## 功能

| 平台 | 命令 | 说明 |
|:-----|:-----|:-----|
| 闲鱼 | `python main.py goofish` | 扫码登录 → 人脸识别二次扫码 → 保存 cookie |
| 小红书 | `python main.py xiaohongshu` | 创作者中心扫码登录 → 保存 storage_state |

## 项目结构

```
china-platform-login/
├── main.py              # CLI 入口
├── config.py            # 共享配置（浏览器指纹/路径/Xvfb）
├── stealth.py           # 完整浏览器伪装脚本（60+ 检测点）
├── utils.py             # 共享工具（二维码生成/cookie 处理）
├── goofish_login.py     # 闲鱼扫码登录（3 阶段流程）
├── xiaohongshu_login.py # 小红书扫码登录（qr-code 接口方案）
├── assets/              # 二维码/截图输出
└── requirements.txt
```

## 环境要求

- Linux + Xvfb（虚拟显示器，有头模式必需）
- Chrome 浏览器
- Python 3.10+
- [patchright](https://github.com/Kaliiiiiiiiii-Vinyzu/patchright)（反检测 playwright 分支）
- qrcode + pillow（二维码生成）

```bash
# Xvfb 虚拟显示器
Xvfb :99 -screen 0 1440x900x24 &

# Python 依赖
pip install patchright qrcode pillow
```

## 使用

```bash
# 闲鱼登录（输出二维码 → 用户扫码 → 人脸识别二维码 → 用户识别 → 自动保存 cookie）
python main.py goofish

# 小红书登录（输出二维码 → 用户扫码 → 自动保存 storage_state）
python main.py xiaohongshu
```

登录过程会输出 `QR_READY` / `FACE_QR_READY` / `LOGIN_SUCCESS` 等标记，
二维码图片保存在 `assets/` 目录，可直接发给用户扫码。

## 关键经验（踩坑记录）

### 闲鱼
1. **必须用有头模式**（Xvfb）：headless 扫码会被阿里风控拒绝，不发放完整登录态
2. **扫码后有二次人脸识别**：新设备登录会跳转 `identity_verify.htm`，需把人脸二维码发给用户再扫一次
3. **cookie 必须只保留 `.goofish.com` 域**：混入 `.taobao.com` 域的同名 cookie（cookie2/_m_h5_tk/tfstk）会导致上传接口登录失效
4. 上传接口有临时风控（`rgv587_flag: sm, action=wait`）：请求太频繁会触发，需等待冷却

### 小红书
1. creator 登录页默认短信登录；**右上角 64x64 图标**切换到"APP扫一扫"
2. 页面 canvas 二维码（html2canvas 绘制）在自动化环境**渲染失败**，抓不到
3. 正确做法：拦截 `customer.xiaohongshu.com/api/cas/customer/web/qr-code` 接口拿 `qrCodeId`/`url`，用 qrcode 库生成二维码
4. 主站登录（web_session）**不等于**创作者中心登录（galaxy_creator_session_id），是两套独立会话
5. 登录态用 `storage_state`（cookies + localStorage）保存，不是普通 cookie 文件

## 免责声明

本工具仅用于个人账号自动化登录研究。请遵守各平台服务条款，
不要用于批量注册、营销骚扰等违规用途。
