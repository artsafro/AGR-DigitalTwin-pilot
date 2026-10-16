---
name: model-maf
description: 'Produce MAF (small architectural forms) from the specification and the SPOZU points: library pick or a new model, dimension check, light version, one 512 atlas, placement with sinking, checks. Use when: «сделай МАФ по спецификации», «подбери МАФ из библиотеки», «расставь МАФ по СПОЗУ».'
---

# Model MAF from the specification

The user's MAF practice (MAF grilling notes, [D094], [D095], [D096]) as a procedure. The rules live in the
[MAF sheet](../../../docs/domain/areas/groundel-maf.md) (rows `MAF-01`..`MAF-24` and its
[Project practice](../../../docs/domain/areas/groundel-maf.md#project-practice) section) and in
[the decision log](../../../docs/decisions.md); each step names the rows it must satisfy instead of restating them.

Out of scope here: producing MAF for a delivery is the job, not this file; the library audit itself
([#183](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/183)); Ground (`model-ground`); Flora
(`model-flora`); light-source FBX (MAF-24).

## Route markers

Every step carries three lines:

- `Route:` the tool route that exists today ([CAPABILITIES](../../../docs/agents/CAPABILITIES.md), headless smoke
  table). DWG through the AutoCAD 2025 core console (`dcc_batch.py acad`, `DXFOUT`) plus `ezdxf`
  (`uv run --extra cad`); scenes through 3ds Max batch (`dcc_batch.py max`, on a copy; the startup
  `polyunwrapper_autoload.mse` error is known, read the log) or Blender headless
  (`blender --background --factory-startup`). Live programs only through `max_exec.py` / `blender_exec.py`
  after a `--ping` (COORDINATION_RULES 22); before any DCC write apply the
  [DCC gate](../../../docs/agents/WORKFLOW.md#gate-dcc-authorization).
- `Needs:` `headless` (an agent runs it today), `live` (the program open by the user), `human` (a user decision or
  a visual look). `no tool yet` means the route exists but no reviewed script does the step.
- `Done when:` the evidence that closes the step.

Work on copies of the user's scenes and drawings (hash the original before and after); every output goes to a new
versioned path outside git (`C:/x/<card>/` or `jobs/<JOB>/outputs/`, both untracked). No PNG, MAX or FBX is
committed.

## Steps

### Step 1 — Specification and SPOZU MAF points

Read the specification rows: name, manufacturer link or picture, overall dimensions L/W/H, colour, material layout,
construction. An individually made MAF carries an attached reference or a scheme in the drawing legend. Read the
SPOZU MAF points: one INSERT per MAF on the MAF layers, with block name, count, insertion XY, rotation about Z
(MAF inserts do carry rotation, unlike Flora points) and block scale. Count nested inserts. Check `$INSUNITS`
against the coordinates (a drawing can declare millimetres while its coordinates are metres) — human when they
disagree. Lamps on lighting layers are MAF-24 geometry only.

- Route: DWG copy -> `dcc_batch.py acad` (`DXFOUT`) -> `ezdxf` (INSERT by layer or block name, nested inserts included).
- Needs: headless; human when `$INSUNITS` and the coordinate magnitude disagree, or a block cannot be matched to a row.
- Done when: a table spec row -> SPOZU block -> count -> rotations, with mismatches listed for the user.

### Step 2 — Pick from the library

The entry point is the audited catalogue `library/maf/catalogue.json`
([#183](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/183)): `spec_matches` are dimension-only
candidates, `npm_matches` are NPM .blend candidates, and previews plus per-MAF .max/FBX paths sit outside git. A
dimension candidate is not a match: compare the preview with the specification picture (construction, shape). Where
the catalogue does not reach (a new library scene, a missing entry): visual selection in a copy of the user's
library scene `МАФы_Union_ALLin.max`, the way the user does it. The catalogue is a technical audit, not
identification and not acceptance.

- Route: catalogue JSON lookup of `library/maf/catalogue.json` plus preview images; `dcc_batch.py max --scene <copy>.max` for a scene read.
- Needs: headless for candidates; human for the visual choice when several candidates remain.
- Done when: every spec row has a catalogue id (with the reason) or is listed for Step 3.

### Step 3 — Model from the reference

A MAF missing from the library, or individually made: model it from the manufacturer picture and the dimensions, or
from the legend scheme of the drawing. Silhouette first (MAF-03), metres (MAF-04). Every individually made MAF goes
to the user as a separate verify line — always, even when all checks pass.

- Route: 3ds Max batch or Blender headless (primitives and extrusions from the scheme).
- Needs: human (reference reading and the look), no tool yet.
- Done when: the model exists at a new versioned path, its source reference is recorded, and its separate verify line is opened.

### Step 4 — Check against the specification

Overall dimensions within 10 cm per axis [D094] (MAF-04). Plan L/W may be swapped (the plan orientation comes from
the SPOZU rotation); height is not swapped. A spec dimension that is missing becomes `review`. Compare colour,
material layout and construction with the specification picture (human). A model outside the tolerance is not scaled
in silence: rescale only uniformly and only with a recorded reason, otherwise go back to Step 2 or Step 3.

- Route: bounding box from the catalogue (`dims_m`, `fbx_readback_dims_m`) or a 3ds Max batch / Blender headless readback.
- Needs: headless for the numbers; human for colour, material layout and construction.
- Done when: per MAF measured L/W/H, spec L/W/H, max deviation, and a verdict pass / fail / review.

### Step 5 — Light version for the NPM budget

NPM and VPM ideally share one model. When the MAF total pushes the NPM Ground budget (MAF-07, the planning MAF
share of [D097]), make a light version: fewer segments, simpler round parts, until it fits. Count triangles per MAF
times the instances from Step 1. Prefer an existing NPM candidate (`npm_matches`). The silhouette stays (MAF-03).
The light version goes back through Step 4.

- Route: 3ds Max batch (ProOptimizer or segment edits on a copy) or Blender headless (Decimate or rebuilt primitives).
- Needs: headless, no tool yet; human for the silhouette look.
- Done when: a table MAF -> tris full / light -> instances -> total against the MAF share, and the NPM total under the budget.

### Step 6 — Shared 512 atlas

One texture set for all GroundEl at 512 (MAF-09), RGB only ([D020]). List every material the MAFs use (wood,
coloured plastics, metal, signs and the rest): solid colours get 64 or 128 squares, patterned textures get larger
slots; then map the UVs of each MAF into its slot. Embedding in the Ground FBX comes later (MAF-13).

- Route: `tools/materials/atlas_maf.py` (material list -> PNG + UV JSON); UV remap in 3ds Max batch or Blender headless.
- Needs: headless for packing; no tool yet for the UV remap; human for the visual check.
- Done when: one 512 RGB atlas, the UV JSON, and every face of every MAF inside its material's slot.

### Step 7 — Hard edges by angle

Hard edges by angle 30-45 degrees (smoothing, MAF-20). Round parts with N segments meet at 360/N degrees: they shade
smooth only when 360/N is below the threshold (at 45 degrees N >= 9, at 30 degrees N >= 13). A light version with
fewer segments shows facets: pick the threshold inside the band and show the user.

- Route: 3ds Max batch (Smooth modifier, auto smooth threshold) or Blender headless (`shade_smooth_by_angle`).
- Needs: headless; human for the look of light round parts.
- Done when: the threshold is recorded per MAF, and no smoothing group crosses an edge sharper than it.

### Step 8 — Placement from SPOZU with sinking

Move the pivot to the horizontal centre of the MAF, down to its lowest point, then up by 10 cm [D095] (MAF-23).
Place that pivot on the SPOZU insertion point together with its rotation, and project the pivot onto the Ground
surface from `model-ground`, so the MAF sinks by 10 cm. Delete the bottom faces that lie under the Ground. A face
is deleted only when all of its vertices are below the Ground at their own XY; a face with any vertex at or above
the Ground stays — a visible hole is a defect [D096] (MAF-20). On a slope the downhill side sinks less: where a
bottom vertex ends above the Ground, the open bottom would show — list it for the user (deeper sinking or a skirt
is the user's call) and never delete it. The placement pivot is temporary and is not the final shared FBX pivot
(MAF-23).

- Route: 3ds Max batch or Blender headless reading the Step 1 point table; Ground heights by a downward ray onto the Ground from `model-ground`.
- Needs: headless, no tool yet; live when the user checks the scene.
- Done when: instance count per spec row equals the SPOZU count, sinking of 10 cm is measured at every pivot, the deleted face count per MAF is recorded, and the list of exposed bottoms is empty or answered by the user.

### Step 9 — Checks before handover

Read back the exported Ground FBX (not the working scene) and go through the sheet rows: completeness against the
specification (MAF-02), scale and dimensions (MAF-04), scene structure (MAF-05), GroundEl/GroundElGlass split
(MAF-06), budgets (MAF-07, MAF-08), one 512 set (MAF-09), names (MAF-11, MAF-12), embedding (MAF-13),
triangulation (MAF-18), transforms (MAF-19), topology, smoothing and sunk bottoms (MAF-20, [D096]), no MAF
collision (MAF-22), placement (MAF-23). Verify lines for the user: one per individually made MAF from Step 3,
always a separate verify line, plus every review row.

- Route: `validate_package.py` through the [validate-delivery](../validate-delivery/SKILL.md) skill; Blender headless readback and renders; MAF checks of [#185](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/185) when merged.
- Needs: headless for the machine checks; human for the visual review and every verify line.
- Done when: a report with every listed MAF row as pass / fail / review / not checked, with evidence; `passed` only when nothing is fail, review or not checked; each individually made MAF has its own verify line.

## Report

Per step: the route actually used, inputs with hashes, counts, and what is left for the user. The individually made
MAF list is written as separate verify lines. A dry walk of this procedure on one urn:
[model-maf dry walk](../../../docs/research/model-maf-dry-walk-2026-10-16.md).
