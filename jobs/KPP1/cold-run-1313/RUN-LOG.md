# KPP1 cold-agent run #3 — issue #1313, run `issue-1313-cold-run-v001`

Measurement, not a fix session (fixing findings is out of scope of #1313). Repository at `origin/main`
`9d7753e1` merged into the card branch (after F9-F20 #1309-#1312 and the false-clean fix #1267 / PR #1300,
all closed/merged). Agent: Hermes `dt-worker` (claude-opus), headless Kanban card `t_c0512482`, fresh context.
Read: AGENTS.md, `docs/PROJECT_STATE.md`, `routes/npm-oks.md`, `docs/procedure/TASK_TO_MODEL.md`,
`jobs/KPP1/{TASK.md,job.yaml,STATE.md (header + pipeline),sources.json,object.json}`, `site-1255/REPORT.md`
(artifact paths), `benchmark-1318/{run_benchmark.py,prepare_master.py}`. Cold runs #1/#2 logs
(`cold-run-1172`, `cold-run-1279`) were read **after** the package attempt, for the comparison only.

## Result in one line

Reached the **package** stage, not only Gate 1: inputs walk (4/4 sources `equal`) -> cold PartsList
(8 parts, `approval_sha256` `aef851f2…1826`) -> Gate 1 requested on the issue -> NPM derived from the approved
R1 master with `agr vpm-to-npm` (exit 0, 30 162 + 504 tris, triangle multiset equal) -> clean-process
readback exit 0 -> xView 116 overlapping faces -> validators NPM/VPM `passed=false` -> `agr package-vpm`
**refused** (no `export_meta.json`). **Package not built**; cold-run walk exit 1, `passed: false`,
`waits: {user: 2, max: 1, visual: 1}`, 0 errors. **14 min 25 s wall and 47 tool calls** from the card to the
package attempt; 6 new findings F21-F26.

## Route chosen and why

The issue allows Gate 1 answers from recorded decisions. `TASK_TO_MODEL` binds Gate 1 to the hash of a new
PartsList (#1309), so a **new build** waits for Artem. R1 geometry is final by [D254] and
`routes/npm-oks.md` "Worked continuation: KPP1" names the route: keep approved R1 geometry and run the approved
master through today's NPM path on a new copy, then readback, xView and validators. That is what this run did;
nothing was rebuilt, no Max call (Max-only AGR Tools stays `waits: max`). DCC: Blender 5.1.2 headless for
derivation/readback (the repo's `agr vpm-to-npm` and readback are Blender tools; Max not needed for a
read-only continuation).

## Run log per stage

Times are local file mtimes / `date` on this PC (UTC+1); calls = tool calls of this session including failed
ones. Renders and image views: 0 in every stage.

| Stage | From - to | Wall | Calls | Failed / retried | Result |
|---|---|---:|---:|---|---|
| S0 orient: card, blocker states, merge `origin/main`, AGENTS/STATE/route/TASK_TO_MODEL, KPP1 TASK/job.yaml/sources | 10:21:54 - 10:24:30 | ~2 min 36 s | 9 | 0 | route = continuation on R1 master; 8 gates known |
| S1 inputs: find R1/site/benchmark artifacts on Drive, walk `jobs/KPP1/job.yaml` | - 10:26:56 | ~2 min 26 s | 8 | 0 | walk exit 1, 0 errors, external 4/4 `equal`; all 8 gates non-pass (5 review, 2 missing+waits, operations waits max) |
| S2 PartsList: packet verify, try R1 `parts-r1-v002.json` as PartsList, schema, write + validate | - 10:28:50 | 1 min 54 s | 8 | 2 (validator: PDF page / model sheet / `build_as`; then album `.pptx` refused as drawing) | `parts-v001.json` valid, 8 parts, 3 questions; R1 parts file **not** a PartsList (22 errors, F21); album cannot be listed (F22) |
| S3 Gate 1 request | - ~10:29:30 | ~40 s | 2 | 1 (`$TMPDIR` path not visible to `gh`) | [issue comment](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/1313#issuecomment-6875224009), unanswered; parts `waits: user` |
| S4 model: approved R1 master | (with S5) | — | (in S5) | — | `master-r1-v001.blend` `492f20af…` from packet-r1-v001 (25/25 rows equal); master xView 112 overlapping faces / 166 pairs |
| S5 derivation `agr vpm-to-npm` (via `benchmark-1318/run_benchmark.py`) | - 10:30:41 | ~1 min 10 s | 8 | 5 (packet integrity mismatch x2 = F23; recursive copy + `execute_code` refused headless; one piped exit hidden) | derive exit 0, main 30 162 + glass 504 tris, `faces_without_region` 0; runner aborted after derive on the pyc it wrote |
| S6 export readback + xView + accounting | - 10:31:40 | ~1 min | 1 (+2 reads) | 0 | readback exit 0 (clean Blender); accounting triangle multiset equal, max position error 2.1 µm; export xView **116** overlapping faces / 169 pairs (exit 1) |
| S7 validators `agr validate` | - 10:32:05 | ~25 s | (same call) | 0 | NPM FBX: pass 4 / fail 1 / review 1 / not_run 2, `passed=false` (V003 master quads fail); VPM r1-v002 ZIP: pass 5 / fail 1 / review 2 / not_run 4, `passed=false` (V001 GeoJSON missing) |
| S8 package `agr package-vpm` | - 10:33:19 | ~1 min 14 s | 3 | 1 (refused) | `refused: … export_meta.json` missing (F25); no NPM packager exists (F24) |
| **Card -> package attempt** | 10:21:54 - 10:33:19 | **11 min 25 s** (+3 min write-up to the walk) | **47** | **9 (19 %)** | package not built; missing gates named below |
| S9 cold-run `job.yaml` + walk, comparison, this log | - 10:40 | ~6 min | 8 | 0 | `walk-v001.json`: exit 1, 0 errors, `waits {user 2, max 1, visual 1}` |

Raw outputs (FBX, atlas, logs, validator JSON): `G:/Мой диск/AGR-evidence/1313-kpp1-cold-run-3/`, hashed in
[evidence-SHA256SUMS.txt](evidence-SHA256SUMS.txt) (45 rows); summary numbers in [stages-v001.json](stages-v001.json).
NPM export `0000_Kpp_1_01.fbx` SHA-256 `d7c878fd066d56afd937ac15061e502baff1aed1826da90d4bc9f4a1092783ad`.

## Comparison with cold runs #1 and #2

| | Run #1 (#1172) | Run #2 (#1279) | Run #3 (#1313) |
|---|---|---|---|
| Stop point | Gate 1 | Gate 1 | **package stage** (refused) |
| Card -> stop, wall | not timed | 5 min 56 s | 11 min 25 s |
| Tool calls to stop | not counted (~17 000 tokens reading) | 43 | 47 |
| Failed calls | — | 5 (12 %) | 9 (19 %) |
| Stages with a machine result | inputs, parts | inputs, parts | inputs, parts, derive, readback, xView, 2 validators, package attempt |
| Renders | 0 | 0 | 0 |
| New findings | G1-G15 (F1-F8) | F9-F20 | F21-F26 |

F9-F20 of run #2 in this run: **F9 gone** (`source_tier` D = drawings-only exists, used); **F10 gone** (parts row:
`triangle_budget` = allocated project budget [D276]); **F11 gone** (`approval_sha256()` + `gate1.parts_sha256`);
**F12 gone** (`sources.json` `repo_inputs` lists `object.json`); **F13 gone** (`jobs/KPP1/TASK.md` indexes D238/D254/
D256/D262/D279); **F17 gone** (`jobs/_template/job.yaml`; the cold-run `job.yaml` walked with 0 errors on the
first try); **F18 gone** (scoped handoff paragraph; build scope still says needs_input, see "Gate 1" below);
**F19 gone** (STATE header names `site-1255`); **F20 gone** (probe below: a `./`-aliased duplicate inputs row makes
the inputs gate `fail`). **F14, F15, F16 not measured**: this run did not re-derive the contour from DWG (geometry
is final R1).

## Findings (issue drafts)

| # | Stage | Where | What | Cost | Proposed change (owner) |
|---|---|---|---|---|---|
| F21 | S2 | `G:/…/1230-kpp1-r1/r1-v002/parts-r1-v002.json` (schema `kpp1-rerun-parts/2`) vs `PartsList` | The approved R1 geometry has no PartsList: its parts file fails `PartsList` with 22 errors (extra keys, no tier/budget). A Gate 1 that binds a hash therefore can never cover the geometry that is actually final [D254]; the cold agent had to reverse-author `parts-v001.json` from the build report. | 3 calls | Convert/attach a validated PartsList to R1 and ask Artem once to bind it (Codex/job owner) |
| F22 | S2 | `SourceRef.kind` (`schemas/PartsList.schema.json`) | No kind for a PPTX/image album: `pdf` requires `page`, `drawing` requires `.dwg/.dxf`. The ИД album (`TEC26_na_RR_1.pptx`, finishes/cassette/RAL authority) cannot be listed in `sources`; recorded as a Gate 1 question. | 1 retry | Add an `album`/`presentation` kind with slide index (schema owner) |
| F23 | S5 | `dt derive atlas`/`npm` `--recipe-dir` imports; `benchmark-1318` packet | Derivation writes `jobs/TEC26-OKS/scripts/__pycache__/export_safety.cpython-313.pyc` into the recipe dir, i.e. into the frozen packet; `run_benchmark.py` then fails `packet integrity mismatch` after a successful derive. The Drive packet `packet-r1-v001` already carries an unlisted pyc (`fb67c1d9…`, mtime 52 s after its `SHA256SUMS.txt`), while the repo's `packet-SHA256SUMS.txt` lists a different pyc (`27cc7239…`). Reproduced on a fresh copy. | 5 calls | Import recipes with `sys.dont_write_bytecode` / `-B` in Blender, exclude `__pycache__` from packets (tools/derive owner) |
| F24 | S8 | `tools/derive/`, `agr delivery-export` pointer | No shared NPM packager: `dt derive npm` writes FBX + atlas but no `0000_<Address>.zip`, so validator V001 stays `not_run` on a bare FBX; the job route used `jobs/KPP1/scripts/run_all.sh`. | 1 search | NPM package step (ZIP + naming) next to `package_vpm.py` (Codex) |
| F25 | S8 | `tools/derive/package_vpm.py` (`agr package-vpm`) | Needs `export_meta.json` next to the package dir (written only by job `export_vpm` scripts); approved R1 evidence (`r1-v002`) has none, so the shared packager refuses the final VPM FBX. `--object` expects `{name, placement, glasses}` while `jobs/KPP1/object.json` is a frames/levels file of the same name. | 1 call | Derive `export_meta` from a readback, or document the producer; rename one of the two `object.json` meanings (Codex) |
| F26 | S7 | `agr validate --profile npm --master` V003 | Approved R1 master is fully triangulated: "master quads" fail (`SM_Kpp_1_Main` 30 162 tris, 0 quads) plus 8 T-junctions; known in `benchmark-1318/summary.json`, but no gate/owner records it in `jobs/KPP1/job.yaml`. NPM from this master can never pass V003. | — | Record the quad-master gap under operations `waits: max` (quad master from the Max/AGR Tools route) (Artem/Max) |

Minor friction, no issue proposed: `execute_code` and `rm -r` are refused in a headless session (use `tar
--exclude` / scripts); `$TMPDIR` (`/tmp/...`) is not visible to native `gh` (use a worktree `tmp/` path).

## Fail-closed probes of the walker

`uv run python jobs/KPP1/cold-run-1313/probe_walk.py . <new dir>` on this run's `job.yaml`: baseline exit 1 non-pass;
duplicated `./` alias input -> inputs `fail`; parts `pass` without `gate1` -> `fail`; parts hash off by one nibble ->
`fail`; `waits` on a `pass` gate -> error; empty inputs -> error, inputs not pass; malformed YAML -> exit 1, parse
error, no report. **7/7 fail-closed** (run #2: 4/5, F20 accepted the duplicate).

## Package and missing gates with owners

Package **not built**. The newest existing package remains `site-1255` site-v004 (validators `passed=false`).

| Gate / item | State in this run | Value / limit | Owner |
|---|---|---|---|
| parts (Gate 1) | `review`, waits user | `approval_sha256` `aef851f2…1826`, [request](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/1313#issuecomment-6875224009) | Artem |
| operations: quad master / final AGR Tools | `review`, waits max | V003 master quads 0 of 30 162 polygons; 8 T-junctions | Artem / Max session (D250) |
| export_readback: overlaps | `fail` | export xView overlapping faces 116 (limit 0, contact pairs = 0 [D152]); D256 covers only 98 VPM / 52 NPM enumerated band pairs | model owner (Max route); Artem for any new exception |
| NPM package ZIP | no tool | V001 `not_run` on bare FBX | Codex (F24) |
| NPM Ground FBX | missing | V001 needs 2..21 FBX, `0000_Kpp_1_Ground.fbx` absent | another author (Ground), not faked |
| VPM package | refused | no `export_meta.json`; GeoJSON missing (V001 fail) | Codex (F25); attributes: territorial code `0000`, FNO, areas are placeholders [D262] — Artem / customer |
| survey / placement | `not_run` | V014 stage unimplemented; V017 manual | validator owner; Artem (V017) |
| visual | missing, waits user | no review sheet for export `d7c878fd…` | Artem |
| checker (SINTEZ) | missing, waits visual | needs complete NPM+VPM packages | Artem / SINTEZ runner after visual |

## Gate 1 note

Card scope is a measurement through all gates; per `TASK_TO_MODEL` "Gate 1 handoff" the request was posted
and the parts gate keeps `waits: user`. No new build was started, so the build-scope `needs_input` block was not
needed; the downstream stages ran only on the already-final R1 geometry and are diagnostics, not a delivery.
