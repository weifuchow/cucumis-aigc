import type { ProjectDetail, ProjectRuntimeStatus } from "@/lib/projects/types";

export type WorkbenchFieldType = "text" | "number" | "select" | "boolean";

export type WorkflowUiOption = {
  label: string;
  value: string | number | boolean;
};

export type WorkflowUiField = {
  key: string;
  label: string;
  description?: string;
  type: WorkbenchFieldType;
  sourcePath: string;
  placeholder?: string;
  visibleWhen?: ProjectRuntimeStatus[];
  editableWhen?: ProjectRuntimeStatus[];
  options?: WorkflowUiOption[];
};

export type WorkflowUiFormSection = {
  id: string;
  title: string;
  description?: string;
  fields: WorkflowUiField[];
};

export type WorkflowUiArtifactSection = {
  id: string;
  title: string;
  description?: string;
  artifactTypes: string[];
};

export type WorkflowUiAction = {
  id: string;
  label: string;
  description?: string;
  kind: "run" | "review" | "confirm";
  decisionType?: string;
  visibleWhen?: {
    runtimeStatuses?: ProjectRuntimeStatus[];
    artifactSectionIds?: string[];
  };
};

export type WorkflowUiConfig = {
  workflowId: string;
  formSections: WorkflowUiFormSection[];
  artifactSections: WorkflowUiArtifactSection[];
  pendingActions: WorkflowUiAction[];
  statusCopy: Partial<Record<ProjectRuntimeStatus, string>>;
};

export type WorkbenchFieldValue = string | number | boolean | null;

export type WorkbenchField = WorkflowUiField & {
  value: WorkbenchFieldValue;
  visible: boolean;
  editable: boolean;
};

export type WorkbenchFormSection = {
  id: string;
  title: string;
  description?: string;
  fields: WorkbenchField[];
};

export type WorkbenchArtifactPreview = {
  path: string;
  kind: "image" | "video" | "json" | "text" | "markdown" | "binary";
  href: string;
};

export type WorkbenchArtifactCard = {
  id: string;
  title: string;
  description: string;
  count: number;
  status: "ready" | "empty";
  previewItems: WorkbenchArtifactPreview[];
  paths: string[];
};

export type WorkbenchArtifactSection = {
  id: string;
  title: string;
  description?: string;
  items: WorkbenchArtifactCard[];
  totalCount: number;
};

export type WorkbenchPendingAction = WorkflowUiAction & {
  visible: boolean;
  enabled: boolean;
};

export type WorkbenchTechnicalDetails = {
  currentStage: string | null;
  nextStage: string | null;
  reviewStatus: string;
  nextRecommendedAction: string | null;
  taskCard: string | null;
  observerSummary: string | null;
  events: ProjectDetail["events"];
  artifactPaths: string[];
  completedStages: string[];
  failedStage: string | null;
};

export type WorkbenchPageModel = {
  header: {
    projectId: string;
    runtimeStatus: ProjectRuntimeStatus;
    headline: string;
    summary: string;
    updatedAt: string | null;
  };
  formSections: WorkbenchFormSection[];
  artifactSections: WorkbenchArtifactSection[];
  pendingActions: WorkbenchPendingAction[];
  technical: WorkbenchTechnicalDetails;
};

export type ProjectWorkbenchSnapshot = {
  project: ProjectDetail;
  workbench: WorkbenchPageModel;
};
