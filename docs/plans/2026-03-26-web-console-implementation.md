# Web Console Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a first version of the Cucumis web console with a Next.js UI, a filesystem-backed project store, safe stage execution adapters, and a minimal Claude Agent SDK project agent.

**Architecture:** Add a new `apps/web` Next.js app inside the existing repo. Keep all durable workflow state in `projects/<project>/` and call existing Python scripts through a typed server-side adapter. The web server owns the read models, APIs, SSE stream, and Agent SDK integration.

**Tech Stack:** Next.js, React, TypeScript, Claude Agent SDK for TypeScript, Node.js child process APIs, existing Python scripts

---

### Task 1: Scaffold The Web App

**Files:**
- Create: `apps/web/package.json`
- Create: `apps/web/tsconfig.json`
- Create: `apps/web/next.config.ts`
- Create: `apps/web/next-env.d.ts`
- Create: `apps/web/app/layout.tsx`
- Create: `apps/web/app/page.tsx`
- Create: `apps/web/app/globals.css`
- Create: `apps/web/.gitignore`

**Step 1: Write the failing test**

No automated test first for scaffold. Validation is a build check.

**Step 2: Run test to verify it fails**

Run: `cd apps/web && npm run build`
Expected: FAIL because the app files do not exist yet.

**Step 3: Write minimal implementation**

Create the Next.js app scaffold with a root layout, global styles, and a root page that redirects or links to the projects UI.

**Step 4: Run test to verify it passes**

Run: `cd apps/web && npm install && npm run build`
Expected: PASS

**Step 5: Commit**

```bash
git add apps/web
git commit -m "feat: scaffold web console app"
```

### Task 2: Build Filesystem Project Store

**Files:**
- Create: `apps/web/lib/projects/types.ts`
- Create: `apps/web/lib/projects/store.ts`
- Create: `apps/web/lib/projects/artifacts.ts`
- Test: `apps/web/lib/projects/store.test.ts`

**Step 1: Write the failing test**

```ts
import { describe, expect, it } from "vitest";
import { listProjects } from "./store";

describe("listProjects", () => {
  it("returns project summaries from workspace files", async () => {
    const projects = await listProjects();
    expect(Array.isArray(projects)).toBe(true);
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd apps/web && npm run test -- store.test.ts`
Expected: FAIL because the store module is missing.

**Step 3: Write minimal implementation**

Read `projects/*`, parse `state.json`, `review-report.json`, and event tails, then return stable DTOs for the UI.

**Step 4: Run test to verify it passes**

Run: `cd apps/web && npm run test -- store.test.ts`
Expected: PASS

**Step 5: Commit**

```bash
git add apps/web/lib/projects
git commit -m "feat: add filesystem project store"
```

### Task 3: Add Stage Runner Adapters

**Files:**
- Create: `apps/web/lib/stages/contracts.ts`
- Create: `apps/web/lib/stages/runner.ts`
- Test: `apps/web/lib/stages/runner.test.ts`

**Step 1: Write the failing test**

```ts
import { describe, expect, it } from "vitest";
import { resolveStageScript } from "./runner";

describe("resolveStageScript", () => {
  it("maps known stages to Python script paths", () => {
    expect(resolveStageScript("creative_design")).toContain("run_creative_design.py");
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd apps/web && npm run test -- runner.test.ts`
Expected: FAIL because the runner module is missing.

**Step 3: Write minimal implementation**

Implement stage name validation, script mapping, child-process execution, timeout handling, and output capture.

**Step 4: Run test to verify it passes**

Run: `cd apps/web && npm run test -- runner.test.ts`
Expected: PASS

**Step 5: Commit**

```bash
git add apps/web/lib/stages
git commit -m "feat: add safe stage runner"
```

### Task 4: Build Read APIs

**Files:**
- Create: `apps/web/app/api/projects/route.ts`
- Create: `apps/web/app/api/projects/[projectId]/route.ts`
- Create: `apps/web/app/api/projects/[projectId]/events/route.ts`
- Create: `apps/web/app/api/projects/[projectId]/review/route.ts`
- Create: `apps/web/app/api/projects/[projectId]/artifacts/route.ts`
- Test: `apps/web/app/api/projects/projects-api.test.ts`

**Step 1: Write the failing test**

Write route tests that assert the handlers return JSON payloads for list, detail, events, review, and artifact reads.

**Step 2: Run test to verify it fails**

Run: `cd apps/web && npm run test -- projects-api.test.ts`
Expected: FAIL because the routes are missing.

