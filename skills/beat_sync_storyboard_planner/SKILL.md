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
- `local_render_technique`
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

### local_render_technique 选项（asset_mode=static 时必填）

| 值 | 效果 | 适用场景 |
|---|---|---|
| `loop` | 单张图片静止循环 | 停顿、信息展示、极短场景 |
| `sequence` | 多张图片依次播放 | 叙述推进、多角度展示 |
| `alternating` | 两张图片快速交替（0.15s/帧） | 奔跑、战斗、快速动作 |
| `crossfade` | 两张图片缓慢淡入淡出 | 情绪过渡、场景切换、回忆 |
| `zoom_in` | 单图缓慢推进（Ken Burns） | 悬念建立、强调细节 |
| `zoom_out` | 单图缓慢拉远 | 开场建立、结尾收束 |
| `pan_left` | 单图向左平移 | 空间展示、时间流逝 |
| `pan_right` | 单图向右平移 | 追逐方向、空间扩展 |

### 决策原则

1. **视频模型预算为 2 次**：整个项目最多 2 个场景调用视频生成模型，其余全走本地合成
2. **优先把预算给最高冲击力的场景**：叙事高潮、情绪爆发点、最难用静态表达的场景
3. **其余场景用 `local_render_technique` 模拟动感**：
   - 奔跑/战斗 → `alternating`（快速交替比静止图更有动感）
   - 情绪转变/回忆 → `crossfade`（缓慢渐变传递情绪变化）
   - 建立镜头/压迫感 → `zoom_in`
   - 开场/结尾 → `zoom_out`
4. **动感词判断**：`visual_description` 含"冲击"、"爆发"、"追逐"、"战斗"、"坠落"、"飞行" → 候选 `mixed`，但先看是否已用完预算
5. **时长参考**：≤2s 的短场景不值得调模型，优先 `loop` 或 `alternating`

### 示例推理

```
visual_description: "主角看着远处的城市灯光，若有所思"
purpose: "narrative_reflection"
→ motion_intent: slow_pan, asset_mode: static, local_render_technique: zoom_in
  ✓ 叙述性，推进镜头增加沉浸感

visual_description: "主角在街道上全速奔跑，双腿交替迈步"
purpose: "action_chase"
→ motion_intent: handheld, asset_mode: static, local_render_technique: alternating
  ✓ 两张奔跑图交替产生动感，无需调视频模型

visual_description: "回忆画面：童年的家，温暖阳光透过窗户"
purpose: "emotional_flashback"
→ motion_intent: locked, asset_mode: static, local_render_technique: crossfade
  ✓ 两张图缓慢渐变，传递时光流逝感

visual_description: "龙从天而降，火焰吞噬整个战场，冲击波横扫一切"
purpose: "climax_peak"
→ motion_intent: fast_push, asset_mode: mixed, local_render_technique: (不适用，走模型)
  ✓ 最高冲击力场景，值得用视频模型预算

visual_description: "屏幕显示数据图表和统计数字"
purpose: "information_display"
→ motion_intent: hold, asset_mode: static, local_render_technique: loop
  ✓ 纯信息，静止即可
```

## Runtime Expectations

- 调用 `python scripts/run_beat_sync_storyboard_planner.py --project <name>` 生成初始 storyboard
- **脚本生成的 motion_intent/asset_mode 是规则默认值，Claude 应在写入前基于上述决策框架逐场景审查并修正**
- 修正后覆盖写入 `storyboard/storyboard.json`
- 事件写入规则与主 workflow 一致
