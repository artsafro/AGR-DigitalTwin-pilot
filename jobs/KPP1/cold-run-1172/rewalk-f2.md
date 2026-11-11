# KPP1 re-walk after F2 (#1202)

`job.yaml` now declares `inputs-manifest.json` with `manifest: external-inputs/1`; the source registry is
`jobs/KPP1/sources.json`. Walk of a fresh worktree of the PR head (commit 5f1b86ae):
`git worktree add --detach C:/x/ev_t_e8e7dd29/fresh FETCH_HEAD`, then
`uv run python -m dt_ai.procedure jobs/KPP1/job.yaml --root . --output C:/x/ev_t_e8e7dd29/walk-fresh.json`
-> exit 1, `passed=false`; `walk-v003.json` (LF, byte-equal to the working-tree walk). Inputs gate `review`,
0 errors, external rows 4/4 `equal` (3 АС.03 DWGs in Downloads, album pptx on the asset store), 0 unreachable;
parts `review` (Gate 1 open), later gates missing as before.

`RUN-LOG.md` stays byte-equal: it is hashed report evidence in `job.yaml`.
