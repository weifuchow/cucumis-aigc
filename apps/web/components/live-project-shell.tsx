"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { StageTimeline } from "@/components/stage-timeline";
import type { ProjectDetail } from "@/lib/projects/types";
import { STAGE_LABELS, STAGE_ORDER, isStageName } from "@/lib/stages/contracts";

type LiveProjectShellProps = {
  initialProject: ProjectDetail;
};

type AgentResponse = {
  reply?: string;
  ranStage?: string | null;
  result?: {
    ok: boolean;
    stderr: string;
    stdout: string;
  };
  error?: string;
};

type AgentProvider = "claude" | "codex";

type ChatMessage = {
  role: "user" | "assistant";
  content: string;
};

const PROVIDER_LABELS: Record<AgentProvider, string> = {
  claude: "Claude Code Agent",
  codex: "Codex Agent",
};

const INITIAL_HISTORIES: Record<AgentProvider, ChatMessage[]> = {
  claude: [
    {
      role: "assistant",
      content: "### Claude Agent 已就绪\n\n我会优先基于项目状态、事件流和 skills 来回答。",
    },
  ],
  codex: [
    {
      role: "assistant",
      content: "### Codex 已就绪\n\n我会基于仓库内容和已桥接的 skills 来回答。",
    },
  ],
};

