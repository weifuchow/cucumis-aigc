---
name: reviewer
description: Assess project readiness missing artifacts and next action into structured review report. Use for production readiness checks.
---

# reviewer

## Purpose

检查项目当前是否健康、是否可继续推进，并将结果写成结构化报告，供主控、脚本和操作者消费。

## Scope

第一版只做“生产可推进性检查”，不做主观内容质量评分。

## Reads

- `projects/<project>/events/events.jsonl`
- `projects/<project>/orchestration/state.json`
- `projects/<project>/orchestration/plan.json`
- `projects/<project>/orchestration/decisions.jsonl`
- `projects/<project>/` 下关键产物

## Writes

- `projects/<project>/review/review-report.json`

## Status Model

- `ready`: 当前结构健康，可继续推进下一步
- `in_progress`: 仍在处理中，但没有明确阻塞
- `blocked`: 状态与文件事实冲突，或关键产物缺失

## Review Rules

### 1. Structure Exists

检查关键路径是否存在，尤其是事件、主控状态和 workflow 当前阶段所需产物。

### 2. State Is Consistent

检查 `completed_stages`、`current_stage`、`next_stage` 与目录事实是否一致，不允许状态宣称阶段完成但产物缺失。

### 3. Next Step Is Clear

报告必须给出明确的 `next_recommended_action`，避免审查结果只指出问题而不给操作建议。

## Non-Goals

- 不做文案质量判断
- 不做分镜创意评分
- 不做自动修复
