import { NextResponse } from "next/server";
import { z } from "zod";

import { runCodexProjectAgent } from "@/lib/agent/codex";
import { runProjectAgent } from "@/lib/agent/session";
import { getNextRunnableStage, runProjectReview, runStage } from "@/lib/stages/runner";
import { isStageName } from "@/lib/stages/contracts";

export const runtime = "nodejs";

const bodySchema = z.object({
  stage: z.string().optional(),
  action: z.string().optional(),
});

export async function POST(
  request: Request,
  context: { params: Promise<{ projectId: string }> },
) {
  const { projectId } = await context.params;

  try {
    const body = bodySchema.parse(await request.json());

    if (body.action && body.action !== "continue_workflow") {
      return NextResponse.json({ error: `Unsupported action: ${body.action}` }, { status: 400 });
    }

    if (body.stage) {
      if (!isStageName(body.stage)) {
        return NextResponse.json({ error: `Unsupported stage: ${body.stage}` }, { status: 400 });
      }

      const result = await runStage({ projectId, stage: body.stage });
      await runProjectReview(projectId);
      return NextResponse.json({
        reply: result.ok
          ? `已执行 ${body.stage}。请检查新产物和 review。`
          : `执行 ${body.stage} 失败，请检查 stderr。`,
        ranStage: body.stage,
        result,
      });
    }

    const nextStage = await getNextRunnableStage(projectId);
    const agent = await runCodexProjectAgent({
      projectId,
      messages: [
        {
          role: "user",
          content: `Inspect current state. If it is safe, run exactly one next stage. The preferred next stage is ${nextStage}. Then summarize the result for the operator.`,
        },
      ],
    });

    return NextResponse.json({
      reply: agent.reply,
      ranStage: nextStage,
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Stage execution failed.";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
