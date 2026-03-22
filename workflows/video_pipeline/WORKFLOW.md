# Video Pipeline Workflow

## Purpose

`video_pipeline` 是 `cucumis-aigc` 的默认听觉驱动工作流定义，描述从自然语言需求到本地视频产出的标准 9 步闭环。由 `master_orchestrator` 解释和推进。

## 刚性约束（全链路）

- **场景时长**：固定 5 秒，不可修改
- **场景数量**：`ceil(总时长 / 5)`，在 creative_design 阶段确定
- **每场景关键帧**：固定 4 张（0s / 1.7s / 3.3s / 5s）
- **帧衔接**：每场景 kf-01 必须视觉衔接上一场景 kf-04
- **上下文防污染**：图片/视频内容不进 Claude 上下文，只传路径
- **音频优先**：所有时序锚点由 audio_foundation 锁定，视觉服从音频

## 主链（9 步）

```
1. creative_design
2. script_writer
3. audio_foundation
4. beat_sync_storyboard_planner
5. image_generator
6. constrained_video_generator
7. timeline_builder
```

## Stage 详述

### Stage 1: `creative_design`

**职责**：需求定稿、节拍规划、提示词设计、成本档位确认

执行顺序：
1. 读取 `request.md`，澄清必要字段（主题、时长、画幅）
2. 生成 3 个差异化创意方案，用户选择
3. 输出场景节拍表（5s 一格，覆盖全片），**等待用户确认节奏**
4. 输出角色多视角提示词 + 关键场景提示词草稿，**等待用户确认**
5. 用户选择成本档位（省钱/标准/不限制）
6. 写入产物

**写入**：
- `brief/selected-concept.json`
- `brief/character-prompts.json`
- `brief/scene-prompts.json`
- `input/input.json`

**检查点**：节拍表确认 + 提示词设计确认，两次均需用户明确回复后才能推进

---

### Stage 2: `script_writer`

**职责**：生成带情绪标注的可朗读脚本

要求：
- audio_track 必须是可直接朗读的完整句子
- visual_track 描述真实画面，不写抽象情绪
- 台词数量 ≈ `总时长 / 7`

**写入**：`script/script.json`

---

### Stage 3: `audio_foundation`

**职责**：建立全链路音频时序骨架（含原 global_timeline_initializer）

执行顺序：
1. 从脚本生成配音时间戳、BGM 匹配、节拍网格
2. 把音频文件合并为全局时间网格（5s 一格的 scene timing slots）

**写入**：
- `audio/voiceover.json`
- `audio/bgm-selection.json`
- `audio/beat-grid.json`
- `timeline/global-timeline.json`

**后置条件**：global-timeline.json 写入后才可进入 Stage 4

---

### Stage 4: `beat_sync_storyboard_planner`

**职责**：在锁定的时间网格上生成踩点分镜

每个 scene：
- `duration_seconds` = 5（固定，不可更改）
- `asset_mode`：`mixed`（需视频模型）或 `static`（本地合成）
- `motion_intent`：语义判断，不按位置规则硬编码

**写入**：`storyboard/storyboard.json`

**视频模型预算**：由 `input.json` 的 `max_video_calls` 控制（标准模式默认 2 次）

---

### Stage 5: `image_generator`

**职责**：三阶段图片生成，每阶段有人工确认检查点

```
Phase 1: 角色基准图（多视角）
    → [CHECKPOINT-1: 展示路径，等用户确认]
Phase 2: 场景地点参考图
    → [CHECKPOINT-2: 快速确认]
Phase 3: 场景关键帧（每场景 4 张，引用 char_refs 基准图）
    → [CHECKPOINT-3: 每场景完成后展示路径，确认再继续]
```

关键帧命名：`{scene_id}-kf-01` 到 `{scene_id}-kf-04`

kf-01 prompt 必须包含上一场景结尾的视觉状态描述（例：`"（接续scene-Xa结尾：[状态]）[本帧内容]"`）

场景有 `char_refs` 时，必须从 `character-manifest.json` 取基准图作为 ref_images 传入模型。

**写入**：
- `assets/images/characters/{char_id}/{view_id}.png`
- `assets/images/locations/{loc_id}/establishing.png`
- `assets/images/scenes/{scene_id}/{keyframe_id}.png`
- `assets/character-manifest.json`
- `assets/manifest.json`

---

### Stage 6: `constrained_video_generator`

**职责**：在预算约束下生成动态视频片段

- 只为 `asset_mode = mixed` 的场景调视频模型
- 调用次数不超过 `input.json` 的 `max_video_calls`
- 其余场景走本地 FFmpeg 静态合成（由 `local_render_technique` 指定效果）

**写入**：`video/clips.json`

---

### Stage 7: `timeline_builder`

**职责**：收尾三合一（含原 subtitle_asset_manager + ffmpeg_renderer_reviewer）

执行顺序：
1. 从 voiceover 时间戳生成字幕，聚合素材 manifest
2. 把分镜、素材引用整合为渲染器无关的 timeline.json
3. 验证时间轴逻辑，生成 render-plan.json，可选执行 FFmpeg 导出

**写入**：
- `subtitles/subtitles.json`
- `assets/manifest.json`（更新）
- `timeline/timeline.json`
- `outputs/render-plan.json`
- `outputs/final.mp4`（需 `--enable-ffmpeg-export`）

---

## 诊断工具（按需，不在主链）

### `observer`（含原 reviewer）

一次运行输出两份结果：
- `review/review-report.json`：健康检查（结构完整性、state 一致性）
- `review/observer-summary.md`：人类可读进度摘要

状态模型：`ready` / `in_progress` / `blocked`

---

## 会话连续性协议

**每次操作前必须执行：**

1. 读 `orchestration/task-card.md`（若存在）
2. 读 `orchestration/state.json`
3. 输出一行状态确认：`[Project: <name>] [Stage: <current>] [Next: <action>]`

task-card.md 由 master_orchestrator 在每次阶段推进后更新，格式固定不超过 20 行：

```markdown
# Task Card — <project>
更新时间：<timestamp>

## 当前状态
- 项目：<project>
- 当前阶段：<stage>
- 已完成：<stages>

## 下一步
**<一句话描述具体操作>**

## 等待事项
- <人工确认检查点或"无">

## 已知阻塞
- <错误/阻塞或"无">
```

---

## 运行时约束

- 主控将当前状态写入 `orchestration/`，每阶段开始/结束写事件日志
- 每阶段只读自己声明的输入，不隐式依赖临时文件
- 失败时必须写错误事件，保留已生成产物，不覆盖未明确替换的产物
- 分镜及后续阶段必须服从已锁定的音频时间网格

## Non-Goals

- 不定义 LLM 提示词细节
- 不绑定具体模型供应商
- 不做自动全流程无人值守执行（v1 含多个人工检查点）
