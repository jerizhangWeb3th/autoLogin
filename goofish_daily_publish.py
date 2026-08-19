"""闲鱼每日自动发布 — Hermes/OpenClaw 运营 + 大模型安装 + 可上门

按星期几轮换主题内容（每天不同，避免重复铺货），自动生成服务卡片图。
复用 goofish_publish.py 的发布逻辑。

运行: python3 goofish_daily_publish.py
"""
import sys
import os
import json
import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# 每日轮换内容（星期几 → 主题）
DAILY_CONTENT = {
    0: {  # 周一：Hermes Agent 基础
        "title": "Hermes Agent AI智能体 部署安装运维指导",
        "desc": (
            "【Hermes Agent 开源 AI 智能体】部署安装与运维指导服务。\n\n"
            "服务内容：\n"
            "1️⃣ Hermes Agent 环境搭建与配置\n"
            "2️⃣ 大模型接入（OpenAI/DeepSeek/本地模型）\n"
            "3️⃣ 常用功能演示与使用指导\n"
            "4️⃣ 后续使用问题咨询\n\n"
            "支持上门服务（同城）或远程协助，全国可发。\n"
            "拍前先沟通需求，确认后再拍。"
        ),
    },
    1: {  # 周二：OpenClaw
        "title": "OpenClaw 开源智能体 部署安装运维指导",
        "desc": (
            "【OpenClaw 开源个人 AI 助手】部署安装与运维指导服务。\n\n"
            "服务内容：\n"
            "1️⃣ OpenClaw 安装与环境配置\n"
            "2️⃣ 平台接入（微信/Telegram/Discord 等）\n"
            "3️⃣ 插件与技能扩展指导\n"
            "4️⃣ 使用中遇到的问题排查\n\n"
            "支持上门服务（同城）或远程协助，全国可发。\n"
            "拍前先沟通需求，确认后再拍。"
        ),
    },
    2: {  # 周三：大模型安装
        "title": "大模型本地部署安装 一键跑通（DeepSeek/Qwen等）",
        "desc": (
            "【本地大模型安装部署】服务——在自己电脑上跑通 AI 大模型。\n\n"
            "服务内容：\n"
            "1️⃣ Ollama/LM Studio 等工具安装\n"
            "2️⃣ DeepSeek、Qwen、Llama 等模型下载部署\n"
            "3️⃣ 本地 API 调用配置（兼容 OpenAI 接口）\n"
            "4️⃣ 常见问题排查\n\n"
            "支持上门服务（同城）或远程协助，全国可发。\n"
            "拍前先沟通电脑配置，确认后再拍。"
        ),
    },
    3: {  # 周四：AI Agent 运营
        "title": "AI Agent 自动化运营搭建 社交媒体自动发文",
        "desc": (
            "【AI Agent 自动化运营】搭建服务——社交媒体自动发文、自动回复。\n\n"
            "服务内容：\n"
            "1️⃣ 社交平台自动发文配置\n"
            "2️⃣ 定时发布任务设置\n"
            "3️⃣ 内容自动生成流程搭建\n"
            "4️⃣ 运营流程优化建议\n\n"
            "支持上门服务（同城）或远程协助，全国可发。\n"
            "拍前先沟通平台和需求，确认后再拍。"
        ),
    },
    4: {  # 周五：Hermes 进阶
        "title": "Hermes Agent 进阶配置 多平台接入与技能扩展",
        "desc": (
            "【Hermes Agent 进阶配置】多平台接入与技能扩展指导。\n\n"
            "服务内容：\n"
            "1️⃣ 多平台接入（微信/飞书/Telegram）\n"
            "2️⃣ 技能（Skill）安装与编写\n"
            "3️⃣ 定时任务（Cron）配置\n"
            "4️⃣ 记忆与知识库管理\n\n"
            "支持上门服务（同城）或远程协助，全国可发。\n"
            "拍前先沟通需求，确认后再拍。"
        ),
    },
    5: {  # 周六：OpenClaw 进阶
        "title": "OpenClaw 进阶配置 插件开发与多账号管理",
        "desc": (
            "【OpenClaw 进阶配置】插件开发与多账号管理指导。\n\n"
            "服务内容：\n"
            "1️⃣ 插件（Plugin）开发指导\n"
            "2️⃣ 多账号多实例管理\n"
            "3️⃣ 自动化流程编排\n"
            "4️⃣ 部署优化建议\n\n"
            "支持上门服务（同城）或远程协助，全国可发。\n"
            "拍前先沟通需求，确认后再拍。"
        ),
    },
    6: {  # 周日：综合服务
        "title": "AI 智能体全套部署 安装运维一条龙服务",
        "desc": (
            "【AI 智能体全套部署】一条龙服务——从零搭建你的 AI 助手。\n\n"
            "服务内容：\n"
            "1️⃣ 环境评估与方案设计\n"
            "2️⃣ Hermes Agent / OpenClaw 安装部署\n"
            "3️⃣ 大模型接入与本地模型配置\n"
            "4️⃣ 平台接入与自动化流程搭建\n"
            "5️⃣ 长期使用咨询支持\n\n"
            "支持上门服务（同城）或远程协助，全国可发。\n"
            "拍前先沟通需求，确认后再拍。"
        ),
    },
}

