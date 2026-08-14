#!/usr/bin/env python3
"""二维码高清转换：512x512 → 2048x2048 高质量 PNG（微信压缩后仍可扫）"""
import os
import sys
from pathlib import Path
from PIL import Image

BASE_DIR = Path(__file__).parent.resolve()
QR_DIR = BASE_DIR / "qr"
HD_DIR = QR_DIR / "hd"
HD_DIR.mkdir(exist_ok=True)


def latest_qr() -> str:
    files = sorted(QR_DIR.glob("douyin_qr_*.png"), key=lambda f: f.name, reverse=True)
    return str(files[0]) if files else ""


def to_hd(src: str, scale: int = 4) -> str:
    """放大二维码：最近邻插值保持方块锐利，转 RGB 高质量保存"""
    img = Image.open(src)
    if img.mode != "RGB":
        img = img.convert("RGB")
    # 最近邻放大（二维码必须用 NEAREST 保持方块边界清晰）
    big = img.resize((img.width * scale, img.height * scale), Image.NEAREST)
    out = str(HD_DIR / f"hd_{Path(src).stem}.png")
    big.save(out, "PNG", optimize=True)
    return out


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else latest_qr()
    if not src or not os.path.exists(src):
        print("ERROR: 无二维码文件", file=sys.stderr)
        sys.exit(1)
    out = to_hd(src)
    print(f"HD: {out}")
    print(f"原图: {os.path.getsize(src)//1024}KB | HD: {os.path.getsize(out)//1024}KB | 尺寸: {Image.open(out).size}")
