import { NextResponse } from "next/server";
import { z } from "zod";

import { runDirectCodexChat } from "@/lib/agent/direct-codex";
import { runDirectClaudeChat } from "@/lib/agent/direct-chat";

export const runtime = "nodejs";

const bodySchema = z.object({
  provider: z.enum(["claude", "codex"]).default("codex"),
  messages: z
    .array(
      z.object({
        role: z.enum(["user", "assistant"]),
        content: z.string().trim().min(1),
      }),
    )
    .min(1),
});

export async function POST(request: Request) {
  try {
    const body = bodySchema.parse(await request.json());
    const result =
      body.provider === "codex"
        ? await runDirectCodexChat(body.messages)
        : await runDirectClaudeChat({
            messages: body.messages,
          });

    return NextResponse.json(result);
  } catch (error) {
    const message = error instanceof Error ? error.message : "Agent chat request failed.";
    console.error("claude chat route failed", error);
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
