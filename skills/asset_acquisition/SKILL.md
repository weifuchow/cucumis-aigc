---
name: asset-acquisition
description: Unified material acquisition skill for video projects. Use when the user wants to find, download, import, or build a reusable local asset library including images, videos, GIFs, scene references, BGM, ambience, or sound effects. Handles user-approved URLs, stock API search, browser-assisted Pixabay Music downloads, local browser download imports, manifests, and downstream handoff.
---

# asset_acquisition

## Purpose

统一处理项目素材获取：根据用户描述或用户提供的 URL，下载/导入图片、视频、GIF、参考图、BGM、环境声和音效，写入本地素材库和 manifest，减少后续 AI 生成成本。

## Use When

- 用户要求“找素材 / 下载素材 / 建素材库 / 获取图片视频音频 / BGM / 音效 / 场景参考”
- 用户给出可使用的图片、视频、音频、GIF 或参考素材 URL
- 用户已经通过浏览器下载了音频，需要导入项目
- 需要先建立本地素材库，再进入 `material_ingest`、`constrained_video_generator` 或 `timeline_builder`

## Interaction Policy

信息模糊时不要立刻下载。先把需求收敛成可执行素材 brief，直到用户明确确认“开始下载 / 确认生成 / 执行”。

必须确认：

- 当前 project：优先使用用户指定项目；否则从当前工作目录或最近项目推断，并向用户确认一次。
- 视频用途和主题：一句话内容、受众、时长、平台。
- 素材来源：用户 URL、官方 stock API、Pixabay Music 浏览器下载、已有本地/浏览器下载文件，可混合。
- 场景拆分：每个场景要有 `scene_id`、画面内容、关键词、情绪、所需 `media_types`。
- 统一风格：所有查询继承同一 `style`，除非用户明确指定局部变化。
- 画幅和尺寸：默认短视频 `9:16`、1080x1920；横屏默认 `16:9`、1920x1080。必须确认。
- 每类素材备选数量：默认每个场景每类 2 个备选；BGM 默认 3 个候选方向。
- 音频策略：区分 BGM、环境声、音效、转场/impact。Freesound 主要用于音效和环境声；Pixabay Music 用浏览器辅助挑选 BGM。

执行前给用户一个简短确认摘要：project、场景列表、统一风格、画幅/尺寸、每类素材数量、BGM 下载策略、是否更新 `assets/manifest.json`。

## Providers

优先使用官方 API 或用户确认的素材 URL：

- Pexels：图片、视频，需要 `PEXELS_API_KEY`
- Pixabay：图片、视频，需要 `PIXABAY_API_KEY`
- Freesound：音效和环境声，需要 `FREESOUND_API_KEY`
- Pixabay Music：BGM 走 `pixabay_music_browser_curator`
- 用户 URL：走 `scripts/run_resource_downloader.py`
- 浏览器已下载音频：走 `scripts/import_browser_audio_downloads.py`

说明：

- 默认从 repo 根目录 `.env` 读取 API key；也可通过 `--env-file` 指定。
- 没有 API key 时，stock 脚本会在 manifest 里写入可人工打开的搜索 URL，不做网页抓取。
- 不绕过登录、付费墙、DRM、验证码或平台下载限制。

## Input Files

统一 brief 推荐写入：

- `projects/<project>/assets/asset-acquisition-request.json`

