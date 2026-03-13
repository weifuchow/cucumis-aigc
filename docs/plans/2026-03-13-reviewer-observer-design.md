# Reviewer Observer Design

**Date:** 2026-03-13

## Purpose

为 `cucumis-aigc` 设计第一版 `reviewer / observer` 层。该层的目标不是做 UI，而是建立稳定的项目审查结果和项目状态摘要产物，使主控、操作者和后续脚本都能消费这些结果。

## Positioning

采用“弱分离”模型：

- `reviewer` 负责检查项目是否健康、是否可继续推进，并生成结构化报告
- `observer` 负责汇总项目状态、最近决策和最近审查结果，生成一份人可读摘要

## Output Location

两者统一落到：

`projects/<project>/review/`

### `review-report.json`

结构化审查结果，供主控或脚本消费。

建议至少包含：

- `project`
- `status`
- `checked_at`
- `completed_stages`
- `missing_artifacts`
- `warnings`
- `next_recommended_action`

其中 `status` 第一版限定为：

- `ready`
- `in_progress`
- `blocked`

### `observer-summary.md`

面向人的摘要，供直接阅读。

建议包含：

1. 项目概览
2. 阶段进度
3. 关键产物
4. 最近决策
5. 审查结果
6. 下一步建议

## Repository Changes

### Skills

- `skills/reviewer/SKILL.md` 从占位升级为正式定义
- `skills/observer/SKILL.md` 从占位升级为正式定义

### Schema

- `schemas/review-report.schema.json`

### Templates

- `templates/project/review/review-report.json`
- `templates/project/review/observer-summary.md`

### Scripts

- `scripts/review_project.py`
- `scripts/observe_project.py`

## Reviewer Rules

第一版只做“生产可推进性检查”，不做主观内容质量判断。

### Rule Layer 1: Structure Exists

检查关键路径是否存在，例如：

- `events/events.jsonl`
- `orchestration/state.json`
- `orchestration/plan.json`
- `input/input.json`

并在阶段已完成时检查对应产物是否存在，例如：

- 已完成 `script_writer` 时，要求 `script/script.json`
- 已完成 `storyboard_planner` 时，要求 `storyboard/storyboard.json`
- 已完成 `timeline_builder` 时，要求 `timeline/timeline.json`

### Rule Layer 2: State Is Consistent

检查主控状态与文件事实是否矛盾，例如：

- 状态声称某阶段完成，但对应文件不存在
- `next_stage` 指向下游阶段，但前置产物未准备好
- `last_failed_stage` 存在，但报告中没有阻塞说明

### Rule Layer 3: Next Step Is Clear

报告必须明确给出当前项目是：

- `ready`
- `in_progress`
- `blocked`

并给出一个明确下一步建议。

## Observer Responsibilities

`observer` 第一版只做事实汇总和 Markdown 生成，不做实时 UI。

它应读取：

- 项目当前状态
- 已完成阶段
- 缺失产物
- 最近主控决策
- 最近审查结果

并写出一份稳定的 `observer-summary.md`。

## Integration

`reviewer` 的 `review-report.json` 应可被 `observer` 和 `master_orchestrator` 共同消费。

`observer-summary.md` 应保持人类可直接阅读，不强行结构化。

## Non-Goals

- 不做 Web 页面
- 不做复杂评分系统
- 不做主观内容质量评估
- 不做自动修复
