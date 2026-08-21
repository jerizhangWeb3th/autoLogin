"""小红书卡片生成模块 — 整合 xiaohongshu-card-design skill 规范 + qiaomu 三风格

【字号铁律】小红书在手机端浏览，小字根本看不清（skill 硬规则）：
    主标题  ≥96px  |  副标题 48-56px  |  卡片标题 36-42px  |  正文 26-30px  |  标签 24-26px
    Golden rule: If in doubt, make it bigger. Tiny text = skipped post.

【四风格】（随机选，无需人工确认）：
    classic   米白杂志标准  #f5f3ed / #1a1a1a / #8b5e3c
    magazine  精致编辑     交替行背景 + 装饰引号 + 更紧凑 padding
    artistic  实验暗色     #0A0615 / #FFFFFF / #C77DFF，三字体混合
    morandi   莫兰迪柔和   #f5ece6 / #3d3a38 / #b08d8d，圆角卡片

用法：
    from platforms.xiaohongshu.cards import generate_cards
    paths = generate_cards(cards=[...], style="random", out_dir="/root/xhs_hermes_cards")
"""
import os
import random
from pathlib import Path

# ── 字体（项目自包含，见 assets/fonts/）──
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
FONT_KAI = str(_PROJECT_ROOT / "assets" / "fonts" / "TsangerJinKai02-W04.ttf")
FONT_NOTO = str(_PROJECT_ROOT / "assets" / "fonts" / "NotoSerifSC-Regular.ttf")

# ── 字号规范（skill 硬规则，已按用户反馈放大一档）──
FONT_SIZES = {
    "title": 128,      # 主标题（封面大字，短词）
    "subtitle": 64,    # 副标题
    "head": 52,        # 卡片标题
    "body": 38,        # 正文
    "tag": 42,         # 标签
}

# ── 三风格配色 ──
STYLES = {
    "classic": {
        "bg": "#f5f3ed", "text": "#1a1a1a", "accent": "#8b5e3c",
        "title_size": 120, "padding": "88px 76px",
    },
    "magazine": {
        "bg": "#f5f3ed", "text": "#1a1a1a", "accent": "#8b5e3c",
        "title_size": 120, "padding": "44px 42px",
    },
    "artistic": {
        "bg": "#0A0615", "text": "#FFFFFF", "accent": "#C77DFF",
        "title_size": 128, "padding": "88px 76px",
    },
    "morandi": {
        "bg": "#f5ece6", "text": "#3d3a38", "accent": "#b08d8d",
        "title_size": 120, "padding": "88px 76px",
    },
}


def pick_style(style: str = "random") -> str:
    """选择风格，random 时随机，否则校验并返回"""
    if style == "random":
        return random.choice(list(STYLES.keys()))
    if style not in STYLES:
        raise ValueError(f"未知风格: {style}，可选 {list(STYLES.keys())}")
    return style


