---
name: pixabay-music-browser-curator
description: Use the in-app browser to help a user search Pixabay Music by video topic, scene mood, and keywords, curate suitable BGM tracks, download confirmed or explicitly batch-approved tracks, then import browser downloads into the project audio library and manifests.
---

# pixabay_music_browser_curator

## Purpose

根据视频主题、场景描述、情绪和节奏，协助用户在 Pixabay Music 页面挑选合适 BGM，并把确认或批量授权下载的音频整理成本地素材库。

## Use When

- 用户希望找适合场景描述的 BGM
- Pixabay Music 没有稳定公开 API，需要浏览器人机协作
- 用户已登录 Pixabay 或愿意在浏览器中处理登录/下载确认
- `stock_asset_curator` 已完成图片、视频、音效 API 下载，但需要补充 BGM

## Workflow

1. 把用户的视频主题、场景、情绪、节奏转成英文搜索词。
2. 在浏览器打开 Pixabay Music 搜索页。
3. 帮用户筛候选：标题、作者、时长、风格、页面 URL、标签和适用场景。
4. 用户确认曲目，或明确说“全部下载/不用问/全要”后，再点击下载。
5. 下载完成后，记录浏览器实际下载文件名，并写入：
   - `projects/<project>/assets/browser-audio-tracks.json`
6. 运行导入脚本，把文件整理到：
   - `projects/<project>/audio/downloaded/`
   - `projects/<project>/assets/downloaded-audio-manifest.json`
7. 可选合并到：
   - `projects/<project>/assets/manifest.json`

## Browser Safety

- 不绕过登录、验证码、付费墙或平台限制
- 登录、验证码、邮箱验证、敏感信息输入由用户接管
- 下载前必须让用户确认曲目；如果用户明确说“全部下载/不用问/全要”，这视为对当前候选的批量确认
- 保存 `source_url`、`license`、`source`、`author`、`tags`

## Suggested Search Terms

- 古风神话：`epic cinematic asian fantasy`, `ancient dramatic orchestra`
- 温暖叙事：`warm emotional storytelling`, `gentle piano cinematic`
- 紧张冲突：`dark suspense cinematic`, `dramatic action trailer`
- 童话绘本：`magical fairy tale`, `soft fantasy adventure`
- 科技商业：`corporate technology upbeat`, `future innovation ambient`

## Manifest Notes

Pixabay Music 的素材来源建议记录：

```json
{
  "source": "Pixabay Music",
  "license": "Pixabay Content License",
  "source_url": "曲目页面 URL",
  "author": "作者名",
  "tags": ["bgm", "cinematic"]
}
```

## Import Command

浏览器下载完成后，不手工拼 manifest，优先写 `browser-audio-tracks.json` 并运行：

```bash
python3 scripts/import_browser_audio_downloads.py \
  --project projects/<project> \
  --tracks projects/<project>/assets/browser-audio-tracks.json \
  --update-asset-manifest
```

`browser-audio-tracks.json` 示例：

```json
[
  {
    "filename": "justmeandmusic-rainy-cafe-lo-fi-chillhop-446208.mp3",
    "provider": "pixabay",
    "source": "Pixabay Music",
    "source_url": "https://pixabay.com/music/lofi-rainy-cafe-lo-fi-chillhop-446208/",
    "title": "Rainy Cafe Lo-Fi Chillhop",
    "author": "JustMeAndMusic",
    "license": "Pixabay Content License",
    "duration_seconds": 60,
    "role": "bgm",
    "use_case": "primary short-form BGM option",
    "tags": ["Lofi", "Chillhop", "Rainy Day", "Cafe Vibes"]
  }
]
```

导入后必须校验：

- `projects/<project>/audio/downloaded/*` 文件存在
- `projects/<project>/assets/downloaded-audio-manifest.json` 可解析
- `projects/<project>/assets/manifest.json` 的 `audio` 已包含导入曲目
