#!/usr/bin/env python3
"""
小红书 API 扫码登录（xhs SDK + qrcode 库，纯 API 不依赖浏览器）

【流程】
  1. get_qrcode() → 获取 qr_id + code + url
  2. qrcode 库从 url 生成二维码 PNG → 发用户
  3. check_qrcode() 轮询 code_status（0=未扫 1=已扫待确认 2=已确认登录成功）
  4. code_status==2 → 保存 cookie

【签名】用 platforms/xiaohongshu/sign.py 的 creator 签名（execjs+Node+crypto-js）
"""
import sys
import json
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))
_sau = "/root/.local/share/uv/tools/social-auto-upload/lib/python3.11/site-packages"
if _sau not in sys.path:
    sys.path.insert(0, _sau)

from uploader.xiaohongshu_uploader import sign as sign_mod  # noqa: E402
import qrcode  # noqa: E402
from xhs import XhsClient  # noqa: E402

QR_DIR = BASE_DIR / "qr"
COOKIE_DIR = BASE_DIR / "cookies"
QR_DIR.mkdir(exist_ok=True)
COOKIE_DIR.mkdir(exist_ok=True)

ACCOUNT_FILE = COOKIE_DIR / "xiaohongshu_hermes.json"
COOKIE_STR_FILE = COOKIE_DIR / "xiaohongshu_hermes_cookie.txt"
STATE_FILE = BASE_DIR / "login_state.txt"
QR_LATEST_FILE = BASE_DIR / "qr_latest.txt"

QR_TTL = 100  # 单次二维码有效期 100 秒（小红书服务端约 120 秒失效，提前刷新保证新鲜）


def _data_str(data):
    if isinstance(data, dict):
        return json.dumps(data, separators=(",", ":"), ensure_ascii=False)
    return data or ""


def sdk_sign(url, data=None, a1="", web_session=""):
    """适配 xhs SDK external_sign（creator 签名）"""
    return sign_mod.generate_xsc(a1, url, _data_str(data))


def ts():
    return time.strftime("%Y%m%d_%H%M%S")


def write_state(state, payload=""):
    STATE_FILE.write_text(f"{state} {payload}".strip())
    print(f"STATE:{state} {payload}", flush=True)


def save_qrcode_png(url):
    """用 qrcode 库从 url 生成二维码 PNG"""
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L,
                       box_size=10, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    out = str(QR_DIR / f"xhs_qr_{ts()}.png")
    img.save(out)
    for old in QR_DIR.glob("xhs_qr_*.png"):
        if str(old) != out:
            old.unlink(missing_ok=True)
    QR_LATEST_FILE.write_text(out)
    print(f"✅ 二维码已生成: {out}", flush=True)
    return out


def save_cookie(cookie_str):
    """保存 cookie（字符串 + storage_state JSON 两种格式）"""
    # 1. cookie 字符串
    COOKIE_STR_FILE.write_text(cookie_str)
    # 2. storage_state JSON（供 patchright 后续使用）
    cookies = []
    for part in cookie_str.split(";"):
        part = part.strip()
        if "=" in part:
            k, v = part.split("=", 1)
            cookies.append({
                "name": k, "value": v,
                "domain": ".xiaohongshu.com", "path": "/",
            })
    ACCOUNT_FILE.write_text(json.dumps({"cookies": cookies, "origins": []}, ensure_ascii=False, indent=2))
    print(f"✅ cookie 已保存: {ACCOUNT_FILE} ({len(cookies)} 项)", flush=True)


def main():
    client = XhsClient(sign=sdk_sign, timeout=60)
    print("=" * 56)
    print("小红书 API 扫码登录（xhs SDK + qrcode）")
    print("=" * 56)

    while True:
        # 1. 获取二维码
        write_state("GET_QR")
        qr_res = client.get_qrcode()
        qr_id = qr_res["qr_id"]
        code = qr_res["code"]
        url = qr_res["url"]
        print(f"qr_id={qr_id} code={code}", flush=True)
        print(f"url={url[:80]}", flush=True)

        # 2. 生成二维码图片
        qr_path = save_qrcode_png(url)
        write_state("QR_READY", qr_path)
        print(f"📱 请用小红书 APP 扫码（{QR_TTL}s 内有效）", flush=True)

        # 3. 轮询扫码状态
        start = time.time()
        last_status = -1
        while time.time() - start < QR_TTL:
            try:
                status = client.check_qrcode(qr_id, code)
                code_status = status.get("code_status", status.get("codeStatus", -1))
                if code_status != last_status:
                    print(f"  扫码状态: {code_status} (0=未扫 1=已扫待确认 2=已确认)", flush=True)
                    last_status = code_status
                if code_status == 2:
                    print("✅ 登录成功!", flush=True)
                    cookie = client.cookie
                    print(f"cookie 长度: {len(cookie)}", flush=True)
                    save_cookie(cookie)
                    write_state("SUCCESS", str(ACCOUNT_FILE))
                    return
            except Exception as e:
                print(f"⚠️ check_qrcode 异常: {str(e)[:100]}", flush=True)
            time.sleep(2)

        # 4. 二维码过期，重新获取
        print("🔄 二维码过期，重新获取...", flush=True)


if __name__ == "__main__":
    main()
