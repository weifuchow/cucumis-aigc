---
name: stock-asset-curator
description: Interactive stock material downloader for video projects. Use when the user asks to get, find, curate, or download reusable local素材/assets including images, videos, BGM, sound effects, or scene references. First guide the user through scene/style/music/size choices, then after explicit confirmation use existing API keys from .env plus browser-assisted Pixabay Music downloads to build a local project素材库 and write manifests.
---

# stock_asset_curator

## Purpose

根据用户的视频内容描述，多轮引导确认场景、统一风格、画幅尺寸、图片/视频/音频数量和音乐方向，然后使用本地 `.env` 里的 API key 自动下载匹配素材到当前 project。BGM 使用 Pixabay Music 浏览器辅助下载，并统一登记到项目素材库。

## Use When

- 用户只有“想做什么视频”的描述，还没有具体素材 URL
- 用户要求“帮我找素材/下载素材/素材库/图片视频音频/BGM/音效/场景素材”
- 需要先建立项目素材库，减少 AI 图片/视频/音频生成
- 需要为每个场景预下载参考图、氛围视频、环境音效、转场素材

## Interaction Policy

不要在第一次模糊输入后立刻下载。先把用户需求收敛成一个可执行素材 brief，直到用户明确确认“开始下载/确认生成/执行”。

必须引导确认：

- 当前 project：优先使用用户指定项目；否则从当前工作目录或最近项目推断，并向用户确认一次。
- 视频用途和主题：一句话内容、受众、时长、平台。
- 场景拆分：每个场景要有 scene_id、画面内容、关键词、情绪、所需 media_types。
- 统一风格：例如 cinematic documentary、clean SaaS、warm lifestyle、Chinese myth fantasy。所有查询都继承同一 `style`，除非用户明确指定局部变化。
- 画幅和尺寸：默认短视频 `9:16`、1080x1920；横屏默认 `16:9`、1920x1080。必须确认。
- 每类素材备选数量：默认每个场景每类 2 个备选；BGM 默认 3 个候选方向。若用户明确说“全部下载/不用问/全要”，可把候选 BGM 批量下载并记录；否则先让用户确认曲目。
- 音频策略：区分 BGM、环境声、音效、转场/impact。Freesound 主要用于音效和环境声；Pixabay Music 用浏览器辅助挑选 BGM。

当信息不足时，按最少问题继续追问。优先一次问 3-5 个关键问题，不要让用户填长表。

执行前必须给用户一个简短确认摘要，包括：

- project 目录
- 场景列表
- 统一风格
- 画幅/尺寸
- 每个场景要下载的图片/视频/音频数量
- 是否包含 BGM 浏览器辅助挑选，以及 BGM 是“确认后单首/多首下载”还是“候选全部下载”

## Providers

优先使用官方 API：

- Pexels：图片、视频，需要 `PEXELS_API_KEY`
- Pixabay：图片、视频，需要 `PIXABAY_API_KEY`
- Freesound：音效，需要 `FREESOUND_API_KEY`

说明：

- 默认从 repo 根目录 `.env` 读取 API key；也可通过 `--env-file` 指定。
- BGM 平台很多没有稳定公开 API。Pixabay Music 走 `pixabay_music_browser_curator`：搜索、试听、多候选、用户确认或明确“全部下载”后，通过浏览器下载，再用 `scripts/import_browser_audio_downloads.py` 导入项目。
- 没有 API key 时，脚本会在 manifest 里写入可人工打开的搜索 URL，不做网页抓取。

## Inputs

推荐写入：

- `projects/<project>/assets/stock-search-request.json`

示例：

```json
{
  "topic": "古风神话短视频",
  "platform": "douyin",
  "duration_seconds": 35,
  "aspect_ratio": "9:16",
  "orientation": "portrait",
  "target_size": {
    "width": 1080,
    "height": 1920
  },
  "style": "cinematic Chinese myth fantasy, dramatic warm light, consistent costume and color palette",
  "alternatives_per_scene": {
    "image": 2,
    "video": 2,
    "audio": 2,
    "bgm": 3
  },
  "queries": [
    {
      "scene_id": "s01",
      "scene": "ancient mountain temple at sunrise",
      "keywords": ["mist", "epic", "wide shot"],
      "media_types": ["image", "video"]
    },
    {
      "scene_id": "s02",
      "scene": "dragon roar and thunder atmosphere",
      "keywords": ["thunder", "wind", "impact"],
      "media_types": ["audio"]
    }
  ]
}
```

## Writes

