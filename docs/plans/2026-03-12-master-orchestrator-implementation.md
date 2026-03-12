# Master Orchestrator Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add the first `master_orchestrator` skill, its orchestration schemas, project template files, and helper scripts for inspecting and updating orchestration state.

**Architecture:** The implementation adds a lightweight orchestration layer on top of the existing skill workspace. The `master_orchestrator` skill will read workflow rules and project artifacts, while reusable scripts handle project inspection and orchestration state writes; shared JSON Schemas define the structure of orchestration outputs.

**Tech Stack:** Markdown, JSON Schema, Python 3 scripts, filesystem-based state

---

### Task 1: Add the `master_orchestrator` skill definition

**Files:**
- Create: `skills/master_orchestrator/SKILL.md`

**Step 1: Write the skill definition**

Document the orchestrator role, reads, writes, control rules, decision logging, and recovery behavior in `skills/master_orchestrator/SKILL.md`.

**Step 2: Verify the skill file renders correctly**

Run: `sed -n '1,220p' skills/master_orchestrator/SKILL.md`
Expected: The file clearly defines a lightweight orchestrator and its outputs under `orchestration/`.

**Step 3: Commit**

```bash
git add skills/master_orchestrator/SKILL.md
git commit -m "docs: add master orchestrator skill"
```

### Task 2: Add orchestration schemas

**Files:**
- Create: `schemas/orchestration-state.schema.json`
- Create: `schemas/orchestration-plan.schema.json`
- Create: `schemas/orchestration-decision.schema.json`
- Modify: `schemas/project-structure.md`

**Step 1: Write the state schema**

Define `current_stage`, `completed_stages`, `skipped_stages`, `last_failed_stage`, and `next_stage`.

**Step 2: Write the plan schema**

Define workflow name, planned stages, optional stages, disabled stages, and plan metadata.

**Step 3: Write the decision schema**

Define one decision record with timestamp, decision type, reason, and payload.

**Step 4: Update project structure contract**

Add the `orchestration/` directory and its required files to `schemas/project-structure.md`.

**Step 5: Verify schema files parse**

Run: `python3 - <<'PY'\nimport json, pathlib\nfor path in sorted(pathlib.Path('schemas').glob('orchestration-*.json')):\n    json.loads(path.read_text())\n    print(path)\nPY`
Expected: All orchestration schema files print without JSON parsing errors.

**Step 6: Commit**

```bash
git add schemas/orchestration-state.schema.json schemas/orchestration-plan.schema.json schemas/orchestration-decision.schema.json schemas/project-structure.md
git commit -m "docs: add orchestration schemas"
```

### Task 3: Extend the project template for orchestration artifacts

**Files:**
- Create: `templates/project/orchestration/state.json`
- Create: `templates/project/orchestration/plan.json`
- Create: `templates/project/orchestration/decisions.jsonl`

**Step 1: Add orchestration template files**

Create minimal starter files for orchestration state, plan, and decision log.

**Step 2: Verify the template paths exist**

Run: `find templates/project/orchestration -maxdepth 2 -type f | sort`
Expected: The three orchestration files are present.

**Step 3: Commit**

```bash
git add templates/project/orchestration
git commit -m "chore: add orchestration project template files"
```

### Task 4: Update workflow docs to reference the orchestrator

**Files:**
- Modify: `workflows/video_pipeline/WORKFLOW.md`
- Modify: `workflows/video_pipeline/state-machine.md`
- Modify: `workflows/video_pipeline/handoff-contracts.md`

**Step 1: Add orchestrator ownership note**

Update the workflow docs to say `master_orchestrator` interprets and advances the workflow.

**Step 2: Add orchestration outputs where relevant**

Document where orchestration state and decision files live when relevant to recovery or validation.

**Step 3: Verify the workflow docs**

Run: `rg -n 'master_orchestrator|orchestration/' workflows/video_pipeline`
Expected: Each relevant workflow document mentions the orchestrator integration.

**Step 4: Commit**

```bash
git add workflows/video_pipeline
git commit -m "docs: wire orchestrator into workflow docs"
```

### Task 5: Write tests for orchestration helper scripts

**Files:**
- Create: `tests/test_orchestration_scripts.py`
- Test: `tests/test_orchestration_scripts.py`

**Step 1: Write a failing test for project inspection**

Add a test that initializes a minimal project tree and expects `scripts/inspect_project.py` to report current stage information.

**Step 2: Run the test to verify failure**

Run: `python3 -m unittest tests/test_orchestration_scripts.py -v`
Expected: FAIL because the new scripts do not exist yet.

**Step 3: Commit**

Skip commit until implementation exists.

### Task 6: Implement `inspect_project.py`

**Files:**
- Create: `scripts/inspect_project.py`
- Modify: `tests/test_orchestration_scripts.py`

**Step 1: Write minimal implementation**

Implement a CLI that reads a project path, checks for known artifact files, and prints a JSON object describing detected state.

**Step 2: Run the orchestration script tests**

Run: `python3 -m unittest tests/test_orchestration_scripts.py -v`
Expected: At least the inspection-related tests pass.

**Step 3: Refine output only if tests require it**

Do not add speculative fields beyond the tested contract.

**Step 4: Commit**

```bash
git add scripts/inspect_project.py tests/test_orchestration_scripts.py
git commit -m "feat: add project inspection script"
```

### Task 7: Implement `update_orchestration_state.py`

**Files:**
- Create: `scripts/update_orchestration_state.py`
- Modify: `tests/test_orchestration_scripts.py`

**Step 1: Add a failing test for orchestration state update**

Extend the test file with a case that writes orchestration state, plan, and one decision record.

**Step 2: Run the test to verify failure**

Run: `python3 -m unittest tests/test_orchestration_scripts.py -v`
Expected: FAIL because the update script does not exist yet.

**Step 3: Implement the minimal updater**

Write a CLI that updates `orchestration/state.json`, optionally writes `plan.json`, and appends a decision JSON line if requested.

**Step 4: Run the tests again**

Run: `python3 -m unittest tests/test_orchestration_scripts.py -v`
Expected: All orchestration script tests pass.

**Step 5: Commit**

```bash
git add scripts/update_orchestration_state.py tests/test_orchestration_scripts.py
git commit -m "feat: add orchestration state update script"
```

### Task 8: Final integration verification

**Files:**
- Modify: `skills/master_orchestrator/SKILL.md`
- Modify: `schemas/`
- Modify: `templates/project/`
- Modify: `scripts/`

**Step 1: Run both test suites**

Run:

```bash
python3 -m unittest tests/test_workspace_scripts.py -v
python3 -m unittest tests/test_orchestration_scripts.py -v
```

Expected: all tests pass.

**Step 2: Run a smoke test on a sample project**

Run:

```bash
name="orchestrator-demo-$(date +%s)"
python3 scripts/init_project.py --project-name "$name"
python3 scripts/inspect_project.py --project "projects/$name"
python3 scripts/update_orchestration_state.py --project "projects/$name" --current-stage input_parser --next-stage script_writer --decision-type stage_selection --decision-reason "initial transition"
python3 scripts/validate_project.py --project "projects/$name"
```

Expected: project is valid, inspection returns JSON, orchestration files are updated.

**Step 3: Verify Git state**

Run: `git status --short`
Expected: clean working tree after the final commit.

**Step 4: Commit**

Skip if no new changes remain.
