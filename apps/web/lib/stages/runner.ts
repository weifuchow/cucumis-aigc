import { execFile } from "node:child_process";
import { readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { promisify } from "node:util";

import { PROJECTS_ROOT, REPO_ROOT, SCRIPTS_ROOT } from "@/lib/config";
import { getProjectSummary } from "@/lib/projects/store";
import { STAGE_ORDER, STAGE_SCRIPT_NAMES, type StageName, isStageName } from "@/lib/stages/contracts";

const execFileAsync = promisify(execFile);

type RunStageOptions = {
  stage: StageName;
  projectId: string;
  extraArgs?: string[];
};

export type StageRunResult = {
  ok: boolean;
  stage: StageName;
  stdout: string;
  stderr: string;
  code: number;
};

export function resolveStageScript(stage: StageName) {
  return path.join(SCRIPTS_ROOT, STAGE_SCRIPT_NAMES[stage]);
}

export async function ensureProjectExists(projectId: string) {
  const summary = await getProjectSummary(projectId);
  return summary;
}

export async function runStage({ stage, projectId, extraArgs = [] }: RunStageOptions): Promise<StageRunResult> {
  const scriptPath = resolveStageScript(stage);
  const projectPath = path.join(PROJECTS_ROOT, projectId);

  try {
    const { stdout, stderr } = await execFileAsync(
      "python3",
      [scriptPath, "--project", projectPath, ...extraArgs],
      {
        cwd: REPO_ROOT,
        timeout: 1000 * 60 * 15,
        maxBuffer: 1024 * 1024 * 8,
      },
    );

    return {
      ok: true,
      stage,
      stdout,
      stderr,
      code: 0,
    };
  } catch (error) {
    const failure = error as NodeJS.ErrnoException & {
      stdout?: string;
      stderr?: string;
      code?: number;
    };

    return {
      ok: false,
      stage,
      stdout: failure.stdout ?? "",
      stderr: failure.stderr ?? failure.message,
      code: typeof failure.code === "number" ? failure.code : 1,
    };
  }
}

export async function runProjectReview(projectId: string) {
  const projectPath = path.join(PROJECTS_ROOT, projectId);
  const commands = ["review_project.py", "observe_project.py", "session_handoff.py"];
  const outputs: StageRunResult[] = [];

  for (const scriptName of commands) {
    try {
      const { stdout, stderr } = await execFileAsync(
        "python3",
        [path.join(SCRIPTS_ROOT, scriptName), "--project", projectPath],
        {
          cwd: REPO_ROOT,
          timeout: 1000 * 60 * 5,
          maxBuffer: 1024 * 1024 * 4,
        },
      );
      outputs.push({
        ok: true,
        stage: "creative_design",
        stdout,
        stderr,
        code: 0,
      });
    } catch (error) {
      const failure = error as NodeJS.ErrnoException & {
        stdout?: string;
        stderr?: string;
        code?: number;
      };
      outputs.push({
        ok: false,
        stage: "creative_design",
        stdout: failure.stdout ?? "",
        stderr: failure.stderr ?? failure.message,
        code: typeof failure.code === "number" ? failure.code : 1,
      });
    }
  }

  return outputs;
}

export async function appendUserDecision(projectId: string, decision: Record<string, unknown>) {
  const decisionsPath = path.join(PROJECTS_ROOT, projectId, "orchestration", "decisions.jsonl");
  const line = `${JSON.stringify({
    timestamp: new Date().toISOString(),
    decision_type: "web_confirmation",
    ...decision,
  })}\n`;

  let existing = "";
  try {
    existing = await readFile(decisionsPath, "utf-8");
  } catch {
    existing = "";
  }

  await writeFile(decisionsPath, `${existing}${line}`, "utf-8");
}

export async function getNextRunnableStage(projectId: string): Promise<StageName> {
  const summary = await getProjectSummary(projectId);
  const nextStage = summary.state.next_stage;

  if (nextStage && isStageName(nextStage)) {
    return nextStage;
  }

  const completed = new Set(summary.state.completed_stages);
  const firstPending = STAGE_ORDER.find((stage) => !completed.has(stage));
  return firstPending ?? "creative_design";
}
