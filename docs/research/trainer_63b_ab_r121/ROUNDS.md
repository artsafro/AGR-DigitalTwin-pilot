# Round log, #121: 63B SKELETONS-first A/B

Head: `origin/main` 8531433d1f1a1e4860ce156fd29d7e0b20bf5903. Evidence dir: `C:/x/ev_t_cc06dd03/`. It is copied to
`G:/Мой диск/AGR-evidence/121-trainer-63b-ab/` together with `SHA256SUMS.txt`.

| round | what | result |
|---|---|---|
| 0 | Preflight on the bank copy where only `practice_ready` was changed (`bank_63b_admit_r0.json`, sha256 `e686dc75…`) | **fail**: 31 files of the scrubbed practice tree still point to the accepted versions or to the unscrubbed repo. `1619-body-training` appears in 2 files (`docs/research/autoresearch-trainer-tower-id.md`, `docs/research/body-training-1619/README.md`), `POLY63-B` in 10, `agr-pilot/AGR-DigitalTwin` in 20, `C:/x/trainer/runs` in 2. The positive trigger witness works: the scan fires on the current bank. The official 63B entry is **not isolated** as is. |
| 1 | Repair: the 31 files are added to the 63B `hidden_repo_paths`, in the copy only (`bank_63b_admit_r1.json`, sha256 `30fec481…`, 35 paths) | **pass**: 3865 files scanned, 71 scrubbed, 0 left, 0 hits in the prompt |
| 2 | A/B run: OLD = empty, NEW = `AGENTS.md` sha256 `fe83e898…`. Codex / gpt-6.1-terra, wall time 10 min 19 s, exit 0 | verdict **unchanged**: both arms stop first at `artifact` (no FBX) |

## Round 2 numbers (`ab.json` sha256 `20c412e6d86ccf8a…`)

| | old | new |
|---|---|---|
| first failing step | artifact | artifact |
| commands / wrong-turns | 27 / 2 | 39 / 4 |
| input tokens | 2 385 411 | 2 724 714 |
| arm wall time (s) | 262.7 | 309.4 |
| stages used | inspect, body, skeleton-guard | inspect, body, skeleton-guard |
| first command that reads `SKELETONS.md` | #1 (the second command) | #1 |
| read audit | **pass** (27 cmds, 5 files, 0 FAIL, 0 WARN) | **pass** (39 cmds, 4 files, 0 FAIL, 0 WARN) |
| QUESTIONS.md | which part of the site FBX is tower B; project zero | the same two questions |

Hypothesis H121: **refuted (n=1)** under the frozen outcome rule. Explanation from the transcripts:
1. The baseline `AGENTS.md` at `8531433d` already sends the agent to `SKELETONS.md` first (the "One door" line). Both
   arms read it as their second command, so the #1924 phrase has no remaining effect on that channel.
2. Both arms stop for the same reason. The 63B task text ("Object: site 63, tower B ... from the site Revit FBX")
   does not say which geometry in the shared site FBX `STLB-04_RR_AR.fbx` is tower B, and gives no level band.
   The 63A task does give one: +10.15 .. +47.95 m, 12 floors. The first failure on 63B is a gap in the bank task
   text, not in the harness.

Side finding (isolation, not about accepted versions): both arms read user-level skills outside the practice tree
(`C:/Users/artsafro/.agents/skills/codex-work-route/SKILL.md`; 3 reads in old, 2 in new).
`codex exec --ignore-user-config` does not hide `~/.agents/skills`.

Not measured: collateral impact on 63A/G22 (no accepted-control rerun) and run-to-run variance (n=1).

Receipt: `G:/Мой диск/AGR-evidence/121-trainer-63b-ab/SHA256SUMS.txt` (29 files: both arm records without `wt/`,
`ab.json`/`ab.md`, audits, preflights, both bank copies, variants). Replay:
`uv run -q agr trainer --bank <bank_63b_admit_r1.json> ab 63b-stage1 --ab variants/old variants/new --scope INVARIANT
--lane codex --out <NEW>` at `origin/main` 8531433d, then `isolation.py audit <arm> <bank> <out>` per arm.
