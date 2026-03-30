import Link from "next/link";

import { ProjectList } from "@/components/project-list";
import { listProjects } from "@/lib/projects/store";

export default async function ProjectsPage() {
  const projects = await listProjects();

  return (
    <div className="stack">
      <div className="page-header">
        <div className="title-block">
          <h1>项目控制台</h1>
          <p>浏览现有 `projects/*`，查看阶段状态、review 结果和最近产物。</p>
        </div>
        <div className="button-row">
          <Link className="button-primary" href="/projects/new">
            新建项目
          </Link>
        </div>
      </div>
      <ProjectList projects={projects} />
    </div>
  );
}
