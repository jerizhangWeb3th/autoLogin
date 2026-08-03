#!/usr/bin/env python3
"""中国电商/社交平台扫码登录 CLI — 闲鱼 + 小红书。

用法:
    python main.py goofish          # 闲鱼扫码登录（含人脸识别二次扫码）
    python main.py xiaohongshu      # 小红书创作者中心扫码登录
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

# 本目录模块
sys.path.insert(0, str(Path(__file__).parent))

import config


def main() -> None:
    parser = argparse.ArgumentParser(
        description="中国平台扫码登录工具（闲鱼/小红书）— Xvfb 有头模式 + stealth 伪装",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "platform",
        choices=["goofish", "xiaohongshu"],
        help="目标平台",
    )
    args = parser.parse_args()

    # 确保虚拟显示器
    config.ensure_xvfb()

    if args.platform == "goofish":
        import goofish_login
        asyncio.run(goofish_login.run_login())
    elif args.platform == "xiaohongshu":
        import xiaohongshu_login
        asyncio.run(xiaohongshu_login.run_login())


if __name__ == "__main__":
    main()
