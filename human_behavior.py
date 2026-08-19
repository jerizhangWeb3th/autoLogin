"""Human Behavior 模块 — 模拟真人操作行为，降低风控检测风险

参考：
- yousali.com 小红书发布反检测实战（7 坑）
- xiaohongshu-mcp issue #674 反检测方案

核心原则：行为层用随机性（不是固定 sleep），指纹层用底层 patch（不是注入脚本）。
"""
import random
import asyncio
import time

# ============ 延迟随机化 ============

async def human_delay(min_s=0.8, max_s=3.0):
    """随机延迟（钟形分布，中间值概率高，避免固定间隔）"""
    # 用两次均匀分布取平均得到近似钟形分布
    d = (random.uniform(min_s, max_s) + random.uniform(min_s, max_s)) / 2
    await asyncio.sleep(d)


async def page_load_delay():
    """页面加载后随机等待（6-14s，模拟真人阅读/感知）"""
    await asyncio.sleep(random.uniform(6, 14))


async def thinking_gap():
    """打字前的"思考停顿"（1-3s）"""
    await asyncio.sleep(random.uniform(1.0, 3.0))


async def between_actions():
    """操作间随机间隔（0.8-2.5s）"""
    await asyncio.sleep(random.uniform(0.8, 2.5))


# ============ 打字节奏 ============

async def human_type(page, selector, text, click_first=True):
    """逐字符模拟真人打字（50-150ms/字符，标点停顿更长）"""
    if click_first:
        try:
            await page.click(selector)
            await between_actions()
        except Exception:
            pass

    # 逐字符输入，模拟真人打字
    for i, ch in enumerate(text):
        await page.keyboard.type(ch, delay=random.uniform(40, 120))
        # 标点/空格处停顿更长
        if ch in "，。！？、；：,.!?;:":
            await asyncio.sleep(random.uniform(0.3, 0.8))
        elif ch == " ":
            await asyncio.sleep(random.uniform(0.2, 0.5))
        # 偶发"思考停顿"
        if i > 8 and random.random() < 0.08:
            await asyncio.sleep(random.uniform(1.0, 2.5))


async def human_type_into(page, comment):
    """在 contenteditable 输入框逐字符输入评论"""
    input_ok = await page.evaluate("""() => {
        const input = document.querySelector('[contenteditable="true"]');
        if (!input) { return false; }
        input.click();
        input.focus();
        return true;
    }""")
    if input_ok is not True:
        return False
    await thinking_gap()

    # 逐字符输入
    for ch in comment:
        await page.keyboard.type(ch, delay=random.uniform(45, 130))
        if ch in "，。！？、；：,.!?;:":
            await asyncio.sleep(random.uniform(0.3, 0.7))
        elif ch == " ":
            await asyncio.sleep(random.uniform(0.2, 0.4))
    return True


# ============ 点击随机化 ============

async def human_click(page, selector, fallback_text=None):
    """点击元素内的随机偏移点（±5px），模拟人手不精确性"""
    try:
        box = await page.locator(selector).bounding_box()
        if box:
            x = box["x"] + box["width"] * random.uniform(0.3, 0.7)
            y = box["y"] + box["height"] * random.uniform(0.3, 0.7)
            # 鼠标先移动到附近（模拟移动轨迹）
            await page.mouse.move(
                x + random.uniform(-30, 30),
                y + random.uniform(-15, 15),
                steps=random.randint(5, 12),
            )
            await asyncio.sleep(random.uniform(0.2, 0.6))
            await page.mouse.move(x, y, steps=random.randint(3, 8))
            await asyncio.sleep(random.uniform(0.1, 0.3))
            await page.mouse.click(x, y)
            return True
    except Exception:
        pass

    # fallback：JS 点击
    try:
        if fallback_text:
            await page.evaluate(f"""() => {{
                const btns = document.querySelectorAll('{selector}');
                for (const b of btns) {{
                    const t = (b.innerText || '').trim();
                    if (t.includes('{fallback_text}')) {{ b.click(); return true; }}
                }}
                return false;
            }}""")
        else:
            await page.click(selector)
        return True
    except Exception:
        return False


# ============ 预热浏览（打破"登录→秒操作→退出"机械形状） ============

async def warmup_browse(page, url="https://www.xiaohongshu.com", min_scrolls=2, max_scrolls=4):
    """发布/评论前预热：随机浏览推荐流，滚动几屏"""
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await page_load_delay()

        # 随机滚动几屏（分段滚动，模拟手指滑动）
        scrolls = random.randint(min_scrolls, max_scrolls)
        for _ in range(scrolls):
            # 分段滚动
            total = random.randint(300, 700)
            steps = random.randint(3, 6)
            for _ in range(steps):
                await page.mouse.wheel(0, total // steps + random.randint(-40, 40))
                await asyncio.sleep(random.uniform(0.3, 0.9))
            await asyncio.sleep(random.uniform(1.0, 2.5))

        # 随机鼠标移动（无目的移动）
        for _ in range(random.randint(2, 4)):
            await page.mouse.move(
                random.randint(200, 1200),
                random.randint(150, 700),
                steps=random.randint(8, 20),
            )
            await asyncio.sleep(random.uniform(0.4, 1.2))

        return True
    except Exception as e:
        print(f"  预热浏览跳过: {str(e)[:60]}")
        return False


# ============ 会话节奏 ============

async def random_comment_interval(min_s=40, max_s=90):
    """评论间随机间隔（40-90s 钟形分布），返回等待秒数"""
    d = (random.uniform(min_s, max_s) + random.uniform(min_s, max_s)) / 2
    return d


def random_publish_time_window(hour_min, hour_max):
    """在小时窗口内随机选一个执行时间（避免固定整点）"""
    from datetime import datetime, timedelta
    now = datetime.now()
    start = now.replace(hour=hour_min, minute=0, second=0, microsecond=0)
    end = now.replace(hour=hour_max, minute=59, second=59, microsecond=0)
    if end < start:
        end += timedelta(days=1)
    target = start + timedelta(seconds=random.randint(0, int((end - start).total_seconds())))
    return target
