# Skill Workspace Skeleton Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the first working skeleton of a Codex / Claude Code skill workspace for the `cucumis-aigc` video pipeline.

**Architecture:** This implementation creates a skills-first repository structure with workflows, shared schemas, templates, reusable scripts, and a local `projects/` runtime directory. The first iteration only fully documents the minimum pipeline chain and provides shared scripts for project initialization, event logging, and workspace validation; other skills receive placeholder `SKILL.md` files.

**Tech Stack:** Markdown, JSON Schema, Python 3 scripts, filesystem conventions

---

### Task 1: Create top-level workspace directories

**Files:**
- Create: `skills/`
- Create: `workflows/video_pipeline/`
- Create: `schemas/`
- Create: `templates/project/`
- Create: `templates/prompts/`
- Create: `templates/docs/`
- Create: `scripts/`
- Create: `projects/.gitkeep`
- Create: `examples/requests/`
- Create: `examples/projects/`

**Step 1: Create the directories**

Create the top-level folder structure required by the approved design.

**Step 2: Verify the directory structure exists**

Run: `find . -maxdepth 3 | sort`
Expected: The new top-level directories are present.

**Step 3: Commit**

```bash
git add skills workflows schemas templates scripts projects examples
git commit -m "chore: add skill workspace skeleton directories"
```

### Task 2: Add workflow documents for the video pipeline

**Files:**
- Create: `workflows/video_pipeline/WORKFLOW.md`
- Create: `workflows/video_pipeline/state-machine.md`
- Create: `workflows/video_pipeline/handoff-contracts.md`

**Step 1: Write the workflow overview**

Document the end-to-end pipeline, stage order, and operator expectations in `workflows/video_pipeline/WORKFLOW.md`.

**Step 2: Write the state machine document**

Define major states, transitions, failure states, and recovery rules in `workflows/video_pipeline/state-machine.md`.

**Step 3: Write the handoff contract document**

Document what each stage must read, write, and emit in `workflows/video_pipeline/handoff-contracts.md`.

**Step 4: Verify the workflow docs**

Run: `sed -n '1,220p' workflows/video_pipeline/WORKFLOW.md && sed -n '1,220p' workflows/video_pipeline/state-machine.md && sed -n '1,220p' workflows/video_pipeline/handoff-contracts.md`
Expected: All three files exist and describe the pipeline coherently.

**Step 5: Commit**

```bash
git add workflows/video_pipeline
git commit -m "docs: add video pipeline workflow docs"
```

### Task 3: Add core skill definitions

**Files:**
- Create: `skills/input_parser/SKILL.md`
- Create: `skills/script_writer/SKILL.md`
- Create: `skills/storyboard_planner/SKILL.md`
- Create: `skills/timeline_builder/SKILL.md`
- Create: `skills/ffmpeg_renderer/SKILL.md`

**Step 1: Write `input_parser`**

Define purpose, inputs, outputs, file writes, and failure behavior for `skills/input_parser/SKILL.md`.

**Step 2: Write `script_writer`**

Define purpose, inputs, outputs, file writes, and failure behavior for `skills/script_writer/SKILL.md`.

**Step 3: Write `storyboard_planner`**

Define purpose, inputs, outputs, file writes, and failure behavior for `skills/storyboard_planner/SKILL.md`.

**Step 4: Write `timeline_builder`**

Define purpose, inputs, outputs, file writes, and failure behavior for `skills/timeline_builder/SKILL.md`.

**Step 5: Write `ffmpeg_renderer`**

Define purpose, inputs, outputs, file writes, and failure behavior for `skills/ffmpeg_renderer/SKILL.md`.

**Step 6: Verify the skill docs**

Run: `find skills -maxdepth 2 -name 'SKILL.md' | sort | xargs -I{} sh -c "echo '--- {}'; sed -n '1,120p' '{}'"`  
Expected: Each core skill has a populated `SKILL.md`.

**Step 7: Commit**

```bash
git add skills/input_parser skills/script_writer skills/storyboard_planner skills/timeline_builder skills/ffmpeg_renderer
git commit -m "docs: add core pipeline skill definitions"
```

### Task 4: Add placeholder skill definitions for remaining stages

**Files:**
- Create: `skills/keyframe_planner/SKILL.md`
- Create: `skills/image_generator/SKILL.md`
- Create: `skills/video_generator/SKILL.md`
- Create: `skills/voice_generator/SKILL.md`
- Create: `skills/subtitle_generator/SKILL.md`
- Create: `skills/asset_manager/SKILL.md`
- Create: `skills/reviewer/SKILL.md`
- Create: `skills/observer/SKILL.md`

**Step 1: Write placeholder `SKILL.md` files**

Each placeholder file should define role, planned inputs/outputs, current status, and future integration point.

**Step 2: Verify placeholder skills exist**

Run: `find skills -maxdepth 2 -name 'SKILL.md' | sort`
Expected: All planned skill directories contain a `SKILL.md`.

