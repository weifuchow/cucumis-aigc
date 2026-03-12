# Video Pipeline Workflow

## Purpose

`video_pipeline` 是 `cucumis-aigc` 的主工作流定义，描述从自然语言需求到本地视频产出的最小闭环。它不负责实现具体能力，而负责定义阶段顺序、每阶段目标、产物位置和人工介入点。

## Workflow Goal

第一版最小闭环是：

1. 输入解析
2. 脚本生成
3. 分镜规划
4. 时间轴构建
5. 渲染占位输出

其目标不是一次性生成高质量最终视频，而是先建立一条能稳定运行、能持久化中间产物、能校验交接的主链路。

## Stage Order

### 1. `input_parser`

- 读取用户任务输入
- 产出结构化任务配置
- 写入 `projects/<project>/input/input.json`

### 2. `script_writer`

- 读取结构化任务配置
- 产出脚本文档
- 写入 `projects/<project>/script/script.json`

### 3. `storyboard_planner`

- 读取脚本
- 产出 scene 级分镜结构
- 写入 `projects/<project>/storyboard/storyboard.json`

### 4. `timeline_builder`

- 读取分镜和已有素材引用
- 产出渲染器无关的时间轴
- 写入 `projects/<project>/timeline/timeline.json`

### 5. `ffmpeg_renderer`

- 读取时间轴
- 生成渲染计划或占位输出
- 写入 `projects/<project>/outputs/render-plan.json`

## Required Runtime Behavior

- 每一阶段开始与结束都必须写事件日志
- 每一阶段只读自己声明的输入，不隐式依赖其他临时文件
- 每一阶段失败时必须写错误事件，并保留已生成产物
- 主流程允许人工中断与重跑，但不得覆盖未明确替换的产物

## Project Layout Assumption

一个 workflow 实例对应 `projects/<project-name>/` 下的一个项目目录。工作流中的每个阶段都只能在该目录及其标准子目录内读写。

## Non-Goals

- 不定义 LLM 提示词细节
- 不定义具体模型供应商
- 不定义复杂调度器实现
- 不要求第一版接入真实图像、视频、配音或字幕生成能力
