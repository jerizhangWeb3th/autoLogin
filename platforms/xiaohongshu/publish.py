"""小红书安全发布 v2 — 合规版（2026-08-10）

针对官方 AI 治理新规（2/12 AI标识、3/10 托管治理、4/27 治理主张）优化：
1. ✅ AI 生成内容主动勾选「AI 标识」（符合 2/12 强制标识要求）
2. ✅ 原创声明勾选
3. ✅ 人工确认模式（默认）：发布前停在预览页，等人工确认
4. ✅ 真人化节奏（随机延迟/逐字符输入）
5. ✅ 内容过滤（违规词检查）

用法：
    python xiaohongshu_safe_publish.py [图片1 图片2 ...] --title "标题" --note "正文" [--tags 标签1,标签2] [--auto] [--ai-label]

参数：
    --auto      跳过人工确认直接发布（默认人工确认）
    --ai-label  AI 生成内容主动勾选标识（推荐 AI 生成时使用）
    --no-label  不勾选 AI 标识（真人原创时）
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

COOKIE = "/root/autoLogin/cookies/xiaohongshu_hermes.json"
PUBLISH_URL = "https://creator.xiaohongshu.com/publish/publish?from=homepage&target=image"

# 内容过滤
sys.path.insert(0, "/root/.hermes/scripts")
try:
    from xhs_content_filter import filter_content
except Exception:
    filter_content = None


async def safe_eval(page, script, retries=3, delay=4):
    for i in range(retries):
        try:
            return await page.evaluate(script)
        except Exception as e:
            if i < retries - 1:
                await asyncio.sleep(delay)
            else:
                return {"error": str(e)[:100]}


async def human_type(page, text, selector=None):
    """逐字符拟人输入（40-120ms/字符）"""
    if selector:
        await page.click(selector)
        await asyncio.sleep(random.uniform(0.5, 1.5))
    for ch in text:
        await page.keyboard.type(ch, delay=random.uniform(40, 120))
    await asyncio.sleep(random.uniform(0.5, 1.5))


async def check_ai_label(page):
    """勾选「AI 生成内容」标识（小红书 2/12 新规要求）"""
    # 查找 AI 标识相关元素
    found = await safe_eval(page, """() => {
        const candidates = [];
        // 常见文案
        const texts = ['AI生成', 'AI合成', '含AI', '人工智能生成', 'AIGC', 'AI 生成'];
        for (const t of texts) {
            const els = Array.from(document.querySelectorAll('div,span,label,button'))
                .filter(e => e.innerText && e.innerText.includes(t) && e.children.length < 5);
            candidates.push(...els.map(e => ({text: e.innerText.trim().slice(0, 40), cls: (e.className||'').slice(0,50)})));
        }
        return candidates.slice(0, 15);
    }""", retries=2)
    print("AI 标识候选:", json.dumps(found, ensure_ascii=False) if isinstance(found, list) else found)

    # 尝试勾选（checkbox/switch）
    clicked = await safe_eval(page, """() => {
        const texts = ['AI生成', 'AI合成', '含AI', '人工智能生成', 'AIGC'];
        for (const t of texts) {
            // 找 checkbox
            const cb = document.querySelector('label:has-text("' + t + '") input[type="checkbox"], ' +
                'div:has-text("' + t + '") input[type="checkbox"], ' +
                'label:has-text("' + t + '") .d-checkbox, ' +
                'div:has-text("' + t + '") .d-switch');
            if (cb) {
                if (cb.type === 'checkbox' && !cb.checked) cb.click();
                else if (!cb.classList.contains('d-checkbox-checked') && !cb.classList.contains('d-switch-checked')) cb.click();
                return {ok: true, method: 'checkbox', text: t};
            }
            // 找可点击的标签
            const label = Array.from(document.querySelectorAll('label, div, span'))
                .find(e => e.innerText && e.innerText.trim() === t);
            if (label && label.click) { label.click(); return {ok: true, method: 'label', text: t}; }
        }
        return {ok: false};
    }""", retries=2)
    print("AI 标识勾选:", json.dumps(clicked, ensure_ascii=False))
    return clicked and clicked.get("ok")


async def check_original(page):
    """勾选原创声明"""
    await safe_eval(page, """() => {
        const texts = ['原创'];
        const cb = document.querySelector('label:has-text("原创") input[type="checkbox"], div:has-text("原创") input[type="checkbox"], label:has-text("原创") .d-checkbox');
        if (cb) {
            if (cb.type === 'checkbox' && !cb.checked) cb.click();
            else if (!cb.classList.contains('d-checkbox-checked')) cb.click();
            return true;
        }
        const label = Array.from(document.querySelectorAll('label, div, span'))
            .find(e => e.innerText && e.innerText.trim().includes('原创') && e.children.length < 3);
        if (label) { label.click(); return true; }
        return false;
    }""", retries=2)


async def main():
    parser = argparse.ArgumentParser(description="小红书安全发布 v2")
    parser.add_argument("images", nargs="+", help="图片路径")
    parser.add_argument("--title", required=True)
    parser.add_argument("--note", default="")
    parser.add_argument("--tags", default="", help="逗号分隔")
    parser.add_argument("--auto", action="store_true", help="自动发布（默认人工确认）")
    parser.add_argument("--ai-label", action="store_true", help="勾选 AI 生成标识")
    parser.add_argument("--no-label", action="store_true", help="不勾选 AI 标识（真人原创）")
    args = parser.parse_args()

    # 内容过滤
    if filter_content:
        res = filter_content(args.title, args.note, [t.strip() for t in args.tags.split(",") if t.strip()])
        if not res["safe"]:
            print(f"❌ 内容含违规词: {res.get('warnings', [])}")
            print("请修改后重试")
            return
        print("✅ 内容过滤通过")

    # 人工确认（默认）
    if not args.auto:
        print("\n📋 发布预览:")
        print(f"  标题: {args.title}")
        print(f"  正文: {args.note[:100]}{'...' if len(args.note) > 100 else ''}")
        print(f"  标签: {args.tags}")
        print(f"  图片: {len(args.images)} 张")
        print(f"  AI标识: {'勾选' if args.ai_label else '不勾选'}")
        print("\n⏸️ 人工确认模式——请确认内容无误后按 Enter 发布，Ctrl+C 取消")
        try:
            input()
        except (KeyboardInterrupt, EOFError):
            print("\n❌ 已取消")
            return

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, executable_path=config.find_chrome(), args=LAUNCH_ARGS)
        context = await browser.new_context(
            user_agent=MAC_UA, locale="zh-CN", timezone_id="Asia/Shanghai",
            viewport={"width": 1440, "height": 900}, device_scale_factor=2,
            storage_state=COOKIE,
        )
        await context.add_init_script(STEALTH_SCRIPT)
        page = await context.new_page()

        # 预热浏览
        print("👀 预热浏览...")
        await page.goto("https://www.xiaohongshu.com/explore", wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(random.uniform(5, 10))
        await page.mouse.wheel(0, random.randint(200, 600))
        await asyncio.sleep(random.uniform(1, 3))

        # 打开发布页
        print("🚀 打开发布页...")
        await page.goto(PUBLISH_URL, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(4)

        # 改版后：发布页先显示类型选择，需点击「上传图文」进入图文编辑界面
        try:
            upload_image_btn = page.locator('text=上传图文').first
            if await upload_image_btn.count() > 0:
                await upload_image_btn.click(timeout=10000)
                await asyncio.sleep(3)
                print("✅ 点击「上传图文」")
        except Exception as e:
            print(f"⚠️ 点击上传图文失败(继续尝试): {str(e)[:60]}")

        # 上传图片
        upload_input = page.locator('.upload-input, input[type="file"]').first
        await upload_input.wait_for(state="attached", timeout=30000)
        await upload_input.set_input_files(args.images)
        print(f"📤 上传 {len(args.images)} 张图片...")

        # 等待标题输入框
        title_input = page.locator('input[placeholder*="标题"], .title-input input, div.d-input input').first
        await title_input.wait_for(state="visible", timeout=60000)
        await asyncio.sleep(random.uniform(1, 2))

        # 填标题（拟人输入）
        print("✍️ 填写标题...")
        await human_type(page, args.title, selector='input[placeholder*="标题"], .title-input input, div.d-input input')

        # 填正文
        if args.note:
            print("✍️ 填写正文...")
            note_el = page.locator('div.ql-editor, [data-placeholder*="输入正文"], [contenteditable="true"]').first
            await note_el.click()
            await asyncio.sleep(random.uniform(0.5, 1.5))
            for ch in args.note:
                await page.keyboard.type(ch, delay=random.uniform(40, 120))
            await asyncio.sleep(random.uniform(0.5, 1.5))

        # 填标签
        if args.tags:
            print("🏷️ 填写标签...")
            for tag in [t.strip() for t in args.tags.split(",") if t.strip()]:
                tag_input = page.locator('input[placeholder*="话题"], input[placeholder*="输入话题"]').first
                if await tag_input.count():
                    await tag_input.click()
                    await asyncio.sleep(random.uniform(0.3, 0.8))
                    await human_type(page, tag)
                    await asyncio.sleep(random.uniform(0.5, 1.2))
                    try:
                        await page.keyboard.press("Enter")
                        await asyncio.sleep(random.uniform(0.5, 1.0))
                    except Exception:
                        pass

        # 原创声明
        print("🔒 勾选原创声明...")
        await check_original(page)

        # AI 标识
        if args.ai_label:
            print("🤖 勾选 AI 生成标识...")
            await check_ai_label(page)
        elif not args.no_label:
            print("🤖 检测并勾选 AI 标识（如页面有）...")
            await check_ai_label(page)

        # 截图预览
        await page.screenshot(path="/tmp/xhs_safe_publish_preview.png", full_page=False)
        print("📸 发布前预览: /tmp/xhs_safe_publish_preview.png")

        # 发布
        if args.auto:
            print("🚀 自动发布中...")
            await page.locator('button:has-text("发布")').click()
            try:
                await page.wait_for_url("**/publish/success**", timeout=10000)
                print("✅ 发布成功!")
            except Exception:
                print("⚠️ 等待成功页超时，可能发布成功或需人工确认")
        else:
            print("\n📋 发布页已就绪，请在浏览器中人工确认后点击「发布」")
            print("⏳ 等待人工操作（最长 5 分钟）...")
            try:
                await page.wait_for_url("**/publish/success**", timeout=300000)
                print("✅ 发布成功!")
            except Exception:
                print("⚠️ 等待超时，请检查浏览器状态")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
