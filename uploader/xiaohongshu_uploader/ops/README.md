# 小红书自运营能力包（ops）

> 从 Xiangyu-CAS/xiaohongshu-ops-skill 迁移融合。用 xhs SDK（XhsClient）纯 API
> 替代 OpenClaw 浏览器自动化，实现小红书全链路自运营：分析 → 选题 → 复刻 → 发布 → 复盘。

## 模块

| 模块 | 能力 | 对应 ops-skill |
|------|------|----------------|
| `client` | XhsClient 统一客户端（cookie 合并 + sign） | —（技术底座） |
| `analyzer` | 首页推荐流分析 + 账号分析 | home-feed-analysis / account-analysis |
| `ideation` | 选题灵感（平台信号 + 搜索建议 + 话题） | topic-ideation |
| `viral_copy` | 爆款复刻（笔记拆解 + 评论信号 + 图片下载） | viral-copy-flow |
| `knowledge_base` | 知识库沉淀（结构化保存 + 检索） | knowledge-base |
| `persona.md` | 文案人设（语气/节奏/禁忌） | persona |

## 用法

```python
from uploader.xiaohongshu_uploader.ops import client, analyzer, ideation, viral_copy, knowledge_base

c = client.get_client()                        # 统一客户端（cookie + sign）

# 首页推荐流分析（数据层，供 LLM 提炼钩子/结构/选题）
notes = analyzer.analyze_home_feed(client=c, limit=20)

# 账号分析（数据层，供 LLM 五维评分）
acc = analyzer.analyze_account(client=c, user_id="<user_id>", limit=15)

# 选题灵感（平台信号）
signals = ideation.search_signals(client=c, keyword="AI工具")

# 爆款复刻（源笔记拆解）
detail = viral_copy.get_note_detail(client=c, source="https://www.xiaohongshu.com/explore/<id>")
comments = viral_copy.get_note_comments(client=c, source="<id>")

# 知识库沉淀
knowledge_base.save_record("pattern", "确认键评论钩子有效", brief="confirmation-hook",
                           body="...", tags=["title-hook"], source="<url>")
```

## 分层设计

- **数据层**（本包）：抓数据 + 结构化，不写死分析结论。
- **分析层**（调用方 agent/LLM）：基于结构化数据生成分析结论、选题、复刻文案。
- **存储层**（knowledge_base）：把结论沉淀成可检索记录。

## 运营 SOP 要点（迁移自 ops-skill）

1. **首页推荐流分析**：抓推荐流前 20 条 → 提炼主导主题 / 高信号样本 / 可复用模式 / 下步动作。
2. **账号分析**：抓账号画像 + 最近 9-15 篇 → 五维评分（定位/结构/互动/辨识度/可持续）→ 最大优势 + 最大短板 + 下步动作。
3. **选题灵感**：混合平台信号（高互动笔记）+ 需求信号（搜索联想）+ 账号定位 → 3-5 条选题（带互动钩子 + 三段结构）。
4. **爆款复刻**：输入爆款 URL → 拆标题/封面/正文/互动模板 → "结构级复刻"（保留主题与机制，重设计措辞，禁止逐字照抄）。
5. **知识库**：任务结束至少沉淀一条记录（结论/证据/可复用点/风险/下一步）。

## 风控底线

- 红线词（政治/色情/赌博/毒品/武器）直接拦截。
- 引流词（微信/QQ/手机/私聊/免费送）+ 广告法敏感词（最/第一/全网最低）自动替换。
- 评论默认 one-send-per-turn，间隔 8-15s，触发"操作频繁"立即停。
