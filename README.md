# cucumis-aigc

> **当前版本**：v1 本地单机闭环，9 步主链，含人工检查点和会话连续性机制

`cucumis-aigc` 是一个面向短视频生产的本地化 AIGC 编排系统。目标不是提供单点生成能力，而是把脚本、分镜、关键帧、图片、动态视频、配音、字幕、时间轴与渲染串成一条可控、可追踪、可恢复的生产工作流。

这不是"模型直接吐出视频"的黑盒产品，而是一套依托 Claude Code 运行、以 `workflow + skills` 为主控组织方式、以本地文件系统为事实来源、以 FFmpeg 为渲染出口的生产系统。

## 核心设计原则

- **生产能力 > 生成能力**：编排、状态管理、恢复、审查比单步生成效果更重要
- **音频优先**：所有时序锚点锁定在配音和 BGM 节拍上，视觉跟着音频走
- **场景时长固定 5 秒**：每场景统一 5s，场景数 = `ceil(总时长 / 5)`，全链路刚性约束
- **文件即事实**：所有中间产物落盘为 JSON，人读机读，状态可完整恢复
- **人工把关检查点**：角色基准图、场景关键帧逐场确认，防止废片积累
- **上下文防污染**：图片/视频文件内容不进入 Claude 上下文，只传路径

## 9 步主链

```
1. creative_design
   需求澄清 → 节拍表 → 角色/场景提示词设计确认 → 成本档位 → input.json

2. script_writer
   情绪标注脚本生成

3. audio_foundation                        ← 含原 global_timeline_initializer
   配音时间戳 + BGM + 节拍网格 + 全局时间网格（5s 一格）

4. beat_sync_storyboard_planner
   踩点分镜规划（每场景固定 5s）

5. image_generator
   Phase1：角色基准图 → [人工确认]
   Phase2：场景地点参考图 → [确认]
   Phase3：场景关键帧（每场景 4 张，kf-01 必须衔接上一场景）→ [逐场确认]

6. constrained_video_generator
   约束性动态视频生成（预算控制，最多 N 次视频模型调用）

7. timeline_builder                        ← 含原 subtitle_asset_manager + ffmpeg_renderer_reviewer
   字幕生成 → 时间轴组装 → FFmpeg 渲染导出
```

**诊断工具（按需调用，不在主链）：**
- `observer`：健康检查 + 进度摘要（含原 reviewer）
- `master_orchestrator`：状态机主控，维护 task-card.md

## 关键生产规则

### 场景时长固定 5 秒

全链路刚性约束。叙事需要更长停留时用多个连续场景，不允许修改单场景时长。

### 每场景 4 张关键帧

| 帧 | 时间点 | 说明 |
|---|---|---|
| kf-01 | 0s | 起始帧，必须与上一场景 kf-04 视觉衔接 |
| kf-02 | 1.7s | 中间帧 A |
| kf-03 | 3.3s | 中间帧 B |
| kf-04 | 5s | 结束帧，供下一场景 kf-01 衔接 |

### 图片生成三个检查点

1. 角色基准图全部生成 → 展示路径 → 等用户确认后继续
2. 场景地点参考图完成 → 快速确认
3. 每个场景 4 张图完成 → 展示路径 → 确认再继续下一场景

### 上下文防污染

Claude 不得将图片/视频文件内容读入对话上下文。生成结果只通过文件路径展示，用户自行打开查看。

## 会话连续性

Claude 每次操作前必须先读 `orchestration/task-card.md` + `orchestration/state.json`，然后输出一行状态确认再行动。task-card.md 由 master_orchestrator 在每次阶段推进后更新，格式固定、不超过 20 行。

## 项目目录结构

```
projects/<name>/
├── request.md
├── input/input.json                      模型配置、时长、画幅
├── brief/
│   ├── selected-concept.json             确认的创意方案
│   ├── character-prompts.json            角色多视角提示词
│   └── scene-prompts.json                场景提示词草稿
├── script/script.json
├── audio/
│   ├── voiceover.json
│   ├── bgm-selection.json
│   └── beat-grid.json
├── timeline/
│   ├── global-timeline.json              全局时间网格（5s 一格）
│   └── timeline.json                     最终渲染时间轴
├── storyboard/storyboard.json
├── assets/
│   ├── asset-plan.json                   角色/场景/关键帧生成计划
│   ├── character-manifest.json           角色基准图路径索引
│   ├── manifest.json                     全素材索引
│   └── images/
│       ├── characters/                   角色基准图（多视角）
│       ├── locations/                    场景参考图
│       └── scenes/                       场景关键帧（每场景 4 张）
├── video/clips.json
├── subtitles/subtitles.json
├── outputs/
│   ├── render-plan.json
│   └── final.mp4
├── orchestration/
│   ├── state.json                        当前工作流阶段
│   ├── task-card.md                      ⭐ 会话锚点（每轮推进后更新）
│   ├── plan.json
│   └── decisions.jsonl
├── events/events.jsonl                   不可变事件日志
└── costs/poe-usage.jsonl
```

## 仓库结构

```
cucumis-aigc/
├── skills/                     9 个 skill 模块
│   ├── master_orchestrator/
│   ├── creative_design/
│   ├── script_writer/
│   ├── audio_foundation/       ← 含 global_timeline_initializer
│   ├── beat_sync_storyboard_planner/
│   ├── image_generator/
│   ├── constrained_video_generator/
│   ├── timeline_builder/       ← 含 subtitle_asset_manager + ffmpeg_renderer_reviewer
│   └── observer/               ← 含 reviewer
├── scripts/                    Python 执行入口（各 skill 独立脚本仍保留）
├── schemas/                    JSON Schema 数据契约
├── workflows/video_pipeline/   工作流定义文档
├── templates/                  项目初始化模板
├── projects/                   活跃项目实例
├── tests/
└── docs/plans/
```

## 快速开始

```bash
# 环境配置
echo "POE_API_KEY=your-key" > .env

# 新建项目
python3 scripts/init_project.py --request "60秒KOF大蛇封印史诗预告"

# 逐阶段执行
python3 scripts/run_creative_design.py --project <name>
python3 scripts/run_script_writer.py --project <name>
python3 scripts/run_audio_foundation.py --project <name>
python3 scripts/run_global_timeline_initializer.py --project <name>
python3 scripts/run_beat_sync_storyboard_planner.py --project <name>
python3 scripts/run_image_generator.py --project <name> --phase all
python3 scripts/run_constrained_video_generator.py --project <name>
python3 scripts/run_timeline_builder.py --project <name>
python3 scripts/run_ffmpeg_renderer_reviewer.py --project <name> --enable-ffmpeg-export

# 诊断
python3 scripts/observe_project.py --project <name>
python3 scripts/validate_project.py --project <name>

# 上下文太长时续跑
python3 scripts/session_handoff.py --project <name>
```

## 路线图

- **v1（当前）**：本地单机闭环，9 步主链，人工检查点，会话连续性
- **v2**：模板化批量生产，风格一致性增强，多项目管理
- **v3**：产品化控制台，权限协作，商业场景适配
