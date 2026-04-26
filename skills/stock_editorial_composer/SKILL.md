---
name: stock-editorial-composer
description: Build complete audio-first videos from external/downloaded/local materials, especially when AI image/video generation is disabled. This skill must explicitly plan, search, download, map, mix BGM/ambience, render rough cuts, add subtitles, and run gap review; optional AI generation is only a controlled fallback for material tiers 1/2.
---

# stock_editorial_composer

## Purpose

统一入口下的素材主导组合编排 skill：先用旁白确定故事、节奏和分镜，再按成本档位搜索/下载/导入素材，最后用本地 FFmpeg 完成 rough cut、混音、字幕和成片。

核心不是一次性下载完整素材，而是：

1. 统一入口确认主题、时长、画幅、旁白需求和成本档位。
2. 先完成脚本、旁白和音频时间轴。
3. 旁白与分镜确定后，才做第一轮素材搜索/下载/导入。
4. 建立 scene-to-asset 映射，同时准备 BGM、环境声和字幕。
5. 用首轮素材串成 rough cut。
6. 看片或检查分镜后发现缺口，进入第二轮补素材/补生成。
7. 只替换最弱场景，重新混音、重导出，直到故事、画面、声音都讲得通。

## Use When

- 用户说“0 成本 / 下载素材整合 / 不生成 / 用素材剪一版 / stock footage”
- 用户希望“统一入口”，但根据成本档位选择素材主导或生成主导
- 项目 `input/source_mode` 是 `local_materials`、`stock_materials` 或类似意图
- 已有旁白或脚本，需要素材辅助多轮补齐
- 已有下载素材，但成片缺少贴合旁白的镜头、BGM、环境声或转场声音
- master 入口判断用户不想走完整 AI 生成链路，但仍想得到可播放 MP4

## User-Visible Stage Contract

素材主导项目必须把下载和声音设计讲清楚。进入本 skill 后，给用户或 `task-card.md` 明确展示下面路径，不要把素材下载藏成内部实现：

1. 旁白文案和音频时间戳
2. 5s 固定场景分镜
3. 按场景生成素材搜索清单
4. 下载/导入视频和图片素材
5. 下载/导入 BGM、环境声或从素材中提取 ambience
6. 生成 scene-to-asset 映射
7. 渲染 rough cut
8. 加字幕
9. 看片后补最弱素材和重混音

每个阶段完成后，应更新 `orchestration/task-card.md`，并在 `events/events.jsonl` 记录关键产物路径。

## Relationship To Other Skills

- 入口仍由 `master_orchestrator` 判断模式和成本档位。
- 素材下载调用 `asset_acquisition` 的脚本与约定。
- 旁白和时间锚点复用 `script_writer`、`audio_foundation`。
- 分镜复用 `beat_sync_storyboard_planner`，但必须把 `asset_mode` 审成 `static` 或本地素材模式。
- 导出复用 `timeline_builder` / `run_ffmpeg_renderer_reviewer.py`。
- 根据成本档位决定是否调用 `image_generator` 或 `constrained_video_generator`。

## Operating Model

### 1. Unified Entry And Cost Tier

先写入或确认：

- `input/source_mode`: `stock_materials`、`hybrid_materials` 或 `generated`
- `input/production_mode`: `stock_editorial`、`hybrid_editorial` 或 `video_pipeline`
- `input/cost_tier`: 可继续兼容 `economy`、`standard`、`unlimited`
- `input/material_cost_tier`: `0`、`1` 或 `2`
- `input/requires_voiceover`: 是否需要旁白
- `input/bgm.required`: 情绪/风光/旁白短片默认 `true`
- `input/bgm.generate`: 档位 0 必须 `false`，优先用下载/导入 BGM；档位 1/2 可按需生成
- `input/ambience.required`: 素材片默认 `true`
- `input/subtitles.required`: 竖屏旁白片默认 `true`
- `input/subtitle_style`: 大字、最多两行、自动换行、底部安全区
- `input/audio_provider` 与 `input/poe_enabled`
- 目标时长、画幅、平台、语言、风格

素材主导档位 0 的强制约束：

- 不运行图片生成。
- 不运行视频生成。
- 缺素材先写补素材 request，不 fallback 到 AI 生成。
- BGM、环境声和字幕仍然是必须处理的成片层，不可省略。

成本档位定义：

| 档位 | `material_cost_tier` | 素材策略 | 生成策略 | 适用 |
|---|---:|---|---|---|
| 全外部素材 | `0` | 图片、视频、BGM、环境声全部下载或导入 | 不调用图片/视频生成；只允许 TTS | 预算严格、纪实/氛围/素材可替代性强 |
| 图像为主 + 少量视频模型 | `1` | 大量下载素材 + 必要图片生成 | 只把 1-2 个关键动态镜头交给视频模型 | 需要少量不可替代镜头 |
| 视频模型为主 | `2` | 下载素材作为参考、BGM、环境声和补充镜头 | 多数关键场景可调用视频模型 | 质量优先、预算较高 |

