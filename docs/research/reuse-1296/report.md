# Reuse instead of rewrite — decision packet (#1296)

Research only. **No `agr` executable is implemented, no scripts are moved/deleted,
no DCC is invoked, no model is certified.** The [first NPM/OKS draft](../../../routes/npm-oks.md)
was pushed first in draft PR #1301, commit `bf2aa7d0`. VPM/Ground route drafting waits
for Artem's verdict. This report is a reuse shortlist, not approval to generalize every historical script.

## 1. Inventory and reproducibility

Frozen source: `bef0522846a4cb73dcceb9e6f4a8d8ae713ee4a4` (origin/main at intake).
[Inventory CSV](data/inventory.csv): **656 rows**, with Git-blob SHA-256, line count,
purpose, input/output evidence, named parameters, DCC references, owner job, job references,
imports, definitions and existing shared-coverage candidates.

| Scope | Count | Inclusion |
|---|---:|---|
| Job-local | 290 | Every tracked script recursively under `jobs/*/scripts`, including 7 shell launchers |
| tools | 233 | Code suffixes plus extensionless shebang `tools/git-hooks/pre-commit` |
| dt_ai entry files | 16 | `src/dt_ai/cli/*` plus modules containing `__main__`; package marker retained explicitly |
| Max AGR Tools | 117 | Python, MAXScript, macro and MZP run scripts; config/docs excluded |

**Reconciliation with 283:** 271 Python + 10 MAXScript + 2 MJS = **283**;
adding the 7 shell scripts makes 290. The 295 tracked files in job script directories
include 5 JSON configs, not executable scripts. The card's five largest directory counts
(138/41/33/29/26) count all files: e.g. ELV is 134 executable scripts + 4 JSON;
KPP1 is 28 + 1 JSON. This is a definition difference, not a missing-script claim.
See [snapshot](data/snapshot.json) for every job count and all excluded non-script paths.
Other jobs are not dropped: vyatskaya-tow02 12, butovskaya-sosh1000 8,
skug26-k5-ac 6, ORCH-OBR22-NPM 1, maf-atlas-512 1.

Reproduce into a **new** directory (stdlib Python, Git; no repository script is imported):

```bash
python docs/research/reuse-1296/measure.py --ref bef0522846a4cb73dcceb9e6f4a8d8ae713ee4a4 --out tmp/reuse-fresh
python docs/research/reuse-1296/measure.py --ref bef0522846a4cb73dcceb9e6f4a8d8ae713ee4a4 --out docs/research/reuse-1296/data --check
```

`--check` compares bytes without writing. A changed source ref invalidates this snapshot;
never silently refresh historical evidence. Raw `git cat-file --batch` bytes are read in memory;
`git archive` was rejected after independent probes found EOL conversion in 23 Max scripts.
The analyzer refuses an existing generation directory and uses exclusive file creation.
It is a research reproducer, not a production artifact publisher or universal alias guard.

### How to interpret each field

- Purpose comes from module documentation / header comments; six otherwise undocumented
  entry/install/job files were inspected and given explicit descriptions in `facts()`.
- Inputs/outputs are up to eight source-line excerpts (with further-hit count), **not** a complete
  side-effect specification. `not declared statically` is unknown, not no I/O. Named flags do not
  replace inspection of positional `sys.argv`, config, globals or runtime host inputs.
- DCC is a **static reference**, not a claim that the file needs or successfully ran that host.
  Pure AGR Tools cores can mention Max while being stdlib-only; glue imports pymxs.
- `owner_job` is certain from location. `job_references` searches exact full path OR basename
  mentions in tracked job code/docs/config. Basename collisions can overcount and dynamic callers
  can be missed: these are discoverability leads, not verified run/session counts.
- `shared_coverage` is a conservative **candidate** map; imports and scored cross-scope content
  matches are separate evidence. “Self/shared” means location, not API stability or completeness.
  Only the inspected derivation trio below is demonstrably already routed through `dt`.
