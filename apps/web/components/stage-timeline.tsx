import { STAGE_LABELS, STAGE_ORDER } from "@/lib/stages/contracts";

type StageTimelineProps = {
  completedStages: string[];
  currentStage: string | null;
  failedStage: string | null;
  nextStage: string | null;
};

export function StageTimeline({
  completedStages,
  currentStage,
  failedStage,
  nextStage,
}: StageTimelineProps) {
  const completed = new Set(completedStages);

  return (
    <div className="panel">
      <div className="panel-inner">
        <div className="split-header">
          <h2 className="section-title">阶段时间线</h2>
          <span className="pill">{nextStage ?? "creative_design"}</span>
        </div>
        <div className="stage-list">
          {STAGE_ORDER.map((stage) => {
            const state = failedStage === stage
              ? "failed"
              : currentStage === stage
                ? "active"
                : completed.has(stage)
                  ? "completed"
                  : "idle";

            return (
              <div className="stage-item" data-state={state} key={stage}>
                <div className="stage-name">{STAGE_LABELS[stage]}</div>
                <div className="muted mono">{stage}</div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
