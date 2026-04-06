"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { StageTimeline } from "@/components/stage-timeline";
import { useAgentConfig, type AgentProvider, PROVIDER_LABELS } from "@/lib/agent-config";
import type { ProjectWorkbenchSnapshot, WorkbenchField, WorkbenchPendingAction } from "@/lib/workbench/types";

type ProjectWorkbenchShellProps = {
  initialSnapshot: ProjectWorkbenchSnapshot;
};

type AgentResponse = {
  reply?: string;
  error?: string;
};

type ChatMessage = {
  role: "user" | "assistant";
  content: string;
};

const INITIAL_HISTORIES: Record<AgentProvider, ChatMessage[]> = {
  claude: [
    {
      role: "assistant",
      content: "### 工作台已就绪\n\n我会优先解释当前结果、待处理事项和下一步。",
    },
  ],
  codex: [
    {
      role: "assistant",
      content: "### Codex 已就绪\n\n我会基于仓库状态、结果文件和执行入口来辅助操作。",
    },
  ],
};

function flattenFieldValues(snapshot: ProjectWorkbenchSnapshot) {
  const entries = snapshot.workbench.formSections.flatMap((section) =>
    section.fields.map((field) => [field.key, field.value]),
  );

  return Object.fromEntries(entries);
}

function hasConfigChanges(snapshot: ProjectWorkbenchSnapshot, values: Record<string, unknown>) {
  return snapshot.workbench.formSections.some((section) =>
    section.fields.some((field) => values[field.key] !== field.value),
  );
}

function FieldInput({
  field,
  value,
  onChange,
}: {
  field: WorkbenchField;
  value: unknown;
  onChange: (nextValue: string | number | boolean) => void;
}) {
  if (field.type === "boolean") {
    return (
      <label className="checkbox-row">
        <input
          checked={Boolean(value)}
          disabled={!field.editable}
          onChange={(event) => onChange(event.target.checked)}
          type="checkbox"
        />
        <span>{field.label}</span>
      </label>
    );
  }

  if (field.type === "select") {
    return (
      <label className="field-control">
        <span>{field.label}</span>
        <select
          disabled={!field.editable}
          onChange={(event) => onChange(event.target.value)}
          value={String(value ?? "")}
        >
          <option value="">请选择</option>
          {field.options?.map((option) => (
            <option key={`${field.key}-${option.value}`} value={String(option.value)}>
              {option.label}
            </option>
          ))}
        </select>
      </label>
    );
  }

  return (
    <label className="field-control">
      <span>{field.label}</span>
      <input
        disabled={!field.editable}
        onChange={(event) =>
          onChange(field.type === "number" ? Number(event.target.value || 0) : event.target.value)
        }
        placeholder={field.placeholder}
        type={field.type === "number" ? "number" : "text"}
        value={typeof value === "number" ? String(value) : String(value ?? "")}
      />
    </label>
  );
}

function ArtifactPreview({
  projectId,
  item,
}: {
  projectId: string;
  item: {
    path: string;
    kind: string;
    href: string;
  };
}) {
  const detailHref = `/projects/${projectId}/artifact?path=${encodeURIComponent(item.path)}`;

  if (item.kind === "image") {
    return (
      <Link className="preview-tile" href={detailHref}>
        <img alt={item.path} src={item.href} />
      </Link>
    );
  }

  if (item.kind === "video") {
    return (
      <Link className="preview-tile preview-video" href={detailHref}>
        <span>视频</span>
      </Link>
    );
  }

  return (
    <Link className="preview-pill" href={detailHref}>
      {item.path}
    </Link>
  );
}

