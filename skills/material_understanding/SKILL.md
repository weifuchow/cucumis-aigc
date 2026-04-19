---
name: material-understanding
description: Generate compact metadata summaries and relationship drafts for each material batch, then consolidate them into project-level catalogs. Use after material_ingest.
---

# material_understanding

## Purpose

逐 batch 生成素材摘要，并汇总成全局素材目录与关系图。

## Reads

- `analysis/batches/<batch>.manifest.json`
- `orchestration/subtasks.json`

## Writes

- `analysis/batches/<batch>.catalog.json`
- `analysis/batches/<batch>.relationships.json`
- `analysis/material-catalog.json`
- `analysis/relationship-graph.json`
- `analysis/style-report.json`

## Commands

```bash
python3 scripts/run_material_batch_understanding.py --project <project>
python3 scripts/run_material_batch_understanding.py --project <project> --all-pending
python3 scripts/run_material_batch_understanding.py --project <project> --batch-id batch-001
```

## Rules

- 主线程优先读汇总文件
- 单个 batch 需要深挖时，再读对应 batch 产物
- 如果所有 batch 已完成，应把 checkpoint 切换到待人工确认
