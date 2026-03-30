import { NextResponse } from "next/server";

import { getObserverSummary, getProjectSummary } from "@/lib/projects/store";

export const runtime = "nodejs";

export async function GET(
  _request: Request,
  context: { params: Promise<{ projectId: string }> },
) {
  const { projectId } = await context.params;
  const [project, observerSummary] = await Promise.all([
    getProjectSummary(projectId),
    getObserverSummary(projectId),
  ]);
  return NextResponse.json({ review: project.review, observerSummary });
}
