"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

export function NewProjectForm() {
  const router = useRouter();
  const [projectId, setProjectId] = useState("");
  const [request, setRequest] = useState("主题：\n目标：\n时长：30秒\n风格：\n语言：中文\n画幅：9:16\n");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);

    try {
      const response = await fetch("/api/projects", {
        method: "POST",
        headers: {
          "content-type": "application/json",
        },
        body: JSON.stringify({
          projectId: projectId || undefined,
          request,
        }),
      });

      const payload = (await response.json()) as { project?: { id: string }; error?: string };

      if (!response.ok || !payload.project) {
        throw new Error(payload.error ?? "Failed to create project.");
      }

      router.push(`/projects/${payload.project.id}`);
      router.refresh();
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Failed to create project.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form className="panel inline-form" onSubmit={onSubmit}>
      <div className="panel-inner input-grid">
        <div className="field">
          <label htmlFor="projectId">项目 ID（可选）</label>
          <input
            id="projectId"
            onChange={(event) => setProjectId(event.target.value)}
            placeholder="比如 ai-tea-launch"
            value={projectId}
          />
        </div>
        <div className="field">
          <label htmlFor="request">需求描述</label>
          <textarea
            id="request"
            onChange={(event) => setRequest(event.target.value)}
            value={request}
          />
        </div>
        {error ? (
          <div className="status-note" data-tone="error">
            {error}
          </div>
        ) : null}
        <div className="button-row">
          <button className="button-primary" disabled={submitting} type="submit">
            {submitting ? "创建中..." : "创建项目"}
          </button>
        </div>
      </div>
    </form>
  );
}
