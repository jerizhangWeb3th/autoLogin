#!/usr/bin/env python3
"""
小红书选题灵感（ops.ideation）— 平台信号抓取 + 搜索建议。

迁移自 xiaohongshu-ops-skill 的 references/xhs-topic-ideation.md。核心思路：
混合三类信号（平台侧高互动内容 / 需求侧搜索建议 / 账号侧定位），用 LLM 生成
选题。本模块负责"信号抓取"，选题生成由调用方（agent/LLM）完成。
"""
from __future__ import annotations

from .analyzer import parse_count


def search_signals(client=None, keyword: str = "", page: int = 1, page_size: int = 20) -> list[dict]:
    """按关键词搜索高互动笔记，返回结构化平台信号（供 LLM 提炼选题）。

    返回按点赞降序排列的笔记列表（标题/点赞/类型/作者），作为选题的"平台侧信号"。
    """
    from .client import get_client

    client = client or get_client()
    notes: list[dict] = []
    try:
        result = client.get_note_by_keyword(keyword, page=page, page_size=page_size)
        items = result.get("items", []) if isinstance(result, dict) else result
        for item in (items or []):
            if not isinstance(item, dict):
                continue
            nc = item.get("note_card", {}) or {}
            interact = nc.get("interact_info", {}) or {}
            user = nc.get("user", {}) or {}
            notes.append({
                "note_id": item.get("id", ""),
                "title": nc.get("display_title", ""),
                "likes": parse_count(interact.get("liked_count", 0)),
                "type": nc.get("type", ""),
                "author": user.get("nickname", ""),
            })
    except Exception as e:
        print(f"⚠️ 搜索信号抓取失败: {str(e)[:120]}")
    notes.sort(key=lambda x: x["likes"], reverse=True)
    return notes


def search_suggestions(client=None, keyword: str = "") -> list[str]:
    """获取搜索联想词（需求侧信号：用户在搜什么、关心什么）。"""
    from .client import get_client

    client = client or get_client()
    try:
        result = client.get_search_suggestion(keyword)
        if isinstance(result, list):
            return [str(x) for x in result][:20]
        if isinstance(result, dict):
            return [str(x) for x in (result.get("suggestions") or result.get("data") or [])][:20]
    except Exception as e:
        print(f"⚠️ 搜索联想抓取失败: {str(e)[:120]}")
    return []


def suggest_topics(client=None, keyword: str = "") -> list[dict]:
    """获取推荐话题（供选题的标签/话题部分使用）。"""
    from .client import get_client

    client = client or get_client()
    try:
        result = client.get_suggest_topic(keyword)
        if isinstance(result, list):
            return [{"name": str(x.get("name", x)) if isinstance(x, dict) else str(x)}
                    for x in result][:20]
        if isinstance(result, dict):
            return [{"name": str(x)} for x in (result.get("topics") or result.get("data") or [])][:20]
    except Exception as e:
        print(f"⚠️ 话题抓取失败: {str(e)[:120]}")
    return []
