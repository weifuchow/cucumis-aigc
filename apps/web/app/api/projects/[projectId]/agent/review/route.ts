import { NextResponse } from "next/server";

import { runProjectReview } from "@/lib/stages/runner";

export const runtime = "nodejs";

export async function POST(
  _request: Request,
  context: { params: Promise<{ projectId: string }> },
) {
  const { projectId } = await context.params;

  try {
    const outputs = await runProjectReview(projectId);
    const hasFailure = outputs.some((output) => !output.ok);

    return NextResponse.json({
      reply: hasFailure
        ? "review/observer 刷新时出现失败，请查看输出。"
        : "review / observer / handoff 已刷新。",
      outputs,
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Review refresh failed.";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
