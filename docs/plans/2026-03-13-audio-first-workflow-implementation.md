# Audio-First Workflow Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Refactor the workspace to use the new audio-first workflow as the default standard and make steps 1-5 executable.

**Architecture:** The implementation rewrites the workflow, orchestration expectations, and core skill set around an audio-driven timing model. The first five steps become executable through filesystem-based scripts that generate structured mock artifacts for parsed input, emotion-tagged script output, audio foundations, global timeline anchors, and beat-synced storyboard output.

**Tech Stack:** Markdown, JSON Schema, Python 3 scripts, filesystem-based state

---

### Task 1: Rewrite workflow and orchestrator docs for the audio-first chain

**Files:**
- Modify: `README.md`
- Modify: `workflows/video_pipeline/WORKFLOW.md`
- Modify: `workflows/video_pipeline/state-machine.md`
- Modify: `workflows/video_pipeline/handoff-contracts.md`
- Modify: `skills/master_orchestrator/SKILL.md`

**Step 1: Rewrite the default 12-step chain**

Replace the existing default stage order with the audio-first chain and document the new responsibilities.

**Step 2: Update orchestrator expectations**

Document the new default planned stages and audio-first decision points in `skills/master_orchestrator/SKILL.md`.

**Step 3: Verify the new stage names appear consistently**

Run: `rg -n 'audio_foundation|global_timeline_initializer|beat_sync_storyboard_planner|prompt_engineer|constrained_video_generator|subtitle_asset_manager|ffmpeg_renderer_reviewer' README.md workflows/video_pipeline skills/master_orchestrator/SKILL.md`
Expected: The new names appear consistently in the rewritten docs.

**Step 4: Commit**

```bash
git add README.md workflows/video_pipeline skills/master_orchestrator/SKILL.md
git commit -m "docs: rewrite workflow for audio-first pipeline"
```

### Task 2: Replace and align skill definitions with the new default names

**Files:**
- Modify: `skills/input_parser/SKILL.md`
- Modify: `skills/script_writer/SKILL.md`
- Create: `skills/audio_foundation/SKILL.md`
- Create: `skills/global_timeline_initializer/SKILL.md`
- Create: `skills/beat_sync_storyboard_planner/SKILL.md`
- Create: `skills/prompt_engineer/SKILL.md`
- Create: `skills/constrained_video_generator/SKILL.md`
- Create: `skills/subtitle_asset_manager/SKILL.md`
- Create: `skills/ffmpeg_renderer_reviewer/SKILL.md`
- Delete/replace conceptual use of: `skills/storyboard_planner/SKILL.md`, `skills/video_generator/SKILL.md`, `skills/subtitle_generator/SKILL.md`, `skills/asset_manager/SKILL.md`, `skills/ffmpeg_renderer/SKILL.md`, `skills/reviewer/SKILL.md`

**Step 1: Upgrade first-five executable skill docs**

Document real inputs, outputs, and artifact paths for `input_parser`, `script_writer`, `audio_foundation`, `global_timeline_initializer`, and `beat_sync_storyboard_planner`.

**Step 2: Add placeholder docs for remaining renamed skills**

Create first-pass definitions for `prompt_engineer`, `constrained_video_generator`, `subtitle_asset_manager`, and `ffmpeg_renderer_reviewer`.

**Step 3: Verify all new default skill docs exist**

Run: `find skills -maxdepth 2 -name 'SKILL.md' | sort`
Expected: The audio-first skill names exist and the obsolete default names are no longer the canonical chain.

**Step 4: Commit**

```bash
git add skills
git commit -m "docs: align skills with audio-first pipeline"
```

### Task 3: Refactor schemas and project structure contracts

**Files:**
- Modify: `schemas/task-input.schema.json`
- Modify: `schemas/script.schema.json`
- Create: `schemas/audio-foundation.schema.json`
- Create: `schemas/global-timeline.schema.json`
- Modify: `schemas/storyboard.schema.json`
- Modify: `schemas/timeline.schema.json`
- Modify: `schemas/project-structure.md`

**Step 1: Extend input and script schemas**

Add music emotion and pacing fields to task input, and add emotion markers / turning points to script output.

**Step 2: Add new audio-first schemas**

Create schemas for audio foundations and the global timeline grid.

**Step 3: Tighten storyboard and timeline schemas**

Update storyboard to require explicit timing and beat alignment, and update timeline to acknowledge global-timeline-driven assembly.

**Step 4: Update project structure contract**

Add `audio/`, `timeline/global-timeline.json`, and any other new required directories or files.

**Step 5: Verify all JSON schemas parse**

Run: `python3 - <<'PY'\nimport json, pathlib\nfor path in sorted(pathlib.Path('schemas').glob('*.json')):\n    json.loads(path.read_text())\nprint('ok')\nPY`
Expected: `ok`

**Step 6: Commit**

```bash
git add schemas
git commit -m "docs: refactor schemas for audio-first artifacts"
```

### Task 4: Extend project templates for audio-first artifacts

**Files:**
- Modify: `templates/project/input/input.json`
- Create: `templates/project/audio/voiceover.json`
- Create: `templates/project/audio/bgm-selection.json`
- Create: `templates/project/audio/beat-grid.json`
- Create: `templates/project/timeline/global-timeline.json`
- Modify: `templates/project/storyboard/.gitkeep` or replace with a real starter file if needed

**Step 1: Add audio and global timeline template files**

