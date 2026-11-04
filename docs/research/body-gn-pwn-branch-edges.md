# Body GN TOW02: which edges make the self-intersected mesh non-PWN

Research card t_03a8a042 (report only, no writer change). Parent: `docs/research/body-gn-z0-snap-attribute-probe.md`
(task 1 of its proposals). Blender 5.1.2, headless, scratch copies only.

## Summary

- **Parent counts reproduced.** Unchanged contours: boolean 32,053 polys, **9,426** duplicate keys (1 same / 9,425 opposite), 4 unbalanced output edges. only_8_10: 39,988 polys, **14,207** (0 / 14,207), 4 unbalanced output edges.
- **The non-PWN edges sit at the 13.7 m in-band split** (band 2 top / band 3 bottom), in one place: x 59.73–59.87, y 403.54–403.71. All 4 boolean-output edges in both variants are the same 4 edges, around a vertical triangle that is one float32 ulp tall (z 13.7 `33335b41` → 13.700001 `34335b41`).
- One of the 4 edges has a single incident face (an open boundary). The other 3 have odd net orientation (±1).
- **The exact self-intersection** (`bpy.ops.mesh.intersect`, solver EXACT, on a copy of the weld output) shows the same 4 edges in only_8_10. On the unchanged contours it shows 3 more at the **65.4 m in-band split** (band 8 top, `cdcc8242`/`cecc8242`, x 50.93–51.23, y 390.15–390.44). The boolean output drops these 3 edges.
- **Answer.** Both in-band splits make the mesh non-PWN on the unchanged contours. Only the 13.7 m split does so on only_8_10, which also removes band 8's 65.4 m split. Nothing sits elsewhere.
- **Implication.** The PWN branch needs both splits gone. The full snap skipped both of them (the lower top has two float32 z values), yet the parent saw 0 unbalanced edges there. One explanation fits: the JSON rewrite of band 2's `band_h` redistributes that split (418/500 refs) and removes the 65.4 m split. This card did not rerun the snap variant.

## Findings

### Counts reproduced (verified, this run)

| Variant | Boolean polys | Duplicate keys (same/opp) | Coord extras | Boolean-output unbalanced edges | Weld unbalanced edges | Self-intersect polys | Self-intersect unbalanced edges |
|---|---|---|---|---|---|---|---|
| parent report, unchanged | 32,053 | 9,426 (1/9,425) | 9,356 | 4 | 1,418–1,516 (range) | — | — |
| unchanged, this run | 32,053 | **9,426 (1/9,425)** | 9,356 | **4** | 1,430 | 32,054 | **7** |
| parent report, only_8_10 | 39,988 | 14,207 (0/14,207) | 14,123 | 4 | — | — | — |
| only_8_10, this run | 39,988 | **14,207 (0/14,207)** | 14,123 | **4** | 1,456 | 39,990 | **4** |

### Unbalanced edges (verified, `run4.json`)

z is shown as float32 hex: `33335b41` = 13.699999809, `34335b41` = 13.700000763, `cdcc8242` = 65.400001526,
`cecc8242` = 65.400009155. "net" is the edge's orientation sum over its faces, the `is_pwn` rule. Faces: `vert` = vertical, `up`/`down` = horizontal facing up/down, `slope` = a sliver tilted by one ulp.

**13.7 m split, band 2 top / band 3 bottom.** The same 4 edges appear in the unchanged boolean, unchanged self-intersect, only_8_10 boolean and only_8_10 self-intersect outputs.

