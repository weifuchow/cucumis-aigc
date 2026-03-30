import { NextResponse } from "next/server";
import { z } from "zod";

import { appendUserDecision } from "@/lib/stages/runner";

export const runtime = "nodejs";

const bodySchema = z.object({
  decisionType: z.string().trim().min(1),
  notes: z.string().default(""),
});

export async function POST(
  request: Request,
  context: { params: Promise<{ projectId: string }> },
) {
  const { projectId } = await context.params;

  try {
    const body = bodySchema.parse(await request.json());
    await appendUserDecision(projectId, {
      decision_type: body.decisionType,
      reason: body.notes,
      source: "web-console",
    });

    return NextResponse.json({
      reply: `已记录确认：${body.decisionType}`,
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Failed to store decision.";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