def build_html(card: dict, idx: int, style: str) -> str:
    """生成单张卡片的 HTML"""
    st = STYLES[style]
    bg, text, accent = st["bg"], st["text"], st["accent"]
    title_size = st["title_size"]
    head_size, body_size = FONT_SIZES["head"], FONT_SIZES["body"]
    subtitle_size, tag_size = FONT_SIZES["subtitle"], FONT_SIZES["tag"]

    # 封面卡
    if card.get("type") == "cover":
        body = f'''
        <div class="cover">
          <div class="tag">{card.get("tag", "")}</div>
          <div class="title">{card.get("title", "")}</div>
          <div class="subtitle">{card.get("subtitle", "")}</div>
        </div>'''
    # 列表卡（一个核心观点/功能点列表）
    else:
        items_html = ""
        for i, item in enumerate(card.get("items", [])):
            # magazine 交替行背景 + morandi 圆角卡片
            alt = ""
            if style == "magazine" and i % 2 == 1:
                alt = " style='background:rgba(0,0,0,0.035);border-radius:12px;padding:24px 16px;'"
            elif style == "morandi":
                alt = " style='background:rgba(176,141,141,0.12);border-radius:16px;padding:24px 20px;margin-bottom:16px;'"
            items_html += f'<div class="item"{alt}>{item}</div>'
        body = f'''
        <div class="list-card">
          <div class="head">{card.get("title", "")}</div>
          {items_html}
        </div>'''

    # 各风格特殊背景
    bg_css = bg
    if style == "artistic":
        bg_css = f"linear-gradient(160deg, {bg} 0%, #160d2e 100%)"
    elif style == "morandi":
        bg_css = f"linear-gradient(160deg, {bg} 0%, #e8dcd2 100%)"
    item_border = "1px solid rgba(199,125,255,0.18)" if style == "artistic" else "1px solid rgba(0,0,0,0.08)"

    return f'''<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
@font-face {{ font-family:'Kai'; src:url('file://{FONT_KAI}'); }}
@font-face {{ font-family:'Noto'; src:url('file://{FONT_NOTO}'); }}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ width:1080px; height:1440px; background:{bg_css}; color:{text};
       font-family:'Noto'; display:flex; align-items:center; justify-content:center; }}
.card {{ width:1080px; height:1440px; padding:{st["padding"]}; display:flex; flex-direction:column; }}
.cover {{ flex:1; display:flex; flex-direction:column; justify-content:center; }}
.tag {{ font-family:'Kai'; font-size:{tag_size}px; color:{accent}; margin-bottom:40px; }}
.title {{ font-family:'Kai'; font-size:{title_size}px; font-weight:bold; line-height:1.15; margin-bottom:36px; }}
.subtitle {{ font-family:'Noto'; font-size:{subtitle_size}px; line-height:1.5; opacity:0.85; }}
.list-card {{ flex:1; display:flex; flex-direction:column; justify-content:center; }}
.head {{ font-family:'Kai'; font-size:{head_size}px; font-weight:bold; color:{accent}; margin-bottom:52px; }}
.item {{ font-family:'Noto'; font-size:{body_size}px; line-height:1.6;
        padding:30px 0; border-bottom:{item_border}; }}
</style></head><body><div class="card">{body}</div></body></html>'''


def generate_cards(cards: list, style: str = "random", out_dir: str = "/root/xhs_hermes_cards") -> list:
    """生成一组卡片 PNG，返回文件路径列表。

    cards 格式:
        [{"type": "cover", "title": "...", "subtitle": "...", "tag": "..."},
         {"type": "list", "title": "核心能力", "items": ["...", "..."]}]
    """
    from playwright.sync_api import sync_playwright

    chosen_style = pick_style(style)
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    print(f"风格: {chosen_style}")

    paths = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, channel="chrome")
        for i, card in enumerate(cards):
            html = build_html(card, i, chosen_style)
            hp = out_path / f"card_{i}.html"
            hp.write_text(html, encoding="utf-8")
            page = browser.new_page(viewport={"width": 1080, "height": 1440}, device_scale_factor=1)
            page.goto(f"file://{hp}")
            page.wait_for_timeout(2500)
            out = out_path / f"card_{i}.png"
            page.screenshot(path=str(out), full_page=False)
            paths.append(str(out))
            print(f"✅ {out} ({out.stat().st_size // 1024}KB)")
            page.close()
        browser.close()
    return paths


if __name__ == "__main__":
    # 示例：Hermes Agent 卡片
    demo = [
        {"type": "cover", "title": "Hermes Agent", "subtitle": "别再手动操作了！这个 AI 智能体帮你全自动搞定", "tag": "AI 智能体 · 效率神器"},
        {"type": "list", "title": "核心能力", "items": ["智能理解你的真实意图", "自动执行复杂任务，全程不打断", "持久记忆，越用越懂你的习惯"]},
        {"type": "list", "title": "技能系统", "items": ["技能无限扩展，能力随装随用", "Claude Code / Cursor / Codex 都能接", "多平台自动化运营一键搞定"]},
        {"type": "list", "title": "为什么值得用", "items": ["写代码 · 查资料 · 自动化全包", "一旦用上，真的回不去了", "关注我，每天一个 AI 神器"]},
    ]
    generate_cards(demo, style="random")
