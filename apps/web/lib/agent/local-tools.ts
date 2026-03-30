import { execFile } from "node:child_process";
import { readdir, readFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { promisify } from "node:util";

import { createSdkMcpServer, tool } from "@anthropic-ai/claude-agent-sdk";
import { z } from "zod";

import { REPO_ROOT, SCRIPTS_ROOT } from "@/lib/config";

const execFileAsync = promisify(execFile);
const HOME_ROOT = os.homedir();

const SAFE_SCRIPT_NAMES = new Set([
  "inspect_project.py",
  "review_project.py",
  "observe_project.py",
  "session_handoff.py",
  "validate_project.py",
]);

function ensureAllowedPath(targetPath: string, fallbackRoot = REPO_ROOT) {
  const candidate = path.isAbsolute(targetPath)
    ? path.resolve(targetPath)
    : path.resolve(fallbackRoot, targetPath);

  const allowedRoots = [REPO_ROOT, HOME_ROOT];
  if (!allowedRoots.some((root) => candidate === root || candidate.startsWith(`${root}${path.sep}`))) {
    throw new Error(`Path is outside allowed roots: ${targetPath}`);
  }

  return candidate;
}

async function runCommand(command: string, args: string[], cwd?: string) {
  const { stdout, stderr } = await execFileAsync(command, args, {
    cwd,
    timeout: 1000 * 30,
    maxBuffer: 1024 * 1024 * 4,
  });

  return {
    stdout: stdout.trim(),
    stderr: stderr.trim(),
  };
}

export function createLocalToolsServer() {
  const getDiskSpace = tool(
    "get_disk_space",
    "Check available disk space for a path on the local machine.",
    {
      targetPath: z.string().default(HOME_ROOT),
    },
    async ({ targetPath }) => {
      try {
        const resolvedPath = path.resolve(targetPath);
        const result = await runCommand("df", ["-h", resolvedPath]);
        return {
          content: [
            {
              type: "text" as const,
              text: [`Path: ${resolvedPath}`, result.stdout, result.stderr].filter(Boolean).join("\n"),
            },
          ],
        };
      } catch (error) {
        return {
          isError: true,
          content: [
            {
              type: "text" as const,
              text: error instanceof Error ? error.message : "Failed to read disk space.",
            },
          ],
        };
      }
    },
  );

  const listDirectory = tool(
    "list_directory",
    "List files in a local directory under the repo or home directory.",
    {
      targetPath: z.string().default("."),
    },
    async ({ targetPath }) => {
      try {
        const resolvedPath = ensureAllowedPath(targetPath);
        const entries = await readdir(resolvedPath, { withFileTypes: true });
        const payload = entries
          .slice(0, 200)
          .map((entry) => `${entry.isDirectory() ? "dir" : "file"} ${entry.name}`)
          .join("\n");

        return {
          content: [
            {
              type: "text" as const,
              text: [`Directory: ${resolvedPath}`, payload].filter(Boolean).join("\n"),
            },
          ],
        };
      } catch (error) {
        return {
          isError: true,
          content: [
            {
              type: "text" as const,
              text: error instanceof Error ? error.message : "Failed to list directory.",
            },
          ],
        };
      }
    },
  );

  const readTextFile = tool(
    "read_text_file",
    "Read a UTF-8 text file under the repo or home directory.",
    {
      targetPath: z.string(),
    },
    async ({ targetPath }) => {
      try {
        const resolvedPath = ensureAllowedPath(targetPath);
        const content = await readFile(resolvedPath, "utf-8");
        return {
          content: [
            {
              type: "resource" as const,
              resource: {
                uri: `file://${resolvedPath}`,
                mimeType: "text/plain",
                text: content.slice(0, 20000),
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
              text: error instanceof Error ? error.message : "Failed to read file.",
            },
          ],
        };
      }
    },
  );

  const runRepoScript = tool(
    "run_repo_script",
    "Run a safe repository Python script from the scripts directory.",
    {
      scriptName: z.string(),
      args: z.array(z.string()).default([]),
    },
    async ({ scriptName, args }) => {
      try {
        if (!SAFE_SCRIPT_NAMES.has(scriptName)) {
          throw new Error(`Unsupported script: ${scriptName}`);
        }

        const scriptPath = path.join(SCRIPTS_ROOT, scriptName);
        const result = await runCommand("python3", [scriptPath, ...args], REPO_ROOT);
        return {
          content: [
            {
              type: "text" as const,
              text: [result.stdout, result.stderr].filter(Boolean).join("\n"),
            },
          ],
        };
      } catch (error) {
        return {
          isError: true,
          content: [
            {
              type: "text" as const,
              text: error instanceof Error ? error.message : "Failed to run repository script.",
            },
          ],
        };
      }
    },
  );

  return createSdkMcpServer({
    name: "local",
    version: "1.0.0",
    tools: [getDiskSpace, listDirectory, readTextFile, runRepoScript],
  });
}
