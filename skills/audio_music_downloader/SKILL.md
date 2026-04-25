---
name: audio-music-downloader
description: Download reusable audio, music, sound effect, and BGM assets from user-approved URLs into a project, write manifests, and optionally register them in assets/manifest.json so later pipeline stages can use local files instead of generating audio.
---

# audio_music_downloader

## Purpose

提前下载可复用的音乐、BGM、音效、环境声、旁白参考音频，减少对 AI 音频生成的依赖。

## Use When

- 用户给出音乐、音效、BGM、环境声、参考音频下载链接
- 用户已经通过浏览器下载了可用音频，需要导入当前 project
- 需要为某个项目预置本地音频素材
- 希望后续 `audio_foundation`、剪辑、混音阶段直接引用本地文件

## Inputs

- `projects/<project>/assets/audio-resources.json` 或任意 JSON/txt URL 清单

JSON 可为数组或包含 `resources` 数组：

```json
[
  {
    "url": "https://example.com/bgm.mp3",
    "title": "soft opening bgm",
    "tags": ["bgm", "warm"],
    "license": "user-approved",
    "source": "example"
  }
]
```

txt 格式为一行一个 URL。

## Writes

- `projects/<project>/audio/downloaded/*`
- `projects/<project>/assets/downloaded-audio-manifest.json`
- 可选更新 `projects/<project>/assets/manifest.json` 的 `audio` 字段

## Command

```bash
python3 scripts/run_resource_downloader.py \
  --project projects/<project> \
  --kind audio \
  --resources projects/<project>/assets/audio-resources.json \
  --update-asset-manifest
```

如果音频是通过浏览器下载到 `~/Downloads`，先写一份带文件名和来源信息的 tracks JSON，再导入：

```bash
python3 scripts/import_browser_audio_downloads.py \
  --project projects/<project> \
  --tracks projects/<project>/assets/browser-audio-tracks.json \
  --update-asset-manifest
```

## Runtime Expectations

- 只下载用户明确提供或确认可使用的 URL
- 不绕过登录、付费墙、DRM 或平台下载限制
- 保留 `source_url`、`license`、`source`、`tags`，方便之后审查版权和来源
- 支持格式：`.mp3`、`.wav`、`.m4a`、`.aac`、`.ogg`、`.flac`
- 下载失败时查看 `downloaded-audio-manifest.json` 的 `failures`
- 浏览器下载导入时必须记录实际文件名、曲目页面 URL、作者、license、用途角色（如 `bgm` / `sfx` / `ambience`）
