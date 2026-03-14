---
name: ffmpeg-renderer-reviewer
description: Validate final timeline and generate render plan with optional ffmpeg export. Use when preparing final render outputs.
---

# ffmpeg_renderer_reviewer

## Purpose

根据最终工程时间轴执行音视频混合、字幕压制和基础逻辑质检，输出最终成片。

## Status

第一版已可执行：当前输出稳定 `render-plan` 并执行基础校验；
真实 ffmpeg 导出将在后续阶段继续增强。

可选开启真实导出：

- `python3 scripts/run_ffmpeg_renderer_reviewer.py --project <path> --enable-ffmpeg-export`

## Reads

- `projects/<project>/timeline/timeline.json`

## Writes

- `projects/<project>/outputs/render-plan.json`
