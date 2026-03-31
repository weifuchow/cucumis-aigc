import { readdir, stat } from "node:fs/promises";
import path from "node:path";

import { PROJECTS_ROOT } from "@/lib/config";

export type ArtifactType =
  | "character_images"
  | "location_images"
  | "scene_keyframes"
  | "prompt_bundle"
  | "script_output"
  | "storyboard_output"
  | "timeline_output"
  | "voiceover_audio"
  | "bgm_assets"
  | "beat_grid"
  | "video_clips"
  | "render_plan"
  | "final_video";

type ArtifactDefinition = {
  title: string;
  description: string;
  files?: string[];
  directories?: string[];
};

const ARTIFACT_REGISTRY: Record<ArtifactType, ArtifactDefinition> = {
  character_images: {
    title: "角色图",
    description: "角色基准图、多角度角色资产。",
    directories: ["assets/images/characters"],
  },
  location_images: {
    title: "场景图",
    description: "场景地点、环境与氛围参考图。",
    directories: ["assets/images/locations"],
  },
  scene_keyframes: {
    title: "关键帧",
    description: "按场景生成的关键帧和视觉连续性结果。",
    directories: ["assets/images/scenes"],
  },
  prompt_bundle: {
    title: "方案与提示词",
    description: "创意方案、提示词和输入上下文。",
    files: ["brief/selected-concept.json", "prompts/prompts.json", "input/input.json", "request.md"],
  },
  script_output: {
    title: "脚本结果",
    description: "脚本正文和叙事文稿。",
    files: ["script/script.json"],
  },
  storyboard_output: {
    title: "分镜结果",
    description: "分镜、关键帧规划与场景拆解。",
    files: ["storyboard/storyboard.json", "keyframes/keyframes.json"],
  },
  timeline_output: {
    title: "时间轴结果",
    description: "全局时间网格与字幕/剪辑时间轴。",
    files: ["timeline/global-timeline.json", "timeline/timeline.json", "subtitles/subtitles.json"],
  },
  voiceover_audio: {
    title: "配音结果",
    description: "配音内容与 TTS 响应产物。",
    files: ["audio/voiceover.json", "audio/tts-response.json"],
  },
  bgm_assets: {
    title: "BGM 结果",
    description: "BGM 规划与使用记录。",
    files: ["audio/bgm-selection.json", "audio/usage.json"],
  },
  beat_grid: {
    title: "节拍结果",
    description: "节拍网格与音频节奏约束。",
    files: ["audio/beat-grid.json"],
  },
  video_clips: {
    title: "视频片段",
    description: "中间视频片段和视频请求记录。",
    files: ["video/clips.json", "video/requests.json", "video/usage.json"],
  },
  render_plan: {
    title: "导出计划",
    description: "渲染计划与输出编排。",
    files: ["outputs/render-plan.json"],
  },
  final_video: {
    title: "最终成片",
    description: "可直接预览的最终视频。",
    files: ["outputs/final.mp4"],
  },
};

async function pathExists(filePath: string) {
  try {
    await stat(filePath);
    return true;
  } catch {
    return false;
  }
}

async function listFilesRecursive(rootPath: string, relativeRoot = ""): Promise<string[]> {
  const entries = await readdir(rootPath, { withFileTypes: true });
  const files: string[] = [];

  for (const entry of entries) {
    const absolutePath = path.join(rootPath, entry.name);
    const relativePath = path.join(relativeRoot, entry.name);

    if (entry.isDirectory()) {
      files.push(...(await listFilesRecursive(absolutePath, relativePath)));
      continue;
    }

    files.push(relativePath);
  }

  return files;
}

export function getArtifactDefinition(type: string) {
  return ARTIFACT_REGISTRY[type as ArtifactType] ?? {
    title: type,
    description: "",
  };
}

export async function collectArtifactPathsByType(projectId: string, type: string) {
  const definition = getArtifactDefinition(type);
  const projectRoot = path.join(PROJECTS_ROOT, projectId);
  const paths = new Set<string>();

  for (const file of definition.files ?? []) {
    if (await pathExists(path.join(projectRoot, file))) {
      paths.add(file);
    }
  }

  for (const directory of definition.directories ?? []) {
    const absoluteDirectory = path.join(projectRoot, directory);
    if (!(await pathExists(absoluteDirectory))) {
      continue;
    }

    const nestedFiles = await listFilesRecursive(absoluteDirectory, directory);
    for (const file of nestedFiles) {
      if (!file.endsWith(".gitkeep")) {
        paths.add(file);
      }
    }
  }

  return Array.from(paths).sort();
}
