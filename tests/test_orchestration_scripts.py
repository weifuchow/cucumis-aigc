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

    def test_update_orchestration_state_writes_state_plan_and_decision(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = pathlib.Path(tmp) / "demo-project"
            (project_dir / "orchestration").mkdir(parents=True)
            (project_dir / "orchestration" / "state.json").write_text(
                json.dumps(
                    {
                        "current_stage": None,
                        "completed_stages": [],
                        "skipped_stages": [],
                        "last_failed_stage": None,
                        "next_stage": None,
                    }
                ),
                encoding="utf-8",
            )
            (project_dir / "orchestration" / "plan.json").write_text(
                json.dumps(
                    {
                        "workflow": "video_pipeline",
                        "planned_stages": [],
                        "optional_stages": [],
                        "disabled_stages": [],
                        "metadata": {},
                    }
                ),
                encoding="utf-8",
            )
            (project_dir / "orchestration" / "decisions.jsonl").write_text(
                "",
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    "python3",
                    str(REPO_ROOT / "scripts" / "update_orchestration_state.py"),
                    "--project",
                    str(project_dir),
                    "--current-stage",
                    "input_parser",
                    "--next-stage",
                    "script_writer",
                    "--completed-stage",
                    "input_parser",
                    "--workflow",
                    "video_pipeline",
                    "--planned-stage",
                    "input_parser",
                    "--planned-stage",
                    "script_writer",
                    "--decision-type",
                    "stage_selection",
                    "--decision-reason",
                    "initial transition",
                ],
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)

            state = json.loads(
                (project_dir / "orchestration" / "state.json").read_text(encoding="utf-8")
            )
            self.assertEqual(state["current_stage"], "input_parser")
            self.assertEqual(state["next_stage"], "script_writer")
            self.assertEqual(state["completed_stages"], ["input_parser"])

            plan = json.loads(
                (project_dir / "orchestration" / "plan.json").read_text(encoding="utf-8")
            )
            self.assertEqual(plan["workflow"], "video_pipeline")
            self.assertEqual(plan["planned_stages"], ["input_parser", "script_writer"])

            decisions = (
                project_dir / "orchestration" / "decisions.jsonl"
            ).read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(decisions), 1)
            decision = json.loads(decisions[0])
            self.assertEqual(decision["decision_type"], "stage_selection")
            self.assertEqual(decision["reason"], "initial transition")


if __name__ == "__main__":
    unittest.main()
