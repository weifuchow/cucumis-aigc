import json
import pathlib
import subprocess
import tempfile
import unittest


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


class OrchestrationScriptsTest(unittest.TestCase):
    def test_inspect_project_reports_current_and_next_stage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = pathlib.Path(tmp) / "demo-project"
            (project_dir / "events").mkdir(parents=True)
            (project_dir / "events" / "events.jsonl").write_text("", encoding="utf-8")
            (project_dir / "orchestration").mkdir()
            (project_dir / "orchestration" / "state.json").write_text(
                json.dumps(
                    {
                        "current_stage": "input_parser",
                        "completed_stages": ["input_parser"],
                        "skipped_stages": [],
                        "last_failed_stage": None,
                        "next_stage": "script_writer",
                    }
                ),
                encoding="utf-8",
            )
            (project_dir / "input").mkdir()
            (project_dir / "input" / "input.json").write_text("{}", encoding="utf-8")

            result = subprocess.run(
                [
                    "python3",
                    str(REPO_ROOT / "scripts" / "inspect_project.py"),
                    "--project",
                    str(project_dir),
                ],
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["current_stage"], "input_parser")
            self.assertEqual(payload["next_stage"], "script_writer")


if __name__ == "__main__":
    unittest.main()
