# Cucumis Web Console

Web control plane for `cucumis-aigc`.

## What it does

- lists local projects from `../../projects`
- shows current workflow state, review data, task card, and event tail
- creates new projects by calling `../../scripts/init_project.py`
- runs selected Python workflow stages through server-side adapters
- exposes a minimal Claude Agent SDK project agent with custom MCP tools
- can load project-level Claude skills from `../../.claude/skills` after skill shortcut sync
- streams live project snapshots with SSE

## Run

1. Install dependencies:

```bash
cd apps/web
npm install
```

2. Start the dev server:

```bash
npm run dev
```

3. Open `http://localhost:3000/projects`

## Skill Shortcut Sync

This repo keeps its skills in `skills/`. To expose the same skill set to both Claude Agent SDK and Codex, run:

```bash
python3 scripts/sync_agent_skill_shortcuts.py
```

This creates:

- `.claude/skills -> skills`
- `~/.agents/skills/cucumis-aigc -> <repo>/skills`

After creating the Codex link, restart any existing Codex session so it can re-scan skills.

## Notes

- This app assumes it lives inside the repository at `apps/web`.
- Durable workflow state still lives in `projects/<project>/`.
- The Claude Agent SDK route requires Claude Agent SDK credentials/runtime to be available in the environment used by the Next.js server.
