# TOW02: extracting engine capabilities from a panelised curtain-wall job

Research for #532, 2026-10-23. No engine modules, schema changes or implementation issues are created.

## Baseline and conclusion

Input baseline: linked parent PR #525, `job/vyatskaya-tow02-review` at
`9c7e9290b6cfcd3f4eee0e586791db70a820b880`, descended from pilot main `442f0b6`.
#525 was approved but still OPEN at measurement time; this is explicitly a parent-branch
analysis, **not** a claim that #525 is merged. The PR is stacked on that parent.

**Extract the measured-ring construction and explicit seam contracts, not the whole job.**
First establish source classification, correspondence and independently checked seams; then
port body primitives; then top/decor/loft; atlas last. Keep TOW02 measurements, part names,
material numbers, elevations, palette and placement recipe in the job. A tolerance change
alone cannot convert this panelised source into a measured, opening-sized building spec.

Primary evidence: [REVIEW-514 §§3,7,8](../../jobs/vyatskaya-tow02/REVIEW-514.md),
[STATE build log](../../jobs/vyatskaya-tow02/STATE.md),
[backlog P13/EG6/R11–R18](../backlog.md), [harness §16](../HARNESS_PLAN.md#16-уроки-кейса-alina-bld-решения-пользователя-2026-10-11-d050).
The historical 7,059 tracked / approximately 11,450 untracked lines are the review's inventory,
not a new LOC measurement and not a list of reusable modules. Untracked helpers are not a
stable engine API. The extractor saw 5,561 parts and no shell; 889 openings remained unsized,
zero decor was found, and the engine produced no final-model geometry. Successful direct Lego
construction is evidence for new capabilities, not evidence that the engine already supports them.

## Function-level extraction decisions

All targets below are **proposed** Python module paths under `dt_ai`; they are not implemented
by this note. G = general algorithm after parameterisation; O = object-specific recipe stays
in the job. Effort is engineering estimate including synthetic regression and one TOW02 replay:
S = 1–2 days, M = 3–5 days, L = 6–10 days; estimates overlap and must not be added mechanically.
The rows cover each requested extraction unit and split the large top/decor/atlas scripts into
separate decisions. Small arithmetic, Blender I/O and namespace-loading helpers stay private
implementation details, not one public engine module per `def`.

**Proposed fields**, marked NEW, are design inputs for future schema work, not accepted `Spec`
fields today. Existing v0.4 `floors[].contour/openings`, `levels`, `weld_m`, `plate_gap_m`, and
later `roof_structures` cannot encode edge correspondence, arbitrary attachment relations,
fin paths or measured pane sequences. Units are metres in an explicit building-local frame;
carry provenance and stable source/part/edge IDs before adapting to Blender or world coordinates.

| Job function / extraction unit | General or object-specific | Target engine module | Inputs / spec fields | Tests needed before promotion | Effort | Backlog coverage |
|---|---|---|---|---|---|---|
| `prepare` / ring-stack preparation (`build_body_blender.py:134–231`, `ring_columns`, `offset_points`) | G correspondence/columns; O CFG_TOW02, 56.7-degree frame, snap/collapse values | `geometry.ring_stack` | Existing levels/contours; NEW `ring_stacks[].rings` with base, band_h, ring_h, ordered edge IDs/intervals; NEW correspondence, snap_m, collapse_shift_m, max_side_m | Fixed-end union of all storey breakpoints; moving edges keep own columns; missing/reordered edge ID, unequal breakpoint count and all-moving unsupported cycle reject; input unchanged; collapsed jog preserves outline within declared bound | L | EG6 + P13; schema/correspondence contract is a gap |
| `build_stack` (`build_body_blender.py:381–466`) | G band/storey/reveal/glass assembly; O TOW02 collections/names | `geometry.ring_stack` | Rings above; existing opening_depth_default_m/IDs via adapter; NEW reveal_m, plane_overlap_m and shared seam IDs | Flat, corner, bent ribbon; inward reveal regression; entirely glazed loop (current start=None must not become silent omission); complete part accounting; preserve top/bottom seam; xView on joined output | L | EG6/P13; #530 owns shared seam policy |
| `_step` (`build_body_blender.py:495–514`, `_wide_strips`) | G corresponding-chain soffit/ledge; O threshold choices | `geometry.ring_steps` | NEW lower/upper column correspondence, join_z, chain fractions, min_strip_m; facade/roof IDs | Inward/outward winding, appearing/disappearing jog, unequal column counts must error rather than emit only a count_mismatch; every omitted strip reported; 4/6/10 mm strips and zero-area cases | M | EG6/P13 |
| `sliding_walls` / `snap_upper_cols` (`build_body_blender.py:326–378`) | G line-vs-endpoint motion distinction; O selected F8 policy values | `geometry.ring_steps` | NEW line_tolerance_m, collapse_m, seam constraints and ring edge IDs; not a replacement for spec.weld_m | End slides 5–50 cm while line moves 0–1.4 mm; line at/above tolerance, two-line corner, parallel intersection; top/bottom loops invariant; reproduce build-v026 F8 witness | M | EG6/P13; coordinate with #530, not a second seam policy |
| `resolve_tjunctions` / `pair_wall_points` (`build_body_blender.py:517–585,622–669`) | G seam-scoped conformity; O material-index exclusion must become semantic role | `ops.seam_conform` | NEW explicit shared seam graph, join planes, protected reveal boundaries, tj_tol_m; polygon mesh | T vertex and edge-interior/end threshold, multiple points sorted, existing shared indices, duplicate seam, both sides updated, no moved coordinates, no new non-manifold edge; combined glass-cleanup witness | M | P13 + R13 (detection only); constructive repair gap; #530 |
| `split_ngon` (`build_body_blender.py:672–769`) | G constrained quad-first partition; not an arbitrary polygon cure | `ops.quad_partition` | Polygon vertices/winding, protected boundary, min angle and triangle fallback policy; no new building field required | Concave/odd boundaries, collinear points, reversed winding, no legal diagonal, self-crossing reject; preserve area/boundary and minimise triangle count against brute force on small polygons; avoid exponential-size surprises | M | P13; R13 does not cover partitioning: gap |
| `seal_leftovers` (`build_body_blender.py:772–832`) | G narrowly recognised join repair; O always-down soffit assumption | `ops.seam_conform` | Declared expected openings, seam plane, outward role, reveal exclusion and repair limits NEW | Only explicit 4-edge hole/collinear T case; do not seal an intentional opening; 3-edge non-collinear/branched/unknown loop errors with coordinates; leftover count cannot be called clean | S | P13, R13 diagnostics; repair gap; #530 |
| `build_mesh` / Fin loft (`build_fins.py:439–515`, Fin ring/path methods, body_samples) | G measured path + profile morph; O 10/12-point notch profile, material IDs, colonnade Z_STEP and cap layout | `geometry.path_loft` | NEW `decor[].path_m`, profile keys/correspondence, morph stations, chord_tol_m, embed_m, host IDs, cap clearance; existing decor.profile/extent alone insufficient | Straight and S paths, changing slope/profile, chord-error sampling, cut/full transition, closed outward caps; per-vertex host embed and cap separation; 26-fin source-distance comparison; reject incompatible topology | L | EG6/P13; #531 host relationships reused |
| `build_walls` / `opening_planes` / zone layout (`build_top_blender.py:834–1125`) | G zone rows x columns and boundary seeding; O Z1–Z4, F/M edge numbers, band199 protrusion | `geometry.zoned_envelope` | NEW `envelope_zones[]` outline/rows with solid/opening/glass_face intervals and body seam IDs; reveal depth; existing roof_structures only for supported boxes/screens | Exact lower seam, shared zone columns, overlapping/gapped interval rejection; corner reveals, band/glass contact, full-height glass; no guessed IDs | L | EG6/P13; NEW zone schema is a gap; #530 |
| `fill_region` / `fill_strip` / `solve_parity` (`build_top_blender.py:390–433,781–819,1278–1285`) | G constrained cap mesh; O parity propagation chain among named TOW02 roofs | `geometry.quad_caps` | Boundary loops including holes, protected seam vertices, interior grid size and optional parity constraints NEW | Concave holes, odd counts, narrow ladder, holes not filled, unchanged boundary coordinates/indices, reported unavoidable triangles; area and no-crossing tests independent of triangulator | L | P13; quad cap coverage gap (R13 is diagnostic) |
| `sweep_coping` / `coping_path` (`build_top_blender.py:1135–1251`) | G mitred fixed-section sweep; O simplifying 10 cm jogs and inner_m=0.73 | `geometry.path_sweep` | NEW host boundary relation, measured footprint, section, closed/open path, end embed and minimum per-vertex clearance | Open/closed paths, reflex corners, self-crossing offset, tilted neighbouring glass; reproduce §7 A: centroid-only 6 mm move must fail minimum-vertex clearance | M | EG6/P13; #531 placement; do not port the known bad constant-offset recipe |
| `build_ac` (`build_decor_blender.py:228–350`; review fixes supersede glass/coping) | G host-bound basket planes/floor; O source #217/#198 envelopes and symmetry assumption | `geometry.attached_parts` | NEW attachments with host face ID/frame, measured profile, floor/coping/glass relation, shell thickness and embed; existing attachments are not built by from_spec | Asymmetric profile, missing host, basket front/glass rigid offset, actual floor winding; two independent DP simplifications must not erase clearance; §7 B including neighbouring coping | M | EG6/P13 + EG2; #531 owns relation contract |
| `build_louvre` (`build_decor_blender.py:431–551`; review-fixes build_louvre replaces plate recipe) | G repeat blade/rail boxes with host clipping; O 15/17 blades, levels, missing source plates | `geometry.attached_parts` | NEW louvre frame, blade/rail sections, stations, host references, embed and face clearance | No invented horizontal plates; ray misses named; lower rail vs soffit level collision (§7 C), rigid neighbour transforms, per-vertex distance at tilted ends | M | EG6/P13; #531 |
| `build_soffit` (`build_decor_blender.py:712–837`) | G exact-boundary underside + inner step + cap; O z=6.9, width/slab levels | `geometry.quad_caps` | Body bottom seam loop, NEW soffit inner offset, slab level, outward direction and holes | Preserve all 257 seam points on TOW02; narrow/reflex offset, odd boundary; fins contact, open reveal exclusion, outward underside; independent boundary/area check | M | EG6/P13; #530 seam ownership |
| `match_runs` (`texture_atlas_blender.py:224–282`, chains/lay_out/anchor) | G geometric run-to-face correspondence; O object names, families and fit tolerances | `uv.run_strip_atlas` | NEW measured window runs with stable IDs, pane u ranges/types, z ranges, face boundaries and coordinate frame; explicit exclusions/drop reasons | Reversed/open/cyclic runs, shifted seam, split 2.7+0.7 height, removed corner sliver, ambiguous/duplicate/missing run; every face and measured run accounted, not guessed | M | EG4/H10; P13 context; R11–R18 do not implement UV |
| `build_library` / run_segments (`texture_atlas_blender.py:324–429`) | G reuse measured strip subsequences; O body/ring/super frame/transom dimensions | `uv.run_strip_atlas` | NEW pane sequence/family catalogue with measured mullion/sash widths, palette/finish map and match tolerance | Unequal pane widths, whole-run quad versus fragments, corner jamb+jamb, no strip match error naming run/face; no uniform-pitch substitute; deterministic coverage | M | EG4/H10; extraction of pane measurements remains gap |
| `pack` / pieces_for / paint / finish_of (`texture_atlas_blender.py:434–577`) | G bounded packing/UV mapping; O 2048, TOW02 palette and output names | `uv.run_strip_atlas` plus Blender adapter | Profile texture size/padding, measured strips, face intervals, finish map, channel rules; no geometry change | Face too long fail; padding and UV nonzero/in-range; every material maps or named error; no cross-strip bleed; read PNG bytes + FBX UV back; dark coping regression §7/§1 | M | EG4/H10; no R11–R18 substitute |
| `clean` / join_corners (`clean_glass_blender.py:35–106`) | G flat=4 points / bent segmented / corner=6 points rule; O object list and 0.5-degree/2 mm/60 mm heuristics | `ops.seam_simplify` | Polygon mesh + NEW shared seam graph/protected boundaries, planarity/corner tolerances; derive glass runs from opening geometry | Flat/corner/bend, small true pane not a sliver, empty/unsupported/NaN reject; simplify BOTH band and glass seam atomically, then local xView; build-v016→v017 must expose 141 contact pairs before corrected extraction | M | EG6/P13; #530 owns this repair, not an independent glass-only port |

### Interfaces and failure policy

Future geometry primitives should return indexed polygon meshes, semantic face roles, stable
part/edge lineage, and explicit omissions/diagnostics; numpy kernels plus a bmesh adapter only
where necessary. Preserve one measured local frame through geometry and QA. A Blender scene
name is not a spec field. Do not transplant the job's `exec` namespace coupling or its implicit
material defaults. No promotion until a second synthetic shape and a TOW02 fragment both pass.

The future tests in the table are requirements, **not results of this analysis**. Include empty,
partial, unsupported, NaN/inf, threshold and duplicate-ID inputs; input/output/report/temp aliases
must error before writes, including absent input paths. Declared-but-not-run checks cannot count
as pass. Seal/repair must retain each element or report its drop reason, never silently delete it.
None of those future contracts is asserted to be implemented by the job scripts today.

R11/R15 are visual comparisons; R12 measures filtered source distance; R13 detects open edges/T
junctions; R14 versions scenes. They support module verification but do not implement geometry.
R16's old area-only description is explicitly superseded by its review amendment; R17 is the
native oracle runner (#528); R18's add-on finds only 40/185 faces and is not a clean gate.
Use existing `ops.inv_xview` contact semantics, not a new overlap approximation. D152 and
[validation](../domain/validation.md) require 2 mm vertex / 5 mm face checks; `inv_xview.py:9–29`
explains boundary contact, 0.9999 parallel cosine, local float precision and report-only versus
gating modes. Independently verify joins, not merely the separately clean parts.

## Measured weld replay: #401 / #403 / #416 do not clear it

Run: `uv run python tmp/tow02_weld_probe.py` on the immutable v0.4 `pipeline/spec-v002.json`
using `Spec.model_validate_json`, the actual `object.json` `BuildInputs.from_object`, and
`dt_ai.geometry.from_spec.build`. The short [rerun log](tow02-weld-rerun.log) records hashes,
version, exact exception, generated controls and before/after immutability check. This is a
fresh Python engine call, no Blender or source re-extraction; no model output is written.

Result: `BuildError: 2D plan weld moves [391.779, 147.796] by 0.003605551 m,
beyond weld_m 0.003 m; not built`. It happens in `_contours` → `_weld_plan` before mesh
construction. Schema validation succeeds: 21 floor records / 22 levels, plate_gap_m=0.005.
The original 64-minute run need not be repeated to exercise this exact failing code path.

The references are **PR numbers**, not extractor repair issues:

- [#401](https://github.com/artsafro/AGR-DigitalTwin-pilot/pull/401) characterises engine
  `_Weld` fixed-anchor priority and non-transitive 1D groups; tests only.
- [#403](https://github.com/artsafro/AGR-DigitalTwin-pilot/pull/403) documents checker,
  extractor and engine weld differences; documentation only.
- [#416](https://github.com/artsafro/AGR-DigitalTwin-pilot/pull/416) characterises extractor
  half-shift grids and wide-component fallback; tests only, no kernel replacement.

All three are merged on the measured baseline. None changes production code or re-extracts
this spec. The extractor's 3D shifted-grid weld and engine's 1D axis groups are different
contracts. Two axis moves can be individually legal while their Euclidean plan move exceeds
3 mm; `_weld_plan` intentionally rejects that. A finite 5×5 independent magnitude probe
(axes 0,1,2,2.9,3 mm, fixed anchor 0) gives **25/25 expected return/error outcomes**, including
exactly 3 mm axially and over-bound diagonals. This is bounded characterisation, not universal
NaN/unsupported-input assurance for `_Weld`.

Do not raise weld_m or relax the 2D guard in this analysis. The backlog statement that the
spec “cannot be built at all” is historical, not a proof over all valid weld_m values; merely
choosing a value between 3.606 and 5 mm can change groups and create another failure. A future
repair must measure the whole displacement distribution and check contour validity, seam
relations and sized openings, not just bypass the first exception. No such repair is claimed.

Minimal reproduction (same API path; an uncaught BuildError exits nonzero):

```python
import json
from pathlib import Path
from dt_ai.spec.model import Spec
from dt_ai.geometry.from_spec import BuildInputs, build
spec = Spec.model_validate_json(Path('jobs/vyatskaya-tow02/pipeline/spec-v002.json').read_text())
obj = json.loads(Path('jobs/vyatskaya-tow02/object.json').read_text())
build(spec, BuildInputs.from_object(obj))
```

## Proposed implementation sequence (titles + acceptance; not created)

1. **Panelised intake: measured rings and source-class contract** — classify shell-less curtain-wall
   input, preserve local frame and source IDs, expose unsized openings/absent decor as questions;
   validate corresponding rings on TOW02 plus a second synthetic tower, without assuming slab=shell.
2. **Register TOW02 dual benchmark: measured build-v030 and native-clean user reference** — pin
   hashes/parts/source frames and expected failures below, with separate geometric and xView scores.
3. **Seam graph and atomic join/simplification (#530 integration)** — all simplifications update
   both sides, coincident seams weld or explicitly separate beyond face tolerance; reproduce §7 D
   as RED and check joined result with native-equivalent contact QA. Reuse #527 gate, #528 oracle
   and #535 performance work; do not create parallel implementations of their responsibilities.
4. **Ring-stack body, ribbon reveals and sliding-wall steps** — generalise prepare/build_stack/_step
   on supplied measured rings, with F8 regression, unchanged endpoint seams and no omitted opening;
   report all deviations and triangles, compare local surfaces to build-v030.
5. **Boundary-preserving quad partition and cap primitives** — test odd/concave/hole boundaries,
   preserve shared seam vertices exactly and explicitly report unavoidable triangles/unsupported loops.
6. **Zone-driven top envelopes and single-section coping** — build top from measured zone spec,
   exact body seam and host-based coping relations; §7 A and D combined regressions stay clean.
7. **Host-derived attached baskets, rails, louvres and soffits (#531 integration)** — derive every
   neighbour from its host relation; §7 A/B/C plus tilted-end/rigid-fix witnesses check every vertex.
8. **Curved-path profile loft for facade fins** — measured path/morph, bounded chord error and host
   embed/cap clearance pass independent geometry checks on 26 TOW02 fins and a synthetic S path.
9. **Measured window-run strip atlas (EG4/H10)** — exact pane sequence and corner joints survive
   glass simplification; all faces/materials accounted, deterministic layout and fresh FBX/PNG readback.
10. **End-to-end panelised benchmark and retirement audit** — run intake→spec→engine→join→atlas→
    readback, score geometry and native contact independently, remove only proven EG6 subgaps;
    leave unmet manual gates and architectural differences explicit.

Dependency order: 1→2→3→4→5→6; 7 and 8 can run in parallel after seam/host interfaces are fixed,
9 follows stable glass topology and pane measurements; 10 joins all. Cap helper design can start
alongside body work but must not duplicate #530's seam ownership. No automatic resumption of
production or permission to change shared requirements follows from these proposals.

## Etalon and limits

Name **TOW02 build-v030 (`outputs/build-v030/tow02_tex.blend`)** as the measured master etalon
for **panelised, shell-less curtain-wall tower → mid-poly master**, with its matching
`export-v005/SM_Vyatskaya_Vl_47_49_013_Main.fbx`. Source measurements and the build-v013→v026→
v027→v028→v029→v030 chain belong in its benchmark provenance, not just the final mesh.
This note names the etalon; it does not modify protected `benchmark/` or claim a new DCC run.

Measured in STATE: F8 update 14,928→14,855 body faces, 69→0 strips under 6 mm, 0 new T vertices;
84/17,982 body vertices move, maximum 1.385 mm; endpoint seams and body glass unchanged.
Export-v005: 35,407 polygons (35,271 quads + 136 triangles), 44,000 vertices, one material.
The historical Blender readback differed from joined geometry by at most 0.07 mm; UVs were
in range. Build-v030 texturing keeps 31 source-run strips / 77.25 px/m and 873 matched window
faces from the preceding chain (STATE v018–v030); it is not a generic VPM-density certificate.

**It is not a clean target**: native Max xView found **185 overlapping faces / 0 vertex pairs**
on export-v005, despite job-local checks reporting zero. REVIEW-514 §3 reports `inv_xview`
185/185 with zero FP/FN on local coordinates; the parent rework replay confirms the retained
arrays, not a fresh production import. Keep those 185 faces as negative regression witnesses,
especially the 141 band/glass contact pairs (141 band faces and 12 glass faces) introduced by
independent glass cleanup at v017.
No module should be rewarded for copying those defects exactly.

Use the user's hand-finished 013 as a **separate QA/placement reference**, not silently rename
it build-v030: after Mesh + Weld 2 mm it has 0/0, before that it has five coincident vertex
pairs; converting back to Editable Poly splits them again. Its translation versus ours is
(4951.864,14903.346,165.443) m. REVIEW-514 records changed railings, raised louvre, top topology,
dark UV placement and sunk fins; neither triangulation count nor UV equality is a universal
geometry acceptance oracle. NPM candidate validation remains not passed in the parent delivery
report; “4+” master acceptance and “can work with this” do not approve the delivery package.

Limits: one tower/source class; no automatic extraction of all measurements; 1.5 cm B088
measurement gap; object-specific top/corner recipes and hand fixes; no UCX/VPM package coverage;
no new visual/manual gate signatures; no proof for arbitrary holes, topology, profile morphs,
material maps or site float32 coordinates. Keep geometric-distance/silhouette, native contact,
UV/palette and manual acceptance scores separate. Evidence is retained at
`C:/Users/artsafro/.AGR-DigitalTwin_pilot/jobs/vyatskaya-tow02/outputs/review-v002/`;
tracked review/state are the portable references. Never present an unavailable local file as
newly measured output. No model input was modified by this analysis.
