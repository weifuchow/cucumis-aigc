# ffmpeg_renderer

## Purpose

接收统一时间轴并生成本地渲染计划。第一版可以只输出 render plan 或占位结果，不强制产出真实视频文件。

## Reads

- `projects/<project>/timeline/timeline.json`

## Writes

- `projects/<project>/outputs/render-plan.json`
- `projects/<project>/outputs/final.mp4` in later iterations

## Required Output

`render-plan.json` 至少应包含：

- `inputs`
- `operations`
- `expected_output`

## Runtime Expectations

- 本 skill 是渲染出口，不应回写上游内容结构
- 第一版优先保证计划结构和落盘行为稳定
- 后续真实 FFmpeg 命令拼装可以逐步接入

## Failure Behavior

- 时间轴缺失或无效时必须中止
- 必须写失败事件，不得静默退出
