# 中国平台扫码登录工具（闲鱼 + 小红书）

把闲鱼（Goofish）和小红书（Xiaohongshu）的扫码登录流程融合为一个项目。
基于 **Patchright + 真 Chrome + Xvfb 有头模式 + 持久化 Profile**，
不做大量硬编码指纹伪造。

## 功能

| 平台 | 命令 | 说明 |
|:-----|:-----|:-----|
| 闲鱼 | `python main.py goofish` | 扫码登录 → 人脸识别二次扫码 → 保存 cookie |
| 小红书 | `python main.py xiaohongshu` | 创作者中心扫码登录 → 保存 storage_state |

## 项目结构

```
autoLogin/
├── main.py              # CLI 入口
├── config.py            # 共享配置（最小启动参数/路径/Xvfb）
├── stealth.py           # 旧伪装脚本 — 保留但默认禁用（STEALTH_ENABLED=False）
├── utils.py             # 共享工具（二维码生成/cookie 处理/日志脱敏）
├── goofish_login.py     # 闲鱼扫码登录（3 阶段流程）
├── xiaohongshu_login.py # 小红书扫码登录（qr-code 接口方案）
├── verify_stealth.py    # 原生指纹自洽性检查
├── assets/              # 二维码/截图输出
└── requirements.txt     # 固定版本
```

## 设计原则：减少伪装，提高一致性

本项目刻意**不做**大量 JS 指纹伪造（Canvas/WebGL/Audio/Chrome API 改写）。
原因：

1. **硬编码指纹产生矛盾信号**：实际环境是 Linux+Xvfb，却声明 macOS/Retina/
   Chrome126，系统字体、UA-CH、GPU、WebGPU、TLS 很容易被交叉比对识破
2. **Patchright 官方建议**：真 Chrome、持久化上下文、`no_viewport=True`，
   明确不要自定义 UA 或 headers
3. **伪装脚本自身可检测**：`screen.height=900` 但 `outerHeight=985`、
   权限 denied 但定位成功、WebGL 用 `Math.random()` 多次读取不一致
4. **注入可能破坏网站**：Canvas 像素改写、WebGL/Audio/媒体设备重写
   可能影响二维码、上传组件和页面正常逻辑
5. **持久化 Profile 积累的真实指纹就是最好的伪装**

保留的配置（收敛到最小）：
```python
def launch_kwargs() -> dict:
    return {
        "channel": "chrome",      # 真 Chrome（非 bundled chromium）
        "headless": False,        # Patchright 反检测在 headful 才完整
        "no_viewport": True,      # 窗口尺寸由系统真实产生
        "locale": "zh-CN",        # 部署环境匹配
        "timezone_id": "Asia/Shanghai",
        # 容器/root 环境才加 ["--no-sandbox"]
    }
```

**注意**：
- `--disable-blink-features=AutomationControlled` 已由 Patchright 处理，无需重复
- 每个平台/账号使用独立且**长期稳定**的 `user_data_dir`，不要每次随机
- Patchright 与 Chrome 版本固定（`requirements.txt` 用 `==`），人工控制升级
- `stealth.py` 保留但默认禁用（`STEALTH_ENABLED=False`），不接入运行流程

## 环境要求

- Linux + Xvfb（虚拟显示器，有头模式必需）
- 真 Chrome 浏览器
- Python 3.10+

```bash
# Xvfb 虚拟显示器
Xvfb :99 -screen 0 1440x900x24 &

# Python 依赖（版本已固定）
pip install -r requirements.txt
```

## 使用

```bash
# 闲鱼登录（输出二维码 → 用户扫码 → 人脸识别二维码 → 用户识别 → 自动保存 cookie）
python main.py goofish

# 小红书登录（输出二维码 → 用户扫码 → 自动保存 storage_state）
python main.py xiaohongshu

# 原生指纹自洽性检查
python verify_stealth.py
```

登录过程输出 `QR_READY` / `FACE_QR_READY` / `LOGIN_SUCCESS` 等标记，
二维码图片保存在 `assets/` 目录，可直接发给用户扫码。

## 关键经验（踩坑记录）

### 闲鱼
1. **必须用有头模式**（Xvfb）：headless 扫码会被阿里风控拒绝，不发放完整登录态
2. **扫码后有二次人脸识别**：新设备登录会跳转 `identity_verify.htm`，需把人脸二维码发给用户再扫一次
3. **cookie 必须只保留 `.goofish.com` 域**：混入 `.taobao.com` 域的同名 cookie（cookie2/_m_h5_tk/tfstk）会导致上传接口登录失效
4. 上传接口有临时风控（`rgv587_flag: sm, action=wait`）：请求太频繁会触发，需等待冷却
5. **判断扫码完成用 cookie，不要用页面跳转**：用户扫码确认后 cookie（unb/tracknick）立即建立，但页面可能不自动跳转仍停在登录页——轮询 cookie 最可靠
6. **不要点击任何按钮**：二维码提取后页面停留，用户扫码后 cookie 自动建立；点击"立即登录"等按钮反而可能触发额外风控

### 小红书
1. creator 登录页默认短信登录；**右上角 64x64 图标**切换到"APP扫一扫"
2. 页面 canvas 二维码（html2canvas 绘制）在自动化环境**渲染失败**，抓不到
3. 正确做法：拦截 `customer.xiaohongshu.com/api/cas/customer/web/qr-code` 接口拿 `qrCodeId`/`url`，用 qrcode 库生成二维码
4. 主站登录（web_session）**不等于**创作者中心登录（galaxy_creator_session_id），是两套独立会话
5. 登录态用 `storage_state`（cookies + localStorage）保存，权限 0600

### 安全
- 日志输出自动脱敏：不打印完整 qrCodeId / Cookie 值 / 账号标识
- cookie 文件与 storage_state 权限 0600
- 固定依赖版本，避免无控制升级引入破坏

## 免责声明

本工具仅用于个人账号自动化登录研究。请遵守各平台服务条款，
不要用于批量注册、营销骚扰等违规用途。
