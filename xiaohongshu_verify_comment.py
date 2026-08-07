"""小红书评论验证 — 检查笔记评论区是否出现指定评论。

跨平台：Windows / macOS / Ubuntu 自动适配。

用法：
    python xiaohongshu_verify_comment.py [账号名] [评论内容片段] [笔记URL]
"""
import os
import sys
import asyncio
import json
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config  # noqa: E402

config.ensure_display()
config.ensure_sau_importable()

from patchright.async_api import async_playwright  # noqa: E402
from uploader.xiaohongshu_uploader.main import MAC_UA, MAC_OVERRIDE_SCRIPT, _LAUNCH_ARGS  # noqa: E402


async def safe_eval(page, script, retries=3, delay=4):
    for i in range(retries):
        try:
            return await page.evaluate(script)
        except Exception as e:
            if i < retries - 1:
                await asyncio.sleep(delay)
            else:
                return {"error": str(e)[:100]}


async def main():
    parser = argparse.ArgumentParser(description="小红书评论验证")
    parser.add_argument("account", nargs="?", default="autoContent")
    parser.add_argument("comment_fragment", nargs="?", default="讲得很清楚")
    parser.add_argument("note_url", nargs="?",
                        default="https://www.xiaohongshu.com/explore/6a748cb2000000002402f8e4?xsec_token=ABqVe8fo23bMfDIFLhdbED4t2YbSKTnAZef2t3Qvjwt7w=&xsec_source=pc_feed")
    args = parser.parse_args()

    cookie_file = str(config.xhs_cookie_file(args.account))
    print(f"验证账号: {args.account} 查找: {args.comment_fragment}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False, executable_path=config.find_chrome(), args=_LAUNCH_ARGS
        )
        context = await browser.new_context(
            user_agent=MAC_UA, locale="zh-CN", timezone_id="Asia/Shanghai",
            viewport={"width": 1440, "height": 900}, device_scale_factor=2,
            storage_state=cookie_file,
        )
        await context.add_init_script("(" + MAC_OVERRIDE_SCRIPT + ")()")
        page = await context.new_page()

        await page.goto(args.note_url, wait_until="domcontentloaded", timeout=30000)
        await page.evaluate(MAC_OVERRIDE_SCRIPT)
        await asyncio.sleep(15)

        # 只检查已发布评论（排除输入框文字）
        r = await safe_eval(page, """(fragment) => {
            const comments = [];
            document.querySelectorAll('[class*="comment-item"]').forEach(el => {
                const t = (el.innerText || '').trim();
                if (t && t.length > 2 && t.length < 300) comments.push(t);
            });
            // 在已发布评论中查找
            const found = comments.some(t => t.includes(fragment));
            return {
                commentCount: comments.length,
                found,
                sample: comments.slice(0, 3).map(t => t.slice(0, 50)),
            };
        }""", args.comment_fragment)
        print(json.dumps(r, ensure_ascii=False, indent=2))
        if isinstance(r, dict) and r.get("found"):
            print("✅ 评论已发布！")
        else:
            print("❌ 评论未找到（可能被折叠/未发出，请人工确认）")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
