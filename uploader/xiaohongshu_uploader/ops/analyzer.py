#!/usr/bin/env python3
"""
小红书分析能力（ops.analyzer）— 首页推荐流分析 + 账号分析。

迁移自 xiaohongshu-ops-skill 的 references/xhs-home-feed-analysis.md 和
xhs-account-analysis.md。数据抓取用 XhsClient 纯 API（替代 OpenClaw 浏览器），
分析结论由调用方（agent/LLM）基于结构化数据生成。

【数据层】这里只负责"抓数据 + 结构化"，不写死分析结论。
【分析层】agent 拿到结构化数据后，按五维框架（定位/结构/互动/辨识度/可持续）生成结论。
"""
from __future__ import annotations

from typing import Any


def parse_count(v: Any) -> int:
    """解析互动数（'935' / '3.6万' / '1.2亿' → int）。"""
    if v is None:
        return 0
    s = str(v).strip()
    if not s:
        return 0
    try:
        if "万" in s:
            return int(float(s.replace("万", "")) * 10000)
        if "亿" in s:
            return int(float(s.replace("亿", "")) * 100000000)
        return int(float(s.replace(",", "")))
    except (ValueError, TypeError):
        return 0


def _note_to_brief(item: dict) -> dict:
    """把首页 feed 的 item 提炼成分析用精简字段。"""
    nc = item.get("note_card", {}) or {}
    user = nc.get("user", {}) or {}
    interact = nc.get("interact_info", {}) or {}
    cover = nc.get("cover", {}) or {}
    # 封面图片 URL（取第一张 prv/wm）
    cover_url = ""
    for info in (cover.get("info_list", []) or []):
        if isinstance(info, dict) and info.get("url"):
            cover_url = info["url"]
            break
    return {
        "note_id": item.get("id", ""),
        "title": nc.get("display_title", ""),
        "type": nc.get("type", ""),  # normal=图文 video=视频
        "likes": parse_count(interact.get("liked_count", 0)),
        "author": user.get("nickname", ""),
        "author_id": user.get("user_id", ""),
        "cover_url": cover_url,
    }


def analyze_home_feed(client=None, limit: int = 20) -> list[dict]:
    """抓取首页推荐流，返回结构化笔记列表（供 LLM 分析钩子/结构/选题）。

    对应 ops-skill 的"首页推荐流分析"。默认抓推荐流前 N 条，提炼
    标题/类型/点赞/作者/封面，去重后返回。
    """
    from xhs.core import FeedType

    from .client import get_client

    client = client or get_client()
    notes: list[dict] = []
    try:
        feed = client.get_home_feed(feed_type=FeedType.RECOMMEND)
        items = feed.get("items", []) if isinstance(feed, dict) else []
        for item in items:
            if not isinstance(item, dict):
                continue
            brief = _note_to_brief(item)
            if brief["title"] or brief["cover_url"]:
                notes.append(brief)
    except Exception as e:
        print(f"⚠️ 首页 feed 抓取失败: {str(e)[:120]}")

    # 去重
    seen: set = set()
    deduped: list[dict] = []
    for n in notes:
        if n["note_id"] and n["note_id"] not in seen:
            seen.add(n["note_id"])
            deduped.append(n)
    return deduped[:limit]


def analyze_account(client=None, user_id: str | None = None, limit: int = 15) -> dict:
    """抓取账号信息 + 最近笔记，返回结构化数据（供 LLM 五维评分）。

    对应 ops-skill 的"账号分析"。返回：
    - profile: 账号画像（昵称/简介/粉丝/获赞/笔记数）
    - notes:   最近笔记列表（标题/互动/作者）
    """
    from .client import get_client

    client = client or get_client()
    if not user_id:
        try:
            self_info = client.get_self_info2() or client.get_self_info()
            user_id = self_info.get("user_id") or self_info.get("id", "")
        except Exception as e:
            print(f"⚠️ 获取自身信息失败: {str(e)[:120]}")
            return {"error": "无 user_id 且无法获取自身信息"}

    profile: dict = {}
    try:
        info = client.get_user_info(user_id)
        if isinstance(info, dict):
            basic = info.get("basic_info", {}) or {}
            interactions = info.get("interactions", []) or []
            # interactions 可能是 list[{type,count}] 或 dict
            def _cnt(t):
                if isinstance(interactions, list):
                    for it in interactions:
                        if isinstance(it, dict) and it.get("type") == t:
                            return parse_count(it.get("count", 0))
                    return 0
                return parse_count(interactions.get(t, 0))
            profile = {
                "user_id": user_id,
                "nickname": basic.get("nickname", ""),
                "desc": (basic.get("desc", "") or "")[:200],
                "followers": _cnt("follows"),
                "followings": _cnt("followings"),
                "note_count": _cnt("notes"),
                "liked_collected": _cnt("liked_collected"),
            }
    except Exception as e:
        print(f"⚠️ 账号信息抓取失败: {str(e)[:120]}")

    notes: list[dict] = []
    try:
        raw_notes = client.get_user_notes(user_id)
        items = (raw_notes.get("notes", []) if isinstance(raw_notes, dict) else raw_notes) or []
        for n in items[:limit]:
            if not isinstance(n, dict):
                continue
            nc = n.get("note_card", {}) or n
            interact = nc.get("interact_info", {}) or {}
            notes.append({
                "note_id": n.get("id", ""),
                "title": nc.get("display_title", ""),
                "type": nc.get("type", ""),
                "likes": parse_count(interact.get("liked_count", 0)),
            })
    except Exception as e:
        print(f"⚠️ 账号笔记抓取失败: {str(e)[:120]}")

    return {"profile": profile, "notes": notes, "sample_note_count": len(notes)}
