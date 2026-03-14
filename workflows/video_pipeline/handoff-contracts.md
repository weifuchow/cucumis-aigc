# Video Pipeline Handoff Contracts

## Purpose

该文档定义主工作流中每个阶段的输入、输出和事件契约，避免 skill 之间通过隐式约定耦合。

## Global Rules

- 所有输入输出路径都相对于 `projects/<project-name>/`
- 所有结构化文件优先使用 JSON
- 所有阶段都必须写事件到 `events/events.jsonl`
- 主控自己的状态、计划和决策统一写到 `orchestration/`
- 阶段产物一旦写出，就应能被后续阶段独立消费

## Stage Contracts

### `creative_brief_intake`

**Reads**
- 客户初始自然语言诉求（通常在 `request.md`）
- `request.md`（若已有草稿）

**Writes**
- `brief/creative-brief.md`
- `brief/intake.json`
- `request.md`（标准化覆盖）

**Emits**
- `workflow.stage.started`
- `artifact.written`
- `workflow.stage.completed`

### `input_parser`

**Reads**
- `request.md`（优先使用标准化 creative brief）

**Writes**
- `input/input.json`

**Emits**
- `workflow.stage.started`
- `artifact.written`
- `workflow.stage.completed`

### `script_writer`

**Reads**
- `input/input.json`

**Writes**
- `script/script.json`

**Emits**
- `workflow.stage.started`
- `artifact.written`
- `workflow.stage.completed`

### `audio_foundation`

**Reads**
- `script/script.json`

**Writes**
- `audio/voiceover.json`
- `audio/bgm-selection.json`
- `audio/beat-grid.json`

**Emits**
- `workflow.stage.started`
- `artifact.written`
- `workflow.stage.completed`

### `global_timeline_initializer`

**Reads**
- `audio/voiceover.json`
- `audio/beat-grid.json`
- `audio/bgm-selection.json`

**Writes**
- `timeline/global-timeline.json`

**Emits**
- `workflow.stage.started`
- `artifact.written`
- `workflow.stage.completed`

### `beat_sync_storyboard_planner`

**Reads**
- `script/script.json`
- `timeline/global-timeline.json`

**Writes**
- `storyboard/storyboard.json`

**Emits**
- `workflow.stage.started`
- `artifact.written`
- `workflow.stage.completed`

### `keyframe_planner`

**Reads**
- `storyboard/storyboard.json`

**Writes**
- `keyframes/keyframes.json`

**Emits**
- `workflow.stage.started`
- `artifact.written`
- `workflow.stage.completed`

### `prompt_engineer`

**Reads**
- `storyboard/storyboard.json`
- `keyframes/keyframes.json`

**Writes**
- `prompts/prompts.json`

**Emits**
- `workflow.stage.started`
- `artifact.written`
- `workflow.stage.completed`

### `image_generator`

**Reads**
- `prompts/prompts.json`

**Writes**
- `assets/manifest.json`
- `assets/images/*` placeholder prompt assets in first version

**Emits**
- `workflow.stage.started`
- `artifact.written`
- `workflow.stage.completed`

### `constrained_video_generator`

**Reads**
- `storyboard/storyboard.json`
- `input/input.json`

**Writes**
- `video/clips.json`
- `video/requests.json`
- `video/usage.json`
- `costs/poe-usage.jsonl` append line

**Emits**
- `workflow.stage.started`
- `artifact.written`
- `workflow.stage.completed`

### `subtitle_asset_manager`

**Reads**
- `audio/voiceover.json`
- `storyboard/storyboard.json`
- `video/clips.json`
- `assets/manifest.json` if present

**Writes**
- `subtitles/subtitles.json`
- `assets/manifest.json`

**Emits**
- `workflow.stage.started`
- `artifact.written`
- `workflow.stage.completed`

### `timeline_builder`

**Reads**
- `storyboard/storyboard.json`
- `timeline/global-timeline.json`
- `video/clips.json`
- `audio/voiceover.json`
- `assets/manifest.json` if present

**Writes**
- `timeline/timeline.json`

**Emits**
- `workflow.stage.started`
- `artifact.written`
- `workflow.stage.completed`

### `ffmpeg_renderer_reviewer`

**Reads**
- `timeline/timeline.json`

**Writes**
- `outputs/render-plan.json`
- `outputs/final.mp4` in later stages

**Emits**
- `workflow.stage.started`
- `artifact.written`
- `workflow.stage.completed`

## Contract Violations

以下情况视为违反交接契约：

- 读取未声明文件
- 写入未约定目录
- 覆盖已有产物但不写事件
- 输出 JSON 结构不符合约定 schema

## Validation Strategy

共享脚本 `scripts/validate_project.py` 应至少检查：

- 必需目录是否存在
- 必需文件是否存在
- JSON 文件是否可解析
- 关键事件日志是否存在
