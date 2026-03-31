import { NextResponse } from "next/server";
import { z } from "zod";

import { updateProjectInputFields } from "@/lib/workbench/projector";

export const runtime = "nodejs";

const bodySchema = z.object({
  values: z.record(z.string(), z.unknown()),
});

export async function PATCH(
  request: Request,
  context: { params: Promise<{ projectId: string }> },
) {
  const { projectId } = await context.params;

  try {
    const body = bodySchema.parse(await request.json());
    const snapshot = await updateProjectInputFields(projectId, body.values);
    return NextResponse.json(snapshot);
  } catch (error) {
    const message = error instanceof Error ? error.message : "Failed to update project config.";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
