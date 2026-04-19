# Material Editorial Handoff Contracts

## Global Rules

- 所有控制面状态都写入 `orchestration/`
- 所有素材理解结果都写入 `analysis/`
- 每个 batch 都必须可单独消费，不依赖完整历史聊天

## Stage Contracts

### `material_ingest`

**Reads**
- 用户提供的素材目录

**Writes**
- `assets/source-manifest.json`
- `analysis/batches/*.manifest.json`
- `orchestration/checkpoints.json`
- `orchestration/subtasks.json`
- `orchestration/context-index.json`

### `material_batch_understanding`

**Reads**
- `analysis/batches/<batch>.manifest.json`

**Writes**
- `analysis/batches/<batch>.catalog.json`
- `analysis/batches/<batch>.relationships.json`
- `analysis/material-catalog.json`
- `analysis/relationship-graph.json`
- `analysis/style-report.json`

### `relationship_mapping`

**Reads**
- `analysis/material-catalog.json`
- `analysis/relationship-graph.json`

**Writes**
- `analysis/relationship-graph.json`（修订）
- `brief/creative-fit-report.json`

### `storyboard_draft`

**Reads**
- `analysis/material-catalog.json`
- `brief/creative-fit-report.json`

**Writes**
- `storyboard/storyboard-draft.json`

### `adjustment_planning`

**Reads**
- `storyboard/storyboard-draft.json`
- `analysis/style-report.json`

**Writes**
- `adjustments/adjustment-plan.json`
- `prompts/prompt-ledger.json`

## Validation Expectations

- 任一 batch 输出损坏，不得推进到汇总阶段
- 未通过 checkpoint，不得推进到 `audio_foundation`
- 子 agent 输出必须是结构化文件，不接受仅存在聊天里的结论
