"use client";

import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

type ChatMessage = {
  role: "user" | "assistant";
  content: string;
};

type AgentProvider = "claude" | "codex";

const PROVIDER_LABELS: Record<AgentProvider, string> = {
  claude: "Claude Chat",
  codex: "Codex Chat",
};

const INITIAL_MESSAGES: Record<AgentProvider, ChatMessage[]> = {
  claude: [
    {
      role: "assistant",
      content:
        "### Claude 已就绪\n\n我可以检查磁盘空间、查看目录、读取文本文件，并运行少量受控仓库脚本。",
    },
  ],
  codex: [
    {
      role: "assistant",
      content:
        "### Codex 已就绪\n\n我会基于仓库上下文、Codex 能力和已桥接的 skills 来回答。",
    },
  ],
};

export function ClaudePlayground() {
  const [provider, setProvider] = useState<AgentProvider>("codex");
  const [histories, setHistories] = useState<Record<AgentProvider, ChatMessage[]>>(INITIAL_MESSAGES);
  const [drafts, setDrafts] = useState<Record<AgentProvider, string>>({
    claude: "我的电脑还剩多少空间？请直接帮我查。",
    codex: "请查看当前仓库，并用 markdown 简短说明你能做什么。",
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [cost, setCost] = useState<number | null>(null);
  const [sessionIds, setSessionIds] = useState<Record<AgentProvider, string | null>>({
    claude: null,
    codex: null,
  });

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const trimmed = drafts[provider].trim();
    if (!trimmed || busy) {
      return;
    }

    const nextMessages = [...histories[provider], { role: "user" as const, content: trimmed }];
    setHistories((current) => ({
      ...current,
      [provider]: nextMessages,
    }));
    setDrafts((current) => ({
      ...current,
      [provider]: "",
    }));
    setBusy(true);
    setError(null);

    try {
      const response = await fetch("/api/claude/chat", {
        method: "POST",
        headers: {
          "content-type": "application/json",
        },
        body: JSON.stringify({ provider, messages: nextMessages }),
      });

      const payload = (await response.json()) as {
        reply?: string;
        error?: string;
        totalCostUSD?: number;
        sessionId?: string | null;
      };

      if (!response.ok || !payload.reply) {
        throw new Error(payload.error ?? "Claude request failed.");
      }

      setHistories((current) => ({
        ...current,
        [provider]: [...nextMessages, { role: "assistant", content: payload.reply ?? "" }],
      }));
      if (provider === "claude") {
        setCost(typeof payload.totalCostUSD === "number" ? payload.totalCostUSD : null);
      }
      setSessionIds((current) => ({
        ...current,
        [provider]: payload.sessionId ?? null,
      }));
    } catch (submitError) {
      const message =
        submitError instanceof Error ? submitError.message : "Agent request failed.";
      setError(message);
      setHistories((current) => ({
        ...current,
        [provider]: [
          ...nextMessages,
          {
            role: "assistant",
            content: `请求失败：${message}`,
          },
        ],
      }));
    } finally {
      setBusy(false);
    }
  }

  function resetChat() {
    setHistories((current) => ({
      ...current,
      [provider]: INITIAL_MESSAGES[provider],
    }));
    setDrafts((current) => ({
      ...current,
      [provider]:
        provider === "claude"
          ? "我的电脑还剩多少空间？请直接帮我查。"
          : "请查看当前仓库，并用 markdown 简短说明你能做什么。",
    }));
    setError(null);
    if (provider === "claude") {
      setCost(null);
    }
    setSessionIds((current) => ({
      ...current,
      [provider]: null,
    }));
  }

  const currentMessages = histories[provider];

  return (
    <div className="stack">
      <div className="panel">
        <div className="panel-inner">
          <div className="split-header">
            <h2 className="section-title">Agent Chat</h2>
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
              {provider === "claude" && cost !== null ? (
                <span className="pill">cost: ${cost.toFixed(4)}</span>
              ) : null}
              {sessionIds[provider] ? <span className="pill mono">{sessionIds[provider]}</span> : null}
            </div>
          </div>
          <p className="muted">
            默认使用 `Codex`，也可以切换到 `Claude`。两边历史独立，回复按 Markdown 渲染。
          </p>
          {error ? (
            <div className="status-note" data-tone="error">
              {error}
            </div>
          ) : (
            <div className="status-note">
              Codex 适合作为默认仓库代理。Claude 仍可用于本地工具问题。
            </div>
          )}
        </div>
      </div>

      <div className="panel">
        <div className="panel-inner">
          <div className="chat-log">
            {currentMessages.map((message, index) => (
              <div
                className="chat-bubble"
                data-role={message.role}
                key={`${provider}-${message.role}-${index}`}
              >
                <div className="chat-role">
                  {message.role === "user" ? "You" : PROVIDER_LABELS[provider]}
                </div>
                <div className="markdown-body">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {message.content}
                  </ReactMarkdown>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <form className="panel inline-form" onSubmit={onSubmit}>
        <div className="panel-inner input-grid">
          <div className="field">
            <label htmlFor="chatInput">消息</label>
            <textarea
              id="chatInput"
              onChange={(event) =>
                setDrafts((current) => ({
                  ...current,
                  [provider]: event.target.value,
                }))
              }
              placeholder={
                provider === "claude"
                  ? "输入任意问题，例如：我的电脑还剩多少空间？"
                  : "输入任意问题，例如：请概括这个仓库的技能体系。"
              }
              value={drafts[provider]}
            />
          </div>
          <div className="button-row">
            <button className="button-primary" disabled={busy} type="submit">
              {busy ? "请求中..." : "发送"}
            </button>
            <button className="button-secondary" onClick={resetChat} type="button">
              清空
            </button>
          </div>
        </div>
      </form>
    </div>
  );
}
