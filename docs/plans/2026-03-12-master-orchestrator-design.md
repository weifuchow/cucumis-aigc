# Master Orchestrator Design

**Date:** 2026-03-12

## Purpose

为 `cucumis-aigc` 增加第一版主控 skill 设计。该主控不是通用应用服务，而是依托 Codex / Claude Code 运行的轻度主控 skill，用于解释 workflow 规则、判断当前阶段、记录编排决策并提供恢复建议。

## Positioning

`master_orchestrator` 的角色是“有判断能力的调度者”，不是吞并下游业务逻辑的超级 skill。

它负责：

- 读取项目当前状态
- 读取目标 workflow 定义
- 判断当前应执行哪个阶段
- 根据输入条件决定某些阶段是否跳过
- 写入主控决策日志
- 在失败时给出恢复建议

它不负责：

- 直接生成脚本、分镜、时间轴内容
- 替代下游 skill 的领域判断
- 变成自由规划的一体化黑盒

## Control Model

第一版采用“固定主链 + 条件跳过”模型。

默认主链：

1. `input_parser`
2. `script_writer`
3. `storyboard_planner`
4. `timeline_builder`
5. `ffmpeg_renderer`

控制能力包括：

- 判断能否进入下一阶段
- 根据输入条件跳过可选阶段
- 在失败后判断恢复起点

## Main Outputs

主控专属产物统一落到：

`projects/<project>/orchestration/`

### `state.json`

记录当前状态快照，例如：

- 当前阶段
- 已完成阶段
- 跳过阶段
- 最后失败阶段
- 下一个候选阶段

### `plan.json`

记录当前执行计划，例如：

- 工作流名称
- 预计执行阶段
- 可选阶段
- 当前禁用阶段

### `decisions.jsonl`

记录关键编排决策，例如：

- 为什么跳过某个阶段
- 为什么从某个阶段恢复
- 为什么判定可以进入下一阶段

## Reads

- `workflows/video_pipeline/WORKFLOW.md`
- `workflows/video_pipeline/state-machine.md`
- `workflows/video_pipeline/handoff-contracts.md`
- `projects/<project>/` 下已有产物
- `projects/<project>/orchestration/state.json` if present
- `projects/<project>/input/input.json` or `request.md`

## Writes

- `projects/<project>/orchestration/state.json`
- `projects/<project>/orchestration/plan.json`
- `projects/<project>/orchestration/decisions.jsonl`
- `projects/<project>/events/events.jsonl`

## New Repository Elements

### Skill

- `skills/master_orchestrator/SKILL.md`

### Schemas

- `schemas/orchestration-state.schema.json`
- `schemas/orchestration-plan.schema.json`
- `schemas/orchestration-decision.schema.json`

### Template Additions

- `templates/project/orchestration/state.json`
- `templates/project/orchestration/plan.json`
- `templates/project/orchestration/decisions.jsonl`

### Scripts

- `scripts/inspect_project.py`
- `scripts/update_orchestration_state.py`

## Script Responsibilities

### `inspect_project.py`

读取项目目录，判断哪些关键产物存在，输出当前可见状态，用于主控判断当前阶段和恢复点。

### `update_orchestration_state.py`

写入或更新 `state.json`、`plan.json`，并在需要时向 `decisions.jsonl` 追加决策记录。

## Workflow Integration

`workflows/video_pipeline/` 应明确声明：该 workflow 默认由 `master_orchestrator` 解释和推进。

## First Iteration Goal

第一版只建立主控的规则定义、产物契约和辅助脚本，不做完整自动 runner。

也就是说，第一版目标是：

- 主控 skill 文档存在
- 主控状态 schema 存在
- 项目模板支持 orchestration 目录
- 可以检查项目当前状态
- 可以写入主控状态与决策

## Non-Goals

- 不做自动调用全部下游 skill 的总执行器
- 不做复杂重试策略
- 不做跨 workflow 的统一调度框架
- 不把主控逻辑写成与 workflow 强耦合的黑盒脚本
