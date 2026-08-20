# 卡片风格参考（AI 生成类）

> 本文件记录 **AI 图像生成类** 风格定义（依赖 `image_generate` 工具）。
> 当前 Hermes 环境无 `image_generate`，这些风格暂不可本地渲染，保留定义供未来集成。
> 本地可生成的 HTML 风格见 `platforms/xiaohongshu/cards.py`（qiaomu 四风格 + morandi）。

## 一、baoyu-infographic（21 布局 × 21 风格）

来源：`baoyu-infographic` skill（https://github.com/JimLiu/baoyu-skills）

### 21 布局（Layout）

| 布局 | 适用 |
|:---|:---|
| `linear-progression` | 时间线、流程、教程 |
| `binary-comparison` | A/B 对比、前后对比 |
| `comparison-matrix` | 多因素对比 |
| `hierarchical-layers` | 金字塔、优先级 |
| `tree-branching` | 分类、层级 |
| `hub-spoke` | 中心概念 + 关联项 |
| `structural-breakdown` | 爆炸图、剖面 |
| `bento-grid` | 多主题总览（默认）|
| `iceberg` | 表面 vs 深层 |
| `bridge` | 问题-方案 |
| `funnel` | 转化、过滤 |
| `isometric-map` | 空间关系 |
| `dashboard` | 指标、KPI |
| `periodic-table` | 分类集合 |
| `comic-strip` | 叙事、序列 |
| `story-mountain` | 情节、张力弧 |
| `jigsaw` | 互联部件 |
| `venn-diagram` | 重叠概念 |
| `winding-roadmap` | 旅程、里程碑 |
| `circular-flow` | 循环流程 |
| `dense-modules` | 高密度模块、数据指南 |

### 21 风格（Style）

| 风格 | 描述 |
|:---|:---|
| `craft-handmade` | 手绘纸艺（默认）|
| `claymation` | 3D 粘土定格 |
| `kawaii` | 日式可爱粉彩 |
| `storybook-watercolor` | 柔和水彩 |
| `chalkboard` | 黑板粉笔 |
| `cyberpunk-neon` | 霓虹赛博朋克 |
| `bold-graphic` | 漫画网点 |
| `aged-academia` | 复古学术 |
| `corporate-memphis` | 扁平矢量孟菲斯 |
| `technical-schematic` | 蓝图工程 |
| `origami` | 折纸几何 |
| `pixel-art` | 复古 8-bit |
| `ui-wireframe` | 灰度界面线框 |
| `subway-map` | 地铁线路图 |
| `ikea-manual` | 极简线描 |
| `knolling` | 平铺整理 |
| `lego-brick` | 乐高积木 |
| `pop-laboratory` | 实验蓝图网格 |
| `morandi-journal` | 手绘莫兰迪暖调 |
| `retro-pop-grid` | 1970s 复古波普 |
| `hand-drawn-edu` | 马卡龙手绘教育 |

### 推荐组合（内容类型 → 布局+风格）

- 教程步骤 → `linear-progression` + `ikea-manual`
- 对比 → `binary-comparison` + `corporate-memphis`
- 技术图 → `structural-breakdown` + `technical-schematic`
- 教育 → `bento-grid` + `chalkboard`
- 产品指南 → `dense-modules` + `morandi-journal`

## 二、baoyu-comic（6 风格 × 7 色调）

来源：`baoyu-comic` skill

### 6 艺术风格（Art）

`ligne-claire`（默认）、`manga`、`realistic`、`ink-brush`、`chalk`、`minimalist`

### 7 色调（Tone）

`neutral`（默认）、`warm`、`dramatic`、`romantic`、`energetic`、`vintage`、`action`

### 5 预设（Preset）

| 预设 | 组合 | 特色 |
|:---|:---|:---|
| `ohmsha` | manga + neutral | 视觉隐喻、无对话头 |
| `wuxia` | ink-brush + action | 武侠气劲、打斗 |
| `shoujo` | manga + romantic | 少女漫装饰 |
| `concept-story` | manga + warm | 视觉符号系统 |
| `four-panel` | minimalist + four-panel | 起承转合、黑白+点缀色 |

### 布局（Layout）

`standard`（默认）、`cinematic`、`dense`、`splash`、`mixed`、`webtoon`、`four-panel`

## 集成说明

未来接入 `image_generate` 工具后，可在 `cards.py` 增加 `generate_ai_card()` 函数，
按上表的布局×风格组合生成 prompt，映射 aspect ratio 到 image_generate 的 landscape/portrait/square。
