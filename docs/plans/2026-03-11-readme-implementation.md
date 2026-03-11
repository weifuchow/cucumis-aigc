# README Rewrite Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rewrite `README.md` into an internal-facing project overview that clarifies positioning, architecture, workflow, v1 scope, and roadmap.

**Architecture:** This is a docs-only change. The implementation rewrites the README around the approved structure: positioning, problem statement, goals, architecture, workflow, principles, scope boundaries, roadmap, and long-term value. Content must stay aligned with the repository's current conceptual state and avoid implying code already exists.

**Tech Stack:** Markdown

---

### Task 1: Capture approved design

**Files:**
- Create: `docs/plans/2026-03-11-readme-design.md`

**Step 1: Write the design document**

Record the approved audience, structure, writing direction, and scope constraints in `docs/plans/2026-03-11-readme-design.md`.

**Step 2: Verify the design document exists**

Run: `sed -n '1,220p' docs/plans/2026-03-11-readme-design.md`
Expected: The file renders the agreed README structure and constraints.

**Step 3: Commit**

Skip commit if `.git` is missing in the workspace.

### Task 2: Rewrite README structure

**Files:**
- Modify: `README.md`

**Step 1: Replace the current README outline**

Rewrite the file so the sections appear in this order:

- 项目定位
- 为什么要做
- 项目目标
- 核心架构
- 视频生产流程
- 核心设计原则
- v1 边界
- 路线图
- 长期价值

**Step 2: Keep technical density high without inventing implementation**

Ensure the README explains the roles of `Orchestrator`、`Skill`、`Filesystem`、`Timeline Schema`、`FFmpeg`、`Observer`, and clearly marks planned structures as “规划” or “目标形态” when needed.

**Step 3: Verify the content renders cleanly**

Run: `sed -n '1,260p' README.md`
Expected: The top half of the README shows the new structure and internal-facing narrative.

**Step 4: Commit**

Skip commit if `.git` is missing in the workspace.

### Task 3: Verify final document quality

**Files:**
- Modify: `README.md`

**Step 1: Check key headings**

Run: `rg '^## ' README.md`
Expected: All target top-level sections are present exactly once.

**Step 2: Check for misleading implementation claims**

Run: `rg '系统目录结构|app/|skills/' README.md`
Expected: Any such content is explicitly marked as planned structure rather than current repository reality.

**Step 3: Final read-through**

Run: `sed -n '1,320p' README.md`
Expected: The README reads as a coherent internal project overview and roadmap document.

**Step 4: Commit**

Skip commit if `.git` is missing in the workspace.
