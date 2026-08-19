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
DEFAULT_COOKIE = str(Path.home() / ".local/share/uv/tools/social-auto-upload/lib/python3.11/site-packages/cookies/xiaohongshu_autoContent.json")


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
        # 等待 __INITIAL_STATE__.feed.feeds 数据
        data = None
        for _ in range(20):
            data = await eval_js(page, """() => {
                const s = window.__INITIAL_STATE__;
                return s?.feed?.feeds ?? null;
            }""", retries=1)
            if data:
                break
            await asyncio.sleep(1)

        feeds = parse_feed_list(data) if data else []
        await browser.close()
        return feeds[:count]


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

        # 滚动到评论区触发渲染
        await eval_js(page, """() => {
            const area = document.querySelector('.comments-container, .note-scroller, #noteContainer');
            if (area) area.scrollIntoView({ behavior: 'smooth', block: 'end' });
        }""")
        await asyncio.sleep(1)

        # 等待评论输入框出现
        ready = False
        for _ in range(20):
            found = await eval_js(page, """() => {
                if (document.querySelector('div.input-box div.content-edit p.content-input')) return 2;
                if (document.querySelector('div.input-box div.content-edit span')) return 2;
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

        # 点击评论输入框激活
        clicked = await eval_js(page, """() => {
            const p = document.querySelector('div.input-box div.content-edit p.content-input');
            if (p) { p.click(); return true; }
            const span = document.querySelector('div.input-box div.content-edit span');
            if (span) { span.click(); return true; }
            const box = document.querySelector('div.input-box');
            if (box) { box.click(); return true; }
            return false;
        }""")
        if not clicked:
            await browser.close()
            return {"success": False, "message": "未找到评论输入框"}
        await asyncio.sleep(0.5)

        # 逐字输入评论（模拟人类打字）
        escaped = json.dumps(content, ensure_ascii=False)
        await eval_js(page, f"""() => {{
            const p = document.querySelector('div.input-box div.content-edit p.content-input');
            if (!p) return false;
            p.focus();
            const text = {escaped};
            for (let i = 0; i < text.length; i++) {{
                document.execCommand('insertText', false, text[i]);
            }}
            return true;
        }}""")
        await asyncio.sleep(random.uniform(1, 3))

        # 提交
        submitted = await eval_js(page, """() => {
            const btn = document.querySelector('div.bottom button.submit');
            if (btn && !btn.disabled) { btn.click(); return true; }
            return false;
        }""")
        if not submitted:
            await browser.close()
            return {"success": False, "message": "未找到提交按钮"}

        await asyncio.sleep(random.uniform(2, 4))
        await browser.close()
        return {"success": True, "message": "评论发表成功"}


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
