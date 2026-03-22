---
name: audio-foundation
description: Build audio timing foundations and global timeline grid from script artifacts. Produces voiceover segments, beat grid, bgm selection, and scene timing slots. Use when preparing timeline anchors.
---

# audio_foundation

## Purpose

从脚本出发，一次性建立整条链路的音频时序骨架：生成配音时间戳、BGM 匹配结果、节拍网格，并合并为全局时间网格。

**已合并原 `global_timeline_initializer` 的职责。** 运行一次即可产出后续分镜所需的全部时间锚点。

## Reads

- `projects/<project>/script/script.json`

## Writes

- `projects/<project>/audio/voiceover.json`
- `projects/<project>/audio/bgm-selection.json`
- `projects/<project>/audio/beat-grid.json`
- `projects/<project>/timeline/global-timeline.json`

## Required Output

### 音频文件

- narration segments with timestamps
- bgm selection metadata
- beat anchors and emotion transition anchors

### global-timeline.json

至少包含：

- narration windows
- beat anchors
- transition windows
- reserved silence gaps
- scene timing slots（每个 slot 固定 5 秒）

## Runtime Expectations

- 音频基建必须先于分镜生成
- 默认通过 Poe API 生成或模拟生成配音相关数据
- 项目级默认模型来自 `input/input.json` 的 `audio_model`
- global-timeline.json 写入后，才允许进入 beat_sync_storyboard_planner

## Scripts

```bash
python3 scripts/run_audio_foundation.py --project <name>
python3 scripts/run_global_timeline_initializer.py --project <name>  # 仍可单独重跑
```
