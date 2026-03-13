# Poe Media SDK Design

**Date:** 2026-03-13

## Purpose

为 `cucumis-aigc` 增加基于 Poe API 的媒体生成接入层，使项目可以在音频与视频阶段使用 Poe 订阅能力完成真实生成，同时保持当前 skill/workflow 的边界清晰。

## Goals

- 通过 `.env` 读取 Poe 认证信息
- 在项目级 `input/input.json` 中声明默认 `audio_model` 与 `video_model`
- 提供一个轻量 Poe SDK 适配层，统一处理模型目录、请求发送、结果解析和成本记录
- 将 `audio_foundation` 与 `constrained_video_generator` 接到该 SDK
- 在没有 Poe 密钥时保留可测试的离线 mock fallback

## Non-Goals

- 不在这一版接入 Web UI
- 不实现多 provider 抽象
- 不为所有视频模型做参数级深度适配
- 不要求第一版支持所有 Poe 媒体输出格式的复杂分支

## Configuration Model

### `.env`

仓库根目录 `.env` 只保存认证与连接信息：

- `POE_API_KEY`
- `POE_BASE_URL=https://api.poe.com/v1`

### Project Input

项目级默认模型放在 `projects/<project>/input/input.json`：

- `audio_model`
- `video_model`

这样同一仓库内的不同项目可以自由切换媒体模型，而不会污染全局配置。

## SDK Layout

建议新增：

```text
scripts/poe/
  __init__.py
  client.py
  catalog.py
  media.py
  usage.py
```

### `client.py`

负责：

- 读取 `.env`
- 创建带认证 header 的请求
- 与 Poe OpenAI-compatible API 通信
- 返回 JSON 结果或统一错误

### `catalog.py`

负责：

- 获取 `/v1/models`
- 过滤出 audio/video 模型
- 规范化模型信息
- 标记推荐模型
- 生成 `price_display`

### `media.py`

负责：

- `generate_audio(...)`
- `generate_video(...)`
- 统一结果解析
- 在无密钥时返回 deterministic mock

### `usage.py`

负责：

- 获取余额
- 读取 points history
- 归一化 `cost_points`

## Artifact Design

### Audio Stage

`audio_foundation` 在现有产物基础上新增：

- `audio/tts-response.json`
- `audio/usage.json`

### Video Stage

新增 `video/` 目录，`constrained_video_generator` 写出：

- `video/clips.json`
- `video/requests.json`
- `video/usage.json`

### Cross-Stage Cost Log

新增：

- `costs/poe-usage.jsonl`

每次 Poe 请求记录：

- `timestamp`
- `skill`
- `model`
- `request_id`
- `cost_points`
- `output_path`

## Runtime Integration

### `run_input_parser.py`

解析原始需求时保留项目级默认模型字段，若未显式指定则写入推荐默认值。

### `run_audio_foundation.py`

优先使用 Poe 生成音频；无密钥时回退到 mock。写出标准音频结构与 Poe 响应摘要/成本信息。

### `run_constrained_video_generator.py`

读取 `storyboard/storyboard.json` 与项目 `video_model`，逐 scene 生成或模拟生成视频片段，并写出请求与 usage 信息。

### `list_poe_models.py`

新增辅助脚本，用于列出当前可用的 audio/video 模型及价格展示字段。

## Testing Strategy

- 为 Poe catalog 和 media 适配层写单元测试
- 为 `run_input_parser.py` 补模型字段测试
- 为 `run_audio_foundation.py` 增加 Poe metadata/usage 测试
- 为 `run_constrained_video_generator.py` 增加端到端脚本测试
- 所有测试默认使用 mock fallback，不依赖真实网络或真实密钥
