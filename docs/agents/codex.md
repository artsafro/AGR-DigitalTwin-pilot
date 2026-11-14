# Codex
For NPM/OKS tasks read `routes/npm-oks.md`; call `agr --help` before writing a script.
For Revit-source tasks read `routes/revit-intake.md` (read-only intake first, [D237]).

Role and default ownership: `docs/agents/ROLES.md`.

- Project config: `.codex/config.toml` (MCP routes, machine-specific absolute paths) and
  `.codex/hooks.json` (PreToolUse → `.claude/hooks/guard.py`; status in `docs/agents/harness-inventory.md`).
- User-level process skills `codex-work-route|loop|engineering|review`
  (`~/.agents/skills/`) apply on top of `docs/agents/WORKFLOW.md`; the project workflow wins
  where they differ.
- A new worktree with a random branch (`codex/<words>-<hex6>` or `<word>-<word>-<hex6>`): rename it before the
  first commit by `docs/agents/NAMING.md`, "Branches" (propose the name in your first reply).
- Environment and checks: `docs/agents/agents-reference.md`.
- Before turning a job script into an adapter, read its accepted case and keep its checks
  as regression tests; Claude confirms on real DCC data.
- Translating `docs/agr/` and Russian code comments to English is backlog work; do not mix
  it into unrelated changes.
