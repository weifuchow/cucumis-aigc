# Reviewer Observer Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add the first `reviewer / observer` layer with a structured review report, a human-readable observer summary, and helper scripts to generate both.

**Architecture:** The implementation upgrades `reviewer` and `observer` from placeholders to formal skills, adds a shared `review-report` schema, extends project templates with review artifacts, and introduces two Python scripts: one for project review and one for summary generation. The first iteration stays filesystem-first and report-oriented, without introducing UI or subjective quality scoring.

**Tech Stack:** Markdown, JSON Schema, Python 3 scripts, filesystem-based reports

---

### Task 1: Upgrade `reviewer` and `observer` skill definitions

**Files:**
- Modify: `skills/reviewer/SKILL.md`
- Modify: `skills/observer/SKILL.md`

**Step 1: Rewrite `reviewer`**

Document the review scope, reads, writes, status model, and first-iteration rule layers in `skills/reviewer/SKILL.md`.

**Step 2: Rewrite `observer`**

Document the observer summary purpose, reads, writes, and summary structure in `skills/observer/SKILL.md`.

**Step 3: Verify both skill files**

Run: `sed -n '1,220p' skills/reviewer/SKILL.md && printf '\n---\n' && sed -n '1,220p' skills/observer/SKILL.md`
Expected: Both files clearly define their first-iteration roles and outputs under `review/`.

**Step 4: Commit**

```bash
git add skills/reviewer/SKILL.md skills/observer/SKILL.md
git commit -m "docs: define reviewer and observer skills"
```

### Task 2: Add review report schema and extend project structure contract

**Files:**
- Create: `schemas/review-report.schema.json`
- Modify: `schemas/project-structure.md`

**Step 1: Write the review report schema**

Define the first-iteration report shape with fields for project, status, timestamps, completed stages, missing artifacts, warnings, and next action.

**Step 2: Update project structure contract**

Add `review/review-report.json` and `review/observer-summary.md` to the project structure contract.

**Step 3: Verify schema parses**

Run: `python3 - <<'PY'\nimport json\nprint(json.loads(open('schemas/review-report.schema.json', encoding='utf-8').read())['title'])\nPY`
Expected: Prints the schema title and exits successfully.

**Step 4: Commit**

```bash
git add schemas/review-report.schema.json schemas/project-structure.md
git commit -m "docs: add review report schema"
```

### Task 3: Extend project templates with review artifacts

**Files:**
- Create: `templates/project/review/review-report.json`
- Create: `templates/project/review/observer-summary.md`

**Step 1: Add starter review files**

Create minimal placeholder files representing the expected review outputs.

**Step 2: Verify template files exist**

Run: `find templates/project/review -maxdepth 2 -type f | sort`
Expected: Both review template files exist.

**Step 3: Commit**

```bash
git add templates/project/review
git commit -m "chore: add review project template files"
```

### Task 4: Write tests for review and observation scripts

**Files:**
- Create: `tests/test_review_observer_scripts.py`

**Step 1: Write a failing test for `review_project.py`**

Create a test that builds a minimal project directory and expects `review_project.py` to write a valid `review-report.json`.

**Step 2: Write a failing test for `observe_project.py`**

Create a test that reads an existing project and review report and expects `observe_project.py` to write a readable `observer-summary.md`.

**Step 3: Run the test file**

Run: `python3 -m unittest tests/test_review_observer_scripts.py -v`
Expected: FAIL because the new scripts do not exist yet.

**Step 4: Commit**

Skip commit until implementation exists.

### Task 5: Implement `review_project.py`

**Files:**
- Create: `scripts/review_project.py`
- Modify: `tests/test_review_observer_scripts.py`

**Step 1: Write the minimal reviewer implementation**

Implement a CLI that inspects project state, checks structure and state consistency, derives a `ready / in_progress / blocked` status, and writes `review/review-report.json`.

**Step 2: Run the review script tests**

Run: `python3 -m unittest tests/test_review_observer_scripts.py -v`
Expected: The review-related tests pass.

**Step 3: Avoid subjective review logic**

Do not add content-quality scoring or creative judgment beyond the approved rules.

**Step 4: Commit**

```bash
git add scripts/review_project.py tests/test_review_observer_scripts.py
git commit -m "feat: add project review script"
```

### Task 6: Implement `observe_project.py`

**Files:**
- Create: `scripts/observe_project.py`
- Modify: `tests/test_review_observer_scripts.py`

**Step 1: Write the minimal observer implementation**

Implement a CLI that reads project state, recent decisions, and the latest review report, then writes `review/observer-summary.md`.

**Step 2: Run the observer script tests**

Run: `python3 -m unittest tests/test_review_observer_scripts.py -v`
Expected: All review/observer script tests pass.

**Step 3: Keep the summary stable and readable**

Generate deterministic Markdown sections matching the approved summary structure.

**Step 4: Commit**

```bash
git add scripts/observe_project.py tests/test_review_observer_scripts.py
git commit -m "feat: add project observer summary script"
```

### Task 7: Align validation and initialization with review artifacts

**Files:**
- Modify: `scripts/init_project.py`
- Modify: `scripts/validate_project.py`
- Modify: `tests/test_workspace_scripts.py`

**Step 1: Add a failing workspace test if needed**

Update workspace tests so initialized projects are expected to include the review template files.

**Step 2: Run the workspace tests to verify failure**

Run: `python3 -m unittest tests/test_workspace_scripts.py -v`
Expected: FAIL if the initialization and validation scripts are not yet aligned.

**Step 3: Update workspace scripts minimally**

Ensure initialized projects include `review/`, and validation checks the review files exist.

**Step 4: Re-run the workspace tests**

Run: `python3 -m unittest tests/test_workspace_scripts.py -v`
Expected: All workspace script tests pass.

**Step 5: Commit**

```bash
git add scripts/init_project.py scripts/validate_project.py tests/test_workspace_scripts.py
git commit -m "feat: align workspace scripts with review artifacts"
```

### Task 8: Final verification

**Files:**
- Modify: `scripts/`
- Modify: `skills/`
- Modify: `schemas/`
- Modify: `templates/project/`

**Step 1: Run all script-related tests**

Run:

```bash
python3 -m unittest tests/test_workspace_scripts.py -v
python3 -m unittest tests/test_orchestration_scripts.py -v
python3 -m unittest tests/test_review_observer_scripts.py -v
```

Expected: all tests pass.

**Step 2: Run a review/observer smoke test**

Run:

```bash
name="review-demo-$(date +%s)"
python3 scripts/init_project.py --project-name "$name"
python3 scripts/review_project.py --project "projects/$name"
python3 scripts/observe_project.py --project "projects/$name"
python3 scripts/validate_project.py --project "projects/$name"
```

Expected: review and observer files are generated and validation succeeds.

**Step 3: Verify Git state**

Run: `git status --short`
Expected: clean working tree after the final commit.

**Step 4: Commit**

Skip if no new changes remain.