**Step 3: Write minimal implementation**

Connect route handlers to the project store and artifact readers with project path validation.

**Step 4: Run test to verify it passes**

Run: `cd apps/web && npm run test -- projects-api.test.ts`
Expected: PASS

**Step 5: Commit**

```bash
git add apps/web/app/api
git commit -m "feat: add project read APIs"
```

### Task 5: Build Core UI Pages

**Files:**
- Create: `apps/web/app/projects/page.tsx`
- Create: `apps/web/app/projects/new/page.tsx`
- Create: `apps/web/app/projects/[projectId]/page.tsx`
- Create: `apps/web/components/project-list.tsx`
- Create: `apps/web/components/project-detail.tsx`
- Create: `apps/web/components/new-project-form.tsx`
- Create: `apps/web/components/stage-timeline.tsx`

**Step 1: Write the failing test**

Write component tests asserting that project summaries and detail sections render expected labels from mock props.

**Step 2: Run test to verify it fails**

Run: `cd apps/web && npm run test -- project-list.test.tsx project-detail.test.tsx`
Expected: FAIL because the pages and components are missing.

**Step 3: Write minimal implementation**

Render list, create, and detail pages backed by the new server utilities.

**Step 4: Run test to verify it passes**

Run: `cd apps/web && npm run test -- project-list.test.tsx project-detail.test.tsx`
Expected: PASS

**Step 5: Commit**

```bash
git add apps/web/app apps/web/components
git commit -m "feat: add core project console pages"
```

### Task 6: Add Project Actions And SSE

**Files:**
- Create: `apps/web/app/api/projects/[projectId]/agent/run/route.ts`
- Create: `apps/web/app/api/projects/[projectId]/agent/review/route.ts`
- Create: `apps/web/app/api/projects/[projectId]/stream/route.ts`
- Create: `apps/web/lib/events/stream.ts`
- Create: `apps/web/components/live-project-shell.tsx`

**Step 1: Write the failing test**

Write tests that assert the action handlers validate inputs and that the event stream emits structured events.

**Step 2: Run test to verify it fails**

Run: `cd apps/web && npm run test -- stream.test.ts`
Expected: FAIL because the handlers and stream helpers are missing.

**Step 3: Write minimal implementation**

Support running a stage, refreshing review data, and opening an SSE stream that polls project files and emits changes.

**Step 4: Run test to verify it passes**

Run: `cd apps/web && npm run test -- stream.test.ts`
Expected: PASS

**Step 5: Commit**

```bash
git add apps/web/app/api/projects apps/web/lib/events apps/web/components/live-project-shell.tsx
git commit -m "feat: add project actions and live updates"
```

### Task 7: Integrate Claude Agent SDK

**Files:**
- Create: `apps/web/lib/agent/prompt.ts`
- Create: `apps/web/lib/agent/tools.ts`
- Create: `apps/web/lib/agent/session.ts`
- Create: `apps/web/app/api/projects/[projectId]/agent/message/route.ts`
- Create: `apps/web/app/api/projects/[projectId]/agent/confirm/route.ts`
- Test: `apps/web/lib/agent/session.test.ts`

**Step 1: Write the failing test**

Write tests for prompt construction and tool definitions, using mocks for the SDK query flow.

**Step 2: Run test to verify it fails**

Run: `cd apps/web && npm run test -- session.test.ts`
Expected: FAIL because the agent modules are missing.

**Step 3: Write minimal implementation**

Create a minimal project agent that can explain current state, recommend next steps, invoke `run_stage`, and record user confirmations.

**Step 4: Run test to verify it passes**

Run: `cd apps/web && npm run test -- session.test.ts`
Expected: PASS

**Step 5: Commit**

```bash
git add apps/web/lib/agent apps/web/app/api/projects
git commit -m "feat: add project agent integration"
```

### Task 8: Verify End-To-End And Document Usage

**Files:**
- Modify: `README.md`
- Create: `apps/web/README.md`

**Step 1: Write the failing test**

No new test. Final verification is build and targeted tests.

**Step 2: Run test to verify it fails**

Run: `cd apps/web && npm run build`
Expected: FAIL if any route, import, or type issue remains.

**Step 3: Write minimal implementation**

Document how to install dependencies, configure environment variables, and run the web console.

**Step 4: Run test to verify it passes**

Run:

```bash
cd apps/web && npm run test
cd apps/web && npm run build
```

Expected: PASS

**Step 5: Commit**

```bash
git add README.md apps/web/README.md
git commit -m "docs: add web console usage guide"
```
