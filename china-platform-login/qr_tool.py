#!/usr/bin/env python3
"""
抖音二维码/页面截图工具 — 取最新时间序列的一张

用法:
    python qr_tool.py latest        # 最新二维码
    python qr_tool.py page          # 最新页面截图(含二维码)
    python qr_tool.py list          # 列出所有二维码
    python qr_tool.py list_page     # 列出所有页面截图
"""
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()
QR_DIR = BASE_DIR / "qr"


def latest(prefix: str) -> str:
    files = sorted(QR_DIR.glob(f"{prefix}_*.png"), key=lambda f: f.name, reverse=True)
    return str(files[0]) if files else ""


def list_all(prefix: str):
    files = sorted(QR_DIR.glob(f"{prefix}_*.png"), key=lambda f: f.name, reverse=True)
    for f in files:
        print(f.name)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "latest"
    if cmd == "latest":
        print(latest("douyin_qr"))
    elif cmd == "page":
        print(latest("douyin_page"))
    elif cmd == "list":
        list_all("douyin_qr")
    elif cmd == "list_page":
        list_all("douyin_page")
