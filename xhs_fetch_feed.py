"""抓取推荐流帖子标题+URL（供选题和评论参考）"""
import os, sys, asyncio, json

sys.path.insert(0, "/root/autoLogin")
os.environ["DISPLAY"] = ":99"

import config  # noqa: E402
config.ensure_display()
config.ensure_sau_importable()

from patchright.async_api import async_playwright  # noqa: E402
from uploader.xiaohongshu_uploader.main import MAC_UA, MAC_OVERRIDE_SCRIPT, _LAUNCH_ARGS  # noqa: E402

COOKIE = "/root/.local/share/uv/tools/social-auto-upload/lib/python3.11/site-packages/cookies/xiaohongshu_autoContent.json"

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
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, executable_path=config.find_chrome(), args=_LAUNCH_ARGS)
        context = await browser.new_context(
            user_agent=MAC_UA, locale="zh-CN", timezone_id="Asia/Shanghai",
            viewport={"width": 1440, "height": 900}, device_scale_factor=2,
            storage_state=COOKIE,
        )
        await context.add_init_script("(" + MAC_OVERRIDE_SCRIPT + ")()")
        page = await context.new_page()

        await page.goto("https://www.xiaohongshu.com", wait_until="domcontentloaded", timeout=30000)
        await page.evaluate(MAC_OVERRIDE_SCRIPT)
        await asyncio.sleep(10)

        # 抓取推荐流：标题 + 链接（a.title 元素）
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

        # 保存到文件供后续使用
        with open("/tmp/xhs_feed_notes.json", "w") as f:
            json.dump(notes, f, ensure_ascii=False, indent=2)
        print(f"\n已保存 /tmp/xhs_feed_notes.json")
        await browser.close()

asyncio.run(main())