- `projects/<project>/assets/curated/images/*`
- `projects/<project>/assets/curated/videos/*`
- `projects/<project>/audio/curated/*`
- `projects/<project>/audio/downloaded/*`
- `projects/<project>/assets/stock-curation-manifest.json`
- `projects/<project>/assets/downloaded-audio-manifest.json`
- 可选更新 `projects/<project>/assets/manifest.json`

## Command

```bash
python3 scripts/run_stock_asset_curator.py \
  --project projects/<project> \
  --request projects/<project>/assets/stock-search-request.json \
  --per-query 2 \
  --update-asset-manifest
```

先看候选、不下载：

```bash
python3 scripts/run_stock_asset_curator.py \
  --project projects/<project> \
  --request projects/<project>/assets/stock-search-request.json \
  --dry-run
```

如果 `.env` 不在当前工作目录：

```bash
python3 scripts/run_stock_asset_curator.py \
  --env-file /path/to/.env \
  --project projects/<project> \
  --request projects/<project>/assets/stock-search-request.json \
  --per-query 2 \
  --update-asset-manifest
```

导入浏览器下载的 BGM：

```bash
python3 scripts/import_browser_audio_downloads.py \
  --project projects/<project> \
  --tracks projects/<project>/assets/browser-audio-tracks.json \
  --update-asset-manifest
```

`browser-audio-tracks.json` 最小格式：

```json
[
  {
    "filename": "artist-track-title-123456.mp3",
    "provider": "pixabay",
    "source": "Pixabay Music",
    "source_url": "https://pixabay.com/music/example-track-123456/",
    "title": "Track Title",
    "author": "Artist",
    "license": "Pixabay Content License",
    "role": "bgm",
    "tags": ["bgm", "cinematic"]
  }
]
```

## Recommended Workflow

1. 访谈并生成素材 brief，不下载。
2. 写入 `projects/<project>/assets/stock-search-request.json`。
3. 先运行 `--dry-run` 查看候选和人工搜索 URL。
4. 给用户摘要候选覆盖情况；如果关键词偏了，调整 request。
5. 用户确认后运行正式下载。
6. 对 BGM 调用 `pixabay_music_browser_curator`，给 3 个以上备选；用户确认曲目或明确“全部下载”后，用浏览器下载。
7. 把浏览器下载文件名、页面 URL、作者、license、tags 写入 `projects/<project>/assets/browser-audio-tracks.json`。
8. 运行 `scripts/import_browser_audio_downloads.py` 导入 BGM，并合并 `assets/manifest.json`。
9. 最后校验本地文件存在、manifest 可解析，并汇总图片/视频/音频数量。

## Downstream Handoff

素材下载完成后，如果用户希望“把素材串成一个具体短片”，不要直接跳到最终 FFmpeg 渲染。先判断项目当前是否已有脚本和分镜：

- 已有 `script/script.json`、`storyboard/storyboard.json`、`timeline/global-timeline.json`：
  - 进入 `constrained_video_generator`，把本地图片/视频素材分配到 scene，必要时用本地 FFmpeg 做 Ken Burns、crossfade、sequence 等低成本动效。
  - 然后进入 `timeline_builder`，生成字幕、组装 `timeline/timeline.json`、写 `outputs/render-plan.json`，必要时导出 `outputs/final.mp4`。
- 只有下载素材、主题和风格，还没有脚本/分镜：
  - 进入 `editorial_orchestrator` 的 `material_editorial` 工作流。
  - 先用 `material_ingest` / `material_understanding` 建立素材目录、关系和风格摘要。
  - 再做 `creative_alignment`、`storyboard_draft`、`adjustment_planning`，确认后才进入 `audio_foundation` 和 `timeline_builder`。

建议下载器完成后写入编排状态，而不是无条件自动渲染：

```bash
python3 scripts/update_orchestration_state.py \
  --project projects/<project> \
  --current-stage stock_asset_curator \
  --completed-stage stock_asset_curator \
  --next-stage material_ingest \
  --workflow-state material_editorial \
  --phase asset_handoff \
  --resume-from assets/manifest.json \
  --decision-type asset_download_completed \
  --decision-reason "Stock assets downloaded and ready for material editorial handoff."
```

如果项目已经有完整分镜，则把 `--next-stage` 改为 `constrained_video_generator`。

## Runtime Expectations

- 只使用官方 API 或用户确认的素材 URL
- 不绕过登录、付费墙、DRM、平台下载限制
- 下载素材必须记录 `source_url`、`provider`、`license`、`author`、`query`
- 同一项目的风格词、画幅、尺寸必须一致写入 request 和 manifest
- 每个场景要尽量提供多个备选，不要只下载一个唯一素材
- 后续发布前要审查人物、商标、品牌露出和具体授权限制
- `assets/manifest.json` 只登记已下载到本地的素材
