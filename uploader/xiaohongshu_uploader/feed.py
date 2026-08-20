"""抓取小红书推荐流帖子标题 + URL（供选题和评论参考）。

适配融合项目：统一使用 core.stealth 的 MAC 伪装与启动参数，替代旧版
xiaohongshu_uploader.main 的 MAC_OVERRIDE_SCRIPT / _LAUNCH_ARGS。
"""
import asyncio
import json
import os
import sys
from pathlib import Path

_BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_BASE_DIR))
os.environ["DISPLAY"] = ":99"

from core.stealth import (  # noqa: E402
    MAC_UA,
    STEALTH_SCRIPT,
    LAUNCH_ARGS,
    ensure_display,
    find_chrome,
)
from patchright.async_api import async_playwright  # noqa: E402

ensure_display()

COOKIE = str(_BASE_DIR / "cookies" / "xiaohongshu_hermes.json")


async def safe_eval(page, script, retries=3, delay=4):
    """带重试的 page.evaluate，失败返回错误字典而非抛异常。"""
    for i in range(retries):
        try:
            return await page.evaluate(script)
        except Exception as e:
            if i < retries - 1:
                await asyncio.sleep(delay)
            else:
                return {"error": str(e)[:100]}


async def main():
    """打开小红书首页，抓取推荐流标题与链接，保存到 /tmp/xhs_feed_notes.json。"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False, executable_path=find_chrome(), args=LAUNCH_ARGS,
        )
        context = await browser.new_context(
            user_agent=MAC_UA,
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
            viewport={"width": 1440, "height": 900},
            device_scale_factor=2,
            storage_state=COOKIE,
        )
        await context.add_init_script(STEALTH_SCRIPT)
        page = await context.new_page()

        await page.goto("https://www.xiaohongshu.com", wait_until="domcontentloaded", timeout=30000)
        await page.evaluate(STEALTH_SCRIPT)
        await asyncio.sleep(10)

        notes = await safe_eval(page, """() => {
            const result = [];
            document.querySelectorAll('a.title[href*="/explore/"][href*="xsec_token"]').forEach(a => {
                const title = (a.innerText || '').trim();
                if (title) {
                    result.push({url: a.href, title});
                }
            });
            const seen = new Set();
            return result.filter(r => {
                if (seen.has(r.url)) return false;
                seen.add(r.url);
                return true;
            }).slice(0, 15);
        }""")

        if not notes or not isinstance(notes, list) or len(notes) == 0:
            print("❌ 无推荐流内容")
            await browser.close()
            return

        print(f"=== 推荐流 {len(notes)} 篇 ===")
        for i, n in enumerate(notes):
            print(f"[{i+1}] {n['title'][:50]}")
            print(f"    {n['url'][:80]}")

        with open("/tmp/xhs_feed_notes.json", "w") as f:
            json.dump(notes, f, ensure_ascii=False, indent=2)
        print("\n已保存 /tmp/xhs_feed_notes.json")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
