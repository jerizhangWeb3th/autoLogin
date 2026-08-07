"""小红书真人化评论 v3 — 完整模拟真人行为（逐字符打字/随机延迟/随机点击/预热浏览）

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

import human_behavior as hb  # noqa: E402

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
    """在指定笔记发评论（真人化操作），返回是否 API 确认"""
    # 打开笔记（带重试，预热后直接 goto 可能 ERR_CONNECTION_CLOSED）
    loaded = False
    for attempt in range(3):
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            loaded = True
            break
        except Exception as e:
            print(f"  goto 重试 {attempt+1}: {str(e)[:60]}")
            await asyncio.sleep(random.uniform(3, 6))
    if not loaded:
        return {"ok": False, "reason": "页面加载失败"}
    await page.evaluate(MAC_OVERRIDE_SCRIPT)
    await hb.page_load_delay()

    # 随机浏览一下评论区（模拟真人先看评论再回复）
    try:
        await page.mouse.wheel(0, random.randint(200, 500))
        await asyncio.sleep(random.uniform(1.0, 2.5))
        await page.mouse.wheel(0, random.randint(100, 300))
        await asyncio.sleep(random.uniform(0.8, 2.0))
    except Exception:
        pass

    # 聚焦评论框（真人点击，带移动轨迹）
    clicked = await hb.human_click(page, '[contenteditable="true"]')
    if not clicked:
        # fallback JS
        r = await safe_eval(page, """() => {
            const input = document.querySelector('[contenteditable="true"]');
            if (input) { input.click(); input.focus(); return true; }
            return false;
        }""", retries=1)
        if r is not True:
            return {"ok": False, "reason": "无评论框"}

    await hb.between_actions()

    # 逐字符真人输入
    typed = await hb.human_type_into(page, comment)
    if not typed:
        return {"ok": False, "reason": "输入失败"}

    # 输入完成后停顿（读一遍的感觉）
    await asyncio.sleep(random.uniform(1.5, 3.5))

    # 点击"发送"（随机偏移点击）
    sent = await hb.human_click(page, 'button[class*="submit"]', fallback_text="发送")
    if not sent:
        return {"ok": False, "reason": "无发送按钮"}

    # 等待 API 确认（最多 12s）
    for _ in range(12):
        await asyncio.sleep(1)
        if len(post_results) > before_count:
            r = post_results[-1]
            success = r.get("success") is True and r.get("code") == 0
            return {"ok": success, "comment_id": r.get("comment_id", "")}

    return {"ok": False, "reason": "API 未响应"}


async def main():
    parser = argparse.ArgumentParser(description="小红书真人化评论 v3")
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

        # 预热浏览：先逛逛推荐流（打破"登录→秒操作"机械形状）
        print("👀 预热浏览推荐流...")
        await hb.warmup_browse(page, min_scrolls=2, max_scrolls=3)

        # 需要链接的话先拿推荐流
        if need_url:
            await asyncio.sleep(random.uniform(2, 5))
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
                # 随机间隔（钟形分布 40-90s），模拟真人节奏
                wait_s = await hb.random_comment_interval(args.min_wait, args.min_wait + 50)
                print(f"  随机等待 {wait_s:.0f}s...")
                await asyncio.sleep(wait_s)

        ok_count = sum(1 for r in results if r.get("ok"))
        print(f"\n=== 完成: {ok_count}/{len(results)} 成功 ===")
        for r in results:
            print(f"  {'✅' if r.get('ok') else '❌'} {r['url'][:55]} | {r['comment']} | {r.get('comment_id','')[:20]}")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
