---
name: subtitle-asset-manager
description: Generate subtitle entries from voiceover and update consolidated asset manifest. Use after video clips and before timeline assembly.
---

# subtitle_asset_manager

## Purpose

基于已有音频时间戳生成字幕，并统一整理图片、视频、音效、配音和 BGM 的结构化素材清单。

## Status

第一版已可执行，生成结构化字幕并聚合素材 manifest。

## Reads

- `projects/<project>/audio/voiceover.json`
- `projects/<project>/storyboard/storyboard.json`
- `projects/<project>/video/clips.json`
- `projects/<project>/assets/manifest.json` if present

## Writes

- `projects/<project>/subtitles/subtitles.json`
- `projects/<project>/assets/manifest.json`
