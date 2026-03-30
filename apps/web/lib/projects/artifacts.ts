import { readFile } from "node:fs/promises";
import path from "node:path";

import { PROJECTS_ROOT } from "@/lib/config";
import type { ArtifactPreview } from "@/lib/projects/types";

const TEXT_EXTENSIONS = new Set([".json", ".md", ".txt", ".log", ".jsonl"]);
const IMAGE_EXTENSIONS = new Set([".png", ".jpg", ".jpeg", ".webp", ".gif"]);
const VIDEO_EXTENSIONS = new Set([".mp4", ".mov", ".webm", ".m4v"]);

export function resolveProjectPath(projectId: string, relativePath = ".") {
  const projectRoot = path.join(PROJECTS_ROOT, projectId);
  const absolutePath = path.resolve(projectRoot, relativePath);

  if (!absolutePath.startsWith(projectRoot)) {
    throw new Error("Invalid project path.");
  }

  return { projectRoot, absolutePath };
}

export function getMimeType(filePath: string) {
  const ext = path.extname(filePath).toLowerCase();

  if (ext === ".json") return "application/json";
  if (ext === ".jsonl") return "application/x-ndjson";
  if (ext === ".md") return "text/markdown; charset=utf-8";
  if (ext === ".txt" || ext === ".log") return "text/plain; charset=utf-8";
  if (ext === ".png") return "image/png";
  if (ext === ".jpg" || ext === ".jpeg") return "image/jpeg";
  if (ext === ".webp") return "image/webp";
  if (ext === ".gif") return "image/gif";
  if (ext === ".mp4" || ext === ".m4v") return "video/mp4";
  if (ext === ".mov") return "video/quicktime";
  if (ext === ".webm") return "video/webm";

  return "application/octet-stream";
}

export async function readArtifactPreview(projectId: string, relativePath: string): Promise<ArtifactPreview> {
  const { absolutePath } = resolveProjectPath(projectId, relativePath);
  const mimeType = getMimeType(absolutePath);
  const ext = path.extname(absolutePath).toLowerCase();

  if (IMAGE_EXTENSIONS.has(ext)) {
    return {
      type: "image",
      mimeType,
      path: relativePath,
      href: `/api/projects/${projectId}/artifacts?path=${encodeURIComponent(relativePath)}`,
    };
  }

  if (VIDEO_EXTENSIONS.has(ext)) {
    return {
      type: "video",
      mimeType,
      path: relativePath,
      href: `/api/projects/${projectId}/artifacts?path=${encodeURIComponent(relativePath)}`,
    };
  }

  const buffer = await readFile(absolutePath);
  const content = buffer.toString("utf-8");

  if (ext === ".json") {
    try {
      const payload = JSON.parse(content);
      return {
        type: "json",
        content: JSON.stringify(payload, null, 2),
        mimeType,
        path: relativePath,
      };
    } catch {
      return {
        type: "text",
        content,
        mimeType,
        path: relativePath,
      };
    }
  }

  if (ext === ".md") {
    return {
      type: "markdown",
      content,
      mimeType,
      path: relativePath,
    };
  }

  if (TEXT_EXTENSIONS.has(ext)) {
    return {
      type: "text",
      content,
      mimeType,
      path: relativePath,
    };
  }

  return {
    type: "text",
    content: content.slice(0, 12000),
    mimeType,
    path: relativePath,
  };
}
