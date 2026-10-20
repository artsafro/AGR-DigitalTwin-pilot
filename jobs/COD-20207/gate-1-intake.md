# COD 20207 Ground — Gate 1 intake (issue #420)

Status: **blocked on user Gate 1 confirmation; not buildable**. Real project data, not synthetic.
No Ground mesh, export, comparison pass or visual-review publication is claimed.
The site choice and etalon authority are supplied by Artem in #420; they do not approve the mappings below.

## Sources and executed route

Only the supplied copies were opened. Desktop originals were not opened or modified.

| Input | Bytes | SHA-256 |
|---|---:|---|
| `C:/x/ground-cod-22/spozu.dwg` | 9933016 | `9b409b023a5dd494c91f6807e7aee392b6a684da48fac371209764770d5f764b` |
| `C:/x/ground-cod-22/gp.dwg` (optional, hashed only) | 92071 | `5f1155b8c317350515dcf0995c5dbcfb643f40c0d1dd28e2af1bd852e7f32300` |
| `C:/x/ground-cod-22/intake-v001/spozu.dxf` | See local file | `e11a4a120832996618f41d4a4cc46bef329bc1ca9b0f18cc6add2bd76fdf12e7` |

Executed from the issue worktree:

- `uv sync --extra cad`: exit 0.
- `uv run python -c "from adapters.cad.dwg import dwg_to_dxf,sha256; r=dwg_to_dxf('C:/x/ground-cod-22/spozu.dwg','C:/x/ground-cod-22/intake-v001'); print(r); print('DXF_SHA256',sha256(r.dxf))"`: exit 0.
- Existing conversion adapter copied the input again to `spozu.copy.dwg`, then ran the inspected `dcc_batch.py acad` session-lock wrapper: AutoCAD 2025 core console, `ACADVER=25.0`, `INSUNITS=6` (metres), 5.9 seconds, process exit 0, wrapper status `ok`. Receipt: `C:/x/ground-cod-22/intake-v001/spozu.acad.json`. Source hash verified unchanged by the adapter.
- `PYTHONPATH=. uv run python tmp/cod_intake.py`: exit 0. Read-only diagnostic using existing `adapters.cad.spozu._walk` (composed transforms and effective layers); full inventory: `C:/x/ground-cod-22/intake-v001/inventory.json`.
- Read-only hatch-region probe using existing `hatch_region` and `boundary_polygon`: exit 0. No repair applied; invalid source listed below.

Origin/main at intake: `45d56e9`. No `jobs/COD-20207` report or `adapters/cad/configs/cod_20207.yaml` exists there; acceptance is not already delivered.

## Drawing inventory

DXF AC1032; 280 layer-table entries; 1361 model-space top-level entities;
7166 visited model-space entities **including INSERT containers and expanded contents**;
0 traversal findings. Counts are not a guarantee that Civil proxy payload geometry is readable.

Layouts: `1_Ситуационный`, `2_СПОЗУ`, `3_ПОР`, `4_ПЗМ`, `5_Благоустройство`,
`6_СПИС`, `7_Транспортная схема`, `Model`. Proposed covering authority: `5_Благоустройство`
legend plus model-space hatches; vertical planning: `3_ПОР`, pending confirmation.

### Boundary candidates

Both are closed `ГП_Граница участка` LWPOLYLINEs, with the same area to rounding.

| Handle | Area m² | XY bounds (metres) | Observation |
|---|---:|---|---|
| `69002` | 5101.588 | (6570.83, 15385.29)–(6674.84, 15449.21) | Intersects all six covering-type groups; proposed working boundary |
| `5968B0` | 5101.588 | (9498.391069, 17275.841707)–(9602.401069, 17339.761707) | Zero overlap with every covering-type group; translated duplicate candidate, not silently discarded |

## Draft parts list — mappings for approval, not executable PartsList

Areas below are unions of **valid** top-level hatches clipped to candidate `69002`.
They are not additive coverage, an approved parts budget, or final surface measurements.
Legend labels are text read from `5_Благоустройство`, not inferred from colour.

