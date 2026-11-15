# Cell ground-vpm — Ground + MAF + Flora + UCX, VPM

The site's Ground surface, MAF and vegetation inside one VPM Ground FBX, with Ground-surface UCX;
external PNG UDIM sets, GeoJSON and optional Ground Light FBX in the VPM archive. Buildings and usable-roof
landscaping belong to [oks-vpm](oks-vpm.md). The paired atlas version belongs to [ground-npm](ground-npm.md).
Router: [scenarios.json](scenarios.json); procedure: [scenario skill](../../.agents/skills/scenario/SKILL.md).
`ready` means this routing card exists, not that a generic conveyor or an accepted complete site exists.

## Read first (in this order, only what the task touches)

1. [requirements-2026](../domain/requirements-2026.md), HP (VPM), and [npm-vpm](../domain/npm-vpm.md):
   Ground composition, area-dependent budget, external textures, names, placement and collision.
2. [TASK_TO_MODEL](../procedure/TASK_TO_MODEL.md): intake, all eight fixed gates and export evidence;
   [node R5](../procedure/node-r5-ground.md) for Ground construction.
3. [ground-surface](../domain/areas/ground-surface.md), [groundel-maf](../domain/areas/groundel-maf.md),
   [flora](../domain/areas/flora.md), [ucx](../domain/areas/ucx.md), [package](../domain/areas/package.md),
   [uv-textures](../domain/uv-textures.md) and [conflicts](../domain/conflicts.md).
4. Stage skills: [model-ground](../../.agents/skills/model-ground/SKILL.md),
   [model-maf](../../.agents/skills/model-maf/SKILL.md), [model-flora](../../.agents/skills/model-flora/SKILL.md),
   then [validate-delivery](../../.agents/skills/validate-delivery/SKILL.md).
5. Ordered route sources: [Ground events](../architecture/ground-route.events.yaml),
   [MAF events](../architecture/maf-route.events.yaml), [Flora events](../architecture/flora-route.events.yaml),
   [package events](../architecture/package-route.events.yaml); [decisions](../decisions.md), especially [D293].
6. Closest etalon below, with its source manifest, exceptions and unclosed gates. GeoAGR is read only
   when named by the task; it is not a mandatory agent tool.

## Rules that bind this cell

