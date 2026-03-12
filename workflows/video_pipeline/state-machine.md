# Video Pipeline State Machine

## State Model

`video_pipeline` 采用阶段推进式状态机。每个阶段只有在前置产物满足要求时才允许进入执行状态。

状态推进的判断者默认是 `master_orchestrator`，并应将其快照写入 `projects/<project>/orchestration/state.json`。

## States

### `created`

- 项目目录已初始化
- 必需模板已落盘
- 尚未开始任何 skill

### `input_parsed`

- `input/input.json` 已生成
- 输入已满足下游脚本生成的最低要求

### `script_generated`

- `script/script.json` 已生成
- 听觉轨与视觉轨已落盘

### `storyboard_planned`

- `storyboard/storyboard.json` 已生成
- scene 列表可供时间轴阶段消费

### `timeline_built`

- `timeline/timeline.json` 已生成
- 渲染层所需的最小结构已齐备

### `render_planned`

- `outputs/render-plan.json` 已生成
- 第一版允许渲染器只输出占位计划，而不是最终视频

### `completed`

- 本轮工作流执行完成
- 关键产物和事件日志存在

### `failed`

- 任一阶段报错
- 必须记录失败阶段、失败原因和恢复建议

## Transitions

```text
created
  -> input_parsed
  -> script_generated
  -> storyboard_planned
  -> timeline_built
  -> render_planned
  -> completed

created/input_parsed/script_generated/storyboard_planned/timeline_built/render_planned
  -> failed
```

## Failure Rules

- 任一阶段失败时，当前状态转为 `failed`
- 不得删除已完成阶段产物
- 失败事件必须写入 `events/events.jsonl`
- 恢复时只能从最后一个有效状态继续，或由操作者明确选择回退重跑

## Recovery Rules

- 如果输入产物有效，可从对应状态继续推进
- 如果输入产物损坏，必须先修复或重建，再恢复下游阶段
- 如果操作者手工修改了中间文件，后续阶段应基于修改后的文件继续
- 每次恢复判断都应追加主控决策到 `projects/<project>/orchestration/decisions.jsonl`

## Event Expectations

每次状态转移至少写一条事件：

- `workflow.state.changed`
- `workflow.stage.started`
- `workflow.stage.completed`
- `workflow.stage.failed`
