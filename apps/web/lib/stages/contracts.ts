export const STAGE_ORDER = [
  "creative_design",
  "script_writer",
  "audio_foundation",
  "beat_sync_storyboard_planner",
  "image_generator",
  "constrained_video_generator",
  "timeline_builder",
] as const;

export type StageName = (typeof STAGE_ORDER)[number];

export const STAGE_LABELS: Record<StageName, string> = {
  creative_design: "Creative Design",
  script_writer: "Script Writer",
  audio_foundation: "Audio Foundation",
  beat_sync_storyboard_planner: "Beat Sync Storyboard Planner",
  image_generator: "Image Generator",
  constrained_video_generator: "Constrained Video Generator",
  timeline_builder: "Timeline Builder",
};

export const STAGE_SCRIPT_NAMES: Record<StageName, string> = {
  creative_design: "run_creative_design.py",
  script_writer: "run_script_writer.py",
  audio_foundation: "run_audio_foundation.py",
  beat_sync_storyboard_planner: "run_beat_sync_storyboard_planner.py",
  image_generator: "run_image_generator.py",
  constrained_video_generator: "run_constrained_video_generator.py",
  timeline_builder: "run_timeline_builder.py",
};

export function isStageName(value: string): value is StageName {
  return STAGE_ORDER.includes(value as StageName);
}
