import { ArtifactPreview } from "@/components/artifact-preview";
import { readArtifactPreview } from "@/lib/projects/artifacts";

export default async function ProjectArtifactPage({
  params,
  searchParams,
}: {
  params: Promise<{ projectId: string }>;
  searchParams: Promise<{ path?: string }>;
}) {
  const { projectId } = await params;
  const { path } = await searchParams;
  const preview = path ? await readArtifactPreview(projectId, path) : null;

  return <ArtifactPreview preview={preview} projectId={projectId} />;
}
