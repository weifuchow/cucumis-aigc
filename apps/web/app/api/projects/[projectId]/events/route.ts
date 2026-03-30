import { NextResponse } from "next/server";

import { getProjectEvents } from "@/lib/projects/store";

export const runtime = "nodejs";

export async function GET(
  _request: Request,
  context: { params: Promise<{ projectId: string }> },
) {
  const { projectId } = await context.params;
  const events = await getProjectEvents(projectId);
  return NextResponse.json({ events });
}