| # | Endpoint A (x, y, z hex) | Endpoint B (x, y, z hex) | Length m | Faces | Net | Incident faces |
|---|---|---|---|---|---|---|
| 1 | 59.730, 403.540, `33335b41` | 59.842, 403.706, `34335b41` | 0.2002 | 1 | +1 | vert tri (13.7→13.700001), open boundary |
| 2 | 59.730, 403.540, `33335b41` | 59.842, 403.706, `33335b41` | 0.2002 | 1 | −1 | down quad at 13.7 (band 3 bottom) |
| 3 | 59.872, 403.685, `34335b41` | 59.842, 403.706, `34335b41` | 0.0366 | 3 | −1 | up tri at 13.700001, vert tri (1 ulp), vert quad 13.700001→17.1 |
| 4 | 59.872, 403.685, `34335b41` | 59.842, 403.706, `33335b41` | 0.0366 | 3 | +1 | vert quad 10.3→13.700001, vert tri (1 ulp), down tri |

Edges 1 and 2 run between the same two (x, y) points, one ulp apart in z at one end. Together with the 1-ulp vertical triangle they form a crack: the down-facing band-3 bottom quad closes on the lower z, and the riser closes on the upper z. Edges 3 and 4 are the T-junction of that riser with band 2's wall (10.3→13.700001) and band 3's wall (13.700001→17.1).

**65.4 m split, band 8 top / band 9 bottom.** These 3 edges appear only in the unchanged self-intersect output.

| # | Endpoint A | Endpoint B | Length m | Faces | Net | Incident faces |
|---|---|---|---|---|---|---|
| 5 | 50.928, 390.154, `cdcc8242` | 51.233, 390.438, `cecc8242` | 0.4167 | 3 | +1 | up quad (slope 1 ulp), vert tri (1 ulp), vert 10-gon 65.4→69.45 |
| 6 | 50.928, 390.154, `cdcc8242` | 51.233, 390.438, `cdcc8242` | 0.4167 | 3 | −1 | vert quad 30.7→65.4, vert tri (1 ulp), down tri |
| 7 | 51.233, 390.438, `cdcc8242` | 51.233, 390.438, `cecc8242` | 8e-6 | 3 | −1 | slope 6-gon, vert tri (1 ulp), vert 11-gon 65.4→69.45 |

This is the same pattern as the 13.7 m split: a 1-ulp riser where the band top changes float32 z, with odd edge sums at its ends. In only_8_10, band 8's z0 moves and its top becomes single `cdcc8242` (parent, horizontal table: "only 8 … (single)"). The 65.4 m split, and with it these 3 edges, are gone.

### Why the boolean output shows only the 13.7 m edges (interpretation, not proven)

`mesh.intersect` with `separate_mode='NONE'` runs the exact solver with no boolean operation: self-intersection only, no cell or raycast classification. So its output (32,054 polys) is close to the solver's `tm_si`. The union then keeps or drops each patch. Around 65.4 m, the raycast classification dropped the faces that carried the odd sums. Around 13.7 m it kept them. The `is_pwn` decision is taken on `tm_si` before that selection (source below). So the self-intersect output, not the boolean output, is the better proxy, and on the unchanged contours it names both splits.

### Source (read, not re-verified this run)

Blender v5.1.2 `mesh_boolean.cc`: `is_pwn` (line 1352) returns false if any edge of the self-intersected triangle mesh has a non-zero orientation sum. `boolean_trimesh` then takes the raycast path for the whole mesh (lines 3584–3600). For `BoolOpType::None` (the `mesh.intersect` path) the self-intersected mesh is returned without classification. URL: https://raw.githubusercontent.com/blender/blender/v5.1.2/source/blender/blenlib/intern/mesh_boolean.cc. The parent report recorded the line numbers and file hash. This card relies on that reading and did not refetch the file.

### Caveats

- `mesh.intersect` writes back through BMesh, which rejoins coplanar triangles into faces. Triangulation diagonals are balanced, so they cannot hide or add odd sums. BMesh could still merge or drop a duplicate face; 32,054 vs 32,053 polys shows the reconstruction is not identical to the GN boolean. The internal `pwn` flag was still not read (no debug build).
- The edge sums use vertex indices. Coordinate-equal vertices with different indices would count as different edges. Weld duplicate keys are 0, and both outputs come from the exact solver's merged vertices.

