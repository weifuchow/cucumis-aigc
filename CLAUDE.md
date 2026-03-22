# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**cucumis-aigc** is a localized AIGC orchestration system for short-form video production. It's not a single model but an integrated workflow that chains script generation, storyboarding, keyframes, image generation, dynamic video, voiceover, subtitles, timeline composition, and rendering into a controllable, traceable, recoverable production pipeline.

**Key Philosophy**: Production capability over generation capability. The system emphasizes orchestration, state management, recovery, auditing, and rendering rather than optimizing individual generation steps.

## Architecture & Design Principles

### Layered Architecture

```
User Intent
  → Workflow Runtime (Codex / Claude Code)
  → Skills (18+ single-responsibility business capability modules)
  → Local Filesystem (JSON files as source of truth)
  → Timeline Schema (audio-driven timing grid)
  → FFmpeg Renderer
  → Final MP4 Output
```

### Core Design Patterns

1. **Audio-First Pipeline**: All timing anchors to audio (voiceover + BGM beat grid)
2. **Single Responsibility Skills**: Each skill handles one specific task; no monolithic modules
3. **File System as Database**: All artifacts stored as JSON files (human-readable, version-controllable, fully debuggable)
4. **Event Sourcing**: Complete change log in `events/events.jsonl` for replay and recovery
5. **Explicit State Management**: Project state stored in `projects/<name>/orchestration/`
6. **Split Timeline Logic**: `global_timeline_initializer` creates audio-driven time grid; `timeline_builder` composes final render timeline

### The 12-Stage Video Pipeline

1. `creative_design` - Intake + standardization
2. `script_writer` - Emotion-tagged script generation
3. `audio_foundation` - Audio timing grid (TTS, BGM selection, beat detection)
4. `global_timeline_initializer` - Global time anchors
5. `beat_sync_storyboard_planner` - Time-constrained storyboards
6. `keyframe_planner` - Visual consistency anchors
7. `prompt_engineer` - Transform storyboards to model prompts
8. `image_generator` - Static image generation
9. `constrained_video_generator` - Dynamic video clips with time/motion constraints
10. `subtitle_asset_manager` - Subtitles + asset manifest
11. `timeline_builder` - Final timeline composition
12. `ffmpeg_renderer_reviewer` - Render to MP4 + quality check

Each stage reads from filesystem, writes to namespace subdirectories, and updates orchestration state.

## Project Structure

```
cucumis-aigc/
├── skills/                    # 18+ skill modules (business capabilities)
│   ├── creative_design/
│   ├── script_writer/
│   ├── audio_foundation/
│   ├── ... (more skills)
├── scripts/                   # 23+ executable Python entry points
│   ├── run_creative_design.py
│   ├── run_script_writer.py
│   ├── run_image_generator.py
│   ├── ... (skill runners)
│   ├── validate_project.py
│   ├── observe_project.py
│   ├── review_project.py
│   └── poe/                   # Poe API integration
│       ├── client.py          # HTTP wrapper (reads .env for POE_API_KEY)
│       ├── media.py           # Image/audio generation helpers
│       ├── usage.py           # Cost tracking
│       └── catalog.py         # Model catalog
├── schemas/                   # 14 JSON Schema files (data contracts)
│   ├── task-input.schema.json
│   ├── script.schema.json
│   ├── audio-foundation.schema.json
│   ├── timeline.schema.json
│   └── ... (more schemas)
├── templates/                 # Project initialization templates
│   ├── project/               # Standard project structure
│   ├── prompts/
│   └── docs/
├── projects/                  # Active project instances
│   └── dragon-fall-35s/        # Example: fully populated project
├── workflows/
│   └── video_pipeline/        # Main workflow definitions
│       ├── state-machine.md   # Workflow states
│       └── handoff-contracts.md
├── tests/                     # Python unittest test suite
├── docs/plans/                # 14+ design & implementation docs
└── examples/                  # Reference examples
```

## Session Start Protocol (MUST FOLLOW)

**Every time you begin working on a project — whether resuming after discussion, starting fresh, or continuing after interruption — you MUST do the following FIRST, before any other action:**

1. Read `projects/<project>/orchestration/task-card.md` if it exists
2. Read `projects/<project>/orchestration/state.json`
3. Output a one-line status: `[Project: <name>] [Stage: <current>] [Next: <action>]`
4. Then proceed with the user's request

**This protocol applies even when the user asks about something unrelated to the pipeline (e.g., debugging, editing prompts). Always anchor yourself to the current stage before acting.**

If `task-card.md` does not exist, create it immediately after reading `state.json`.

---

## Project Directory Structure (Per Project)

Each project in `projects/<project-name>/` follows this structure:

```
README.md                          # Project context
request.md                         # Original customer request
events/events.jsonl               # Immutable event log
orchestration/
  ├── state.json                  # Current workflow state
  ├── plan.json                   # Execution plan
  ├── decisions.jsonl             # Manual intervention decisions
  └── task-card.md                # ⭐ CURRENT TASK CARD — always read first
input/input.json                  # Standardized task input
script/script.json                # Script with emotion markers
audio/
  ├── voiceover.json
  ├── bgm-selection.json
  ├── beat-grid.json
  └── usage.json
storyboard/storyboard.json
keyframes/keyframes.json
prompts/prompts.json
assets/
  ├── manifest.json
  ├── images/
  └── image-usage.json
video/
  ├── clips.json
  └── usage.json
timeline/
  ├── global-timeline.json
  └── timeline.json
outputs/
  ├── render-plan.json
  └── final.mp4
review/
  ├── review-report.json
  └── observer-summary.md
costs/poe-usage.jsonl
```

