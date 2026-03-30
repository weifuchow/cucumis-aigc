import { readFile } from "node:fs/promises";
import path from "node:path";

import { createSdkMcpServer, tool } from "@anthropic-ai/claude-agent-sdk";
import { z } from "zod";

import { WORKFLOWS_ROOT } from "@/lib/config";
import { resolveProjectPath } from "@/lib/projects/artifacts";
import { getProjectDetail } from "@/lib/projects/store";
import { appendUserDecision, getNextRunnableStage, runProjectReview, runStage } from "@/lib/stages/runner";
import { isStageName } from "@/lib/stages/contracts";

export function createProjectToolsServer() {
  const getProjectState = tool(
    "get_project_state",
    "Read the current project summary, state, review, recent events, and task card.",
    {
      projectId: z.string(),
    },
    async ({ projectId }) => {
      try {
        const project = await getProjectDetail(projectId);
        return {
          content: [
            {
              type: "text" as const,
              text: JSON.stringify(project, null, 2),
            },
          ],
        };
      } catch (error) {
        return {
          isError: true,
          content: [
            {
              type: "text" as const,
              text: error instanceof Error ? error.message : "Failed to read project state.",
            },
          ],
        };
      }
    },
  );

  const getProjectArtifact = tool(
    "get_project_artifact",
    "Read a text artifact from the project workspace.",
    {
      projectId: z.string(),
      relativePath: z.string(),
    },
    async ({ projectId, relativePath }) => {
      try {
        const { absolutePath } = resolveProjectPath(projectId, relativePath);
        const content = await readFile(absolutePath, "utf-8");
        return {
          content: [
            {
              type: "resource" as const,
              resource: {
                uri: `file://${absolutePath}`,
                mimeType: "text/plain",
                text: content,
              },
            },
          ],
        };
      } catch (error) {
        return {
          isError: true,
          content: [
            {
              type: "text" as const,
              text: error instanceof Error ? error.message : "Failed to read artifact.",
            },
          ],
        };
      }
    },
  );

  const listProjectArtifacts = tool(
    "list_project_artifacts",
    "List important artifact paths already known for the project.",
    {
      projectId: z.string(),
    },
    async ({ projectId }) => {
      try {
        const project = await getProjectDetail(projectId);
        return {
          content: [
            {
              type: "text" as const,
              text: JSON.stringify(project.artifactPaths, null, 2),
            },
          ],
        };
      } catch (error) {
        return {
          isError: true,
          content: [
            {
              type: "text" as const,
              text: error instanceof Error ? error.message : "Failed to list artifacts.",
            },
          ],
        };
      }
    },
  );

  const runProjectStage = tool(
    "run_stage",
    "Run a single validated stage script for the project.",
    {
      projectId: z.string(),
      stage: z.string(),
    },
    async ({ projectId, stage }) => {
      if (!isStageName(stage)) {
        return {
          isError: true,
          content: [{ type: "text" as const, text: `Unsupported stage: ${stage}` }],
        };
      }

      const result = await runStage({ projectId, stage });
      await runProjectReview(projectId);

      return {
        isError: !result.ok,
        content: [
          {
            type: "text" as const,
            text: JSON.stringify(result, null, 2),
          },
        ],
      };
    },
  );

  const runReview = tool(
    "run_review",
    "Refresh project review, observer summary, and handoff files.",
    {
      projectId: z.string(),
    },
    async ({ projectId }) => {
      const outputs = await runProjectReview(projectId);
      return {
        content: [
          {
            type: "text" as const,
            text: JSON.stringify(outputs, null, 2),
          },
        ],
      };
    },
  );

  const writeDecision = tool(
    "append_user_decision",
    "Append a user confirmation or operator decision into orchestration decisions.",
    {
      projectId: z.string(),
      decisionType: z.string(),
      notes: z.string().default(""),
    },
    async ({ projectId, decisionType, notes }) => {
      await appendUserDecision(projectId, {
        decision_type: decisionType,
        reason: notes,
      });
      return {
        content: [
          {
            type: "text" as const,
            text: `Recorded ${decisionType} for ${projectId}.`,
          },
        ],
      };
    },
  );

  const getStageContract = tool(
    "get_stage_contract",
    "Read the workflow contract so you can explain stage behavior and stage order.",
    {
      stage: z.string().default("overview"),
    },
    async ({ stage }) => {
      const workflowPath = path.join(WORKFLOWS_ROOT, "video_pipeline", "WORKFLOW.md");
      try {
        const raw = await readFile(workflowPath, "utf-8");
        const snippet =
          stage === "overview"
            ? raw
            : raw
                .split(`### Stage`)
                .find((section) => section.includes(`\`${stage}\``))
                ?.trim() ?? raw;
        return {
          content: [
            {
              type: "text" as const,
              text: snippet.slice(0, 12000),
            },
          ],
        };
      } catch (error) {
        return {
          isError: true,
          content: [
            {
              type: "text" as const,
              text: error instanceof Error ? error.message : "Failed to read workflow contract.",
            },
          ],
        };
      }
    },
  );

  const getNextStage = tool(
    "get_next_runnable_stage",
    "Resolve the safest next runnable stage from current project state.",
    {
      projectId: z.string(),
    },
    async ({ projectId }) => {
      try {
        const stage = await getNextRunnableStage(projectId);
        return {
          content: [{ type: "text" as const, text: stage }],
        };
      } catch (error) {
        return {
          isError: true,
          content: [
            {
              type: "text" as const,
              text: error instanceof Error ? error.message : "Failed to resolve next stage.",
            },
          ],
        };
      }
    },
  );

  return createSdkMcpServer({
    name: "project",
    version: "1.0.0",
    tools: [
      getProjectState,
      getProjectArtifact,
      listProjectArtifacts,
      runProjectStage,
      runReview,
      writeDecision,
      getStageContract,
      getNextStage,
    ],
  });
}
