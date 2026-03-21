# Video Pipeline State Machine

## State Model

`video_pipeline` 采用阶段推进式状态机。每个阶段只有在前置产物满足要求时才允许进入执行状态。

状态推进的判断者默认是 `master_orchestrator`，并应将其快照写入 `projects/<project>/orchestration/state.json`。

## 阶段分类

| 类型 | 说明 |
|------|------|
| **Claude 推理阶段** | Claude Code 读取文件、做判断、直接写 JSON 产物；不调用任何脚本 |
| **纯执行阶段（批处理）** | 调用 Python 脚本执行 API/FFmpeg；无模型推理；可批量串联运行 |

---

## 简化后的 7 阶段流程

```
[Claude] creative_design
    ↓ input/input.json
[Claude] script_writer
    ↓ script/script.json
[Script] audio_pipeline        ← audio_foundation + global_timeline_initializer
    ↓ audio/*.json + timeline/global-timeline.json
[Claude] beat_sync_storyboard_planner
    ↓ storyboard/storyboard.json
[Claude] asset_planner
    ↓ assets/asset-plan.json
[Script] visual_pipeline       ← asset_planner(validate) + image_generator + constrained_video_generator
    ↓ assets/images/** + video/clips.json
[Script] post_pipeline         ← subtitle_asset_manager + timeline_builder + ffmpeg_renderer_reviewer
    ↓ outputs/final.mp4
```

---

## States

### `created`

- 项目目录已初始化
- 必需模板已落盘
- 尚未开始任何 skill

### `input_parsed`

- `input/input.json` 已生成（`creative_design` 输出）
- 风格、时长、语言、画幅比等参数已确认

### `script_generated`

- `script/script.json` 已生成（`script_writer` 输出）
- 听觉轨、视觉轨和情绪标注已落盘

### `audio_founded`

- `audio_pipeline` 批处理完成
- `audio/voiceover.json`、`audio/bgm-selection.json`、`audio/beat-grid.json` 已生成
- `timeline/global-timeline.json` 已生成

### `storyboard_planned`

- `storyboard/storyboard.json` 已生成（`beat_sync_storyboard_planner` 输出）
- 场景列表已与音频时间网格对齐

### `asset_planned`

- `assets/asset-plan.json` 已生成（`asset_planner` Claude 输出）
- 角色视图、场景建立图、每场景关键帧方案已确定
- `decisions` 块已写明是否需要角色图/场景图

### `visuals_generated`

- `visual_pipeline` 批处理完成
- `assets/images/` 已按三阶段结构生成（characters/ + locations/ + scenes/）
- `assets/manifest.json` 已更新
- `video/clips.json` 已生成

### `completed`

- `post_pipeline` 批处理完成
- `subtitles/subtitles.json` 已生成
- `timeline/timeline.json` 已生成
- `outputs/final.mp4` 已渲染

### `failed`

- 任一阶段报错
- 必须记录失败阶段、失败原因和恢复建议

---

## Transitions

```text
created
  -> input_parsed          (creative_design)
  -> script_generated      (script_writer)
  -> audio_founded         (audio_pipeline)
  -> storyboard_planned    (beat_sync_storyboard_planner)
  -> asset_planned         (asset_planner)
  -> visuals_generated     (visual_pipeline)
  -> completed             (post_pipeline)

任意状态 -> failed
```

---

## 批处理命令参考

```bash
# 纯执行阶段 — 直接运行批处理脚本
python scripts/run_audio_pipeline.py   --project projects/<name>
python scripts/run_visual_pipeline.py  --project projects/<name>
python scripts/run_post_pipeline.py    --project projects/<name>

# Claude 推理阶段 — 由 Claude Code skill 触发，无需手动运行脚本
# creative_design / script_writer / beat_sync_storyboard_planner / asset_planner
```

---

## Failure Rules

- 任一阶段失败时，当前状态转为 `failed`
- 不得删除已完成阶段产物
- 失败事件必须写入 `events/events.jsonl`
- 恢复时只能从最后一个有效状态继续，或由操作者明确选择回退重跑

## Recovery Rules

- 如果输入产物有效，可从对应状态继续推进
- 如果输入产物损坏，必须先修复或重建，再恢复下游阶段
- 如果操作者手工修改了中间文件，后续阶段应基于修改后的文件继续
- 每次恢复判断都应追加主控决策到 `projects/<project>/orchestration/decisions.jsonl`

## Event Expectations

每次状态转移至少写一条事件：

- `workflow.state.changed`
- `workflow.stage.started`
- `workflow.stage.completed`
- `workflow.stage.failed`
