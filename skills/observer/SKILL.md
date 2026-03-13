# observer

## Purpose

汇总项目状态、关键产物、最近决策和最近审查结果，生成一份人类可直接阅读的项目摘要。

## Reads

- `projects/<project>/orchestration/state.json`
- `projects/<project>/orchestration/plan.json`
- `projects/<project>/orchestration/decisions.jsonl`
- `projects/<project>/review/review-report.json`
- `projects/<project>/` 下关键产物

## Writes

- `projects/<project>/review/observer-summary.md`

## Summary Structure

第一版摘要固定包含：

1. 项目概览
2. 阶段进度
3. 关键产物
4. 最近决策
5. 审查结果
6. 下一步建议

## Non-Goals

- 不做实时 UI
- 不做复杂图表
- 不修改任何项目事实文件