| Proposed part / operation | Source layer | Hatches | Valid clipped union m² | Legend evidence / question |
|---|---|---:|---:|---|
| Asphalt / layered-cake plane | `ГП_Благо_ТИП_1` | 1 | 2430.264599 | `542F39`: asphalt drives, type 1 |
| Tile / layered-cake plane | `ГП_Благо_ТИП_2` | 8 | 361.511102 | `542F44`: tile sidewalks, type 2 |
| Reinforced tile / layered-cake plane | `ГП_Благо_ТИП_3` | 5 (1 invalid) | 125.603787 | `593455`: reinforced tile sidewalks, type 3 |
| Geogrid / layered-cake plane | `ГП_Благо_ТИП_4` | 5 | 491.897629 | `542F72`: geogrid, type 4 |
| Reinforced geogrid / layered-cake plane | `ГП_Благо_ТИП_5` | 1 (+2 proxies) | 9.025629 | `593451`: reinforced geogrid, type 5; proxies unresolved |
| Unclassified covering / operation pending | `ГП_Благо_ТИП_6` | 3 | 2.490864 | No type-6 label established; do not assume lawn |
| Drive curb / profile extrusion | `ГП_БР дорожный` | 5 LWPOLYLINEs | n/a | `542F6A`: БР100.30.15; exposed height and alignment require approval |
| Garden curb / profile extrusion | `ГП_БР сад` | 4 LWPOLYLINEs | n/a | `542FB1`: БР100.20.08; exposed height and alignment require approval |
| Relief / TIN projection | `ГП_Красная поверхность`, `ГП_ПОР_красная`, `ГП_Отметки поверхностей`, `ГП_Характерки` | n/a | not measured | 1 + 5 + 15 + 18 Civil proxy entities respectively; no readable design-Z list established |
| Boundary skirt / perimeter extrusion | `ГП_Граница участка` | n/a | pending boundary selection | At least 1 m per GND-03; project zero not established |

`ГП_Черная поверхность` also contains one proxy (existing-surface candidate, not selected as design).
`ГП_Благо_ТИП_3` hatch `4C5784` has a self-intersecting first loop at
(6642.69999287543, 15434.7342055753). It is excluded from the area above, **not repaired**.
Flora/MAF placement remains out of scope; inventory retains their layers rather than discarding sources.
No source is consumed by a production build at this stage.

## Questions to Artem (Gate 1)

1. Confirm boundary `69002` and use of model-space coverings with layout `5_Благоустройство` as legend authority; is `5968B0` only a duplicate/context contour? Confirm CRS and project-zero height (INSUNITS establishes metres only).
2. Confirm types 1–5 above. What is type 6, and which source supplies lawn/unhatched regions and building-footprint holes? Confirm material/texture identities from the handmade etalon rather than borrowing Vatutino's slots.
3. May self-intersecting hatch `4C5784` be repaired with `make_valid`, or should it be replaced by an authoritative contour? No Vatutino-specific repair permission is carried over.
4. Confirm design relief authority (`3_ПОР` / red Civil surface) and provide/authorize an export of design elevations or 3D surface if the proxy payload cannot be extracted by the existing route. Confirm exposed drive/garden curb heights and which edges require steps/ramps.
5. Approve the completed parts mapping before build (D111/D124/D125). Surface budget allocation, joints, master grid and any relief tolerance exceptions remain unapproved for this site; Vatutino-only D150 must not be reused.

The machine-readable public `PartsList` requires resolved operations/budgets/source coverage and explicit approval.
Do not create an apparently buildable config or fabricate those fields while these questions are open.
After answers: write/validate the actual parts list and `adapters/cad/configs/cod_20207.yaml`, then use the existing pipeline; record every required pipeline change.

## Pipeline findings and remaining acceptance

- Layer mapping is project data, but the six covering types, two boundary candidates, invalid contour and proxy-based relief require explicit handling.
- Existing DWG conversion and nested traversal work on this second drawing. No production-code change made.
- Existing Vatutino job scripts are still named/site-configured for Vatutino; reusability beyond the adapter has **not** been demonstrated.
- General surface/UCX/material/relief checks remain mandatory; the Vatutino-specific gap exception is not applicable.
- Handmade etalon inspection, matched-point height comparison, NPM/VPM/surface budgets, xView, materials, UCX, and Vatutino-v014 comparison are **not measured: Gate 1 awaits approval**.
- No scene is published to `C:/x/review/pending.json`: publishing an unbuilt/unapproved scene would be misleading.

Next worker: resume from these receipts and answers, keep all assets under `C:/x/ground-cod-22/`, use only copied etalons, and publish one PR only after the full acceptance is delivered. No PR opened for this partial intake.