- Versioned files are historical evidence, not an invitation to delete “duplicates”. No portability,
  architectural equivalence or new production pass is inferred from this census.

## 2. Duplicate groups: name AND content

[Normalized-name groups](data/duplicate-groups.md), [all qualifying pairs](data/duplicates.csv).
Exhaustive all-pairs comparison of the selected corpus emits **130 pairs**:
64 content-qualified pairs and 66 name-only pairs; no nonempty exact-text pair was found.
Name flag remains present even when a pair is classified as content.

Method: strip `_vNNN` / trailing `_NNN` versions from lower-case stems; do not erase job
identifiers such as `_psu275`. Content uses Jaccard similarity of distinct **5-token shingles**,
identifiers retained, quoted strings/numbers normalized, comments stripped heuristically;
threshold **>= 0.65**, at least 40 distinct shingles in each file. No connected-component
transitivity is asserted: use the actual pair score. The regex is language-agnostic and can
misread comment markers inside strings/docstrings; this is a candidate finder, not a parser,
clone proof or recall-complete detector. Small snippets and heavily renamed algorithms may be missed.

| Evidence | Result | Reuse action |
|---|---|---|
| `package_vpm` | 9 job files + 1 shared tool | Existing `dt derive package`, do not extract a tenth implementation |
| `delivery_export`, `open_view_max2026`, `contact_renders`, `make_textures_full`, `build_full` | 5 / 4 / 4 / 4 / 4 job versions | Most are ELV version lineage, **not** independent proof across five jobs |
| KPP1 `qa_master.py` vs PSU275 `qa_master_psu275.py` | 0.957069, different names | Characterize geometry expectations before a shared QA facade |
| ELV `make_textures_full.py` vs `make_textures_pilot.py` | 0.959871, different names | Move project paint parameters into config only after approval |
| KPP1 `export_vpm.py` vs PSU275 `export_vpm_psu275.py` | 0.871416, different names | Separate common export transaction from object/coordinate assumptions |
| ELV `side_by_side.py` vs `side_by_side_full.py` | 0.748344 | Candidate common contact-sheet composition, not a new renderer |
| PSU275 `sample_finish_masks.py` vs `sample_wall_masks.py` | 0.749292 | Shared sampling candidate, preserve finish/source identity |

### Reuse that already exists (most important finding)

`src/dt_ai/cli/shared_tools.py` already supplies `dt derive atlas`, `dt derive npm`,
`dt derive package`, and `dt ground v015`. Runtime `--help` was exercised for `dt` and
`dt derive atlas`; that proves CLI discovery, **not model production**.
The shared tools' headers name KPP1/PSU275/TEC26 ancestry. Atlas/export still depend on
`jobs/TEC26-OKS/scripts/{finish_map,make_textures,export_safety}.py` by default: **shared entry,
partly job-bound implementation**, not completed decoupling. `tools/materials/npm_atlas_udim.py`
is a separate OBJ/MTL + in-memory atlas route (not an FBX reader); `npm_core.py` is the AGR Tools
host-independent atlas planner with Max glue, not an interchangeable export adapter.

## 3. Top ten proposed `agr` subcommands

Order prioritizes reuse/call reduction, not a promise to build ten new implementations.
One facade should alias/dispatch existing `dt` and tools, preserve exit codes, emit a
small JSON receipt, and expose `--help` / `--dry-run` / `--config` where applicable.
Project dimensions, seam phase/width, atlas layout, paths and naming must be arguments/config,
not copied Python constants. **All `agr` syntax is proposed.**