export function LiveProjectShell({ initialProject }: LiveProjectShellProps) {
  const [project, setProject] = useState(initialProject);
  const [provider, setProvider] = useState<AgentProvider>("codex");
  const [histories, setHistories] = useState<Record<AgentProvider, ChatMessage[]>>(INITIAL_HISTORIES);
  const [drafts, setDrafts] = useState<Record<AgentProvider, string>>({
    claude: "解释一下当前状态，并告诉我下一步。",
    codex: "请阅读当前项目状态，并告诉我下一步。",
  });
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setProject(initialProject);
  }, [initialProject]);

  useEffect(() => {
    const stream = new EventSource(`/api/projects/${project.id}/stream`);

    stream.addEventListener("project.snapshot", (event) => {
      const payload = JSON.parse((event as MessageEvent).data) as { project: ProjectDetail };
      setProject(payload.project);
    });

    stream.onerror = () => {
      stream.close();
    };

    return () => {
      stream.close();
    };
  }, [project.id]);

  async function refreshProject() {
    const response = await fetch(`/api/projects/${project.id}`);
    const payload = (await response.json()) as { project: ProjectDetail };
    setProject(payload.project);
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
      const response = await fetch(`/api/projects/${project.id}/agent/message`, {
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
      await refreshProject();
    } catch (messageError) {
      const content =
        messageError instanceof Error ? messageError.message : "Agent request failed.";
      setError(content);
      appendAssistantMessage(`请求失败：${content}`);
    } finally {
      setBusyAction(null);
    }
  }

  async function runStage(stage?: string) {
    setBusyAction(`run:${stage ?? "next"}`);
    setError(null);

    try {
      const response = await fetch(`/api/projects/${project.id}/agent/run`, {
        method: "POST",
        headers: {
          "content-type": "application/json",
        },
        body: JSON.stringify({ stage }),
      });
      const payload = (await response.json()) as AgentResponse;
      if (!response.ok) {
        throw new Error(payload.error ?? "Stage run failed.");
      }
      appendAssistantMessage(
        payload.reply ??
          (payload.ranStage ? `已执行 \`${payload.ranStage}\`。` : "已请求执行下一步。"),
      );
      await refreshProject();
    } catch (runError) {
      const content = runError instanceof Error ? runError.message : "Stage run failed.";
      setError(content);
      appendAssistantMessage(`执行失败：${content}`);
    } finally {
      setBusyAction(null);
    }
  }

  async function runReview() {
    setBusyAction("review");
    setError(null);

    try {
      const response = await fetch(`/api/projects/${project.id}/agent/review`, {
        method: "POST",
      });
      const payload = (await response.json()) as AgentResponse;
      if (!response.ok) {
        throw new Error(payload.error ?? "Review refresh failed.");
      }
      appendAssistantMessage(payload.reply ?? "已刷新 review / observer / handoff。");
      await refreshProject();
    } catch (reviewError) {
      const content = reviewError instanceof Error ? reviewError.message : "Review refresh failed.";
      setError(content);
      appendAssistantMessage(`刷新失败：${content}`);
    } finally {
      setBusyAction(null);
    }
  }

  async function confirmCheckpoint(action: string) {
    setBusyAction(`confirm:${action}`);
    setError(null);

    try {
      const response = await fetch(`/api/projects/${project.id}/agent/confirm`, {
        method: "POST",
        headers: {
          "content-type": "application/json",
        },
        body: JSON.stringify({
          decisionType: action,
          notes: `Confirmed from web console: ${action}`,
        }),
      });
      const payload = (await response.json()) as AgentResponse;
      if (!response.ok) {
        throw new Error(payload.error ?? "Checkpoint confirmation failed.");
      }
      appendAssistantMessage(payload.reply ?? "确认已记录。");
      await refreshProject();
    } catch (confirmError) {
      const content =
        confirmError instanceof Error ? confirmError.message : "Checkpoint confirmation failed.";
      setError(content);
      appendAssistantMessage(`确认失败：${content}`);
    } finally {
      setBusyAction(null);
    }
  }

  const activeStage = project.state.current_stage;
  const currentMessages = histories[provider];
  const suggestedStage =
    project.state.next_stage && isStageName(project.state.next_stage)
      ? project.state.next_stage
      : undefined;

  return (
    <div className="layout-grid">
      <div className="stack">
        <StageTimeline
          completedStages={project.state.completed_stages}
          currentStage={project.state.current_stage}
          failedStage={project.state.last_failed_stage}
          nextStage={project.state.next_stage}
        />
        <div className="panel">
          <div className="panel-inner">
            <div className="split-header">
              <h2 className="section-title">项目摘要</h2>
              <span className="pill" data-tone={project.runtimeStatus}>
                {project.runtimeStatus}
              </span>
            </div>
            <div className="meta-list">
              <div className="meta-row">
                <span className="meta-label">当前阶段</span>
                <span className="mono">{activeStage ?? "none"}</span>
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
                <span className="meta-label">建议动作</span>
                <span>{project.review.next_recommended_action ?? "Run creative_design."}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="stack">
        <div className="panel">
          <div className="panel-inner">
            <div className="split-header">
              <h2 className="section-title">项目 Agent</h2>
              <div className="pill-row">
                {(["claude", "codex"] as AgentProvider[]).map((item) => (
                  <button
                    className="pill"
                    data-tone={provider === item ? "running" : undefined}
                    key={item}
                    onClick={() => setProvider(item)}
                    type="button"
                  >
                    {PROVIDER_LABELS[item]}
                  </button>
                ))}
              </div>
            </div>
            <div className="panel agent-chat-panel">
              <div className="panel-inner">
                <div className="chat-log">
                  {currentMessages.map((entry, index) => (
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
            <div className="field">
              <label htmlFor="agentMessage">给 agent 的消息</label>
              <textarea
                id="agentMessage"
                onChange={(event) =>
                  setDrafts((current) => ({
                    ...current,
                    [provider]: event.target.value,
                  }))
                }
                value={drafts[provider]}
              />
            </div>
            <div className="button-row">
              <button className="button-primary" disabled={busyAction !== null} onClick={sendAgentMessage} type="button">
                {busyAction === "message" ? "处理中..." : "发送消息"}
              </button>
              <button className="button-secondary" disabled={busyAction !== null} onClick={() => runStage()} type="button">
                {busyAction === "run:next" ? "执行中..." : "执行下一步"}
              </button>
              <button className="button-secondary" disabled={busyAction !== null} onClick={runReview} type="button">
                {busyAction === "review" ? "刷新中..." : "刷新诊断"}
              </button>
            </div>
            {suggestedStage ? (
              <div className="status-note">
                推荐阶段：<span className="mono">{suggestedStage}</span>
              </div>
            ) : null}
            {error ? (
              <div className="status-note" data-tone="error">
                {error}
              </div>
            ) : null}
          </div>
        </div>

        <div className="panel">
          <div className="panel-inner">
            <div className="split-header">
              <h2 className="section-title">快速动作</h2>
              <span className="tiny muted">受控执行 Python stages</span>
            </div>
            <div className="button-row">
              {STAGE_ORDER.map((stage) => (
                <button
                  className="button-secondary"
                  disabled={busyAction !== null}
                  key={stage}
                  onClick={() => runStage(stage)}
                  type="button"
                >
                  {STAGE_LABELS[stage]}
                </button>
              ))}
            </div>
            <div className="button-row">
              <button
                className="button-primary"
                disabled={busyAction !== null}
                onClick={() => confirmCheckpoint("concept_selection_confirmed")}
                type="button"
              >
                记录方案确认
              </button>
              <button
                className="button-primary"
                disabled={busyAction !== null}
                onClick={() => confirmCheckpoint("beat_confirmation")}
                type="button"
              >
                记录节拍确认
              </button>
              <button
                className="button-primary"
                disabled={busyAction !== null}
                onClick={() => confirmCheckpoint("prompt_confirmation")}
                type="button"
              >
                记录提示词确认
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="stack">
        <div className="panel">
          <div className="panel-inner">
            <div className="split-header">
              <h2 className="section-title">关键产物</h2>
              <span className="tiny muted">{project.artifactPaths.length} items</span>
            </div>
            <div className="artifact-list">
              {project.artifactPaths.map((artifactPath) => (
                <Link
                  className="pill"
                  href={`/projects/${project.id}/artifact?path=${encodeURIComponent(artifactPath)}`}
                  key={artifactPath}
                >
                  {artifactPath}
                </Link>
              ))}
            </div>
          </div>
        </div>

        <div className="panel">
          <div className="panel-inner">
            <h2 className="section-title">Task Card</h2>
            <div className="text-block">{project.taskCard ?? "暂无 task-card.md"}</div>
          </div>
        </div>

        <div className="panel">
          <div className="panel-inner">
            <h2 className="section-title">事件流</h2>
            <div className="event-list">
              {project.events.slice(-12).reverse().map((event, index) => (
                <div className="stage-item" key={`${event.timestamp ?? "event"}-${index}`}>
                  <div className="stage-name mono">{event.event_type}</div>
                  <div className="tiny muted">{event.timestamp ?? "no timestamp"}</div>
                  <div className="text-block">{event.message ?? JSON.stringify(event.raw)}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
