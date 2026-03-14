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

    def test_session_handoff_writes_markdown_pack(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = pathlib.Path(tmp) / "demo-project"
            (project_dir / "orchestration").mkdir(parents=True)
            (project_dir / "review").mkdir(parents=True)
            (project_dir / "orchestration" / "state.json").write_text(
                json.dumps(
                    {
                        "current_stage": "prompt_engineer",
                        "completed_stages": ["input_parser", "script_writer"],
                        "skipped_stages": [],
                        "last_failed_stage": None,
                        "next_stage": "image_generator",
                    }
                ),
                encoding="utf-8",
            )
            (project_dir / "orchestration" / "plan.json").write_text(
                json.dumps(
                    {
                        "workflow": "video_pipeline",
                        "planned_stages": ["input_parser", "script_writer", "prompt_engineer", "image_generator"],
                        "optional_stages": [],
                        "disabled_stages": [],
                        "metadata": {},
                    }
                ),
                encoding="utf-8",
            )
            (project_dir / "orchestration" / "decisions.jsonl").write_text(
                "\n".join(
                    [
                        json.dumps({"timestamp": "2026-03-14T00:00:00+00:00", "decision_type": "advance", "reason": "ready"}),
                        json.dumps({"timestamp": "2026-03-14T00:05:00+00:00", "decision_type": "retry", "reason": "prompt tweak"}),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (project_dir / "review" / "review-report.json").write_text(
                json.dumps(
                    {
                        "status": "ready",
                        "next_recommended_action": "Run image_generator.",
                        "missing_artifacts": [],
                        "warnings": [],
                    }
                ),
                encoding="utf-8",
            )
            (project_dir / "review" / "observer-summary.md").write_text(
                "# Project Overview\n\n- Current stage: prompt_engineer\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    "python3",
                    str(REPO_ROOT / "scripts" / "session_handoff.py"),
                    "--project",
                    str(project_dir),
                    "--decisions-tail",
                    "2",
                ],
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            output_path = pathlib.Path(result.stdout.strip())
            self.assertTrue(output_path.exists())
            content = output_path.read_text(encoding="utf-8")
            self.assertIn("# Session Handoff Pack", content)
            self.assertIn("Run image_generator.", content)
            self.assertIn("prompt tweak", content)

    def test_session_handoff_defaults_when_review_missing(self) -> None:
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
            (project_dir / "orchestration" / "decisions.jsonl").write_text("", encoding="utf-8")

            result = subprocess.run(
                [
                    "python3",
                    str(REPO_ROOT / "scripts" / "session_handoff.py"),
                    "--project",
                    str(project_dir),
                ],
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            output_path = pathlib.Path(result.stdout.strip())
            content = output_path.read_text(encoding="utf-8")
            self.assertIn("Run input_parser.", content)


if __name__ == "__main__":
    unittest.main()
