# Project Workbench Redesign

**Date:** 2026-03-31

**Goal**

Replace the current stage-oriented project detail page with a workbench-oriented entry that is easier for non-operator users to understand while keeping the internal filesystem-backed workflow unchanged.

## Problem

The current web detail page is shaped around internal workflow mechanics:

- fixed stage timeline
- direct stage action buttons
- raw artifact path list
- operator-style agent panel

This makes the page useful for internal debugging, but not as a stable product entry for external users. The workflow itself is expected to evolve, especially in form fields, confirmation points, and artifact display rules, so the UI needs a more stable abstraction.

## Chosen Direction

Adopt a `workbench` model for project detail.

The detail page should be organized around four stable user-facing concerns:

- task configuration
- progress summary
- artifact results
- pending actions

Internal workflow stages remain available, but move into a lower-priority technical details area.

## Architecture

### 1. Workflow UI Config

Add a workflow-specific UI config file under `workflows/video_pipeline/ui.json`.

This config defines:

- editable business fields for the task configuration area
- artifact sections to display in the result area
- pending action rules
- user-facing copy for status summaries

This is not a workflow executor. It is only a UI contract.

### 2. Workbench Projector

Add a server-side projector in `apps/web/lib/workbench/`.

The projector reads:

- existing project state from `orchestration/`
- review information
- important artifact files
- workflow UI config

It produces a stable `WorkbenchPageModel` for the frontend.

### 3. Workbench Components

Replace the current detail-page shell with a workbench shell composed of:

- header / progress overview
- config panel
- artifact result sections
- pending actions
- technical details

The technical details section keeps internal workflow controls and diagnostics available without making them the main product surface.

### 4. Controlled Config Editing

The first version allows editing a limited set of business inputs sourced from `input/input.json`.

Editable fields are controlled by the workflow UI config and must include:

- field type
- display label
- source JSON path
- visibility rules
- editability rules

The frontend does not hardcode these fields.

## Product Shape

### Main View

The project detail page should render these sections in priority order:

1. header with user-facing status
2. task configuration
3. artifact results
4. pending actions
5. technical details

### Artifact Results

Artifacts are grouped by result type rather than by internal stage.

The first version should surface at least:

- image results
- text results
- audio results
- video results

Each result group should show:

- count
- availability state
- a small preview set when possible
- links to full previews

### Pending Actions

The page should present business actions such as:

- continue workflow
- refresh diagnostics
- confirm current results and continue

The page should avoid showing internal stage buttons as the primary interaction model.

## File-Level Changes

### New

- `schemas/workflow-ui.schema.json`
- `workflows/video_pipeline/ui.json`
- `apps/web/lib/workbench/types.ts`
- `apps/web/lib/workbench/workflow-ui.ts`
- `apps/web/lib/workbench/artifact-registry.ts`
- `apps/web/lib/workbench/projector.ts`
- `apps/web/components/project-workbench-shell.tsx`

### Modified

- `apps/web/app/projects/[projectId]/page.tsx`
- `apps/web/app/api/projects/[projectId]/route.ts`
- `apps/web/app/api/projects/[projectId]/stream/route.ts`
- `apps/web/app/api/projects/[projectId]/agent/run/route.ts`
- `apps/web/app/globals.css`
- `apps/web/lib/projects/artifacts.ts`

## Non-Goals

- visual workflow editor
- arbitrary JSON editing
- multi-workflow template browser
- replacing the Python execution boundary
- removing technical/operator visibility entirely

## Success Criteria

The redesign is successful when:

1. a non-operator user can understand the current task from the first screen
2. images and other artifacts are visible as grouped results rather than raw file paths
3. limited business parameters can be edited from the page
4. the page no longer depends on stage names as its main structure
5. changing UI fields or artifact grouping primarily requires config/projector changes instead of page rewrites
