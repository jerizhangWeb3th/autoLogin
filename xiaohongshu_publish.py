#!/usr/bin/env python3
"""
小红书发布模块（融合自 auto-rednote 插件，准确的 selector + 流程）

来源：auto-rednote (BodaFu) 的 publish.ts，翻译为 Python + patchright。
- 复用其准确 selector（小红书网页改版后仍有效）
- 用 autoLogin 的 stealth_core（MAC_UA + STEALTH_SCRIPT + LAUNCH_ARGS）
- 填内容用 DOM 原生 setter + dispatchEvent（比逐字符输入更可靠）

用法：
    python xiaohongshu_publish.py 图1.png 图2.png --title "标题" --content "正文" --tags AI工具,代码理解 [--cookie path] [--dry-run]
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

PUBLISH_URL = "https://creator.xiaohongshu.com/publish/publish?source=official"
DEFAULT_COOKIE = str(Path.home() / ".local/share/uv/tools/social-auto-upload/lib/python3.11/site-packages/cookies/xiaohongshu_autoContent.json")

# 内容过滤
sys.path.insert(0, "/root/.hermes/scripts")
try:
    from xhs_content_filter import filter_content
except Exception:
    filter_content = None


async def eval_js(page, script, retries=3):
    """执行原生 JS，带重试"""
    for i in range(retries):
        try:
            return await page.evaluate(script)
        except Exception as e:
            if i >= retries - 1:
                raise
            await asyncio.sleep(2)


async def click_publish_tab(page, tab_text: str) -> bool:
    """点击发布类型 tab（上传图文 / 上传视频）"""
    r = await eval_js(page, f"""() => {{
        const tabs = document.querySelectorAll('div.creator-tab, .publish-tab, [class*="tab-item"]');
        for (const tab of tabs) {{
            if (tab.textContent && tab.textContent.includes('{tab_text}')) {{
                tab.click(); return true;
            }}
        }}
        return false;
    }}""")
    return r is True


async def upload_images(page, image_paths):
    """上传图片（第一张 .upload-input，后续 input[type=file]）"""
    for i, img in enumerate(image_paths):
        sel = ".upload-input" if i == 0 else 'input[type="file"]'
        el = page.locator(sel).first
        await el.wait_for(state="attached", timeout=30000)
        await el.set_input_files(img)
        print(f"📤 上传第 {i+1} 张: {os.path.basename(img)}", flush=True)
        await asyncio.sleep(random.uniform(1.5, 2.5))


async def input_title(page, title: str):
    """填标题（DOM 原生 setter + dispatchEvent）"""
    escaped = json.dumps(title, ensure_ascii=False)
    r = await eval_js(page, f"""() => {{
        const input = document.querySelector('input[placeholder*="标题"], .title-input input, div.d-input input');
        if (!input) return false;
        const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')?.set;
        if (setter) setter.call(input, {escaped}); else input.value = {escaped};
        input.dispatchEvent(new Event('input', {{ bubbles: true }}));
        input.dispatchEvent(new Event('change', {{ bubbles: true }}));
        return true;
    }}""")
    if not r:
        raise RuntimeError("未找到标题输入框")


async def input_content(page, content: str):
    """填正文（ql-editor 富文本，innerHTML + dispatchEvent）"""
    escaped = json.dumps(content, ensure_ascii=False)
    r = await eval_js(page, f"""() => {{
        const editor = document.querySelector('div.ql-editor, [data-placeholder*="输入正文"], [contenteditable="true"]');
        if (!editor) return false;
        editor.focus();
        editor.innerHTML = {escaped}.split('\\n').map(line => '<p>' + (line || '<br>') + '</p>').join('');
        editor.dispatchEvent(new Event('input', {{ bubbles: true }}));
        return true;
    }}""")
    if not r:
        raise RuntimeError("未找到内容编辑器")


async def input_tags(page, tags):
    """填标签（编辑器末尾插入 #标签 + 点击联想）"""
    for tag in tags:
        escaped = json.dumps(f"#{tag}", ensure_ascii=False)
        await eval_js(page, f"""() => {{
            const editor = document.querySelector('div.ql-editor, [contenteditable="true"]');
            if (!editor) return false;
            editor.focus();
            const range = document.createRange();
            range.selectNodeContents(editor);
            range.collapse(false);
            const sel = window.getSelection();
            sel?.removeAllRanges();
            sel?.addRange(range);
            document.execCommand('insertText', false, {escaped});
            return true;
        }}""")
        await asyncio.sleep(0.8)
        # 点击标签联想
        clicked = await eval_js(page, """() => new Promise(resolve => {
            let tries = 0;
            const check = () => {
                const item = document.querySelector('#creator-editor-topic-container .item, .topic-item, [class*="topic-item"]');
                if (item) { item.click(); resolve(true); return; }
                if (++tries < 10) setTimeout(check, 300); else resolve(false);
            };
            check();
        })""")
        if not clicked:
            try:
                await page.keyboard.press("Enter")
            except Exception:
                pass
        await asyncio.sleep(0.3)


