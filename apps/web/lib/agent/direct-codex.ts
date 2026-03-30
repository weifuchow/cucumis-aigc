import { Codex, Thread } from "@openai/codex-sdk";

import { REPO_ROOT } from "@/lib/config";

export type DirectChatMessage = {
  role: "user" | "assistant";
  content: string;
};

const threads = new Map<string, Thread>();

function getThread(threadKey: string) {
  const existing = threads.get(threadKey);
  if (existing) {
    return existing;
  }

  const codex = new Codex();
  const thread = codex.startThread({
    workingDirectory: REPO_ROOT,
    sandboxMode: "read-only",
    approvalPolicy: "never",
    modelReasoningEffort: "medium",
  });
  threads.set(threadKey, thread);
  return thread;
}

function buildPrompt(messages: DirectChatMessage[]) {
  const transcript = messages
    .slice(-12)
    .map((message) => `${message.role.toUpperCase()}: ${message.content}`)
    .join("\n\n");

  return [
    "You are a Codex local agent running inside the Cucumis web console.",
    "The current working directory is the repository root.",
    "Use repository context and available skills when relevant.",
    "If the user asks about local state, inspect the environment instead of guessing.",
    "Answer in concise markdown.",
    "",
    "Conversation:",
    transcript,
  ].join("\n");
}

export async function runDirectCodexChat(messages: DirectChatMessage[]) {
  const thread = getThread("direct-chat");
  const turn = await thread.run(buildPrompt(messages));

  return {
    reply: turn.finalResponse || "Codex did not return a response.",
    sessionId: thread.id,
  };
}