| Topic | Rule |
|---|---|
| Tools | Agent: Blender / Max / AGR Tools, chosen per step with a one-line why [D293]. No forced DCC. Confirm application, version, units, document and ownership read-only before DCC calls; save new versions only. |
| Order | Ground order, relief LAST: flat Ground → IDs/textures → projection onto relief → texture fix + skirt → UCX (VPM only) → MAF/Flora → NPM on atlas → export/checks/checker [D293]. |
| One Ground master | Ground geometry is the same in VPM and NPM; only the atlas and the UDIM unwrap differ [D293]. Before export an NPM version exists in the same coordinates: convert the placed VPM or place low/high versions together. |
| Master topology | Working masters use quads wherever possible. Triangles are allowed where unavoidable and must be reported per object (count and face share); any n-gon (>4 sides) fails the master check BEFORE export triangulation. Export triangulation remains separate. This is not permission to repair previously delivered objects [D312]. Record per-object triangle count and face share before export triangulation. |
| Ground UV | 4096 tile: quad side 3.8–4.0 m; UV islands may overlap/stack for tileable finishes, no UV-overlap check. Source: [Artem #1380](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/1380#issuecomment-6893094521), with [D021]. Measure actual density/padding: diffuse 512–1706 px/m [D160]; sequential UDIM from 1001, no mirrored islands, no visible seams. MAF/Flora tiles follow Ground [D210]; glass in 1001 without maps [D221]. |
| VPM budget | Whole Ground FBX non-UCX triangles (surface + MAF + Flora), area band from GND-06, reg pp.28–29; input area = S_ter - S_pz, not site area alone [D010]. Missing area is review, not a guessed ceiling. |
| NPM budget | Total ≤180 000 triangles; start surface 50k / MAF 60k / Flora 70k [D097]. Bring 2–3 options, Artem cuts [D167]; first lighten Flora copies, never delete plants merely to meet budget ([Artem #1412 item 10](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/1412#issuecomment-6892291256)). This is not the VPM budget. |
| MAF identity | No substitution [D164]; catalogue pick matches specification picture and DWG contour, dimensions ≤10 cm per axis [D094], lego decomposition/inserts [D165], approved shared material IDs [D168]. Authoring names `<spec position>_<catalogue id>_GroundEl` [D166] are not VPM export names. |
| Copies | Lightening (LOD / light NPM variants) is done only on library copies, never on library originals; job/project copies named `<original>__<job>` are listed in the job manifest so they can be cleaned after delivery [D301]. |
| Flora identity | Species, height/crown ±20% and colour per schedule [D099]; unspecified lawn-level beds are Ground texture, named plants/big bushes are models [D101]. NPM stars / default VPM shells [D102]; catalogue identity `confirmed-interim` [D311] is not geometric verification. |
| Flora opacity | Flora ALWAYS has an opacity map: NPM separate opacity forms the bush/crown silhouette, diffuse RGB with no alpha [D020]; VPM diffuse with alpha. Missing NPM opacity or missing VPM diffuse alpha = FAIL per [Artem #1412 item 6](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/1412#issuecomment-6892291256). This explicit answer resolves the choice for this card; C18/FLO-08 still describe the older review behaviour, not permission to omit opacity. |
| Interim maps | A delivery to Artem MAY carry interim (stand-in, D245) Flora maps; Artem checks the look at the end of the delivery, so replacing a stand-in is not a precondition of the delivery [D299]. Keep stand-ins labelled, red on the species sheet [D246]; map approval is byte/object-bound [D245]. |
| Collision | Ground surface only; MAF (including fences/canopies) have no UCX at any thickness [D298]; no vegetation or lighting UCX. Hulls closed, convex, no material slots; gaps 2 mm–1 cm [D098], one-sided Ground → UCX deviation ≤10 cm [D134]; UCX budget [D012]. No UCX in the NPM derivative. |
| Placement | Project DWG points; sink MAF/Flora 10 cm [D095]/[D100], delete MAF bottoms only below Ground [D096]. Flora random Z and ±10% scale, record seed. A placed object that does not land on the Ground surface is deleted and listed in the placement report [D302]; this is not budget-driven deletion. |
| Placement frame | Project boundary and zero from sources or ask [D293]. MSK-77 is not a vertical datum: keep height system unknown if unknown; project zero/h_relief and ground mark are separate [D279]. VPM Ground-local shared pivot, reset transforms, GeoJSON placement [D018]/[D135]. |
| Hand-off | The finished package goes to ARTEM, as an archive or as a 3ds Max scene with quads; Artem does the acceptance and the hand-off to the customer, the agent has no customer channel [D300]. Give the absolute versioned path; retain a quad review copy [D270]. |

The opacity and tile/stacking source comments above have **no D-id** in the current decision log yet;
do not invent one or claim that C18/its validator has already been aligned. Use the cited explicit user
answers for this route, record the implementation discrepancy and require manual evidence where automation
still returns review. All other unresolved source conflicts (for example C37 small level differences) stop
the dependent modelling choice; this card does not settle them.

## Fixed gates

Continue the one entry sequence: this card → `jobs/<ID>/TASK.md` / contract → `jobs/<ID>/job.yaml`.
Use [TASK_TO_MODEL gates](../procedure/TASK_TO_MODEL.md#gates-same-for-every-path), not a second checklist.

| Gate | Required evidence |
|---|---|
| `inputs` | Source paths/SHA-256, profile, units, sheet authority, plot/stage, coordinate/height facts; no inferred zero. |
| `parts` | PartsList with coverage, budgets, operations, questions; hash-bound user Gate 1 confirmation before build. |
| `operations` | Per-step chosen route/why, before/after invariants; failures roll back, deviations logged before continuing. |
| `budgets` | Measured master/profile/UCX triangles, material/texture/UV/density/skirt values against cited limits. |
| `export_readback` | New versioned exported files + hashes; fresh-process topology, UV, material and transform readback. |
| `report` | Commands, sources, drops, exceptions, checks and missing/manual items; QA/acceptance/publication distinct. |
| `visual` | Artem's hash-bound geometry/appearance acceptance, species sheet and source overlays; notification is not approval. |
| `checker` | Complete final SINTEZ on the same bytes AFTER visual acceptance, raw output + version/normalized receipt. |

Only all eight complete gates permit `passed=true`. `review`, `not_run`, unavailable checks and a successful
export process are not a pass. Preliminary SINTEZ diagnostics may precede visual review, not final SINTEZ.

## Route by stage

Rows preserve the Ground event map order. Read a command's `--help` and the cited job contract before use;
these are entry points, not argument-free production recipes. **RED** = no generic reviewed agr/dt command
for this stage on a new site; record the current manual/job route and evidence rather than invent a command.

| Stage | Route today and completion evidence | Status / limits |
|---|---|---|
| 1 — `sources` | `agr inspect`, `dt index-pdf`; copied SPOZU DWG → DXF intake with `tools/source/inspect_ground_dxf.py`, nested blocks/hatches/legends, coverings and planting sheets/specs inventoried. | Existing intake routes; source authority must be explicit. |
| 2 — `zero` | Read boundary and project ±0.000 from PZU/vertical planning or supplied relief; record area/height provenance with `src/dt_ai/core/heights.py` as arithmetic support. | **RED**: no boundary/zero command; inspect drawings and ask if missing or conflicting. |
| 3 — `surfaces` | Build flat Ground by coverings/hatches → material IDs; method C layered cake, nominal 6 mm offsets; preserve plot holes/contours, curbs, ramps, steps and walls. Use node R5 and model-ground in the chosen DCC. | **RED**: no generic coverings builder; job DCC construction. Hatch background colour is not line colour. |
| 4 — `quads` | Resolve triangles/seams/insets on flat Ground, retain quads where possible; record topology and contour checks. `agr ground` is the `dt ground v015` alias, not a new-site builder. | Vatutino-only replay; new-site cuts/pairing remain job DCC work, not automatic adoption of D157/D193 exceptions. |
| 5 — `textures` | Assign textures by approved ID; seamless tiling UV islands/UDIM, same finish aligned across boundaries; measure density/padding, inspect seams. | **RED**: no generic flat Ground ID/UV/texturing command; unwrap in DCC, existing job texture scripts are precedents. |
| 6 — `relief` | Project the already textured flat Ground onto source relief (Z-only, preserve XY/IDs/UV and layer offsets), then handle local level changes. Conform/BVH ray projection in chosen DCC with model-ground invariants; record projection misses and face-centre checks. | **RED**: no generic projection command. `agr ground` / `dt ground v015` are Vatutino-only and build relief before coverings; not the D293 new-site route. Flat only if confirmed by source/user, not by absence of marks. |
| 7 — `skirt` | Fix textures after projection; extrude every outer component perimeter ≥1 m down, inner holes excluded [D251]; VPM skirt placeholders averaged colour, 256×256, opaque. Read back every outer edge's drop. | `agr ground` covers its frozen Vatutino producer only; on a new site DCC work, inspect steep strips rather than assume skirt presence proves depth. |
| 8 — `ucx` | Build Ground-surface hulls in DCC, prior art `tools/blender/ucx_build.py` and Vatutino UCX reports; audit convexity/closure, coverage, gaps, budget, names and Ground → UCX distance independently. | **RED**: `agr ucx` is unavailable; v015 builder reports UCX not_run. Shared builder existence is not proof of real-site coverage. |
| 9 — `placement` | Follow MAF/Flora event maps and their skills: catalogue → matching/dimensions/IDs/maps → place from SPOZU on completed relief. `src/dt_ai/placement/engine.py` via `jobs/VATUTINO-SITE/place_site.py` is precedent. Every requested object is placed or has a reported drop/reason; apply D302 on misses. | **RED**: no agr/dt placement command. Job scripts/DCC, no implicit species/model substitution. Keep specification-to-instance identity before joining into VPM Ground. |
| 10 — `npm` | Before export, NPM in the same coordinates: conversion or parallel low/high placement [D293]. Ground atlas 2K; one GroundEl 512 atlas, one Flora 2048 atlas with separate opacity. `agr vpm-to-npm` exists for its atlas/derive contract; map job MAF/Flora explicitly. | Partial: no universal full-site converter. Lighten job copies only; count full NPM total, bring options to Artem. |
| 11 — `package` | Master QA before export: `runtime.master_topology(nodes)` or `uv run python tools/qa/master_topology.py MASTER.blend --out NEW.json`; retain quad master, triangulate derived exports only. Export/read back, then `agr package-vpm` / paired `agr package-npm` with their documented inputs. | VPM export names `SM_Address_Ground`, `SM_Address_GroundGlass`, `UCX_SM_Address_Ground_001..999`; authoring GroundEl/Flora suffixes are not VPM names. External PNG/GeoJSON/optional Light FBX; no synthetic missing Ground or customer data. |
| 12 — `validate` | `agr validate` / `tools/qa/validate_package.py` on package plus exported scene readback, `--ground-area-m2` from documented S_ter - S_pz; `dt qa xview` after each geometry write and on export [D152]. Inspect GND/MAF/FLO/UCX rows and manual V015/V016/V017, species/placement and opacity evidence. | Partial validators; xView thresholds 2 mm vertices / 5 mm faces. Fix failures or obtain explicit scoped decisions, never promote missing evidence to pass. |
| 13 — `sintez` | After Artem visual acceptance, run installed SINTEZ AGR Checker on exact exported bytes; capture raw results/tool version and unresolved checks, then archive/quad Max scene to Artem [D300]. | **RED**: no generic agr/dt SINTEZ command in this route; use installed checker/job integration after verifying its availability. Agent/code review is not Artem acceptance. |

## Etalons

- `jobs/VATUTINO-SITE/ground-v015-route-a-session-20261104.md`: Ground NPM/VPM accepted with UCX [D193].
  Its texel exception is hash/face-list bound, not a general exemption. Ground acceptance is not a complete
  Ground + MAF + Flora package pass; R02/R11 collision coverage/deviation remain unmeasured in that case.
- `jobs/VATUTINO-SITE/site-route-20261109.md`, `jobs/VATUTINO-SITE/placement-report.md` and
  `jobs/VATUTINO-SITE/flora-route-a-v004.md`: assembly/placement/stand-in precedent, not a new all-green receipt.
- `jobs/kasatkino-ground/LESSONS.md`: accepted flat underlay then Artem's Conform; supports the projection
  step's place in the route, not a generic projection tool.
- `jobs/silikatniy-uvk-pzu-viz/LESSONS.md`: hatch background/line colour and drawing-driven flat Ground lessons.
  A visualization-only scene is not a VPM delivery etalon.

## Evidence checklist

- [ ] Source manifest/hashes, plot/stage overlay, coverings/MAF/plant schedules with per-item source refs;
  boundary, project zero, ground mark and height system separately recorded.
- [ ] Gate 1 answer bound to PartsList; DCC route/one-line why per step; versioned outputs, no source/library edits.
- [ ] Flat textured master evidence before relief; XY/IDs/UV preserved through projection, misses and gaps measured;
  skirt depth per outer edge, curb/step/wall completeness, topology report before export triangulation.
- [ ] Per-object master triangle count/share, no n-gons; profile totals and VPM area operands, NPM options/decision.
- [ ] MAF/species matching, dimensions/colour, maps and stand-in sheet; job-copy manifest; placement seed, requested/
  placed/deleted counts and drop reasons; Ground-only UCX overlay, gap/deviation/budget evidence.
- [ ] Both profiles in the same coordinates, correct atlas/UDIM/opacity/names, units/reset transforms/shared pivot;
  hashes and fresh-process export readback. Review master is separate from triangulated delivery.
- [ ] Validator/xView raw reports with every non-pass, manual row evidence, Artem visual answer and final SINTEZ
  receipt for those same hashes; archive or Max quad scene absolute path to Artem. No customer-channel claim.

## Minimal contract (ask once, ≤5 questions, recommendation first)

1. **Sources/authority:** which SPOZU coverings/planting/vertical-planning sheets, relief, MAF and plant specs win;
   confirm boundary/stage, project zero and coordinate/height data. Recommend the project-marked sources.
2. **Scope and protected data:** Ground + which MAF/Flora, existing master and paired NPM; «Не трогать» = source DWG,
   accepted masters, library originals. Recommend one shared Ground geometry, derived job copies only.
3. **Library/budget:** unresolved catalogue/species/ID picks and VPM area operands; recommend matched originals,
   NPM 50k/60k/70k start and 2–3 measured options if over, Artem decides.
4. **Pilot/appearance:** which site patch end to end; confirm interim map labels and the review reference.
   Recommend one representative relief/material/MAF/Flora patch accepted before the rest.
5. **Acceptance/output:** archive or Max quad scene path to Artem; ask once whether to open each new stage scene
   for acceptance [D270], reusing any recorded answer. Recommend retaining both master and exported readback.

## Stop and ask

- Missing/conflicting boundary, project zero, authority, elevation marks, duplicate XY with contradictory Z,
  insufficient/collinear relief points, or projection misses: do not invent a flat site or silently move contours.
- Unanswered Gate 1, library/species mismatch, unknown material ID, unsupported UV/map binding or unresolved C37:
  identify the exact object/source and propose choices; never use the first catalogue entry as a default.
- Failed invariants, unapproved geometry change, unexplained relief/skirt/UCX defect or over-budget site:
  preserve failed evidence and propose bounded repairs/options. No blanket carry-over of Vatutino exceptions.
- Missing DCC/checker access or mandatory evidence: report the actual failure/owner. Do not turn unavailable,
  review or not_run into pass. Delivery with stand-in maps is allowed [D299], not a waiver of other gates.

## Known gaps (do not assume a tool exists)

No generic flat Ground → relief projection, site-wide placement or Ground UCX CLI; `agr ground` is a frozen
Vatutino replay and `agr ucx` is unavailable. MAF/Flora source matching, full row coverage and visual judgement
remain partly manual; `agr vpm-to-npm` does not automatically replace and seat every site asset. C18/opacity
implementation alignment and the #1380 shared UV-owner migration are not performed by this documentation card.
Accepted Ground geometry, technical QA, Artem acceptance and final delivery/checker status stay distinct.
