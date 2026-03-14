# Project Structure Contract

## Purpose

每个工作流实例都必须落在 `projects/<project-name>/` 下，并遵守统一目录结构。任何 skill 只能在约定位置读写。

## Required Layout

```text
projects/<project-name>/
  README.md
  request.md
  events/
    events.jsonl
  orchestration/
    state.json
    plan.json
    decisions.jsonl
  input/
    input.json
  script/
    script.json
  audio/
    voiceover.json
    bgm-selection.json
    beat-grid.json
    tts-response.json
    usage.json
  storyboard/
    storyboard.json
  keyframes/
    keyframes.json
  prompts/
    prompts.json
  subtitles/
    subtitles.json
  video/
    clips.json
    requests.json
    usage.json
  timeline/
    global-timeline.json
    timeline.json
  review/
    review-report.json
    observer-summary.md
  costs/
    poe-usage.jsonl
  assets/
    manifest.json
    image-requests.json
    image-usage.json
    images/
  outputs/
    render-plan.json
```

## Rules

- `request.md` 保存原始需求，不应被后续阶段覆盖
- `events/events.jsonl` 保存全量事件流，采用 JSON Lines
- `orchestration/` 保存主控状态、执行计划和关键决策日志
- `audio/` 保存配音时间戳、BGM 匹配和节拍网格
- `audio/tts-response.json` 和 `audio/usage.json` 保存 Poe 调用摘要与成本信息
- `video/` 保存逐镜头视频生成请求、产物和成本信息
- `keyframes/` 保存每个 scene 的关键视觉锚点
- `prompts/` 保存模型可执行提示词
- `assets/image-requests.json` 和 `assets/image-usage.json` 保存图片阶段 Poe 调用摘要与成本信息
- `subtitles/` 保存结构化字幕条目
- `timeline/global-timeline.json` 保存音频驱动的全局时间网格
- `assets/manifest.json` 聚合图片、字幕、音频、视频资产索引
- `review/` 保存结构化审查结果和人类可读摘要
- `costs/poe-usage.jsonl` 聚合所有 Poe 调用的成本日志
- 所有 JSON 文件都应可被标准库解析
- 对于尚未执行的阶段，允许目标文件缺失，但目录应存在
- 任何人工修改都应尽量通过写事件保留痕迹

## Validation Baseline

共享脚本 `scripts/validate_project.py` 第一版至少检查：

- 根目录是否存在
- `README.md`、`request.md`、`events/events.jsonl` 是否存在
- `orchestration/state.json`、`orchestration/plan.json`、`orchestration/decisions.jsonl` 是否存在
- `input/`、`script/`、`audio/`、`storyboard/`、`video/`、`timeline/`、`review/`、`costs/`、`assets/`、`outputs/` 是否存在
- `review/review-report.json`、`review/observer-summary.md` 是否存在

## Future Expansion

后续可增加：

- `video/`
