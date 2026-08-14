"""
中国平台登录大项目 — 统一入口

【架构】
    autoLogin/
    ├── stealth_core.py          # ★ 浏览器匿名性核心（独立优化点）
    ├── douyin_login.py          # 抖音登录模块
    ├── xiaohongshu_login.py     # 小红书登录模块
    ├── goofish_login.py         # 闲鱼登录模块
    ├── goofish_publish.py       # 闲鱼发布模块
    ├── verify_stealth.py        # 匿名性验证脚本
    └── tools/                   # 二维码/发码工具

【设计原则】
1. 浏览器匿名性（stealth_core.py）单独拎出 —— 匿名性不足只改这一个文件
2. 各平台登录是独立操作流程，互不影响
3. 跨平台：Windows / macOS / Linux 自动适配
"""

import argparse
import asyncio
import sys


def main():
    parser = argparse.ArgumentParser(description="中国平台登录")
    parser.add_argument("platform", choices=["douyin", "xiaohongshu", "goofish"],
                        help="要登录的平台")
    args = parser.parse_args()

    if args.platform == "douyin":
        from douyin_login import main as douyin_main
        asyncio.run(douyin_main())
    elif args.platform == "xiaohongshu":
        from xiaohongshu_login import main as xhs_main
        asyncio.run(xhs_main())
    elif args.platform == "goofish":
        from goofish_login import main as goofish_main
        asyncio.run(goofish_main())


if __name__ == "__main__":
    main()
