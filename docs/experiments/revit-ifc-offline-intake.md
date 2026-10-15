# Offline IFC intake versus KPP1 tolerances

## Question and verdict

Can Revit-free IfcOpenShell recover levels, slab/wall contours and hosted opening boxes within K01 tolerances?

**MAYBE — technically feasible on a synthetic subset, not ready as a generic production importer.** Six IFC4 cases pass covered comparisons; simple swept polygons and an explicit wall-index naming contract are required. No approved KPP1 IFC export was available. Do not replace TwinPack or claim KPP1 acceptance.

One method tested: offline IfcOpenShell intake, from `docs/research/revit-api-automation.md`, Proposed Next Tasks #1. `jobs/KPP1/scripts/export_revit_groups.mjs` exports FBX via a live bridge, not offline IFC; read but not run. Revit was never started; no other DCC invoked.

## Setup

Baseline implementation `91795c0`, preserved baseline/report commit `206fcf3`. Windows uv environment, **IfcOpenShell 0.9.0 pinned**, IFC4 metre/mm variants. No tracked IFC found. Copied B01/B02/B02t specifications and K01 tolerances were prepared before experimentation under `%TEMP%/agr-exp-t_b083dc71/`; references, `data/`, RVT and production code unchanged.

Inputs are etalon-derived **specifications**, not freshly read MAX/FBX. Generated IFC is **synthetic**, not Autodesk export. B02t covers its stepped contour, not terrace/parapet semantics. Generator uses building translation `(17,-11,2)` m and 30-degree rotation, nested storey/element/host placements, polygon slabs, uncut vertical walls and opening solids with `IfcRelVoidsElement`.

Extractor reads IFC only, never oracle geometry: checked units, composed placements, slab extrusion profile rings, wall footprints versus geometry-kernel vertices, opening dimensions from kernel vertices in host coordinates. Names `W0000..Wnnnn` identify contour edges and are checked against edge origins/directions. This synthetic contract is not a claim about Revit exports. Geometry is building-local metres; `frame.to_object` maps raw IFC units/coordinates to that frame. Separate provenance records SHA-256 and GlobalIds. Kind/material/family attributes are not guessed.

Five samples per stage, medians below. Parse-only reopens IFC. Full intake includes reopen, geometry, validation, hashing and provenance; excludes Python startup/import, IFC generation, comparison and output writing. Sequential warm-filesystem tiny cases, not a scaling benchmark. Final raw measurements, hashes, counts and rows: [`results.json`](../../experiments/revit-ifc-offline-intake/results.json), accepted run `ifc-v002` after frame/mapping hardening. Earlier run superseded.

## Baseline versus prototype

Generic IFC adapter is unimplemented (`adapters/revit/README.md`); current TwinPack requires previously exported JSON/OBJ from live Revit. No baseline IFC importer exists. JSON read + current `Spec.model_validate` on the same copied inputs is a lower-cost control, **not equivalent extraction or a speedup claim**.

| Fixture / units | JSON + Spec median, s | IFC parse median, s | IFC intake median, s | Storeys/slabs/walls/openings | Covered K01 rows |
|---|---:|---:|---:|---|---|
| B01 / m | 0.000141800 | 0.000644500 | 0.039888000 | 3/2/8/2 | 17/17 |
| B01 / mm | 0.000141800 | 0.000646900 | 0.034865400 | 3/2/8/2 | 17/17 |
| B02 / m | 0.000155200 | 0.000747800 | 0.059450300 | 3/2/14/2 | 17/17 |
| B02 / mm | 0.000155200 | 0.000784900 | 0.056670800 | 3/2/14/2 | 17/17 |
| B02t / m | 0.000195200 | 0.000799000 | 0.053645300 | 3/2/14/2 | 17/17 |
| B02t / mm | 0.000195200 | 0.000887000 | 0.059828400 | 3/2/14/2 | 17/17 |

Across six files: **18 storeys, 12 slabs, 72 walls, 12 openings, 102 covered rows pass** (including informational grille rows). Sizes 12,231–17,792 bytes. Exact expected counts per file.

| Maximum unrounded output difference | Observed | Threshold |
|---|---:|---:|
| Level elevation | 8.882e-13 mm | K01 30 mm |
| Slab contour coordinate component | 4.441e-12 mm | K01 Hausdorff 50 mm / area rel 0.02 |
| Opening bbox component | 5.329e-12 mm | K01 50 mm |
| Wall profile versus kernel plan vertices | 8.335e-12 mm | Experimental guard 1 mm |

These are floating-point **synthetic round-trip residuals**, not real measurement accuracy. Area/Hausdorff/kink counts pass. Slabs use supported extrusion profiles; wall readback checks plan geometry, not full topology/materials. `roof=None` and missing roof reports deliberately skip roof/parapet rows: comparator match is not complete delivery compliance.

## Correctness and complexity

