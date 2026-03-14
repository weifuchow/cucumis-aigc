---
name: master-orchestrator
description: Inspect workflow state choose next stage and write orchestration decisions. Use for stage planning recovery and control flow.
---

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

1. `creative_design`
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

- 若尚未存在项目目录，主控第一步应创建 `project_id` 并初始化项目目录（可通过 `scripts/init_project.py` 自动生成）
- 主控必须优先读取 workflow 定义，而不是硬编码业务路径
- 主控写出的状态与计划必须可被脚本和人工同时读取
- 所有主控决策都应尽量落盘，而不是只存在于瞬时推理里
- 主控不应直接生成下游业务内容
- 主控在分镜及其后续阶段前，必须优先检查音频时间锚点是否已建立

## Context Hygiene

- 主线程只保留控制面信息：目标、阶段决策、风险与验收结论
- 长分析、批量代码阅读和重构执行优先交给子 agent
- 子 agent 输入必须最小化：任务目标 + 关键文件路径 + 验收标准
- 禁止把整段历史聊天原样转发给子 agent
- 每轮结束必须写入 `orchestration/decisions.jsonl`，必要时刷新 `review/observer-summary.md`
- 当主线程上下文变长时，先运行：
  - `python3 scripts/session_handoff.py --project <project-path>`
  - 再开新线程，仅用 handoff 文档续跑

## Subagent Policy

- 以下场景建议开启子 agent：
  - 跨多个目录的大规模分析
  - 大范围代码修改前的方案对比
  - 长日志定位与回归验证
- 以下场景不建议开启子 agent：
  - 单文件小改
  - 明确且短路径的命令执行
  - 需要连续人机确认的细粒度交互

## Failure Behavior

- 如果当前状态不足以安全推进，必须停止并写决策记录
- 如果检测到关键产物损坏，应输出恢复建议
- 失败时必须写 `workflow.stage.failed` 或等价事件

## Non-Goals

- 不实现完整自动 runner
- 不替代下游 skill 的业务逻辑
- 不做跨 workflow 的统一调度框架
