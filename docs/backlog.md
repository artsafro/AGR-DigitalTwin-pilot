# Backlog — unsolved decisions and missing stages

Each item names its default owner (`ROLES.md`). Take one item per branch; move finished
items out of this file in the same merge. `C<N>` = conflict N in `docs/domain/conflicts.md`.

## Decisions for the user (block production)

- **C1–C34** — open source conflicts and 5 dubious rules (`docs/domain/conflicts.md`).
  Decided on 2026-10-07 [D010, D011, D012, D013, D014, D015, D016, D017, D018, D019, D020, D021]: C1, C2, C3, C5, C6, C12, C13, C14, C19, C20, C21, C26. Owner: Claude
  prepares a one-page choice per conflict; the user decides; the decision goes to `docs/domain/`
  and the YAML `conflicts:` block (status `noted`).
- **G1** — GLOSSARY: expansion of "AGR", Master scene, Source album, Current album,
  Production asset. Owner: user + Claude.

## Production stages (default owner Claude; code parts handed to Codex)

- **P1** Run `analyze-architectural-source` on a real source (first: an Obr22 accepted FBX,
  read-only) and on the Revit sources in `data/sources/revit/`.
- **P2** Master building layer: schema and one real object.
- **P3** Windows / stained glass / doors: accept a general procedure (REVIT-OPENINGS pilot
  not accepted).
- **P4** Roof, decor, exterior equipment.
- **P5** UCX generation (VPM) + validator V010.
- **P6** Lights FBX (VPM).
- **P7** Coordinates: MSK-77, zero mark, pivot (reg p.32–33) — export experiment in
  Max and Blender; validator V013/V014.
- **P8** GeoJSON generation from object data.
- **P9** Ground: accept mesh shape (v008), height smoothing parameters (dubious D2).
- **P10** MAF (GroundEl) pipeline from the 3ds Max scripts.
- **P11** Flora: SpeedTree → FBX readback (geometry, scale, textures).
- **P12** (Codex) Generalize BODY extraction to multi-height massing: `exterior.py` supports one
  perimeter and one height. Working job version for PSU275: `jobs/PSU275/scripts/`
  `massing_profiles.py` (union of rectangular masses → per-plane profiles), `sample_wall_masks.py`
  (ray-measured openings), `massing_surface.py` (cut lines stop at holes, corner cuts exchanged,
  T-free quads), `drop_step_bottom_rims.py` (shell post-step). Move into `src/dt_ai/geometry/`
  with tests; keep the PSU275 outputs as regression.

