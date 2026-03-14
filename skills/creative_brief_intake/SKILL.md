---
name: creative-brief-intake
description: Guide users from a one-line idea to a complete creative brief through multi-turn clarification and write a standard request markdown file before input parsing.
---

# creative_brief_intake

## Purpose

把客户的一句话需求转成可执行的 `Creative Brief`，作为整个视频工作流的最前置输入质量门。

## Reads

- 用户自然语言初始诉求（可能只有一句话）
- `projects/<project>/request.md`（如果已有草稿）

## Writes

- `projects/<project>/brief/creative-brief.md`
- `projects/<project>/brief/intake.json`
- `projects/<project>/request.md`（标准化覆盖）

## Multi-turn Intake Workflow

按轮次引导，不要一次问太多。每轮最多 3 个问题。

### Round 1: 基础约束

收集最小可执行字段：

- 主题（做什么）
- 目标（想达成什么）
- 时长（秒）

### Round 2: 传播与听觉方向

收集产出形态字段：

- 受众与平台
- 音乐情绪与节奏偏好
- 旁白和字幕要求

### Round 3: 视觉与验收边界

补齐执行边界：

- 视觉偏好与禁用项
- 内容结构（开场/转折/高潮/收束）
- 关键硬约束（时间对齐、可复现、可编辑）

## Completion Criteria

只有满足以下条件才结束 intake：

- 主题、时长、平台、画幅、语言明确
- 音乐情绪、节奏偏好、旁白和字幕要求明确
- 至少 3 条执行约束明确
- 生成标准 `Creative Brief` 并写入 `request.md`

## Standard Output

优先使用以下模板字段（见 `references/creative-brief-template.md`）：

- 主题 / 目标 / 时长 / 风格 / 语言 / 画幅 / 音乐 / 节奏
- 受众 / 平台 / 旁白要求 / 字幕要求
- 内容结构 / 视觉偏好 / 约束

## Script Fallback

当无法进行完整多轮对话（批处理或自动化场景）时，使用脚本：

`python3 scripts/run_creative_brief_intake.py --project <project-path>`

脚本会用默认值补齐缺失字段，并生成标准 brief 文件。
