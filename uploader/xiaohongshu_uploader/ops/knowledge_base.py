#!/usr/bin/env python3
"""
小红书知识库沉淀（ops.knowledge_base）— 结构化保存 + 检索。

迁移自 xiaohongshu-ops-skill 的 references/xhs-knowledge-base.md 和
knowledge-base/ 目录结构。目标：把每次分析/选题/发布/回复/复盘的结论沉淀成
可检索、可复用、可追踪的记录，让后续决策快速回答"之前怎么做的 / 什么有效 /
下次复用什么"。

目录分层（与 ops-skill 一致）：
    knowledge-base/
      accounts/   # 账号定位、账号诊断、竞品分析
      topics/     # 选题候选、争议点、标题骨架
      patterns/   # 爆款结构、封面层级、互动机制
      actions/    # 发布、回复、抓取、下载、复刻等动作记录
      reviews/    # 结果复盘、有效/无效原因、下次调整
"""
from __future__ import annotations

import time
from pathlib import Path

KB_ROOT = Path(__file__).resolve().parent.parent.parent.parent / "knowledge-base"

# 记录类型 → 子目录映射
_TYPE_DIR = {
    "account": "accounts",
    "topic": "topics",
    "pattern": "patterns",
    "action": "actions",
    "review": "reviews",
}


def _subdir(record_type: str) -> Path:
    d = KB_ROOT / _TYPE_DIR.get(record_type, "actions")
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_record(record_type: str, summary: str, *, brief: str = "", body: str = "",
                tags: list[str] | None = None, source: str = "") -> Path:
    """保存一条结构化记录，返回文件路径。

    record_type: account | topic | pattern | action | review
    summary:     一句话结论
    brief:       文件名简短标识（2-6 个高信息量词，如 "confirmation-comment-hook"）
    body:        正文（证据/可复用点/风险/下一步）
    tags:        标签列表
    source:      来源（笔记 URL / 账号名等）
    """
    d = _subdir(record_type)
    date = time.strftime("%Y-%m-%d")
    slug = brief or f"{record_type}-{int(time.time())}"
    fname = d / f"{date}-{slug}.md"

    tag_str = ", ".join(tags) if tags else ""
    content = f"""---
id: {date}-{slug}
type: {record_type}
status: active
created_at: {time.strftime('%Y-%m-%dT%H:%M:%S')}
source: "{source}"
tags: [{tag_str}]
---

# 结论

{summary}

# 详情

{body or summary}
"""
    fname.write_text(content, encoding="utf-8")
    print(f"✅ 知识库已沉淀: {fname}")
    return fname


def search_records(query: str, limit: int = 10) -> list[dict]:
    """按关键词检索知识库（匹配文件名 + 内容），返回最相关的记录摘要。"""
    hits: list[dict] = []
    if not KB_ROOT.exists():
        return hits
    for md in KB_ROOT.rglob("*.md"):
        if md.name == "README.md":
            continue
        try:
            text = md.read_text(encoding="utf-8")
        except OSError:
            continue
        if query.lower() in text.lower():
            hits.append({
                "path": str(md),
                "filename": md.name,
                "summary": _extract_summary(text),
            })
        if len(hits) >= limit:
            break
    return hits


def _extract_summary(text: str) -> str:
    """从记录里提取结论首行（# 结论 之后的第一段非空行）。"""
    in_conclusion = False
    for line in text.splitlines():
        if line.strip() == "# 结论":
            in_conclusion = True
            continue
        if in_conclusion:
            s = line.strip()
            if s:
                return s[:120]
    return ""


def ensure_index() -> Path:
    """确保知识库总览入口存在（knowledge-base/README.md）。"""
    readme = KB_ROOT / "README.md"
    if not readme.exists():
        KB_ROOT.mkdir(parents=True, exist_ok=True)
        readme.write_text(
            "# XHS Knowledge Base\n\n"
            "小红书运营知识库总览（由 ops.knowledge_base 维护）。\n\n"
            "- accounts/  账号定位、账号诊断、竞品分析\n"
            "- topics/    选题候选、争议点、标题骨架\n"
            "- patterns/  爆款结构、封面层级、互动机制\n"
            "- actions/   发布、回复、抓取、下载、复刻等动作记录\n"
            "- reviews/   结果复盘、有效/无效原因、下次调整\n",
            encoding="utf-8",
        )
    return readme


if __name__ == "__main__":
    ensure_index()
    print(f"知识库根目录: {KB_ROOT}")
