# global_timeline_initializer

## Purpose

把配音时间戳和 BGM 节点合并成全局时间网格，作为后续分镜和视觉生成的统一时间骨架。

## Reads

- `projects/<project>/audio/voiceover.json`
- `projects/<project>/audio/bgm-selection.json`
- `projects/<project>/audio/beat-grid.json`

## Writes

- `projects/<project>/timeline/global-timeline.json`

## Required Output

`global-timeline.json` 至少包含：

- narration windows
- beat anchors
- transition windows
- reserved silence gaps
- scene timing slots
