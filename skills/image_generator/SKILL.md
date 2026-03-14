---
name: image-generator
description: Generate image assets through Poe model calls (with local mock fallback) and update manifest/usage artifacts.
---

# image_generator

## Purpose

根据分镜和关键帧约束生成静态图、封面图和参考图。

## Status

第一版已可执行，接入 Poe 图片模型并保留本地 mock fallback，可生成素材索引与调用元数据。

## Planned Reads

- `projects/<project>/prompts/prompts.json`
- `projects/<project>/input/input.json`

## Planned Writes

- `projects/<project>/assets/images/`
- `projects/<project>/assets/manifest.json`
- `projects/<project>/assets/image-requests.json`
- `projects/<project>/assets/image-usage.json`
- `projects/<project>/costs/poe-usage.jsonl`

## Runtime Expectations

- 需要为每个 prompt 生成可追溯的占位资产记录
- `assets/manifest.json` 的 `images` 字段必须可被后续阶段复用
