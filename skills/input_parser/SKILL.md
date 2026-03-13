# input_parser

## Purpose

将原始任务请求转换成标准化输入配置，作为整条听觉驱动视频生产链的统一起点。

## Reads

- `projects/<project>/request.md`
- 操作者补充的结构化参数，如时长、语言、画幅或风格要求

## Writes

- `projects/<project>/input/input.json`

## Required Output

`input.json` 至少应包含：

- `topic`
- `goal`
- `duration_seconds`
- `language`
- `aspect_ratio`
- `style`
- `music_emotion`
- `pacing_preference`
- `requires_voiceover`
- `requires_subtitles`

## Runtime Expectations

- 解析前写 `workflow.stage.started`
- 写入产物后写 `artifact.written`
- 完成时写 `workflow.stage.completed`
- 如果输入不完整，必须显式指出缺失字段，而不是静默猜测

## Failure Behavior

- 无法确定关键字段时中止阶段
- 写 `workflow.stage.failed`
- 保留原始 `request.md`
