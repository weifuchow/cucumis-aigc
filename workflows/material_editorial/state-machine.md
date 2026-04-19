# Material Editorial State Machine

## States

### `created`

- 项目已初始化
- 尚未扫描用户素材目录

### `materials_indexed`

- `assets/source-manifest.json` 已生成
- batch manifests 已写入 `analysis/batches/`
- `orchestration/subtasks.json` 已初始化

### `materials_understood`

- 所有 batch 已完成理解
- `analysis/material-catalog.json` 与 `analysis/relationship-graph.json` 可读

### `editorial_planning`

- 正在做创意对齐、分镜草案或调整方案
- 必须依赖人工确认点推进

### `ready_for_audio`

- 前置编导链已确认通过
- 可以进入 `audio_foundation`

### `completed`

- 已跑完音频与时间轴收尾流程

### `failed`

- 任一阶段失败
- 必须记录失败阶段、恢复建议和可复用产物

## Recovery Rules

- 任何恢复都先看 `orchestration/task-card.md`
- `material_batch_understanding` 只重跑未完成 batch
- `relationship_mapping` 之后的阶段必须尊重已确认 checkpoint
- 一旦用户重新指定创意方向，受影响的摘要文件应标记过期并重新生成
