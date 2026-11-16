# Antigravity
Any job: read `docs/agents/SKELETONS.md` first (skeleton + hooks, no parallel pipeline [D324]).
For NPM/OKS tasks read `routes/npm-oks.md`; call `agr --help` before writing a script.
For Revit-source tasks read `routes/revit-intake.md` (read-only intake first, [D237]).

Read and follow `AGENTS.md` (shared rules, where things are). Your lane is in
`docs/agents/ROLES.md`: research, documentation, independent review and support tasks.
Skills: `.agents/skills/*/SKILL.md`. MCP config: `.agents/mcp_config.json`.
The guard hook (`.agents/hooks.json` → `.claude/hooks/guard.py`) asks before
destructive or outward actions.

- DCC per step: choose Blender or Max with a one-line reason [D270]; details/helper: `docs/agents/CAPABILITIES.md#dcc-acceptance-defaults`.
- Ask once per task: «по завершении этапов открывать тебе сцену для приёмки?»; yes: automatically open a new version at each stage + absolute path; no: path only; retain the answer [D270].
- Acceptance: 3ds Max 2026 QUAD review copy, a user preference; triangulate only required delivery exports [D270].
