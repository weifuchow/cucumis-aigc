---
name: timeline-builder
description: Assemble final timeline from all artifacts, generate subtitles, build render plan, and export MP4. Covers subtitle assembly, timeline composition, and ffmpeg rendering in one step.
---

# timeline_builder

## Purpose

流水线收尾三合一：字幕生成 → 时间轴组装 → FFmpeg 渲染。

**已合并原 `subtitle_asset_manager` 和 `ffmpeg_renderer_reviewer` 的职责。**

三步无决策分支，依次顺序执行：

1. **字幕生成**：从 voiceover 时间戳生成结构化字幕，按画幅生成可读样式，聚合素材 manifest
2. **时间轴组装**：把分镜、素材引用整合为渲染器无关的 timeline.json
3. **渲染输出**：验证时间轴逻辑，生成 render-plan.json，可选执行 ffmpeg 导出

## Reads

- `projects/<project>/audio/voiceover.json`
- `projects/<project>/storyboard/storyboard.json`
- `projects/<project>/video/clips.json`
- `projects/<project>/assets/manifest.json`
- `projects/<project>/timeline/global-timeline.json`
- `projects/<project>/audio/bgm-selection.json`
- `projects/<project>/input/input.json` if present

## Writes

- `projects/<project>/subtitles/subtitles.json`
- `projects/<project>/assets/manifest.json`（更新）
- `projects/<project>/timeline/timeline.json`
- `projects/<project>/outputs/render-plan.json`
- `projects/<project>/outputs/final.mp4`（需 `--enable-ffmpeg-export`）

## Required Output

### subtitles.json

如果 `input.subtitles.required` 不是 `false`，必须输出结构化字幕：

- 字幕来自 `audio/voiceover.json` 的分段时间戳。
- 每条字幕包含 `text`、`display_text`、`start`、`end`。
- 竖屏 9:16 默认大字、底部安全区、高对比描边。
- 每条字幕最多两行；每行约 10-14 个中文字；长句拆成连续短字幕。
- 不要把整段旁白挤成一行。
- 字幕样式写入 `style` 字段，例如字体、字号、最大行长、位置。

### timeline.json

至少包含：`metadata`、`tracks`、`segments`、`output`

每个 segment 必须明确时间区间与关联 scene。

### render-plan.json

描述渲染策略、音视频轨道、字幕轨道及导出参数。

## Runtime Expectations

- 时间轴必须可由渲染阶段直接消费
- 第一版允许素材引用为占位值，但结构必须完整
- 真实 FFmpeg 导出需显式开启：`--enable-ffmpeg-export`
- 素材主导项目不得输出 `missing://` 作为最终可交付版本；缺素材时先写 gap report 或补素材 request
- 带旁白的 9:16 短片默认要输出硬字幕版本，除非用户明确关闭字幕
- 如果本机 ffmpeg 缺少 `subtitles`/`ass`/`drawtext` 滤镜，应使用透明 PNG 字幕层 + `overlay` 等可行 fallback，而不是跳过字幕
- 导出后至少抽查 3 个关键帧：开头、中段/高潮、结尾，确认字幕未出界、未过小、未挤满单行

## Audio Mix Validation

渲染输出不能只验证文件存在，还要验证声音层是否可感知：

- 有 BGM 需求时，最终视频必须包含 BGM 层。
- 有 ambience 需求时，最终视频应包含环境声或记录为什么无法获取。
- BGM 应可听但不盖旁白；用户反馈听不到时输出 `music-forward` 版本。
- 推荐记录 `audio/mix-manifest.json`：voiceover、BGM、ambience 的来源、音量、时间段。
- 可用 `ffmpeg volumedetect` 或等价方法检查最终音频响度。

## Version Naming

不要反复覆盖唯一产物。按阶段保留清晰版本名，例如：

- `outputs/rough-cut-voiceover-only.mp4`
- `outputs/rough-cut-with-ambience.mp4`
- `outputs/rough-cut-full-audio.mp4`
- `outputs/rough-cut-full-audio-music-forward.mp4`
- `outputs/rough-cut-full-audio-subtitled.mp4`

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
