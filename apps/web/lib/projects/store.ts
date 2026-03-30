import { readdir, readFile, stat } from "node:fs/promises";
import path from "node:path";

import { PROJECTS_ROOT } from "@/lib/config";
import type {
  ProjectDetail,
  ProjectEvent,
  ProjectReview,
  ProjectRuntimeStatus,
  ProjectStateFile,
  ProjectSummary,
} from "@/lib/projects/types";

const IMPORTANT_ARTIFACTS = [
  "brief/creative-brief.md",
  "brief/selected-concept.json",
  "input/input.json",
  "script/script.json",
  "audio/voiceover.json",
  "audio/bgm-selection.json",
  "audio/beat-grid.json",
  "timeline/global-timeline.json",
  "storyboard/storyboard.json",
  "assets/manifest.json",
  "video/clips.json",
  "timeline/timeline.json",
  "outputs/render-plan.json",
  "outputs/final.mp4",
  "review/observer-summary.md",
  "review/review-report.json",
];

const DEFAULT_STATE: ProjectStateFile = {
  current_stage: null,
  completed_stages: [],
  skipped_stages: [],
  last_failed_stage: null,
  next_stage: null,
};

const DEFAULT_REVIEW: ProjectReview = {
  status: "unknown",
  checked_at: null,
  completed_stages: [],
  missing_artifacts: [],
  warnings: [],
  next_recommended_action: null,
};

async function readJsonFile<T>(filePath: string, fallback: T): Promise<T> {
  try {
    const raw = await readFile(filePath, "utf-8");
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

async function fileExists(filePath: string) {
  try {
    await stat(filePath);
    return true;
  } catch {
    return false;
  }
}

function deriveRuntimeStatus(state: ProjectStateFile, review: ProjectReview): ProjectRuntimeStatus {
  if (state.last_failed_stage) {
    return "failed";
  }

  if (review.status === "blocked") {
    return "blocked";
  }

  if (state.current_stage && !state.next_stage) {
    return "running";
  }

  if (
    state.next_stage === "creative_design" &&
    !state.completed_stages.length &&
    !state.current_stage
  ) {
    return "ready";
  }

  if (state.current_stage === "completed") {
    return "completed";
  }

  return state.next_stage ? "ready" : "running";
}

async function readEventLines(projectRoot: string): Promise<ProjectEvent[]> {
  try {
    const raw = await readFile(path.join(projectRoot, "events", "events.jsonl"), "utf-8");
    return raw
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean)
      .slice(-50)
      .map((line) => {
        try {
          const payload = JSON.parse(line) as Record<string, unknown>;
          return {
            timestamp: typeof payload.timestamp === "string" ? payload.timestamp : null,
            event_type: typeof payload.event_type === "string" ? payload.event_type : "unknown",
            message: typeof payload.message === "string" ? payload.message : null,
            raw: payload,
          } satisfies ProjectEvent;
        } catch {
          return {
            timestamp: null,
            event_type: "raw.line",
            message: line,
            raw: { line },
          } satisfies ProjectEvent;
        }
      });
  } catch {
    return [];
  }
}

async function collectArtifactPaths(projectId: string) {
  const artifactPaths: string[] = [];

  await Promise.all(
    IMPORTANT_ARTIFACTS.map(async (relativePath) => {
      if (await fileExists(path.join(PROJECTS_ROOT, projectId, relativePath))) {
        artifactPaths.push(relativePath);
      }
    }),
  );

  return artifactPaths.sort();
}

export async function listProjects(): Promise<ProjectSummary[]> {
  try {
    const entries = await readdir(PROJECTS_ROOT, { withFileTypes: true });
    const projectDirs = entries.filter((entry) => entry.isDirectory()).map((entry) => entry.name);

    const summaries = await Promise.all(projectDirs.map((projectId) => getProjectSummary(projectId)));

    return summaries.sort((left, right) => {
      const leftTime = left.updatedAt ? Date.parse(left.updatedAt) : 0;
      const rightTime = right.updatedAt ? Date.parse(right.updatedAt) : 0;
      return rightTime - leftTime;
    });
  } catch {
    return [];
  }
}

export async function getProjectSummary(projectId: string): Promise<ProjectSummary> {
  const projectRoot = path.join(PROJECTS_ROOT, projectId);
  const state = await readJsonFile<ProjectStateFile>(
    path.join(projectRoot, "orchestration", "state.json"),
    DEFAULT_STATE,
  );
  const review = await readJsonFile<ProjectReview>(
    path.join(projectRoot, "review", "review-report.json"),
    DEFAULT_REVIEW,
  );
  const events = await readEventLines(projectRoot);
  const artifactPaths = await collectArtifactPaths(projectId);
  const projectStat = await stat(projectRoot).catch(() => null);
  const updatedAt = review.checked_at ?? projectStat?.mtime.toISOString() ?? null;
  const lastEvent = events.at(-1) ?? null;

  return {
    id: projectId,
    path: projectRoot,
    state,
    review,
    runtimeStatus: deriveRuntimeStatus(state, review),
    updatedAt,
    lastEventType: lastEvent?.event_type ?? null,
    artifactPaths,
  };
}

export async function getProjectEvents(projectId: string) {
  return readEventLines(path.join(PROJECTS_ROOT, projectId));
}

export async function getTaskCard(projectId: string) {
  try {
    return await readFile(
      path.join(PROJECTS_ROOT, projectId, "orchestration", "task-card.md"),
      "utf-8",
    );
  } catch {
    return null;
  }
}

export async function getObserverSummary(projectId: string) {
  try {
    return await readFile(path.join(PROJECTS_ROOT, projectId, "review", "observer-summary.md"), "utf-8");
  } catch {
    return null;
  }
}

export async function getProjectDetail(projectId: string): Promise<ProjectDetail> {
  const [summary, events, taskCard, observerSummary] = await Promise.all([
    getProjectSummary(projectId),
    getProjectEvents(projectId),
    getTaskCard(projectId),
    getObserverSummary(projectId),
  ]);

  return {
    ...summary,
    events,
    taskCard,
    observerSummary,
  };
}
