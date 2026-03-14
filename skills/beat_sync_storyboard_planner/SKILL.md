---
name: beat-sync-storyboard-planner
description: Generate a beat aligned storyboard from script and global timeline artifacts. Use when scene timing must follow audio rhythm.
---

# beat_sync_storyboard_planner

## Purpose

基于脚本和全局时间网格生成严格踩点的分镜结构，确保 scene 时长、转场意图和动作节奏对齐音频节点。

## Reads

- `projects/<project>/script/script.json`
- `projects/<project>/timeline/global-timeline.json`

## Writes

- `projects/<project>/storyboard/storyboard.json`

## Required Output

每个 scene 至少包含：

- `scene_id`
- `start_time`
- `end_time`
- `duration_seconds`
- `beat_alignment`
- `transition_intent`
- `motion_intent`
- `visual_description`
