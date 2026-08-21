#!/usr/bin/env python3
"""
小红书自运营能力包（ops）— 从 Xiangyu-CAS/xiaohongshu-ops-skill 迁移融合。

用 xhs SDK（XhsClient）纯 API 替代 OpenClaw 浏览器自动化，实现：
- client        : XhsClient 统一客户端（cookie + sign）
- analyzer      : 首页推荐流分析 + 账号分析（数据抓取 + 结构化）
- ideation      : 选题灵感（平台信号抓取 + 主题框生成）
- viral_copy    : 爆款复刻（笔记详情抓取 + 图片下载）
- knowledge_base: 知识库沉淀（结构化保存 + 检索）
"""
from . import client, analyzer, ideation, viral_copy, knowledge_base  # noqa: F401

__all__ = ["client", "analyzer", "ideation", "viral_copy", "knowledge_base"]
