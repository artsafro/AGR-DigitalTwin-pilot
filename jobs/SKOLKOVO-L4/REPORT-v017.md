# Skolkovo L4 — v017: first whole-building assembly pass through the kernel, export + readback, delivered-frame check

**`passed=false`.** All 49 PartsList v010 parts were run through kernel operations for the first time (FBX only, no
Revit). The assembly exports and reads back 1:1, but 95 of 6,955 source objects are not built yet, the total is
over the plan budget, and joints, UV/materials/UCX, visual review and SINTEZ are still open. No PR yet.

## What ran (`tmp/skolkovo-l4-v017/`; scripts, logs, runs, FBX on Drive `evidence-v017/`)

- `asm.py` is the per-object decision table. For every source object of the 47 non-rod parts (sha-bound PartsList
  `fca5b23b…2302`), it tries kernel operations on an isolated object scene. The cheapest one that applies wins, in
  this order: `keep` (source ≤ the part's per-object budget share), `primitive_box`, `rebuild_by_contour` top /
  front / side, then `keep`. Every result goes through `run_operation` / `check_operation`: open borders,
  see-through holes (26 directions), back faces, close overlap.
  Sources: facade facts `0de28302…` ↔ `source-geometry-v002` (11,510 buffers, names and tris 1:1). v1 facts
  `dedcd2a2…` ↔ `v1-exterior`, shifted by (42.266, −35.629, 0) into the facade frame.
  Run `run-01`: 24 processes, about 37 min.
- `rods.py` collects the accepted rods. Masts are v014 final 3628/3651/3674 and v015 repair-3 3697/3719. KNS is the
  v016 `kns-run-05` set of 108 proxies, each sha256-checked against its manifest. Same frame shift as v1.
- `repair1.py` handles every object rejected in run-01: `rebuild_by_contour(allow_multi=True)`, which builds one
  prism per contour piece, as the kernel's own rejection asked.
- `export_v017.py` (Blender 5.1, factory startup) writes one mesh object per part to a new versioned FBX. Then
  `tools/blender/fbx_structure.py` reads it back. The repair-1 meshes are not in this FBX yet.

## Results (`evidence-v017/summary-v017.json`, `repair1-v017.json`, `cmp-v017.json`)

| | objects | built | not built | tris | plan budget |
|---|---:|---:|---:|---:|---:|
| run-01 (47 parts) + rods (2 parts) | 6,955 | 6,751 | 204 (29 no buffer, 175 rejected) | 161,694 | 147,000 |
| + repair 1 (175 rejected) | | +109 | 95 (29 no buffer, 66 rejected) | +7,536 → 169,230 | 147,000 |
| + repair 2 (66 rejected, per connected component) | | +18 | **77 (29 no buffer, 48 rejected)** | +2,746 → **171,976** | 147,000 |

- Operation mix in run-01: `primitive_box` 5,593, `keep` 711, `contour` top 164 / side 93 / front 77, plus the 113 accepted rod proxies (6,751 in total).
  Repair 1 rebuilt 107 of the 120 `v1_baseline_roof_access_railing` objects (6,952 of 7,680 tris) and 2 railings.
- Repair 2 (`repair2.py`, `evidence-v017/repair2-v017.json`) split each object into connected components and ran
  the decision table per component; an object is built only when every component applies. It built 18 of 66 (the
  last 13 v1 roof-access railings, so 120/120 there now; 3 roof/entrance details; 2 railings).
  The 48 still rejected are mostly single-component objects:
  - plinth flashings 10+1, a single profile railing each;
  - roof/entrance details 15+1;
  - v1 external structure 7, which lies outside the building;
  - mullions 6, ladders 3, railings 3, others 2.

  These need a per-profile loft recipe like the v016 KNS recipes. Repair 2 meshes are on Drive; they are not in the
  v017 FBX.
- Rejected after repair 1 (66), with the kernel's reasons:
  - "prism is not a closed oriented 2-manifold after the 0.1 mm weld" (68 tries).
  - "contour repeats a vertex" (39).
  - Silhouette 82–287 mm over the limit (25).

  Rejected per part: roof/entrance details 18, v1 roof-access railing 13, plinth flashings 10+1,
  v1 external structure 7, mullions 6, railings 4+1, ladders 3, others 3.
- The 29 objects without a buffer are v1 objects (mullions 18, reveals 7, glazing 4). They were not extracted in
  v006, whose rule was a conservative candidate rule. Each one is listed in the summary as `missing_source_buffer`;
  none was replaced by a default.
- Budget by operation (after repair 1):
  - `from_face`: 48,122 tris against a budget of 15,692. The kernel has no "exterior face only" operation. Thin
    panels whose plan is 2 tris (a face) become 12-tri closed boxes, because open single faces fail
    `open_borders_hidden` / `no_visible_back_faces` in isolation.
  - `contour_rebuild`: 115,604 / 122,584.
  - `detail_per_profile`: 5,468 / 8,688.
  - `primitive`: 36 / 36.

  Largest overruns:
  - cassette perimeter profiles +10,528. These are open 10-tri tubes, closed to 12 tris.
  - substrate reveals +9,058.
  - solid cassettes +7,362.
  - perforated cassettes +4,930.
  - roof skins +4,664.
  - soffits +2,448.
- Export / readback (`export/skolkovo_l4_assembly_v017.fbx`, sha256 `8368e0a5…ee73`): 43 objects, 161,694 tris.
  The readback matches 43/43 objects, and the tris match per object. Units are METRIC m (FBX unit scale 100). There
  are 6 empty parts: plinth flashings, roof/entrance details and ladders, all rejected, plus v1 mullions (no buffer).
  The FBX also has 0 material slots, no UV and no UCX: none of the three is built yet.
- Delivered frame (`cmp-v017.json`): the v006 registration pair maps source to the VPM candidate frame with a
  1e-6 m residual. At yaw 61.41°, the assembly's min corner (−28.02, −30.50) matches the delivered VPM bbox min
  (−28.12, −30.52). Every part except two lies inside the delivered `SM_BolshoyBulvar_64` bbox:
  - `v1_baseline_external_structure_frame` extends 34 m outside, so these v1 objects are not on this building. This
    is a scope question for the next run, not decided here.
  - The masts and KNS rise 0.5 m above the delivered z max (26.88 vs 26.38).
- Delivered reference sizes: NPM `0809_BolshoyBulvar_64_01.fbx` 49,657 tris, 1 node. VPM `SM_BolshoyBulvar_64.fbx`
  59,116 tris, 225 nodes, of which 223 are UCX. **The approved plan (147,000) is 2.5× the delivered VPM.** The masts
  alone (54,934) are about the size of the whole delivered VPM. This is reported, not acted on: budgets stay as
  approved at Gate 1.

## Fail-closed probes (`probe_v017.py`, 6/6)

- An unmapped facts hash is an error, and so is an out-of-range object row.
- A PartsList hash mismatch is an error.
- A NaN source mesh is not applied.
- An empty mesh is an error. This probe failed first (`keep` accepted an empty mesh), was fixed in `asm.py`, and
  run-01 was rechecked: 0 applied rows with src = 0 or tris = 0.
- `asm.py` on an existing output dir exits non-zero and writes nothing.

## L5 timing (2026-10-22, wall clock)

| Stage | Time |
|---|---|
| Context / source mapping | 20 min |
| Decision-table driver + sample | 15 min |
| run-01 (6,842 objects, 24 processes) | 37 min |
| Rods collection | 2 min |
| Export + readback + delivered-frame comparison | 10 min |
| Repair 1 | 13 min |
| Repair 2 | 20 min |
| Probes / report / evidence | 15 min |
| **Total** | **≈ 2 h 10 min** |

Cumulative since v013 (masts hub, KNS, assembly) ≈ 6 h; earlier stages are in RESUME-v009/v011.

## Next steps

1. 48 rejected objects (after repairs 1-2): a per-profile loft recipe, like v016 (plinth flashings, roof details,
   mullions, ladders). Then re-export the FBX with the repair-1/2 meshes merged.
2. 29 v1 objects without a buffer: extract them from the v1 FBX (3ds Max headless, one process, copy only), or
   report them as dropped with the reason.
3. `from_face` overrun (+32k): build an exterior-face operation in context (hidden open borders against the
   neighbour wall), or add it as kernel menu work. That needs a decision before replacing boxes by faces. The
   `v1_baseline_external_structure_frame` objects 34 m outside the delivered bbox need the scope question.
4. Joints (291 conditional) on the assembled scene; whole-scene `no_close_overlap`/hole check.
5. UV/materials (v008 appearance bindings), UCX, NPM derivation, then review tool, SINTEZ, suite via
   `suite_slot.py`, PR, dt-reviewer.

Drive `G:/Мой диск/AGR-evidence/353-skolkovo-l4/evidence-v017/`: 195 files, `SHA256SUMS.txt` sha256
`454ca30806e01efadcd4f4dea69b730c8f5a8d232f69240a788375827fb98ab8`, `sha256sum -c` 0 mismatches.
