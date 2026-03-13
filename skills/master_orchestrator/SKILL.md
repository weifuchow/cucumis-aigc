# master_orchestrator

## Purpose

`master_orchestrator` 是第一版轻度主控 skill。它负责解释 workflow 规则、检查项目当前状态、决定下一阶段、记录主控决策，并在失败时提供恢复建议。

## Reads

- `workflows/video_pipeline/WORKFLOW.md`
- `workflows/video_pipeline/state-machine.md`
- `workflows/video_pipeline/handoff-contracts.md`
- `projects/<project>/request.md`
- `projects/<project>/input/input.json` if present
- `projects/<project>/orchestration/state.json` if present
- `projects/<project>/` 下已有产物

## Writes

- `projects/<project>/orchestration/state.json`
- `projects/<project>/orchestration/plan.json`
- `projects/<project>/orchestration/decisions.jsonl`
- `projects/<project>/events/events.jsonl`

## Responsibilities

- 判断当前 workflow 的真实状态
- 基于固定主链选择下一阶段
- 根据输入配置或已有产物跳过可选阶段
- 记录每次关键编排决策
- 在失败时输出恢复建议

## Control Model

第一版采用“固定主链 + 条件跳过”模型，默认主链为：

1. `input_parser`
2. `script_writer`
3. `audio_foundation`
4. `global_timeline_initializer`
5. `beat_sync_storyboard_planner`
6. `keyframe_planner`
7. `prompt_engineer`
8. `image_generator`
9. `constrained_video_generator`
10. `subtitle_asset_manager`
11. `timeline_builder`
12. `ffmpeg_renderer_reviewer`

## Required Outputs

### `orchestration/state.json`

记录当前状态快照，例如：

- `current_stage`
- `completed_stages`
- `skipped_stages`
- `last_failed_stage`
- `next_stage`

### `orchestration/plan.json`

记录本次执行计划，例如：

- `workflow`
- `planned_stages`
- `optional_stages`
- `disabled_stages`

### `orchestration/decisions.jsonl`

按 JSON Lines 记录关键编排决策，例如：

- 为什么跳过某个阶段
- 为什么从某个阶段恢复
- 为什么判定可以进入下一阶段

## Runtime Expectations

- 主控必须优先读取 workflow 定义，而不是硬编码业务路径
- 主控写出的状态与计划必须可被脚本和人工同时读取
- 所有主控决策都应尽量落盘，而不是只存在于瞬时推理里
- 主控不应直接生成下游业务内容
- 主控在分镜及其后续阶段前，必须优先检查音频时间锚点是否已建立

## Failure Behavior

- 如果当前状态不足以安全推进，必须停止并写决策记录
- 如果检测到关键产物损坏，应输出恢复建议
- 失败时必须写 `workflow.stage.failed` 或等价事件

## Non-Goals

- 不实现完整自动 runner
- 不替代下游 skill 的业务逻辑
- 不做跨 workflow 的统一调度框架
