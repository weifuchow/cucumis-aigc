---
name: input-parser
description: Map brief/intake.json to structured pipeline input.json with model defaults. Use after creative_brief_intake and before script generation.
---

# input_parser

## Purpose

将 `brief/intake.json`（创意引导产物）映射为流水线统一输入格式 `input/input.json`，并补充模型配置默认值。

**不再重复解析 `request.md`**——创意引导阶段已完成解析，本阶段只做字段映射 + 模型配置注入。

## Reads

- `projects/<project>/brief/intake.json`（由 `creative_brief_intake` 生成）

## Writes

- `projects/<project>/input/input.json`

## 字段映射

| intake.json 字段 | input.json 字段 | 备注 |
|---|---|---|
| topic, goal, duration_seconds 等 | 直接复制 | 创意字段透传 |
| 缺失的 style/music_emotion/pacing_preference | 补默认值 | 专业克制 / 平稳推进 / 均匀 |
| audio_model / image_model / video_model | 注入默认值 | 可被 intake 覆盖 |

## 模型配置默认值

```json
{
  "audio_model": "elevenlabs-v3",
  "image_model": "flux-schnell",
  "video_model": "veo-3.1-fast",
  "requires_voiceover": true,
  "requires_subtitles": true
}
```

如需使用不同模型，在 `brief/intake.json` 中显式指定，或 Claude 执行后直接修改 `input/input.json`。

## Runtime Expectations

- 调用 `python scripts/run_input_parser.py --project <name>`
- 依赖 `brief/intake.json` 存在，必须在 `creative_brief_intake` 之后执行
- 如果缺少必要字段，明确报告而不是静默猜测