若用户只说主题，先产出脚本/旁白方向；不要直接下载一大包泛素材。第一轮素材必须等到旁白、主题、分镜方向稳定后再做。

### 2. Narration First

先让声音决定结构：

```bash
python3 scripts/run_script_writer.py --project projects/<project>
python3 scripts/run_audio_pipeline.py --project projects/<project>
```

如果 TTS 提供商失败，可用现有 provider 直连或 mock，但必须保证：

- `script/script.json` 有真实可朗读台词
- `audio/voiceover.json` 有可用分段
- `timeline/global-timeline.json` 和旁白分段对齐

### 3. Storyboard Before First Asset Search

旁白完成后，先做分镜结构，再搜索素材：

```bash
python3 scripts/run_beat_sync_storyboard_planner.py --project projects/<project>
```

人工或模型审查 `storyboard/storyboard.json`：

- 每条旁白对应一个或多个明确画面需求。
- 标出每个 scene 的素材需求：人物、动作、地点、物件、情绪、声音。
- 根据 `material_cost_tier` 标出 `asset_mode`：
  - `0`: `local_stock_video` / `local_stock_image`
  - `1`: 大多数 `local_stock_*`，少量 `generated_image` / `generated_video`
  - `2`: 多数关键场景允许 `generated_video`
- 档位 0 时，缺素材不直接生成，先写入补素材 request。

### 4. First Asset Pass: Explicit Material Download

第一轮素材搜索发生在旁白和分镜确定之后。首轮只覆盖分镜里的主需求，不追求一次到位：

- 场景建立：城市/人物/地点/时代/风格
- 核心动作：走路、看手机、窗边、车流、雨、空街等
- 声音底：BGM、ambience、关键 sound effects

写入：

- `assets/stock-search-request.json`
- `assets/audio-stock-search-request.json`
- `assets/manifest.json`
- `assets/scene-asset-map.json`（下载后写入或更新）

在运行下载前，必须对用户明确说明：

```
接下来会开始下载/导入外部素材：视频画面、BGM、环境声。下载完成后会把每个 5s 场景绑定到本地素材路径，再渲染 rough cut。
```

运行：

```bash
python3 scripts/run_asset_acquisition.py \
  --project projects/<project> \
  --request projects/<project>/assets/stock-search-request.json \
  --per-query 2 \
  --material-library-root materials \
  --update-asset-manifest
```

档位行为：

- `material_cost_tier=0`: 只运行素材下载/导入，不运行图片或视频生成。
- `material_cost_tier=1`: 先下载素材；只有明确缺口才运行图片生成或最多少量视频生成。
- `material_cost_tier=2`: 下载素材仍用于参考、BGM、环境声和替代镜头，但关键动态 scene 可进入视频生成链路。

素材下载验收：

- `scene-asset-map.json` 中每个 scene 都必须有本地 `materials/...` 路径或明确 `missing_reason`。
- 档位 0 不允许 `missing_reason` 触发生成，只能触发第二轮搜索。
- 下载失败时写 `events/events.jsonl`，并保留候选 URL、搜索词和失败原因。
- BGM 下载或导入要写入 `audio/bgm/bgm-main.*` 或 `materials/audio/bgm/...`，不要只停在候选列表。

### 5. Assemble Rough Cut With Complete Audio Layers

生成分镜后，逐场景绑定本地素材：

- `storyboard/storyboard.json`
- `video/clips.json`
- `subtitles/subtitles.json`
- `timeline/timeline.json`
- `outputs/final.mp4`
- `audio/bgm/bgm-main.*` 或等价 BGM bed
- `audio/mix-manifest.json` 或等价混音记录

要求：

- 每个 scene 的 `url` 指向本地 `materials/...` 文件。
- `asset_mode` 默认 `static` 或 `local_stock_video`，不要默认 `mixed`。
- 档位 0 不要把缺素材场景送去生成，先记录缺口。
- 档位 1/2 也应先判断下载素材是否足够，再决定是否生成。
- rough cut 至少保留三个可比版本名之一：`voiceover-only`、`with-ambience`、`full-audio`、`music-forward`、`subtitled`。

### 6. Second Pass Gap Review Loop

第二轮发生在 rough cut 已经串起来之后，而不是第一轮下载前。每轮 rough cut 后输出一个缺口列表，优先级从高到低：

