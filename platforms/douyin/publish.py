"""抖音图文发布 v1 — patchright + 真 Chrome + 伪装浏览器（用户要求）

与 sau 默认（channel="chromium" 自带内核）不同：
- 用 patchright 驱动真 Chrome（环境自洽，指纹真实）
- 持久化 profile /root/.douyin-profile（登录态复用）
- 隐藏自动化痕迹（webdriver/CDP 变量），不伪造 UA/指纹

流程（参照 sau DouYinNote 已验证逻辑）：
1. 打开 creator.douyin.com/creator-micro/content/upload
2. 点「发布图文」→ 上传图片
3. 填标题（≤20字）+ 正文（≤1000字）+ 话题
4. 点「发布」→ 跳转 manage 页 = 成功
"""
import asyncio, json, os, sys, time
from pathlib import Path

sys.path.insert(0, str(Path.home() / ".local/share/uv/tools/patchright/lib/python3.11/site-packages"))
os.environ["DISPLAY"] = ":99"

from patchright.async_api import async_playwright

PROFILE = "/root/.douyin-profile"
STEALTH = "/root/.local/share/uv/tools/social-auto-upload/lib/python3.11/site-packages/utils/stealth.min.js"

STEALTH_EXTRA = """
    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
    delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
    delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
    delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;
"""


async def apply_stealth(context):
    if os.path.exists(STEALTH):
        await context.add_init_script(path=STEALTH)
    await context.add_init_script(STEALTH_EXTRA)
    return context


async def main():
    title = os.environ.get("DOUYIN_TITLE", "")
    note = os.environ.get("DOUYIN_NOTE", "")
    tags = [t for t in os.environ.get("DOUYIN_TAGS", "").split(",") if t]
    images = [p for p in os.environ.get("DOUYIN_IMAGES", "").split(",") if p]

    if not title or not images:
        print("❌ 需要 DOUYIN_TITLE 和 DOUYIN_IMAGES")
        return

    if len(title) > 20:
        print(f"❌ 标题超长: {len(title)}>20 字符")
        return
    if len(note) > 1000:
        print(f"❌ 正文超长: {len(note)}>1000 字符")
        return

    for img in images:
        if not os.path.exists(img):
            print(f"❌ 图片不存在: {img}")
            return

    print(f"=== 抖音图文发布 v1 (patchright+真Chrome) [ {time.strftime('%H:%M:%S')} ] ===")
    print(f"标题: {title} | 图片: {len(images)} 张 | 话题: {tags}")

    async with async_playwright() as pw:
        context = await pw.chromium.launch_persistent_context(
            user_data_dir=PROFILE,
            channel="chrome",
            headless=False,
            viewport={"width": 1440, "height": 900},
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        )
        # 完整伪装：patchright + stealth.min.js
        await apply_stealth(context)
        page = context.pages[0] if context.pages else await context.new_page()

        # 1. 打开发布页
        print("🚀 打开抖音发布页...")
        await page.goto("https://creator.douyin.com/creator-micro/content/upload", wait_until="domcontentloaded", timeout=90000)
        await asyncio.sleep(4)

        # 检查是否登录
        if "creator-micro" not in page.url:
            print("❌ 未登录（页面跳转到登录），请先扫码登录")
            return

        # 2. 点「发布图文」
        print("🔀 切换到图文发布...")
        try:
            await page.get_by_text("发布图文", exact=True).click(timeout=10000)
        except Exception as e:
            print(f"⚠️ 点发布图文失败: {str(e)[:60]}，尝试直接找上传框")
        await asyncio.sleep(2)

        # 3. 上传图片
        print(f"📤 上传 {len(images)} 张图片...")
        try:
            file_input = page.locator("div[class^='container'] input[accept*='image'], input[type='file']").first
            await file_input.set_input_files(images, timeout=20000)
            print("✅ 图片已选择")
        except Exception as e:
            print(f"❌ 上传失败: {str(e)[:100]}")
            return

        # 4. 等待进入图文发布页
        await asyncio.sleep(3)
        print("✍️ 填写标题、正文、话题...")

        # 标题
        try:
            title_input = page.locator("input[placeholder*='标题'], input[placeholder*='填写']").first
            await title_input.click()
            await title_input.fill(title)
            print(f"✅ 标题已填: {title}")
        except Exception as e:
            print(f"⚠️ 填标题失败: {str(e)[:60]}")

        # 正文 + 话题
        try:
            desc_input = page.locator("div[contenteditable='true'], textarea").first
            await desc_input.click()
            text = note
            if tags:
                text += " " + " ".join(f"#{t}" for t in tags)
            await desc_input.fill(text)
            print(f"✅ 正文+话题已填 ({len(text)} 字)")
        except Exception as e:
            print(f"⚠️ 填正文失败: {str(e)[:60]}")

        await asyncio.sleep(2)

        # 5. 截图确认
        await page.screenshot(path="/tmp/douyin_note_preview.png", full_page=False)
        print("📸 预览截图: /tmp/douyin_note_preview.png")

        # 6. 点发布
        print("🚀 点击发布...")
        try:
            pub = page.get_by_role("button", name="发布", exact=True)
            if await pub.count():
                await pub.click(timeout=5000)
                print("✅ 已点击发布")
                # 等待跳转 manage 页
                for _ in range(30):
                    await asyncio.sleep(1)
                    if "manage" in page.url:
                        print("🎉 图文发布成功! URL=", page.url[:60])
                        return
                print("⚠️ 未检测到跳转 manage，可能发布中或需要确认")
            else:
                print("❌ 未找到发布按钮")
        except Exception as e:
            print(f"❌ 发布失败: {str(e)[:100]}")

        await page.screenshot(path="/tmp/douyin_note_after_publish.png")
        print("📸 发布后截图: /tmp/douyin_note_after_publish.png")


if __name__ == "__main__":
    asyncio.run(main())
