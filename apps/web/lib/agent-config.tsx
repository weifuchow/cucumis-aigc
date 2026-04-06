"use client";

import { createContext, useContext, useState, useEffect, type ReactNode } from "react";

export type AgentProvider = "claude" | "codex";

export const PROVIDER_LABELS: Record<AgentProvider, string> = {
  claude: "Claude Code Agent",
  codex: "Codex Agent",
};

const STORAGE_KEY = "cucumis:agent-provider";

type AgentConfigContextType = {
  provider: AgentProvider;
  setProvider: (p: AgentProvider) => void;
};

const AgentConfigContext = createContext<AgentConfigContextType>({
  provider: "codex",
  setProvider: () => {},
});

export function AgentConfigProvider({ children }: { children: ReactNode }) {
  const [provider, setProviderState] = useState<AgentProvider>("codex");

  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "claude" || stored === "codex") {
      setProviderState(stored);
    }
  }, []);

  function setProvider(p: AgentProvider) {
    setProviderState(p);
    localStorage.setItem(STORAGE_KEY, p);
  }

  return (
    <AgentConfigContext.Provider value={{ provider, setProvider }}>
      {children}
    </AgentConfigContext.Provider>
  );
}

export function useAgentConfig() {
  return useContext(AgentConfigContext);
}
