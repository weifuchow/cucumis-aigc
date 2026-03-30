type ChatMessage = {
  role: "user" | "assistant";
  content: string;
};

export function buildProjectAgentPrompt(projectId: string, messages: ChatMessage[]) {
  const transcript = messages
    .slice(-12)
    .map((message) => `${message.role.toUpperCase()}: ${message.content}`)
    .join("\n\n");

  return [
    "You are the project agent for a filesystem-first video pipeline.",
    `Your project id is "${projectId}".`,
    "You must reason from project state, recent events, task card, review data, and stage contracts.",
    "Never invent file contents that have not been returned by tools.",
    "Only use the provided MCP tools. Do not assume access to built-in tools.",
    "Prefer concise markdown answers with headings or bullets when useful.",
    "If the user asks to continue execution, inspect state first and only run a single valid next stage.",
    "If a tool returns an error, explain the blocker and propose the safest next action.",
    "When a stage run succeeds, summarize what ran and what the operator should inspect next.",
    "",
    "Conversation:",
    transcript,
  ].join("\n");
}
