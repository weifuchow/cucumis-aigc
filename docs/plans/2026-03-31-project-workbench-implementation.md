# Project Workbench Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a config-driven workbench view for project detail pages so external users see task configuration, grouped artifacts, and pending actions instead of internal workflow mechanics.

**Architecture:** Keep the existing filesystem-backed workflow runtime and stage runner intact. Add a workflow UI config plus a server-side workbench projector, then replace the project detail page shell to render the projected model while retaining technical controls in a lower-priority section.

**Tech Stack:** Next.js App Router, TypeScript, server-side filesystem reads, existing project APIs, existing Python stage adapters

---

### Task 1: Add Workflow UI Config

**Files:**
- Create: `schemas/workflow-ui.schema.json`
- Create: `workflows/video_pipeline/ui.json`

**Step 1: Write the failing test**

Document the expected config shape in the schema:

- form sections with field definitions
- artifact sections
- pending actions

**Step 2: Run validation to verify it fails**

Run: `node -e "JSON.parse(require('fs').readFileSync('workflows/video_pipeline/ui.json','utf8'))"`

Expected: FAIL because the file does not exist yet.

**Step 3: Write minimal implementation**

Create a workflow UI config for:

- business input fields from `input/input.json`
- artifact sections for image/text/audio/video results
- pending actions for continue, review, and confirm

**Step 4: Run validation to verify it passes**

Run: `node -e "JSON.parse(require('fs').readFileSync('workflows/video_pipeline/ui.json','utf8')); console.log('ok')"`

Expected: `ok`

**Step 5: Commit**

```bash
git add schemas/workflow-ui.schema.json workflows/video_pipeline/ui.json
git commit -m "feat: add workflow ui config"
```

### Task 2: Add Workbench Types And Projector

**Files:**
- Create: `apps/web/lib/workbench/types.ts`
- Create: `apps/web/lib/workbench/workflow-ui.ts`
- Create: `apps/web/lib/workbench/artifact-registry.ts`
- Create: `apps/web/lib/workbench/projector.ts`
- Modify: `apps/web/lib/projects/artifacts.ts`

**Step 1: Write the failing test**

Define the expected projected model:

- header
- config sections
- artifact sections
- pending actions
- technical details

**Step 2: Run typecheck to verify it fails**

Run: `cd apps/web && npm run typecheck`

Expected: FAIL because the workbench modules do not exist.

**Step 3: Write minimal implementation**

Implement:

- workflow UI loader
- artifact grouping registry
- projector that reads project detail + `input/input.json` + workflow UI config
- helper functions for artifact hrefs and artifact kind detection

**Step 4: Run typecheck to verify it passes**

Run: `cd apps/web && npm run typecheck`

Expected: PASS

**Step 5: Commit**

```bash
git add apps/web/lib/workbench apps/web/lib/projects/artifacts.ts
git commit -m "feat: add workbench projector"
```

### Task 3: Replace The Project Detail Shell

**Files:**
- Create: `apps/web/components/project-workbench-shell.tsx`
- Modify: `apps/web/app/projects/[projectId]/page.tsx`
- Modify: `apps/web/app/globals.css`

**Step 1: Write the failing test**

Describe the expected rendered sections:

- task configuration
- artifact results
- pending actions
- technical details

**Step 2: Run the app to verify it is missing**

Run: `cd apps/web && npm run dev`

Expected: current page still renders stage timeline / project agent / raw artifact list as the main structure.

**Step 3: Write minimal implementation**

Create a new client shell that:

- consumes the projected workbench model
- supports config editing
- renders grouped artifacts with previews
- renders pending actions
- keeps agent/stage diagnostics inside technical details

**Step 4: Run the app to verify it passes**

Run: `cd apps/web && npm run dev`

Expected: project detail page uses the workbench layout.

**Step 5: Commit**

```bash
git add apps/web/components/project-workbench-shell.tsx apps/web/app/projects/[projectId]/page.tsx apps/web/app/globals.css
git commit -m "feat: redesign project detail as workbench"
```

### Task 4: Update Project APIs For Workbench Refresh

**Files:**
- Modify: `apps/web/app/api/projects/[projectId]/route.ts`
- Modify: `apps/web/app/api/projects/[projectId]/stream/route.ts`
- Create: `apps/web/app/api/projects/[projectId]/config/route.ts`
- Modify: `apps/web/app/api/projects/[projectId]/agent/run/route.ts`

**Step 1: Write the failing test**

Define the expected API payload:

- `project`
- `workbench`

and the expected config-update API contract.

**Step 2: Run typecheck to verify it fails**

Run: `cd apps/web && npm run typecheck`

Expected: FAIL until the workbench payloads and config route are wired in.

**Step 3: Write minimal implementation**

Implement:

- GET detail route returning both raw project detail and projected workbench
- SSE stream returning the same snapshot shape
- config update route writing allowed fields back to `input/input.json`
- action route support for a generic `continue_workflow` action payload

**Step 4: Run typecheck to verify it passes**

Run: `cd apps/web && npm run typecheck`

Expected: PASS

**Step 5: Commit**

```bash
git add apps/web/app/api/projects/[projectId]
git commit -m "feat: wire workbench detail apis"
```

### Task 5: Verify With Local Smoke Checks

**Files:**
- Modify: none required unless fixes are needed

**Step 1: Run typecheck**

Run: `cd apps/web && npm run typecheck`

Expected: PASS

**Step 2: Start the web app**

Run: `cd apps/web && npm run dev`

Expected: local dev server starts on `http://localhost:3000`

**Step 3: Smoke-check the workbench page**

Run:

```bash
curl -I http://localhost:3000/projects
curl -I http://localhost:3000/projects/test
```

Expected: `200 OK` for both routes.

**Step 4: Record any follow-up gaps**

Note any missing artifact previews or workflow-state edge cases that need another iteration.

**Step 5: Commit**

```bash
git add .
git commit -m "chore: verify workbench redesign"
```
