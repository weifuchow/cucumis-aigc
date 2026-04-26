---
name: master_orchestrator
description: Inspect workflow state choose next stage and write orchestration decisions. Use for stage planning recovery and control flow.
---

# master_orchestrator

## Purpose

`master_orchestrator` 是第一版轻度主控 skill。它负责解释 workflow 规则、检查项目当前状态、决定下一阶段、记录主控决策，并在失败时提供恢复建议。

主控还必须在项目早期主动锁定用户的强制制作要素，尤其是：素材来源、是否允许 AI 生成、素材下载、BGM、环境声、字幕、音频供应商和成本档位。不要等用户在后续阶段逐项纠偏。

## Reads

- `workflows/video_pipeline/WORKFLOW.md`
- `workflows/video_pipeline/state-machine.md`
- `workflows/video_pipeline/handoff-contracts.md`
- `projects/<project>/request.md`
- `projects/<project>/input/input.json` if present
- `projects/<project>/orchestration/state.json` if present
- `projects/<project>/` 下已有产物

## Writes

- `projects/<project>/orchestration/state.json`
- `projects/<project>/orchestration/plan.json`
- `projects/<project>/orchestration/decisions.jsonl`
- `projects/<project>/events/events.jsonl`

## Responsibilities

- 判断当前 workflow 的真实状态
- 基于固定主链选择下一阶段
- 根据输入配置或已有产物跳过可选阶段
- 记录每次关键编排决策
- 在失败时输出恢复建议

## Control Model

固定主链（9 步），合并了原 12 步中的薄 skill：

1. `creative_design`
2. `script_writer`
3. `audio_foundation` ← 已合并 `global_timeline_initializer`
4. `beat_sync_storyboard_planner`
5. `image_generator`
6. `constrained_video_generator`
7. `timeline_builder` ← 已合并 `subtitle_asset_manager` + `ffmpeg_renderer_reviewer`

**素材主导 / 成本档位 0-2 分支：**

当用户明确要求“下载素材整合 / 0 成本 / 不生成视频 / stock footage / 本地素材剪辑”，或 `input/source_mode` 为 `local_materials`、`stock_materials`、`hybrid_materials` 时：

- 主入口仍由 `master_orchestrator` 解析项目和状态。
- 立即把项目切到 `stock_editorial_composer` 主线，并在用户可见回复中说明完整路径：`旁白 → 分镜 → 素材搜索/下载 → scene-to-asset 映射 → BGM/环境声 → rough cut → 字幕 → 复审补素材`。
- 仍然音频主导：先完成脚本/旁白、`audio_foundation` 和分镜；旁白与分镜确认后，才进入第一轮素材搜索。
- 成本档位使用 `material_cost_tier`：
  - `0`：全部外部/下载/本地素材，跳过图片和视频生成。
  - `1`：大量下载素材和图片，本地剪辑为主，只允许少量关键视频模型调用。
  - `2`：大量视频模型，下载素材仍用于参考、BGM、环境声和补充镜头。
- 素材获取调用 `asset_acquisition`；rough cut、多轮补素材、scene-to-asset 映射、BGM/环境声混音和本地导出交给 `stock-editorial-composer`。
- 第二轮素材/生成发生在 rough cut 串起来之后：先看片或读 gap report，再只补最弱场景。
- 这种分支复用 `script_writer`、`audio_foundation`、`beat_sync_storyboard_planner` 和 `timeline_builder`；根据档位决定是否跳过 `image_generator` 和 `constrained_video_generator`。

**素材分支默认锁定：**

用户只要表达“不需要 AI 生成 / 大量外部素材 / 下载素材 / stock / 本地剪辑 / 0 成本”等任一意图，除非用户后续明确改口，否则写入或保持：

- `input/source_mode = "stock_materials"`
- `input/production_mode = "stock_editorial"`
- `input/material_cost_tier = 0`
- `input/max_video_calls = 0`
- `input/ai_image_generation = false`
- `input/ai_video_generation = false`
- `input/bgm.required = true`
- `input/ambience.required = true`
- `input/subtitles.required = true`（竖屏短片默认需要字幕，除非用户明确不要）

## Forced Intake Lock

新建项目或进入生产前，必须确保以下字段已确认或有明确默认值，并写入 `brief/intake.json` 与 `input/input.json`。缺失时先补齐，不要直接推进下载或生成。

| 字段 | 说明 | 默认/规则 |
|---|---|---|
| `duration_seconds` | 总时长 | 用户给出；未给则追问 |
| `aspect_ratio` | 画幅 | 用户给出；短视频可默认 `9:16` 但需告知 |
| `source_mode` | 素材来源 | `generated` / `stock_materials` / `local_materials` / `hybrid_materials` |
| `material_cost_tier` | 素材成本档位 | 素材主导默认 `0` |
| `ai_image_generation` | 是否允许 AI 图片 | 素材主导默认 `false` |
| `ai_video_generation` | 是否允许 AI 视频 | 素材主导默认 `false` |
| `audio_provider` | 配音供应商 | 如用户说 ElevenLabs key，则 `elevenlabs` direct |
| `poe_enabled` | 是否允许 Poe | 用户说禁用 Poe 时必须为 `false` |
| `bgm.required` | 是否需要背景音乐 | 情绪短片默认 `true` |
| `ambience.required` | 是否需要环境声 | 素材片默认 `true` |
| `subtitles.required` | 是否需要字幕 | 竖屏旁白片默认 `true` |
| `subtitle_style` | 字幕样式 | 默认大字、最多两行、自动换行、底部安全区 |

