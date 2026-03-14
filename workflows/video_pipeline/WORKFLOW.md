# Video Pipeline Workflow

## Purpose

`video_pipeline` 是 `cucumis-aigc` 的默认听觉驱动工作流定义，描述从自然语言需求到本地视频产出的标准闭环。它不负责实现具体能力，而负责定义阶段顺序、每阶段目标、产物位置和人工介入点。

该 workflow 默认由 `skills/master_orchestrator/SKILL.md` 解释和推进。

## Workflow Goal

第一版当前已可执行并可调试的主链覆盖 12 个默认阶段。
其中第 7 到 11 阶段当前为稳定 mock 产物实现，用于打通交接与调试闭环。

整个默认标准链为：

1. `creative_design`
2. `script_writer`
3. `audio_foundation`
4. `global_timeline_initializer`
5. `beat_sync_storyboard_planner`
6. `keyframe_planner`
7. `prompt_engineer`
8. `image_generator`
9. `constrained_video_generator`
10. `subtitle_asset_manager`
11. `timeline_builder`
12. `ffmpeg_renderer_reviewer`

其目标不是一次性生成高质量最终视频，而是先建立一条能稳定运行、能持久化中间产物、能校验交接的听觉驱动主链路。

## Stage Order

### 1. `creative_design`

- 读取客户原始一句话诉求或粗糙需求
- 串行执行 `creative_brief_intake` 与 `input_parser`
- 先通过多轮引导补齐关键字段
- 写入 `projects/<project>/brief/creative-brief.md`
- 同步覆盖写入 `projects/<project>/request.md`
- 写入 `projects/<project>/input/input.json`

### 2. `script_writer`

- 读取结构化任务配置
- 产出带情绪标注的脚本文档
- 写入 `projects/<project>/script/script.json`

### 3. `audio_foundation`

- 读取带情绪标注的脚本
- 产出配音时间戳、BGM 匹配结果和节拍网格
- 写入 `projects/<project>/audio/voiceover.json`
- 写入 `projects/<project>/audio/bgm-selection.json`
- 写入 `projects/<project>/audio/beat-grid.json`

### 4. `global_timeline_initializer`

- 读取音频基建产物
- 产出全局时间网格
- 写入 `projects/<project>/timeline/global-timeline.json`

### 5. `beat_sync_storyboard_planner`

- 读取脚本和全局时间网格
- 产出严格限时的分镜
- 写入 `projects/<project>/storyboard/storyboard.json`

## Required Runtime Behavior

- 主控应将当前状态、执行计划和关键决策写入 `projects/<project>/orchestration/`
- 每一阶段开始与结束都必须写事件日志
- 每一阶段只读自己声明的输入，不隐式依赖其他临时文件
- 每一阶段失败时必须写错误事件，并保留已生成产物
- 主流程允许人工中断与重跑，但不得覆盖未明确替换的产物
- 分镜及其后续阶段必须服从已锁定的音频时间网格

## Project Layout Assumption

一个 workflow 实例对应 `projects/<project-name>/` 下的一个项目目录。工作流中的每个阶段都只能在该目录及其标准子目录内读写。

## Non-Goals

- 不定义 LLM 提示词细节
- 不定义具体模型供应商
- 不定义复杂调度器实现
- 不要求第一版接入真实图像、视频、配音或字幕生成能力
