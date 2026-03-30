import { NextResponse } from "next/server";

import { getProjectDetail } from "@/lib/projects/store";

export const runtime = "nodejs";

export async function GET(
  _request: Request,
  context: { params: Promise<{ projectId: string }> },
) {
  const { projectId } = await context.params;
  const project = await getProjectDetail(projectId);
  return NextResponse.json({ project });
}
