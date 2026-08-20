# -*- coding: utf-8 -*-
"""登录流程公共基类与工具函数（阿里规范：DRY + docstring + 类型注解）。

消除各平台 uploader 的重复代码，统一以下公共逻辑：
  - format_msg             日志消息格式化（替代各平台 _msg）
  - build_login_result     登录结果字典构造（替代各平台 _build_login_result）
  - emit_qrcode_callback   二维码回调触发（替代各平台 _emit_qrcode_callback）
  - build_launch_kwargs    浏览器启动参数（替代各平台 _build_launch_kwargs）
  - resolve_account_file   账号 cookie 文件路径解析（替代各平台 _resolve_account_file）

各平台 uploader 只保留平台特有的二维码提取、登录判定与上传逻辑。
"""
from __future__ import annotations

import inspect
from pathlib import Path

from conf import BASE_DIR, LOCAL_CHROME_PATH


def format_msg(emoji: str, text: str) -> str:
    """构造带 emoji 前缀的日志消息。

    Args:
        emoji: emoji 表情符号。
        text: 日志正文。

    Returns:
        格式化后的消息字符串。
    """
    return f"{emoji} {text}"


def build_login_result(
    success: bool,
    status: str,
    message: str,
    account_file: str,
    qrcode: dict | None = None,
    current_url: str = "",
) -> dict:
    """构造统一的登录结果字典。

    Args:
        success: 是否登录成功。
        status: 状态码（如 cookie_valid / cookie_invalid / success）。
        message: 状态描述。
        account_file: 账号 cookie 文件路径。
        qrcode: 二维码信息（含 image_path / image_data_url），无则 None。
        current_url: 登录后当前页面 URL。

    Returns:
        标准登录结果字典。
    """
    return {
        "success": success,
        "status": status,
        "message": message,
        "account_file": str(account_file),
        "qrcode": qrcode,
        "current_url": current_url,
    }


async def emit_qrcode_callback(qrcode_callback, payload: dict) -> None:
    """触发二维码回调，兼容同步与异步回调函数。

    Args:
        qrcode_callback: 回调函数或可等待对象，为空则跳过。
        payload: 回调参数（含 image_path / image_data_url）。
    """
    if not qrcode_callback:
        return
    result = qrcode_callback(payload)
    if inspect.isawaitable(result):
        await result


def build_launch_kwargs(
    headless: bool,
    channel: str | None = None,
    extra_args: list[str] | None = None,
) -> dict:
    """构造浏览器启动参数。

    Args:
        headless: 是否无头模式。
        channel: 浏览器 channel（如 "chrome"），None 时用默认。
        extra_args: 额外的浏览器启动参数。

    Returns:
        playwright launch 参数字典。
    """
    kwargs: dict = {"headless": headless}
    if LOCAL_CHROME_PATH:
        kwargs["executable_path"] = LOCAL_CHROME_PATH
    if channel:
        kwargs["channel"] = channel
    if extra_args:
        kwargs["args"] = extra_args
    return kwargs


def resolve_account_file(account_file: str | Path, platform_dir: str) -> str:
    """解析账号 cookie 文件路径。

    Args:
        account_file: 账号文件路径或文件名。
        platform_dir: 平台 cookie 子目录（如 douyin_uploader）。

    Returns:
        解析后的绝对路径字符串。
    """
    path = Path(account_file).expanduser()
    if path.is_absolute():
        return str(path)
    if len(path.parts) == 1:
        return str((Path(BASE_DIR) / "cookies" / platform_dir / path).resolve())
    return str(path.resolve())
