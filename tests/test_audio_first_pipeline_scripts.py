import json
import pathlib
import subprocess
import tempfile
import unittest


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


def run_script(script_name: str, project_dir: pathlib.Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "python3",
            str(REPO_ROOT / "scripts" / script_name),
            "--project",
            str(project_dir),
        ],
        capture_output=True,
        text=True,
    )


class AudioFirstPipelineScriptsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.project_dir = pathlib.Path(self.temp_dir.name) / "demo-project"

        subprocess.run(
            [
                "python3",
                str(REPO_ROOT / "scripts" / "init_project.py"),
                "--project-name",
                "demo-project",
                "--projects-dir",
                str(pathlib.Path(self.temp_dir.name)),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        (self.project_dir / "request.md").write_text(
            "\n".join(
                [
                    "主题：本地化 AI 视频工作流",
                    "时长：45 秒",
                    "风格：专业、克制",
                    "语言：中文",
                    "画幅：9:16",
                    "音乐：前半段压抑，后半段燃向",
                    "节奏：前慢后快",
                ]
            ),
            encoding="utf-8",
        )

    def test_run_input_parser_writes_music_emotion_and_pacing(self) -> None:
        result = run_script("run_input_parser.py", self.project_dir)
        self.assertEqual(result.returncode, 0, result.stderr)

        payload = json.loads((self.project_dir / "input" / "input.json").read_text(encoding="utf-8"))
        self.assertEqual(payload["music_emotion"], "前半段压抑，后半段燃向")
        self.assertEqual(payload["pacing_preference"], "前慢后快")

    def test_run_input_parser_writes_project_level_models(self) -> None:
        result = run_script("run_input_parser.py", self.project_dir)
        self.assertEqual(result.returncode, 0, result.stderr)

        payload = json.loads((self.project_dir / "input" / "input.json").read_text(encoding="utf-8"))
        self.assertEqual(payload["audio_model"], "elevenlabs-v3")
        self.assertEqual(payload["video_model"], "veo-3.1-fast")

    def test_run_script_writer_adds_emotion_markers_and_turning_points(self) -> None:
        self.assertEqual(run_script("run_input_parser.py", self.project_dir).returncode, 0)
        result = run_script("run_script_writer.py", self.project_dir)
        self.assertEqual(result.returncode, 0, result.stderr)

        payload = json.loads((self.project_dir / "script" / "script.json").read_text(encoding="utf-8"))
        self.assertTrue(payload["emotion_markers"])
        self.assertTrue(payload["turning_points"])

    def test_run_audio_foundation_writes_audio_artifacts(self) -> None:
        self.assertEqual(run_script("run_input_parser.py", self.project_dir).returncode, 0)
        self.assertEqual(run_script("run_script_writer.py", self.project_dir).returncode, 0)
        result = run_script("run_audio_foundation.py", self.project_dir)
        self.assertEqual(result.returncode, 0, result.stderr)

        voiceover = json.loads((self.project_dir / "audio" / "voiceover.json").read_text(encoding="utf-8"))
        bgm = json.loads((self.project_dir / "audio" / "bgm-selection.json").read_text(encoding="utf-8"))
        beat_grid = json.loads((self.project_dir / "audio" / "beat-grid.json").read_text(encoding="utf-8"))
        self.assertTrue(voiceover["segments"])
        self.assertTrue(bgm["track_id"])
        self.assertTrue(beat_grid["beats"])

    def test_run_audio_foundation_records_poe_metadata(self) -> None:
        self.assertEqual(run_script("run_input_parser.py", self.project_dir).returncode, 0)
        self.assertEqual(run_script("run_script_writer.py", self.project_dir).returncode, 0)
        result = run_script("run_audio_foundation.py", self.project_dir)
        self.assertEqual(result.returncode, 0, result.stderr)

        tts_response = json.loads((self.project_dir / "audio" / "tts-response.json").read_text(encoding="utf-8"))
        usage = json.loads((self.project_dir / "audio" / "usage.json").read_text(encoding="utf-8"))
        cost_lines = (self.project_dir / "costs" / "poe-usage.jsonl").read_text(encoding="utf-8").splitlines()

        self.assertEqual(tts_response["model"], "elevenlabs-v3")
        self.assertEqual(usage["model"], "elevenlabs-v3")
        self.assertIn(usage["mode"], {"mock", "live"})
        self.assertTrue(cost_lines)
        self.assertEqual(json.loads(cost_lines[0])["skill"], "audio_foundation")

    def test_run_global_timeline_initializer_writes_global_timeline(self) -> None:
        self.assertEqual(run_script("run_input_parser.py", self.project_dir).returncode, 0)
        self.assertEqual(run_script("run_script_writer.py", self.project_dir).returncode, 0)
        self.assertEqual(run_script("run_audio_foundation.py", self.project_dir).returncode, 0)
        result = run_script("run_global_timeline_initializer.py", self.project_dir)
        self.assertEqual(result.returncode, 0, result.stderr)

        payload = json.loads(
            (self.project_dir / "timeline" / "global-timeline.json").read_text(encoding="utf-8")
        )
        self.assertTrue(payload["scene_timing_slots"])

    def test_run_beat_sync_storyboard_planner_writes_timed_storyboard(self) -> None:
        self.assertEqual(run_script("run_input_parser.py", self.project_dir).returncode, 0)
        self.assertEqual(run_script("run_script_writer.py", self.project_dir).returncode, 0)
        self.assertEqual(run_script("run_audio_foundation.py", self.project_dir).returncode, 0)
        self.assertEqual(run_script("run_global_timeline_initializer.py", self.project_dir).returncode, 0)
        result = run_script("run_beat_sync_storyboard_planner.py", self.project_dir)
        self.assertEqual(result.returncode, 0, result.stderr)

        payload = json.loads(
            (self.project_dir / "storyboard" / "storyboard.json").read_text(encoding="utf-8")
        )
        self.assertTrue(payload["scenes"])
        first_scene = payload["scenes"][0]
        self.assertIn("start_time", first_scene)
        self.assertIn("end_time", first_scene)
        self.assertIn("beat_alignment", first_scene)
        self.assertIn("transition_intent", first_scene)
        self.assertIn("motion_intent", first_scene)

    def test_run_constrained_video_generator_writes_video_artifacts(self) -> None:
        self.assertEqual(run_script("run_input_parser.py", self.project_dir).returncode, 0)
        self.assertEqual(run_script("run_script_writer.py", self.project_dir).returncode, 0)
        self.assertEqual(run_script("run_audio_foundation.py", self.project_dir).returncode, 0)
        self.assertEqual(run_script("run_global_timeline_initializer.py", self.project_dir).returncode, 0)
        self.assertEqual(run_script("run_beat_sync_storyboard_planner.py", self.project_dir).returncode, 0)
        result = run_script("run_constrained_video_generator.py", self.project_dir)
        self.assertEqual(result.returncode, 0, result.stderr)

        clips = json.loads((self.project_dir / "video" / "clips.json").read_text(encoding="utf-8"))
        requests = json.loads((self.project_dir / "video" / "requests.json").read_text(encoding="utf-8"))
        usage = json.loads((self.project_dir / "video" / "usage.json").read_text(encoding="utf-8"))
        cost_lines = (self.project_dir / "costs" / "poe-usage.jsonl").read_text(encoding="utf-8").splitlines()

        self.assertTrue(clips["clips"])
        self.assertEqual(requests["model"], "veo-3.1-fast")
        self.assertEqual(usage["model"], "veo-3.1-fast")
        self.assertIn(json.loads(cost_lines[-1])["skill"], {"audio_foundation", "constrained_video_generator"})

    def test_run_timeline_builder_writes_timeline_artifact(self) -> None:
        self.assertEqual(run_script("run_input_parser.py", self.project_dir).returncode, 0)
        self.assertEqual(run_script("run_script_writer.py", self.project_dir).returncode, 0)
        self.assertEqual(run_script("run_audio_foundation.py", self.project_dir).returncode, 0)
        self.assertEqual(run_script("run_global_timeline_initializer.py", self.project_dir).returncode, 0)
        self.assertEqual(run_script("run_beat_sync_storyboard_planner.py", self.project_dir).returncode, 0)
        self.assertEqual(run_script("run_constrained_video_generator.py", self.project_dir).returncode, 0)

        result = run_script("run_timeline_builder.py", self.project_dir)
        self.assertEqual(result.returncode, 0, result.stderr)

        payload = json.loads((self.project_dir / "timeline" / "timeline.json").read_text(encoding="utf-8"))
        self.assertIn("metadata", payload)
        self.assertIn("tracks", payload)
        self.assertIn("segments", payload)
        self.assertIn("output", payload)
        self.assertTrue(payload["segments"])

    def test_run_ffmpeg_renderer_reviewer_writes_render_plan(self) -> None:
        self.assertEqual(run_script("run_input_parser.py", self.project_dir).returncode, 0)
        self.assertEqual(run_script("run_script_writer.py", self.project_dir).returncode, 0)
        self.assertEqual(run_script("run_audio_foundation.py", self.project_dir).returncode, 0)
        self.assertEqual(run_script("run_global_timeline_initializer.py", self.project_dir).returncode, 0)
        self.assertEqual(run_script("run_beat_sync_storyboard_planner.py", self.project_dir).returncode, 0)
        self.assertEqual(run_script("run_constrained_video_generator.py", self.project_dir).returncode, 0)
        self.assertEqual(run_script("run_timeline_builder.py", self.project_dir).returncode, 0)

        result = run_script("run_ffmpeg_renderer_reviewer.py", self.project_dir)
        self.assertEqual(result.returncode, 0, result.stderr)
        first_plan_text = (self.project_dir / "outputs" / "render-plan.json").read_text(encoding="utf-8")

        second_result = run_script("run_ffmpeg_renderer_reviewer.py", self.project_dir)
        self.assertEqual(second_result.returncode, 0, second_result.stderr)
        second_plan_text = (self.project_dir / "outputs" / "render-plan.json").read_text(encoding="utf-8")
        self.assertEqual(first_plan_text, second_plan_text)

        payload = json.loads(first_plan_text)
        self.assertEqual(payload["version"], "v1")
        self.assertIn("checks", payload)
        self.assertIn("ffmpeg", payload)
        self.assertGreater(payload["duration_seconds"], 0)

    def test_run_ffmpeg_renderer_reviewer_rejects_missing_required_tracks(self) -> None:
        self.assertEqual(run_script("run_input_parser.py", self.project_dir).returncode, 0)
        self.assertEqual(run_script("run_script_writer.py", self.project_dir).returncode, 0)
        self.assertEqual(run_script("run_audio_foundation.py", self.project_dir).returncode, 0)
        self.assertEqual(run_script("run_global_timeline_initializer.py", self.project_dir).returncode, 0)
        self.assertEqual(run_script("run_beat_sync_storyboard_planner.py", self.project_dir).returncode, 0)
        self.assertEqual(run_script("run_constrained_video_generator.py", self.project_dir).returncode, 0)
        self.assertEqual(run_script("run_timeline_builder.py", self.project_dir).returncode, 0)

        timeline_path = self.project_dir / "timeline" / "timeline.json"
        timeline_payload = json.loads(timeline_path.read_text(encoding="utf-8"))
        timeline_payload["tracks"] = []
        timeline_path.write_text(json.dumps(timeline_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        result = run_script("run_ffmpeg_renderer_reviewer.py", self.project_dir)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing required tracks", result.stderr)


if __name__ == "__main__":
    unittest.main()
