import { NewProjectForm } from "@/components/new-project-form";

export default function NewProjectPage() {
  return (
    <div className="stack">
      <div className="title-block">
        <h1>新建项目</h1>
        <p>创建一个新的工作流目录，写入 `request.md`，然后在项目页里继续推进各阶段。</p>
      </div>
      <NewProjectForm />
    </div>
  );
}
