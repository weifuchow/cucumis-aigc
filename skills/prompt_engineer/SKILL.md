---
name: prompt-engineer
description: Translate storyboard and keyframe constraints into structured scene prompts. Use before image or video generation steps.
---

# prompt_engineer

## Purpose

将踩点分镜描述翻译成视觉模型可执行的提示词，并补充机位、光影、画质和负面提示词。

## Status

第一版已可执行，输出稳定结构化 scene prompts。

## Reads

- `projects/<project>/storyboard/storyboard.json`
- `projects/<project>/keyframes/keyframes.json`

## Writes

- `projects/<project>/prompts/prompts.json`
