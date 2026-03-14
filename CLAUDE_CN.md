# CLAUDE.md (中文版)

本文档为 Claude Code (claude.ai/code) 在此仓库工作时提供指导。

## 项目概述

**cucumis-aigc** 是一个本地化 AIGC 编排系统，用于短视频制作。它不是单一模型，而是集成工作流，将脚本生成、故事板、关键帧、图像生成、动态视频、配音、字幕、时间轴合成和渲染整合成一个可控、可追踪、可恢复的生产管道。

**核心哲学**：生产能力优于生成能力。系统强调编排、状态管理、恢复、审计和渲染，而不是优化单个生成步骤。

## 架构与设计原则

### 分层架构

```
用户意图
  ↓
工作流运行时 (Codex / Claude Code)
  ↓
技能模块 (18+ 单一职责业务能力模块)
  ↓
本地文件系统 (JSON 文件作为真实数据源)
  ↓
时间轴架构 (音频驱动的计时网格)
  ↓
FFmpeg 渲染器
  ↓
最终 MP4 输出
```

### 核心设计模式

1. **音频优先管道**：所有计时都锚定到音频（配音 + BGM 节拍网格）
2. **单一职责技能**：每个技能处理一项具体任务，无单体模块
3. **文件系统即数据库**：所有产物存储为 JSON 文件（人类可读、版本可控、完全可调试）
4. **事件溯源**：`events/events.jsonl` 中保存完整变更日志，用于重放和恢复
5. **显式状态管理**：项目状态存储在 `projects/<name>/orchestration/`
6. **分离时间轴逻辑**：`global_timeline_initializer` 创建音频驱动的时间网格；`timeline_builder` 合成最终渲染时间轴

### 12 阶段视频制作管道

1. `creative_design` - 输入 + 标准化
2. `script_writer` - 情感标签脚本生成
3. `audio_foundation` - 音频计时网格 (文字转语音、BGM 选择、节拍检测)
4. `global_timeline_initializer` - 全局时间锚点
5. `beat_sync_storyboard_planner` - 时间约束故事板
6. `keyframe_planner` - 视觉一致性锚点
7. `prompt_engineer` - 将故事板转换为模型提示词
8. `image_generator` - 静态图像生成
9. `constrained_video_generator` - 动态视频片段（带时间/运动约束）
10. `subtitle_asset_manager` - 字幕 + 资源清单
11. `timeline_builder` - 最终时间轴合成
12. `ffmpeg_renderer_reviewer` - 渲染为 MP4 + 质量检查

每个阶段都从文件系统读取输入，写入到自己的命名空间子目录，并更新编排状态。

## 项目结构

```
cucumis-aigc/
├── skills/                    # 18+ 技能模块（业务能力）
│   ├── creative_design/
│   ├── script_writer/
│   ├── audio_foundation/
│   ├── ... (更多技能)
├── scripts/                   # 23+ 可执行 Python 入口点
│   ├── run_creative_design.py
│   ├── run_script_writer.py
│   ├── run_image_generator.py
│   ├── ... (技能运行器)
│   ├── validate_project.py
│   ├── observe_project.py
│   ├── review_project.py
│   └── poe/                   # Poe API 集成
│       ├── client.py          # HTTP 包装器（从 .env 读取 POE_API_KEY）
│       ├── media.py           # 图像/音频生成助手
│       ├── usage.py           # 成本追踪
│       └── catalog.py         # 模型目录
├── schemas/                   # 14 个 JSON Schema 文件（数据契约）
│   ├── task-input.schema.json
│   ├── script.schema.json
│   ├── audio-foundation.schema.json
│   ├── timeline.schema.json
│   └── ... (更多 schema)
├── templates/                 # 项目初始化模板
│   ├── project/               # 标准项目结构
│   ├── prompts/
│   └── docs/
├── projects/                  # 活跃项目实例
│   └── dragon-fall-35s/        # 示例：完整填充的项目
├── workflows/
│   └── video_pipeline/        # 主工作流定义
│       ├── state-machine.md   # 工作流状态
│       └── handoff-contracts.md
├── tests/                     # Python unittest 测试套件
├── docs/plans/                # 14+ 设计与实现文档
└── examples/                  # 参考示例
```

## 项目目录结构（每个项目）

每个项目在 `projects/<project-name>/` 中遵循此结构：

```
README.md                          # 项目上下文
request.md                         # 原始客户请求
events/events.jsonl               # 不可变事件日志
orchestration/
  ├── state.json                  # 当前工作流状态
  ├── plan.json                   # 执行计划
  └── decisions.jsonl             # 人工干预决策
input/input.json                  # 标准化任务输入
script/script.json                # 带情感标记的脚本
audio/
  ├── voiceover.json
  ├── bgm-selection.json
  ├── beat-grid.json
  └── usage.json
storyboard/storyboard.json
keyframes/keyframes.json
prompts/prompts.json
assets/
  ├── manifest.json
  ├── images/
  └── image-usage.json
video/
  ├── clips.json
  └── usage.json
timeline/
  ├── global-timeline.json
  └── timeline.json
outputs/
  ├── render-plan.json
  └── final.mp4
review/
  ├── review-report.json
  └── observer-summary.md
costs/poe-usage.jsonl
```

## 常用开发命令

### 运行技能/脚本

所有技能都是 `scripts/` 目录下的可执行 Python 脚本：

