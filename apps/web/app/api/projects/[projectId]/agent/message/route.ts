import { NextResponse } from "next/server";
import { z } from "zod";

import { runCodexProjectAgent } from "@/lib/agent/codex";
import { runProjectAgent } from "@/lib/agent/session";

export const runtime = "nodejs";

const bodySchema = z.object({
  provider: z.enum(["claude", "codex"]).default("claude"),
  messages: z
    .array(
      z.object({
        role: z.enum(["user", "assistant"]),
        content: z.string().trim().min(1),
      }),
    )
    .min(1),
});

export async function POST(
  request: Request,
  context: { params: Promise<{ projectId: string }> },
) {
  const { projectId } = await context.params;

  try {
    const body = bodySchema.parse(await request.json());
    const result =
      body.provider === "codex"
        ? await runCodexProjectAgent({
            projectId,
            messages: body.messages,
          })
        : await runProjectAgent({
            projectId,
            messages: body.messages,
          });

    return NextResponse.json(result);
  } catch (error) {
    const message = error instanceof Error ? error.message : "Agent request failed.";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
