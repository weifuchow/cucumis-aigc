import Link from "next/link";

import type { ArtifactPreview as ArtifactPreviewType } from "@/lib/projects/types";

type ArtifactPreviewProps = {
  preview: ArtifactPreviewType | null;
  projectId: string;
};

export function ArtifactPreview({ preview, projectId }: ArtifactPreviewProps) {
  if (!preview) {
    return (
      <div className="panel">
        <div className="panel-inner">
          <h2 className="section-title">产物预览</h2>
          <p className="muted">从项目详情页选择一个产物进行查看。</p>
        </div>
      </div>
    );
  }

  return (
    <div className="panel">
      <div className="panel-inner">
        <div className="split-header">
          <h2 className="section-title">{preview.path}</h2>
          <Link className="button-link" href={`/projects/${projectId}`}>
            返回项目
          </Link>
        </div>
        {preview.type === "image" ? (
          <img alt={preview.path} src={preview.href} style={{ width: "100%", borderRadius: 12 }} />
        ) : null}
        {preview.type === "video" ? (
          <video controls src={preview.href} style={{ width: "100%", borderRadius: 12 }} />
        ) : null}
        {preview.type === "json" || preview.type === "text" || preview.type === "markdown" ? (
          <pre className="code-block">{preview.content}</pre>
        ) : null}
      </div>
    </div>
  );
}
