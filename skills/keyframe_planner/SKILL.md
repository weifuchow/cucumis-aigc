---
name: keyframe-planner
description: Generate keyframe anchors for each storyboard scene. Use before prompt engineering and image generation.
---

# keyframe_planner

## Purpose

为每个 scene 定义关键视觉锚点，作为后续图像与动态视频生成的统一视觉约束。

## Status

第一版已可执行，输出稳定 mock 关键帧锚点用于后续提示词阶段调试。

## Planned Reads

- `projects/<project>/storyboard/storyboard.json`

## Planned Writes

- `projects/<project>/keyframes/keyframes.json`

## Runtime Expectations

- 每个 storyboard scene 至少生成一个 keyframe
- keyframe 必须带 `scene_id` 和 `timestamp`
- 输出 JSON 必须可解析并可被 `prompt_engineer` 直接消费
