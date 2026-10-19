# Capability roadmap: NPM/VPM production areas, readiness levels, ticket candidates

Research snapshot: upstream `artsafro/AGR-DigitalTwin` main `ea7ecce` (2026-10-15), pilot main `5ff8015`,
`hermes_kanban` as of 2026-10-15 15:30.
Scope: a grilling session between the user and Claude Code (30 questions, 2026-10-15), written up so that the pilot
board can derive a PRD and tickets from it. It is not a ticket list and not a delivery schedule. Nothing in the
upstream repository was changed by this report.

Terms: OKS, NPM, VPM in `GLOSSARY.md`; Ground = relief + GroundEl (MAF) + Flora per `docs/domain/npm-vpm.md`
(reg p.1-2). "Area" below means one production capability; "level" means how far an agent can work that area
without the user.

## Summary

- The roadmap is a **capability roadmap**: for every production area it states what rules, skills, tools, etalons,
  evals and accepted cases exist, and what is missing before any agent can pick a card in that area. It is not a
  list of deliveries (decision 1).
- The area tree is **OKS** {BODY, Windows/doors, Decor, UV/atlas, Textures, UCX, Master → NPM/VPM derivation,
  Export + package} and **Ground** {Surface, Ground textures, Ground UCX, GroundEl/MAF, Flora}, with MAF and Flora
  each split into *identification*, *modelling skill* and *library*. Unreal and IFC are outside this roadmap;
  the agent harness (#118) is a separate track (decisions 2, 3, 15).
- **NPM/VPM is an axis, not a branch**: one mid-poly master per object, derived into NPM and VPM by each profile's
  rules; one ticket of an area covers both profiles or says "NPM only" explicitly (decision 4).
- Readiness has three levels: **L1** the agent knows the rules (requirement sheet, patterns, skill); **L2** the agent
  can check itself (tool with readback, benchmark against an etalon, eval); **L3** verified on a real object by the
  **user's** acceptance. "Passed the official AGR check" is a flag on the object, never a level (decisions 5, 6).
- Today only OKS BODY is at L3; UV/textures and UCX are L2-partial (tools and reviewed objects exist, no benchmark);
  Windows, Decor, Ground are L1-partial; MAF, Flora and the Master → NPM/VPM derivation have rule lines but no
  sheet, skill, tool, benchmark or case (coverage matrix, §4).
- Dependencies between areas bind only at L3 (a real object walks the OKS chain). L1 and L2 of every area are
  independent and run in parallel on already accepted meshes (decision 8).
- The user owns three etalon sources the repository does not yet see: 3ds Max libraries of MAF and of Flora, and
  PDF specifications of MAF from past projects. The MAF library is named "by eye"; identifying each etalon against
  the specifications (screenshot → image search → manufacturer page → specification row) is its own sub-area and a
  prerequisite for a MAF benchmark (decisions 10, 11).
- The board needs one new card kind, `verify` (an independent model checker that never sees how the model was
  built), review for L1 requirement-sheet research cards, and roadmap topics in `night_queue.json` (§9).
- `docs/pipeline.md` upstream says UCX is "missing" while `jobs/KPP1/scripts/vpm_ucx.py` and
  `jobs/PSU275/scripts/vpm_ucx.py` build it and both reviewed deliveries contain it; the matrix records the fact,
  the upstream file is not changed here.

## 1. Goal and boundaries

Goal: any agent that takes a card for any area — BODY, windows, decor, UV/atlas, textures, UCX, derivation,
packaging, Ground surface, Ground textures, GroundEl/MAF, Flora — finds in the repository the rules, the skill, the
tool, the etalon and the acceptance procedure for that area, and can work it to the level the area has reached.

In scope: NPM and VPM deliveries per the Moscow regulation (`standards/source/Rasporyajenies19012026trebovaniya(2).pdf`,
56 pages: App.1 NPM pp.1-19, App.2 VPM pp.20-50, App.3 GeoJSON pp.51-56; every `reg p.N` below is a page of it).

Out of scope, by the user's decision: the Unreal experience (U1-U2) and IFC (U3) — "first learn to model to the
AGR regulation, then make it beautiful in Unreal" — they get their own branches later; the agent harness
(`docs/prd/agent-ready-harness.md`, #118, #119-#134) — a separate track that this roadmap only references in its
definition of L2; porting the pilot's `docs/research` and `docs/experiments` into upstream — not now.

## 2. Area tree and the NPM/VPM axis

```
Delivery profile (axis, not a branch): NPM | VPM — every area has two requirement columns

OKS (building)
├── BODY                 exterior surface, roof, terraces, parapets, inset slabs
├── Windows / doors      openings, frames, stained glass, doors
├── Decor                portals, belts, pilasters, cornices (NPM mid-poly as simple solids)
├── UV / atlas           NPM embedded atlas, VPM UDIM; cross-cutting rule table (§7.4)
├── Textures             finish atlases, tiles, maps d/n/o/m/r; ERM for VPM
├── UCX                  VPM collision hulls; cross-cutting rule table (§7.6)
├── Master → NPM/VPM     one mid-poly master → two deliveries: decimation, atlas vs UDIM, naming, pivots
└── Export + package     FBX export, readback, ZIP, GeoJSON, lights, validator V001-V017, AGR checker

Ground (site)
├── Surface              relief, planes, zones, parking marks, road markings, perimeter extrusion
├── Ground textures      Ground set(s) with density rule, GroundGlass
├── Ground UCX           VPM only, <= 10 cm shape tolerance (part of the UCX capability)
├── GroundEl / MAF       identification → modelling skill → library; 1 texture set <= 512
└── Flora                identification → modelling skill → library; 1 set <= 2048, diffuse (+ opacity)

Later, own branches: Unreal experience, IFC.   Separate track: agent harness.
```

The axis in one sentence: model once at mid-poly, then derive. NPM takes the simplified solids with an embedded
atlas (`docs/domain/npm-vpm.md` reg p.6-7, `docs/domain/uv-textures.md`), VPM takes the same master with UDIM maps,
UCX, GeoJSON and lights (reg p.26-36). A rule that differs between profiles is written in both columns of the
requirement sheet; a rule that is the same is written once.

## 3. Readiness levels and the definition of done

| Level | Meaning | Mandatory components | Who closes |
|---|---|---|---|
| L1 | the agent knows the rules | requirement sheet for the area (§3.1); patterns in `docs/domain/patterns/`; a skill in `.agents/skills/` that walks the area step by step | agent + `dt-reviewer` docs review (this is the one research kind that **is** reviewed) |
| L2 | the agent can check itself | a tool or script with readback (`src/`, `tools/`, `twinqa`); a benchmark with a hand-made etalon in `benchmark/`; an eval or grader in the harness (`dt evals`) | agent + `dt-reviewer`; `verify` card for model outputs |
| L3 | verified on a real object | at least one case in `docs/cases.md` that the **user accepted** on a real source; the object in `jobs/REGISTRY.md` | the user only |

Per area the regulation decides which requirements the level tests: geometry areas pass geometry requirements,
texture areas pass texture requirements, UCX passes collision requirements. "Official AGR check passed" is recorded
on the object in `jobs/REGISTRY.md`; no area reaches a level because of it and no area loses one without it.
No official delivery has passed yet (KPP1 v005 about 90 %, PSU275 delivery-v003 "as reviewed").

### 3.1 The L1 artifact: one requirement sheet per area

`docs/domain/areas/<area>.md`, one file per area, one table:

| Requirement | reg page | NPM | VPM | How it is checked (validator id, benchmark, manual gate) | Detail in |
|---|---|---|---|---|---|

The sheet is the first thing an agent reads after taking a card. It links the existing rule files
(`docs/domain/geometry.md`, `uv-textures.md`, `materials.md`, `npm-vpm.md`, `export-import.md`, `validation.md`)
and never duplicates their text; a conflict stays in `docs/domain/conflicts.md` and the sheet points at it. For OKS
areas most rows already exist in those files and the sheet is mostly an index; for Ground, MAF and Flora the rows
must be extracted from the PDF (they exist today as single lines: `npm-vpm.md:9,27,29,38`, `uv-textures.md:17-19`,
`geometry.md:13,59,61,111`).

## 4. Coverage matrix (upstream main `ea7ecce`)

| Area | Rules | Patterns | Skill | Tool / script | Benchmark / etalon | Accepted case | Real source | Level |
|---|---|---|---|---|---|---|---|---|
| OKS BODY | yes `geometry.md` | 14 (2 proven: roof-inset-plane, terrace) | partial (`analyze-architectural-source` only) | yes `src/dt_ai/geometry`, engine | B01, B02, B02t green; K01 6/9 | Obr22, KPP1 v005, PSU275 v003 | Revit KPP1/PSU275, OBJ03 FBX | **L3** |
| Windows / doors | partial (`geometry.md`, C24/C25) | 1 (opening-plane) + vent-grille | no | partial (`build_shell_windows`, window_atlas job) | no | frames v002; REVIT-OPENINGS pilot not accepted | Revit | L1-partial |
| Decor | partial (`geometry.md`, mid-poly rule) | 1 (facade-decor-inset, draft) | no | partial (OBJ03 from_source, EXPERIMENTAL, closed #117) | B03 README only; K02 waits for `.max` | none (OBJ03 unsuccessful) | OBJ03 FBX; K02 `.max` pending | L1-partial |
| UV / atlas | yes `uv-textures.md` | no | partial (`rizomuv-mcp`) | yes (`uv.py`, glb_atlas, uv_continuous) | no | Obr22 v011/v012, SOSH1150 v006, GLB | job inputs | L2-partial |
| Textures | yes `uv-textures.md`, `materials.md` | no | no | yes (facades atlas tile v003, procedural v010) | no | facades atlas, A/B main atlases | job inputs | L2-partial |
| UCX (OKS) | yes `geometry.md` §Collision, C3 decided | no | no | job scripts only (`jobs/KPP1`, `jobs/PSU275` `vpm_ucx.py`; Max `UCX_Tools.ms` as reference) — not generalised (backlog H10, P5) | no | inside KPP1/PSU275 as reviewed | derived | L2-partial |
| Master → NPM/VPM derivation | spread over `npm-vpm.md`, `export-import.md` | no | no | job scripts (`export_npm`, `package_vpm`, `run_all`) duplicated per job (H10, EG4) | no | KPP1, PSU275 (per-job) | — | L1-partial |
| Export + package + validation | yes `export-import.md`, `validation.md` | no | partial (`validate-delivery`, `run-evidence`) | yes (`twinqa` V001-V017, FBX readback) | no | KPP1, PSU275 packages | — | L2-partial |
| Ground surface | partial (`geometry.md:13,59,61,111`) | no | no | partial (`jobs/GROUND-PROJECTION` scripts; Max `Ground_Tools`) | no | contours/18 IDs/materials of v003 accepted; v008 mesh waits for review | only in the job's local outputs | L1-partial |
| Ground textures | partial (`uv-textures.md:19,21,43`, density conflict) | no | no | no | no | materials of v003 | — | L1-partial |
| Ground UCX | partial (`geometry.md:59,61`) | no | no | no | no | no | — | L0 |
| GroundEl / MAF | lines only (`npm-vpm.md:9,27`, `uv-textures.md:17`) | no | no | Max `Maf Tools.mcr` (AGR base, reference) | no | no | user's Max library + PDF specifications (outside the repo) | L0 |
| Flora | lines only (`npm-vpm.md:9,27`, `uv-textures.md:18`) | no | partial (`speedtree-mcp`) | SpeedTree MCP; Max `FloraAtlas.ms` | no | no | user's Max library (outside the repo); `flora.dwg` test | L0 |

Facts behind the matrix: `docs/pipeline.md` (stages #1-#16, P9-P11, U1-U3), `docs/backlog.md` (P1-P12, EG1-EG5,
Q1-Q7, H10, U1-U3), `docs/cases.md`, `jobs/REGISTRY.md` (two registered objects: `tec26-kpp1`, `tec26-psu275`;
18 job folders), `benchmark/README.md`, `.agents/skills/` (16 skills), `docs/agr/INDEX.md` (Ground case study,
UCX review, MAF plugin review; nothing on Flora). `GLOSSARY.md` has no entry for Ground, GroundEl, MAF, Flora or UCX
(backlog G1).

## 5. Dependency graph and the parallelism rule

```
OKS:    BODY ──→ Windows/doors ──→ UV/atlas ──→ Textures ──→ Master→NPM/VPM ──→ Export+package
          ├────→ Decor ───────────┘
          └────→ UCX  (needs only the accepted BODY mesh; not windows, not textures)
Ground: Surface ──→ Ground textures
          └──────→ Ground UCX
MAF:    identification ──→ modelling skill ──→ library        (independent of OKS and Ground)
Flora:  identification ──→ modelling skill ──→ library        (independent of everything)
```

Rule: the arrows bind at **L3 only** — a real object walks the chain and the next area's L3 needs the previous
area's accepted output for that object. **L1 and L2 of every area are independent** and run in parallel on meshes
that are already accepted (Obr22, KPP1 v005, PSU275 v003, B01/B02/B02t etalons). Two areas that do not share files
may be worked by two writers at once (one task = one branch = one worktree = one writing agent stays).

Cross-cutting capabilities: **UCX** is one capability with a target table (OKS Main, Ground; MAF, lighting and
vegetation get none — reg p.36 §13.2), and **atlas/texture rules** is one capability with a target table (OKS set
limits, GroundEl ≤ 512, Flora ≤ 2048, Ground density) — each has its own tickets bound to a target, not a copy of
the ticket in every area.

## 6. Learning sources while there is no live order

Allowed, in the user's order of preference (decision 9):

1. **Old real sources not yet modelled** — `data/sources/revit/` (KPP1, PSU275), `data/sources/OBJ03/`,
   the user's Max libraries of MAF and Flora, the MAF PDF specifications, the K02 `.max` files when they arrive.
2. **Synthetic objects** — marked synthetic, never presented as a real object (`AGENTS.md`), in `jobs/SYNTH-*`
   (the prefix already exists: `jobs/SYNTH-001`); allowed at L1-L2 only.
3. **Re-modelling an accepted object from scratch** under the current rules (benchmark mode) — optional.

Etalons today: `benchmark/bench-*/etalon.json` (extracted; `etalon.max`/`etalon.fbx` by link when large), the
accepted cases in `docs/cases.md`. Etalon candidates not yet in the repository: the user's Max MAF library and Max
Flora library; the user gives their local paths to the board separately together with the specification PDFs
(binary assets are never committed; `data/` is git-ignored and a protected path).

## 7. Areas: what exists, what is missing per level, ticket candidates

Ticket candidates are written in the fields of the pilot issue template (Requirement / Acceptance / Inputs and
versions / Evidence the PR must bring) so that `tools/check_ready_gate.py` can pass once the board fills the rest
(Out of scope, Context). Sizes: S < half a day of agent time, M one to two days, L more. "Blocked by" is stated only
where an input really does not exist yet.

### 7.1 OKS BODY — L3

Exists: rules, 14 patterns, engine `src/dt_ai/geometry` + `dt build`, B01/B02/B02t green, K01 6/9, three accepted
objects. Missing to make L3 reusable by any agent: no BODY skill (the knowledge is in patterns and in
`docs/agents/WORKFLOW.md`), multi-height BODY (P12), master layer (P2), K01 3/9 open checks.

- **T-BODY-1 (S, L1)** Requirement: requirement sheet `docs/domain/areas/body.md` indexing `geometry.md` BODY rules,
  patterns and conflicts C7/C8/C10. Acceptance: every row cites a reg page or a `[D<n>]`; no text copied from the
  rule files. Inputs: `docs/domain/geometry.md`, `patterns/INDEX.md`, `decisions.md`. Evidence: `dt-reviewer` docs
  verdict.
- **T-BODY-2 (M, L1)** Requirement: skill `.agents/skills/model-body/SKILL.md` — stages (contour → walls → floors →
  roof/terraces → readback), per stage the pattern to apply and the check to run. Acceptance: an agent that follows it
  on B01 reproduces the green run without reading other docs. Evidence: B01 run log, `dt evals` record.
- **T-BODY-3 (M, L2)** Requirement: close K01 to 9/9 or record each open check as a decided conflict. Evidence:
  `tools/qa/run_benchmark.py` table before/after.
- **T-BODY-4 (M, L2)** Requirement: multi-height BODY (backlog P12) with a benchmark. Blocked by: a decision on the
  etalon shape (user).

### 7.2 Windows / doors — L1-partial

Exists: opening-plane pattern, C24/C25 choice pages, `build_shell_windows`, window frames case v002, REVIT-OPENINGS
pilot (not accepted), backlog P3 "windows procedure". Missing: sheet, skill, benchmark with window etalon, accepted
real-object windows (KPP1/PSU275 windows were accepted as part of the whole model, not as an area).

- **T-WIN-1 (S, L1)** sheet `areas/windows.md`: NPM (openings in the atlas, plane rule, frames as texture) vs VPM
  (frames as geometry, glass in UDIM 1001 per ADR-0001); conflicts C23/C25 pointed, not decided.
- **T-WIN-2 (M, L1)** skill: window types library (#4 `ready-for-human`) + procedure P3 → `.agents/skills/model-windows`.
  Blocked by: #4 (user's window type decisions).
- **T-WIN-3 (M, L2)** benchmark `bench-b05-windows`: B01 box with three window types, etalon by the user
  (`benchmark/README.md` rule: etalon → extractor → spec, never the reverse). Blocked by: the user's etalon.
- **T-WIN-4 (M, L3)** windows of KPP1 v007 accepted as an area: user acceptance item.

### 7.3 Decor — L1-partial

Exists: facade-decor-inset (draft), mid-poly decision (simple solids ≤ 150k, no baking), B03/K02 READMEs, OBJ03
closed as unsuccessful (#117; code EXPERIMENTAL, not resumed without the user). Missing: everything above the pattern.

- **T-DEC-1 (S, L1)** sheet `areas/decor.md` (NPM mid-poly solids; VPM full detail; limits reg p.7 §3.6 and
  p.28-29 §3.9).
- **T-DEC-2 (M, L2)** K02 benchmark run once `source.max`/`etalon.max` exist. Blocked by: user's `.max` files
  (backlog, `benchmark/README.md`).
- **T-DEC-3 (M, L2)** B03 etalon and first run. Blocked by: user's etalon.

### 7.4 UV / atlas — L2-partial (cross-cutting rule table)

Exists: `uv-textures.md` with reg pages, `uv.py`, `technical_library/uv`, `rizomuv-mcp`, accepted Obr22 v011/v012,
SOSH1150 v006, GLB atlases; pilot hypothesis #83 (corner matching) adopt PR #102 open. Missing: target table,
benchmark, skill, V009 texel density (Q2).

- **T-UV-1 (S, L1)** sheet `areas/uv-atlas.md` with the **target table**: OKS Main (1 set + roof set, reg p.9 §5.11),
  GroundEl (≤ 512, p.10 §5.12), Flora (≤ 2048, diffuse + opacity, p.10 §5.13), Ground relief (density 10-40
  "px per sq.m", p.10 §6.1-6.2, unit conflict open), VPM UDIM single channel (p.31 §2.1.1), glass tile 1001
  (p.31 §2.2).
- **T-UV-2 (M, L2)** benchmark `bench-uv-01`: Obr22 typical floor, etalon = accepted v011/v012 UV, checks = no
  overlaps outside glass, texel density within band, atlas pixel rules (Q1). Evidence: comparison table.
- **T-UV-3 (M, L2)** V009 texel density in `twinqa` (backlog Q2) with a RED test on a wrong-density fixture.

### 7.5 Textures — L2-partial

Exists: facades atlas tile v003, A/B main atlases, procedural textures v010 decision, materials registry (partial,
#7), Q7 (RGBA → RGB + `_o_` opacity, NPM placeholder 128×128). Missing: sheet, skill, benchmark, ERM/Normal VPM maps
proven on a real object.

- **T-TEX-1 (S, L1)** sheet `areas/textures.md`: map suffixes d/n/o/m/r (reg p.10-11 §9), VPM Diffuse/ERM/Normal
  (p.34 §4.3), PNG count 3-2100 (p.26 §1.2), name = filename (p.12-13 §3.4), Q7 rules as `[D<n>]`.
- **T-TEX-2 (M, L2)** benchmark: one accepted atlas (facades v003) re-produced from its tiles, byte-identical PNG
  hashes or a documented tolerance.
- **T-TEX-3 (M, L3)** VPM map set (Diffuse/ERM/Normal UDIM) accepted on KPP1 or PSU275 as an area.

### 7.6 UCX — L2-partial (cross-cutting, VPM only)

Exists: `geometry.md` §Collision (built for Ground surface and OKS, not MAF/lighting/vegetation, reg p.36 §13.2;
shape tolerance Ground ≤ 10 cm, pedestrian floors ≤ 30 cm, rest ≤ 1 m, p.36 §13.5; names
`UCX_SM_{Address}_{Main|Ground}_{001..999}`, p.34 §4.2; C3 decided; ADR-0002 limit/gap), two job scripts
(`jobs/KPP1/scripts/vpm_ucx.py` 33 hulls / 396 tris; `jobs/PSU275/scripts/vpm_ucx.py` 23 boxes, 2 mm gaps), V010,
GeoAGR `ucx_check.exe` review. Missing: one shared tool (H10/P5), benchmark, skill, Ground target never built.

- **T-UCX-1 (S, L1)** sheet `areas/ucx.md` with the target table (OKS Main / Ground / none for MAF, Flora,
  lights) and the gap/limit decisions.
- **T-UCX-2 (M, L2)** one `dt ucx` (or `tools/ucx/`) built from the two job scripts, parameterised by target; RED
  test = PSU275 hulls reproduced from the accepted mesh within tolerance. Evidence: counts and max deviation per
  hull vs the reviewed delivery.
- **T-UCX-3 (M, L2)** benchmark `bench-ucx-01` on B01/B02t (convex hulls vs etalon volume, max distance ≤ 30 cm
  at pedestrian floors). Etalon: derived from the etalon mesh by the user's rule, approved by the user.
- **T-UCX-4 (M, L3)** Ground UCX on the GROUND-PROJECTION site (≤ 10 cm). Blocked by: Ground surface v008 review.
- Fact to fix in the same PR as T-UCX-2: `docs/pipeline.md` #10 "UCX missing" → "job scripts, not generalised".

### 7.7 Master → NPM/VPM derivation — L1-partial (new node)

Exists: the logic lives in `jobs/KPP1/scripts/` and `jobs/PSU275/scripts/` (`export_npm`, `make_npm_atlas`,
`package_vpm`, `qa_master`, `run_all`), duplicated per job (backlog H10, EG4; pilot report
`job-artifact-name-contract.md`). Missing: a written contract and one shared implementation.

- **T-DER-1 (S, L1)** sheet `areas/derivation.md`: what a master must contain (quad, material ids per ADR-0001,
  LEVEL helpers, pivots per reg p.32-33 §9) and what each profile removes or adds (triangulation, atlas embed vs
  UDIM external, UCX, lights, GeoJSON, naming p.11-13 §3 / p.33-35 §4).
- **T-DER-2 (L, L2)** shared pipeline `dt derive --profile npm|vpm` built from the two job script sets, with the
  KPP1 and PSU275 packages reproduced hash-for-hash or with a documented diff. Evidence: RED (one job's package
  cannot be built by the other job's scripts) → GREEN.
- **T-DER-3 (M, L3)** KPP1 v007 derived through the shared pipeline and accepted by the user.

### 7.8 Export + package + validation — L2-partial

Exists: `export-import.md`, `validation.md`, V001-V017, FBX readback, `validate-delivery` skill, packages of KPP1
and PSU275; missing: GeoJSON on a real object (P8, validator only), lights (P6), MSK-77 pivot (P7), AGR checker
pass (Q5), the two validators merged (Q3), clearance classification (Q4).

- **T-PKG-1 (S, L1)** sheet `areas/package.md` (ZIP and FBX limits reg p.6-7, p.26; GeoJSON p.51-56 with [D011],
  [D016]; lights p.33-35).
- **T-PKG-2 (M, L2)** GeoJSON and lights produced for PSU275 and validated (P6, P8) — the first real-object run.
- **T-PKG-3 (M, L2)** SINTEZ/AGR checker integration (Q5) as a gate, output recorded as evidence.

### 7.9 Ground surface — L1-partial

Exists: `geometry.md:111` (NPM ≤ 50 000 polys, ~3 m quads, smoothed height field — a project decision from
`jobs/GROUND-PROJECTION/NPM_RESULT.md`), perimeter extrusion ≥ 1 m (p.7 §3.4, p.28 §3.7), bounds rule (p.2, 21),
contours + 18 IDs + materials of v003 accepted, v008 mesh waiting for review, AGR case study
`docs/agr/case_studies/GROUND_CONTOURS_AND_NPM.md`. Missing: sheet, skill, tool outside the job, benchmark, VPM
Ground (triangle table p.28-29 §3.9-3.10 with the p.40 conflict).

- **T-GND-1 (S, L1)** sheet `areas/ground-surface.md` (NPM and VPM columns; the triangle-table conflict pointed).
- **T-GND-2 (user, L3)** review of GROUND-PROJECTION v008 — the user's open gate; also the priority follow-up on
  the production copy ("Ground Max import", decision 14).
- **T-GND-3 (M, L2)** `dt ground` from the GROUND-PROJECTION scripts (contours → height field → quad mesh →
  readback), with v003 contours as the RED/GREEN fixture.
- **T-GND-4 (M, L2)** benchmark `bench-g01-site`: synthetic site with two slopes and a 30 cm step; etalon by the
  user.

### 7.10 Ground textures — L1-partial

- **T-GTX-1 (S, L1)** rows in `areas/uv-atlas.md` and `areas/textures.md` for the Ground target (density band,
  ≤ 20 sets, baking vs slicing p.18 fig.7-8); the density unit conflict stays in `conflicts.md` for the user.
- **T-GTX-2 (M, L2)** Ground texture set for the GROUND-PROJECTION site at the accepted density, validated by
  the V009 check from T-UV-3. Blocked by: T-UV-3, the density unit decision.

### 7.11 GroundEl / MAF — L0 → three sub-areas

Rules today: GroundEl = MAF, fences, lighting masts, planters (p.1-2); 1 texture set ≤ 512 (p.10 §5.12); counted in
the Ground 180k budget (p.7 §3.6); no UCX (p.36 §13.2); identical in NPM and VPM (p.4, 24); names
`SM_{Address}_GroundEl` (p.11-12 §3.3). AGR base: `ZAVOD_AND_MAX_PLUGINS_REVIEW.md` (Maf Tools, Collizii).
Sources the user owns: a 3ds Max library of etalon MAF (named by eye), PDF specifications of MAF from past projects.

**MAF / identification** (prerequisite for the benchmark, not for L1):
- **T-MAF-1 (M)** Requirement: for every etalon in the Max library — isolate the object, render a screenshot,
  reverse image search (Yandex/Google Images) and manufacturer sites, match it to a row of a specification PDF.
  Done per object = name from the specification (manufacturer + article/name) + source link + comparison screenshot
  + confidence high/medium/low (+ dimensions from the manufacturer's sheet when found, which also checks the
  etalon's scale). Low confidence goes to the user. Acceptance: an inventory table `jobs/SYNTH-MAF-ID/inventory.md`
  with one row per library object, no row without a confidence value. Inputs: local paths to the Max library and the
  PDFs (the user provides them to the board), 3ds Max 2024 or 2026 by day (rule 22) or headless (rule 17). Evidence:
  the table, screenshots, the list of unmatched objects. External image search with screenshots of the user's
  library models is allowed (decision 11).

**MAF / modelling skill**:
- **T-MAF-2 (S, L1)** sheet `areas/groundel-maf.md` from the PDF pages above plus the specification conventions.
- **T-MAF-3 (M, L1)** skill `.agents/skills/model-maf`: from a picture or drawing to a mid-poly solid within the
  GroundEl budget, UV into the shared ≤ 512 set, naming, pivot; Blender or 3ds Max as the agent prefers (decision 13).
- **T-MAF-4 (M, L2)** benchmark `bench-maf-01`: three identified etalons (bench, urn, lamp post); the agent
  models each from the manufacturer's image/drawing only; `verify` compares with the etalon (bounding box, triangle
  count, pivot, UV set, name) by the requirement sheet. Blocked by: T-MAF-1 for the three chosen objects.
- **T-MAF-5 (L, L3)** ten MAF from one real specification modelled, verified and sent to the user as one scene —
  the user's acceptance.

**MAF / library** (after the skill): typed MAF with correct names as an etalon set; a by-product of T-MAF-1 and
T-MAF-4, not a goal before L2.

### 7.12 Flora — L0 → same three sub-areas, lower priority

Rules today: Flora = greenery about 2× above lawn level (p.1-2); 1 set ≤ 2048, diffuse + opacity only
(p.10 §5.13); no density rule; no UCX; names `SM_{Address}_Flora`. Tools: `speedtree-mcp` skill, SpeedTree MCP
adapter, Max `FloraAtlas.ms`. `docs/agr/INDEX.md` has nothing on Flora. Source the user owns: a 3ds Max Flora
library; whether planting schedules (species lists) exist is an open question (§10).

- **T-FLO-1 (S, L1)** sheet `areas/flora.md`.
- **T-FLO-2 (M)** identification of the Max Flora library against planting schedules — only if schedules exist;
  otherwise an inventory by species as named.
- **T-FLO-3 (M, L1)** skill `model-flora`: SpeedTree → FBX readback (backlog P11) or card/billboard planes within
  the 2048 set; opacity map rule.
- **T-FLO-4 (M, L2)** benchmark `bench-flora-01`: one tree, one shrub, one hedge; `verify` on triangle budget,
  atlas size, opacity, naming.

## 8. Decisions taken in the grilling (2026-10-15, the user)

1. The roadmap is a capability roadmap (readiness per area), not a list of deliveries.
2. Area tree as in §2; OKS has the nodes BODY, Windows/doors, Decor, UV/atlas, Textures, UCX, Master → NPM/VPM
   derivation, Export + package; Ground has Surface, Ground textures, Ground UCX, GroundEl/MAF, Flora.
3. Unreal and IFC are outside this roadmap (own branches later); the harness is a separate track; pilot research is
   not ported to upstream now.
4. NPM/VPM is an axis: one mid-poly master, derived into both profiles; one ticket covers both unless it says
   "NPM only" / "VPM only".
5. Levels L1 (knows the rules), L2 (can check itself), L3 (verified on a real object by the user's acceptance).
6. "Official AGR check passed" is a flag on the object, not a level.
7. The L1 artifact is one requirement sheet per area (`docs/domain/areas/<area>.md`), linking existing rule files,
   no duplication; L1 research cards are reviewed.
8. Dependencies bind at L3 only; L1-L2 of all areas are independent and may run in parallel on accepted meshes.
9. Learning sources: old real sources, synthetic objects (marked, `jobs/SYNTH-*`), re-modelling accepted objects
   (optional).
10. MAF and Flora: the modelling skill comes first, trained against the user's Max libraries as etalon candidates;
    the typed library is built after the skill. L2 = benchmark against an etalon, as for OKS.
11. MAF identification is its own sub-area with the done-criterion of §7.11; sending screenshots of the user's
    library models to external image search is allowed; specification PDFs and library scenes are given to the
    board as local paths, never committed.
12. Model acceptance on the board: a new card kind `verify` (independent checker that never sees how the model was
    built) produces the check table and renders; final acceptance, finish mapping, ID0 resolution and visual sign-off
    are the user's.
13. DCC: 3ds Max and Blender together, as the agent finds convenient; Max 2024 or 2026, Blender 5.1 — the agent's
    choice (answers to the pilot's open questions in `3dsmax-scripting.md` 1, `blender-bpy-automation.md` 1).
14. Priority follow-up on the production copy (`bim-blender-agr.md` question 3): Ground Max import.
15. The roadmap lives in the pilot (this report → PRD → tickets on the pilot board); upstream is not the source of
    truth for it while the board runs on the pilot.
16. Ticket depth (delegated to Claude): per area, first a reviewed L1 research card, then a map issue with
    sub-issues for L2 (the `#118` shape: map issue, children as sub-issues, native `blocked_by`), L3 always through
    the user; this report gives candidates, the board cuts the tickets.

Not decided, left to the user: everything in §10.

## 9. What the board needs (proposals for `hermes_kanban`)

- **`verify` card kind** — input: a PR or run that produced a model (FBX + run record), the area's requirement
  sheet, the etalon when there is one; output: a table `check / expected / measured / pass-fail` by the sheet, renders
  from fixed cameras, `delivery_passed=false` always; reviewer profile separate from the author and from
  `dt-reviewer` (code); never a fix proposal. Upstream has the role already as a Claude subagent
  (`.claude/agents/independent-checker.md`) — the card kind is its board form.
- **Review for L1 research cards** — research cards are not reviewed today (`agr_refill.py`); a requirement sheet
  extracted from the regulation must get the docs round of `dt-reviewer` (one round). Mark these cards by title
  prefix `Research (L1): <area>`.
- **Topics in `night_queue.json`** — one research item per area for the L1 sheets (§7, `T-*-1`), approved by the
  user; the hypothesizer so far produced only QA/intake tooling claims (#83-#107), none on windows, decor, UCX,
  Ground, MAF or Flora — the roadmap sections are the missing input.
- **Map issues per area** on the pilot repo after the L1 sheet is merged, in the pilot issue template, with
  `blocked_by` only where §7 says "Blocked by".
- **Local asset paths** for the Max libraries and the MAF PDFs reach workers through the card body (Inputs), not
  through the repository.

## 10. Open questions for the user

1. Flora: do planting schedules (species, heights) from past projects exist, so that the Flora library can be
   identified like MAF (§7.12 T-FLO-2)?
2. MAF naming in the library after identification: manufacturer + article from the specification (recommended),
   or the project's own MAF numbering?
3. Density unit for Ground textures (`docs/domain/conflicts.md`, reg p.10 §6.1-6.2) — blocks T-GTX-2.
4. Triangle budget for VPM Ground: table p.28-29 vs fig. p.40 (800k/3M) — `conflicts.md`.
5. Etalons the benchmarks wait for: B03 and K02 `.max` files, a windows etalon (T-WIN-3), a site etalon
   (T-GND-4) — which first?
6. Window type library (#4, `ready-for-human`) — blocks T-WIN-2.
7. From the pilot reports, still open: Max/FBX plugin build to pin and headless licensing confirmation
   (`3dsmax-scripting.md` 1, 3), DCC lease ownership (`mcp-dcc-bridges.md` 3), IFC schema and coordinate base
   (`ifc-intake-src-contract.md` 2-3) — tooling-track decisions, not roadmap blockers.

## 11. Proposed next tasks

- **S** — L1 requirement sheets, one research card per area, reviewed: T-BODY-1, T-WIN-1, T-DEC-1, T-UV-1,
  T-TEX-1, T-UCX-1, T-DER-1, T-PKG-1, T-GND-1, T-MAF-2, T-FLO-1 (eleven cards, all independent, all on existing
  rule files and the PDF).
- **M** — the first L2 tools and benchmarks that need no new etalon: T-UCX-2 (shared UCX tool from the two job
  scripts), T-UV-2 and T-UV-3 (UV benchmark on Obr22, V009), T-GND-3 (`dt ground` from the job scripts),
  T-MAF-1 (MAF identification once the paths are given), T-BODY-2 (BODY skill), T-MAF-3 (MAF skill).
- **L** — T-DER-2 (shared derivation pipeline, H10), T-MAF-5 (ten MAF scene for the user), and the map issues per
  area once the sheets are merged.
