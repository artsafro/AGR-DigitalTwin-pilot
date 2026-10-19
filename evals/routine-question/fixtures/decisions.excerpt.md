EXCERPT of `docs/decisions.md` (8 real rows, copied 2026-10-15): the reference evidence of this task, so a
reference verdict does not change when a decision is added. The real run reads the whole file.

| ID | Date | Decision | Applies to | Source |
|---|---|---|---|---|
| D001 | 2026-10-06 | Roles: Claude leads 3D/DCC production, Codex code and organization, Antigravity supports both | `docs/agents/ROLES.md` | chat |
| D005 | 2026-10-07 | A name says what the thing does; object codes live only in data, never in shared names | `docs/agents/NAMING.md` | chat |
| D010 | 2026-10-07 | C1: the VPM triangle table is the hard limit; project target <= 150 000 triangles per OKS FBX in VPM as in NPM | `docs/domain/conflicts.md` #1, `docs/domain/npm-vpm.md` | chat |
| D038 | 2026-10-10 | Every slab (roof in a parapet, terrace) is inset - hole + plate, joint required, a solid slab fails; etalons that differ are fixed | pattern `roof-inset-plane`, benchmarks | PR #63 |
| D071 | 2026-10-13 | Five read-only subagents; only the main agent writes, commits and decides | `docs/agents/WORKFLOW.md` (Subagents) | PR #86 |
| D074 | 2026-10-14 | Events make skills and subagents mandatory (triggers table) | `docs/agents/WORKFLOW.md` (Triggers) | PR #107 |
| D078 | 2026-10-14 | An auto-named worktree branch is renamed before its first commit; the agent proposes, the user confirms | `docs/agents/NAMING.md` | PR #107 |
| D080 | 2026-10-14 | Primitive first: reduction, not reproduction; the parts list is confirmed before any build | pattern `primitive-first` | PR #106 |
