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
  input/
    input.json
  script/
    script.json
  storyboard/
    storyboard.json
  timeline/
    timeline.json
  assets/
    manifest.json
  outputs/
    render-plan.json
```

## Rules

- `request.md` 保存原始需求，不应被后续阶段覆盖
- `events/events.jsonl` 保存全量事件流，采用 JSON Lines
- 所有 JSON 文件都应可被标准库解析
- 对于尚未执行的阶段，允许目标文件缺失，但目录应存在
- 任何人工修改都应尽量通过写事件保留痕迹

## Validation Baseline

共享脚本 `scripts/validate_project.py` 第一版至少检查：

- 根目录是否存在
- `README.md`、`request.md`、`events/events.jsonl` 是否存在
- `input/`、`script/`、`storyboard/`、`timeline/`、`assets/`、`outputs/` 是否存在

## Future Expansion

后续可增加：

- `audio/`
- `subtitles/`
- `review/`
- `keyframes/`
- `images/`
- `video/`
