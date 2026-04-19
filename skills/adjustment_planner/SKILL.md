---
name: adjustment-planner
description: Produce shot-level adjustment recommendations for user-provided materials, including filters, crops, AI edits, manual pickup needs, and prompt logging requirements. Use after storyboard_draft.
---

# adjustment_planner

## Purpose

根据分镜草案输出逐镜头调整方案，明确：

- 直接使用
- 滤镜/调色/裁切
- 轻微图像或视频模型调整
- 需要人工补拍或补图
- prompt 与模型入参如何落盘

## Reads

- `storyboard/storyboard-draft.json`
- `analysis/style-report.json`
- `analysis/material-catalog.json`

## Writes

- `adjustments/adjustment-plan.json`
- `prompts/prompt-ledger.json`
