# storyboard_planner

## Purpose

将脚本拆解为 scene 级分镜结构，明确每段画面的目标、节奏和素材需求。

## Reads

- `projects/<project>/script/script.json`

## Writes

- `projects/<project>/storyboard/storyboard.json`

## Required Output

`storyboard.json` 至少应包含 `scenes` 列表。每个 scene 至少包含：

- `scene_id`
- `purpose`
- `visual_description`
- `estimated_duration_seconds`
- `asset_mode`
- `subtitle_text`

## Runtime Expectations

- 每个 scene 都应可被下游时间轴阶段单独消费
- `asset_mode` 需要明确是静态、动态或混合
- 输出结构必须稳定，便于后续 schema 校验

## Failure Behavior

- 脚本缺失关键信息时必须报错
- 不允许输出没有 scene 标识的分镜结构
