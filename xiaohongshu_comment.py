#!/usr/bin/env python3
"""
小红书评论/互动模块（融合自 auto-rednote 插件）

来源：auto-rednote (BodaFu) 的 interact.ts + feeds.ts，翻译为 Python + patchright。
- list_feeds: 从 __INITIAL_STATE__.feed.feeds 提取推荐流
- post_comment: 在笔记下发表评论（准确的 selector）

用法：
    python xiaohongshu_comment.py --list-feeds [--count 5]
    python xiaohongshu_comment.py --comment <feedId> --xsec <xsecToken> --content "评论内容"
"""
import asyncio
import os
import sys
import json
import random
import argparse
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(BASE_DIR))

_sau = str(Path.home() / ".local/share/uv/tools/social-auto-upload/lib/python3.11/site-packages")
if _sau not in sys.path:
    sys.path.insert(0, _sau)

from stealth_core import MAC_UA, LAUNCH_ARGS, STEALTH_SCRIPT, find_chrome, ensure_display  # noqa: E402

XHS_HOME = "https://www.xiaohongshu.com"
DEFAULT_COOKIE = str(BASE_DIR / "cookies" / "xiaohongshu_hermes.json")


async def eval_js(page, script, retries=3):
    for i in range(retries):
        try:
            return await page.evaluate(script)
        except Exception:
            if i >= retries - 1:
                raise
            await asyncio.sleep(2)


def parse_feed_list(raw):
    """解析 feed 列表（从 __INITIAL_STATE__.feed.feeds）"""
    if not isinstance(raw, list):
        return []
    feeds = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        note_card = item.get("noteCard") or item.get("note_card") or {}
        feeds.append({
            "id": str(item.get("id") or item.get("noteId") or ""),
            "xsecToken": str(item.get("xsecToken") or item.get("xsec_token") or ""),
            "title": note_card.get("displayTitle") or "",
            "type": note_card.get("type") or "normal",
        })
    return [f for f in feeds if f["id"]]


async def list_feeds(count=10, cookie_path=DEFAULT_COOKIE):
    """获取首页推荐 Feed 列表"""
    ensure_display()
    chrome = find_chrome()
    from patchright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, executable_path=chrome, args=LAUNCH_ARGS)
        context = await browser.new_context(
            user_agent=MAC_UA, locale="zh-CN", timezone_id="Asia/Shanghai",
            viewport={"width": 1440, "height": 900}, device_scale_factor=2,
            storage_state=cookie_path,
        )
        await context.add_init_script(STEALTH_SCRIPT)
        page = await context.new_page()

        await page.goto(XHS_HOME, wait_until="domcontentloaded", timeout=60000)
        # 等待 .note-item 卡片出现（小红书改版后 __INITIAL_STATE__ 已失效，改从 DOM 提取）
        for _ in range(20):
            cnt = await eval_js(page, "() => document.querySelectorAll('.note-item').length", retries=1)
            if cnt and cnt > 0:
                break
            await asyncio.sleep(1)

        # 从 DOM 提取 feed 卡片（.note-item 里的 explore 链接含 feedId + xsecToken）
        feeds = await eval_js(page, """() => {
            const cards = document.querySelectorAll('.note-item');
            const feeds = [];
            cards.forEach(card => {
                const link = card.querySelector('a[href*="xsec_token"]') || card.querySelector('a[href*="/explore/"]');
                if (!link) return;
                const m = link.href.match(/\\/explore\\/([a-f0-9]{24})/i);
                if (!m) return;
                const tm = link.href.match(/xsec_token=([^&]+)/);
                feeds.push({
                    id: m[1],
                    xsecToken: tm ? decodeURIComponent(tm[1]) : '',
                });
            });
            return feeds;
        }""")
        await browser.close()
        return (feeds or [])[:count]


