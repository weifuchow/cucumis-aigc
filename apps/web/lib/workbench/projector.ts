import { readFile, writeFile } from "node:fs/promises";
import path from "node:path";

import { PROJECTS_ROOT } from "@/lib/config";
import { getArtifactHref, getArtifactKind } from "@/lib/projects/artifacts";
import { getProjectDetail, getProjectSummary } from "@/lib/projects/store";
import type { ProjectDetail, ProjectRuntimeStatus } from "@/lib/projects/types";
import { collectArtifactPathsByType, getArtifactDefinition } from "@/lib/workbench/artifact-registry";
import type {
  ProjectWorkbenchSnapshot,
  WorkbenchArtifactSection,
  WorkbenchFieldValue,
  WorkbenchPageModel,
} from "@/lib/workbench/types";
import { getEditableFieldMap, getWorkflowUiConfig, isStatusVisible } from "@/lib/workbench/workflow-ui";

function getNestedValue(input: Record<string, unknown>, sourcePath: string): WorkbenchFieldValue {
  const value = sourcePath.split(".").reduce<unknown>((current, segment) => {
    if (!current || typeof current !== "object" || !(segment in current)) {
      return null;
    }

    return (current as Record<string, unknown>)[segment];
  }, input);

  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return value;
  }

  return null;
}

function setNestedValue(target: Record<string, unknown>, sourcePath: string, value: unknown) {
  const segments = sourcePath.split(".");
  let current: Record<string, unknown> = target;

  for (const segment of segments.slice(0, -1)) {
    const next = current[segment];
    if (!next || typeof next !== "object" || Array.isArray(next)) {
      current[segment] = {};
    }
    current = current[segment] as Record<string, unknown>;
  }

  current[segments.at(-1) as string] = value;
}

async function readJsonObject(filePath: string) {
  try {
    const raw = await readFile(filePath, "utf-8");
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" ? (parsed as Record<string, unknown>) : {};
  } catch {
    return {};
  }
}

async function readDecisions(projectId: string) {
  const decisionsPath = path.join(PROJECTS_ROOT, projectId, "orchestration", "decisions.jsonl");

  try {
    const raw = await readFile(decisionsPath, "utf-8");
    return raw
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line) => JSON.parse(line) as Record<string, unknown>);
  } catch {
    return [];
  }
}

function buildHeadline(project: ProjectDetail) {
  const stage = project.state.current_stage ?? project.state.next_stage ?? "workflow";

  switch (project.runtimeStatus) {
    case "completed":
      return "已完成，可直接查看成片与导出结果";
    case "failed":
      return "最近一次执行失败，先处理错误再继续";
    case "blocked":
      return "流程当前被阻塞，需要先处理诊断问题";
    case "running":
      return `正在处理：${stage}`;
    case "waiting_for_confirmation":
      return "当前结果需要人工确认";
    default:
      return `已就绪，下一步建议：${stage}`;
  }
}

async function buildArtifactSections(project: ProjectDetail) {
  const config = await getWorkflowUiConfig();

  const sections = await Promise.all(
    config.artifactSections.map(async (section) => {
      const items = await Promise.all(
        section.artifactTypes.map(async (artifactType) => {
          const definition = getArtifactDefinition(artifactType);
          const paths = await collectArtifactPathsByType(project.id, artifactType);

          return {
            id: artifactType,
            title: definition.title,
            description: definition.description,
            count: paths.length,
            status: paths.length ? "ready" as const : "empty" as const,
            previewItems: paths.slice(0, 4).map((artifactPath) => ({
              path: artifactPath,
              kind: getArtifactKind(artifactPath),
              href: getArtifactHref(project.id, artifactPath),
            })),
            paths,
          };
        }),
      );

      const visibleItems = items.filter((item) => item.count > 0 || item.id === "final_video");

      return {
        id: section.id,
        title: section.title,
        description: section.description,
        items: visibleItems.length ? visibleItems : items,
        totalCount: items.reduce((sum, item) => sum + item.count, 0),
      } satisfies WorkbenchArtifactSection;
    }),
  );

  return sections;
}