| # | Candidate / wraps today | Required task parameters and remaining gap | Hypothesized avoided calls | Minutes saved / task | Output tokens saved / task |
|---|---|---|---:|---:|---:|
| 1 | `inspect`: `dt inspect`, `dt index-pdf`, `dt_ai.album` entry points, source census / PDF corpus inventory | job/source manifest, units, source revision, outputs; select adapter, no auto approval | 5–12 | 2.7–6.4 | 3,055–7,331 |
| 2 | `vpm-to-npm`: **existing** `dt derive atlas` + `dt derive npm`; alternate OBJ path `tools/materials/npm_atlas_udim.py` | master/spec/recipe-dir, address/index/prefix, atlas config, placement; decouple TEC26 defaults, do not silently choose adapter | 10–25 | 5.3–13.3 | 6,109–15,274 |
| 3 | `unwrap-atlas`: `atlas_core.py`, `npm_core.py`, `uvlayout_core.py`; job `vpm_uv.py` | profile, unit_m, map/ID correspondence, atlas size/padding, seam origin; Blender adapter must prove parity, not import Max scene objects | 8–20 | 4.3–10.6 | 4,888–12,219 |
| 4 | `package-vpm`: **existing** `dt derive package` / `tools/derive/package_vpm.py` | FBX/texture/object metadata, output version; unknown GeoJSON/glass values stay blockers; no-geojson is not delivery pass | 4–10 | 2.1–5.3 | 2,444–6,109 |
| 5 | `validate`: `tools/qa/validate_package.py`, `twinqa.scene`, `dt qa xview`; final installed SINTEZ as separate stage | profile, actual export, optional quad master, input/parts hashes, checker version, report; distinguish fail/review/not_run and manual checks | 6–15 | 3.2–8.0 | 3,666–9,164 |
| 6 | `delivery-export`: ELV `delivery_export_v005.py`, shared `export_core.py` / `deliver_core.py`, `tools/export/batch_export_plan.py` | naming, frame, master, per-part disposition, pivot/coords, version; ELV exclusions and thumbnail are not universal | 8–18 | 4.3–9.6 | 4,888–10,997 |
| 7 | `open-in-max`: ELV `open_view_max2026_v004.ms`, AGR Tools `handoff_core.py` / host glue | copied scene, Max version, units, owned PID/lock, view config; Blender review fallback; never steal a busy scene | 3–8 | 1.6–4.3 | 1,833–4,888 |
| 8 | `contact-renders`: ELV `contact_renders_v005.py`, `contact_sheet.py`, `side_by_side*.py`; `tools/qa/render_qa.py` for numerical QA only | versioned artifact, source page/image, cameras/layout; reuse compositor, cap views per #1280; no shared contact producer identified | 4–12 | 2.1–6.4 | 2,444–7,331 |
| 9 | `brick-seams`: facade module/UV logic in `uvlayout_core.py`; ELV `cassette_joints.py`, `sandwich_joints_full.py` as **related**, not brick implementations | source-approved module/phase/width/course/bond, region/openings, units, profile; **no dedicated brick generator found**—calibrate texture/UV route before geometry | 8–20 | 4.3–10.6 | 4,888–12,219 |
| 10 | `ucx`: `tools/blender/ucx_build.py` → `dt_ai.geometry.ucx_build`; AGR Tools `ucx_core.py` / `ucx10_core.py` separate host path | Main/Ground, object/with, cell/gap/min_cell/tol/depth, inclusion/drop reasons; VPM only, not NPM step | 8–20 | 4.3–10.6 | 4,888–12,219 |

**How estimates were calculated (not measured speedups):** from merged #1273 / PR #1277
[data/sessions.csv](../agent-step-waste-1273/data/sessions.csv), all 28 job sessions:
`m = median(60 * active_h / tool_calls) = 0.5314888337468983 minutes/call`;
`t = median(out_tokens / tool_calls) = 610.9462419952814 output tokens/call`.
For the stated **assumed** avoided-call range `[L,H]`, savings are `[L*m,H*m]` and
`[round(L*t),round(H*t)]`. Ranges represent removing discovery/path patching/repeated
single-operation orchestration; they are hypotheses to measure in the benchmark, not telemetry
attributed to these individual commands. Active time is based on rounded historical hours and
includes reasoning/DCC waits; multiplying it by removed calls is a rough planning proxy.
Input/cache/reasoning tokens and dollar savings are **not measured**; output-only estimates
must not be called total token savings. The unconditional lower bound is **zero**: these
historical ownership/state transitions were not replayed, so the table is a conditional
scenario if the assumed calls really disappear. Do not add overlapping commands' savings.