async def post_comment(feed_id, xsec_token, content, cookie_path=DEFAULT_COOKIE):
    """在笔记下发表顶级评论"""
    ensure_display()
    chrome = find_chrome()
    from patchright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, executable_path=chrome, args=LAUNCH_ARGS)
        context = await browser.new_context(
            user_agent=MAC_UA, locale="zh-CN", timezone_id="Asia/Shanghai",
            viewport={"width": 1440, "height": 900}, device_scale_factor=2,
            storage_state=cookie_path,
        )
        await context.add_init_script(STEALTH_SCRIPT)
        page = await context.new_page()

        url = f"{XHS_HOME}/explore/{feed_id}?xsec_token={xsec_token}&xsec_source=pc_feed"
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(3)

        # 滚动到评论区触发渲染（改版后用 window.scrollTo 滚动到底部）
        await eval_js(page, """() => {
            window.scrollTo(0, document.body.scrollHeight);
        }""")
        await asyncio.sleep(3)

        # 等待评论输入框出现
        ready = False
        for _ in range(20):
            found = await eval_js(page, """() => {
                if (document.querySelector('p.content-input')) return 2;
                if (document.querySelector('[class*="content-input"]')) return 2;
                if (document.querySelector('#noteContainer, .note-container, .note-scroller, .comments-container')) return 1;
                return 0;
            }""")
            if found == 2:
                ready = True
                break
            await asyncio.sleep(1)

        if not ready:
            await browser.close()
            return {"success": False, "message": "评论输入框未出现"}

        # 聚焦评论输入框（DOM 层 focus，不经过点击，避免遮罩拦截）
        clicked = await eval_js(page, """() => {
            const p = document.querySelector('p.content-input') || document.querySelector('[class*="content-input"]');
            if (p) { p.focus(); return true; }
            return false;
        }""")
        if not clicked:
            await browser.close()
            return {"success": False, "message": "未找到评论输入框"}
        await asyncio.sleep(0.5)

        # 逐字输入评论（模拟人类打字）
        escaped = json.dumps(content, ensure_ascii=False)
        await eval_js(page, f"""() => {{
            const p = document.querySelector('p.content-input') || document.querySelector('[class*="content-input"]');
            if (!p) return false;
            p.focus();
            const text = {escaped};
            for (let i = 0; i < text.length; i++) {{
                document.execCommand('insertText', false, text[i]);
            }}
            return true;
        }}""")
        await asyncio.sleep(random.uniform(1, 3))

        # 提交（精确匹配「发送」按钮，排除「登录」按钮）
        submitted = await eval_js(page, """() => {
            const btns = Array.from(document.querySelectorAll('button'));
            const send = btns.find(b => b.textContent.trim() === '发送' || b.textContent.trim() === '评论');
            if (send && !send.disabled) { send.click(); return true; }
            return false;
        }""")
        if not submitted:
            await browser.close()
            return {"success": False, "message": "未找到提交按钮"}

        await asyncio.sleep(3)

        # 验证：评论提交成功后输入框会清空
        cleared = await eval_js(page, """() => {
            const p = document.querySelector('p.content-input');
            return !p || !p.textContent || p.textContent.trim() === '';
        }""")
        await browser.close()
        if cleared:
            return {"success": True, "message": "评论发表成功"}
        else:
            return {"success": False, "message": "评论未确认发出（输入框未清空）"}


def main():
    ap = argparse.ArgumentParser(description="小红书评论（融合 auto-rednote）")
    ap.add_argument("--list-feeds", action="store_true")
    ap.add_argument("--count", type=int, default=5)
    ap.add_argument("--comment", help="feedId")
    ap.add_argument("--xsec", help="xsecToken")
    ap.add_argument("--content", help="评论内容")
    ap.add_argument("--cookie", default=DEFAULT_COOKIE)
    args = ap.parse_args()

    if args.list_feeds:
        feeds = asyncio.run(list_feeds(args.count, args.cookie))
        print(json.dumps(feeds, ensure_ascii=False, indent=2))
    elif args.comment and args.content:
        if not args.xsec:
            print("❌ 需要 --xsec <xsecToken>")
            sys.exit(1)
        result = asyncio.run(post_comment(args.comment, args.xsec, args.content, args.cookie))
        print(json.dumps(result, ensure_ascii=False))
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
