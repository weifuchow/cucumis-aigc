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


class ReviewObserverScriptsTest(unittest.TestCase):
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

    def test_review_project_writes_ready_report_for_initialized_project(self) -> None:
        result = run_script("review_project.py", self.project_dir)
        self.assertEqual(result.returncode, 0, result.stderr)

        report = json.loads((self.project_dir / "review" / "review-report.json").read_text(encoding="utf-8"))
        self.assertEqual(report["project"], "demo-project")
        self.assertEqual(report["status"], "ready")
        self.assertEqual(report["completed_stages"], [])
        self.assertEqual(report["missing_artifacts"], [])
        self.assertEqual(report["next_recommended_action"], "Run input_parser.")

    def test_review_project_blocks_inconsistent_completed_stage(self) -> None:
        result = subprocess.run(
            [
                "python3",
                str(REPO_ROOT / "scripts" / "update_orchestration_state.py"),
                "--project",
                str(self.project_dir),
                "--current-stage",
                "beat_sync_storyboard_planner",
                "--next-stage",
                "global_timeline_initializer",
                "--completed-stage",
                "input_parser",
                "--completed-stage",
                "script_writer",
                "--workflow",
                "video_pipeline",
                "--planned-stage",
                "input_parser",
                "--planned-stage",
                "script_writer",
                "--planned-stage",
                "audio_foundation",
                "--planned-stage",
                "global_timeline_initializer",
                "--planned-stage",
                "beat_sync_storyboard_planner",
                "--decision-type",
                "resume",
                "--decision-reason",
                "resume from storyboard",
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

        review_result = run_script("review_project.py", self.project_dir)
        self.assertEqual(review_result.returncode, 0, review_result.stderr)

        report = json.loads((self.project_dir / "review" / "review-report.json").read_text(encoding="utf-8"))
        self.assertEqual(report["status"], "blocked")
        self.assertIn("script/script.json", report["missing_artifacts"])
        self.assertEqual(report["next_recommended_action"], "Restore or regenerate script/script.json.")

    def test_review_project_marks_running_stage_as_in_progress(self) -> None:
        result = subprocess.run(
            [
                "python3",
                str(REPO_ROOT / "scripts" / "update_orchestration_state.py"),
                "--project",
                str(self.project_dir),
                "--current-stage",
                "audio_foundation",
                "--completed-stage",
                "input_parser",
                "--completed-stage",
                "script_writer",
                "--workflow",
                "video_pipeline",
                "--planned-stage",
                "input_parser",
                "--planned-stage",
                "script_writer",
                "--planned-stage",
                "audio_foundation",
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        (self.project_dir / "script" / "script.json").write_text(
            json.dumps({"audio_track": [], "visual_track": [], "beats": [], "emotion_markers": [], "turning_points": []}),
            encoding="utf-8",
        )

        review_result = run_script("review_project.py", self.project_dir)
        self.assertEqual(review_result.returncode, 0, review_result.stderr)

        report = json.loads((self.project_dir / "review" / "review-report.json").read_text(encoding="utf-8"))
        self.assertEqual(report["status"], "in_progress")
        self.assertEqual(report["next_recommended_action"], "Continue audio_foundation.")

    def test_observe_project_writes_human_readable_summary(self) -> None:
        subprocess.run(
            [
                "python3",
                str(REPO_ROOT / "scripts" / "update_orchestration_state.py"),
                "--project",
                str(self.project_dir),
                "--current-stage",
                "audio_foundation",
                "--next-stage",
                "global_timeline_initializer",
                "--completed-stage",
                "input_parser",
                "--completed-stage",
                "script_writer",
                "--workflow",
                "video_pipeline",
                "--planned-stage",
                "input_parser",
                "--planned-stage",
                "script_writer",
                "--planned-stage",
                "audio_foundation",
                "--planned-stage",
                "global_timeline_initializer",
                "--planned-stage",
                "beat_sync_storyboard_planner",
                "--decision-type",
                "advance",
                "--decision-reason",
                "audio assets ready",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        (self.project_dir / "script" / "script.json").write_text(
            json.dumps({"audio_track": [], "visual_track": [], "beats": [], "emotion_markers": [], "turning_points": []}),
            encoding="utf-8",
        )

        review_result = run_script("review_project.py", self.project_dir)
        self.assertEqual(review_result.returncode, 0, review_result.stderr)

        observe_result = run_script("observe_project.py", self.project_dir)
        self.assertEqual(observe_result.returncode, 0, observe_result.stderr)

        summary = (self.project_dir / "review" / "observer-summary.md").read_text(encoding="utf-8")
        self.assertIn("# Project Overview", summary)
        self.assertIn("Current stage: `audio_foundation`", summary)
        self.assertIn("Next stage: `global_timeline_initializer`", summary)
        self.assertIn("Recent decision: `advance` - audio assets ready", summary)
        self.assertIn("Review status: `ready`", summary)


if __name__ == "__main__":
    unittest.main()