确认后可写一个 `input/intake-lock.json` 或在 `input/input.json` 中保留同等字段。后续所有 skill 必须以该锁定配置为准。

**诊断工具（按需调用，不在主链）：**
- `observer` ← 已合并 `reviewer`（健康检查 + 进度摘要）
- `master_orchestrator`（自身）

**已废弃（职责已并入上方）：**
- `global_timeline_initializer` → 并入 `audio_foundation`
- `subtitle_asset_manager` → 并入 `timeline_builder`
- `ffmpeg_renderer_reviewer` → 并入 `timeline_builder`
- `reviewer` → 并入 `observer`

## Required Outputs

### `orchestration/task-card.md` ⭐ 最重要

**每次做出阶段决策后必须立即更新此文件。** 格式固定、极简、不超过 20 行：

```markdown
# Task Card — <project>
更新时间：<timestamp>

## 当前状态
- 项目：<project>
- 当前阶段：<current_stage>
- 已完成：<completed_stages 逗号分隔>

## 下一步（最重要）
**<下一步具体操作，一句话>**

例如：运行 `python3 scripts/run_image_generator.py --project vidu-new --phase scenes --max-scenes 2`

## 等待事项
- <如有人工确认检查点，列出在此；否则写"无">

## 已知阻塞
- <当前已知错误或阻塞点；否则写"无">
```

**此文件是唯一需要在多轮对话间保持一致的上下文锚点。** 任何阶段推进、检查点等待、错误发生后都必须更新。

### `orchestration/state.json`

记录当前状态快照，例如：

- `current_stage`
- `completed_stages`
- `skipped_stages`
- `last_failed_stage`
- `next_stage`

### `orchestration/plan.json`

记录本次执行计划，例如：

- `workflow`
- `planned_stages`
- `optional_stages`
- `disabled_stages`

### `orchestration/decisions.jsonl`

按 JSON Lines 记录关键编排决策，例如：

- 为什么跳过某个阶段
- 为什么从某个阶段恢复
- 为什么判定可以进入下一阶段

## Project Resolution（启动时必须优先执行）

**若用户未指定 project ID，必须先做以下判断，再进入任何 workflow 逻辑：**

### Step 1：扫描现有项目

列出 `projects/` 目录下所有子目录，展示给用户：

```
当前已有项目：
  1. dragon-fall-35s
  2. my-other-project
  ...
  N. 新建项目

请输入项目编号，或直接输入新项目的标题：
```

### Step 2：用户选择

- **选已有项目** → 进入 **Resume 模式**：读取已有产物与编排状态，从断点继续执行
- **选新建 / 输入标题** → 进入 **New 模式**：根据标题生成 project_id（slug 格式），调用 `scripts/init_project.py` 初始化目录，从 `creative_design` 阶段开始

### Step 3：确认后再推进

确认模式与项目后，输出一行提示说明当前模式，然后继续正常 orchestration 流程。

---

## Runtime Expectations

- 若尚未存在项目目录，主控第一步应创建 `project_id` 并初始化项目目录（可通过 `scripts/init_project.py` 自动生成）
- 主控必须优先读取 workflow 定义，而不是硬编码业务路径
- 主控写出的状态与计划必须可被脚本和人工同时读取
- 所有主控决策都应尽量落盘，而不是只存在于瞬时推理里
- 主控不应直接生成下游业务内容
- 主控在分镜及其后续阶段前，必须优先检查音频时间锚点是否已建立
- 主控在素材主导项目中必须把“素材下载”作为显式可见阶段，不得只写成内部实现细节。
- 每次进入下载、混音、字幕、导出前，都要在 `task-card.md` 的下一步中写清楚用户可理解的动作和目标产物。

## Context Hygiene

- 主线程只保留控制面信息：目标、阶段决策、风险与验收结论
- 长分析、批量代码阅读和重构执行优先交给子 agent
- 子 agent 输入必须最小化：任务目标 + 关键文件路径 + 验收标准
- 禁止把整段历史聊天原样转发给子 agent
- 每轮结束必须写入 `orchestration/decisions.jsonl`，必要时刷新 `review/observer-summary.md`
- 当主线程上下文变长时，先运行：
  - `python3 scripts/session_handoff.py --project <project-path>`
  - 再开新线程，仅用 handoff 文档续跑

## Subagent Policy

- 以下场景建议开启子 agent：
  - 跨多个目录的大规模分析
  - 大范围代码修改前的方案对比
  - 长日志定位与回归验证
- 以下场景不建议开启子 agent：
  - 单文件小改
  - 明确且短路径的命令执行
  - 需要连续人机确认的细粒度交互

## Failure Behavior

- 如果当前状态不足以安全推进，必须停止并写决策记录
- 如果检测到关键产物损坏，应输出恢复建议
- 失败时必须写 `workflow.stage.failed` 或等价事件

## Non-Goals

- 不实现完整自动 runner
- 不替代下游 skill 的业务逻辑
- 不做跨 workflow 的统一调度框架
