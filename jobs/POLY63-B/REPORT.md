# Tower 63B — polygon #1619, stage 1

## v003 review candidate

- At +26.70/+42.45 m the formerly free facade-to-shoulder edges are sewn. The four transition heights (+23.55/+26.70/+39.30/+42.45 m) are supported by source wall endpoint clusters; this is not a survey of every shoulder edge. Curtain and band-end mouths remain open. The synthetic skewed belt fails on the old generator and passes with shared stations.
- On native v002 the four candidate pairs were jamb/shoulder termination contacts: 3358/8479, 5484/8732, 6156/8963 and 7897/9216 respectively in ascending Z. Fresh shared v003 FBX readback has zero self-intersection candidates (2 mm), inward or reversed exterior faces, unexpected free facade edges, and winding conflicts. 8,565 quads, 976 horizontal shoulder triangles; #1616 typical band **89.457**, 100% quads, zero n-gons/slivers.
- The D337 **0.60 m assumed step was not measured from a facade sheet**. The fitted tangencies and envelope radius stay fixed, while the developed UV span is snapped to a whole number of repeats from the starting tangency. Additional subdivisions enforce sagitta. On the FBX: 1 channel, 1,462 exterior arc face samples across 8 corners, maximum midpoint sagitta 9.36 mm and max UV round-trip difference 0.00000062 UV units. This is not certified physical panel spacing or the final UDIM atlas. Finish IDs remain provisional from FBX types; Revit 2025 read-only was unavailable.
- Sheet (including same-camera before/after) and `SHA256SUMS.txt`: `G:/Мой диск/AGR-evidence/1619-body-training/tower-B/v003/`. QUAD copy: `C:/x/review-63B/63B_Stage1_v003.fbx`.

### Frozen `oks-vpm` Stage 1 replay

Run from the repository root with `DESIGN` set to the v002 evidence `source_sections_and_openings.json`, and `OUT` set to a fresh output directory. The body hook verifies frozen input hashes and consumes the shared `body_core.prepare_plan` levels, role and name. The recorded path stops before windows, capsules, roofs or packaging, and `orientation.json` binds the plan and the native readback.

```bash
uv run python -m jobs.POLY63-B.hooks.body_grid "$DESIGN" "$OUT/model.json"
uv run python -c "from pathlib import Path; from dt_ai.core.blender_runner import run_blender; import sys; p=Path(sys.argv[1]); b='C:/Program Files/Blender Foundation/Blender 4.4/blender.exe'; s='63B_Stage1_v003'; f=p/(s+'.fbx'); run_blender('jobs/POLY63-B/hooks/export_review.py',(p/'model.json',p,s),executable=b,outputs=(f,p/(s+'.blend'),p/'round.png'),log_path=p/'export.log'); run_blender('tools/blender/fbx_readback.py',(f,p/'readback.json'),executable=b,output_json=p/'readback.json',log_path=p/'readback.log')" "$OUT"
uv run python -m jobs.POLY63-B.hooks.check_readback "$OUT/model.json" "$OUT/readback.json" "$DESIGN" "$OUT/orientation.json" "$OUT/band.json"
uv run python tools/qa/mesh_quality_score.py "$OUT/band.json" --out "$OUT/score.json"
```

## v002 historical witness (superseded)

Review draft, not accepted VPM. Only the typical shell, FBX world metres: +4.65 to +51.90, pitch 3.15 m, 13 main storeys and 2 repeated recessed belt storeys. Podium, unique upper setbacks and roof excluded. No window/door infill, glass, capsules, baskets, posts or other inserts. Full-height curtain slots remain open. The checked FBX is a non-triangulated review export (8409 quads; 968 triangles only on horizontal shoulders).

Modelling split [D336]: plinth=inset; inset=windows, stained_glass, roof, flashings, posts; texture=panels; reason=training stage intentionally has no plinth or inset parts, only the typical shell and source opening interfaces.

- A/B sections at +17.50/+24.90 m from the source wall and opening fills. Deep marked exterior returns are retained; small facade relief is not inherited. The plan sheet overlays section linework, not an interior-wall slice. Rounded sampled hull chord deviation is 14.51/13.76 mm (A/B); no approved texture pitch in the supplied material-free FBX, so texture-step alignment is **not verified**.
- Opening spans and reveal depths from projected FBX source element geometry, not an RVT parametric opening or a frame/glazing work order. A fitted projection is used for the cavity back plane, not a copy of the sloped native reveal mesh. Three separate provisional IDs distinguish regular vent cladding, render returns, belt vent cladding. No confirmed finish colours: read-only Revit endpoint refused the connection, and no document was opened/saved/edited.
- Mesh quality #1616: 88.930; 100% quads, zero slivers/n-gons on vertical facade and reveals, shoulders excluded from this band score. Fresh Blender 4.4 FBX readback: zero inverted faces and zero inward facade faces; maximum correspondence drift 9 µm. Four self-intersection candidates remain; no duplicate/isolated geometry at the reported 2 mm tolerance. Horizontal shoulder and continuous curtain seams remain review items; belt shoulders are a storey-boundary approximation, not certified exact source elevations. The stage has intentionally open top/bottom and window/reveal mouths.
- Evidence: `G:/Мой диск/AGR-evidence/1619-body-training/tower-B/v002/`, review copy `C:/x/review-63B/63B_Stage1_v002.fbx`. No Max auto-open per Gate 1. The FBX, sheet, input sections, source opening ledger, readback and score are checksum-bound there.
