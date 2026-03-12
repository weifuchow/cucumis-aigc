import json
import pathlib
import subprocess
import tempfile
import unittest


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


class WorkspaceScriptsTest(unittest.TestCase):
    def test_init_project_creates_expected_structure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace_root = pathlib.Path(tmp)
            projects_dir = workspace_root / "projects"
            projects_dir.mkdir()

            result = subprocess.run(
                [
                    "python3",
                    str(REPO_ROOT / "scripts" / "init_project.py"),
                    "--project-name",
                    "demo-project",
                    "--projects-dir",
                    str(projects_dir),
                ],
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)

            project_dir = projects_dir / "demo-project"
            self.assertTrue((project_dir / "README.md").exists())
            self.assertTrue((project_dir / "request.md").exists())
            self.assertTrue((project_dir / "events" / "events.jsonl").exists())
            self.assertTrue((project_dir / "orchestration" / "state.json").exists())
            self.assertTrue((project_dir / "orchestration" / "plan.json").exists())
            self.assertTrue((project_dir / "orchestration" / "decisions.jsonl").exists())
            self.assertTrue((project_dir / "input" / "input.json").exists())
            self.assertTrue((project_dir / "script").is_dir())
            self.assertTrue((project_dir / "storyboard").is_dir())
            self.assertTrue((project_dir / "timeline").is_dir())
            self.assertTrue((project_dir / "assets").is_dir())
            self.assertTrue((project_dir / "outputs").is_dir())

    def test_write_event_appends_json_line(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace_root = pathlib.Path(tmp)
            projects_dir = workspace_root / "projects"
            projects_dir.mkdir()
            project_dir = projects_dir / "demo-project"
            project_dir.mkdir()
            events_dir = project_dir / "events"
            events_dir.mkdir()
            events_path = events_dir / "events.jsonl"
            events_path.write_text("", encoding="utf-8")

            result = subprocess.run(
                [
                    "python3",
                    str(REPO_ROOT / "scripts" / "write_event.py"),
                    "--project",
                    str(project_dir),
                    "--event-type",
                    "workflow.started",
                    "--payload",
                    '{"stage":"input_parser"}',
                ],
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)

            lines = events_path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 1)
            event = json.loads(lines[0])
            self.assertEqual(event["event_type"], "workflow.started")
            self.assertEqual(event["payload"]["stage"], "input_parser")

    def test_validate_project_accepts_initialized_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace_root = pathlib.Path(tmp)
            projects_dir = workspace_root / "projects"
            projects_dir.mkdir()
            project_dir = projects_dir / "demo-project"
            project_dir.mkdir()

            (project_dir / "README.md").write_text("demo", encoding="utf-8")
            (project_dir / "request.md").write_text("request", encoding="utf-8")
            (project_dir / "events").mkdir()
            (project_dir / "events" / "events.jsonl").write_text("", encoding="utf-8")
            (project_dir / "orchestration").mkdir()
            (project_dir / "orchestration" / "state.json").write_text(
                '{"current_stage": null, "completed_stages": [], "skipped_stages": [], "last_failed_stage": null, "next_stage": null}',
                encoding="utf-8",
            )
            (project_dir / "orchestration" / "plan.json").write_text(
                '{"workflow": "video_pipeline", "planned_stages": [], "optional_stages": [], "disabled_stages": [], "metadata": {}}',
                encoding="utf-8",
            )
            (project_dir / "orchestration" / "decisions.jsonl").write_text("", encoding="utf-8")
            (project_dir / "input").mkdir()
            (project_dir / "input" / "input.json").write_text("{}", encoding="utf-8")
            (project_dir / "script").mkdir()
            (project_dir / "storyboard").mkdir()
            (project_dir / "timeline").mkdir()
            (project_dir / "assets").mkdir()
            (project_dir / "outputs").mkdir()

            result = subprocess.run(
                [
                    "python3",
                    str(REPO_ROOT / "scripts" / "validate_project.py"),
                    "--project",
                    str(project_dir),
                ],
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)

    def test_validate_project_rejects_missing_orchestration_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = pathlib.Path(tmp) / "demo-project"
            project_dir.mkdir()

            (project_dir / "README.md").write_text("demo", encoding="utf-8")
            (project_dir / "request.md").write_text("request", encoding="utf-8")
            (project_dir / "events").mkdir()
            (project_dir / "events" / "events.jsonl").write_text("", encoding="utf-8")
            (project_dir / "input").mkdir()
            (project_dir / "input" / "input.json").write_text("{}", encoding="utf-8")
            (project_dir / "script").mkdir()
            (project_dir / "storyboard").mkdir()
            (project_dir / "timeline").mkdir()
            (project_dir / "assets").mkdir()
            (project_dir / "outputs").mkdir()

            result = subprocess.run(
                [
                    "python3",
                    str(REPO_ROOT / "scripts" / "validate_project.py"),
                    "--project",
                    str(project_dir),
                ],
                capture_output=True,
                text=True,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("orchestration/state.json", result.stderr)


if __name__ == "__main__":
    unittest.main()