1. 旁白提到具体动作/物件但画面没有，例如“手机静音”“窗边”“一个人走”。
2. 情绪转折画面不够明确，例如“孤独从空变满”“回到宁静”。
3. 声音缺层次，例如 BGM 听不见、雨声不明显、结尾没有 room tone。
4. 镜头重复或素材时长不足。
5. 授权不适合发布，例如 `CC BY-NC` 用于商用项目。

对缺口写补充请求或生成请求：

- `assets/story-specific-stock-search-request.json`
- `assets/audio-supplement-search-request.json`
- `assets/generation-gap-request.json`（仅档位 1/2 且用户同意时）

每轮只补最弱的 3-6 个点。下载后只替换对应 scene，不推倒全部结构。

### 7. Skip Unnecessary Stages

素材主导时可以跳过不必要阶段：

- 档位 0：跳过 `image_generator`、`constrained_video_generator`、AI keyframe consistency 检查。
- 档位 0：如已有可用 BGM/环境声，跳过 `bgm_generator`。
- 档位 1：只对 gap report 中明确标记的 scene 调用生成阶段。
- 档位 2：仍应保留素材下载作为 reference/audio/support，不强制跳过。

无论档位如何，都不要跳过：

- `script_writer`（或等价人工脚本）
- `audio_foundation`
- `beat_sync_storyboard_planner`
- `timeline_builder`
- 声音混音检查

### 8. Audio Bed Is Mandatory

有旁白不等于有声音设计。每版成片必须检查：

- BGM 是否可听，但不盖旁白。
- 开场是否有空间声，例如远车流、城市底噪。
- 中段是否按画面加入雨声、路声、环境声。
- 结尾是否有 room tone 或接近安静的氛围。
- 音乐走向是否匹配叙事段落：压抑段克制、离开段渐开、旅途段开阔、高潮段推起、回归段回落。

建议用 `ffmpeg volumedetect` 检查：

```bash
ffmpeg -hide_banner -nostats -i projects/<project>/audio/bgm-main.mp3 \
  -af volumedetect -f null - 2>&1 | tail -12
```

经验值：

- 单独 BGM/ambience bed 平均响度约 `-34 dB` 到 `-24 dB` 更容易被听见。
- 最终混音平均响度可在 `-22 dB` 到 `-15 dB` 左右，视旁白动态调整。
- 如果 BGM bed 低到 `-45 dB` 以下，多半会被用户感知为“没有 BGM”。
- 若用户反馈“没有 BGM”，优先输出 `music-forward` 版本，而不是仅声明文件存在。

### 8b. Subtitles Are Default For Vertical Voiceover Cuts

如果 `input/subtitles.required` 不是 `false`，rough cut 完成后必须加字幕：

- 从 `audio/voiceover.json` 的段落时间戳生成 `subtitles/subtitles.json`。
- 竖屏 9:16 默认大字，底部安全区，白字黑描边或等价高对比样式。
- 每条字幕最多两行；每行约 10-14 个中文字；长句拆成连续短字幕。
- 不要把完整旁白段落挤成一行。
- 输出硬字幕版本，例如 `outputs/*-subtitled.mp4`。
- 抽至少 3 个关键帧检查字幕是否出界、遮挡主体或太小。

### 9. Re-export

补素材或混音后必须重建：

```bash
python3 scripts/run_timeline_builder.py --project projects/<project>
python3 scripts/run_ffmpeg_renderer_reviewer.py \
  --project projects/<project> \
  --enable-ffmpeg-export
```

保留上一版：

- `outputs/final-v1.mp4`
- `outputs/final-before-audio-fix.mp4`
- 或用清晰的版本名

## Required Artifacts

- `assets/manifest.json`
- `assets/*stock-search-request.json`
- `assets/generation-gap-request.json`（档位 1/2 可选）
- `script/script.json`
- `audio/voiceover.json`
- `audio/bgm-selection.json`
- `audio/mix-manifest.json`
- `timeline/global-timeline.json`
- `storyboard/storyboard.json`
- `video/clips.json`
- `subtitles/subtitles.json`
- `timeline/timeline.json`
- `outputs/render-plan.json`
- `outputs/final.mp4`
- `review/stock-editorial-gap-report.md`（建议）

## Completion Criteria

- 最终视频可播放，时长满足用户约束。
- 旁白、字幕、画面段落对齐。
- 所有 scene 都有本地素材路径，不是 `missing://`。
- BGM 和环境声可被听见，并和画面阶段匹配。
- 若要求字幕，已输出带字幕版本且字幕大、短、可读。
- 已记录剩余缺口：素材不足、授权风险、声音风险或可选 AI 生成建议。
- 已记录成本档位及每个生成调用的理由；档位 0 不应出现图片/视频生成调用。