# 价格
PRICE = 49.9


def make_card_image(day: int, title: str) -> str:
    """生成服务卡片图（竖版 1086x1448，深色科技风）"""
    import subprocess
    import tempfile

    out_dir = Path("/tmp/goofish_daily")
    out_dir.mkdir(exist_ok=True)

    weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    weekday = weekday_names[day]

    # 简单用 PIL 生成卡片（闲鱼首图）
    html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=600">
<style>
@font-face {{
  font-family: 'TsangerJinKai';
  src: url('file:///tmp/qiaomu-info-card-designer/assets/TsangerJinKai02-W04.ttf') format('truetype');
}}
@font-face {{
  font-family: 'NotoSerifSC';
  src: url('file:///tmp/qiaomu-info-card-designer/assets/NotoSerifSC-Regular.ttf') format('truetype');
}}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ background:#0a0c1a; }}
.card {{
  width: 600px; min-height: 800px; padding: 40px;
  background: linear-gradient(160deg, #0a0c1a 0%, #141832 60%, #1a1f3d 100%);
  display: flex; flex-direction: column; justify-content: center; gap: 24px;
  position: relative; overflow: hidden;
}}
.badge {{
  display: inline-block; padding: 8px 18px; border-radius: 100px;
  background: rgba(99,102,241,0.15); border: 1px solid rgba(99,102,241,0.4);
  color: #818cf8; font-family: 'TsangerJinKai'; font-size: 22px; letter-spacing: 0.1em;
}}
.title {{
  font-family: 'TsangerJinKai'; font-size: 48px; line-height: 1.3;
  color: #fff; font-weight: normal;
}}
.sub {{
  font-family: 'NotoSerifSC'; font-size: 24px; line-height: 1.6; color: #a5b4fc;
}}
.divider {{ height: 2px; background: linear-gradient(90deg, #818cf8, transparent); }}
.footer {{
  font-family: 'NotoSerifSC'; font-size: 20px; color: #64748b;
  display: flex; justify-content: space-between; margin-top: 8px;
}}
</style></head><body>
<div class="card">
  <div><span class="badge">AI 部署服务</span></div>
  <div class="title">{title.split(" ")[0]}<br>{title.split(" ")[1] if len(title.split(" ")) > 1 else ""}</div>
  <div class="divider"></div>
  <div class="sub">• 部署安装指导<br>• 大模型接入配置<br>• 问题排查支持<br>• 支持上门 / 远程</div>
  <div class="footer"><span>可上门 · 全国包邮</span><span>¥49.9</span></div>
</div>
</body></html>"""

    html_path = out_dir / f"card_{day}.html"
    html_path.write_text(html)
    img_path = out_dir / f"card_{day}.png"

    # 用 playwright 截图
    venv_py = "/root/.hermes/hermes-agent/venv/bin/python"
    script = f'''
import sys
sys.path.insert(0, "/root/.hermes/hermes-agent/venv/lib/python3.11/site-packages")
import os
os.environ.setdefault("DISPLAY", ":99")
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(headless=True, args=["--no-sandbox"])
    pg = b.new_page(viewport={{"width": 600, "height": 900}}, device_scale_factor=2)
    pg.goto("file://{html_path}")
    pg.wait_for_timeout(2000)
    pg.screenshot(path="{img_path}", full_page=True)
    b.close()
print("ok")
'''
    subprocess.run([venv_py, "-c", script], check=True, timeout=90)

    # 转成 1086 宽
    from PIL import Image
    im = Image.open(img_path)
    w, h = im.size
    nw = 1086
    nh = int(h * nw / w)
    im = im.resize((nw, nh), Image.LANCZOS)
    im.save(img_path)
    return str(img_path)


def main() -> None:
    # 按当天星期取内容
    day = datetime.datetime.now().weekday()
    content = DAILY_CONTENT[day]
    utils_log = lambda msg: print(msg)  # noqa: E731

    utils_log(f"📅 {datetime.datetime.now():%Y-%m-%d %H:%M} 周{'一二三四五六日'[day]}")
    utils_log(f"📌 标题: {content['title']}")

    # 生成卡片图
    utils_log("🎨 生成服务卡片...")
    card_img = make_card_image(day, content["title"])
    utils_log(f"  卡片: {card_img}")

    # 用 goofish_publish 发布
    sys.argv = ["goofish_publish.py", "--title", content["title"], "--desc", content["desc"], "--price", str(PRICE), card_img]
    # 注意：必须在独立 globals 中 exec，否则 goofish_publish.py 内部的
    # import（argparse 等）绑定到本函数局部命名空间，其 main() 无法解析 → NameError
    _pub_path = Path(__file__).parent / "goofish_publish.py"
    _code = compile(_pub_path.read_text(encoding="utf-8"), str(_pub_path), "exec")
    exec(_code, {"__name__": "__main__", "__file__": str(_pub_path)})


if __name__ == "__main__":
    main()
