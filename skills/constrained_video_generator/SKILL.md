# constrained_video_generator

## Purpose

在明确时长和运动意图约束下生成动态视频片段，保证镜头动态与情绪节点和 BGM 转折点一致。

## Reads

- `projects/<project>/storyboard/storyboard.json`
- `projects/<project>/input/input.json`

## Writes

- `projects/<project>/video/clips.json`
- `projects/<project>/video/requests.json`
- `projects/<project>/video/usage.json`
- `projects/<project>/costs/poe-usage.jsonl`

## Runtime Expectations

- 项目级默认模型来自 `input/input.json` 的 `video_model`
- 第一版通过 Poe API 或本地 mock fallback 生成逐镜头视频片段
- 输出必须保留 scene 与 request 的映射关系
