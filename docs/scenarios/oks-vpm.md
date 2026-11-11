# Cell oks-vpm — OKS building, VPM

One OKS (building, its usable roof, its MainGlass) delivered as a VPM ZIP: FBX + optional `_Light.fbx` + GeoJSON +
external PNG UDIM sets. Ground, MAF and Flora of the same site are the `ground-vpm` cell. Router table:
[scenarios.json](scenarios.json); procedure: the `scenario` skill.

## Read first (in this order, only what the task touches)

1. [requirements-2026.md](../domain/requirements-2026.md) section «HP (VPM)» — the regulation rows (FBX, ZIP, GeoJSON,
   geometry, materials, UDIM, UCX).
2. [TASK_TO_MODEL.md](../procedure/TASK_TO_MODEL.md) — fixed gates and the evidence checklist.
3. Area sheets for the stages in play: [body](../domain/areas/body.md), [windows](../domain/areas/windows.md),
   [decor](../domain/areas/decor.md), [textures](../domain/areas/textures.md), [uv-atlas](../domain/areas/uv-atlas.md),
   [ucx](../domain/areas/ucx.md), [package](../domain/areas/package.md).
4. [AGR Tools OVERVIEW](../agr-tools/OVERVIEW.md) when the work runs in 3ds Max (stages 0–9).
5. The closest etalon below, its `jobs/<ID>/TASK.md` and case study.
6. GeoAGR (the team's legacy Max combine) only when a task names a GeoAGR tool: `C:\x\GeoAGR-private\docs\reference\README.md`
   (outside the repo, read-only).

## Rules that bind this cell

| Topic | Rule |
|---|---|
| Passport | `jobs/<ID>/passport.json` (K1) is required only on the AGR Tools route until a second route exists; other OKS routes record the same facts in `job.yaml` inputs / REPORT [D247]. |
| Budget | ≤ 150 000 triangles per OKS FBX (project target), regulation ceiling 1 000 000 [D161] |
| Texel | VPM diffuse 512–1706 px/m [D160]; AGR Tools grid 3.6 m per tile at 1000 px/m [D207] |
| UDIM | body numbered per mesh from 1001 [D209]; all glass UVs in 1001, no maps on glass [D221] |
| Windows | library first, types by form + size [D140]; families F100 / F73 / F58 [D204] |
| Topology | xView clean: vertices 2 mm = 0, faces 5 mm = 0 [D152]; continue loops and rings [D200] |
| Decor | embed 10–20 mm into the facade [D199] |
| Hand-off | a non-triangulated work FBX next to the ZIP [D198]; final export from Max or Blender, Max preferred [D212] |
| External data | MSK-77 by the customer's DWG (or the customer's GeoJSON point); FNO from SINTEZ; GeoJSON = the customer's file; УКЭП by the customer [D220], [D163] |
| UCX | gap 2 mm – 1 cm [D098], SINTEZ too-close < 0.2 mm checked separately [D162] |

## Route by stage

| Stage | Route today | Status |
|---|---|---|
| Source intake | skill `analyze-architectural-source` | tool, run by hand |
| Body, windows, capsules, roof | **standard**: AGR Tools stages 1–4 (Max) [D250]; job scripts in the etalons are precedent, not an automatic standard-route fallback | AGR Tools not yet run on a real building; etalons used job scripts |
| Materials, UDIM, textures | AGR Tools stages 5–6; `tools/materials/` | partial; texel checked by V009 |
| UCX | AGR Tools `ucx_core`; etalon `jobs/KPP1/scripts/` | job scripts, no Main UCX case accepted |
| Export, readback | Max export [D212]; `tools/blender/fbx_readback.py`; `dt qa xview` | proven |
| Package and checks | AGR Tools stage 9; `tools/qa/validate_package.py`; SINTEZ AGR Checker | validator V001–V013 partial; no package has reached passed=true yet |

For body / windows / roof, **after Gate 1**, when **Max is busy**, the offline route
(`dt_ai.ops` / [VARIANTS R14 kernel-prisms](../methods/building-body/VARIANTS.md)) is permitted only as
`path: deviation` [D250]. Append the [deviation log](../procedure/TASK_TO_MODEL.md#free-path-and-deviation-log)
before continuing; all eight gates remain required, including before/after invariants, export readback,
visual acceptance and final SINTEZ. This route permission is not Gate 1 approval or a waiver of a failed check.

## Etalons

- `jobs/elv-tc-vpm` — VPM only from a Revit FBX + AGR booklet; accepted 2026-11-05; first passed=true attempt (D220).
- `jobs/KPP1` — VPM + NPM v005, [case study](../agr/case_studies/KPP1_VPM_NPM_V005.md).
- `jobs/PSU275` — [delivery v003](../agr/case_studies/PSU275_VPM_NPM_DELIVERY_V003.md).
- `jobs/skug26-k5-ac` — AC screens texture, [case study](../agr/case_studies/SKUG26_K5_AC_SCREENS_VPM.md).

## Checks

`tools/qa/validate_package.py` stages V001–V004, V007–V013 for VPM ([validation.md](../domain/validation.md)), `--scene`
for the UV, texel and UCX stages; `dt qa xview` [D152]; SINTEZ AGR Checker before the hand-off; manual V016, V017.

## Minimal contract (ask once, ≤ 5 questions, each with a recommendation)

- **Source**: which file is the geometry authority (Revit FBX, Max scene, album) and which wins on conflict.
- **Address stem** and OKS index (`SM_<Address>_NNN`, reg 1.3.x).
- **Placement**: customer DWG or the customer's GeoJSON point; the customer's GeoJSON file.
- **Etalon**: which accepted job this one should look like (texel, joints, palette) — in numbers.
- **Не трогать**: source files, geometry that matches the album, anything the user finished by hand.
- **Acceptance**: what passed=true means for this job (lights, signage, УКЭП in or out).
- **Pilot**: one facade end to end, a picture to the user, then the rest.

## Known gaps (do not assume a tool exists)

No shared NPM↔VPM derive command (T-DER-2); `_Light.fbx` content has no validator stage; decor embed [D199] and
loop continuity [D200] are not checked automatically; the GeoJSON generator `export.geojson_write` is not
delivery-ready until the customer examples are studied [D220].
