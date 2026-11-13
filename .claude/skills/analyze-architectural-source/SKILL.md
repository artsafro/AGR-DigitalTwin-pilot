---
name: analyze-architectural-source
description: 'Inspect an incoming architectural source (DWG/DXF drawings, FBX, Revit, SketchUp, Blender, 3ds Max, Unreal input) and record what it contains before any processing. Use when a new or updated source file arrives, or before building production assets from one. Use when: «пришёл новый FBX», «разбери исходник из Revit», «что внутри этого файла перед сборкой?».'
---

# Analyze architectural source

Read-only inspection. Leave the source file unchanged; write findings to the report only.
Domain rules live in `docs/domain/` (each rule cites its source); open the file named
in a step when that step needs the rule, not before.

## Decision first: target profile

Ask or record which deliverable this source feeds: **NPM**, **VPM**, **both**, or
**Unreal-only**. The profile decides which budgets, coordinate rules and naming apply
(`docs/domain/npm-vpm.md`). If unknown, record it as a user question and analyse
against both NPM and VPM.

## 2D drawings — DWG / DXF branch (F14)

After steps 1–3, take this branch for drawing-only sources. Steps 4–6 are mesh-only:
record `not applicable: 2D drawing` for mesh classification, topology, material slots and UVs;
do not invent a welded mesh or run `dt spec extract`. Continue to step 7.

1. Resolve the source path and SHA-256 from `jobs/<JOB>/sources.json`; keep originals unchanged.
   Record sheet/revision and the authority for units, scale, levels and coordinates. For KPP1 АС.03 R1:
   L03 = plan, L01 = facade heights/openings, L02 = finishes (registry roles are proposals, not approval).
2. DWG: `uv run python tools/methods/body/dwg_to_dxf.py <source.dwg> <new.dxf> <receipt.json>
   --workdir C:/x/<card>/readback` runs AutoCAD DXFOUT on a hashed copy. DXF: start at census directly.
   A failed conversion is not usable geometry. Keep its receipt; never pass the original to AutoCAD.
3. `uv run python tools/methods/body/plan_from_dxf.py census <sheet.dxf> <census.json>`.
   Review layers/handles and establish a sheet-specific role map and frame; never copy a different sheet's map.
4. Plans: `uv run python tools/methods/body/plan_from_dxf.py extract <plan.dxf> <contours.json>
   <report.json> --map-file <roles.json> --contour-source hatch --z0 <confirmed-bottom>
   --z1 <confirmed-top> --origin-mm <x,y> --frame-shift-m <x,y>`.
   Choose `lines` instead of `hatch` only when the mapped source warrants it. Missing levels yield
   provisional output (exit 2), not buildable contours. Record invocation, coverage and drops.
5. Facades: `uv run python tools/methods/body/facade_openings_from_dxf.py <facade.dxf>
   <mapping.json> <new-schedule.json>`. See the tool docstring for the explicit handle/frame map.
   It measures rectangular LINE/LWPOLYLINE outlines only, in millimetre DXFs; every other entity needs
   a named drop reason. INSERT/curved/nonrectangular outlines need another measured route, not bbox guesses.
   Review window/door kinds and sheet datum against the drawing. The schedule supplies width, height,
   sill/head and sheet position for parts, NOT wall depth, world orientation or cutter boxes.
6. Record finishes/annotations as drawing evidence, not mesh materials/UVs. Link each measured fact to
   sheet + handle and source hash. Unresolved authority, missing outlines, depth or facade-to-plan mapping
   remains a question before modelling/Gate 1; no schedule is architectural approval.

## Steps

1. **Identify.** Record path, format, file size, modification date, SHA-256 and
   authoring tool/version if discoverable. Done when the source has a row in
   `docs/sources/README.md`.

2. **Scale and placement.** Determine units, up axis, origin, and one real-world
   reference dimension (storey height, door, grid spacing). Record where the source
   sits relative to the profile's placement rule: NPM in MSK-77 at project heights;
   VPM local origin with pivot at the geometric centre X/Y and Z at project zero
   (`docs/domain/geometry.md`). Done when the reference dimension is measured and
   compared with its expected value, and CRS / zero mark are either confirmed from a
   document or listed as user questions. Never assume a CRS or zero mark.

3. **Structure and composition.** List the object/layer/collection hierarchy,
   object count and instancing. Classify every top-level group as OKS (Body,
   windows, roof, usable roof), Ground, GroundEl, Flora, glass, or out of scope
   (interiors, existing non-reconstructed buildings, context). Use `GLOSSARY.md`
   terms. Done when every top-level group has a class and a count; anything
   unclassifiable is a user question.

