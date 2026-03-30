export type ReviewStatus = "ready" | "in_progress" | "blocked" | "completed" | "unknown";

export type ProjectRuntimeStatus =
  | "ready"
  | "running"
  | "waiting_for_confirmation"
  | "blocked"
  | "failed"
  | "completed";

export type ProjectStateFile = {
  current_stage: string | null;
  completed_stages: string[];
  skipped_stages: string[];
  last_failed_stage: string | null;
  next_stage: string | null;
};

export type ProjectReview = {
  status: ReviewStatus;
  checked_at: string | null;
  completed_stages: string[];
  missing_artifacts: string[];
  warnings: string[];
  next_recommended_action: string | null;
};

export type ProjectSummary = {
  id: string;
  path: string;
  state: ProjectStateFile;
  review: ProjectReview;
  runtimeStatus: ProjectRuntimeStatus;
  updatedAt: string | null;
  lastEventType: string | null;
  artifactPaths: string[];
};

export type ProjectDetail = ProjectSummary & {
  events: ProjectEvent[];
  taskCard: string | null;
  observerSummary: string | null;
};

export type ProjectEvent = {
  timestamp: string | null;
  event_type: string;
  message: string | null;
  raw: Record<string, unknown>;
};

export type ArtifactPreview =
  | {
      type: "json" | "text" | "markdown";
      content: string;
      mimeType: string;
      path: string;
    }
  | {
      type: "image" | "video";
      mimeType: string;
      path: string;
      href: string;
    };
