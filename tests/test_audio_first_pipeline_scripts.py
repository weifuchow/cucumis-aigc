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


if __name__ == "__main__":
    unittest.main()
