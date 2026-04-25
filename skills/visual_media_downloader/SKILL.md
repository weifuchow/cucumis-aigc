---
name: visual-media-downloader
description: Download reusable video, image, stock footage, reference image, GIF, and visual assets from user-approved URLs into a project, write manifests, and optionally register them in assets/manifest.json so later pipeline stages can use local files instead of generating visuals.
---

# visual_media_downloader

## Purpose

提前下载可复用的视频、图片、参考图、GIF、素材镜头，减少对 AI 图片/视频生成的依赖。

## Use When

- 用户给出图片、视频、参考图、素材镜头下载链接
- 需要为某个项目预置本地视觉素材
- 希望后续 `image_generator`、`constrained_video_generator`、`timeline_builder` 直接引用本地文件

## Inputs

- `projects/<project>/assets/visual-resources.json` 或任意 JSON/txt URL 清单

JSON 可为数组或包含 `resources` 数组：

```json
[
  {
    "url": "https://example.com/scene-reference.webp",
    "title": "market reference",
    "tags": ["reference", "market"],
    "license": "user-approved",
    "source": "example"
  }
]
```

txt 格式为一行一个 URL。

## Writes

- `projects/<project>/assets/downloaded/*`
- `projects/<project>/assets/downloaded-visual-manifest.json`
- 可选更新 `projects/<project>/assets/manifest.json` 的 `images` / `videos` 字段

## Command

```bash
python3 scripts/run_resource_downloader.py \
  --project projects/<project> \
  --kind visual \
  --resources projects/<project>/assets/visual-resources.json \
  --update-asset-manifest
```

## Runtime Expectations

- 只下载用户明确提供或确认可使用的 URL
- 不绕过登录、付费墙、DRM 或平台下载限制
- 保留 `source_url`、`license`、`source`、`tags`，方便之后审查版权和来源
- 图片支持：`.png`、`.jpg`、`.jpeg`、`.webp`、`.gif`、`.bmp`、`.tiff`
- 视频支持：`.mp4`、`.mov`、`.m4v`、`.webm`、`.mkv`、`.avi`
- 下载失败时查看 `downloaded-visual-manifest.json` 的 `failures`

