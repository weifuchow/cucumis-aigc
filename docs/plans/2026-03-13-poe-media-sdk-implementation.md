# Poe Media SDK Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a Poe-backed media SDK, project-level model selection, and real audio/video generation entrypoints for the audio-first workflow.

**Architecture:** The implementation introduces a small `scripts/poe/` adapter layer that loads Poe credentials, fetches and classifies models, and provides `generate_audio` / `generate_video` helpers. Workflow scripts stay thin: they read project-level model settings, call the adapter, write normalized artifacts, and fall back to deterministic mock outputs when Poe credentials are unavailable.

**Tech Stack:** Python 3 standard library, JSON, dotenv-style config parsing, unittest

---

### Task 1: Document and template the new Poe-backed project configuration

**Files:**
- Modify: `schemas/task-input.schema.json`
- Modify: `templates/project/input/input.json`
- Modify: `schemas/project-structure.md`
- Create: `.env.example`

**Step 1: Add a failing test for project input model fields**

Update `tests/test_audio_first_pipeline_scripts.py` to assert `input.json` includes `audio_model` and `video_model`.

**Step 2: Run the test to verify it fails**

Run: `python3 -m unittest tests.test_audio_first_pipeline_scripts.AudioFirstPipelineScriptsTest.test_run_input_parser_writes_project_level_models -v`
Expected: FAIL because the fields do not exist yet.

**Step 3: Update schema/template/docs minimally**

Add `audio_model` and `video_model` to the task input schema, project template, and project-structure contract. Add `.env.example` with Poe connection variables.

**Step 4: Re-run the test**

Run the same command and expect it still fails until `run_input_parser.py` is updated in a later task.

### Task 2: Add the Poe SDK catalog layer

**Files:**
- Create: `scripts/poe/__init__.py`
- Create: `scripts/poe/client.py`
- Create: `scripts/poe/catalog.py`
- Create: `scripts/poe/usage.py`
- Create: `tests/test_poe_sdk.py`

**Step 1: Write failing catalog tests**

Add tests for:
- `.env` / environment config loading
- media model classification
- price display formatting
- recommendation sorting

**Step 2: Run the new Poe SDK tests**

Run: `python3 -m unittest tests/test_poe_sdk.py -v`
Expected: FAIL because the package does not exist yet.

**Step 3: Implement the minimal SDK catalog/config layer**

Use stdlib only. Read `.env`, fetch model catalog with `urllib`, classify audio/video models, and normalize display data.

**Step 4: Re-run the tests**

Expect the catalog-related tests to pass.

### Task 3: Add Poe media generation helpers

**Files:**
- Create: `scripts/poe/media.py`
- Modify: `tests/test_poe_sdk.py`

**Step 1: Write failing media helper tests**

Cover:
- audio generation returns normalized payload
- video generation returns normalized payload
- missing API key falls back to deterministic mock

**Step 2: Run the targeted tests**

Run: `python3 -m unittest tests.test_poe_sdk.PoeSdkTest -v`
Expected: FAIL on missing media helper behavior.

**Step 3: Implement minimal media helpers**

Support:
- `generate_audio(...)`
- `generate_video(...)`
- normalized metadata
- usage event extraction
- mock fallback when no key exists

**Step 4: Re-run the targeted tests**

Expect Poe SDK tests to pass.

### Task 4: Integrate project-level model defaults into input parsing

**Files:**
- Modify: `scripts/run_input_parser.py`
- Modify: `tests/test_audio_first_pipeline_scripts.py`

**Step 1: Update the failing input parser test**

Assert project input now includes default `audio_model` and `video_model`.

**Step 2: Run the targeted test**

Run: `python3 -m unittest tests.test_audio_first_pipeline_scripts.AudioFirstPipelineScriptsTest.test_run_input_parser_writes_project_level_models -v`
Expected: FAIL because parser does not write these fields.

**Step 3: Implement minimal parser changes**

Write recommended default models into `input.json`.

**Step 4: Re-run the targeted test**

Expect PASS.

### Task 5: Integrate Poe audio generation into `run_audio_foundation.py`

**Files:**
- Modify: `scripts/run_audio_foundation.py`
- Modify: `templates/project/audio/voiceover.json`
- Create: `templates/project/audio/tts-response.json`
- Create: `templates/project/audio/usage.json`
- Modify: `tests/test_audio_first_pipeline_scripts.py`

