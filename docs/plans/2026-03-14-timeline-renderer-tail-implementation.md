# Timeline & Renderer Tail-Chain Implementation Plan

**Date:** 2026-03-14

## Goal

让 audio-first 主链从 `run_constrained_video_generator.py` 后继续可执行，新增：

- `scripts/run_timeline_builder.py`
- `scripts/run_ffmpeg_renderer_reviewer.py`

并保证：

- 产出 `timeline/timeline.json`
- 产出 `outputs/render-plan.json`
- 全量测试通过
- 一条完整 smoke 可执行

## TDD Plan

### Task 1: 先补失败测试

修改或新增测试，先对以下行为写断言：

1. `run_timeline_builder.py` 可从现有前置产物生成 `timeline/timeline.json`
2. `run_ffmpeg_renderer_reviewer.py` 生成稳定 `outputs/render-plan.json`
3. renderer 能识别基础异常（如 timeline 缺关键轨道）
4. `validate_project.py` 能覆盖后半链关键文件（`timeline/timeline.json`、`outputs/render-plan.json`）

先运行相关测试，确认红灯。

### Task 2: 实现 timeline_builder

实现脚本逻辑：

1. 读取 `storyboard/storyboard.json`、`timeline/global-timeline.json`、`video/clips.json`、`audio/voiceover.json`、`audio/bgm-selection.json`
2. 构造 renderer-agnostic `timeline.json`
3. 写入稳定字段顺序和 deterministic 内容
4. 输入缺失或结构异常时返回非 0

### Task 3: 实现 ffmpeg_renderer_reviewer

实现脚本逻辑：

1. 读取并校验 `timeline/timeline.json`
2. 执行基础检查：时长、关键轨道、必要文件、segment 时间区间
3. 生成 `outputs/render-plan.json`
4. 在 `ffmpeg` 字段保留未来真实命令结构（`enabled`/`binary`/`args_template`）

### Task 4: 模板与 schema 对齐

视实现结果补充：

1. `templates/project/timeline/timeline.json`
2. `templates/project/outputs/render-plan.json`
3. 如必要，新增 `schemas/render-plan.schema.json` 并收紧 `schemas/timeline.schema.json`

### Task 5: 全量验证

至少执行：

1. `python3 -m unittest discover -s tests -v`
2. 完整 smoke:
   - `init_project`
   - `run_input_parser`
   - `run_script_writer`
   - `run_audio_foundation`
   - `run_global_timeline_initializer`
   - `run_beat_sync_storyboard_planner`
   - `run_constrained_video_generator`
   - `run_timeline_builder`
   - `run_ffmpeg_renderer_reviewer`
   - `validate_project`

## Git Plan

1. 在 `codex/timeline-renderer-phase2` worktree 分支开发
2. 本地验证通过后提交
3. 合并回 `main`
4. 推送 `origin/main`
