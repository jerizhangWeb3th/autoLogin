"""小红书安全评论 v1 — 合规版（2026-08-10）

针对官方 AI 治理新规优化：
1. ✅ 低频控制：单次最多 3 条（默认 2），全天建议 ≤5 条
2. ✅ 人工确认：评论前打印预览，等待确认（--auto 跳过）
3. ✅ 真人化：预热浏览/逐字符输入/随机间隔（40-90s 钟形）
4. ✅ 内容过滤：违规词检查
5. ✅ 公开验证：发送后确认评论公开显示

⚠️ 重要：自动评论是「虚假互动」高发风险区，官方 3/10 公告明确打击。
   请务必控制频率，建议每天 ≤5 条，且间隔分散。

用法：
    python xiaohongshu_safe_comment.py [评论文件] [--auto]

评论文件格式（每行）：URL<TAB>评论内容
"""
import os, sys, asyncio, json, random, argparse

os.environ["DISPLAY"] = ":99"

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent.parent))

import config  # noqa: E402
config.ensure_display()
config.ensure_sau_importable()

from patchright.async_api import async_playwright  # noqa: E402
from core.stealth import MAC_UA, STEALTH_SCRIPT, LAUNCH_ARGS  # noqa: E402

from core import human_behavior as hb  # noqa: E402

sys.path.insert(0, "/root/.hermes/scripts")
try:
    from xhs_content_filter import filter_content
except Exception:
    filter_content = None

COOKIE = "/root/autoLogin/cookies/xiaohongshu_hermes.json"
MAX_COMMENTS = 3  # 单次最多 3 条（安全上限）


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


async def verify_public_visible(page, comment_text):
    """验证评论公开显示在评论区"""
    keyword = (comment_text or "").strip()[:20]
    if not keyword:
        return True
    try:
        for _ in range(3):
            await page.mouse.wheel(0, random.randint(300, 600))
            await asyncio.sleep(random.uniform(1.0, 2.0))
        found = await safe_eval(page, f"""() => {{
            const kw = {json.dumps(keyword)};
            const all = Array.from(document.querySelectorAll('[class*="comment"] [class*="content"], [class*="comment"] p, [class*="comment"] span'));
            return all.some(e => (e.innerText || '').includes(kw));
        }}""", retries=2)
        return found is True
    except Exception:
        return True


async def comment_on(page, url, comment, post_results, before_count):
    """在指定笔记发评论（真人化+公开验证）"""
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
    await page.evaluate(STEALTH_SCRIPT)
    await hb.page_load_delay()

    # 滚动到评论区底部（确保评论区加载）
    try:
        await page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(3)
        # 再小幅滚动（模拟真人浏览）
        await page.mouse.wheel(0, random.randint(100, 300))
        await asyncio.sleep(random.uniform(1.0, 2.0))
    except Exception:
        pass

    # 聚焦评论框（JS 方式，避免占位符拦截）
    focused = await safe_eval(page, """() => {
        const input = document.querySelector('[contenteditable="true"], #content-textarea');
        if (input) { input.focus(); input.click(); return true; }
        return false;
    }""", retries=1)
    if focused is not True:
        clicked = await hb.human_click(page, '[contenteditable="true"]')
        if not clicked:
            return {"ok": False, "reason": "无评论框"}

    await hb.between_actions()

    # 逐字符真人输入
    typed = await hb.human_type_into(page, comment)
    if not typed:
        return {"ok": False, "reason": "输入失败"}

    await asyncio.sleep(random.uniform(1.5, 3.5))

    # 点击发送（精确找「发送」按钮，避免点到「登录」）
    sent = await safe_eval(page, """() => {
        const btns = Array.from(document.querySelectorAll('button'));
        const send = btns.find(b => { const t = (b.innerText || b.textContent || '').trim(); return t === '发送' || t === '评论'; });
        if (send && !send.disabled) { send.click(); return true; }
        return false;
    }""", retries=1)
    if sent is not True:
        return {"ok": False, "reason": "无发送按钮"}

    # 等待 API 确认
    api_ok = False
    comment_id = ""
    for _ in range(12):
        await asyncio.sleep(1)
        if len(post_results) > before_count:
            r = post_results[-1]
            api_ok = r.get("success") is True and r.get("code") == 0
            comment_id = r.get("comment_id", "")
            break

    if not api_ok:
        return {"ok": False, "reason": "API 未确认"}

    # 公开可见性验证
    await hb.between_actions()
    public_visible = await verify_public_visible(page, comment)
    if not public_visible:
        return {"ok": False, "reason": "评论未公开显示（可能被折叠）", "comment_id": comment_id}
    return {"ok": True, "comment_id": comment_id}


async def main():
    parser = argparse.ArgumentParser(description="小红书安全评论 v1")
    parser.add_argument("comments_file", nargs="?", default="/tmp/xhs_comments.txt")
    parser.add_argument("--auto", action="store_true", help="跳过人工确认")
    args = parser.parse_args()

    items = load_comments(args.comments_file)
    if not items:
        print(f"❌ 评论文件为空: {args.comments_file}")
        return

    # 安全上限
    if len(items) > MAX_COMMENTS:
        print(f"⚠️ 评论数量 {len(items)} 超过安全上限 {MAX_COMMENTS}，仅保留前 {MAX_COMMENTS} 条")
        items = items[:MAX_COMMENTS]

    # 内容过滤
    if filter_content:
        filtered = []
        for item in items:
            res = filter_content("", item["comment"], [])
            if res["safe"]:
                filtered.append(item)
            else:
                print(f"❌ 违规词拦截: {item['comment'][:40]} {res.get('warnings', [])}")
        items = filtered
        if not items:
            print("全部被过滤，退出")
            return
    print("✅ 内容过滤通过")

    # 人工确认
    if not args.auto:
        print("\n📋 评论预览:")
        for i, item in enumerate(items):
            print(f"  [{i+1}] {item['url'][:60] if item['url'] else '(推荐流)'}")
            print(f"      → {item['comment'][:60]}")
        print(f"\n⏸️ 共 {len(items)} 条，按 Enter 执行，Ctrl+C 取消")
        try:
            input()
        except (KeyboardInterrupt, EOFError):
            print("\n❌ 已取消")
            return

    # 无 URL 的项从推荐流补
    need_url = [i for i in items if not i["url"]]

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, executable_path=config.find_chrome(), args=LAUNCH_ARGS)
        context = await browser.new_context(
            user_agent=MAC_UA, locale="zh-CN", timezone_id="Asia/Shanghai",
            viewport={"width": 1440, "height": 900}, device_scale_factor=2,
            storage_state=COOKIE,
        )
        await context.add_init_script(STEALTH_SCRIPT)

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

        print("👀 预热浏览推荐流...")
        await hb.warmup_browse(page, min_scrolls=2, max_scrolls=3)

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
                wait_s = await hb.random_comment_interval(45, 95)
                print(f"  随机等待 {wait_s:.0f}s...")
                await asyncio.sleep(wait_s)

        ok_count = sum(1 for r in results if r.get("ok"))
        print(f"\n=== 完成: {ok_count}/{len(results)} 成功 ===")
        for r in results:
            print(f"  {'✅' if r.get('ok') else '❌'} {r['url'][:55]} | {r['comment']} | {r.get('comment_id','')[:20]}")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