## How it applies to this repository

- `tools/methods/body/body_blender.py` (`_gn_tree`, cap construction; writer `24c94691` lines 72–106): the PWN branch is blocked by 1-ulp risers where one band's extruded Top faces land on two float32 z values (13.7 m, 65.4 m). The source is extrude height `band_h = z1 − z0` in float32 per face, as measured in the parent report. Any fix has to make each band's top a single float32 z, not just make interfaces coincide. No change was made to that file.
- `docs/research/body-gn-z0-snap-attribute-probe.md`: its "Mechanism (consistent, not proven)" now has concrete edges. The edges cannot be quoted for the snap variant until that variant is rerun with `run4.py`.
- Scratch: `C:/x/t_03a8a042/run4.py` (SHA-256 in `C:/x/t_03a8a042/FROZEN_SHA256SUMS.txt`), output `run4.json` and `run4.log`. Library reused read-only: `C:/x/t_ad9bc345/{snap.py,probe.py,census.py,detail.py,run1.json,in/contours.json}`. The JSON is small (about 40 KB) and is not committed, so no Drive upload was needed.

### Script (`C:/x/t_03a8a042/run4.py`, abridged)

```python
# loads C:/x/t_ad9bc345/snap.py as a library (P = probe, build_cap_ids, CONTOURS, run1 z0 changes)
for name, c in {"unchanged": contours, "only_8_10": contours_with_band8_band10_z0_from_run1}.items():
    me = build_cap_ids(c)
    b = P.tap_eval(me, "boolean", False)          # pinned 24c94691 tree
    A = unbalanced(b["coords"], b["polys"])       # is_pwn rule on boolean output
    w = P.tap_eval(me, "weld", False)
    o = new object from w; edit mode; select all
    bpy.ops.mesh.intersect(mode="SELECT", separate_mode="NONE", solver="EXACT")
    B = unbalanced(o.data)                        # is_pwn rule on exact self-intersection

def unbalanced(coords, polys):                    # net orientation per undirected index edge
    tot[(min(a,b), max(a,b))] += 1 if a < b else -1  for each directed face edge a->b
    return edges with tot != 0, with endpoint z (float32 hex), band, incident face classes
```

Reproduction:

```text
B="C:/Program Files/Blender Foundation/Blender 5.1/blender.exe"
"$B" --background --factory-startup --python-exit-code 1 --python C:/x/t_03a8a042/run4.py -- C:/x/t_03a8a042/run4.json   # ~44 s
python C:/x/t_03a8a042/show.py
```

## Proposed next tasks

1. **Rerun the edge locator on the full-snap variant.** Scope: report-only. Run `run4.py` with `snapped_contours.json` added as a variant. Confirm that the self-intersect output has 0 unbalanced edges, and record where band 2's redistributed 13.7 m split went (418/500 refs) and why it no longer leaves an open riser. This settles whether the full snap's PWN result comes from the 13.7 m geometry by chance. Value M, effort S. Archive: no roadmap link (#727 is closed; no open roadmap issue covers the GN body variant).
2. **Single-float32-top rule for the GN body cap (design note).** Scope: report-only. Specify a rule that makes each band's extruded top one float32 z, for example choose `z0` so that `float32(z0) + float32(band_h)` rounds to one value for every face. Test it on TOW02 with `run4.py` (target: 0 unbalanced edges on self-intersect and no new twins). Value M, effort M. Archive: no roadmap link (the GN line is parked behind the kernel route #753 unless the user reopens it).

## Open questions for the user

- The PWN blockers are now identified: 1-ulp risers at the 13.7 m and 65.4 m in-band splits. Keep the GN body line (task 2), or park it in favour of the kernel route #753?
- The card policy says not to run DCC applications, but the card body asks for a Blender run. As in the parent card, Blender ran headless on scratch copies only. Is that the accepted reading for report-only research cards?
