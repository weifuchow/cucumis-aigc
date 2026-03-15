---
name: constrained-video-generator
description: Generate constrained video clip metadata from storyboard scenes and project model settings. Use when producing video clips usage and request artifacts.
---

# constrained_video_generator

## Purpose

在明确时长和运动意图约束下生成动态视频片段，保证镜头动态与情绪节点和 BGM 转折点一致。

**执行前应先审查 storyboard 的 asset_mode/motion_intent，确认哪些场景真正需要调用视频模型，哪些可以用本地静态合成节省成本。**

## Reads

- `projects/<project>/storyboard/storyboard.json`
- `projects/<project>/input/input.json`
- `projects/<project>/assets/manifest.json`（可选，判断是否有可用图片素材）

## Writes

- `projects/<project>/video/clips.json`
- `projects/<project>/video/requests.json`
- `projects/<project>/video/usage.json`
- `projects/<project>/costs/poe-usage.jsonl`

## 关键决策：哪些场景需要调视频模型

脚本已内置规则分流，但 Claude 应在执行前做一次语义复核，判断 storyboard 的分类是否合理。

### 分流逻辑

```
场景需要调视频模型（asset_mode=mixed）：
- motion_intent ∈ {fast_push, black_flash, whip_pan, handheld}
- visual_description 描述真实运动（爆炸、飞行、追逐、坠落）
- 场景是情绪高点或叙事转折点

场景可以本地静态合成（asset_mode=static）：
- motion_intent ∈ {hold, slow_pan, locked, static}
- 叙述性/信息性场景（旁白、数据展示、建立镜头）
- 时长 ≤ 2s
- 已有对应的生成图片素材
```

### 发现 storyboard 分类不合理时

如果 storyboard 中某个场景的 `asset_mode=mixed` 但内容明显是叙述性的（或反之），Claude 应：
1. 在执行前修正该场景的 `asset_mode` 和 `motion_intent`
2. 将修正记录到 `orchestration/decisions.jsonl`
3. 再执行脚本

## Runtime Expectations

- 调用 `python scripts/run_constrained_video_generator.py --project <name>`
- 项目级默认模型来自 `input/input.json` 的 `video_model`
- 脚本会自动分流：static 场景走 FFmpeg，dynamic 场景调 Poe API
- 输出必须保留 scene 与 request 的映射关系
- `video/requests.json` 的 `strategy` 字段记录了静态/动态场景数量，可用于验证分流结果
