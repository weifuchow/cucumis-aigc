# timeline_builder

## Purpose

把分镜结构和素材引用整合为渲染器无关的时间轴，作为渲染层唯一可信输入。

## Reads

- `projects/<project>/storyboard/storyboard.json`
- `projects/<project>/assets/manifest.json` if present

## Writes

- `projects/<project>/timeline/timeline.json`

## Required Output

`timeline.json` 至少应包含：

- `metadata`
- `tracks`
- `segments`
- `output`

## Runtime Expectations

- 时间轴必须可由后续渲染阶段直接消费
- 第一版允许素材引用为空或为占位值，但结构必须完整
- 需要明确每个 segment 的时间区间与关联 scene

## Failure Behavior

- 如果缺少可用分镜结构，必须终止
- 不允许写出无法解析的时间轴 JSON
