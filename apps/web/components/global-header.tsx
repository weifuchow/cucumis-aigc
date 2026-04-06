"use client";

import Link from "next/link";

import { useAgentConfig, type AgentProvider, PROVIDER_LABELS } from "@/lib/agent-config";

export function GlobalHeader() {
  const { provider, setProvider } = useAgentConfig();

  return (
    <header className="page-header">
      <div className="title-block">
        <Link href="/projects">
          <h1>Cucumis Console</h1>
        </Link>
        <p>
          面向本地视频工作流的控制台。项目状态、阶段执行、产物预览和 Agent
          编排都保持在同一个仓库里。
        </p>
      </div>
      <div className="pill-row">
        <Link className="pill" href="/projects">
          项目列表
        </Link>
        <Link className="pill" href="/projects/new">
          新建项目
        </Link>
        <Link className="pill" href="/chat">
          Agent Chat
        </Link>
        <span className="pill" style={{ opacity: 0.5, pointerEvents: "none" }}>
          Agent:
        </span>
        {(["codex", "claude"] as AgentProvider[]).map((p) => (
          <button
            className="pill"
            data-tone={provider === p ? "running" : undefined}
            key={p}
            onClick={() => setProvider(p)}
            type="button"
          >
            {PROVIDER_LABELS[p]}
          </button>
        ))}
      </div>
    </header>
  );
}
