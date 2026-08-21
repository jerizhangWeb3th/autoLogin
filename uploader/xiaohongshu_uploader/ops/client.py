#!/usr/bin/env python3
"""
小红书自运营统一客户端（ops.client）

用 xhs SDK（XhsClient）纯 API 实现数据抓取，替代浏览器自动化（OpenClaw CDP）。
XhsClient 覆盖首页推荐流、笔记详情、用户信息/笔记、评论、通知、发布等全链路，
比浏览器自动化更稳定、更快，且天然规避 webdriver 指纹风控。

【cookie 加载】优先用含 customerClientId + galaxy_creator_session_id 的创作者
登录态（发布/评论权限），缺失时回退主站 web_session（浏览权限）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# 确保 autoLogin 项目根在 sys.path 最前（避免 import 到 sau 安装目录的同名包）
_BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
if str(_BASE_DIR) not in sys.path:
    sys.path.insert(0, str(_BASE_DIR))

# cookie 候选路径（按优先级：创作者中心登录态 > 主站登录态）
_COOKIE_CANDIDATES = [
    # sau 安装目录的创作者 cookie（含 customerClientId + galaxy_creator_session_id）
    Path.home() / ".local/share/uv/tools/social-auto-upload/lib/python3.11/site-packages/cookies/xiaohongshu_hermes.json",
    # autoLogin 项目 cookie（主站 web_session）
    _BASE_DIR / "cookies" / "xiaohongshu_hermes.json",
]


def load_cookie_string() -> str:
    """合并所有候选 cookie 文件为 k=v; k=v 字符串。

    两个文件互补：autoLogin 的含 web_session（主站签名必需），sau 的含
    customerClientId + galaxy_creator_session_id（创作者发布权限）。合并去重，
    后遍历到的覆盖同名 key。
    """
    merged: dict = {}
    for p in _COOKIE_CANDIDATES:
        if not p.exists():
            continue
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        cookies = raw.get("cookies", []) if isinstance(raw, dict) else []
        for c in cookies:
            if isinstance(c, dict) and c.get("name") and c.get("value"):
                merged[c["name"]] = c["value"]
    return "; ".join(f"{k}={v}" for k, v in merged.items())


def get_client(timeout: int = 60):
    """获取配置好 cookie + sign 的 XhsClient 实例。"""
    from xhs import XhsClient

    from uploader.xiaohongshu_uploader import sign as sign_mod

    def sdk_sign(url: str, data=None, a1: str = "", web_session: str = "") -> str:
        """适配 xhs SDK external_sign（creator 签名，execjs+Node+crypto-js）。"""
        data_str = json.dumps(data, separators=(",", ":"), ensure_ascii=False) if isinstance(data, (dict, list)) else (data or "")
        return sign_mod.generate_xsc(a1, url, data_str)

    cookie = load_cookie_string()
    return XhsClient(cookie=cookie, sign=sdk_sign, timeout=timeout)


if __name__ == "__main__":
    c = load_cookie_string()
    print(f"cookie 长度: {len(c)}")
    # 只打印关键字段，不泄露完整值
    for key in ("web_session", "customerClientId", "galaxy_creator_session_id"):
        present = f"{key}=" in c
        print(f"  {key}: {'✅' if present else '❌'}")
