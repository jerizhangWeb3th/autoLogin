#!/usr/bin/env python3
"""
发送工具：取最新二维码+截图 → 复制到 sent/ 目录（防删除）→ 记录 md5

用法:
    python send_qr_now.py          # 复制最新二维码+截图到 sent/，打印 MEDIA 路径
    python send_qr_now.py verify   # 验证最近一次发送的文件 md5 是否与源一致
"""
import hashlib
import os
import shutil
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent.resolve()  # 项目根目录
QR_DIR = BASE_DIR / "qr"
SENT_DIR = QR_DIR / "sent"
SENT_DIR.mkdir(exist_ok=True)
LOG_FILE = QR_DIR / "send_log.txt"


def md5(p: str) -> str:
    with open(p, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


def latest(prefix: str) -> str:
    files = sorted(QR_DIR.glob(f"{prefix}_*.png"), key=lambda f: f.name, reverse=True)
    return str(files[0]) if files else ""


def do_send():
    qr = latest("douyin_qr")
    page = latest("douyin_page")
    stamp = time.strftime("%Y%m%d_%H%M%S")
    results = {}
    for key, src in [("QR", qr), ("PAGE", page)]:
        if not src or not os.path.exists(src):
            results[key] = f"ERROR: 无文件 {src}"
            continue
        # 复制到 sent/（唯一名字，永不删除）
        dest = str(SENT_DIR / f"{key}_{stamp}.png")
        shutil.copy2(src, dest)
        src_md5 = md5(src)
        dst_md5 = md5(dest)
        results[key] = {
            "src": os.path.basename(src),
            "dest": os.path.basename(dest),
            "src_md5": src_md5,
            "dst_md5": dst_md5,
            "match": src_md5 == dst_md5,
            "age_src": int(time.time() - os.path.getmtime(src)),
        }
        # 记录日志
        with open(LOG_FILE, "a") as f:
            f.write(f"{time.strftime('%H:%M:%S')} {key} {os.path.basename(src)} -> {os.path.basename(dest)} "
                    f"md5={src_md5[:12]}{'/' + dst_md5[:12]} match={'OK' if src_md5 == dst_md5 else 'MISMATCH!'} "
                    f"age={results[key]['age_src']}s\n")

    # 打印结果
    for key in ["QR", "PAGE"]:
        r = results[key]
        if isinstance(r, str):
            print(f"{key}: {r}")
        else:
            print(f"{key}: {r['dest']}")
            print(f"  md5 {r['src_md5'][:12]} == {r['dst_md5'][:12]} | match={r['match']} | age={r['age_src']}s")
    # 打印 MEDIA 路径（供回复使用）
    print("---")
    for key in ["QR", "PAGE"]:
        r = results[key]
        if isinstance(r, dict):
            print(f"MEDIA:{SENT_DIR / r['dest']}")


def verify():
    if not os.path.exists(LOG_FILE):
        print("无发送日志")
        return
    with open(LOG_FILE) as f:
        lines = f.readlines()
    print(f"发送日志 {len(lines)} 条:")
    for line in lines[-10:]:
        print(" ", line.strip())


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "verify":
        verify()
    else:
        do_send()