Why these candidates: report W1 has 52 multi-image moments/18 sessions and 247 extra images;
W2 has 94 repeated + 15 failed instance calls; W3 173 failed calls; W4 median 18 test runs/2 full
suites over 13 board cards. R6 OKS appears in 11 measured sessions/cards, windows 5,
colouring 5; seams/joints 7 sessions. There is **no measured brick-specific session**.
The session/call counts motivate priorities, not per-command ROI or a $10 proof.
Reference sessions: ELV `271fa1bc`, Garibaldi `86b05944`, KPP1 card `t_d1f84643`,
TEC26 colouring retro (`docs/retros/2026-10-22-tec26-colouring-claude.md`).

## 4. Route, architecture and follow-up boundaries

Read only [routes/npm-oks.md](../../../routes/npm-oks.md) for the first route and worked KPP1
continuation. `standard` node work versus `full` delivery follows accepted #1280 requirements;
existing TASK_TO_MODEL gates stay binding. Links to R1/R4/R6 on main bridge #1281 until its
production recipes merge; no missing/unmerged procedure is claimed as installed.

**Blender headless first** for measurement/analysis/construction on hashed copies. Keep numpy /
stdlib cores separate from bpy and pymxs glue. Max remains for Corona/viz and AGR Tools-native
checks; do not wait for Max for a Blender-capable operation. Reuse the existing background
runner and session-lock rules rather than introduce another DCC launcher.

CLI first provides shell access across Claude, Codex and cheaper models/providers. A thin MCP
wrapper later should expose the same command catalog and contracts. #1292 Code Mode can batch
several guarded Max operations with request IDs, but does not replace a stable geometry core,
per-export independent verification or human acceptance. Unknown outcome → reconcile against
scene IDs/counts/hashes; never blindly replay a write. Avoid parallel new CLI and MCP algorithms.

Proposed implementation sequence **after approval**, not new issues/cards created here:
1. Discoverability facade/aliases over existing `dt derive` + package/validate (no port).
2. One parameterized NPM/OKS pilot, removing only demonstrated project constants.
3. Contact-sheet/open-scene orchestration, default no renders while Artem online.
4. Characterize seam/brick gap and host adapter parity; add code only if existing cores cannot serve it.
5. Run [benchmark](benchmark.md), then decide whether VPM/Ground route and an MCP wrapper earn their cost.

## 5. Questions for Artem

1. Approve the NPM/OKS draft shape first, with no VPM/Ground draft yet? Recommendation: yes; pilot KPP1 derivation rather than create another building script.
2. Approve aliases over the **already existing** `dt derive`/shared tools as the first `agr` milestone? Recommendation: avoid a second CLI implementation or generic build rewrite.
3. Authorize which exact accepted master + source/material/coordinate packet for the benchmark? Recommendation: freeze a KPP1-sized complete building packet; current KPP1 historical reports contain open gates, so not an accepted full-delivery oracle as-is.
4. Which cheaper **exact provider/model/version and paid cap** is authorized for the $10 attempt? Recommendation: one Kimi trial first, Claude/Codex as comparison controls; record real billing, no inferred subscription dollars.
5. Prefer the repeatable NPM-derivation microbenchmark below over speculative “brick seams on a typical floor”? Recommendation: yes; no standalone brick generator/brick-specific cost sample was found. Keep the broader $10 VPM+NPM+textures+sources+all-checkers goal as the second, explicitly gated track.
