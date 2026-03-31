import { readFile } from "node:fs/promises";
import path from "node:path";

import { z } from "zod";

import { WORKFLOWS_ROOT } from "@/lib/config";
import type { ProjectRuntimeStatus } from "@/lib/projects/types";
import type { WorkflowUiConfig } from "@/lib/workbench/types";

const runtimeStatusSchema = z.enum([
  "ready",
  "running",
  "waiting_for_confirmation",
  "blocked",
  "failed",
  "completed",
]);

const fieldOptionSchema = z.object({
  label: z.string(),
  value: z.union([z.string(), z.number(), z.boolean()]),
});

const fieldSchema = z.object({
  key: z.string(),
  label: z.string(),
  description: z.string().optional(),
  type: z.enum(["text", "number", "select", "boolean"]),
  sourcePath: z.string(),
  placeholder: z.string().optional(),
  visibleWhen: z.array(runtimeStatusSchema).optional(),
  editableWhen: z.array(runtimeStatusSchema).optional(),
  options: z.array(fieldOptionSchema).optional(),
});

const formSectionSchema = z.object({
  id: z.string(),
  title: z.string(),
  description: z.string().optional(),
  fields: z.array(fieldSchema),
});

const artifactSectionSchema = z.object({
  id: z.string(),
  title: z.string(),
  description: z.string().optional(),
  artifactTypes: z.array(z.string()),
});

const actionSchema = z.object({
  id: z.string(),
  label: z.string(),
  description: z.string().optional(),
  kind: z.enum(["run", "review", "confirm"]),
  decisionType: z.string().optional(),
  visibleWhen: z
    .object({
      runtimeStatuses: z.array(runtimeStatusSchema).optional(),
      artifactSectionIds: z.array(z.string()).optional(),
    })
    .optional(),
});

const workflowUiSchema = z.object({
  workflowId: z.string(),
  formSections: z.array(formSectionSchema),
  artifactSections: z.array(artifactSectionSchema),
  pendingActions: z.array(actionSchema),
  statusCopy: z
    .object({
      ready: z.string().optional(),
      running: z.string().optional(),
      waiting_for_confirmation: z.string().optional(),
      blocked: z.string().optional(),
      failed: z.string().optional(),
      completed: z.string().optional(),
    })
    .default({}),
});

function getWorkflowUiPath(workflowId: string) {
  return path.join(WORKFLOWS_ROOT, workflowId, "ui.json");
}

export async function getWorkflowUiConfig(workflowId = "video_pipeline"): Promise<WorkflowUiConfig> {
  const raw = await readFile(getWorkflowUiPath(workflowId), "utf-8");
  return workflowUiSchema.parse(JSON.parse(raw)) as WorkflowUiConfig;
}

export function isStatusVisible(
  statuses: ProjectRuntimeStatus[] | undefined,
  runtimeStatus: ProjectRuntimeStatus,
) {
  if (!statuses?.length) {
    return true;
  }

  return statuses.includes(runtimeStatus);
}

export async function getEditableFieldMap(workflowId = "video_pipeline") {
  const config = await getWorkflowUiConfig(workflowId);
  return new Map(config.formSections.flatMap((section) => section.fields.map((field) => [field.key, field])));
}
