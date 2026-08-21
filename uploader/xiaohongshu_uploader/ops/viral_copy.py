#!/usr/bin/env python3
"""
小红书爆款复刻（ops.viral_copy）— 源笔记拆解 + 图片下载。

迁移自 xiaohongshu-ops-skill 的 references/xhs-viral-copy-flow.md。核心流程：
输入爆款 URL/note_id → 抓笔记详情（标题/正文/互动）+ 评论信号 → LLM 分析爆款
因素并生成"结构级复刻"的新笔记（保留主题与互动机制，重设计措辞与素材）。

本模块负责"源笔记拆解 + 图片下载"，复刻改写由调用方（agent/LLM）完成。
"""
from __future__ import annotations

from .analyzer import parse_count


def _extract_note_id(source: str) -> str:
    """从笔记 URL 或纯 ID 提取 note_id。"""
    import re

    s = source.strip()
    # 支持 https://www.xiaohongshu.com/explore/<id> 或 discovery/item/<id>
    m = re.search(r"(?:explore|item|note)/([0-9a-fA-F]{20,})", s)
    if m:
        return m.group(1)
    if re.fullmatch(r"[0-9a-fA-F]{20,}", s):
        return s
    return s


def get_note_detail(client=None, source: str = "") -> dict:
    """抓取笔记详情（标题/正文/互动/图片），返回结构化拆解数据。"""
    from .client import get_client

    client = client or get_client()
    note_id = _extract_note_id(source)
    try:
        note = client.get_note_by_id(note_id)
    except Exception as e:
        print(f"⚠️ 笔记详情抓取失败: {str(e)[:120]}")
        return {"error": str(e)[:120], "note_id": note_id}

    if not isinstance(note, dict):
        return {"error": "返回结构异常", "note_id": note_id}

    note = note.get("note", note) if "note" in note else note
    interact = note.get("interact_info", {}) or {}
    user = note.get("user", {}) or {}

    # 图片列表
    images: list[str] = []
    for img in (note.get("image_list", []) or []):
        if isinstance(img, dict):
            url = img.get("url_default") or img.get("url_pre") or img.get("url", "")
            if url:
                images.append(url)

    return {
        "note_id": note_id,
        "title": note.get("title", ""),
        "desc": (note.get("desc", "") or "")[:500],
        "type": note.get("type", ""),
        "likes": parse_count(interact.get("liked_count", 0)),
        "collects": parse_count(interact.get("collected_count", 0)),
        "comments": parse_count(interact.get("comment_count", 0)),
        "shares": parse_count(interact.get("share_count", 0)),
        "author": user.get("nickname", ""),
        "author_id": user.get("user_id", ""),
        "tags": [t.get("name", "") for t in (note.get("tag_list", []) or []) if isinstance(t, dict)],
        "image_count": len(images),
        "images": images,
    }


def get_note_comments(client=None, source: str = "", limit: int = 20) -> list[str]:
    """抓取笔记热门评论（评论信号：用户共鸣点、争议点、可复用触发词）。"""
    from .client import get_client

    client = client or get_client()
    note_id = _extract_note_id(source)
    comments: list[str] = []
    try:
        result = client.get_note_comments(note_id)
        items = result.get("comments", []) if isinstance(result, dict) else result
        for c in (items or [])[:limit]:
            if isinstance(c, dict):
                txt = c.get("content", "").strip()
                if txt:
                    comments.append(txt)
    except Exception as e:
        print(f"⚠️ 评论抓取失败: {str(e)[:120]}")
    return comments


def download_note_images(client=None, source: str = "", dir_path: str = "/tmp/xhs_note_images") -> list[str]:
    """下载笔记图片到本地目录，返回文件路径列表（供复刻配图参考）。"""
    from pathlib import Path

    from .client import get_client

    client = client or get_client()
    note_id = _extract_note_id(source)
    out = Path(dir_path)
    out.mkdir(parents=True, exist_ok=True)
    try:
        client.save_files_from_note_id(note_id, str(out))
        files = sorted(out.glob("*"))
        return [str(f) for f in files if f.is_file()]
    except Exception as e:
        print(f"⚠️ 图片下载失败: {str(e)[:120]}")
        return []
