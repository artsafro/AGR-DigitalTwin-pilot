# Decision log

Every dated user decision, one line each, sorted by date. The line is a pointer, not the rule: the full text
lives where "Applies to" says, and that text carries the id (`[D012]`). ADRs (`docs/adr/`) stay for
architectural forks; conflicts keep their `C<N>` in `docs/domain/conflicts.md` and are logged here when decided.

Add a decision: next free id, the date the user decided, one sentence, the file or pattern it applies to, and the
source (PR, issue or `chat`). Put `[D<n>]` next to the decision in that file. Superseded decisions stay, with
"superseded by D<n>". Format and references: `tests/test_decisions.py`.

A decision found later than logged (#138) is appended with its own date and Source `backfill #138 (...)`; only such rows break the date order, and new
decisions follow them as usual.

Where the id goes, by kind of file (#138)

Markdown outside the excluded folders (`docs/agr/`, `docs/research/`, `jobs/`, `technical_library/`, `data/`,
handoff and project-state files) carries `[D<n>]` on the same line as the mention. Tracked Python does the same
in comments, docstrings and strings, except under `jobs/`, `technical_library/`, `data/`, `docs/agr/`
and the checker's own examples. `standards/material_id_ranges.yaml` carries the id in its
comment. Locked standards YAML is not edited: a top-level `conflicts:` entry whose note says "decided" must list
an `ids` number whose item in `docs/domain/conflicts.md` carries a `[D<n>]` from this log. JSON, `jobs/**` and
frozen fixtures (`tests/fixtures/` and `evals/*/fixtures/`) carry no id, for Markdown and Python alike.

| ID | Date | Decision | Applies to | Source |
|---|---|---|---|---|
| D001 | 2026-10-06 | Roles: Claude leads 3D/DCC production, Codex code and organization, Antigravity supports both | `docs/agents/ROLES.md` | chat |
| D002 | 2026-10-06 | Blender Online Access enabled | `tools/mcp/README.md` (Blender) | chat |
| D003 | 2026-10-06 | MCP routes for every listed DCC must be production-capable (create, edit, save, export); inspection alone is not completion | `tools/mcp/README.md` | chat |
| D004 | 2026-10-07 | While Codex is unavailable Claude takes its git and harness duties (branches, PRs, merges, state after merges) | `docs/agents/ROLES.md` | chat |
| D005 | 2026-10-07 | A name says what the thing does; object codes live only in data, never in shared names | `docs/agents/NAMING.md` | chat |
| D006 | 2026-10-07 | Branches `claude/npm-models-school-kpp-ec9ced`, `claude/modest-ptolemy-684fb7`, `feature/kpp1-ground` are not merged on purpose | `docs/backlog.md` H12 | chat |
| D007 | 2026-10-07 | PSU275 target profile: NPM and VPM | `docs/sources/psu275.md` | chat |
| D008 | 2026-10-07 | PSU275 geometry reference is Revit only; missing parts from the FBX | `docs/sources/psu275.md` | chat |
| D009 | 2026-10-07 | PSU275: work in the detached Revit 2025 copy; absolute mark from drawings, no MSK-77 yet; first-floor bounds by Claude | `docs/sources/psu275.md` | chat |
| D010 | 2026-10-07 | C1: the VPM triangle table is the hard limit; project target <= 150 000 triangles per OKS FBX in VPM as in NPM. Clarified 2026-10-15 (#141): 150 000 is the budget of the one mid-poly master per OKS FBX from which NPM and VPM are derived | `docs/domain/conflicts.md` #1, `docs/domain/npm-vpm.md`, `docs/domain/areas/body.md` BODY-G | chat |
| D011 | 2026-10-07 | C2: GeoJSON as the checker - OKS `FNO_code` mandatory, `act_AGR` may be empty, never invent | `docs/domain/conflicts.md` #2 | chat |
| D012 | 2026-10-07 | C3: UCX budget by the checker formula (< 50 000 -> 15 000, else min(ceil 5 %, 100 000)) | `docs/domain/conflicts.md` #3, `docs/domain/validation.md` | chat |
| D013 | 2026-10-07 | C5: NPM placeholders 128x128 (Metallic/Roughness only), VPM 256x256 | `docs/domain/conflicts.md` #5 | chat |
| D014 | 2026-10-07 | C6: NPM deliveries carry no normal map | `docs/domain/conflicts.md` #6 | chat |
| D015 | 2026-10-07 | C12: binary units (1 GB = 1024 MiB) | `docs/domain/conflicts.md` #12 | chat |
| D016 | 2026-10-07 | C13: `Glasses` GeoJSON as the checker (`[]` or one object keyed by glass material) | `docs/domain/conflicts.md` #13 | chat |
| D017 | 2026-10-07 | C14: VPM lights only in `SM_<Address>_Light.fbx`; any non-mesh in the main FBX fails | `docs/domain/conflicts.md` #14 | chat |
| D018 | 2026-10-07 | C19: VPM pivot as the checker (origin 0,0,0, bbox centre within 10 %, shared origin, Z = project zero) | `docs/domain/conflicts.md` #19 | chat |
| D019 | 2026-10-07 | C20: encode the missing YAML rules as the checker plus regulation limits | `docs/domain/conflicts.md` #20 | chat |
| D020 | 2026-10-07 | C21: no alpha in any NPM image; opacity as a separate `_o_` map | `docs/domain/conflicts.md` #21 | chat |
| D021 | 2026-10-07 | C26: cut VPM quads to about 4 x 4 m (1024 px/m; adapter default 3.9 m) | `docs/domain/conflicts.md` #26 | chat |
| D022 | 2026-10-08 | Strict level contour: with no full-height shape the extractor stops and the user gives `contour_at_m` | `docs/HARNESS_PLAN.md` §4 | PR #19 |
| D023 | 2026-10-08 | Projections not over the full storey height never change the contour; they are questions; `bands` only with a benchmark need and an ADR | `docs/HARNESS_PLAN.md` §4, pattern `contour-niche` | #6 |
| D024 | 2026-10-08 | Roof slopes up to 10 deg are one roof (area-weighted height); steeper parts are a question | pattern `parapet` | #9 |
| D025 | 2026-10-08 | A door recess from the floor (>= 1.9 m high, 0.7-3 m wide, one straight mouth) is an opening, not a contour notch | patterns `wall-from-contour`, `contour-niche` | #31 |
| D026 | 2026-10-08 | Spec opening = the hole with its frame; glass as `glass_w` / `glass_h` / `panes` | pattern `wall-from-contour` | #36, PR #39 |
| D027 | 2026-10-08 | Revit attachments by the main-walls hull rule | `docs/agents/CAPABILITIES.md` (Revit twin path) | PR #35 |
| D028 | 2026-10-08 | The body is the largest connected part of the source mesh; the other parts are attachments | `docs/HARNESS_PLAN.md` §4, `GLOSSARY.md` (BODY) | chat (plan grilling) |
| D029 | 2026-10-08 | The opening anchor is the hole in the body for any source; a plane or glass only gives `window_type` | `docs/HARNESS_PLAN.md` §4 | chat (plan grilling) |
| D030 | 2026-10-08 | Material IDs are a reading scheme of the working model; UDIM tiles and slots are assigned on export | `docs/adr/0001-material-ids-are-a-reading-scheme.md` | chat (plan grilling Q4) |
| D031 | 2026-10-08 | Every spec carries a mandatory `frame` (source -> object matrix from `object.json`); two specs are compared only in the object frame | `docs/HARNESS_PLAN.md` §3 | chat (plan grilling Q5) |
| D032 | 2026-10-09 | A projection or groove in section with depth and height both <= 0.10 m is relief, not a question | patterns `wall-from-contour`, `contour-niche` | PR #46 |
| D033 | 2026-10-09 | An inward shell offset that self-intersects (niche, corner) stops and asks | patterns `contour-niche`, `non-90-corner` | PR #48 |
| D034 | 2026-10-09 | The 0.20 m frame and 0.10 m depth thresholds stay, in `spec_extract` of the benchmark tolerances | pattern `wall-from-contour` | PR #40 |
| D035 | 2026-10-09 | Vent grilles are openings of kind `grille` | pattern `vent-grille` | PR #40 |
| D036 | 2026-10-09 | An opening across levels in a typical-floor template: ask before copying it up a run | pattern `typical-floor-repeat` | PR #48 |
| D037 | 2026-10-10 | C24 final: one opening depth per building; `npm_min` plane at full depth, `mid` at half; supersedes the same-day reverse | `docs/domain/conflicts.md` #24, `conflict-choices-2026-10-09.md`, pattern `opening-plane` | PR #52 |
| D038 | 2026-10-10 | Every slab (roof in a parapet, terrace) is inset - hole + plate, joint required, a solid slab fails; etalons that differ are fixed | pattern `roof-inset-plane`, benchmarks | PR #63 |
| D039 | 2026-10-10 | `plate_gap_m` / `plate_overlap_m` are building parameters of the spec, default 5 / 20 mm | pattern `roof-inset-plane` | PR #64 |
| D040 | 2026-10-10 | A benchmark etalon never comes from the engine; its README names the author | `docs/HARNESS_PLAN.md` §6, `benchmark/` | PR #61 |
| D041 | 2026-10-10 | Terrace = a floor-step ledge with a parapet; spec v0.4 `terraces: [{level, parapet_h_m}]` | pattern `terrace` | PR #59 |
| D042 | 2026-10-10 | Pattern `terrace` proven on benchmark `bench-b02t-terrace` | pattern `terrace`, `patterns/INDEX.md` | PR #61 |
| D043 | 2026-10-10 | Floor step: engine order step -> oblique wall -> terrace; ledge with the roof ID, soffit with the facade ID | pattern `floor-step` | PR #55 |
| D044 | 2026-10-10 | Markup helpers plan approved (HARNESS_PLAN §14, MH1-MH3), after the terrace | `docs/HARNESS_PLAN.md` §14, pattern `markup-helpers` | PR #60 |
| D045 | 2026-10-10 | Revit levels mapped by `object.json` `revit_levels`; `LEVEL_roof` = base + offset + volume / area | pattern `markup-helpers` | PR #69 |
| D046 | 2026-10-10 | A Blender B01 etalon made by Claude by hand from the brief proves the Blender route | pattern `markup-helpers` | PR #68 |
| D047 | 2026-10-10 | B01 first green run recorded as a case (a benchmark result, not a model acceptance) | `docs/cases.md` | PR #51 |
| D048 | 2026-10-11 | OD1: default opening depth 0.4 m; a source with no depth takes it, listed as "depth by default", never 0 | `docs/domain/conflicts.md` #24, pattern `opening-plane` | PR #76 |
| D049 | 2026-10-11 | Intake plan approved (HARNESS_PLAN §15, IN0-IN8); no own skill, extend `analyze-architectural-source` | `docs/HARNESS_PLAN.md` §15 | PR #70 |
| D050 | 2026-10-11 | The colleague's job on building OBJ03 (the first OBJ03 case in `docs/cases.md`) is a lesson: honest mixed mode with numbered engine gaps, `pipeline_gate`, job scripts committed before running | `docs/HARNESS_PLAN.md` §16, `docs/cases.md` | PR #73 |
| D051 | 2026-10-11 | Facade decor: one solid per element inset 0.02 m, body not cut, 5 mm off openings; projection <= 0.10 m (inclusive) is texture | pattern `facade-decor-inset` | PR #73 |
| D052 | 2026-10-11 | The first decor benchmark is a real facade fragment (K02, source and etalon separate files); synthetic B03 deferred | `benchmark/bench-k02-decor-fragment`, `benchmark/bench-b03-decor` | PR #73 |
| D053 | 2026-10-11 | K01: KPP1 material IDs from `jobs/KPP1/materials.json`; geometry thresholds = HARNESS_PLAN §5 starting numbers | `benchmark/bench-k01-kpp1` | PR #72 |
| D054 | 2026-10-12 | Split decor pieces merge: one section, one axis, gaps <= `plate_gap_m` x 12 = 0.06 m | pattern `facade-decor-inset` | PR #74 |
| D055 | 2026-10-12 | Decor ids by material: metal 16-20, plaster / stone / tile 26-30 | pattern `facade-decor-inset` | PR #76 |
| D056 | 2026-10-12 | A free-standing decor column is a box >= 2 m high, 0.05-1.5 m a side, its bottom on a `LEVEL_*` | pattern `facade-decor-inset` | PR #74 |
| D057 | 2026-10-12 | A projection over 0.8 m is no decor: an attachment candidate, listed in the report | pattern `facade-decor-inset`, `docs/backlog.md` EG2 | PR #74 |
| D058 | 2026-10-12 | One question per type: one kind and cross-section repeated is one question with count and positions | pattern `facade-decor-inset`, `docs/HARNESS_PLAN.md` §7 | PR #74 |
| D059 | 2026-10-12 | Decor elements meet by a run-in, not a gap (horizontal main, vertical subordinate; corner rule) | pattern `facade-decor-inset` | PR #75 |
| D060 | 2026-10-12 | Rule 3: a storey contour is its mid-storey section; a change only in the 0.3 m under the next level is the slab edge | `docs/HARNESS_PLAN.md` §4 | PR #81 |
| D061 | 2026-10-12 | Rule 4: `roof.parapet_thickness_m` measured as a mitred inset; unreadable -> the default, marked | `docs/HARNESS_PLAN.md` (spec v0.6) | PR #81 |
| D062 | 2026-10-12 | Rule 5: the extractor never substitutes a value; `--collect-stops` lists every stop, writes no spec | `docs/HARNESS_PLAN.md` §4 | PR #80 |
| D063 | 2026-10-12 | `%TEMP%\pytest-of-artsafro` stays inaccessible; pytest runs with a short `--basetemp` | `docs/agents/REVIEW_CHECKLIST.md` | PR #79 |
| D064 | 2026-10-12 | `pipeline_gate` does not cover a compromised environment (for example a fake `py` on PATH) | `docs/agents/CAPABILITIES.md` (Pipeline gate) | PR #79 |
| D065 | 2026-10-13 | One parapet thickness per building; a terrace parapet takes the same | `docs/HARNESS_PLAN.md` (spec v0.6) | PR #81 |
| D066 | 2026-10-13 | Rules 1-2: a panel facade without a shell is read by panels (`source_class: panelised`, `slabs`) | `docs/HARNESS_PLAN.md` §4 | PR #83 |
| D067 | 2026-10-13 | Roof screen enclosures are body silhouette: spec v0.7 `roof_structures`, `npm_min` planes and top, roof ids | pattern `roof-screen-enclosure` | PR #92 |
| D068 | 2026-10-13 | The building weld `weld_m` is 3 mm | pattern `roof-inset-plane` | chat |
| D069 | 2026-10-13 | A slab opening that is no shaft, with both sizes under 0.7 m, is no body opening; listed in the report | pattern `roof-inset-plane` | PR #83 |
| D070 | 2026-10-13 | OBJ03 decision 3a: OD1 applies; a source with no depth is no longer a question | `conflict-choices-2026-10-09.md` C24 | chat |
| D071 | 2026-10-13 | Five read-only subagents; only the main agent writes, commits and decides | `docs/agents/WORKFLOW.md` (Subagents) | PR #86 |
| D072 | 2026-10-13 | Disputed geometry: look first (isolated renders, views, sizes), then classify | `docs/agents/WORKFLOW.md` (Subagents) | chat |
| D073 | 2026-10-13 | Review procedure: rounds by risk, ceiling 3; P1 fixed in the PR, P2 to issues; merge on the user's command | `docs/agents/REVIEW_CHECKLIST.md` | PR #86 |
| D074 | 2026-10-14 | Events make skills and subagents mandatory (triggers table) | `docs/agents/WORKFLOW.md` (Triggers) | PR #107 |
| D075 | 2026-10-14 | Rule of three: repeated procedures become code, a skill or a pattern; the agent only proposes | `docs/agents/WORKFLOW.md` (Rule of three) | PR #107 |
| D076 | 2026-10-14 | Context rotation: `/handover` -> `/clear` -> «продолжай» or `/takeover` at a task boundary or 40-50 % context | `docs/agents/WORKFLOW.md` (Context rotation) | PR #107 |
| D077 | 2026-10-14 | Kanban board on GitHub Projects over the issues | `docs/agents/KANBAN.md` | PR #114 |
| D078 | 2026-10-14 | An auto-named worktree branch is renamed before its first commit; the agent proposes, the user confirms | `docs/agents/NAMING.md` | PR #107 |
| D079 | 2026-10-14 | OBJ03 by `from_source` is unsuccessful; `from_source` stays as an experimental start | `docs/cases.md`, `docs/agents/CAPABILITIES.md` | #117 |
| D080 | 2026-10-14 | Primitive first: reduction, not reproduction; the parts list is confirmed before any build | pattern `primitive-first` | PR #106 |
| D081 | 2026-10-14 | OBJ03: thin plates are opening ids; the storey band frame runs round the contour; pier steps 0.07-0.10 m kept | pattern `primitive-first` | PR #106 |
| D082 | 2026-10-14 | Silhouette test at 0.07 m in five views | pattern `primitive-first` | PR #106 |
| D083 | 2026-10-14 | About 12 section points describe a silhouette; the budget per group is the job's (OBJ03: total 150 000) | pattern `primitive-first` | PR #106 |
| D084 | 2026-10-14 | Nothing of the source is dropped: unreducible pieces kept as source faces, listed | pattern `primitive-first` | PR #106 |
| D085 | 2026-10-14 | By source modules: real sections, one mesh per run; joints superseded the same day by D080 | pattern `facade-decor-inset` | PR #106 |
| D086 | 2026-10-14 | A build by source modules follows the source: screens with no top get no top plane | pattern `roof-screen-enclosure` | PR #106 |
| D087 | 2026-10-14 | A terrace glass railing is one 20 mm plate per free side; frames and posts are texture | pattern `terrace` | PR #106 |
| D088 | 2026-10-14 | Every agent-facing document is in English; Russian only for human cheat sheets | `AGENTS.md`, `docs/prd/agent-ready-harness.md` | #118 |
| D089 | 2026-10-14 | Harness waves in order: context and memory -> evals and trace -> guardrails and tools -> process and readiness | `docs/prd/agent-ready-harness.md` | #118 |
| D090 | 2026-10-14 | Agent-ready = two capability evals green (B01 from the root; ticket to PR) | `docs/prd/agent-ready-harness.md` | #118 |
| D091 | 2026-10-14 | Harness work follows grilling -> to-spec -> to-tickets -> implement -> code-review | `docs/agents/WORKFLOW.md` (Loop) | chat |
| D092 | 2026-10-14 | Merges stay on the user's command; the only added autonomy is the spec's two escalation classes | `docs/prd/agent-ready-harness.md` | #118 |
| D093 | 2026-10-15 | A decor end at a building corner starts `plate_gap_m` (5 mm) off the wall face, beyond the weld (was 0.5 mm); the checker welds by distance | `docs/domain/patterns/facade-decor-inset.md` | #101 |
| D094 | 2026-10-15 | MAF overall dimensions may differ from the specification by <= 10 cm; Artem: "5-10 cm off the specification is fine" | `docs/domain/areas/groundel-maf.md` MAF-04 | #180, MAF grilling rounds 1-2 |
| D095 | 2026-10-15 | MAF placement: pivot at the lowest point raised by 10 cm, projected onto the Ground surface, so the MAF sinks 10 cm and its bottom faces are deleted; Artem: "fixed sinking 10 cm" | `docs/domain/areas/groundel-maf.md` MAF-23 | #180, MAF grilling rounds 1-2 |
| D096 | 2026-10-15 | Faces below the Ground surface (sunk MAF bottoms) are not 'open polygons' for the VPM open-geometry rule; Artem: "polygons that go under the ground are not visible" | `docs/domain/areas/groundel-maf.md` MAF-20; `docs/domain/conflicts.md` C38 | #180, MAF grilling rounds 1-2 |
| D097 | 2026-10-15 | Artem: "texel density is per linear metre: NPM 10-40 at 2K, VPM 520-1706 at 4K" — pixels per linear metre: NPM Ground 10-40 px/m with 2K textures, VPM 520-1706 px/m with 4K textures, consistent with [D021]; project note: "the NPM Ground budget is 180 000" triangles (reg p.7 §3.6), starting split surface 50k / MAF 60k / Flora 70k | `docs/domain/conflicts.md` #4 | #175, user (Artem), Ground grilling rounds 2-3 |
| D098 | 2026-10-15 | Artem: "UCX: as the regulation, except the gap - from 2 mm to 1 cm, the regulation's 0.02-1 cm is a typo" — gap between collision pieces 2 mm - 1 cm inclusive is the project rule; reg p.36 §13.4 has a typo; a check reports gaps outside the band (implementation out of scope here) | `docs/domain/conflicts.md` #15, `docs/domain/areas/ucx.md` R10 | #175, user (Artem), Ground grilling rounds 2-3 |
| D099 | 2026-10-15 | Flora matching: height and crown diameter may vary +-20 %; leaf/flower colour per spec or internet photo search for species | `docs/domain/geometry.md` | #187 (Flora grilling round 1 Q2; user Artem: "Height may vary +-20 %, crown diameter +-20 %; leaf/flower colour follows specification; without picture search species name on internet and match its look") |
| D100 | 2026-10-15 | Flora placement: SPOZU points have no rotation; authoring pivot on SPOZU point, slightly above lowest point to sink 10 cm into Ground; random Z rotation and scale +-10 % inside +-20 % tolerance; final FBX resets transforms and shares origin | `docs/domain/geometry.md` | #187 (Flora grilling round 1 Q6 and round 2 Q7-Q8; user Artem: "SPOZU points have no rotation; pivot on point, slightly above lowest point to sink into Ground when projected. random Z rotation and scale +-10 % inside +-20 % tolerance. sinking 10 cm as MAF") |
| D101 | 2026-10-15 | Flower beds: Ground texture when specification just says flower beds / small greenery; 3D models when plants are listed; big bushes always models | `docs/domain/geometry.md` | #187 (Flora grilling round 1 Q5; user Artem: "usually flower beds are Ground texture when specification just says flower beds / small greenery; models when it lists plants; big bushes always models") |
| D102 | 2026-10-15 | VPM bush: default is shell of NPM star; detailed model only on explicit request; study library VPM bushes and follow their logic (recommendation until then) | `docs/domain/geometry.md` | #187 (Flora grilling round 2 Q10; user Artem: "default VPM bush = shell of NPM star; detailed only on explicit request; study library VPM bushes and follow their logic, until then recommendation") |
| D103 | 2026-10-16 | Future Unreal interactive experience lives in separate repository, root placeholder removed | `docs/backlog.md` | artsafro/AGR-DigitalTwin#2 owner comment |
| D104 | 2026-10-16 | Done = NPM and VPM fully match the source, pass the SINTEZ AGR Checker and visually match the source; geometry is accepted by a person (visual and mathematical) first, SINTEZ last | `docs/grill/modeling-architecture-2026-10-16.md` Q1 | chat (grilling) |
| D105 | 2026-10-16 | The pilot becomes the main repository when the first vertical slice (Ground + MAF + Flora site) is delivered; until then only `src/`, `standards/`, `docs/domain/` count as portable | `docs/grill/modeling-architecture-2026-10-16.md` Q2 | chat (grilling) |
| D106 | 2026-10-16 | Geometry autoresearch stays off until a trusted automatic geometry metric exists (refined by D120) | `docs/grill/modeling-architecture-2026-10-16.md` Q3 | chat (grilling) |
| D107 | 2026-10-16 | Build by reducing the source (views, sections, then DCC); the spec extractor becomes the measuring tool for acceptance; `from_spec` stays a generator for simple boxes and benchmarks | `docs/grill/modeling-architecture-2026-10-16.md` Q5 | chat (grilling) |
| D108 | 2026-10-16 | The agent never edits a delivery mesh freehand: only operations from the menu, each with invariants checked before and after; a broken invariant rolls back and stops with a question | `docs/grill/modeling-architecture-2026-10-16.md` Q8 | chat (grilling) |
| D109 | 2026-10-16 | NPM opacity planes: see-through repeating parts (railings, rod ladders, grilles, AC screens, fences) are candidates by type, swapped largest triangle saving first until the NPM fits its budget | `docs/grill/modeling-architecture-2026-10-16.md` Q10 | chat (grilling) |
| D110 | 2026-10-18 | The operation library runs in headless Blender (bpy + bmesh) and is tested on synthetic inputs; 3ds Max stays for `.max` sources, the MAF / Flora libraries and the final xView review; FBX with readback between them | `docs/grill/modeling-architecture-2026-10-16.md` Q11 | chat (grilling) |
| D111 | 2026-10-18 | Decomposition works on one parts-list format fed by a structure reader for FBX / SKP (names, layers, components, materials, connectivity, sections; split by material id when there is no structure); an RVT is read directly as enrichment | `docs/grill/modeling-architecture-2026-10-16.md` Q12, Q13 | chat (grilling) |
| D112 | 2026-10-18 | When the album and the 3D model disagree the architect decides (most often the album wins); the agent works provisionally from the album and lists every discrepancy above tolerance as a question for the architect | `docs/grill/modeling-architecture-2026-10-16.md` Q14a | chat (grilling) |
| D113 | 2026-10-18 | Two lines after the pause: the Ground + MAF + Flora site locally on the board, the operation kernel in the cloud; every area is grilled before building | `docs/grill/modeling-architecture-2026-10-16.md` Q15 | chat (grilling) |
| D114 | 2026-10-18 | The three objects the user delivered (the 16-storey building of the sample sheet, the Butovskaya school, OBJ03) become benchmark triples: source + album + delivered ZIP and working 3ds Max scene, author the user | `docs/grill/modeling-architecture-2026-10-16.md` Q16, Q17, Q31 | chat (grilling) |
| D115 | 2026-10-18 | Open borders are normal at joints: an embedded face hidden in the neighbour is deleted; embed depth 10-20 mm; the operation invariant is visibility (borders hidden, deleted faces covered, no overlapping faces closer than 5 mm), not closure | `docs/grill/modeling-architecture-2026-10-16.md` Q18, Q18a | chat (grilling) |
| D116 | 2026-10-18 | Windows are never taken from the source: the agent measures each opening and places a library type taken from the album; a window not in the library is a question to the user | `docs/grill/modeling-architecture-2026-10-16.md` Q20 | chat (grilling) |
| D117 | 2026-10-18 | Textures are procedural recipes per finish type with parameters from the album (RAL colour, panel grid); panel joints are texture, not geometry | `docs/grill/modeling-architecture-2026-10-16.md` Q21 | chat (grilling) |
| D118 | 2026-10-18 | Cursor and Antigravity stay as workers with thin, cheap drivers (the Pi lane pattern), measured per card; routing by task kind; experimenter, hypothesizer, prompt-engineer and daily evaluator stay off until the benchmark triples exist | `docs/grill/modeling-architecture-2026-10-16.md` Q23 | chat (grilling) |
| D119 | 2026-10-18 | Every question to the user goes through the board dashboard: a Needs-you card with options and a link to a page with pictures; Telegram only notifies | `docs/grill/modeling-architecture-2026-10-16.md` Q24 | chat (grilling) |
| D120 | 2026-10-18 | Outside-expert research yields capped proposal documents, not PRs, each naming the number it should move and how to test it, about 70 % product methods / 30 % harness; experiments only on hypotheses the user picked, on the benchmark triples | `docs/grill/modeling-architecture-2026-10-16.md` Q25 | chat (grilling) |
| D121 | 2026-10-18 | Context diet: coordination rules cut to one page, a worker reads AGENTS.md + its area file + the card, state files generated from the board and git, base context per card <= 10k tokens | `docs/grill/modeling-architecture-2026-10-16.md` Q26 | chat (grilling) |
| D122 | 2026-10-18 | No paid CI: the merge gate is a local CI receipt (commit, commands, counts) in the PR; the broken GitHub workflow runs only on manual trigger; no self-hosted runner on a public repository | `docs/grill/modeling-architecture-2026-10-16.md` Q27 | chat (grilling) |
| D123 | 2026-10-18 | Open PRs by group: site line (#273 fix P1, #238, #239), checks that become kernel invariants (#226, #248, #228, #230, #231), parked with branches kept (#279, #260, #252), docs (#266, #280) | `docs/grill/modeling-architecture-2026-10-16.md` Q29 | chat (grilling) |
| D124 | 2026-10-18 | Weld or embed per joint by mesh cost: weld when it adds no or few edges on a simple grid, embed 10-20 mm when welding would cut extra loops into either mesh; unwrap convenience alone is no reason | `docs/grill/modeling-architecture-2026-10-16.md` Q30 | chat (grilling) |
| D125 | 2026-10-18 | Two human gates: the parts list before the build and one acceptance sheet after it (Face Orientation back-face counts, model over album facades, model vs source overlays, material ids vs the legend, sections at level marks, deviations, SINTEZ); only automatic checks in between | `docs/grill/modeling-architecture-2026-10-16.md` Q19 | chat (grilling) |
| D126 | 2026-10-18 | UCX, MSK-77 placement, lights and GeoJSON are code, not agent judgement: UCX boxes per part, placement by fitting the plan outline to the SPOZU footprint with the album zero mark, lights from the album and SPOZU, GeoJSON from object data | `docs/grill/modeling-architecture-2026-10-16.md` Q22 | chat (grilling) |
| D127 | 2026-10-18 | The album is read as a vector PDF (PyMuPDF, AutoCAD PDFIMPORT as fallback): its legend becomes the material list and part classes, its marks and dimensions the control points of acceptance, its callouts label the parts | `docs/grill/modeling-architecture-2026-10-16.md` Q14 | chat (grilling) |
| D128 | 2026-10-18 | The 16-storey building of the sample sheet is the first benchmark triple, OBJ03 the second (hard test) | `docs/grill/modeling-architecture-2026-10-16.md` Q17 | chat (grilling) |
| D129 | 2026-10-18 | Operation invariants also require quad-dominance (triangles only where unavoidable) and texel readiness (quad size limits per profile) | `docs/grill/modeling-architecture-2026-10-16.md` Q28 | chat (grilling) |
| D130 | 2026-10-18 | Project sessions and workers load only the 3D MCP servers: claude.ai connectors are off in the project settings (`disableClaudeAiConnectors`), and off on claude.ai for desktop and cloud sessions | `.claude/settings.json`, `docs/grill/modeling-architecture-2026-10-16.md` Q33 | chat |
| D131 | 2026-10-19 | Kernel operations are pure numpy functions on the meshes of `dt_ai.ops.invariants`; bmesh only through an adapter for booleans, extrusion and solidify | `src/dt_ai/ops/operations.py` | user (Telegram 2026-10-19), confirming PR #290 "Decision to confirm"; #292 |
| D132 | 2026-10-19 | (decided 2026-10-16, recorded 2026-10-19) For a deep panel-contour recess, the user checks the drawings to clarify whether it is a niche or a missing wall; the extractor stops and asks rather than deciding | `src/dt_ai/spec/mesh.py` `_panel_contour` | [PR #274](https://github.com/artsafro/AGR-DigitalTwin-pilot/pull/274), User decision (2026-10-16, #85) |
| D134 | 2026-10-19 | UCX R11-R13 distance limits are one-sided, model surface -> UCX: Ground <= 10 cm, pedestrian-reachable OKS <= 30 cm, remaining OKS <= 1 m. Exposed UCX -> model distance is diagnostic only, not a tolerance failure; target completeness and functional-void preservation still apply | `docs/domain/areas/ucx.md` R11-R13, `docs/domain/geometry.md`, `src/dt_ai/geometry/ucx_build.py` | user 2026-10-19, #166 |
| D135 | 2026-10-19 | (decided 2026-10-16, recorded 2026-10-19) Transform rotation is 0 for both NPM and VPM after reset; geometry is rotated to DWG contour during placement and reset bakes plan angle into vertex positions | `docs/domain/conflicts.md#npm-vpm-plan-rotation-after-reset`, `docs/domain/validation.md`, `docs/domain/areas/derivation.md` DER-07, `docs/domain/geometry.md` | #214 (user Artem) |
| D136 | 2026-10-08 | An opening across a level is one record in the lower floor, with `level_from` and `level_to` (spec v0.2) | pattern `wall-from-contour` | backfill #138 (src/dt_ai/spec/model.py; src/dt_ai/spec/openings.py; spec v0.2) |
| D137 | 2026-10-08 | Glass panes of one frame (gap <= 0.15 m, aligned) are one opening (#31) | pattern `wall-from-contour` | backfill #138 (src/dt_ai/spec/openings.py; #31) |
| D138 | 2026-10-08 | No Rhino verdict; the match / install-Rhino criterion applies only after Revit walls come from location lines (#29) | `src/dt_ai/spec/compare.py` | backfill #138 (src/dt_ai/spec/compare.py; #29) |
| D139 | 2026-10-08 | One questions file per object is merged from versioned spec reports (#7) | `src/dt_ai/spec/questions_file.py` | backfill #138 (tests/test_spec_questions_file.py; src/dt_ai/spec/questions_file.py; #7) |
| D140 | 2026-10-09 | The window-type library (#4) reads `Win_Typical.max` only, names types by form and size with no project, treats the same subdivision within 2 cm as one type, counts fields from the row under the fanlight, keeps a balcony door and window as one frame, and leaves every entry unconfirmed until the user names it | `tools/library/build_window_types.py` | backfill #138 (tools/library/build_window_types.py; tests/test_window_types.py; #4) |
| D141 | 2026-10-09 | An NPM shell open at its reveals has no closed section in a window band, so a height open on both sides is listed and not judged | `src/twinqa/geometry/checks.py` | backfill #138 (src/twinqa/geometry/checks.py) |
| D142 | 2026-10-12 | Decor set into the body is judged against the body (the storey contour), with no numeric depth bound (#76, #78) | `src/twinqa/geometry/checks.py` | backfill #138 (tests/qa/test_from_spec_decor.py; src/twinqa/geometry/checks.py; #76, #78) |
| D143 | 2026-10-13 | The build path by source modules sits beside `from_spec`, measures the spec by the same modules, and builds a textured band 0.04 m thick; D079 later closed OBJ03 by this path as unsuccessful | `src/dt_ai/geometry/from_source.py` | backfill #138 (src/dt_ai/geometry/from_source.py) |
| D144 | 2026-10-13 | The material-id ranges cache follows the file: one parse per path and version | `src/dt_ai/spec/mesh.py` | backfill #138 (src/dt_ai/spec/mesh.py; tests/test_spec_contour_shapes.py) |
| D145 | 2026-10-13 | A face piece with one side a point on a strip line is a triangle (a pointed corner, PR #100) | pattern `non-90-corner` | backfill #138 (src/dt_ai/geometry/from_spec.py; tests/qa/test_from_spec.py; PR #100) |
| D146 | 2026-10-13 | On the experimental from_source path only (build="from_source"), a decor mesh was left out of the body topology checks, because the body is never cut (OBJ03 2a); rejected for delivery acceptance by D079 (#117): a new passing model needs topology on every mesh incl. decor, and from_spec keeps the strict checks | `src/twinqa/geometry/checks.py` | backfill #138 (src/twinqa/geometry/checks.py; OBJ03 2a) |
| D147 | 2026-10-13 | On the experimental from_source path only (build="from_source"), an open loop flat on a horizontal face at its height was closed by contact (seated: a wall standing on a slab); from_spec keeps the strict open-edge rule, and after D079 (#117) this does not relax topology acceptance of a new delivery | `src/twinqa/geometry/checks.py` | backfill #138 (src/twinqa/geometry/checks.py) |
| D148 | 2026-10-14 | An overlap is a crossing deeper than the weld: faces within weld_m are one weld, and a plate plate_gap_m off a face is no overlap | `src/twinqa/geometry/checks.py` | backfill #138 (src/twinqa/geometry/checks.py; tests/qa/test_from_source.py) |
| D149 | 2026-10-14 | A panelised source is checked with basis spec, because its sections never close | `src/twinqa/geometry/checks.py` | backfill #138 (src/twinqa/geometry/checks.py) |
| D150 | 2026-10-20 | Vatutino Ground only: accept the 12 steep/flatter-junction vertices and their 6 associated face centres at the measured gaps in the frozen exception manifest, explicitly pinned by source/geometry and sample IDs; keep the 20 mm gate for every other sample and all lower-bound/other gates unchanged. This is not a general spacing-rule relaxation | `jobs/VATUTINO-SITE/ground-gap-exceptions.json`, `jobs/VATUTINO-SITE/ground-build-v014.md`, `jobs/VATUTINO-SITE/build_ground.py` | Artem option a, card #295 comment 2026-10-20; D150 reserved in [PR #308](https://github.com/artsafro/AGR-DigitalTwin-pilot/pull/308#issuecomment-6282784444) after checking open-PR reservations D136-D149 |
| D153 | 2026-10-19 | (decided 2026-10-19, recorded 2026-10-20) Relief/layer-step tolerance is 1 cm: add TIN-edge cuts only in 4 m cells deviating by more than 1 cm; other cells stay 4 x 4 m; method C remains. Required TIN edges may be closer than 1 m in those correction cells (orchestrator clarification, not a user minimum-spacing rule) | `src/dt_ai/geometry/ground_cake.py`, `tests/test_ground_cake.py` relief refinement | backfill #337: Artem "разница в 1 см не страшна", [#295 comment 6265799957][ground-refinement-source]; [#308 clarification](https://github.com/artsafro/AGR-DigitalTwin-pilot/pull/308#issuecomment-6267750172) |
| D154 | 2026-10-19 | (decided 2026-10-19, recorded 2026-10-20) On steep relief raise a layer locally so the normal gap to the base is 5-20 mm (V004 band); flat ground keeps nominal +6 / +12 mm. D150 remains a separate frozen Ground exception, not authority for this earlier rule | `src/dt_ai/geometry/ground_cake.py` `raise_steep_layers`, `tests/test_ground_cake.py` | backfill #337: Artem "on steep relief raise a layer LOCALLY", [#295 comment 6274902891][ground-gap-source]; [#308](https://github.com/artsafro/AGR-DigitalTwin-pilot/pull/308#issuecomment-6274902436) |

[ground-refinement-source]: https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/295#issuecomment-6265799957
[ground-gap-source]: https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/295#issuecomment-6274902891
