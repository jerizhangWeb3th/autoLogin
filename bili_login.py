"""biliup 扫码登录控制器：用 pexpect 选择「扫码登录」，持续运行等用户扫码。"""
import os
import sys
import time

import pexpect

BILIUP = "/root/.social-auto-upload/tools/biliup/linux-x86_64/biliup"
ACCOUNT = "cookies/bilibili_bilibili_main.json"

env = dict(os.environ)
env["DISPLAY"] = ":99"


def main():
    child = pexpect.spawn(
        BILIUP, ["-u", ACCOUNT, "login"],
        cwd="/root/autoLogin", env=env, encoding="utf-8", timeout=60,
    )

    # 1. 等待登录方式菜单出现
    child.expect("选择一种登录方式", timeout=30)
    print("STATE:MENU", flush=True)

    # 2. 下移一格（短信登录 → 扫码登录）并回车
    child.send("\x1b[B")
    time.sleep(0.5)
    child.send("\r")
    print("STATE:SELECTED_SCAN", flush=True)

    # 3. 持续转发输出（等用户扫码），直到进程退出或超时
    start = time.time()
    while time.time() - start < 600:  # 最长等 10 分钟
        try:
            index = child.expect(["\r\n", pexpect.EOF, pexpect.TIMEOUT], timeout=30)
            if index == 0:
                line = child.before.strip()
                if line:
                    print(f"OUT:{line}", flush=True)
            elif index == 1:
                print("STATE:EOF", flush=True)
                break
            else:
                # TIMEOUT：检查是否有二维码文件生成
                print("STATE:WAITING", flush=True)
        except pexpect.TIMEOUT:
            print("STATE:WAITING", flush=True)
    else:
        print("STATE:TIMEOUT_10MIN", flush=True)

    child.close()
    print("STATE:EXIT", flush=True)


if __name__ == "__main__":
    main()
