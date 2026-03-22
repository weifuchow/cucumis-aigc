---
name: observer
description: Check project health and summarize progress into readable report. Combines readiness check and human-visible status overview. Use for production readiness checks or status visibility.
---

# observer（原 observer + reviewer 合并）

## Purpose

一次运行同时输出两份结果：

1. **健康检查**（原 reviewer）：验证项目结构完整性、state 与产物是否一致、是否可安全推进
2. **进度摘要**（原 observer）：生成人类可读的项目状态报告，含阶段进度、关键产物、下一步建议

## Reads

- `projects/<project>/orchestration/state.json`
- `projects/<project>/orchestration/plan.json`
- `projects/<project>/orchestration/decisions.jsonl`
- `projects/<project>/events/events.jsonl`
- `projects/<project>/` 下关键产物目录

## Writes

- `projects/<project>/review/review-report.json`（健康检查结构化结果）
- `projects/<project>/review/observer-summary.md`（人类可读摘要）

## 健康检查规则

### 1. Structure Exists
检查关键路径存在，尤其是当前阶段所需产物。

### 2. State Is Consistent
`completed_stages`、`current_stage`、`next_stage` 与目录事实必须一致，不允许状态声称完成但产物缺失。

### 3. Next Step Is Clear
报告必须给出 `next_recommended_action`，不允许只列问题不给操作建议。

## 健康状态模型

- `ready`：结构健康，可推进下一步
- `in_progress`：处理中，无明确阻塞
- `blocked`：状态与文件事实冲突，或关键产物缺失

## 进度摘要结构

1. 项目概览
2. 阶段进度
3. 关键产物列表（路径，不读取内容）
4. 最近决策
5. 健康检查结论
6. 下一步建议

## Non-Goals

- 不做内容质量评分
- 不做自动修复
- 不读取图片/视频文件内容
