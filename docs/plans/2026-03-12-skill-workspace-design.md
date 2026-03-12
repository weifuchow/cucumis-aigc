# Skill Workspace Design

**Date:** 2026-03-12

## Purpose

为 `cucumis-aigc` 设计第一版项目骨架。该骨架不是传统应用服务，而是一个依托 Codex / Claude Code 运行的 skill workspace，核心资产是 `SKILL.md`、workflow 文档、通用脚本、模板和本地产物目录。

## Runtime Assumption

- 运行时是 Codex / Claude Code
- 仓库主入口不是 Web 服务或 Python 应用
- 主要执行单位是 `skills/<name>/SKILL.md` 和相关脚本
- 主流程通过 `workflows/` 表达，而不是通过常驻服务进程表达

## Design Direction

采用双层结构：

- `skills/` 负责能力模块化与复用
- `workflows/` 负责主流程编排与交接定义

并配套：

- `schemas/` 作为跨 skill 的公共契约
- `scripts/` 作为被多个 skill 复用的通用脚本
- `templates/` 作为项目、prompt 和文档模板
- `projects/` 作为本地运行产物目录
- `examples/` 作为示例输入与示例项目

## Scope

第一版骨架采用“文档 + 最小脚本骨架”方案。

本次真正写内容的部分：

1. `workflows/video_pipeline/`
2. `skills/input_parser/`
3. `skills/script_writer/`
4. `skills/storyboard_planner/`
5. `skills/timeline_builder/`
6. `skills/ffmpeg_renderer/`
7. `scripts/init_project.py`
8. `scripts/write_event.py`
9. `scripts/validate_project.py`

其余 skill 仅创建目录与基础 `SKILL.md` 占位。

## Target Layout

```text
cucumis-aigc/
  README.md
  skills/
    <skill>/
      SKILL.md
      templates/
      scripts/
      examples/
  workflows/
    video_pipeline/
      WORKFLOW.md
      state-machine.md
      handoff-contracts.md
  schemas/
    task-input.schema.json
    script.schema.json
    storyboard.schema.json
    timeline.schema.json
    asset-manifest.schema.json
    event.schema.json
    project-structure.md
  templates/
    project/
      README.md
      input.json
      events.jsonl
      assets/
      outputs/
    prompts/
    docs/
  scripts/
    init_project.py
    write_event.py
    validate_project.py
  projects/
    .gitkeep
  examples/
    requests/
    projects/
  docs/
    plans/
```

## Responsibilities

### `skills/`

每个 skill 目录存放单一能力的说明、模板、脚本与示例，保证可单独演进和单独调用。

### `workflows/`

定义从输入到成片的主链路、状态流转、失败恢复和上下游交接约定。

### `schemas/`

定义跨 skill 的公共数据结构，确保输入输出能稳定拼接。

### `scripts/`

提供通用自动化能力，例如初始化项目、写事件日志、校验目录结构。

### `templates/`

提供项目初始化与文档复用模板，避免 skill 各自重复造轮子。

### `projects/`

作为每次运行的本地产物根目录，贯彻“文件即事实”。

## First Iteration Goal

第一版要形成一个最小闭环：

用户输入 -> 结构化输入 -> 脚本 -> 分镜 -> 时间轴 -> 渲染占位输出

这里的“渲染”可以先是 mock 或占位结果，不要求第一版就接入完整真实能力。

## Non-Goals

- 不构建 FastAPI / Typer 应用骨架
- 不引入常驻服务进程
- 不一次性写满全部 skill 的完整实现
- 不在第一版接入真实模型与复杂 FFmpeg 管线