| Check | Baseline | After |
|---|---|---|
| Existing offline tests | 1767 pass, 2 skip, 11 DCC deselected; 169.30 s | Same counts; 144.60 s |
| Prototype tests | absent | **13 passed**, 0.93 s |
| Harness negative controls | absent | **9/9** expected outcomes |
| Profiles / schemas | pass / 11 pass | pass / 11 pass |
| Production changes | none | **0 lines** |
| Prototype size | absent | pilot 777 lines / 41 functions; tests 135 lines / 15 functions |

Suite timing is not an attributed speedup. DCC checks remain unverified. Existing duplicate-ZIP-name warning persists. CI: not run (billing lock).

Tests cover units, frame raw-building-origin mapping, placement elevations despite wrong raw `Elevation`, real IFC level displacement 31 mm and opening displacement 51 mm, missing units/representation/host, swapped wall names, nonvertical extrusion and tilted slab. Comparator controls cover inside/outside level 30 mm, bbox 50 mm, contour area 2%, Hausdorff 50 mm, missing floor/opening. Initial focused run caught two invalid nested pytest assertions; small assertion-only repair, all 13 rerun green. No tolerances relaxed.

## Commands

Copy benchmark inputs first; outputs must never target source/reference directories.

```bash
uv run --with ifcopenshell==0.9.0 python experiments/revit-ifc-offline-intake/pilot.py \
  --inputs C:/Users/artsafro/AppData/Local/Temp/agr-exp-t_b083dc71 \
  --out tmp/t_b083dc71/ifc-v003
uv run --with ifcopenshell==0.9.0 pytest -q experiments/revit-ifc-offline-intake \
  --basetemp=tmp/t_b083dc71/pytest-ifc --tb=short
env -u MSYS_NO_PATHCONV -u MSYS2_ARG_CONV_EXCL uv run pytest -q \
  -m 'not dcc and not blender' --basetemp=tmp/t_b083dc71/pytest-after --tb=short
uv run dt profiles check
uv run dt schemas --check
```

Baseline preceded prototype in prior attempt; original 5-run JSON medians B01 0.000158100 s, B02 0.000151300 s, B02t 0.000167200 s. Resumed harness remeasured control before each fixture. Results read back; counts/maxima aggregated in Python.

## Offline versus live boundary

**Demonstrated offline:** represented storey count/elevation with nested placement/units; slab contours with niches/steps; uncut wall footprints; void hosts and opening boxes; K01 level/floor/kink/opening counts, level/area/Hausdorff/bbox thresholds, provenance.

**Needs real IFC evidence, not inherently live Revit:** generic wall-edge association, IFC2x3, mapped/BRep/tessellated geometry, holes/curves, multiple slabs/storey, rooms/spaces/materials. Prototype rejects or does not cover these. Wall-name contract is not generic intake.

**Still needs approved export and/or user-opened Revit for source checks:** actual KPP1 completeness/coordinate alignment; exporter version/view/settings; phases/options/category filtering; unloaded/nested RVT links; native UniqueId/ElementId mapping and handedness; native roof/parapet semantics; RVT modification/save/readback; IFC link/import parametric round-trip. Baltic/MSK-77 needs approved georeferencing, not just a parse.

No room, UV, topology, material, roof, terrace or delivery acceptance inferred.

## Decision and follow-up

**MAYBE: IfcOpenShell offline intake.** Measured 35–60 ms/case and covered accuracy are promising for offline checks; shared synthetic assumptions, no independent Autodesk export and restrictive naming/representation prevent generic adoption.

No `adopt` verdict, therefore no adoption task or GitHub issue created. Proposed next experiment: **Validate offline intake on an approved KPP1 IFC export** — obtain versioned IFC/exporter settings from a user-opened Revit copy; compare native/TwinPack reference; replace naming with geometric host-edge association; add real representations and quantify unsupported coverage before adoption.

## Recovery

Earlier attempt preserved baseline but wrote no prototype. This retry used three authorized Cursor wrapper rounds: prototype, hardening, tests-only. First two timed out at 600 s after writing code; final narrow round exited successfully. Driver confirmed stopped processes, restored preserved settings byte-identically (empty diff), removed wrapper task files before testing. No quota error observed. Findings rely on actual execution, not agent completion text.

## Agent trace

- Sessions: not measured (no transcript)
- Written by: Prototype and tests written by Cursor (grok-4.7-medium); Hermes driver, verification, report and small assertion fix
- Subagents: not measured (no usage log, no transcript)
- Skills: not measured (no usage log, no transcript)
- Commands: not measured (no usage log, no transcript)
- Hook denials: not measured (no transcript)
- Retries: not measured (no transcript)
- Context at handover: not measured (no transcript)
- Duration: not measured (no transcript)
- Commits: `91795c0..206fcf3` (1 commits)

Generated by `tools/hooks/agent_trace.py --base 91795c0 --writer ...` before results commit; interval reflects that generation point.
