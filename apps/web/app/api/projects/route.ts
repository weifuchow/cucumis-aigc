import { execFile } from "node:child_process";
import { writeFile } from "node:fs/promises";
import path from "node:path";
import { promisify } from "node:util";

import { NextResponse } from "next/server";
import { z } from "zod";

import { PROJECTS_ROOT, REPO_ROOT, SCRIPTS_ROOT } from "@/lib/config";
import { getProjectDetail, listProjects } from "@/lib/projects/store";
import { runProjectReview } from "@/lib/stages/runner";

export const runtime = "nodejs";

const execFileAsync = promisify(execFile);

const createProjectSchema = z.object({
  projectId: z.string().trim().min(1).optional(),
  request: z.string().trim().min(1),
  projectPrefix: z.string().trim().min(1).default("proj"),
});

export async function GET() {
  const projects = await listProjects();
  return NextResponse.json({ projects });
}

export async function POST(request: Request) {
  const payload = createProjectSchema.parse(await request.json());
  const args = [
    path.join(SCRIPTS_ROOT, "init_project.py"),
    ...(payload.projectId ? ["--project-name", payload.projectId] : ["--project-prefix", payload.projectPrefix]),
    "--projects-dir",
    PROJECTS_ROOT,
  ];

  try {
    const { stdout } = await execFileAsync("python3", args, {
      cwd: REPO_ROOT,
      timeout: 1000 * 60,
    });

    const projectPath = stdout.trim();
    const projectId = path.basename(projectPath);
    await writeFile(path.join(projectPath, "request.md"), `${payload.request.trim()}\n`, "utf-8");
    await runProjectReview(projectId);

    const detail = await getProjectDetail(projectId);
    return NextResponse.json({ project: detail }, { status: 201 });
  } catch (error) {
    const message =
      error instanceof Error ? error.message : "Failed to initialize project.";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
