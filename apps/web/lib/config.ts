import path from "node:path";

export const APP_ROOT = process.cwd();
export const REPO_ROOT = path.resolve(APP_ROOT, "..", "..");
export const PROJECTS_ROOT = path.join(REPO_ROOT, "projects");
export const SCRIPTS_ROOT = path.join(REPO_ROOT, "scripts");
export const WORKFLOWS_ROOT = path.join(REPO_ROOT, "workflows");
export const CLAUDE_SKILLS_ROOT = path.join(REPO_ROOT, ".claude", "skills");

export const POLL_INTERVAL_MS = 3000;
