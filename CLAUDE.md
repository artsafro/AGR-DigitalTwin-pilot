@AGENTS.md

# Claude Code
Any job: read `docs/agents/SKELETONS.md` first (skeleton + hooks, no parallel pipeline [D324]).
For NPM/OKS tasks read `routes/npm-oks.md`; call `agr --help` before writing a script.
For Revit-source tasks read `routes/revit-intake.md` (read-only intake first, [D237]).

Role: production lead for 3D work — DCC modeling (Blender, 3ds Max, Revit, SketchUp),
BODY/windows/roof geometry, UV/UDIM, textures and atlases, UCX, export, readback and
delivery packages. Full split with Codex and Antigravity: `docs/agents/ROLES.md`.

- MCP: Claude uses its user-scope registrations (`claude mcp list`); routes, status and
  limits per application are in `docs/agents/CAPABILITIES.md`. Load the matching DCC skill
  (`blender-mcp`, `revit-mcp`, `autocad-mcp`, `rizomuv-mcp`, `speedtree-mcp`, `3dsmax-mcp-dev`).
- Guard: `.claude/hooks/guard.py` (PreToolUse) asks before push, history rewrite,
  recursive deletes, installs, system changes and writes to production binaries.
- When production work needs new code in `src/` or a shared tool, keep it minimal and
  hand the generalisation to Codex (`docs/backlog.md`), unless the task says otherwise.
- While Codex is unavailable, Claude also owns git/GitHub work (branches, push, PRs,
  merges to `main`, state updates after merges) — fallback in `docs/agents/ROLES.md`.
- DCC per step: choose Blender or Max with a one-line reason [D270]; details/helper: `docs/agents/CAPABILITIES.md#dcc-acceptance-defaults`.
- Ask once per task: «по завершении этапов открывать тебе сцену для приёмки?»; yes: automatically open a new version at each stage + absolute path; no: path only; retain the answer [D270].
- Acceptance: 3ds Max 2026 QUAD review copy, a user preference; triangulate only required delivery exports [D270].
- Herdr workspace rules: `docs/HERDR.md`.
- `technical_library/`: read it only when the task names a package from it.
