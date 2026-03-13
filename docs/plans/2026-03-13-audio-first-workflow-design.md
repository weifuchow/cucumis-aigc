# Audio-First Workflow Design

**Date:** 2026-03-13

## Purpose

将 `cucumis-aigc` 的默认标准流程从“视觉优先”重构为“听觉驱动”流程。新的默认流程以配音时间戳和 BGM 节点为时序锚点，后续分镜、关键帧、图片、动态视频和最终时间轴都围绕音频时间网格展开。

## New Default 12-Step Workflow

1. `input_parser`
2. `script_writer`
3. `audio_foundation`
4. `global_timeline_initializer`
5. `beat_sync_storyboard_planner`
6. `keyframe_planner`
7. `prompt_engineer`
8. `image_generator`
9. `constrained_video_generator`
10. `subtitle_asset_manager`
11. `timeline_builder`
12. `ffmpeg_renderer_reviewer`

## Core Principles

### Audio Before Visuals

`audio_foundation` 必须先于分镜阶段完成。配音时间戳和 BGM 转折点先锁定，画面不再提前自由发散。

### Global Time Grid First

在画面正式生成前，先生成 `global-timeline.json`。它是后续 scene 时长、切点和转场强度的全局约束。

### Beat-Sync Storyboarding

分镜必须严格对齐音频时间网格。scene 时长是刚性输入，不再只是“预计时长”。

### Constrained Visual Execution

图片和视频生成接受明确时长、动作意图和情绪节点约束，而不是后置补时间。

## Scope of First Executable Iteration

本次真正做到可执行的范围是前 1 到 5 步：

1. `input_parser`
2. `script_writer`
3. `audio_foundation`
4. `global_timeline_initializer`
5. `beat_sync_storyboard_planner`

后 6 到 12 步本次只完成命名、职责、workflow、schema 和模板对齐，不要求全部做深实现。

## Repository Refactor

### Workflow

`workflows/video_pipeline/` 改写为新的听觉驱动流程，旧的默认顺序废弃。

### Skills

保留：

- `input_parser`
- `script_writer`
- `keyframe_planner`
- `image_generator`
- `timeline_builder`

新增或替换为：

- `audio_foundation`
- `global_timeline_initializer`
- `beat_sync_storyboard_planner`
- `prompt_engineer`
- `constrained_video_generator`
- `subtitle_asset_manager`
- `ffmpeg_renderer_reviewer`

### Orchestrator

`master_orchestrator` 的默认主链同步改为新的 12 步，其中前 1 到 5 步是当前最小可执行主链。

## Data Model Changes

### Script Output

`script/script.json` 除了听觉轨和视觉轨，还要包含：

- `emotion_markers`
- `turning_points`
- 带情绪标签的 narration 段

### Audio Outputs

新增 `audio/` 下的结构化产物：

- `voiceover.json`
- `bgm-selection.json`
- `beat-grid.json`

### Global Timeline

新增：

- `timeline/global-timeline.json`

其内容至少包括：

- narration windows
- bgm anchors
- transition windows
- reserved silence gaps
- scene timing slots

### Storyboard Output

`storyboard/storyboard.json` 改为严格时序分镜，至少包含：

- `start_time`
- `end_time`
- `duration_seconds`
- `beat_alignment`
- `transition_intent`
- `motion_intent`

## First Executable Skills

### `input_parser`

输出标准输入时必须包含音乐情绪诉求与节奏偏好。

### `script_writer`

升级为“脚本生成 + 情绪标注”。

### `audio_foundation`

第一版不接真实音频模型，但必须生成 mock 的：

- `voiceover.json`
- `bgm-selection.json`
- `beat-grid.json`

### `global_timeline_initializer`

读取音频基建结果，生成 `timeline/global-timeline.json`。

### `beat_sync_storyboard_planner`

读取脚本和全局时间网格，输出带严格时间约束的分镜。

## Non-Goals

- 不在本次实现真实 TTS
- 不在本次接入真实 BGM 检索与鼓点分析
- 不在本次做后 6 到 12 步的深实现
- 不并行保留旧默认流程
