import { ClaudePlayground } from "@/components/claude-playground";

export default function ChatPage() {
  return (
    <div className="stack">
      <div className="title-block">
        <h1>Codex 本地工具聊天</h1>
        <p>
          这里默认使用 Codex Agent SDK，也可以切换到 Claude。它们都通过受控本地工具读取目录、
          文本文件，并执行少量安全的仓库脚本。
        </p>
      </div>
      <ClaudePlayground />
    </div>
  );
}
