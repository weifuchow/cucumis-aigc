---
name: editorial-orchestrator
description: Orchestrate the material_editorial workflow for large, messy user-provided folders. Use when Codex needs resumable stage control, checkpoint management, context compaction, and batch-level delegation before any final generation.
---

# editorial_orchestrator

## Purpose

主控 `material_editorial` 工作流，负责：

- 判断当前恢复点
- 控制上下文只保留摘要层
- 决定下一阶段和待确认事项
- 管理 batch subtasks 与人工确认点

## Must Read First

- `workflows/material_editorial/WORKFLOW.md`
- `workflows/material_editorial/state-machine.md`
- `workflows/material_editorial/handoff-contracts.md`
- `projects/<project>/orchestration/task-card.md` if present
- `projects/<project>/orchestration/state.json`

## Writes

- `projects/<project>/orchestration/state.json`
- `projects/<project>/orchestration/checkpoints.json`
- `projects/<project>/orchestration/subtasks.json`
- `projects/<project>/orchestration/context-index.json`
- `projects/<project>/orchestration/task-card.md`
- `projects/<project>/orchestration/decisions.jsonl`

## Context Hygiene

- 主线程只读控制面和汇总文件
- `analysis/batches/*.json` 只在处理某个批次时按需读取
- 素材原文件不进入聊天上下文；只传路径与结构化摘要
- 上下文变长时，先刷新 `session-handoff.md` 再续跑

## Subagent Policy

- 可以把单个 batch 的理解交给子 agent
- 子 agent 输入必须最小化：
  - 一个 batch manifest
  - 明确输出路径
  - 验收标准
- 不允许子 agent 做最终阶段推进决策

## Recovery Policy

- 若 `subtasks.json` 里存在 `pending/failed` 批次，优先从这些批次恢复
- 若 checkpoint 未确认，停止在当前阶段并更新 task-card
- 若用户修改创意方向，记录决策并只刷新受影响摘要