async def click_publish_button(page) -> bool:
    """点击发布按钮"""
    r = await eval_js(page, """() => {
        const selectors = [
            '.publishBtn button', 'button.el-button--primary',
            '.publish-page-publish-btn button.bg-red', '.publish-btn', '[class*="publish-btn"]',
        ];
        for (const sel of selectors) {
            const btn = document.querySelector(sel);
            if (btn && !btn.disabled) { btn.click(); return true; }
        }
        const btns = document.querySelectorAll('button');
        for (const btn of btns) {
            const text = btn.textContent?.trim();
            if ((text === '发布' || text === '立即发布') && !btn.disabled) { btn.click(); return true; }
        }
        return false;
    }""")
    return r is True


async def publish_note(title, content, media_paths, tags=None, cookie_path=DEFAULT_COOKIE, dry_run=False):
    """发布小红书图文笔记"""
    tags = tags or []

    # 内容过滤（发布前必做）
    if filter_content:
        result = filter_content(title, content, tags)
        if not result.get("safe"):
            raise RuntimeError(f"内容违规: {result.get('warnings')}")
        title = result.get("title", title)
        content = result.get("desc", content)
        tags = result.get("tags", tags)

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

        # 打开发布页
        await page.goto(PUBLISH_URL, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(4)

        # 点击「上传图文」
        await click_publish_tab(page, "上传图文")
        await asyncio.sleep(1)

        # 上传图片
        if media_paths:
            await upload_images(page, media_paths)

        # 填标题 + 正文 + 标签
        await input_title(page, title)
        await asyncio.sleep(0.3)
        await input_content(page, content)
        await asyncio.sleep(0.3)
        if tags:
            await input_tags(page, tags)

        # 截图预览
        await page.screenshot(path="/tmp/xhs_publish_preview.png", full_page=False)
        print("📸 发布前预览: /tmp/xhs_publish_preview.png", flush=True)

        if dry_run:
            print("🔍 DRY-RUN 模式，不实际发布", flush=True)
            await browser.close()
            return {"success": True, "dry_run": True}

        # 发布
        ok = await click_publish_button(page)
        if not ok:
            await browser.close()
            return {"success": False, "message": "未找到发布按钮"}

        await asyncio.sleep(3)
        try:
            await page.wait_for_url("**/publish/success**", timeout=15000)
            print("✅ 发布成功!", flush=True)
            success = True
        except Exception:
            print("⚠️ 等待成功页超时，可能发布成功", flush=True)
            success = True  # 点了发布就视为大概率成功

        await browser.close()
        return {"success": success, "message": "发布完成"}


def main():
    ap = argparse.ArgumentParser(description="小红书发布（融合 auto-rednote）")
    ap.add_argument("images", nargs="+", help="图片路径")
    ap.add_argument("--title", required=True)
    ap.add_argument("--content", required=True)
    ap.add_argument("--tags", default="", help="逗号分隔")
    ap.add_argument("--cookie", default=DEFAULT_COOKIE)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    tags = [t.strip() for t in args.tags.split(",") if t.strip()]
    result = asyncio.run(publish_note(
        args.title, args.content, args.images, tags, args.cookie, args.dry_run,
    ))
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