```bash
# 初始化新项目
python scripts/init_project.py --request "你的视频简介"

# 运行单个技能（总是从文件系统读取项目状态）
python scripts/run_creative_design.py --project dragon-fall-35s
python scripts/run_script_writer.py --project dragon-fall-35s
python scripts/run_image_generator.py --project dragon-fall-35s
python scripts/run_ffmpeg_renderer_reviewer.py --project dragon-fall-35s

# 验证和观察
python scripts/validate_project.py --project dragon-fall-35s
python scripts/observe_project.py --project dragon-fall-35s
python scripts/review_project.py --project dragon-fall-35s
```

### 运行测试

```bash
# 运行所有测试
python -m pytest tests/

# 运行特定测试文件
python -m pytest tests/test_poe_sdk.py -v

# 运行单个测试
python -m pytest tests/test_poe_sdk.py::TestPoeSdkUsage -v
```

测试使用 Python 的 `unittest` 框架，并创建临时项目来验证完整管道。

### 环境设置

创建 `.env` 文件：

```
POE_API_KEY=your-poe-api-key
POE_BASE_URL=https://api.poe.com/v1
```

无 `requirements.txt` 或 `package.json` —— 项目仅使用 Python 标准库 + 系统 FFmpeg。

### 工具函数

```bash
# 查看可用的 LLM 模型
python scripts/list_poe_models.py

# 手动写入事件
python scripts/write_event.py --project <name> --event-type <type>

# 更新编排状态
python scripts/update_orchestration_state.py --project <name>

# 在会话间切换项目状态
python scripts/session_handoff.py --project <name>
```

## 关键模式与实践

### 1. 基于文件的状态管理

所有持久状态都保存到本地文件，没有内存中的运行时状态。这使得：
- 从文件系统完整恢复项目
- 人类调试和检查
- 版本控制兼容性
- 会话间轻松交接

### 2. 技能实现模式

每个技能：
- 从文件系统读取输入 (`projects/<name>/<stage>/`)
- 从 `schemas/` 读取 schema 验证契约
- 从 `orchestration/state.json` 读取编排状态
- 写入结果到其输出命名空间
- 追加到 `events/events.jsonl`
- 更新 `orchestration/state.json`
- 将成本记录到 `costs/poe-usage.jsonl`

### 3. 交接契约

每个技能在 `workflows/video_pipeline/handoff-contracts.md` 中有明确的输入/输出契约。新技能必须声明其依赖 —— 不要创建未声明的数据依赖。

### 4. 错误恢复

失败的阶段在编排状态中被标记。项目可以从特定检查点恢复，无需重新运行已完成的阶段。在继续前始终验证项目状态。

### 5. 成本追踪

每个技能的成本记录到 `costs/poe-usage.jsonl` 用于预算可见性。使用 `scripts/usage_audit.py` 汇总成本。

## 测试与验证

### 项目验证

```bash
python scripts/validate_project.py --project <name>
```

检查：
- 所有必需的目录存在
- 必需的 JSON 文件存在且根据 schema 有效
- 项目结构完整性
- 返回详细错误消息

### 质量审查

```bash
python scripts/review_project.py --project <name>
```

对 18 种不同产物类型的自动化结构化审查。

### 观察

```bash
python scripts/observe_project.py --project <name>
```

生成人类可读的项目状态，追踪已完成/跳过/失败的阶段。

## 未来工作重要注意事项

### 添加新技能时

1. 在 `schemas/` 中定义输入/输出 JSON schema
2. 更新 `workflows/video_pipeline/handoff-contracts.md`
3. 在 `skills/` 中创建技能模块
4. 创建运行器脚本 `scripts/run_<skill_name>.py`
5. 为 Codex/Claude Code 集成添加对应的 `agents/openai.yaml`
6. 在 `tests/` 中添加测试覆盖

### 修改管道流程时

- 使用新状态更新 `workflows/video_pipeline/state-machine.md`
- 记录阶段顺序和依赖关系
- 确保与现有项目目录的向后兼容性
- 使用现有项目（如 `dragon-fall-35s`）测试

### 项目调试

1. 检查 `projects/<name>/events/events.jsonl` 获取完整事件追踪
2. 检查 `orchestration/state.json` 查看当前阶段
3. 检查 `orchestration/decisions.jsonl` 查看人工干预
4. 检查每个阶段命名空间中的 JSON 文件（它们是人类可读的）
5. 运行 `observe_project.py` 查看高级状态

### Schema 验证

所有 JSON 文件应根据其 schema 验证。添加新数据结构时：
1. 在 `schemas/` 中创建 schema
2. 在技能实现中参考 schema
3. 写入前使用 `jsonschema` 库验证

## FFmpeg 渲染

`ffmpeg_renderer_reviewer` 消费时间轴 schema 并输出 MP4。关键文件：
- `timeline/timeline.json` - 最终渲染指令
- `scripts/run_ffmpeg_renderer_reviewer.py` - 渲染器实现
- `outputs/final.mp4` - 最终视频输出

FFmpeg 命令构建在技能实现中进行抽象。不要在此边界外构建原始 FFmpeg 命令。

## 项目 ID 生成

格式：`{prefix}-{YYYYMMDD-HHMMSS}-{random_hex}`
示例：`proj-20260314-104400-a1b2c3`

由 `init_project.py` 生成以确保唯一性和时间追踪。

## 设计哲学

- **不要过早抽象**：三行相似代码好于一个临时工具函数
- **严格分离关注点**：技能是单一职责的；编排与执行分离
- **显式化状态**：所有决策和转换都记录在文件系统中
- **启用审计**：所有操作的完整事件追踪和成本日志
- **优先本地执行**：最小化外部平台依赖以提高可靠性
- **为恢复设计**：任何阶段都可以失败并恢复，无数据丢失