如果是 stock API 搜索，兼容现有脚本格式：

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
  ],
  "resources": [
    {
      "url": "https://example.com/reference.webp",
      "title": "market reference",
      "media_type": "image",
      "tags": ["reference", "market"],
      "license": "user-approved",
      "source": "example"
    }
  ]
}
```

User URL 下载清单可为 JSON 数组或包含 `resources` 数组；txt 格式为一行一个 URL。视觉和音频资源可拆成：

- `projects/<project>/assets/visual-resources.json`
- `projects/<project>/assets/audio-resources.json`

## Writes

- `projects/<project>/materials/images/*`
- `projects/<project>/materials/videos/*`
- `projects/<project>/materials/visual/*`
- `projects/<project>/materials/audio/ambience/*`
- `projects/<project>/materials/audio/bgm/*`
- `projects/<project>/assets/stock-curation-manifest.json`
- `projects/<project>/assets/downloaded-visual-manifest.json`
- `projects/<project>/assets/downloaded-audio-manifest.json`
- `projects/<project>/assets/browser-audio-tracks.json`
- 可选更新 `projects/<project>/assets/manifest.json`

## Commands

Stock API 搜索/下载：

```bash
python3 scripts/run_asset_acquisition.py \
  --project projects/<project> \
  --request projects/<project>/assets/stock-search-request.json \
  --per-query 2 \
  --material-library-root materials \
  --update-asset-manifest
```

先看候选、不下载：

```bash
python3 scripts/run_asset_acquisition.py \
  --project projects/<project> \
  --request projects/<project>/assets/stock-search-request.json \
  --material-library-root materials \
  --dry-run
```

用户确认 URL 下载视觉素材：

```bash
python3 scripts/run_resource_downloader.py \
  --project projects/<project> \
  --kind visual \
  --resources projects/<project>/assets/visual-resources.json \
  --output-subdir materials/visual \
  --update-asset-manifest
```

用户确认 URL 下载音频素材：

```bash
python3 scripts/run_resource_downloader.py \
  --project projects/<project> \
  --kind audio \
  --resources projects/<project>/assets/audio-resources.json \
  --output-subdir materials/audio/bgm \
  --update-asset-manifest
```

导入浏览器下载的 BGM：

```bash
python3 scripts/import_browser_audio_downloads.py \
  --project projects/<project> \
  --tracks projects/<project>/assets/browser-audio-tracks.json \
  --output-subdir materials/audio/bgm \
  --update-asset-manifest
```

## Recommended Workflow

1. 访谈并生成素材 brief，不下载。
2. 写入 `asset-acquisition-request.json`；需要调用现有 stock 脚本时同步写 `stock-search-request.json`。
3. 对 stock/API 素材先运行 `--dry-run` 查看候选和人工搜索 URL。
4. 用户确认后运行正式下载。
5. 对用户 URL，按 media type 拆到 `visual-resources.json` / `audio-resources.json` 并运行 `run_resource_downloader.py`，输出目录必须在 `materials/` 下。
6. 对 BGM 调用 `pixabay_music_browser_curator`，给 3 个以上备选；用户确认曲目或明确“全部下载”后，用浏览器下载。
7. 把浏览器下载文件名、页面 URL、作者、license、tags 写入 `browser-audio-tracks.json` 并导入。
8. 校验本地文件存在、manifest 可解析，并汇总图片/视频/音频数量。

## Downstream Handoff

素材下载完成后，如果用户希望“把素材串成一个具体短片”，先判断项目当前是否已有脚本和分镜：

- 已有 `script/script.json`、`storyboard/storyboard.json`、`timeline/global-timeline.json`：
  - 进入 `constrained_video_generator`，把本地图片/视频素材分配到 scene。
  - 然后进入 `timeline_builder`，生成字幕、组装 `timeline/timeline.json`、写 `outputs/render-plan.json`。
- 只有下载素材、主题和风格，还没有脚本/分镜：
  - 进入 `editorial_orchestrator` 的 `material_editorial` 工作流。
  - 先用 `material_ingest` / `material_understanding` 建立素材目录、关系和风格摘要。

建议下载完成后写入编排状态：

```bash
python3 scripts/update_orchestration_state.py \
  --project projects/<project> \
  --current-stage asset_acquisition \
  --completed-stage asset_acquisition \
  --next-stage material_ingest \
  --workflow-state material_editorial \
  --phase asset_handoff \
  --resume-from assets/manifest.json \
  --decision-type asset_download_completed \
  --decision-reason "Assets downloaded and ready for material editorial handoff."
```

如果项目已经有完整分镜，则把 `--next-stage` 改为 `constrained_video_generator`。

## Runtime Expectations

- 只使用官方 API 或用户确认的素材 URL
- 下载素材必须记录 `source_url`、`provider`/`source`、`license`、`author`、`query` 或 `tags`
- 同一项目的下载素材统一存放在 `materials/` 下，不写入 `assets/curated`、`assets/downloaded`、`audio/curated` 或 `audio/downloaded`
- 同一项目的风格词、画幅、尺寸必须一致写入 request 和 manifest
- 每个场景尽量提供多个备选，不要只下载一个唯一素材
- 后续发布前要审查人物、商标、品牌露出和具体授权限制
- `assets/manifest.json` 只登记已下载到本地的素材
