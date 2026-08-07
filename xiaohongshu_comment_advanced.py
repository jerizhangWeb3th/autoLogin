"""小红书真人化评论：从文件读取针对性评论 → 逐条发表（API 验证）

用法：
    python xiaohongshu_comment_advanced.py [评论文件] [最小间隔]
    
评论文件格式（每行一条）：
    URL<TAB>评论内容
    或 仅评论内容（自动从推荐流挑帖）
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

async def safe_eval(page, script, retries=3, delay=4):
    for i in range(retries):
        try:
            return await page.evaluate(script)
        except Exception as e:
            if i < retries - 1:
                await asyncio.sleep(delay)
            else:
                return {"error": str(e)[:100]}

def load_comments(path):
    """加载评论文件：每行 URL<TAB>评论 或 仅评论"""
    items = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "\t" in line:
                url, comment = line.split("\t", 1)
                items.append({"url": url.strip(), "comment": comment.strip()})
            else:
                items.append({"url": None, "comment": line})
    return items


async def comment_on(page, url, comment, post_results, before_count):
    """在指定笔记发评论，返回是否 API 确认"""
    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
    await page.evaluate(MAC_OVERRIDE_SCRIPT)
    await asyncio.sleep(10)

    # 聚焦评论框
    clicked = await safe_eval(page, """() => {
        const input = document.querySelector('[contenteditable="true"]');
        if (input) { input.click(); input.focus(); return true; }
        return false;
    }""", retries=1)
    if clicked is not True:
        return {"ok": False, "reason": "无评论框"}

    await asyncio.sleep(2)

    # 输入（真人化评论，带 emoji/标点更像真人）
    await page.evaluate("""(comment) => {
        const input = document.querySelector('[contenteditable="true"]');
        if (!input) return;
        input.focus();
        document.execCommand('insertText', false, comment);
        input.dispatchEvent(new Event('input', {bubbles: true}));
    }""", comment)
    await asyncio.sleep(3)

    # 点发送
    await safe_eval(page, """() => {
        const btns = document.querySelectorAll('button[class*="submit"]');
        for (const b of btns) {
            const t = (b.innerText || '').trim();
            if (t.includes('发送')) { b.click(); return true; }
        }
        return false;
    }""", retries=1)

    # 等待 API 确认（最多 12s）
    for _ in range(12):
        await asyncio.sleep(1)
        if len(post_results) > before_count:
            r = post_results[-1]
            success = r.get("success") is True and r.get("code") == 0
            return {"ok": success, "comment_id": r.get("comment_id", "")}

    return {"ok": False, "reason": "API 未响应"}


async def main():
    parser = argparse.ArgumentParser(description="小红书真人化评论")
    parser.add_argument("comments_file", nargs="?", default="/tmp/xhs_comments.txt", help="评论文件（每行: URL<TAB>评论）")
    parser.add_argument("min_wait", nargs="?", type=int, default=40, help="最小间隔秒")
    args = parser.parse_args()

    items = load_comments(args.comments_file)
    if not items:
        print(f"❌ 评论文件为空: {args.comments_file}")
        return

    # 无 URL 的项从推荐流补链接
    need_url = [i for i in items if not i["url"]]
    has_url = [i for i in items if i["url"]]

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, executable_path=config.find_chrome(), args=_LAUNCH_ARGS)
        context = await browser.new_context(
            user_agent=MAC_UA, locale="zh-CN", timezone_id="Asia/Shanghai",
            viewport={"width": 1440, "height": 900}, device_scale_factor=2,
            storage_state=COOKIE,
        )
        await context.add_init_script("(" + MAC_OVERRIDE_SCRIPT + ")()")

        # API 拦截
        post_results = []
        async def on_response(resp):
            if "comment/post" in resp.url:
                try:
                    body = await resp.text()
                    data = json.loads(body)
                    post_results.append({
                        "code": data.get("code"),
                        "success": data.get("success"),
                        "comment_id": (data.get("data") or {}).get("comment", {}).get("id", ""),
                    })
                except Exception:
                    pass
        context.on("response", on_response)

        page = await context.new_page()

        # 需要链接的话先拿推荐流
        if need_url:
            await page.goto("https://www.xiaohongshu.com", wait_until="domcontentloaded", timeout=30000)
            await page.evaluate(MAC_OVERRIDE_SCRIPT)
            await asyncio.sleep(10)
            links = await safe_eval(page, """() => {
                const result = [];
                document.querySelectorAll('a[href*="/explore/"][href*="xsec_token"]').forEach(a => result.push(a.href));
                return [...new Set(result)];
            }""")
            random.shuffle(links if isinstance(links, list) else [])
            for i, item in enumerate(need_url):
                if links and i < len(links):
                    item["url"] = links[i]

        # 过滤无 URL 的项
        items = [i for i in items if i["url"]]
        print(f"待评论 {len(items)} 条")

        results = []
        for idx, item in enumerate(items):
            url, comment = item["url"], item["comment"]
            print(f"\n[{idx+1}/{len(items)}] {url[:70]}")
            print(f"  评论: {comment[:60]}")

            before = len(post_results)
            r = await comment_on(page, url, comment, post_results, before)
            print(f"  结果: {json.dumps(r, ensure_ascii=False)}")
            results.append({"url": url[:80], "comment": comment[:50], "ok": r.get("ok"), "comment_id": r.get("comment_id", "")})

            if idx < len(items) - 1:
                wait = random.randint(args.min_wait, args.min_wait + 20)
                print(f"  等待 {wait}s...")
                await asyncio.sleep(wait)

        ok_count = sum(1 for r in results if r.get("ok"))
        print(f"\n=== 完成: {ok_count}/{len(results)} 成功 ===")
        for r in results:
            print(f"  {'✅' if r.get('ok') else '❌'} {r['url'][:55]} | {r['comment']} | {r.get('comment_id','')[:20]}")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
