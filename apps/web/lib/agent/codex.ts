import { Codex, Thread } from "@openai/codex-sdk";

import { PROJECTS_ROOT, REPO_ROOT } from "@/lib/config";

type ChatMessage = {
  role: "user" | "assistant";
  content: string;
};

type RunCodexProjectAgentArgs = {
  projectId: string;
  messages: ChatMessage[];
};

const threads = new Map<string, Thread>();

function getThread(projectId: string) {
  const existing = threads.get(projectId);
  if (existing) {
    return existing;
  }

  const codex = new Codex();
  const thread = codex.startThread({
    workingDirectory: REPO_ROOT,
    additionalDirectories: [PROJECTS_ROOT],
    sandboxMode: "read-only",
    approvalPolicy: "never",
    modelReasoningEffort: "medium",
  });
  threads.set(projectId, thread);
  return thread;
}

function buildPrompt(projectId: string, messages: ChatMessage[]) {
  const transcript = messages
    .slice(-12)
    .map((message) => `${message.role.toUpperCase()}: ${message.content}`)
    .join("\n\n");

  return [
    "You are the Codex project agent inside the Cucumis web console.",
    `Project id: ${projectId}.`,
    "The repository root is the current working directory.",
    `Project workspace files live under ${PROJECTS_ROOT}/${projectId}.`,
    "Answer in concise markdown.",
    "If repository skills are relevant, use them.",
    "When asked about project state, inspect the repo files instead of guessing.",
    "",
    "Conversation:",
    transcript,
  ].join("\n");
}

export async function runCodexProjectAgent({ projectId, messages }: RunCodexProjectAgentArgs) {
  const thread = getThread(projectId);
  const turn = await thread.run(buildPrompt(projectId, messages));

  return {
    reply: turn.finalResponse || "Codex did not return a response.",
  };
}
