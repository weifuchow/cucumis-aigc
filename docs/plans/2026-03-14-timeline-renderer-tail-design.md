# Timeline & Renderer Tail-Chain Design

**Date:** 2026-03-14

## Purpose

在现有 audio-first 前半链基础上，补齐后半链最小可执行闭环：

1. `timeline_builder` 读取分镜、全局时间轴、视频 clips、音频产物，产出 `timeline/timeline.json`
2. `ffmpeg_renderer_reviewer` 读取 `timeline/timeline.json` 与关键产物，产出 `outputs/render-plan.json` 并执行基础校验

## Brainstorming

### 方案 A：直接做真实 ffmpeg 渲染

- 优点：一步到位输出 `final.mp4`
- 缺点：依赖本机 ffmpeg 和真实媒体文件，当前 `mock://` clips 无法稳定跑通，失败面大

### 方案 B：先做 render-plan + validation（本次选型）

- 优点：和当前“文件即事实、可恢复”风格一致；可稳定测试；后续可增量替换执行层
- 缺点：第一版不保证真实视频导出

### timeline 输入拼装策略

- 优先以 `storyboard.scenes` 为主线（scene 粒度最稳定）
- 用 `video/clips.json` 按 `scene_id` 关联视频引用
- 用 `audio/voiceover.json` 作为音频主轨输入
- 用 `timeline/global-timeline.json` 写入 metadata，保留可追溯性

## Key Design Decisions

### Decision 1: `timeline.json` 结构保持渲染器无关

输出严格包含 `metadata`、`tracks`、`segments`、`output`，并在 `tracks` 中显式区分：

- `video_main`
- `audio_voiceover`
- `audio_bgm`

`segments` 保存每个 scene 的开始结束时间、scene 关联、素材引用与字幕文本。

### Decision 2: `render-plan.json` 采用稳定、可回放排序

渲染计划包含：

- `version`
- `timeline_source`
- `duration_seconds`
- `checks`（基础校验结果）
- `stages`（prepare/mix/render/review 占位）
- `ffmpeg`（命令模板与参数占位）

场景和输入文件按稳定顺序输出，避免重跑 diff 噪音。

### Decision 3: 基础校验在 renderer 阶段集中执行

至少校验：

- timeline 总时长 > 0
- 存在关键轨道（video + audio）
- 关键输入文件存在并可解析
- `segments` 时间区间有效且不反向

若失败，脚本非 0 退出，避免写出误导性 render plan。

### Decision 4: reviewer/observer 不改协议，仅继续消费 renderer 产物

保持 `review_project.py` 现有阶段映射：`ffmpeg_renderer_reviewer` 对应 `outputs/render-plan.json`。
必要时仅补充 validator 与测试，让后半链产物在现有 review/observe 路径上可见。

## Non-Goals

- 本次不实现复杂多 provider 渲染抽象
- 本次不强制真实 ffmpeg 导出 `final.mp4`
- 本次不引入 UI 或任务调度系统
