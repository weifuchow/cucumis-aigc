---
name: image-generator
description: Generate mock image asset records from prompts and update asset manifest. Use when visual reference assets are needed.
---

# image_generator

## Purpose

根据分镜和关键帧约束生成静态图、封面图和参考图。

## Status

第一版已可执行，生成调试用 mock 图像提示资产并写入素材清单。

## Planned Reads

- `projects/<project>/storyboard/storyboard.json`
- `projects/<project>/keyframes/keyframes.json`

## Planned Writes

- `projects/<project>/assets/images/`
- `projects/<project>/assets/manifest.json`

## Runtime Expectations

- 需要为每个 prompt 生成可追溯的占位资产记录
- `assets/manifest.json` 的 `images` 字段必须可被后续阶段复用
