import { query } from "@anthropic-ai/claude-agent-sdk";

import { buildProjectAgentPrompt } from "@/lib/agent/prompt";
import { REPO_ROOT } from "@/lib/config";
import { createProjectToolsServer } from "@/lib/agent/tools";

type ChatMessage = {
  role: "user" | "assistant";
  content: string;
};

type RunProjectAgentArgs = {
  projectId: string;
  messages: ChatMessage[];
};

export async function runProjectAgent({ projectId, messages }: RunProjectAgentArgs) {
  const prompt = buildProjectAgentPrompt(projectId, messages);
  const projectServer = createProjectToolsServer();
  let finalText = "";
  let totalCostUSD = 0;

  for await (const message of query({
    prompt,
    options: {
      cwd: REPO_ROOT,
      settingSources: ["project"],
      tools: ["Skill"],
      mcpServers: {
        project: projectServer,
      },
      allowedTools: ["Skill", "mcp__project__*"],
    },
  })) {
    if (message.type === "result") {
      if (message.subtype === "success") {
        finalText = message.result ?? finalText;
      } else {
        finalText = message.errors.join("\n");
      }
      totalCostUSD = message.total_cost_usd ?? totalCostUSD;
    }
  }

  return {
    reply: finalText || "No response returned from the project agent.",
    totalCostUSD,
  };
}
