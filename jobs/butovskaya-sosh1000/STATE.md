# butovskaya-sosh1000 — school for 1000 pupils, Bolshaya Butovskaya vl. 9 (NPM by autoresearch, #118)

Pipeline status: experiment (autoresearch lane 3 of 3, issue artsafro/AGR-DigitalTwin-pilot#118). Not a delivery:
`delivery_passed=false`; technical QA, user acceptance and publication are open.

## Source (read only)

- The user's open Revit 2025 model `БУТОВСКАЯ_СОШ1000_АР_В3_ВИЗАМ_2025.rvt` (workshared, 8 levels -3.4 ... 18.6 m),
  read once through the in-Revit MCP add-in with read-only commands (`scripts/snapshot_revit.py`). Never
  modified, synced or saved.
- The add-in's geometry read returns per element a bounding box, volume, area and face count, no tessellation.
  The snapshot is therefore one axis-aligned box per element (walls, curtain panels and mullions, roofs, floors,
  windows, doors): 11 060 elements, 170 without a box, 4 site pieces outside the building zone left out
  (`scripts/evaluate.py` `ZONE`), 10 886 boxes in the etalon. The building is orthogonal in project coordinates,
  so wall and panel boxes are close to the elements (fill ratio volume / box: walls median 0.85, panels 1.00);
  roofs (0.47) and floors (0.58) are coarser. Counts and hashes: `docs/experiments/autoresearch-butovskaya-npm.md`.
- Snapshot: `C:/x/butovskaya-snapshot/` (local, outside the repo; nothing in `data/`).

## Scripts

| Script | Does |
|---|---|
| `scripts/snapshot_revit.py` | step 0: the read-only snapshot (refuses any non read-only command) |
| `scripts/evaluate.py` | metric `silhouette_err_m2` and guard, fixed after step 0 |
| `scripts/build_npm.py` | the NPM, built from the snapshot only; the one file the loop edits |
| `scripts/render_views.py` | five orthographic png views (model and snapshot) |

```
uv run python jobs/butovskaya-sosh1000/scripts/build_npm.py --out C:/x/butovskaya-npm/model_dump.json
uv run python jobs/butovskaya-sosh1000/scripts/evaluate.py --model C:/x/butovskaya-npm/model_dump.json
```

## Model (current best, see the report for the loop)

Exp 15 of 20: `silhouette_err_m2` 17.584 (first build 334.066), 141 132 triangles, 0 open / non-manifold /
winding edges, levels exact; report `docs/experiments/autoresearch-butovskaya-npm.md`.

One closed mesh `SM_butovskaya_sosh1000_body`: plan regions per height layer (thresholds = the 8 levels + the box
tops with the most plan area), extruded and meshed edge to edge on a 0.05 m grid; up faces roof id 21, walls and
soffits facade id 1; flush opening planes (ids 11 window, 12 door) cut into the wall faces where an opening box
fits one wall face. `LEVEL_<name>` helpers at the snapshot's level elevations.

## Open

- Visual acceptance by the user (renders in `docs/experiments/autoresearch-butovskaya-npm/`).
- Opening planes are flush, not recessed (pattern `opening-plane` asks a 0.4 m reveal in `npm_min`); the metric
  does not see openings, so the loop never improved them. Not every snapshot opening gets a plane (report).
- Horizontal faces are CDT-triangulated (the OBJ03 decision against triangulated horizontal faces was for that
  object; a question for this one).
- No FBX export, no materials table, no UV: geometry only.