## Common Development Commands

### Running Skills/Scripts

All skills are executable Python scripts in `scripts/`:

```bash
# Initialize a new project
python scripts/init_project.py --request "Your video brief here"

# Run individual skills (always read project state from filesystem)
python scripts/run_creative_design.py --project dragon-fall-35s
python scripts/run_script_writer.py --project dragon-fall-35s
python scripts/run_image_generator.py --project dragon-fall-35s
python scripts/run_ffmpeg_renderer_reviewer.py --project dragon-fall-35s

# Validation and observation
python scripts/validate_project.py --project dragon-fall-35s
python scripts/observe_project.py --project dragon-fall-35s
python scripts/review_project.py --project dragon-fall-35s
```

### Running Tests

```bash
# Run all tests
python -m pytest tests/

# Run specific test file
python -m pytest tests/test_poe_sdk.py -v

# Run single test
python -m pytest tests/test_poe_sdk.py::TestPoeSdkUsage -v
```

Tests use Python's `unittest` framework and create temporary projects to validate the full pipeline.

### Environment Setup

Create `.env` file with:
```
POE_API_KEY=your-poe-api-key
POE_BASE_URL=https://api.poe.com/v1
```

No `requirements.txt` or `package.json`—project uses Python standard library + system FFmpeg.

### Utilities

```bash
# View available LLM models
python scripts/list_poe_models.py

# Manually write events
python scripts/write_event.py --project <name> --event-type <type>

# Update orchestration state
python scripts/update_orchestration_state.py --project <name>

# Hand off project state between sessions
python scripts/session_handoff.py --project <name>
```

## Key Patterns & Practices

### 1. File-Based State Management

All persistent state goes to local files. No in-memory runtime state. This enables:
- Full project recovery from filesystem
- Human debugging and inspection
- Version control compatibility
- Easy handoff between sessions

### 2. Skill Implementation Pattern

Each skill:
- Reads input from filesystem (`projects/<name>/<stage>/`)
- Reads schemas from `schemas/` to validate contracts
- Reads orchestration state from `orchestration/state.json`
- Writes results to its output namespace
- Appends to `events/events.jsonl`
- Updates `orchestration/state.json`
- Logs costs to `costs/poe-usage.jsonl`

### 3. Handoff Contracts

Each skill has explicit input/output contracts in `workflows/video_pipeline/handoff-contracts.md`. New skills must declare their dependencies—do not create undeclared data dependencies.

### 4. Error Recovery

Failed stages are marked in orchestration state. Projects can resume from specific checkpoints without re-running completed stages. Always validate project state before proceeding.

### 5. Cost Tracking

Per-skill cost logging to `costs/poe-usage.jsonl` for budget visibility. Aggregate costs with `scripts/usage_audit.py`.

## Testing & Validation

### Project Validation

```bash
python scripts/validate_project.py --project <name>
```

Checks:
- All required directories exist
- Required JSON files present and valid per schema
- Project structure completeness
- Returns detailed error messages

### Quality Review

```bash
python scripts/review_project.py --project <name>
```

Automated structured review of 18 distinct artifact types.

### Observation

```bash
python scripts/observe_project.py --project <name>
```

Generates human-readable project status, tracking completed/skipped/failed stages.

## Important Notes for Future Work

### When Adding New Skills

1. Define input/output JSON schemas in `schemas/`
2. Update `workflows/video_pipeline/handoff-contracts.md`
3. Create skill module in `skills/`
4. Create runner script `scripts/run_<skill_name>.py`
5. Add corresponding `agents/openai.yaml` for Codex/Claude Code integration
6. Add test coverage in `tests/`

### When Modifying Pipeline Flow

- Update `workflows/video_pipeline/state-machine.md` with new states
- Document stage ordering and dependencies
- Ensure backward compatibility with existing project directories
- Test with existing projects (e.g., `dragon-fall-35s`)

### Debugging Projects

1. Check `projects/<name>/events/events.jsonl` for full event trace
2. Check `orchestration/state.json` for current stage
3. Check `orchestration/decisions.jsonl` for manual interventions
4. Inspect JSON files in each stage namespace (they're human-readable)
5. Run `observe_project.py` for high-level status

### Schema Validation

All JSON files should validate against their schemas. When adding new data structures:
1. Create schema in `schemas/`
2. Reference schema in skill implementations
3. Validate before writing with `jsonschema` library

## FFmpeg Rendering

`ffmpeg_renderer_reviewer` consumes timeline schema and outputs MP4. Key files:
- `timeline/timeline.json` - Final render instructions
- `scripts/run_ffmpeg_renderer_reviewer.py` - Renderer implementation
- `outputs/final.mp4` - Final video output

FFmpeg command construction is abstracted in skill implementations. Do not construct raw FFmpeg commands outside this boundary.

## Project ID Generation

Format: `{prefix}-{YYYYMMDD-HHMMSS}-{random_hex}`
Example: `proj-20260314-104400-a1b2c3`

Generated by `init_project.py` for uniqueness and temporal tracking.

## Design Philosophy

- **Do not premature abstract**: Three similar lines are better than one-off utility functions
- **Separate concerns strictly**: Skills are single-responsibility; orchestration is separate from execution
- **Make state explicit**: All decisions and transitions recorded in filesystem
- **Enable auditability**: Full event traces and cost logs for all operations
- **Prefer local execution**: Minimize external platform dependencies for reliability
- **Design for resumption**: Any stage can fail and resume without data loss