export function ProjectWorkbenchShell({ initialSnapshot }: ProjectWorkbenchShellProps) {
  const [snapshot, setSnapshot] = useState(initialSnapshot);
  const { provider } = useAgentConfig();
  const [histories, setHistories] = useState<Record<AgentProvider, ChatMessage[]>>(INITIAL_HISTORIES);
  const [drafts, setDrafts] = useState<Record<AgentProvider, string>>({
    claude: "总结当前结果，并告诉我是否适合继续执行。",
    codex: "请基于当前项目状态，总结结果并提示下一步。",
  });
  const [configDraft, setConfigDraft] = useState<Record<string, unknown>>(flattenFieldValues(initialSnapshot));
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setSnapshot(initialSnapshot);
    setConfigDraft(flattenFieldValues(initialSnapshot));
  }, [initialSnapshot]);

  useEffect(() => {
    const stream = new EventSource(`/api/projects/${snapshot.project.id}/stream`);

    stream.addEventListener("project.snapshot", (event) => {
      const payload = JSON.parse((event as MessageEvent).data) as ProjectWorkbenchSnapshot;
      setSnapshot(payload);
      setConfigDraft(flattenFieldValues(payload));
    });

    stream.onerror = () => {
      stream.close();
    };

    return () => {
      stream.close();
    };
  }, [snapshot.project.id]);

  const hasChanges = useMemo(() => hasConfigChanges(snapshot, configDraft), [snapshot, configDraft]);

  async function refreshSnapshot() {
    const response = await fetch(`/api/projects/${snapshot.project.id}`);
    const payload = (await response.json()) as ProjectWorkbenchSnapshot;
    setSnapshot(payload);
    setConfigDraft(flattenFieldValues(payload));
  }

  function appendAssistantMessage(content: string) {
    setHistories((current) => ({
      ...current,
      [provider]: [...current[provider], { role: "assistant", content }],
    }));
  }

  async function sendAgentMessage() {
    const message = drafts[provider].trim();
    if (!message) {
      return;
    }

    setBusyAction("message");
    setError(null);
    const nextMessages = [...histories[provider], { role: "user" as const, content: message }];
    setHistories((current) => ({
      ...current,
      [provider]: nextMessages,
    }));
    setDrafts((current) => ({
      ...current,
      [provider]: "",
    }));

    try {
      const response = await fetch(`/api/projects/${snapshot.project.id}/agent/message`, {
        method: "POST",
        headers: {
          "content-type": "application/json",
        },
        body: JSON.stringify({
          provider,
          messages: nextMessages,
        }),
      });
      const payload = (await response.json()) as AgentResponse;
      if (!response.ok) {
        throw new Error(payload.error ?? "Agent request failed.");
      }
      appendAssistantMessage(payload.reply ?? "Agent did not return a message.");
      await refreshSnapshot();
    } catch (messageError) {
      const content =
        messageError instanceof Error ? messageError.message : "Agent request failed.";
      setError(content);
      appendAssistantMessage(`请求失败：${content}`);
    } finally {
      setBusyAction(null);
    }
  }

  async function saveConfig() {
    setBusyAction("save-config");
    setError(null);

    try {
      const response = await fetch(`/api/projects/${snapshot.project.id}/config`, {
        method: "PATCH",
        headers: {
          "content-type": "application/json",
        },
        body: JSON.stringify({ values: configDraft }),
      });
      const payload = (await response.json()) as ProjectWorkbenchSnapshot & { error?: string };
      if (!response.ok) {
        throw new Error(payload.error ?? "Failed to save config.");
      }
      setSnapshot(payload);
      setConfigDraft(flattenFieldValues(payload));
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "Failed to save config.");
    } finally {
      setBusyAction(null);
    }
  }

  async function runPendingAction(action: WorkbenchPendingAction) {
    setBusyAction(action.id);
    setError(null);

    try {
      if (action.kind === "run") {
        const response = await fetch(`/api/projects/${snapshot.project.id}/agent/run`, {
          method: "POST",
          headers: {
            "content-type": "application/json",
          },
          body: JSON.stringify({ action: action.id }),
        });
        const payload = (await response.json()) as AgentResponse;
        if (!response.ok) {
          throw new Error(payload.error ?? "Run action failed.");
        }
        appendAssistantMessage(payload.reply ?? "已请求继续执行。");
      } else if (action.kind === "review") {
        const response = await fetch(`/api/projects/${snapshot.project.id}/agent/review`, {
          method: "POST",
        });
        const payload = (await response.json()) as AgentResponse;
        if (!response.ok) {
          throw new Error(payload.error ?? "Review refresh failed.");
        }
        appendAssistantMessage(payload.reply ?? "已刷新诊断。");
      } else {
        const response = await fetch(`/api/projects/${snapshot.project.id}/agent/confirm`, {
          method: "POST",
          headers: {
            "content-type": "application/json",
          },
          body: JSON.stringify({
            decisionType: action.decisionType ?? action.id,
            notes: `Confirmed from workbench: ${action.label}`,
          }),
        });
        const payload = (await response.json()) as AgentResponse;
        if (!response.ok) {
          throw new Error(payload.error ?? "Checkpoint confirmation failed.");
        }
        appendAssistantMessage(payload.reply ?? "已记录确认。");
      }

      await refreshSnapshot();
    } catch (actionError) {
      const content = actionError instanceof Error ? actionError.message : "Action failed.";
      setError(content);
      appendAssistantMessage(`执行失败：${content}`);
    } finally {
      setBusyAction(null);
    }
  }

  return (
    <div className="stack">
      <div className="panel">
        <div className="panel-inner workbench-hero">
          <div className="stack">
            <div className="split-header">
              <div>
                <h2 className="section-title">{snapshot.workbench.header.headline}</h2>
                <p className="muted">{snapshot.workbench.header.summary}</p>
              </div>
              <span className="pill" data-tone={snapshot.workbench.header.runtimeStatus}>
                {snapshot.workbench.header.runtimeStatus}
              </span>
            </div>
            <div className="meta-list workbench-meta-list">
              <div className="meta-row">
                <span className="meta-label">项目</span>
                <span className="mono">{snapshot.workbench.header.projectId}</span>
              </div>
              <div className="meta-row">
                <span className="meta-label">当前阶段</span>
                <span className="mono">{snapshot.workbench.technical.currentStage ?? "none"}</span>
              </div>
              <div className="meta-row">
                <span className="meta-label">建议下一步</span>
                <span>{snapshot.workbench.technical.nextRecommendedAction ?? "继续执行下一步"}</span>
              </div>
              <div className="meta-row">
                <span className="meta-label">更新时间</span>
                <span className="mono">{snapshot.workbench.header.updatedAt ?? "unknown"}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="workbench-grid">
        <div className="stack">
          <div className="panel">
            <div className="panel-inner">
              <div className="split-header">
                <h2 className="section-title">任务配置</h2>
                <div className="button-row">
                  <button
                    className="button-secondary"
                    disabled={!hasChanges || busyAction !== null}
                    onClick={() => setConfigDraft(flattenFieldValues(snapshot))}
                    type="button"
                  >
                    重置
                  </button>
                  <button
                    className="button-primary"
                    disabled={!hasChanges || busyAction !== null}
                    onClick={saveConfig}
                    type="button"
                  >
                    {busyAction === "save-config" ? "保存中..." : "保存配置"}
                  </button>
                </div>
              </div>
              <div className="stack">
                {snapshot.workbench.formSections.map((section) =>
                  section.fields.length ? (
                    <section className="config-section" key={section.id}>
                      <div className="section-copy">
                        <h3>{section.title}</h3>
                        {section.description ? <p className="muted">{section.description}</p> : null}
                      </div>
                      <div className="inline-form-grid">
                        {section.fields.map((field) => (
                          <FieldInput
                            field={field}
                            key={field.key}
                            onChange={(value) =>
                              setConfigDraft((current) => ({
                                ...current,
                                [field.key]: value,
                              }))
                            }
                            value={configDraft[field.key]}
                          />
                        ))}
                      </div>
                    </section>
                  ) : null,
                )}
              </div>
            </div>
          </div>

          <div className="panel">
            <div className="panel-inner">
              <div className="split-header">
                <h2 className="section-title">产物结果</h2>
                <span className="tiny muted">
                  {snapshot.workbench.artifactSections.reduce((sum, section) => sum + section.totalCount, 0)} items
                </span>
              </div>
              <div className="stack">
                {snapshot.workbench.artifactSections.map((section) => (
                  <section className="artifact-section" key={section.id}>
                    <div className="section-copy">
                      <h3>{section.title}</h3>
                      {section.description ? <p className="muted">{section.description}</p> : null}
                    </div>
                    <div className="artifact-section-grid">
                      {section.items.map((item) => (
                        <div className="artifact-card" key={item.id}>
                          <div className="split-header">
                            <div>
                              <h4>{item.title}</h4>
                              <p className="muted">{item.description}</p>
                            </div>
                            <span className="pill" data-tone={item.status === "ready" ? "ready" : undefined}>
                              {item.count}
                            </span>
                          </div>
                          {item.previewItems.length ? (
                            <div className="thumbnail-grid">
                              {item.previewItems.map((preview) => (
                                <ArtifactPreview
                                  item={preview}
                                  key={`${item.id}-${preview.path}`}
                                  projectId={snapshot.project.id}
                                />
                              ))}
                            </div>
                          ) : (
                            <div className="status-note">当前还没有这类结果。</div>
                          )}
                          {item.paths.length > item.previewItems.length ? (
                            <div className="artifact-link-list">
                              {item.paths.slice(item.previewItems.length, item.previewItems.length + 6).map((artifactPath) => (
                                <Link
                                  className="preview-pill"
                                  href={`/projects/${snapshot.project.id}/artifact?path=${encodeURIComponent(artifactPath)}`}
                                  key={artifactPath}
                                >
                                  {artifactPath}
                                </Link>
                              ))}
                            </div>
                          ) : null}
                        </div>
                      ))}
                    </div>
                  </section>
                ))}
              </div>
            </div>
          </div>
        </div>

        <div className="stack">
          <div className="panel">
            <div className="panel-inner">
              <div className="split-header">
                <h2 className="section-title">待处理事项</h2>
                <span className="tiny muted">只展示当前需要用户参与的动作</span>
              </div>
              <div className="stack">
                {snapshot.workbench.pendingActions.length ? (
                  snapshot.workbench.pendingActions.map((action) => (
                    <button
                      className={action.kind === "confirm" ? "button-primary" : "button-secondary"}
                      disabled={busyAction !== null || !action.enabled}
                      key={action.id}
                      onClick={() => runPendingAction(action)}
                      type="button"
                    >
                      {busyAction === action.id ? "处理中..." : action.label}
                    </button>
                  ))
                ) : (
                  <div className="status-note">当前没有需要处理的人工动作。</div>
                )}
                {error ? (
                  <div className="status-note" data-tone="error">
                    {error}
                  </div>
                ) : null}
              </div>
            </div>
          </div>

          <details className="panel details-block" open>
            <summary>技术详情</summary>
            <div className="panel-inner stack">
              <StageTimeline
                completedStages={snapshot.workbench.technical.completedStages}
                currentStage={snapshot.workbench.technical.currentStage}
                failedStage={snapshot.workbench.technical.failedStage}
                nextStage={snapshot.workbench.technical.nextStage}
              />

              <div className="panel">
                <div className="panel-inner">
                  <div className="split-header">
                    <h3 className="section-title">技术诊断</h3>
                    <span className="pill">{snapshot.workbench.technical.reviewStatus}</span>
                  </div>
                  <div className="meta-list">
                    <div className="meta-row">
                      <span className="meta-label">当前阶段</span>
                      <span className="mono">{snapshot.workbench.technical.currentStage ?? "none"}</span>
                    </div>
                    <div className="meta-row">
                      <span className="meta-label">下一阶段</span>
                      <span className="mono">{snapshot.workbench.technical.nextStage ?? "unknown"}</span>
                    </div>
                    <div className="meta-row">
                      <span className="meta-label">建议动作</span>
                      <span>{snapshot.workbench.technical.nextRecommendedAction ?? "none"}</span>
                    </div>
                  </div>
                </div>
              </div>

              {snapshot.workbench.technical.taskCard ? (
                <div className="panel">
                  <div className="panel-inner markdown-body">
                    <h3 className="section-title">Task Card</h3>
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {snapshot.workbench.technical.taskCard}
                    </ReactMarkdown>
                  </div>
                </div>
              ) : null}

              {snapshot.workbench.technical.observerSummary ? (
                <div className="panel">
                  <div className="panel-inner markdown-body">
                    <h3 className="section-title">Observer Summary</h3>
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {snapshot.workbench.technical.observerSummary}
                    </ReactMarkdown>
                  </div>
                </div>
              ) : null}

              <div className="panel">
                <div className="panel-inner">
                  <div className="split-header">
                    <h3 className="section-title">项目 Agent</h3>
                    <div className="pill-row">
                      <span className="pill" data-tone="running">{PROVIDER_LABELS[provider]}</span>
                    </div>
                  </div>
                  <div className="panel agent-chat-panel">
                    <div className="panel-inner">
                      <div className="chat-log">
                        {histories[provider].map((entry, index) => (
                          <div
                            className="chat-bubble"
                            data-role={entry.role}
                            key={`${provider}-${entry.role}-${index}`}
                          >
                            <div className="chat-role">
                              {entry.role === "user" ? "You" : PROVIDER_LABELS[provider]}
                            </div>
                            <div className="markdown-body">
                              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                {entry.content}
                              </ReactMarkdown>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                  <label className="field-control">
                    <span>给 agent 的消息</span>
                    <textarea
                      onChange={(event) =>
                        setDrafts((current) => ({
                          ...current,
                          [provider]: event.target.value,
                        }))
                      }
                      value={drafts[provider]}
                    />
                  </label>
                  <div className="button-row">
                    <button className="button-primary" disabled={busyAction !== null} onClick={sendAgentMessage} type="button">
                      {busyAction === "message" ? "处理中..." : "发送消息"}
                    </button>
                    <button
                      className="button-secondary"
                      disabled={busyAction !== null}
                      onClick={() => runPendingAction({
                        id: "continue_workflow",
                        label: "继续执行",
                        kind: "run",
                        visible: true,
                        enabled: true,
                      })}
                      type="button"
                    >
                      执行下一步
                    </button>
                  </div>
                </div>
              </div>

              <div className="panel">
                <div className="panel-inner">
                  <div className="split-header">
                    <h3 className="section-title">原始产物路径</h3>
                    <span className="tiny muted">{snapshot.workbench.technical.artifactPaths.length} items</span>
                  </div>
                  <div className="artifact-link-list">
                    {snapshot.workbench.technical.artifactPaths.map((artifactPath) => (
                      <Link
                        className="preview-pill"
                        href={`/projects/${snapshot.project.id}/artifact?path=${encodeURIComponent(artifactPath)}`}
                        key={artifactPath}
                      >
                        {artifactPath}
                      </Link>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </details>
        </div>
      </div>
    </div>
  );
}
