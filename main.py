"""中国平台自动化运营 — 统一入口

分层架构：
    core/        匿名性 + 真人行为（平台无关基础）
    platforms/   各平台业务（登录 / 发布 / 评论 / 推荐流）
    scripts/     独立脚本（选题抓取等）

用法：
    python main.py douyin        # 抖音登录
    python main.py xiaohongshu   # 小红书登录
    python main.py goofish       # 闲鱼登录

设计原则：
    1. 匿名性（core/stealth）与真人行为（core/human_behavior）单独拎出，是唯二优化点
    2. 各平台业务独立成包，互不影响、各自演进
    3. 登录/发布/评论等脚本也可直接运行（不依赖 main.py）
"""
import argparse
import asyncio

LOGIN_MODULES = {
    "douyin": "platforms.douyin.login",
    "xiaohongshu": "platforms.xiaohongshu.login",
    "goofish": "platforms.goofish.login",
}


def main():
    parser = argparse.ArgumentParser(description="中国平台自动化运营")
    parser.add_argument("platform", choices=list(LOGIN_MODULES.keys()), help="要登录的平台")
    args = parser.parse_args()

    mod = __import__(LOGIN_MODULES[args.platform], fromlist=["main"])
    asyncio.run(mod.main())


if __name__ == "__main__":
    main()
