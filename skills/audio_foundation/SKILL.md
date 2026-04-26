---
name: audio-foundation
description: Build audio timing foundations and global timeline grid from script artifacts. Produces voiceover segments, beat grid, bgm selection, and scene timing slots. Use when preparing timeline anchors.
---

# audio_foundation

## Purpose

从脚本出发，一次性建立整条链路的音频时序骨架：生成配音时间戳、BGM 匹配/需求结果、节拍网格，并合并为全局时间网格。

**已合并原 `global_timeline_initializer` 的职责。** 运行一次即可产出后续分镜所需的全部时间锚点。

## Reads

- `projects/<project>/script/script.json`
- `projects/<project>/input/input.json` if present

## Writes

- `projects/<project>/audio/voiceover.json`
- `projects/<project>/audio/bgm-selection.json`
- `projects/<project>/audio/voiceover-main.mp3` or equivalent if TTS is enabled
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
- 项目级默认模型来自 `input/input.json` 的 `audio_model`
- 音频供应商必须优先读取 `input.audio_provider` 与 `input.poe_enabled`
- 如果 `input.poe_enabled=false`，任何 Poe 路径都不得作为 fallback
- 如果 `input.audio_provider="elevenlabs"`，使用直接 ElevenLabs API 路径，并写明 provider metadata
- 如果用户只有外部素材/下载素材要求，TTS 仍可使用用户允许的 provider，但图片/视频生成禁用不影响旁白生成
- global-timeline.json 写入后，才允许进入 beat_sync_storyboard_planner

## Provider Rules

音频供应商属于强制制作要素，不能在失败时静默切换。

| input 字段 | 行为 |
|---|---|
| `audio_provider=elevenlabs` | 使用 direct ElevenLabs API，输出 `provider: "elevenlabs"` |
| `poe_enabled=false` | 禁止 Poe TTS、Poe ElevenLabs、Poe fallback |
| `audio_provider=poe` 且 `poe_enabled=true` | 才允许 Poe |
| 未指定 provider | 可使用项目默认 provider；若需要联网或外部账号，先说明 |

输出 `audio/voiceover.json` 时必须包含：

- `segments[].text`
- `segments[].start`
- `segments[].end`
- `provider`
- `target_duration_seconds`
- `actual_duration_seconds`
- `source_path` if an audio file exists

## BGM Planning Rules

`audio_foundation` 不一定负责下载 BGM，但必须为下游写清楚 BGM 需求：

- 如果 `input.bgm.required=true`，`audio/bgm-selection.json` 不能是空概念，至少要包含情绪段落、节奏、推荐关键词、使用时段。
- 素材主导项目要标记 `bgm_source_preference: "download_or_import"`。
- 档位 0 时不要要求 AI 生成 BGM；写入外部 BGM 搜索方向。
- BGM 段落应和叙事弧线对齐：压抑、松动、开阔、高潮、回落。

## Scripts

```bash
python3 scripts/run_audio_foundation.py --project <name>
python3 scripts/run_global_timeline_initializer.py --project <name>  # 仍可单独重跑
```
