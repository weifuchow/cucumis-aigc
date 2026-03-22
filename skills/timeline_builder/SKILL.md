---
name: timeline-builder
description: Assemble final timeline from all artifacts, generate subtitles, build render plan, and export MP4. Covers subtitle assembly, timeline composition, and ffmpeg rendering in one step.
---

# timeline_builder

## Purpose

流水线收尾三合一：字幕生成 → 时间轴组装 → FFmpeg 渲染。

**已合并原 `subtitle_asset_manager` 和 `ffmpeg_renderer_reviewer` 的职责。**

三步无决策分支，依次顺序执行：

1. **字幕生成**：从 voiceover 时间戳生成结构化字幕，聚合素材 manifest
2. **时间轴组装**：把分镜、素材引用整合为渲染器无关的 timeline.json
3. **渲染输出**：验证时间轴逻辑，生成 render-plan.json，可选执行 ffmpeg 导出

## Reads

- `projects/<project>/audio/voiceover.json`
- `projects/<project>/storyboard/storyboard.json`
- `projects/<project>/video/clips.json`
- `projects/<project>/assets/manifest.json`
- `projects/<project>/timeline/global-timeline.json`
- `projects/<project>/audio/bgm-selection.json`

## Writes

- `projects/<project>/subtitles/subtitles.json`
- `projects/<project>/assets/manifest.json`（更新）
- `projects/<project>/timeline/timeline.json`
- `projects/<project>/outputs/render-plan.json`
- `projects/<project>/outputs/final.mp4`（需 `--enable-ffmpeg-export`）

## Required Output

### timeline.json

至少包含：`metadata`、`tracks`、`segments`、`output`

每个 segment 必须明确时间区间与关联 scene。

### render-plan.json

描述渲染策略、音视频轨道、字幕轨道及导出参数。

## Runtime Expectations

- 时间轴必须可由渲染阶段直接消费
- 第一版允许素材引用为占位值，但结构必须完整
- 真实 FFmpeg 导出需显式开启：`--enable-ffmpeg-export`

## Scripts

```bash
# 单步重跑（调试用）
python3 scripts/run_subtitle_asset_manager.py --project <name>
python3 scripts/run_timeline_builder.py --project <name>
python3 scripts/run_ffmpeg_renderer_reviewer.py --project <name>

# 可选完整导出
python3 scripts/run_ffmpeg_renderer_reviewer.py --project <name> --enable-ffmpeg-export
```

## Failure Behavior

- 如果缺少分镜结构，必须终止
- 不允许写出无法解析的时间轴 JSON
