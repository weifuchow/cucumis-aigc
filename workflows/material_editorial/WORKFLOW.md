# Material Editorial Workflow

## Purpose

`material_editorial` 面向“用户提供杂乱素材文件夹”的前置编导链。目标不是立即生成，而是先理解素材、建立关系、输出分镜草案与调整方案，并在关键处等待人工确认。

## Design Goals

- 可恢复：任何阶段中断后，都能从 `orchestration/` 产物续跑
- 控上下文：主线程只看摘要文件，不回读全量素材
- 可分片：素材按 batch 拆分，允许子 agent 或脚本并行理解
- 可审计：每次素材理解、关系判断、调整建议都要落盘

## 主链

```text
1. material_ingest
2. material_batch_understanding
3. relationship_mapping
4. creative_alignment
5. storyboard_draft
6. adjustment_planning
7. human_checkpoints
8. audio_foundation
9. timeline_builder
```

## Stage Summary

### 1. `material_ingest`

- 扫描用户素材目录
- 生成 `assets/source-manifest.json`
- 按目录和媒体类型切分 `analysis/batches/*.manifest.json`
- 初始化 `orchestration/checkpoints.json`、`orchestration/subtasks.json`、`orchestration/context-index.json`

### 2. `material_batch_understanding`

- 逐 batch 生成素材摘要和关系草稿
- 每个 batch 单独写出，避免一次性读全量素材
- 汇总到 `analysis/material-catalog.json`、`analysis/relationship-graph.json`、`analysis/style-report.json`

### 3. `relationship_mapping`

- 复核并整理人物、地点、事件、时间线关系
- 标记冲突、重复、桥接缺口

### 4. `creative_alignment`

- 将用户创意目标和现有素材能力对齐
- 输出哪些段落可直接讲通，哪些需要补素材或 AI 调整

### 5. `storyboard_draft`

- 在已确认的素材关系基础上生成完整分镜草案
- 明确每段素材用途、时长、字幕和旁白意图

### 6. `adjustment_planning`

- 为每个镜头输出调整建议
- 包括滤镜、裁切、转场、字幕样式、图像/视频微调、需人工补拍项
- 所有 AI 修改入参写入 `prompts/prompt-ledger.json`

### 7. `human_checkpoints`

- 关键确认点：
  - 素材扫描范围
  - 素材理解
  - 关系链
  - 分镜草案
  - 调整方案
- 任一未确认，禁止进入生成与渲染阶段

### 8. `audio_foundation`

- 复用现有音频基建
- 只在前置编导链确认完成后执行

### 9. `timeline_builder`

- 复用现有字幕、时间轴和渲染能力
- 仅消费已确认的分镜和素材调整方案

## Control Surface

主线程始终只保留以下控制面文件：

- `orchestration/task-card.md`
- `orchestration/state.json`
- `orchestration/checkpoints.json`
- `orchestration/subtasks.json`
- `orchestration/context-index.json`

长分析结果写在 `analysis/`，按需读取。

## Subagent Policy

- 允许把单个 batch 的理解任务交给子 agent
- 禁止把全量聊天历史或整个项目目录直接塞给子 agent
- 子 agent 输入最小化：
  - 任务目标
  - 单个 batch manifest 路径
  - 输出路径
  - 验收标准

## Resume Rules

- 恢复时先读 `task-card.md` 与 `state.json`
- 如存在未完成 batch，仅重跑 `orchestration/subtasks.json` 中 `pending/failed` 项
- 已完成 batch 不重复理解
- 创意改变时，只让受影响的摘要文件失效，不全量重做
