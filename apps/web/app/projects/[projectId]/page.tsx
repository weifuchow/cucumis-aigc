import { ProjectWorkbenchShell } from "@/components/project-workbench-shell";
import { getProjectWorkbenchSnapshot } from "@/lib/workbench/projector";

export default async function ProjectPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = await params;
  const snapshot = await getProjectWorkbenchSnapshot(projectId);

  return (
    <div className="stack">
      <div className="title-block">
        <h1>{snapshot.project.id}</h1>
        <p>
          文件系统仍然是事实来源。这个页面现在把项目输入、产物结果、待处理事项和技术细节投影成一张更直观的工作台。
        </p>
      </div>
      <ProjectWorkbenchShell initialSnapshot={snapshot} />
    </div>
  );
}