export async function buildWorkbenchPageModel(project: ProjectDetail): Promise<WorkbenchPageModel> {
  const config = await getWorkflowUiConfig();
  const input = await readJsonObject(path.join(PROJECTS_ROOT, project.id, "input", "input.json"));
  const decisions = await readDecisions(project.id);
  const artifactSections = await buildArtifactSections(project);

  const formSections = config.formSections.map((section) => ({
    id: section.id,
    title: section.title,
    description: section.description,
    fields: section.fields.map((field) => ({
      ...field,
      value: getNestedValue(input, field.sourcePath),
      visible: isStatusVisible(field.visibleWhen, project.runtimeStatus),
      editable: isStatusVisible(field.editableWhen, project.runtimeStatus),
    })),
  }));

  const confirmedDecisionTypes = new Set(
    decisions
      .map((entry) => (typeof entry.decision_type === "string" ? entry.decision_type : null))
      .filter((value): value is string => Boolean(value)),
  );

  const pendingActions = config.pendingActions.map((action) => {
    const statusAllowed = isStatusVisible(action.visibleWhen?.runtimeStatuses, project.runtimeStatus);
    const requiredSections = action.visibleWhen?.artifactSectionIds ?? [];
    const hasRequiredArtifacts = !requiredSections.length
      || requiredSections.some((sectionId) => artifactSections.find((section) => section.id === sectionId)?.totalCount);
    const alreadyConfirmed = action.decisionType ? confirmedDecisionTypes.has(action.decisionType) : false;

    return {
      ...action,
      visible: statusAllowed && hasRequiredArtifacts && !alreadyConfirmed,
      enabled: statusAllowed,
    };
  });

  return {
    header: {
      projectId: project.id,
      runtimeStatus: project.runtimeStatus,
      headline: buildHeadline(project),
      summary:
        config.statusCopy[project.runtimeStatus] ??
        "项目详情来自文件系统快照，新的结果会在这里持续更新。",
      updatedAt: project.updatedAt,
    },
    formSections: formSections.map((section) => ({
      ...section,
      fields: section.fields.filter((field) => field.visible),
    })),
    artifactSections,
    pendingActions: pendingActions.filter((action) => action.visible),
    technical: {
      currentStage: project.state.current_stage,
      nextStage: project.state.next_stage,
      reviewStatus: project.review.status,
      nextRecommendedAction: project.review.next_recommended_action,
      taskCard: project.taskCard,
      observerSummary: project.observerSummary,
      events: project.events,
      artifactPaths: project.artifactPaths,
      completedStages: project.state.completed_stages,
      failedStage: project.state.last_failed_stage,
    },
  };
}

export async function getProjectWorkbenchSnapshot(projectId: string): Promise<ProjectWorkbenchSnapshot> {
  const project = await getProjectDetail(projectId);
  const workbench = await buildWorkbenchPageModel(project);
  return { project, workbench };
}

function coerceValue(type: string, value: unknown) {
  if (type === "number") {
    return typeof value === "number" ? value : Number(value ?? 0);
  }

  if (type === "boolean") {
    return typeof value === "boolean" ? value : value === "true" || value === "1";
  }

  return typeof value === "string" ? value : String(value ?? "");
}

export async function updateProjectInputFields(
  projectId: string,
  values: Record<string, unknown>,
): Promise<ProjectWorkbenchSnapshot> {
  const project = await getProjectSummary(projectId);
  const editableFields = await getEditableFieldMap();
  const inputPath = path.join(project.path, "input", "input.json");
  const input = await readJsonObject(inputPath);

  for (const [key, rawValue] of Object.entries(values)) {
    const field = editableFields.get(key);
    if (!field) {
      continue;
    }

    if (!isStatusVisible(field.editableWhen as ProjectRuntimeStatus[] | undefined, project.runtimeStatus)) {
      continue;
    }

    setNestedValue(input, field.sourcePath, coerceValue(field.type, rawValue));
  }

  await writeFile(inputPath, `${JSON.stringify(input, null, 2)}\n`, "utf-8");
  return getProjectWorkbenchSnapshot(projectId);
}
