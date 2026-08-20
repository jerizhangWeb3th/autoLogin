"""共享工具函数 — 二维码生成、cookie 处理、日志。

两个平台的登录流程都复用这里的工具。
"""

import base64
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import conf as config


def log(msg: str) -> None:
    """带时间戳的日志输出（自动脱敏敏感信息）。"""
    msg = redact(msg)
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# ============================================================
# 日志脱敏
# ============================================================
_SENSITIVE_PATTERNS = [
    # qrCodeId / token / 会话 id（保留前 8 位便于对照）
    (re.compile(r"(qrCodeId|qr_code_id|session_id|access[-_]?token)=([A-Za-z0-9_\-]{8,})"), r"\1=[REDACTED:\2...]"),
    # 长 cookie 值
    (re.compile(r"(sgcookie|csg|cookie2|web_session|galaxy_creator_session_id)=[^\s,;}\"]+"), r"\1=[REDACTED]"),
    # 通用 token/ticket
    (re.compile(r"(token|ticket|secret)=[A-Za-z0-9_\-]{8,}"), r"\1=[REDACTED]"),
    # unb / 账号标识
    (re.compile(r"unb=(\d{4})\d+"), r"unb=\1****"),
]


def redact(text: str) -> str:
    for pattern, repl in _SENSITIVE_PATTERNS:
        text = pattern.sub(repl, text)
    return text


# ============================================================
# 二维码生成
# ============================================================
def generate_qr_png(content: str, out_path: str) -> bool:
    """用 qrcode 库把任意字符串内容生成二维码 PNG。

    返回 True 表示生成成功。
    """
    py_code = f"""
import qrcode
qr = qrcode.QRCode(version=None, box_size=10, border=4)
qr.add_data({json.dumps(content)})
qr.make(fit=True)
img = qr.make_image(fill_color="black", back_color="white")
img.save({json.dumps(out_path)})
print("QR_GEN_OK")
"""
    try:
        r = subprocess.run(
            [config.QR_PYTHON, "-c", py_code],
            capture_output=True, text=True, timeout=30,
        )
        ok = "QR_GEN_OK" in r.stdout
        if not ok:
            log(f"二维码生成失败: {r.stderr.strip()[:150]}")
        return ok
    except Exception as e:
        log(f"二维码生成异常: {e}")
        return False


# ============================================================
# Cookie 处理
# ============================================================
async def snap_cookies_async(context) -> dict:
    """async 版：抓取浏览器全部 cookie。"""
    cookies = await context.cookies()
    return {c["name"]: c["value"] for c in cookies if c.get("value")}


def _chmod_0600(path: str) -> None:
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def write_goofish_cookies(cookies: dict, path: str = None) -> None:
    """写闲鱼 cookies.json（Chrome 扩展风格 JSON 数组），权限 0600。

    注意：闲鱼必须只保留 .goofish.com 域的 cookie，
    混入 .taobao.com 域的同名 cookie 会导致上传接口登录失效。
    """
    path = path or str(config.GOOFISH_COOKIE_FILE)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(
        json.dumps(
            [{"name": k, "value": v} for k, v in cookies.items()],
            ensure_ascii=False, indent=2,
        )
    )
    _chmod_0600(path)
    log(f"✅ cookie 已写入 {path} (共 {len(cookies)} 个)")


async def save_storage_state(context, path: str = None) -> dict:
    """保存小红书 storage_state（cookies + localStorage），权限 0600。

    只输出字段存在性，不输出 Cookie 值/账号标识。
    """
    path = path or str(config.XHS_COOKIE_FILE)
    await context.storage_state(path=path)
    _chmod_0600(path)
    saved = json.loads(Path(path).read_text())
    cks = saved.get("cookies", [])
    names = [c["name"] for c in cks]
    log(f"💾 已保存 {len(cks)} 个 cookie → {path}")
    log(
        f"关键字段: a1={'✅' if 'a1' in names else '❌'} "
        f"galaxy={'✅' if 'galaxy_creator_session_id' in names else '❌'} "
        f"web_session={'✅' if 'web_session' in names else '❌'}"
    )
    return saved
