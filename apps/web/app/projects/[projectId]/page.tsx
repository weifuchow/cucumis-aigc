import { LiveProjectShell } from "@/components/live-project-shell";
import { getProjectDetail } from "@/lib/projects/store";

export default async function ProjectPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = await params;
  const project = await getProjectDetail(projectId);

  return (
    <div className="stack">
      <div className="title-block">
        <h1>{project.id}</h1>
        <p>
          文件系统仍然是事实来源。这个页面只是把 `orchestration/`、`events/`、
          `review/` 和关键产物投影成可操作的控制台。
        </p>
      </div>
      <LiveProjectShell initialProject={project} />
    </div>
  );
}
