"""小红书自动评论（主站笔记下发表评论）。

跨平台：Windows / macOS / Ubuntu 自动适配。
依赖：patchright + 真 Chrome + macOS 伪装 + 主站 web_session（先跑 xiaohongshu_main_login.py）。

用法：
    python xiaohongshu_comment.py [账号名] [评论内容]
    默认账号: autoContent
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
    parser = argparse.ArgumentParser(description="小红书自动评论")
    parser.add_argument("account", nargs="?", default="autoContent")
    parser.add_argument("comment", nargs="?", default="讲得很清楚，学习了！👍")
    args = parser.parse_args()

    cookie_file = str(config.xhs_cookie_file(args.account))
    comment = args.comment
    print(f"账号: {args.account} 评论: {comment[:30]}")

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

        # 1. 主站拿带 token 的笔记链接
        await page.goto("https://www.xiaohongshu.com", wait_until="domcontentloaded", timeout=30000)
        await page.evaluate(MAC_OVERRIDE_SCRIPT)
        await asyncio.sleep(8)

        links = await safe_eval(page, """() => {
            const result = [];
            document.querySelectorAll('a[href*="/explore/"][href*="xsec_token"]').forEach(a => result.push(a.href));
            return [...new Set(result)].slice(0, 1);
        }""")
        if not links or not isinstance(links, list) or len(links) == 0:
            print("❌ 无笔记链接（可能未登录主站，先跑 xiaohongshu_main_login.py）")
            await browser.close()
            return

        note_url = links[0]
        print(f"打开笔记: {note_url[:90]}")
        await page.goto(note_url, wait_until="domcontentloaded", timeout=30000)
        await page.evaluate(MAC_OVERRIDE_SCRIPT)
        await asyncio.sleep(15)

        # 2. 点击评论输入框聚焦
        clicked = await safe_eval(page, """() => {
            const input = document.querySelector('[contenteditable="true"]');
            if (input) { input.click(); input.focus(); return true; }
            return false;
        }""")
        print("点击评论框:", clicked)
        await asyncio.sleep(2)

        # 3. 输入评论内容
        typed = await page.evaluate("""(comment) => {
            const input = document.querySelector('[contenteditable="true"]');
            if (!input) return 'no-input';
            input.focus();
            document.execCommand('insertText', false, comment);
            input.dispatchEvent(new Event('input', {bubbles: true}));
            return {text: input.innerText.slice(0, 50)};
        }""", comment)
        print("输入评论:", json.dumps(typed, ensure_ascii=False, indent=2))
        await asyncio.sleep(2)

        # 4. 找提交按钮并点击
        submit = await safe_eval(page, """() => {
            const selectors = [
                'button[class*="submit"]', 'button[class*="send"]',
                'button[class*="publish"]', '[class*="submit"] button',
                '[class*="comment"] button', 'button:not([disabled])',
            ];
            for (const sel of selectors) {
                const btns = document.querySelectorAll(sel);
                for (const b of btns) {
                    const t = (b.innerText || '').trim();
                    if (t && (t.includes('发') || t.includes('提交') || t.includes('发送'))) {
                        b.click();
                        return {sel, text: t.slice(0, 20)};
                    }
                }
            }
            return null;
        }""")
        print("提交按钮:", json.dumps(submit, ensure_ascii=False, indent=2))
        await asyncio.sleep(5)

        # 5. 验证（排除输入框文字：检查评论区已有评论，需人工二次确认）
        verify = await safe_eval(page, """() => {
            const inputText = (document.querySelector('[contenteditable="true"]') || {}).innerText || '';
            return {
                inputCleared: inputText.length === 0,
                bodyTail: document.body.innerText.slice(-250),
            };
        }""")
        print("验证(输入框清空=可能已发出):", json.dumps(verify, ensure_ascii=False, indent=2))
        print("⚠️ 请人工在笔记评论区确认评论是否出现")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
