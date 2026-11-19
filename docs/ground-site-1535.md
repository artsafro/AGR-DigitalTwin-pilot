# Ground DXF INSERT placement (#1535)

## Contract

`dt ground site SPEC NEW_OUT` and `agr ground site SPEC NEW_OUT` use the same
`dt_ai.geometry.ground_site.covers_from_dxf` adapter. Existing model-space string handles stay valid.
A block HATCH needs its **outermost-first** placement chain, not a manually exploded/model-space copy:

```json
{"id": 1, "name": "Paving", "hatches": [
  {"handle": "HATCH_HANDLE", "insert_chain": ["OUTER_INSERT", "INNER_INSERT"]}
]}
```

An MINSERT step is `{"handle":"INSERT_HANDLE","cell":[row,column]}` (zero-based).
Select a cell explicitly, including `[0,0]`; the adapter never silently expands a whole array.
The first INSERT must belong to model space; every next INSERT and the final HATCH must belong to
the preceding block. Block base points, translation, rotation, uniform XY scale, XY reflection and
nested placements are composed before world-unit chord flattening. Areas are measured from the
transformed polygons. Z scale may differ from XY for a planar hatch; zero/singular scales,
non-uniform XY scales, tilted placements/boundaries and non-finite values are named errors.

A HATCH handle may appear **once across the entire request**, even through different INSERTs or
MINSERT cells. A repeated identity is a named error, not a union. Use separate requests when inspecting
multiple placements of one definition. This deliberately conservative contract avoids silent merging.
Unknown cover/reference keys, missing handles and broken chains are errors.

### Explicit self-touching interpretation [D343]

The default refuses invalid rings. Only an explicitly authorized source row may add
`"self_touching":"even-odd"`. Invalid flattened rings are noded along their existing segments,
polygonized, and every positive-area odd-parity face is retained; there is no area cutoff,
buffer repair, coordinate snapping or moved source edge. Separate HATCH rings still combine by XOR,
so nesting/holes retain the historical interpretation. Valid rings use the unchanged path.
This is not permission to resolve competing material assignments or repair source files.

### Explicit bounded TIN edge continuation

The full Silikatny boundary extends beyond the original relief support. Its existing #1315 permissions
([G1](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/1315#issuecomment-6872153353),
[standing rule](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/1315#issuecomment-6874264219))
allow the nearest original TIN plane on these small remainders. The proof therefore supplies:

```json
{"params":{"relief_extension":{"max_m":1.5,"reason":"source-bound approval and measured remainder"}}}
```

This is an explicit opt-in, not a new general model policy. The default still allows only the noding
snap margin. The bound must be finite, positive, greater than snap, and accompanied by a non-empty
reason. Beyond it the build still refuses. The report records every continuation sample, actual maximum,
reason and `not_source_elevations:true`; original relief points are not changed/removed. The OBJ
pointwise zero readback uses exactly the same declared continuation bound. The face-error metric remains
an error against original TIN intersections, not an independent certificate for assumed heights.

The full source also exposed a micrometre-rounded shared-edge split that stalled relief refinement on
a skinny triangle. The minimized real-source regression preserves that witness. Relief insertion now uses
a finer identity grid and face planes are evaluated around a local corner to avoid cancellation;
outline recovery retains its previous micrometre grid. No relief tolerance was increased.

## Real source proof

Spec: [`ground-site-1535-full.json`](../jobs/SIL13-COLD-1315/ground-site-1535-full.json).
Source DXF SHA256: `35b537cfe7f05236bf13c2159ef4ae689118162c0f4418a2a93983437c4e3cf4`.
Boundary: `33FBCEF`, **12958.738864 m²**, no crop. Same original #1315 DXF, no source edits.

```text
uv run agr ground site jobs/SIL13-COLD-1315/ground-site-1535-full.json tmp/full-1535-v006
exit 0; geometry_status=built; 37911 exported/read-back triangles; passed=false
```

- 24 in-bound covering HATCH instances, grouped by source layer/background into 10 diagnostic IDs;
  156 regions before clipping. Four hatches (`33F183E`, `33F183F`, `33F1840`, `33F1841`)
  are placed through real INSERT `33FBCCB`, rotation **208.9900925356413 degrees**.
- Complete recursive source inventory: 24 selected + 297 reasoned drops (non-cover layers or
  outside the site); 0 extraction errors. The full per-instance inventory is in external evidence.
- Only `33F1841` and `33FBCC1` need even-odd interpretation; their rows opt in [D343].
- 1685 source relief points; original support remainder **7.608474253 m²**;
  maximum original boundary-to-support distance **1.482247067 m**.
  19 continuation sample points exceed snap, actual maximum **1.482384392 m** after noding,
  below the explicit 1.5 m bound. These are assumptions, not surveyed elevations.
- Original-TIN face error **9.856807054 mm**, 0 faces above 10 mm; pointwise exported zero check `pass`.
- Skirt and UDIM readback completed; the only build finding is the existing separate UCX owner.
  This does not certify delivery topology, materials, footprint composition or visual acceptance.

Control:

```text
uv run dt ground site jobs/SIL13-COLD-1315/ground-site-1406-pilot.json tmp/fragment-1535-final
exit 0; 798 triangles; entire readback dictionary equals committed ground-site-1406-report.json
```

The historical D283 fragment is unchanged, including its existing diagnostic material policy. The full
spec is a separate full-boundary adapter proof, not a replacement for that control or #1315's accepted
production composition. Seeded/rolled lawn and asphalt use explicit diagnostic placeholder colours where
the source has no background colour; none is presented as an accepted production material.

## Evidence

`G:/Мой диск/AGR-evidence/1535-ground-inserts/v001/` contains actual full/fragment flat and projected
OBJs, reports, source inventory, exact spec snapshot, summary and a same-frame before/after OBJ plan plot.
All **10 files** were copied/read back and verified against `SHA256SUMS.txt`.

- `SHA256SUMS.txt`: `6ebc2dde0e60422d8a7814745bab1d5f89587f4c5fbbdd033781b909815bcbfb`
- `before-after.png`: `6dbd90d6df60e64112219d2ae737af8f70a8f89b2c0402a9da280ff15a1549cd`

The plot is a diagnostic visualization of actual exported triangles, not a native DCC beauty render.
No Max/Blender scene, customer drawing, library or accepted #1315 artifact was mutated.
UCX, MAF/Flora, footprint cut-out/composition, native xView, quad master and delivery acceptance remain
with their existing owners, not waived by the successful command. `passed` remains false.

## Regression witnesses

`tests/test_ground_site_inserts_1535.py` covers scaled/rotated/mirrored parents, nested placement with
non-zero base points, all six MINSERT cells, repeated HATCH identity across placements, broken/partial
chains, invalid numeric/unsupported transforms, explicit/default even-odd, small positive lobes down to
1e-18 m², bounded continuation/default refusal, the minimized source refinement failure, unknown mapping
keys, source mutation during build, resolved/hardlink input aliases, foreign partial paths, stale outputs
and a fresh-process placed-hatch positive before repeated refusal.

Generated similarity probe: 5 scales × 13 angles × 2 reflection states = **130/130** exact-area/contour
comparisons against an independent analytic oracle. The nested MINSERT fixture adds **6/6** cell oracles.
Full suite: deferred to merge batch (rule 68).
