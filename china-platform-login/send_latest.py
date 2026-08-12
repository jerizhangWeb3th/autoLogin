#!/usr/bin/env python3
"""
发送助手：确保取到最新鲜的页面截图（二维码不过期）

策略：
1. 取最新 douyin_page_*.png
2. 若截图 < 15 秒：直接用（新鲜）
3. 若截图 15~45 秒：等下一轮（脚本每 15 秒截一次，最多等 ~20 秒）
4. 返回最终确认的新鲜截图路径
"""
import os
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()
QR_DIR = BASE_DIR / "qr"


def latest_page() -> str:
    files = sorted(QR_DIR.glob("douyin_page_*.png"), key=lambda f: f.name, reverse=True)
    return str(files[0]) if files else ""


def wait_fresh(max_wait: float = 40.0) -> str:
    """等待拿到足够新鲜的截图（<20秒），返回路径"""
    start = time.time()
    while time.time() - start < max_wait:
        p = latest_page()
        if p and os.path.exists(p):
            age = time.time() - os.path.getmtime(p)
            if age <= 20:
                return p
            # 太旧：等待脚本下一轮截图（每15秒一张）
            print(f"  截图 {os.path.basename(p)} 已 {age:.0f} 秒，等下一轮...", file=sys.stderr)
        else:
            print("  暂无截图，等待生成...", file=sys.stderr)
        time.sleep(5)
    return latest_page() or ""


if __name__ == "__main__":
    p = wait_fresh()
    if p:
        age = time.time() - os.path.getmtime(p)
        print(f"{p}")
        print(f"age={age:.0f}s", file=sys.stderr)
    else:
        print("ERROR: 无截图", file=sys.stderr)
        sys.exit(1)
