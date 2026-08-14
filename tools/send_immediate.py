#!/usr/bin/env python3
"""即时发码：轮询等待二维码生成，一生成立即转高清（最小化链路时间）"""
import os
import sys
import time
import glob
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent.resolve()
QR_DIR = BASE_DIR / "qr"
HD_DIR = QR_DIR / "hd"
HD_DIR.mkdir(exist_ok=True)


def wait_and_convert(timeout: int = 90) -> str:
    """轮询等待 douyin_qr_*.png 生成，生成后立即转高清"""
    t0 = time.time()
    last_seen = None
    while time.time() - t0 < timeout:
        qrs = sorted(QR_DIR.glob("douyin_qr_*.png"), key=lambda f: f.name)
        if qrs:
            latest = str(qrs[-1])
            if latest != last_seen:
                last_seen = latest
                # 检查文件大小稳定（截图完成）
                sz = os.path.getsize(latest)
                if sz > 5 * 1024:
                    age = time.time() - os.path.getmtime(latest)
                    # 转高清
                    r = subprocess.run(
                        [sys.executable, str(BASE_DIR / "tools" / "qr_to_hd.py"), latest],
                        capture_output=True, text=True,
                    )
                    hd_files = sorted(HD_DIR.glob("hd_douyin_qr_*.png"), key=lambda f: f.name)
                    if hd_files:
                        hd = str(hd_files[-1])
                        print(f"READY {hd}")
                        print(f"源: {os.path.basename(latest)} (生成 {age:.0f}秒前)")
                        return hd
        time.sleep(2)
    print("TIMEOUT 未等到二维码")
    return ""


if __name__ == "__main__":
    wait_and_convert()
