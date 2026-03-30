import "./globals.css";
import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  title: "Cucumis Web Console",
  description: "Filesystem-first control plane for cucumis-aigc projects.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>
        <div className="page-shell">
          <header className="page-header">
            <div className="title-block">
              <Link href="/projects">
                <h1>Cucumis Console</h1>
              </Link>
              <p>
                面向本地视频工作流的控制台。项目状态、阶段执行、产物预览和 Claude Agent
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
                Claude Chat
              </Link>
            </div>
          </header>
          {children}
        </div>
      </body>
    </html>
  );
}
