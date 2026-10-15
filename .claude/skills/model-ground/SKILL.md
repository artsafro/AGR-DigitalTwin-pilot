---
name: model-ground
description: 'Build a Ground surface (благоустройство) from the SPOZU DWG by the layered-cake method, one master for NPM and VPM. Use when: «сделай Ground по СПОЗУ», «построй благоустройство», «слоёный пирог для Ground», «спроецируй Ground на рельеф».'
---

# Model Ground from SPOZU

The user's practice (Ground grilling 2026-10-15) as a procedure. The rules live in the
[Ground surface sheet](../../../docs/domain/areas/ground-surface.md) (rows `GND-01`..`GND-12` and its
"Project practice" section) and in [the decision log](../../../docs/decisions.md); each step names the rows
it must satisfy instead of restating them. GROUND-PROJECTION is a source of lessons, never a reference
result ([case study](../../../docs/agr/case_studies/GROUND_CONTOURS_AND_NPM.md)).

Out of scope here: MAF ([sheet](../../../docs/domain/areas/groundel-maf.md)), Flora
([sheet](../../../docs/domain/areas/flora.md)), collision construction ([UCX sheet](../../../docs/domain/areas/ucx.md)).

## Route markers

Every step carries two lines:

- `Route:` the tool route that exists today ([CAPABILITIES](../../../docs/agents/CAPABILITIES.md),
  headless smoke table). DWG is read through the AutoCAD 2025 core console (`dcc_batch.py acad`, `DXFOUT`) plus
  `ezdxf` (`uv run --extra cad`); meshes through 3ds Max batch (`dcc_batch.py max`) or Blender headless
  (`blender --background --factory-startup`). Live programs only through `max_exec.py` / `blender_exec.py`
  after a `--ping` (COORDINATION_RULES 22); before any DCC write apply the
  [DCC gate](../../../docs/agents/WORKFLOW.md#gate-dcc-authorization).
- `Needs:` `headless` (an agent runs it today), `live` (the program open by the user), `human` (a user
  decision or a visual look). `no tool yet` means the route exists but no reviewed script does the step.

Work on copies; every output goes to a new versioned path under `jobs/<JOB>/outputs/`. Record per step the
route actually used and its evidence (counts, hashes, renders) for the hand-over report.

## Steps

### Step 1 — SPOZU DWG intake

Copy the SPOZU DWG, export the copy to DXF with the core console, open the DXF with `ezdxf`. Find the
coverings sheet (a layout) or work through model space; inventory layers, hatches, planting points, MAF points
and the plant/MAF specification tables. SPOZU geometry often sits inside block references: count entities
through `INSERT` virtual entities, not model space alone.

- Route: `dcc_batch.py acad --dwg <copy> --file dxfout.scr` (`DXFOUT`), then `ezdxf` inventory.
- Needs: headless; human when several layouts could be "the coverings sheet".
- Done when: a layer inventory with entity counts per type (including nested ones) and the chosen sheet are recorded.

### Step 2 — Boundary layer

Take the designed-plot boundary: a layer named like «граница проектируемого участка» / «граница ГП». It
sets the Ground extent ([GND-01](../../../docs/domain/areas/ground-surface.md)); a construction stage narrows it.

- Route: `ezdxf` layer search plus a closed-polyline check and area.
- Needs: headless; human when no layer matches those names or several candidates exist (project layer names vary).
- Done when: exactly one closed boundary contour with its area in m² is recorded and the user confirmed it if it was chosen by hand.

### Step 3 — Coverings to contours

Build a closed contour from every covering hatch (take existing contours when the drawing has them), clip
to the boundary, group by covering type, write one DWG per covering type. List the coverings with their
material names; flower beds follow [D101].

- Route: `ezdxf` hatch boundary paths -> closed polylines -> one DXF per type; DXF -> DWG with
  `dcc_batch.py acad` (`SAVEAS`).
- Needs: headless, no tool yet (no reviewed contour script); human for the covering -> material list.
- Done when: every covering contour is closed and inside the boundary, the covering areas are summed against the boundary area, and one file per covering type exists.

### Step 4 — Layered cake (default method C)

Make the base plane: the boundary shape, carrying the covering with the largest area (for example tile).
Put every other covering on top as its own plane, inset with a 6 mm step above the layer below; no stitching
of overlaps. Subdivide each layer at 3 m and unwrap it as equal stacked polygons (tiling UV), one material
per covering. The 6 mm step sits inside the spacing band of [geometry.md](../../../docs/domain/geometry.md);
for VPM cuts [D021] records about 4 m against this 3 m cell — when a VPM project needs one cell size, ask the user.

- Route: 3ds Max batch (`dcc_batch.py max --file <job>.ms`; startup reports a `polyunwrapper_autoload.mse`
  error, read the log) or Blender headless (import DXF/curves, fill, subdivide, UV).
- Needs: headless, no tool yet; live 3ds Max when the user wants the scene in Max.
- Done when: one plane per covering, base plane covering the whole boundary, layer Z steps of 6 mm, every face inside its covering contour, UV tiling per layer, material per covering.

### Step 5 — Elevations from vertical planning

Build the flat Ground first and stop here when the project is flat. Otherwise read the SPOZU vertical-planning
sheet: elevation points (design marks) with their XY.

- Route: `ezdxf` text/block-attribute parse of elevation marks (nested block references included).
- Needs: headless; human to tell design marks from existing ones and to confirm the sheet.
- Done when: a point list `x, y, z` with its source layer, a count, and the min/max Z is recorded; marks outside the boundary are listed separately.

### Step 6 — Relief surface

Triangulate the elevation points into a relief surface inside the boundary. Level differences and unevenness
are worked separately afterwards; the treatment of small steps is open ([C37](../../../docs/domain/conflicts.md)).

- Route: Blender headless (bmesh triangulation) or 3ds Max batch (`Terrain` from points).
- Needs: headless, no tool yet (T-GND-3 in the [roadmap](../../../docs/research/capability-roadmap.md)).
- Done when: the surface passes through every source point (Z difference below 1 mm) and covers the boundary.

### Step 7 — Project the flat Ground onto the relief

Project the flat, already textured Ground onto the relief along Z only: XY, contours, material IDs and UVs stay
as built in step 4.

- Route: 3ds Max batch (`Conform`) or Blender headless (Shrinkwrap, project along Z, then apply).
- Needs: headless, no tool yet; human for the visual look of slopes.
- Done when: XY of every vertex and every UV is unchanged against step 4, material IDs per face are unchanged, and the layer steps are still 6 mm after projection.

### Step 8 — Curbs, steps, ramps, retaining walls

Model them as Ground geometry ([GND-07](../../../docs/domain/areas/ground-surface.md)); which height
differences become geometry is open ([C37](../../../docs/domain/conflicts.md)) — ask when one is small.

- Route: 3ds Max batch or Blender headless (extrude along the SPOZU curb/stair/wall contours).
- Needs: live or human today (no tool yet; heights per element come from the drawings and the user).
- Done when: every curb, step, ramp and retaining wall of the SPOZU plan is either modelled or listed with the user's reason to skip it.

### Step 9 — NPM and VPM from one master

Derive both profiles from this one Ground master. Textures: NPM 2K at 10-40 px per linear metre, VPM 4K at
520-1706 px per linear metre ([D097]; the VPM lower bound is open, [C36](../../../docs/domain/conflicts.md)).
A stacked tiling cell of side `s` metres spans `s × density` pixels, so size the cell's UV square from the band.
Then the profile rows: perimeter extrusion GND-03, budgets GND-04/GND-06 (split per [D097]), UV and UDIM
GND-08/GND-09, names GND-11, pivot GND-12 in the [sheet](../../../docs/domain/areas/ground-surface.md).
VPM collisions follow the [UCX sheet](../../../docs/domain/areas/ucx.md) and [D098].

- Route: 3ds Max batch or Blender headless for derivation and FBX export; texel density per face measured on the exported FBX.
- Needs: headless, no tool yet for derivation; human for texture sets.
- Done when: both FBX exist at new versioned paths, are read back, and every face of the relief surface has a density inside its profile band.

### Step 10 — Checks before hand-over

Read the exported files back and run the [validate-delivery](../validate-delivery/SKILL.md) skill. Check the
user's typical Ground rejections explicitly:

- texture seams after unwrap (tiling broken) — render the textured Ground from fixed cameras;
- collisions: convex pieces, spacing between pieces, Ground-to-collision distance, gap per [D098];
- gaps between coverings or against the boundary — top-down coverage of the boundary;
- open polygons in VPM; flipped normals in VPM;
- material IDs and contours unchanged after FBX (raw material layer, not only slot names); metres, not
  scaled world units (both are case-study lessons).

- Route: `py -3 tools/qa/validate_package.py <zip|fbx> --json`; Blender headless readback and renders.
- Needs: headless for readback and numbers; human for the visual verdict.
- Done when: every check above ends as pass, fail, review or not checked with evidence; `passed=true` only per validate-delivery.

## Fallback methods

Method C above is the default ([sheet, Project practice](../../../docs/domain/areas/ground-surface.md#project-practice)).
Switch only with the user's yes and record why.

- **Method A — stitch + subdivide.** Import the per-covering DWGs one by one, turn each into a plane, close
  the gaps between planes by adding or removing vertices until all are welded, Subdivide at 3 m, split by
  material ID, unwrap. Use when: the delivery needs one welded surface without stacked layers (for example
  the stacked layers separate visibly after projection on steep relief, or a reviewer rejects the overlaps).
  Route: 3ds Max batch or live. Needs: live or human (vertex welding is manual today).
- **Method B — ShapeMerge / Conform onto a pre-cut UV'd plane.** Prepare a plane cut into ~3×3 m polygons,
  each unwrapped and stacked for tiling; ShapeMerge the covering contours onto it, or project an uncut Ground
  onto the cut plane with Boolean / Conform. Use when: a uniform 3 m grid with identical tiling UVs must hold
  across all coverings (tiling seams were the rejection), or a finished uncut Ground arrives from elsewhere.
  Route: 3ds Max batch or live (ShapeMerge, Boolean, Conform are 3ds Max tools). Needs: headless, no tool yet.

These "use when" triggers are the agent's reading of the method properties the user described, not user rules.

## Report

Per step: route used, `Needs` marker, evidence, open questions. Lists of what stayed manual and every open
conflict touched (C36, C37) go to the hand-over summary; technical QA, user acceptance and publication are
separate statuses.
