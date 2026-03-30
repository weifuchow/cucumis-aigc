# Cucumis Web Console Design

**Date:** 2026-03-26

**Goal**

Build a first-party web control plane for `cucumis-aigc` that keeps the existing filesystem-first video pipeline intact while adding a browser UI, a TypeScript orchestration layer, and Claude Agent SDK powered project agents.

## Chosen Approach

Adopt a hybrid architecture:

- `Next.js + TypeScript` for the web UI and server routes
- `Claude Agent SDK (TypeScript)` for project-level orchestration
- Existing Python stage scripts as the stable execution boundary
- Existing `projects/<project>/` directories as the source of truth

This avoids an early rewrite of the pipeline while still making the system operable as a web product.

## Architecture

The system is split into four layers.

### 1. Web UI

`apps/web` provides:

- project list
- project creation
- project detail with stage timeline
- artifact preview
- project agent chat and action panel

The UI never executes shell commands directly and does not implement its own workflow logic.

### 2. Agent Runtime

The server-side TypeScript layer hosts a Claude Agent SDK agent per project session. The agent is responsible for:

- reading current project state
- explaining current progress and blockers
- deciding the next valid action
- requesting user confirmations at workflow checkpoints
- invoking approved execution tools

The agent does not receive arbitrary shell access. It only receives a constrained tool surface.

### 3. Execution Adapter

The web server exposes a typed adapter that maps safe server actions to the existing Python scripts. First version targets:

- `init_project.py`
- `run_creative_design.py`
- `run_script_writer.py`
- `run_audio_foundation.py`
- `run_beat_sync_storyboard_planner.py`
- `review_project.py`
- `observe_project.py`
- `session_handoff.py`

Later stages can be added without changing the UI or agent contract.

### 4. Project Workspace

Each project remains rooted in `projects/<project>/`. All durable state, artifacts, logs, and review data are read from or written to this structure. The web app is a view/controller over this workspace model.

## Product Shape

Version 1 focuses on an operator console rather than a pure freeform chat interface.

### Core pages

- Project list page
- Project creation page
- Project detail page
- Artifact preview drawer/page

### Project detail layout

- Header with project metadata and state
- Stage timeline
- Agent panel
- Artifact preview panel
- Event log stream

## State Model

The application derives state from existing project files:

- `orchestration/state.json`
- `orchestration/plan.json`
- `orchestration/task-card.md`
- `orchestration/decisions.jsonl`
- `events/events.jsonl`
- `review/review-report.json`

No database is required for version 1. The web app should not create a second workflow state store.

## Checkpoint Model

The UI must productize manual confirmations already present in the workflow. Project runtime state is normalized into:

- `running`
- `waiting_for_confirmation`
- `blocked`
- `failed`
- `completed`

Expected checkpoint types include:

- concept selection
- beat confirmation
- prompt confirmation
- image batch confirmation

The server records user decisions into project files before allowing the agent to continue.

## API Shape

### Read APIs

- `GET /api/projects`
- `GET /api/projects/:id`
- `GET /api/projects/:id/events`
- `GET /api/projects/:id/review`
- `GET /api/projects/:id/artifacts`

### Action APIs

- `POST /api/projects`
- `POST /api/projects/:id/agent/message`
- `POST /api/projects/:id/agent/run`
- `POST /api/projects/:id/agent/confirm`
- `POST /api/projects/:id/agent/review`

### Streaming API

- `GET /api/projects/:id/stream`

Server-Sent Events are sufficient for version 1 because the primary need is one-way status and log streaming.

## Claude Agent SDK Integration

The project agent runs in the server layer and gets a constrained toolset. The first tool surface should include:

- `get_project_state`
- `get_project_artifact`
- `list_project_artifacts`
- `run_stage`
- `run_review`
- `generate_handoff`
- `append_user_decision`
- `get_stage_contract`

Agent sessions should default to SDK-managed settings rather than inheriting user-local filesystem settings. Project instructions can be loaded deliberately later if needed.

## First Release Scope

### Included

- `apps/web` Next.js application
- project list/detail/create flows
- safe project store for reading workspace state
- stage runner for calling Python scripts
- basic project agent for status explanation and next-step execution
- SSE updates
- artifact preview for JSON, Markdown, image, and video
- review and observer views

### Excluded

- multi-user auth
- online editors for prompts/storyboards
- arbitrary shell access
- queue workers and distributed execution
- full TypeScript rewrite of stages

## Risks And Mitigations

### Risk: mixed TypeScript and Python orchestration becomes inconsistent

Mitigation:

- keep Python stage scripts as pure execution boundary
- keep workflow source of truth in project files
- centralize cross-language mapping in one `stage-runner` layer

### Risk: agent becomes an uncontrolled shell wrapper

Mitigation:

- expose only typed tools
- validate stage names and project paths server-side
- disallow arbitrary command execution from the agent

### Risk: UI state drifts from filesystem state

Mitigation:

- derive read models from files on demand
- use SSE to invalidate and refresh views
- avoid introducing a database in v1

## Success Criteria

The design is successful when a user can:

1. create a project from the browser
2. inspect project state and artifacts in the browser
3. ask a project agent what to do next
4. trigger stage execution safely from the browser
5. handle manual confirmation checkpoints from the browser
6. recover from blocked or failed states without leaving the web console
