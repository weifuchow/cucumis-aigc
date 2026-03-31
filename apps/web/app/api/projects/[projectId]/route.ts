import { NextResponse } from "next/server";

import { getProjectWorkbenchSnapshot } from "@/lib/workbench/projector";

export const runtime = "nodejs";

export async function GET(
  _request: Request,
  context: { params: Promise<{ projectId: string }> },
) {
  const { projectId } = await context.params;
  const snapshot = await getProjectWorkbenchSnapshot(projectId);
  return NextResponse.json(snapshot);
}
