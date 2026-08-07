"""小红书随机评论 v2：用 API 拦截验证（comment/post 返回 success 即成功）

用法：
    python xiaohongshu_random_comment.py [篇数] [间隔秒数]
    默认: 5 篇, 间隔 30-60s
"""
import os, sys, asyncio, json, random, argparse

sys.path.insert(0, "/root/china-platform-login")
os.environ["DISPLAY"] = ":99"

import config  # noqa: E402
config.ensure_display()
config.ensure_sau_importable()

from patchright.async_api import async_playwright  # noqa: E402
from uploader.xiaohongshu_uploader.main import MAC_UA, MAC_OVERRIDE_SCRIPT, _LAUNCH_ARGS  # noqa: E402

COOKIE = "/root/.local/share/uv/tools/social-auto-upload/lib/python3.11/site-packages/cookies/xiaohongshu_autoContent.json"

COMMENTS = [
    "收藏了，谢谢分享！",
    "学到了，关注了！",
    "很实用，支持！",
    "感谢分享，很有启发！",
    "写得很用心，赞！",
    "这个思路不错，收藏！",
]

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
    parser = argparse.ArgumentParser(description="小红书随机评论")
    parser.add_argument("count", nargs="?", type=int, default=5, help="评论篇数（默认5）")
    parser.add_argument("min_wait", nargs="?", type=int, default=30, help="最小间隔秒（默认30）")
    args = parser.parse_args()

    n_targets = max(1, min(args.count, 10))
    min_wait = args.min_wait

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, executable_path=config.find_chrome(), args=_LAUNCH_ARGS)
        context = await browser.new_context(
            user_agent=MAC_UA, locale="zh-CN", timezone_id="Asia/Shanghai",
            viewport={"width": 1440, "height": 900}, device_scale_factor=2,
            storage_state=COOKIE,
        )
        await context.add_init_script("(" + MAC_OVERRIDE_SCRIPT + ")()")

        # API 拦截：记录评论提交结果
        post_results = []
        async def on_response(resp):
            if "comment/post" in resp.url:
                try:
                    body = await resp.text()
                    data = json.loads(body)
                    post_results.append({
                        "url": resp.url[:100],
                        "code": data.get("code"),
                        "success": data.get("success"),
                        "msg": data.get("msg", "")[:50],
                        "comment_id": (data.get("data") or {}).get("comment", {}).get("id", ""),
                    })
                except Exception:
                    pass
        context.on("response", on_response)

        page = await context.new_page()
        await page.goto("https://www.xiaohongshu.com", wait_until="domcontentloaded", timeout=30000)
        await page.evaluate(MAC_OVERRIDE_SCRIPT)
        await asyncio.sleep(10)

        links = await safe_eval(page, """() => {
            const result = [];
            document.querySelectorAll('a[href*="/explore/"][href*="xsec_token"]').forEach(a => result.push(a.href));
            return [...new Set(result)];
        }""")
        if not links or not isinstance(links, list) or len(links) == 0:
            print("❌ 无推荐流链接")
            await browser.close()
            return

        random.shuffle(links)
        targets = links[:n_targets]
        print(f"推荐流 {len(links)} 篇，随机评论 {n_targets} 篇")

        results = []
        for idx, url in enumerate(targets):
            comment = random.choice(COMMENTS)
            print(f"\n[{idx+1}/3] {url[:70]}")
            print(f"  内容: {comment}")

            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await page.evaluate(MAC_OVERRIDE_SCRIPT)
            await asyncio.sleep(10)

            # 聚焦评论框
            await safe_eval(page, """() => {
                const input = document.querySelector('[contenteditable="true"]');
                if (input) { input.click(); input.focus(); return true; }
                return false;
            }""", retries=1)
            await asyncio.sleep(2)

            # 输入
            await page.evaluate("""(comment) => {
                const input = document.querySelector('[contenteditable="true"]');
                if (!input) return;
                input.focus();
                document.execCommand('insertText', false, comment);
                input.dispatchEvent(new Event('input', {bubbles: true}));
            }""", comment)
            await asyncio.sleep(3)

            # 点发送
            before = len(post_results)
            await safe_eval(page, """() => {
                const btns = document.querySelectorAll('button[class*="submit"]');
                for (const b of btns) {
                    const t = (b.innerText || '').trim();
                    if (t.includes('发送')) { b.click(); return true; }
                }
                return false;
            }""", retries=1)

            # 等待 API 响应（最多 10s）
            ok = False
            for _ in range(10):
                await asyncio.sleep(1)
                if len(post_results) > before:
                    ok = True
                    break

            if ok:
                r = post_results[-1]
                success = r.get("success") is True and r.get("code") == 0
                print(f"  ✅ API: success={success} comment_id={r.get('comment_id','')[:20]}")
                results.append({"url": url[:80], "comment": comment, "ok": success, "comment_id": r.get("comment_id","")})
            else:
                print(f"  ❌ 未捕获 API 响应")
                results.append({"url": url[:80], "comment": comment, "ok": False, "reason": "no-api"})

            # 间隔 30-60s
            if idx < len(targets) - 1:
                wait = random.randint(30, 60)
                print(f"  等待 {wait}s 防风控...")
                await asyncio.sleep(wait)

        ok_count = sum(1 for r in results if r.get("ok"))
        print(f"\n=== 完成: {ok_count}/{len(results)} 成功 ===")
        for r in results:
            print(f"  {'✅' if r.get('ok') else '❌'} {r['url'][:60]} | {r['comment']} | id={r.get('comment_id','')[:24]}")
        await browser.close()

asyncio.run(main())