**Step 1: Add a failing audio integration test**

Assert the script writes:
- `audio/tts-response.json`
- `audio/usage.json`
- model metadata using the configured `audio_model`

**Step 2: Run the targeted test**

Run: `python3 -m unittest tests.test_audio_first_pipeline_scripts.AudioFirstPipelineScriptsTest.test_run_audio_foundation_records_poe_metadata -v`
Expected: FAIL because the metadata files do not exist yet.

**Step 3: Implement the minimal integration**

Call the Poe media helper, normalize the returned data, and write the extra files.

**Step 4: Re-run the targeted test**

Expect PASS.

### Task 6: Add constrained video generation entrypoint

**Files:**
- Create: `scripts/run_constrained_video_generator.py`
- Create: `templates/project/video/clips.json`
- Create: `templates/project/video/requests.json`
- Create: `templates/project/video/usage.json`
- Modify: `schemas/project-structure.md`
- Modify: `tests/test_audio_first_pipeline_scripts.py`

**Step 1: Write a failing video generation test**

Cover a minimal flow that produces:
- `video/clips.json`
- `video/requests.json`
- `video/usage.json`

**Step 2: Run the targeted test**

Run: `python3 -m unittest tests.test_audio_first_pipeline_scripts.AudioFirstPipelineScriptsTest.test_run_constrained_video_generator_writes_video_artifacts -v`
Expected: FAIL because the script does not exist yet.

**Step 3: Implement the minimal script**

Read `storyboard/storyboard.json` and project `video_model`, call the Poe helper (or mock fallback), and write normalized video artifacts.

**Step 4: Re-run the targeted test**

Expect PASS.

### Task 7: Add model listing and cost logging support

**Files:**
- Create: `scripts/list_poe_models.py`
- Create: `templates/project/costs/poe-usage.jsonl`
- Modify: `scripts/run_audio_foundation.py`
- Modify: `scripts/run_constrained_video_generator.py`
- Modify: `tests/test_poe_sdk.py`

**Step 1: Write failing tests**

Cover:
- list script outputs categorized models
- audio/video scripts append to `costs/poe-usage.jsonl`

**Step 2: Run the relevant tests**

Run: `python3 -m unittest tests/test_poe_sdk.py tests/test_audio_first_pipeline_scripts.py -v`
Expected: FAIL on missing list script or cost log behavior.

**Step 3: Implement minimal support**

Add the list script and append normalized cost events after each media call.

**Step 4: Re-run the relevant tests**

Expect PASS.

### Task 8: Align workspace initialization and validation

**Files:**
- Modify: `scripts/validate_project.py`
- Modify: `tests/test_workspace_scripts.py`

**Step 1: Add failing workspace assertions**

Expect initialized projects to include video/cost template paths and validate review/audio/video/cost artifacts appropriately.

**Step 2: Run the workspace tests**

Run: `python3 -m unittest tests/test_workspace_scripts.py -v`
Expected: FAIL until workspace alignment is complete.

**Step 3: Implement minimal updates**

Ensure validation checks the new paths that should always exist and leaves stage-optional files flexible.

**Step 4: Re-run the workspace tests**

Expect PASS.

### Task 9: Final verification and smoke test

**Files:**
- Modify: `scripts/`
- Modify: `schemas/`
- Modify: `templates/project/`
- Modify: `tests/`

**Step 1: Run the full test suite**

Run: `python3 -m unittest discover -s tests -v`
Expected: all tests pass.

**Step 2: Run a media smoke test**

Run:

```bash
name="poe-demo-$(date +%s)"
python3 scripts/init_project.py --project-name "$name"
python3 scripts/run_input_parser.py --project "projects/$name"
python3 scripts/run_script_writer.py --project "projects/$name"
python3 scripts/run_audio_foundation.py --project "projects/$name"
python3 scripts/run_global_timeline_initializer.py --project "projects/$name"
python3 scripts/run_beat_sync_storyboard_planner.py --project "projects/$name"
python3 scripts/run_constrained_video_generator.py --project "projects/$name"
python3 scripts/validate_project.py --project "projects/$name"
```

Expected: all scripts complete successfully and media/cost artifacts are written.

**Step 3: Verify git state**

Run: `git status --short`
Expected: clean after the final commit.