4. **Source class.** On the welded mesh, measure three facts with `classify_source`
   (`src/dt_ai/spec/source_class.py`; `PANELISED` and `PANEL_HINT_SHARE` live in
   `src/dt_ai/spec/mesh.py`): the number of connected parts, the share of the largest
   part by surface area, and whether any part is a closed shell. A closed shell is
   topological and ignores winding: every edge of that part is used by exactly two
   triangles, with no signed-volume test. Inconsistent winding on a closed mesh is
   still a shell, so the class stays monolithic and is never certified shell-free or
   panelised. Rule 1 [D066]:
   `panelised` only when there are at least two connected parts, the largest share is
   strictly below `PANEL_HINT_SHARE` (0.5), and no shell is present. Route `panelised`
   to `measurement+direct-build` (measurement and a direct build). Do not run
   `dt spec extract` on a `panelised` source. A closed shell, a single part, or a
   largest share strictly above `PANEL_HINT_SHARE` is `monolithic` and keeps the
   existing `dt spec extract` route. A largest share equal to `PANEL_HINT_SHARE` with
   no shell and more than one part is an error, not a guessed class. Record the three
   numbers, the class and the route in `docs/sources/<source-name>.md` and on the
   source row in `docs/sources/README.md`. Done when that record is written, or the
   line is `not checked: <reason>`.

5. **Geometry health.** Triangle count per future FBX against the profile budget,
   non-manifold edges, duplicated or overlapping faces, flipped normals, unapplied
   transforms, pivots. Separate deliberate embeds from defects before reporting a
   finding (`docs/domain/validation.md`, QA procedure). Done when each check has a
   number or `not checked: <reason>`.

6. **Materials and UVs.** Every material slot is classified (opaque, glass,
   emissive, vegetation/opacity, unknown); texture references found/missing; UV
   channels per object (`docs/domain/materials.md`, `docs/domain/uv-textures.md`).
   Done when no slot is unclassified without being listed as a question.

7. **Report.** Write `docs/sources/<source-name>.md`: findings above, including the
   source class and its route, production
   risks, user questions, and every entry of `docs/domain/conflicts.md` that this
   source touches (by number). Update its row in `docs/sources/README.md`.

## Completion

Every step has a recorded result. Unknowns are written as unknowns with the reason,
never filled by assumption. Synthetic or estimated values are labelled.

## Intake mode — "study the sources" (historical archive/2026-11:docs/HARNESS_PLAN.md §15; procedure in this section)

When the user puts every source of an object into `jobs/<JOB>/sources/` and says "изучи исходники",
run the steps above for each file and write `jobs/<JOB>/intake/` (read only: nothing in `sources/` changes,
nothing is exported). Exception to step 2 here: when only images or PDF without dimensions exist, the
reference dimension is not measured — it is the anchor question below, and the intake is complete with
the anchor open (the draft stays not buildable):

1. `sources.json` — one entry per file: path, sha256, bytes, format, what was read (`geometry`,
   `dimensions`, `image`, `materials`, `metadata`), units, frame, version, `opened`, the reason it did not
   open. Role by priority — BIM (Revit, IFC) → 3D (SketchUp, Max, FBX) → DWG → PDF with dimensions →
   images: `primary` for the best-ranked source with geometry or dimensions; the others `check`,
   `materials` or `none`. ArchiCAD comes in as IFC.
2. `picture.md` — `## Facts` table (Fact | Value | Source | Confidence) for storeys and levels, contours,
   openings, roof, attachments, materials; every fact names its source (`path#locator`) and a confidence:
   `measured` (read from geometry), `read_from_drawing` (from dimensions), `estimated` (anything from
   images), `unknown`. `## Contradictions` table (Fact | Source A | Value A | Source B | Value B | Status)
   — Status stays `open`; never pick a side.
3. `questions.md` — the gray zone, in the questions-file format (`dt spec merge-questions`).
4. `spec-draft.json` — the spec blocks; a block without a source is `null` with confidence `unknown`, never a
   default. Images only / PDF without dimensions: `anchor.needed` true and an anchor question (one
   dimension the user confirms — a door, a storey, an opening, a brick or panel module; a range like
   "door 2.1-2.4 m" only phrases the question). Until it is confirmed nothing is `measured` and no spec is
   built.
5. An implementation proposal (end of `picture.md` or the report): extractor route (mesh / Revit / 2D /
   image), the patterns needed, what the user must give before the start.

Done when `uv run dt intake check --dir jobs/<JOB>/intake` reports `ok`; it also says whether the draft is
`buildable` (every required block filled, the anchor confirmed, the spec valid). The engine runs on a
buildable draft only.