- **P13** (Codex) Findings of `jobs/vyatskaya-tow02` (2026-10-20, first panelised curtain-wall tower; modelling
  accepted by the user as "4+", too slow). Details and numbers: `jobs/vyatskaya-tow02/STATE.md` (Build log, Lessons).
  Engine and harness problems:
  - Speed: `dt spec extract` took 20 min on 690 k triangles (pure Python); `run_benchmark` extracts again before
    building, and the engine build ran 64 min with no progress output or timeout before it was stopped.
  - Panelised source (3ds Max curtain wall, RC_TOW_02: 5 561 parts, no shell): 889 ribbon openings unsized (no
    reveal on panels), 0 decor (fins missed), terrace parapets 3.41 / 2.75 m, roof parapet read off a glass
    railing, roof boxes absent, contour edges skewed up to ±3° after simplification.
  - Engine: BuildError "2D plan weld moves 0.0036 m, beyond weld_m 0.003"; the spec forbids weld_m >= plate_gap_m
    (0.005), so the spec cannot be built at all.
  - Dumper `tools/source/measure_spec_blender.py` writes faces of meshes with a mirrored world matrix (negative
    scale, typical for 3ds Max FBX) inward; some slabs inward as well.
  - Level helpers: the user's empties (`Empty`…`Empty.007`) are not read, only `LEVEL_*`; levels went to
    object.json by hand. A rename/markup step or reading any empty named in object.json would remove the detour.
  - Not built by the engine (EG6): rounded corners, ribbon glazing around a corner, decor along a curve (S-curve
    fins), glass railings in `from_spec`, mid `roof_structures` (BuildError).
  - Harness: `pipeline_gate` only admits engine-gap build scripts in `jobs/<JOB>/scripts/`, so read-only
    `measure_*`/`inspect_*` tools ended in `outputs/` (untracked); subagents may not write report `.md` files, so
    their reports lived only in chat. Proposal: admit read-only tools (no bpy writes) or a `jobs/<JOB>/tools/`.
  New job code to generalise (all `Engine gap: EG6`, `jobs/vyatskaya-tow02/scripts/`):
  - `build_body_blender.py` — ring-stack body: one outline per storey with vertex correspondence; shared columns on
    fixed edges (union over storeys), own columns on moving edges; step soffits between differing storeys cut into
    strips per chain so walls and soffits share vertices (no T-junctions); collapsed-jog handling; fixed-line snap;
    1 cm weld; mitred reveals; mid-reveal glass planes; `seal_leftovers` for quad holes / T-junctions.
  - `build_fins.py` — decor loft along a measured 3D path with linear profile morph, cut at the body with
    >= 10 mm embed (ray sampling), ring spacing by chord error, cap lift over coplanar roof faces.
  - `build_top_blender.py` — zones with z-patterns (solid / opening / glass_face), quad cap fill with holes,
    single-section coping sweep, railing planes, roof boxes; bottom row equal to the body seam vertex for vertex.
  - `build_decor_blender.py` — AC baskets (one-sided planes + floor), railings, louvre blades as boxes with
    ray-cast end embed, colonnade soffit that closes the body's open loop.
  - Measurement method: building-local frame by min-area rectangle of a slab; orthographic elevations/sections
    from numpy arrays instead of viewport captures; storey outlines with vertex correspondence
    (`outputs/measure-v002/bend_rings/`), builder-ready top parts schema (`outputs/measure-v002/top_parts/`).

## Engine gaps — mixed mode (user decision 2026-10-11 [D050], `docs/HARNESS_PLAN.md` §16)

The engine builds what it can (body, openings, floor steps, terraces, inset slabs). Job scripts do only
the gaps listed here; a job script names its gap in its header (`Engine gap: EG<n>`, checked by
`pipeline_gate` on new scripts); anything not listed is asked, not scripted. A gap leaves this list when
the engine covers it.

- **EG1** Facade decor (pattern `facade-decor-inset`): PR 2 spec block `decor` + extractor, with a test of
  merging a split element (same cross-section, one axis, gaps <= `plate_gap_m` x N, N = 12: 0.06 m, user 2026-10-12 [D054]) and of the
  inclusive 0.10 m threshold; PR 3 engine + (meeting by run-in and at building corners, user 2026-10-12 [D059]) +
  checker (no decor overlap with openings, no body edge cut, ids 26-30, 10 cm threshold); PR 4 run on
  `bench-k02-decor-fragment` (real fragment: `source.max` + `etalon.max` by the user). Later regression: the
  synthetic `bench-b03-decor` (free-standing column).
- **EG2** Attachments over 0.8 m (balconies, canopies, bays; slab, railing, soffit) — pattern to be written; the
  decor extractor already lists them as `decor.attachment_candidates` (user 2026-10-12 [D057]).
- **EG3** `mid` window sashes / detailed windows from the opening plane.
- **EG4** UV, atlas and delivery package = **H10**.
- **EG5** Pattern primitive-first, `from_source` (2026-10-14): (a) instances by translation only - a copy turned
  90/180 degrees is a type of its own (OBJ03 v009: 1 328 piers -> 798 types); add rotation to the type key and the
  modules export; (b) regenerate `npm/` from an edited `modules/modules.blend` (now both come from one build).
  Owner Codex.
