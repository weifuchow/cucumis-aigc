import { ClaudePlayground } from "@/components/claude-playground";

export default function ChatPage() {
  return (
    <div className="stack">
      <div className="title-block">
        <h1>Claude 本地工具聊天</h1>
        <p>
          这里的 Claude 不只是普通对话模型。它可以通过受控本地工具读取磁盘空间、
          浏览目录、读取文本文件，并执行少量安全的仓库脚本。
        </p>
      </div>
      <ClaudePlayground />
    </div>
  );
}
