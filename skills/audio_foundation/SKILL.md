---
name: audio-foundation
description: Build audio timing foundations from script artifacts by producing voiceover segments beat grid and bgm selection. Use when preparing timeline anchors.
---

# audio_foundation

## Purpose

基于脚本中的情绪标注建立整条链路的音频时序锚点，生成配音时间戳、BGM 匹配结果和节拍网格。

## Reads

- `projects/<project>/script/script.json`

## Writes

- `projects/<project>/audio/voiceover.json`
- `projects/<project>/audio/bgm-selection.json`
- `projects/<project>/audio/beat-grid.json`

## Required Output

第一版至少输出：

- narration segments with timestamps
- bgm selection metadata
- beat anchors and emotion transition anchors

## Runtime Expectations

- 音频基建必须先于分镜生成
- 默认通过 Poe API 生成或模拟生成配音相关数据
- 项目级默认模型来自 `input/input.json` 的 `audio_model`
- 所有时间戳都应为后续全局时间网格的刚性输入