- **EG6** Curtain-wall tower parts the engine does not build (2026-10-20, job `vyatskaya-tow02`, hybrid
  route: body by the engine): rounded corners and ribbon glazing that wraps a corner (BuildError "corner openings
  are not built yet"); fins that follow a curve over floors (decor is a straight extrusion per wall); glass
  railings on `from_spec` terraces and roofs (only `from_source.terrace_railings` builds them).
  Extended 2026-10-20 ("да"): the whole body of a panelised curtain-wall source built from measurements. This
  3ds Max source has no shell (RC_TOW_02: 5 561 parts, the largest 11 % of its area); run as `source_class:
  panelised` (slabs as body, contours from panels) the extractor took 20 min, sized none of 889 ribbon openings
  (no reveal to measure on a panel facade), found 0 decor, and the engine stopped at BuildError "2D plan weld
  moves ... 0.0036 m, beyond weld_m 0.003" (`jobs/vyatskaya-tow02/pipeline/spec-v002.*`, `outputs/spec-v001/`).
  Also seen there: the dumper writes mirrored-matrix meshes (negative scale) with inward faces.

## Markup helpers (after the terrace; owner Claude, code parts Codex)

Plan: `docs/HARNESS_PLAN.md` §14 (user decision 2026-10-10 [D044]). One PR each, in this order, each with
the pattern `markup-helpers` (written or extended) and its test.

- **MH1b** (MH1 done: Blender route closed on the Blender B01 etalon, pattern `markup-helpers`) — later:
  a script that places `LEVEL_*` Empties in a Blender scene from `spec.json`.
- **MH3** Axes and anchors: generate `AXIS_<name>` (line) from Revit `Grids` through TwinPack; the
  extractor reads the `AXIS_<letter>` / `AXIS_<digit>` grid and binds openings to axes, not absolute
  coordinates; named anchors `TERRACE_<n>`, `ENTRANCE_<name>` as hints to patterns (smaller gray zone).

## Intake — "study the sources" (after the plan is approved; owner Claude, code parts Codex)

Plan: `docs/HARNESS_PLAN.md` §15 (user decision 2026-10-11 [D049]). One PR each, extending the skill
`analyze-architectural-source` (no parallel skill); intake reads only, never changes or exports sources.

- **IN2** Intake on the existing adapters (FBX mesh dump, Revit twin): inventory, picture, contradictions,
  implementation proposal. Test: K01 KPP1 (Revit + FBX).
- **IN3** PDF adapter: text, vector dimensions, page rasters. Test: one real PDF.
- **IN4** Images: agent reading, scale anchors (a user-confirmed dimension or a brick / panel module);
  nothing measured, no spec and no engine run before an anchor is confirmed. Test: B02 from Max screenshots.
- **IN5** DWG through the AutoCAD MCP. Test: one real facade DWG.
- **IN6** SketchUp adapter on intake (after H2). Test: one real SKP.
- **IN7** 3ds Max through the MCP, read only. Test: one real MAX.
- **IN8** Acceptance cases: K01 full (Revit + FBX + PDF) matches the existing specs within the K01
  tolerances, Revit / mesh contradictions listed; B02 images give an estimated spec-draft and the anchor
  question.

## QA (default owner Codex)

- **Q1** Validator: NPM embedded atlas pixel rules (PNG inside FBX), units.
- **Q2** Texel density V009.
- **Q3** Merge `src/dt_ai/validate/bundle.py` (C001–C004) and `src/twinqa` (V001–V017)
  into one validator and one report format.
- **Q4** Clearance hits: classify embed vs defect automatically where possible.
- **Q5** SINTEZ AGR Checker integration (AGR INT-001): coverage map vs the regulation,
  run in an isolated Blender 4.4, import findings.

- **Q6** Encode conflict #20 (decided 2026-10-07 [D019]): `_NNN` address index only with more than one
  OKS; GeoJSON field types/required/decimals as the checker table and lengths from reg p.53-55;
  alpha-plane offset 0.003-0.01 m; Light FBX rules (point/spot, `_Omni`/`_Spot`, numbering).
- **Q7** Convert accepted GLB RGBA NPM atlases to RGB + `_o_` opacity (conflict #21); fix the 3ds Max
  placeholder tool to write 128x128 for NPM (conflict #5). Owner: Claude (DCC), Codex (tool).
- **Q8** NPM texture rules for validation need refinement [D172]: the texture findings on the TOW02 hand finish
  (a shared set of mirrored twin OKS named after the twin, 014 vs 013 [D156]; own-colour padding under 8 px) were
  not accepted; settle the rule with Artem before the validator fails on it
  (`docs/deliveries/vyatskaya-tow02-npm-user-v05-2026-10-21.md`) [D172]. Owner: Claude (rules), Codex (validator).

## Unreal and IFC

- **U1** Unreal import rules (UE 5.5/5.7): scale, pivots, materials, collisions, LODs.
- **U2** Future Unreal interactive experience lives in separate repository, root placeholder removed per owner decision 2026-10-16 [D103].
- **U3** IFC export route.

## Reuse proposals (rule of three, `docs/agents/WORKFLOW.md`; proposals only, nothing created)

Added by `/handover` (procedures repeated in a session) and `/reuse-scan` (repeats across jobs). Line:
`- **R<n>** proposal <date>, <branch> - <CLI command | skill | pattern | src/ module>: <what>; seen <N> times;
effort <S/M/L>`. The user or the owner turns one into a task or drops it.

- **R1** proposal 2026-10-15, harness/agent-ready-prd - CLI command: set a board card's Status and Agent for an
  issue number (find the project item by graphql, `gh project item-edit` twice, option ids from
  `docs/agents/issue-tracker.md`); seen 18 times (17 cards + 1 move to In progress) as an ad-hoc shell loop; effort S
- **R2** proposal 2026-10-15, harness/agent-ready-prd - CLI command: publish a set of tickets from one definition
  file (title, labels, owner, blocked-by keys, body sections) in dependency order with native blocked-by links,
  sub-issue links to a parent and board cards; seen 1 run of 16 tickets through a scratchpad script plus 3 body
  edits by a second script; effort M
- **R3** proposal 2026-10-15, harness/evals-runner - CLI command: the post-merge state update - temporary detached
  worktree from `origin/main`, replace given `PROJECT_STATE.md` sections, run the state and decision tests, commit
  `State: #<PR> merged ...`, push to `main`, remove the worktree; seen 3 times (#137, #139, #140); effort S
- **R4** proposal 2026-10-15, harness/evals-runner - CLI command or skill: one Codex review round of a PR - prompt
  from the issue text, `REVIEW_CHECKLIST.md` questions, the diff range and the review class; `codex exec -s read-only`;
  the findings table posted as a PR comment with the fix commit; seen 5 rounds in this session (#137 x1, #139 x1,
  #140 x3); effort M
- **R5** proposal 2026-10-18, claude/confident-hopper-4jccys - CLI command: append one grilling answer (question,
  recommendation, answer, status, next queue item) to a grilling log and commit it; seen about 30 times as an
  inline python edit + commit + push per answer; effort S
- **R6** proposal 2026-10-18, claude/confident-hopper-4jccys - pattern: a red check with no output and no steps
  (billing lock) is a known cause, commented once per PR, not re-investigated per push; seen about 20 times;
  largely removed by D122 (workflow on manual trigger); effort S
- **R7** proposal 2026-10-18, claude/confident-hopper-4jccys - CLI command: add a decision row (next `D<n>`, date
  order) together with its `[D<n>]` anchor in the target file and run `tests/test_decisions.py`; seen 2 times
  (D104-D129 batch, D130); effort S
- **R8** proposal 2026-10-19, feature/kernel-op-primitive - CLI command: mutation probe of a module - back up the
  file, apply one named textual mutation, run its tests, print passed / failed, restore the file, repeat per
  mutation from a small list; seen 4 times (C3 five mutations, C4a five, a re-run of one that survived, C4b six);
  effort S
- **R9** proposal 2026-10-19, feature/kernel-op-primitive - CLI command: compare failing tests with a clean base -
  detached temporary worktree from `origin/main`, run the named failing tests there, print "same failures / new
  failures", remove the worktree; seen 4 times (#288, #289, #290, #291, each with the same 5 environment
  failures); effort S
- **R10** proposal 2026-10-19, feature/kernel-op-primitive - CLI command: the local CI receipt text for a PR
  (commit, commands, counts, known environment failures from R9) for the body and for the billing-lock comment
  of R6; seen 8 times (5 PR bodies, 3 comments, same shape); effort S
- **R11** proposal 2026-10-20, job/vyatskaya-tow02-midpoly - CLI command: orthographic elevations (4 sides, local
  frame) of source vs built objects from numpy triangle dumps, stacked into one PNG — a screenshot-free visual
  check; seen 6 times; effort S
- **R12** proposal 2026-10-20, job/vyatskaya-tow02-midpoly - src/ module (checker): BVH nearest distance of built
  faces to source faces filtered by material and z range (median / p95 / max, faces over a limit by z); seen 4
  times; effort S
- **R13** proposal 2026-10-20, job/vyatskaya-tow02-midpoly - src/ module (checker): classify open edges (expected:
  stack seam rows, reveal backs, glass borders; unexpected listed with coordinates) and find T-junction vertices;
  seen 3 times; effort S
- **R14** proposal 2026-10-20, job/vyatskaya-tow02-midpoly - skill step: save the open Blender scene as the next
  `outputs/build-vNNN/` version (new folder, never over an existing one) and log it in STATE; seen 6 times; effort S
- **R15** proposal 2026-10-21, job/vyatskaya-tow02-midpoly - CLI command: headless Blender side-by-side renders of
  the source vs our model from identical orthographic cameras (per facade normal + top + close-ups, source glass
  overridden white), composed into left/right sheets; seen 6 times; effort S
- **R16** proposal 2026-10-21, job/vyatskaya-tow02-midpoly - src/ module (checker): xView-equivalent mesh QA with
  explicit tolerances - overlapping vertices (distinct verts within d), overlapping faces (parallel within 5°, planes
  within d, overlap area > 0), mismatched winding edges, bowtie vertices that 3ds Max splits on import, outward
  orientation by ray test; grouped by source part; seen 5 times; effort M. Overlapping vertices / faces and bow-tie
  vertices: `dt qa xview` (#527); winding edges and outward orientation still open.
  Review #514 (2026-10-21): `dt_ai.ops.inv_xview` reproduces xView 185/185 on TOW02 export-v005 and 0/0 on the
  user's model (`jobs/vyatskaya-tow02/REVIEW-514.md`); the "area > 0" rule above is what missed them.
- **R17** proposal 2026-10-21, job/vyatskaya-tow02-midpoly - CLI command: run 3ds Max xView checks on an FBX in a
  separate Max instance via a startup script (`jobs/vyatskaya-tow02/scripts/xview_check.ms`; xView does not compute
  through the MCP bridge) with the "Disable xView" dialog answered, one JSONL line per checker; seen 3 times; effort S.
  Review #514: the shared runner already exists, `tools/qa/xview_dump.ms` + `tools/qa/xview_parity.py` (#380,
  tolerances set by script); `jobs/vyatskaya-tow02/scripts/xview_review.ms` duplicates it and adds `.max` loading,
  face centres per hit and the user's pre-export "Mesh + Weld 2 mm" mode checked on Editable Mesh (Poly re-splits
  non-manifold vertices); paths must be ASCII (Max 2024 misreads a Cyrillic jobs file). Left: fold those into
  `xview_dump.ms` and list it in `docs/agents/CAPABILITIES.md` (issue #528); seen 8 times.
- **R18** proposal 2026-10-21, review #514 - Artem's Blender add-on `xview_overlapping_faces_improved.py`
  (viewport overlay, 16 s on 35k faces vs xView 107 s) as an interactive helper: it finds 40 of 185 xView faces with
  0 false hits; to match xView it needs boundary contact counted (zero-area contact rule), a fixed 0.81 deg normal
  limit and a per-vertex plane test - or call `inv_xview` from it; evidence `outputs/review-v002/xcheck/XCHECK.md`
  (local); seen 1 time; effort S. Waits for the user's decision whether the add-on goes into the repository.
- **R19** proposal 2026-10-22, job/vyatskaya-tow02-review - pattern: root cause of one overlap defect of a built
  model: `inv_xview` pair -> part and z -> builder function and line -> the arithmetic that lands inside the 5 mm /
  0.81 deg window -> the user's hand fix in numbers -> a placement rule + a unit case; seen 4 times (railings,
  AC glass, louvre, band/glass, `jobs/vyatskaya-tow02/REVIEW-514.md` §7); effort S
- **R20** proposal 2026-10-22, job/vyatskaya-tow02-review - skill: review of a user's hand finish against our
  export (per-part BVH diff in a shared local frame, xView and `inv_xview` on both, checker parity, cause class
  per defect, time from transcripts, follow-up issues through the ready gate); seen 2 times (#424 retro, #514);
  effort M

## Harness and organization (default owner Codex)

- **H1** Validate the Codex PreToolUse hook (`.codex/hooks.json` → guard.py): payload
  fields, "ask" support. Record the result in `CAPABILITIES.md`.
- **H2** SketchUp MCP route: own venv for `adapters/sketchup/` (the old one stayed in the
  former AGR folder) and re-verify.
- **H3** `revit-twin` MCP: its source was on unmerged DT branch `feature/revit-workflow`
  (in `data/archive/DigitalTwinProject-Claude-all.bundle`); recover or drop the user
  registration that points at a removed worktree.
- **H4** Translate `docs/agr/` (brief, rules, ADRs, cases, case template) and Russian
  comments/READMEs in `technical_library/`, `tools/`, `jobs/` to English. Owner: Antigravity.
- **H5** CI: GitHub Actions failed with `startup_failure` (billing) in the old AGR repo.
  Decide hosted CI vs a local pre-push check.
- **H6** Herdr: re-point the Herdr workspace and plugin to this repo; verify the HUD.
- **H7** Tidy `tools/` by `docs/agents/NAMING.md`: stage subfolders, `<verb>_<subject>` names
  without versions or object codes (`git mv`, update `CAPABILITIES.md`, skills, tests); move
  one-off job scripts into `jobs/<JOB>/`; delete nothing that an accepted case cites.
- **H10** Shared VPM/NPM pipeline from `jobs/KPP1/scripts` and `jobs/PSU275/scripts` (duplicated
  `export_npm`, `make_npm_atlas`, `package_vpm`, `vpm_ucx`, `qa_master*`, `run_all`) into
  `tools/<stage>/`, parameters in `jobs/<id>/object.json`; regression: both objects give the same
  outputs and QA. Then rename job folders to object ids and tag `pipeline/vpm-npm-v1`.
- **H8** Machine-specific MCP paths in `.codex/config.toml` / `.agents/mcp_config.json`:
  document the install steps so another machine can reproduce them.
- **H9** Git LFS budget of the GitHub account is exhausted (push rejected 2026-10-06):
  raise the budget, move binaries to another store, or drop LFS patterns. Heavy data: legacy job outputs and Revit sources live in `jobs/*/outputs` and
  `data/` (local only). Decide backup (external disk / NAS / LFS) before deleting the old
  folders' last copies.
- **H11** Former projects, moved here on 2026-10-06: DigitalTwinProject (Claude,
  `C:\Users\artsafro\DigitalTwinProject`, archive `data/archive/DigitalTwinProject-Claude-all.bundle`) and
  AGR_Project (Codex, `C:\Users\artsafro\.AGR_Project`, archives `AGR_Project-all.bundle`,
  `AGR_Project-uncommitted-2026-10-06.zip`). The user plans to delete both folders; before that check the
  user-level configs that still point at them (H2, H3) and re-create the bundles if work continued there
  after 2026-10-06 23:24. Dropped on purpose: AGR process history, the Cursor verifier, the KPP1-VPM task,
  Codex `agent_monitor` (kept in the uncommitted-files archive).
- **H12** Branches not merged on purpose (user, 2026-10-07 [D006]): `claude/npm-models-school-kpp-ec9ced`
  (BUTOVSKAYA-NPM, work in progress), `claude/modest-ptolemy-684fb7` and `feature/kpp1-ground` (TEC26
  ground, adds `ezdxf`). Owner: user decides when to resume.
- **H13** (Claude) Rerun the merged `fix/export-safety` scripts on real data: KPP1 full `run_all.sh` on a new
  version, PSU275 v003/v004 re-assembly with `assemble_body_roof.py`; so far only synthetic tests pass.
