import Link from "next/link";

import type { ProjectSummary } from "@/lib/projects/types";

type ProjectListProps = {
  projects: ProjectSummary[];
};

export function ProjectList({ projects }: ProjectListProps) {
  if (!projects.length) {
    return (
      <div className="panel">
        <div className="panel-inner">
          <h2 className="section-title">还没有项目</h2>
          <p className="muted">先创建一个项目，把现有 projects 目录下的工作流带到 web 控制台里。</p>
        </div>
      </div>
    );
  }

  return (
    <div className="grid projects-grid">
      {projects.map((project) => (
        <Link className="panel project-card" key={project.id} href={`/projects/${project.id}`}>
          <div className="panel-inner">
            <div className="split-header">
              <h2>{project.id}</h2>
              <span className="pill" data-tone={project.runtimeStatus}>
                {project.runtimeStatus}
              </span>
            </div>
            <div className="meta-list">
              <div className="meta-row">
                <span className="meta-label">当前阶段</span>
                <span className="mono">{project.state.current_stage ?? "none"}</span>
              </div>
              <div className="meta-row">
                <span className="meta-label">下一阶段</span>
                <span className="mono">{project.state.next_stage ?? "creative_design"}</span>
              </div>
              <div className="meta-row">
                <span className="meta-label">Review</span>
                <span>{project.review.status}</span>
              </div>
              <div className="meta-row">
                <span className="meta-label">最近事件</span>
                <span className="mono">{project.lastEventType ?? "none"}</span>
              </div>
              <div className="meta-row">
                <span className="meta-label">产物数</span>
                <span>{project.artifactPaths.length}</span>
              </div>
            </div>
          </div>
        </Link>
      ))}
    </div>
  );
}
