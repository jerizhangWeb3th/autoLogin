"""闲鱼发布 — 完整流程（登录态检查 → 上传 → 发布）。

修复历史（2026-08-06）:
  之前发布失败原因：**登录会话过期**（FAIL_SYS_SESSION_EXPIRED），cookie 存在
  但服务端已失效，导致上传接口返回 punish (rgv587_flag: sm)。**不是 IP 风控，
  也不是 appkey 问题**（登录后 xy_chat/fleamarket 均正常上传）。

  修复流程：
    1. 检查登录态（主页是否显示用户名 / mtop 登录接口）
    2. 若过期 → 扫码重新登录（goofish_login.py）
    3. 上传图片（goofish-cli upload，登录后正常）
    4. 发布商品（goofish-cli mtop 签名流程）

运行: python3 goofish_publish.py [--title "xxx"] [--desc "xxx"] [--price 49.9] [图片...]
"""
import sys, os, json, argparse, random
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

SITE_PKG = Path.home() / ".local/share/uv/tools/goofish-cli/lib/python3.11/site-packages"
if str(SITE_PKG) not in sys.path:
    sys.path.insert(0, str(SITE_PKG))

os.environ["GOOFISH_HEADLESS"] = "1"
os.environ["GOOFISH_AUTO_REFRESH_TOKEN"] = "1"

import config
import utils
from goofish_cli.commands.item.publish import _build_publish_data
from goofish_cli.commands.media.upload import upload
from goofish_cli.commands.location.default import default as get_location
from goofish_cli.core import Session
from goofish_cli.core.guard import watch
from goofish_cli.core.mtop import call

DEFAULT_IMAGES = [
    "/tmp/xhs_v3/cover.jpg",
    "/tmp/xhs_v3/features.jpg",
    "/tmp/xhs_v3/tips.jpg",
    "/tmp/xhs_v3/workflow.jpg",
]


def check_login() -> bool:
    """检查登录态：cookie 是否有 unb/tracknick/sgcookie。"""
    session = Session.load()
    ok = bool(session.tracknick)
    utils.log(f"登录态: {'✅ ' + session.tracknick if ok else '❌ 未登录'}")
    return ok


def publish(title: str, desc: str, price: float, images: list[str], cat: dict | None = None) -> str:
    """上传图片 + 发布商品，返回 item_id。"""
    # 1. 上传图片（全部）
    image_infos = []
    for img in images:
        if not os.path.exists(img):
            utils.log(f"⚠️ 图片不存在: {img}")
            continue
        utils.log(f"📤 上传 {os.path.basename(img)}...")
        result = upload(img)
        if isinstance(result, dict) and result.get("url"):
            image_infos.append(result)
            utils.log(f"  ✅ {result['url'][:60]}")
        else:
            utils.log(f"  ❌ 上传失败: {result}")
    if not image_infos:
        raise RuntimeError("没有图片上传成功")

    # 2. 位置
    loc = get_location() or {"division_id": ""}

    # 3. 构建发布数据
    cat_info = cat or {
        "cat_id": "50023914",
        "cat_name": "AI模型训练",
        "channel_cat_id": "202038701",
        "tb_cat_id": "",
    }
    data = _build_publish_data(
        title=title,
        desc=desc,
        image_infos=image_infos,
        price=price,
        delivery="快递",
        post_price=0,
        can_self_pickup=True,
        cat_info=cat_info,
        location=loc,
        original_price=False,
    )

    # 4. 发布
    utils.log("🚀 发布中...")
    session = Session.load()
    with watch():
        raw = call(session, api="mtop.idle.pc.idleitem.publish", data=data, version="1.0", spm_cnt="a21ybx.publish.0.0")
    ret = raw.get("ret", [])
    item_id = (raw.get("data", {}) or {}).get("itemId", "")
    if any("SUCCESS" in r for r in ret):
        utils.log(f"🎉 发布成功! item_id={item_id}")
        return item_id
    utils.log(f"❌ 发布失败: {ret}")
    return ""


def main() -> None:
    parser = argparse.ArgumentParser(description="闲鱼发布")
    parser.add_argument("--title", default="Hermes Agent AI运维部署 使用指导")
    parser.add_argument("--desc", default=(
        "Hermes Agent 开源 AI 智能体的部署与运维指导说明。"
        "买回去遇到不会安装、不懂运维的可以问我。"
        "服务包含部署配置、运维操作、问题排查。全国包邮。拍前先沟通。"
    ))
    parser.add_argument("--price", type=float, default=49.9)
    parser.add_argument("images", nargs="*", default=None, help="图片路径（默认用素材库）")
    args = parser.parse_args()

    images = args.images or DEFAULT_IMAGES

    if not check_login():
        utils.log("⚠️ 请先运行 goofish_login.py 扫码登录")
        sys.exit(1)

    item_id = publish(args.title, args.desc, args.price, images)
    if item_id:
        utils.log(f"🔗 https://www.goofish.com/item?id={item_id}")
    else:
        sys.exit(1)


if __name__ == "__main__":
    config.ensure_xvfb()
    main()
