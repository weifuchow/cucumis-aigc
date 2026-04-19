---
name: material-ingest
description: Scan a user-provided material folder, build a source manifest, and split assets into resumable analysis batches. Use at the start of the material_editorial workflow.
---

# material_ingest

## Purpose

把用户提供的素材目录扫描成可恢复、可分片的结构化输入。

## Reads

- 用户提供的素材目录路径

## Writes

- `assets/source-manifest.json`
- `analysis/batches/*.manifest.json`
- `orchestration/checkpoints.json`
- `orchestration/subtasks.json`
- `orchestration/context-index.json`

## Command

```bash
python3 scripts/run_material_ingest.py --project <project> --source-dir <folder>
```

## Notes

- batch 默认按目录和媒体类型切分
- 目标是让后续理解阶段只处理单个 batch，而不是整包素材
