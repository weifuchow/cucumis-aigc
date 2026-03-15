---
name: beat-sync-storyboard-planner
description: Generate a beat aligned storyboard from script and global timeline artifacts. Use when scene timing must follow audio rhythm.
---

# beat_sync_storyboard_planner

## Purpose

基于脚本和全局时间网格生成严格踩点的分镜结构，确保 scene 时长、转场意图和动作节奏对齐音频节点。

**核心职责之一是为每个 scene 智能分配 `motion_intent` 和 `asset_mode`——这两个字段直接决定后续是走本地 FFmpeg 静态合成（零成本），还是调用视频生成模型（高成本）。**

## Reads

- `projects/<project>/script/script.json`
- `projects/<project>/timeline/global-timeline.json`

## Writes

- `projects/<project>/storyboard/storyboard.json`

## Required Output

每个 scene 至少包含：

- `scene_id`
- `start_time` / `end_time` / `duration_seconds`
- `beat_alignment`
- `transition_intent`
- `motion_intent`
- `asset_mode`
- `visual_description`
- `purpose`
- `subtitle_text`

## 关键决策：motion_intent 与 asset_mode

**不要用位置规则（如"最后一个场景 = fast_push"）来赋值。应根据每个场景的叙事内容做语义判断。**

### motion_intent 选项及适用场景

| 值 | 适用场景 |
|---|---|
| `hold` | 纯信息展示、数字/文字特写、停顿强调 |
| `slow_pan` | 环境建立、叙述性旁白、平静情绪 |
| `locked` | 对话场景、静态对比、沉思时刻 |
| `fast_push` | 高能量转折、冲突爆发、关键揭示 |
| `black_flash` | 场景切换强调、情绪休止、章节分割 |
| `whip_pan` | 快节奏剪辑、动作追逐、极度紧张 |
| `handheld` | 混乱现场、主观视角、紧张追逐 |
| `mixed` | 多运动意图并存、复杂场景 |

### asset_mode 选项

| 值 | 含义 | 何时使用 |
|---|---|---|
| `static` | 本地 FFmpeg 静态合成，不调视频模型 | 叙述性、信息性、情绪平稳的场景 |
| `mixed` | 需要视频生成模型，产生真实动态 | 高能量动作、戏剧转折、需要真实运动感的场景 |

### 决策原则

1. **优先 static**：除非场景明确需要真实运动感，否则 `asset_mode=static` 更节省成本
2. **动感词判断**：`visual_description` 或 `purpose` 含有"冲击"、"爆发"、"追逐"、"战斗"、"坠落"、"飞行"等动态词 → `mixed`
3. **叙事位置参考（次要）**：开场建立通常 `slow_pan/static`；高潮段落更可能 `mixed`；结尾收束通常 `hold/static`
4. **时长参考**：≤2s 的短场景用 `static` + `hold` 即可，不值得调模型
5. **情绪强度**：`emotion_markers` 中 intensity 高的场景考虑 `mixed`

### 示例推理

```
visual_description: "主角看着远处的城市灯光，若有所思"
purpose: "narrative_reflection"
→ motion_intent: slow_pan, asset_mode: static  ✓ 叙述性，静态足够

visual_description: "龙从天而降，火焰吞噬整个战场"
purpose: "climax_action"
→ motion_intent: fast_push, asset_mode: mixed  ✓ 需要真实动态

visual_description: "屏幕显示数据图表和统计数字"
purpose: "information_display"
→ motion_intent: hold, asset_mode: static  ✓ 纯信息，静态更合适
```

## Runtime Expectations

- 调用 `python scripts/run_beat_sync_storyboard_planner.py --project <name>` 生成初始 storyboard
- **脚本生成的 motion_intent/asset_mode 是规则默认值，Claude 应在写入前基于上述决策框架逐场景审查并修正**
- 修正后覆盖写入 `storyboard/storyboard.json`
- 事件写入规则与主 workflow 一致
