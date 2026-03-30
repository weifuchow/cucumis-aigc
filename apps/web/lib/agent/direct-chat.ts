import { query } from "@anthropic-ai/claude-agent-sdk";

import { REPO_ROOT } from "@/lib/config";
import { createLocalToolsServer } from "@/lib/agent/local-tools";

export type ChatMessage = {
  role: "user" | "assistant";
  content: string;
};

type RunDirectClaudeChatArgs = {
  messages: ChatMessage[];
};

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function isRetryableClaudeError(error: unknown) {
  if (!(error instanceof Error)) {
    return false;
  }

  return (
    error.message.includes("process exited with code 1") ||
    error.message.includes("ECONNRESET") ||
    error.message.includes("timed out")
  );
}

function buildPrompt(messages: ChatMessage[]) {
  const header = [
    "You are a local tool-enabled Claude agent running inside a controlled web console.",
    "Use tools whenever the user asks about local disk space, local files, repository contents, or safe script execution.",
    "Use project skills when they are relevant to the task and available in the repository.",
    "Do not claim lack of access to the local machine if a provided tool can answer the request.",
    "Never invent local state. If tool output is insufficient, say exactly what is missing.",
    "Answer normally and concisely after using the relevant tools.",
  ].join(" ");

  const transcript = messages
    .slice(-12)
    .map((message) => `${message.role.toUpperCase()}: ${message.content}`)
    .join("\n\n");

  return `${header}\n\nConversation:\n${transcript}\n\nASSISTANT:`;
}

export async function runDirectClaudeChat({ messages }: RunDirectClaudeChatArgs) {
  const prompt = buildPrompt(messages);
  let attempt = 0;
  let lastError: unknown;
  const localToolsServer = createLocalToolsServer();

  while (attempt < 2) {
    attempt += 1;

    try {
      let reply = "";
      let totalCostUSD = 0;
      let sessionId: string | null = null;

      for await (const message of query({
        prompt,
        options: {
          cwd: REPO_ROOT,
          settingSources: ["project"],
          tools: ["Skill"],
          mcpServers: {
            local: localToolsServer,
          },
          allowedTools: [
            "Skill",
            "mcp__local__get_disk_space",
            "mcp__local__list_directory",
            "mcp__local__read_text_file",
            "mcp__local__run_repo_script",
          ],
        },
      })) {
        if (message.type === "result") {
          totalCostUSD = message.total_cost_usd ?? totalCostUSD;
          sessionId = message.session_id ?? sessionId;

          if (message.subtype === "success") {
            reply = message.result;
          } else {
            reply = message.errors.join("\n");
          }
        }
      }

      return {
        reply: reply || "Claude did not return a response.",
        totalCostUSD,
        sessionId,
      };
    } catch (error) {
      lastError = error;

      if (attempt >= 2 || !isRetryableClaudeError(error)) {
        break;
      }

      await sleep(400);
    }
  }

  throw lastError instanceof Error ? lastError : new Error("Claude chat failed.");
}
