import { POLL_INTERVAL_MS } from "@/lib/config";
import { getProjectDetail } from "@/lib/projects/store";

function encodeEvent(name: string, data: unknown) {
  return `event: ${name}\ndata: ${JSON.stringify(data)}\n\n`;
}

export function createProjectStream(projectId: string) {
  let interval: NodeJS.Timeout | null = null;
  let lastSignature = "";

  return new ReadableStream<Uint8Array>({
    async start(controller) {
      const encoder = new TextEncoder();

      const pushSnapshot = async () => {
        const project = await getProjectDetail(projectId);
        const signature = JSON.stringify({
          updatedAt: project.updatedAt,
          runtimeStatus: project.runtimeStatus,
          currentStage: project.state.current_stage,
          nextStage: project.state.next_stage,
          eventCount: project.events.length,
          lastEvent: project.events.at(-1)?.timestamp ?? null,
        });

        if (signature === lastSignature) {
          return;
        }

        lastSignature = signature;
        controller.enqueue(encoder.encode(encodeEvent("project.snapshot", { project })));
      };

      await pushSnapshot();
      interval = setInterval(() => {
        void pushSnapshot();
      }, POLL_INTERVAL_MS);
    },
    cancel() {
      if (interval) {
        clearInterval(interval);
      }
    },
  });
}
