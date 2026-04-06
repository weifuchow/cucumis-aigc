import "./globals.css";
import type { Metadata } from "next";
import type { ReactNode } from "react";

import { AgentConfigProvider } from "@/lib/agent-config";
import { GlobalHeader } from "@/components/global-header";

export const metadata: Metadata = {
  title: "Cucumis Web Console",
  description: "Filesystem-first control plane for cucumis-aigc projects.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>
        <AgentConfigProvider>
          <div className="page-shell">
            <GlobalHeader />
            {children}
          </div>
        </AgentConfigProvider>
      </body>
    </html>
  );
}