Create starter JSON files for the new artifact layout.

**Step 2: Ensure template tree matches updated project structure**

Update template contents to reflect the new required fields.

**Step 3: Verify template files exist**

Run: `find templates/project -maxdepth 3 -type f | sort`
Expected: The audio-first template files exist.

**Step 4: Commit**

```bash
git add templates/project
git commit -m "chore: extend templates for audio-first artifacts"
```

### Task 5: Update workspace tests for the new project structure

**Files:**
- Modify: `tests/test_workspace_scripts.py`

**Step 1: Add failing expectations for new initialized files**

Update the workspace tests to require the new audio and global timeline files in initialized projects.

**Step 2: Run tests to verify failure**

Run: `python3 -m unittest tests/test_workspace_scripts.py -v`
Expected: FAIL until the scripts are aligned.

**Step 3: Commit**

Skip commit until implementation exists.

### Task 6: Align `init_project.py` and `validate_project.py` with the new structure

**Files:**
- Modify: `scripts/init_project.py`
- Modify: `scripts/validate_project.py`
- Modify: `tests/test_workspace_scripts.py`

**Step 1: Update initialization behavior**

Ensure initialized projects copy the new audio-first template structure.

**Step 2: Update validation behavior**

Require the new audio and global timeline files when validating a project.

**Step 3: Run workspace tests again**

Run: `python3 -m unittest tests/test_workspace_scripts.py -v`
Expected: PASS

**Step 4: Commit**

```bash
git add scripts/init_project.py scripts/validate_project.py tests/test_workspace_scripts.py
git commit -m "feat: align workspace scripts with audio-first structure"
```

### Task 7: Write tests for first-five executable scripts

**Files:**
- Create: `tests/test_audio_first_pipeline_scripts.py`

**Step 1: Add a failing test for `input_parser` output expectations**

The test should require music emotion and pacing fields in generated input.

**Step 2: Add a failing test for `script_writer` output expectations**

The test should require emotion markers and turning points.

**Step 3: Add a failing test for `audio_foundation`**

The test should require `voiceover.json`, `bgm-selection.json`, and `beat-grid.json`.

**Step 4: Add a failing test for `global_timeline_initializer`**

The test should require `timeline/global-timeline.json`.

**Step 5: Add a failing test for `beat_sync_storyboard_planner`**

The test should require a strictly timed storyboard output.

**Step 6: Run the new test file**

Run: `python3 -m unittest tests/test_audio_first_pipeline_scripts.py -v`
Expected: FAIL because the scripts do not exist yet.

### Task 8: Implement executable step scripts for the audio-first chain

**Files:**
- Create: `scripts/run_input_parser.py`
- Create: `scripts/run_script_writer.py`
- Create: `scripts/run_audio_foundation.py`
- Create: `scripts/run_global_timeline_initializer.py`
- Create: `scripts/run_beat_sync_storyboard_planner.py`
- Modify: `tests/test_audio_first_pipeline_scripts.py`

**Step 1: Implement `run_input_parser.py`**

Write minimal logic that converts a request file into `input/input.json` with music emotion and pacing fields.

**Step 2: Implement `run_script_writer.py`**

Write minimal logic that generates structured script output with emotion markers and turning points.

**Step 3: Implement `run_audio_foundation.py`**

Generate mock `voiceover.json`, `bgm-selection.json`, and `beat-grid.json` from the structured script.

**Step 4: Implement `run_global_timeline_initializer.py`**

Combine voiceover and beat-grid data into `timeline/global-timeline.json`.

**Step 5: Implement `run_beat_sync_storyboard_planner.py`**

Generate a strictly timed storyboard aligned to the global timeline.

**Step 6: Run the new test file**

Run: `python3 -m unittest tests/test_audio_first_pipeline_scripts.py -v`
Expected: PASS

**Step 7: Commit**

```bash
git add scripts/run_input_parser.py scripts/run_script_writer.py scripts/run_audio_foundation.py scripts/run_global_timeline_initializer.py scripts/run_beat_sync_storyboard_planner.py tests/test_audio_first_pipeline_scripts.py
git commit -m "feat: add executable audio-first pipeline steps"
```

### Task 9: Final verification

**Files:**
- Modify: `scripts/`
- Modify: `schemas/`
- Modify: `templates/project/`
- Modify: `skills/`

**Step 1: Run all relevant tests**

Run:

```bash
python3 -m unittest tests/test_workspace_scripts.py -v
python3 -m unittest tests/test_orchestration_scripts.py -v
python3 -m unittest tests/test_audio_first_pipeline_scripts.py -v
```

Expected: all tests pass.

**Step 2: Run an end-to-end smoke test for steps 1-5**

Run:

```bash
name="audio-first-demo-$(date +%s)"
python3 scripts/init_project.py --project-name "$name"
python3 scripts/run_input_parser.py --project "projects/$name"
python3 scripts/run_script_writer.py --project "projects/$name"
python3 scripts/run_audio_foundation.py --project "projects/$name"
python3 scripts/run_global_timeline_initializer.py --project "projects/$name"
python3 scripts/run_beat_sync_storyboard_planner.py --project "projects/$name"
python3 scripts/validate_project.py --project "projects/$name"
```

Expected: the first five audio-first artifacts are created and validation succeeds.

**Step 3: Verify Git state**

Run: `git status --short`
Expected: clean working tree after the final commit.

**Step 4: Commit**

Skip if no new changes remain.