**Step 3: Commit**

```bash
git add skills
git commit -m "docs: add placeholder skill definitions"
```

### Task 5: Add shared schemas and project structure contract

**Files:**
- Create: `schemas/task-input.schema.json`
- Create: `schemas/script.schema.json`
- Create: `schemas/storyboard.schema.json`
- Create: `schemas/timeline.schema.json`
- Create: `schemas/asset-manifest.schema.json`
- Create: `schemas/event.schema.json`
- Create: `schemas/project-structure.md`

**Step 1: Write minimal JSON Schema files**

Define the smallest useful structure for task input, script, storyboard, timeline, asset manifest, and event data.

**Step 2: Write the project structure contract**

Document required files and directories under each generated project in `schemas/project-structure.md`.

**Step 3: Verify schema files are parseable**

Run: `python3 - <<'PY'\nimport json, pathlib\nfor path in pathlib.Path('schemas').glob('*.json'):\n    json.loads(path.read_text())\n    print(path)\nPY`
Expected: Each schema path prints with no JSON parsing errors.

**Step 4: Commit**

```bash
git add schemas
git commit -m "docs: add shared workspace schemas"
```

### Task 6: Add shared templates and examples

**Files:**
- Create: `templates/project/README.md`
- Create: `templates/project/input.json`
- Create: `templates/project/events.jsonl`
- Create: `examples/requests/minimal-video-request.md`
- Create: `examples/projects/minimal-project-tree.md`

**Step 1: Write project template files**

Add placeholder template files that represent the minimum initialized project layout.

**Step 2: Add example request and example project tree**

Provide one realistic input request and one rendered example project structure.

**Step 3: Verify templates and examples exist**

Run: `find templates examples -maxdepth 3 -type f | sort`
Expected: The template and example files are present.

**Step 4: Commit**

```bash
git add templates examples
git commit -m "docs: add project templates and examples"
```

### Task 7: Add reusable scripts for project runtime

**Files:**
- Create: `scripts/init_project.py`
- Create: `scripts/write_event.py`
- Create: `scripts/validate_project.py`

**Step 1: Write a failing script verification**

Plan to run:

```bash
python3 scripts/init_project.py --help
python3 scripts/write_event.py --help
python3 scripts/validate_project.py --help
```

Expected before implementation: each command fails because the file does not yet exist.

**Step 2: Write `init_project.py`**

Create a project directory from `templates/project/`, initialize required files, and print the created path.

**Step 3: Write `write_event.py`**

Append a JSON line event into a project's `events.jsonl`.

**Step 4: Write `validate_project.py`**

Check a target project directory for required files and directories and exit non-zero on violations.

**Step 5: Run script help commands**

Run:

```bash
python3 scripts/init_project.py --help
python3 scripts/write_event.py --help
python3 scripts/validate_project.py --help
```

Expected: all three commands exit successfully and show usage.

**Step 6: Run a smoke test**

Run:

```bash
python3 scripts/init_project.py --project-name demo-project
python3 scripts/write_event.py --project projects/demo-project --event-type workflow.started --payload '{"stage":"input_parser"}'
python3 scripts/validate_project.py --project projects/demo-project
```

Expected: project directory is created, one event is appended, validation exits successfully.

**Step 7: Commit**

```bash
git add scripts templates/project
git commit -m "feat: add shared workspace runtime scripts"
```

### Task 8: Align README with the new workspace structure

**Files:**
- Modify: `README.md`

**Step 1: Update README terminology**

Replace application-oriented framing with skill-workspace framing where needed, while preserving the approved product-level overview.

**Step 2: Add a short workspace structure section**

Describe `skills/`, `workflows/`, `schemas/`, `scripts/`, `templates/`, and `projects/` in terms of the new repository reality.

**Step 3: Verify README headings and structure**

Run: `sed -n '1,260p' README.md`
Expected: The README still reads as the project overview, but no longer implies an app-service codebase as the primary skeleton.

**Step 4: Commit**

```bash
git add README.md
git commit -m "docs: align README with skill workspace skeleton"
```

### Task 9: Final verification

**Files:**
- Modify: `README.md`
- Modify: `skills/`
- Modify: `workflows/`
- Modify: `schemas/`
- Modify: `scripts/`

**Step 1: Verify all planned files exist**

Run: `find skills workflows schemas scripts templates examples -maxdepth 4 | sort`
Expected: All planned skeleton paths exist.

**Step 2: Verify runtime scripts on a fresh sample project**

Run:

```bash
rm -rf projects/demo-project
python3 scripts/init_project.py --project-name demo-project
python3 scripts/write_event.py --project projects/demo-project --event-type workflow.started --payload '{"stage":"input_parser"}'
python3 scripts/validate_project.py --project projects/demo-project
```

Expected: all commands exit 0 and the sample project remains valid.

**Step 3: Verify Git state**

Run: `git status --short`
Expected: clean working tree.

**Step 4: Commit**

Skip if no new changes remain after prior commits.
