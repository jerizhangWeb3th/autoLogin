#!/usr/bin/env python3
"""重启登录 + 发最新二维码（标准流程）

每次调用：杀进程 → 清空 qr 文件夹 → 重启 → 轮询等最新二维码 → 转高清 → 输出路径
确保每次发送的都是最新二维码，无旧码残留。
"""
import os
import sys
import time
import glob
import signal
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent.resolve()
QR_DIR = BASE_DIR / "qr"
HD_DIR = QR_DIR / "hd"


def kill_procs():
    """杀掉 douyin_login 和 chrome 进程 + 清理单例锁"""
    for pat in ["douyin_login", "chrome"]:
        r = subprocess.run(["pgrep", "-f", pat], capture_output=True, text=True)
        for pid in r.stdout.strip().split("\n"):
            if pid and pid != str(os.getpid()):
                try:
                    os.kill(int(pid), signal.SIGKILL)
                except Exception:
                    pass
    for f in ["SingletonLock", "SingletonCookie", "SingletonSocket"]:
        p = Path(f"/root/.douyin-profile/{f}")
        if p.exists():
            try:
                p.unlink()
            except Exception:
                pass


def clear_qr():
    """清空 qr 文件夹（含 hd/ 子目录）所有文件 + 状态文件，确保无旧码残留"""
    for d in (QR_DIR, HD_DIR):
        if d.exists():
            for f in d.iterdir():
                try:
                    if f.is_file():
                        f.unlink(missing_ok=True)
                except Exception:
                    pass
    # 清空状态文件，避免读到旧二维码路径
    for sf in (BASE_DIR / "qr_latest.txt", BASE_DIR / "login_state.txt"):
        try:
            sf.write_text("")
        except Exception:
            pass
    print("🧹 已清空二维码文件夹 + 状态文件", flush=True)


def start_login():
    log = open("/tmp/douyin_login.log", "w")
    p = subprocess.Popen(
        ["python3", "-u", str(BASE_DIR / "douyin_login.py")],
        stdout=log, stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    return p


def wait_state_qr(timeout: int = 90) -> str:
    """轮询读取状态文件（qr_latest.txt）里记录的二维码完整路径

    代码里 write_latest/write_state 已保存二维码完整名称，
    发送时以状态文件为准，确保发送的就是代码记录的最新二维码。
    """
    qr_latest_file = BASE_DIR / "qr_latest.txt"
    state_file = BASE_DIR / "login_state.txt"
    t0 = time.time()
    while time.time() - t0 < timeout:
        # 1. 优先读 qr_latest.txt（write_latest 写的纯路径）
        if qr_latest_file.exists():
            path = qr_latest_file.read_text().strip()
            if path and os.path.exists(path) and os.path.getsize(path) > 5 * 1024:
                return path
        # 2. fallback 读 login_state.txt（write_state 写的 "STATE payload"）
        if state_file.exists():
            content = state_file.read_text().strip()
            parts = content.split(" ", 1)
            if len(parts) == 2:
                path = parts[1].strip()
                if path and os.path.exists(path) and os.path.getsize(path) > 5 * 1024:
                    return path
        time.sleep(2)
    return ""


def main():
    kill_procs()
    time.sleep(2)
    clear_qr()
    p = start_login()
    print(f"登录启动 (PID {p.pid})", flush=True)

    qr = wait_state_qr()
    if not qr:
        print("TIMEOUT 未等到状态文件记录二维码", flush=True)
        sys.exit(1)
    age = time.time() - os.path.getmtime(qr)
    print(f"✅ 状态文件记录二维码: {os.path.basename(qr)} ({os.path.getsize(qr)//1024}KB, {age:.0f}秒前)", flush=True)

    # 转高清（明确传状态文件记录的源文件）
    r = subprocess.run(
        [sys.executable, str(BASE_DIR / "tools" / "qr_to_hd.py"), qr],
        capture_output=True, text=True,
    )
    hd_files = sorted(HD_DIR.glob("hd_douyin_qr_*.png"), key=lambda f: f.name)
    if hd_files:
        hd = str(hd_files[-1])
        age2 = time.time() - os.path.getmtime(hd)
        print(f"✅ 高清图: {hd} ({os.path.getsize(hd)//1024}KB, {age2:.0f}秒前)", flush=True)
        print(f"OUTPUT {hd}", flush=True)
    else:
        print("ERROR 转高清失败", flush=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
