import { readFile } from "node:fs/promises";

import { NextResponse } from "next/server";

import { getMimeType, resolveProjectPath } from "@/lib/projects/artifacts";

export const runtime = "nodejs";

export async function GET(
  request: Request,
  context: { params: Promise<{ projectId: string }> },
) {
  const { projectId } = await context.params;
  const url = new URL(request.url);
  const relativePath = url.searchParams.get("path");

  if (!relativePath) {
    return NextResponse.json({ error: "Missing artifact path." }, { status: 400 });
  }

  try {
    const { absolutePath } = resolveProjectPath(projectId, relativePath);
    const buffer = await readFile(absolutePath);
    const mimeType = getMimeType(absolutePath);
    return new Response(buffer, {
      headers: {
        "content-type": mimeType,
      },
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Failed to read artifact.";
    return NextResponse.json({ error: message }, { status: 404 });
  }
}
