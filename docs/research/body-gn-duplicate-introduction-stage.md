# Building-body GN: which writer stage first creates duplicate triangle keys?

`delivery_passed=false`. Report-only diagnosis. No writer repair, no face removal, no tolerance, gate, receipt or committed-row change. Input is `synthetic_drawing: true` (`contours.json` says so); nothing here describes a real building.

## Summary

- The opposite-winding duplicates of R11 (TOW02 `blender-gn-union`) first appear inside the Geometry Nodes tree, at the output of **Mesh Boolean (UNION, EXACT, Self Intersection)**. Its input (the 1e-5 weld output) has 0 undirected index-cycle duplicates. Its output has 9,426: 9,425 opposite winding and 1 same direction, 9,423 of them horizontal faces at band-boundary heights (6.9, 10.3, 17.1, 20.5, 23.9, 27.3, 65.4, 72.2, 76.25 m).
- The boolean is one node, so its interior cannot be observed. The bounded interval is `weld (Merge by Distance 1e-5) output -> Mesh Boolean output`.
- Merge by Distance 0.001 lowers the count to 7,938 n-gon pairs (all opposite). Applying the modifier, the opening stage (0 openings), `from_mesh` and `dissolve_limit` keep 7,938.
- `bmesh.ops.triangulate` turns them into 14,942 triangle extras (14,938 opposite, 4 same). 14,145 come from triangulating the duplicated n-gon pairs. 797 come from pairs of n-gons with *different* cycles whose triangles coincide. Those triangle keys appear first at triangulate, including the 13.7 m and 69.45 m levels. The frozen keys cannot say whether that overlapping geometry is older.
- The replay matches the baseline exactly. `to_mesh` and the receipt count 54,388, the raw FBX `Vertices` and `PolygonVertexIndex` arrays are equal to the preserved R11 FBX, and the unchanged public `fbx_readback.py` reads 39,446. Only the FBX file hash differs, because of header bytes.
- Two headless builds in Blender 5.1.2 (`ec6e62d40fa9`). Controls behaved as frozen. Input hashes were the same before and after.

## Findings

Labels: **verified** (I ran it or read the code) or **source claims**.

### Inputs and versions (verified)

| Item | Value |
|---|---|
| Writer | `24c94691e54736411d6f6d26c810c25d10505e90:tools/methods/body/body_blender.py` (`gn_union`, lines 145-189); `openings.py` copied verbatim |
| `contours.json` | `92a83fc90efd039126f8b86b57ff7fae1002bea72868d7193e27b2904535152e`: 13 bands, 26 + 12 polygons, no holes, no `openings` |
| Preserved R11 FBX | `b8b2f4d3431e444b37e0cf3732a7dbf00d17cff24bddc906a8e64469c60550a0` |
| Preserved receipt | `a3382904001873501de4d8f6cdfad5a64ec4cccf4ca3ffe3cf3751da60f9321f` |
| Pinned manifest | the same three lines are in `24c94691:docs/methods/building-body/SHA256SUMS` (tow02) |
| Blender | 5.1.2, build hash `ec6e62d40fa9`, `--background --factory-startup --python-exit-code 1`, two build processes and one public-readback process |
| `tools/blender/fbx_readback.py` | identical to the pinned file (`diff -q` empty) |

All three inputs were hashed under `C:/x/methods/building-body/tow02/` before the runs, then copied to `C:/x/t_f3e77f4a/in/`, and hashed again after the runs. The hashes did not change. The tracked writer and the source repository were not touched. No GUI scene was opened.

### Frozen definitions (written and hashed before the first real-input run, `census.py`)

- Directed cycle key: the vertex-index cycle rotated so that its minimum index comes first. Undirected key: the minimum of the directed key and the reversed directed key. Extras: `sum(n-1)` over keys with multiplicity `n > 1`. For each extra copy, *same* means its directed key equals an earlier copy, and *opp* means it is the reverse of an earlier copy.
- A sorted triangle key is reported only when every polygon has arity 3, so it does not exist before triangulate.
- Coincident-coordinate keys use the same classification on vertices quantised to 1e-6 (in the stage's own units). An index-key extra with no coord change is new duplicate topology. A coord-only extra that later becomes an index extra is a weld remap, not new geometry.
- Instrumentation only reads `bm.verts` / `bm.faces` / `me.vertices` / `me.polygons`. It calls no `validate` or `update` on live data. To see inside the GN tree, the pinned tree is copied with one node output routed to Group Output. That copy is evaluated on a **copy** of the cap mesh (`evaluated_get` -> `to_mesh` -> `to_mesh_clear`). The live object gets the untruncated tree and `modifier_apply`, as in the pinned writer.

### Controls (verified, run 1 and run 2)

| Control | polys | idx und. extras | same | opp | coord extras |
|---|---|---|---|---|---|
| Clean box, `create_cube` + triangulate | 12 | 0 | 0 | 0 | 0 |
| Two closed boxes 3 m apart (12 tris + 6 quads) | 18 | 0 | 0 | 0 | 0 |
| Triangle cycles `012, 012, 210, 120` | 4 | 3 | 2 | 1 | 3 |

### Stage table, TOW02 real input (verified; run 1 = run 2 at every row)

Columns: undirected index extras (same / opp), then the same for coordinate keys.

| # | Stage (pinned order) | verts | polys | arity | idx extras (same/opp) | coord extras (same/opp) | sorted-tri extras |
|---|---|---|---|---|---|---|---|
| 1 | cap tessellation | 3,426 | 3,350 | {3} | 0 | 0 | 0 |
| 2 | cap `remove_doubles` 1e-5 | 3,426 | 3,350 | {3} | 0 | 0 | 0 |
| 3 | cap normals up / `to_mesh` (GN input) | 3,426 | 3,350 | {3} | 0 | 0 | 0 |
| 4 | GN tap Flip Faces (bottoms) | 3,426 | 3,350 | {3} | 0 | 0 | 0 |
| 5 | GN tap Extrude Mesh | 6,852 | 6,776 | 3:3,350 4:3,426 | 0 | 0 | n/a |
| 6 | GN tap Join | 10,278 | 10,126 | 3:6,700 4:3,426 | 0 | 1 (0/1) | n/a |
| 7 | GN tap Merge by Distance 1e-5 (weld) | 7,198 | 10,126 | same | **0** | 1 (0/1) | n/a |
| 8 | **GN tap Mesh Boolean UNION EXACT self-int.** | 19,176 | 32,053 | 3..86 | **9,426 (1/9,425)** | 9,356 (1/9,355); 489 coord-degenerate | n/a |
| 9 | GN tap Merge by Distance 0.001 (= full tree) | 17,251 | 29,049 | 3..84 | 7,938 (0/7,938) | 7,938 | n/a |
| 10 | live `modifier_apply` | 17,251 | 29,049 | 3..84 | 7,938 (0/7,938) | 7,938 | n/a |
| 11 | after openings (schedule empty, 0 cut) | 17,251 | 29,049 | 3..84 | 7,938 | 7,938 | n/a |
| 12 | `bmesh.from_mesh` | 17,251 | 29,049 | 3..84 | 7,938 | 7,938 | n/a |
| 13 | `dissolve_limit` 0.0017 | 16,185 | 20,476 | 3..648 | 7,938 (0/7,938) | 7,938 | n/a |
| 14 | `triangulate` | 16,185 | 54,388 | {3} | 14,942 (4/14,938) | 14,942 | 14,942 |
| 15 | `bm.to_mesh` (receipt counts this) | 16,185 | 54,388 | {3} | 14,942 (4/14,938) | 14,942 | 14,942 |
| 16 | exported raw FBX `PolygonVertexIndex` | 16,185 | 54,388 | {3} | 14,942 (4/14,938) | 14,942 | 14,942 |
| 17 | preserved R11 FBX (reference) | 16,185 | 54,388 | {3} | 14,942 (4/14,938) | 14,942 | 14,942 |
| 18 | public `fbx_readback.py` on the run-1 FBX | - | 39,446 | {3: 39,446} | - | - | - |

Row 9 equals row 10 in every count, so the truncated-tree copy is a faithful view of the live apply. Rows 16 and 17 have equal `Vertices` arrays and equal `PolygonVertexIndex` arrays (`RAW_VS_PRESERVED {"vertices_equal": true, "polys_equal": true}`). The new FBX hashes (`75665081…`, `1257e1fe…`) differ from `b8b2f4d3…` only outside these arrays. That is not geometry drift. Receipt `triangles` = 54,388 in both runs. My numbers at rows 16-18 match the #743 report (**source claims** there: 54,388 raw, 14,942 extras = 14,938 opp + 4 same, 39,446 readback).

### Where the duplicates sit (verified, run 2 `detail.py`)

| Stage | horizontal extras | vertical | other | extras area | horizontal extras by z (m) |
|---|---|---|---|---|---|
| Boolean | 9,423 | 3 | 0 | 3,782.442 | 6.9: 882, 10.3: 1,105, 17.1: 1,345, 20.5: 1,431, 23.9: 1,413, 27.3: 1,502, 65.4: 806, 72.2: 792, 76.25: 147 |
| Merge 0.001 … dissolve | 7,938 | 0 | 0 | 2,725.568 | 6.9: 769, 10.3: 919, 17.1: 1,121, 20.5: 1,201, 23.9: 1,170, 27.3: 1,153, 65.4: 710, 72.2: 754, 76.25: 141 |
| Triangulate … FBX | 14,938 | 0 | 4 | 3,786.039 | adds 13.7: 284, 69.45: 266; others grow |

Every one of these heights is a `z1` of one band and the `z0` of the next (`contours.json` bands). So the twins are the shared horizontal interfaces between stacked prisms: the top cap of band *k* (up) and the flipped bottom cap of band *k+1* (down). The exact union leaves both copies in its output instead of removing them as internal faces. The final extras area, 3,786.039, equals the #743 figure.

Triangulate provenance. On a `bm.copy()` with a per-face source layer, triangulated the same way, the 14,942 triangle extras split as follows:

| Origin | extras |
|---|---|
| both copies from n-gons that were already an undirected duplicate pair | 14,145 |
| both copies from n-gons that were not duplicates (different cycles, coinciding triangles) | 797 |
| same source n-gon / mixed | 0 / 0 |

So triangulate creates no new geometry, but 797 duplicate triangle keys become visible there for the first time. These include all of 13.7 m and 69.45 m. Before triangulate those faces are coplanar overlapping n-gons with different vertex cycles, which a cycle key cannot see. This report does not say which stage created that overlap.

### Observed anomaly, not explained

After the 1e-5 weld (row 7) there is one coord-only opposite pair: triangles `(620, 621, 3605)` and `(620, 6714, 621)` at z ≈ 10.3. Vertices 3605 and 6714 print the identical float coordinate `(59.84199905, 403.70599365, 10.30000019)`, yet Merge by Distance 1e-5 left them separate. Its neighbours 620/621 sit at z = 10.30000114, about 1 µm higher, which is a float32 step. It is one face pair and it does not explain the 9,426 at row 8. I did not investigate it further.

### External sources (source claims, not re-verified beyond reading)

- Blender Manual, Mesh Boolean node: the Exact solver "offers the best results when there are coplanar faces or other overlapping geometry". *Self Intersection* "correctly calculates cases when one or both operands have self-intersections". *Hole Tolerant* "optimizes the Boolean output for non-manifold geometry" — https://docs.blender.org/manual/en/latest/modeling/geometry_nodes/mesh/operations/mesh_boolean.html (the page is the 5.2 LTS manual; the run used 5.1.2). The R11 output contradicts the expectation that coplanar opposite interfaces get resolved. Why the solver kept them was not investigated.
- Blender Manual, Merge by Distance node — https://docs.blender.org/manual/en/latest/modeling/geometry_nodes/geometry/operations/merge_by_distance.html.
- #743 report `docs/research/body-gn-triangle-count-boundary.md` (branch `docs/research-body-gn-triangle-count-boundary`): import-time `Mesh.validate` is where 54,388 becomes 39,446. That parser is reused here as `fbxraw.py`.

## How it applies to this repository

- `tools/methods/body/body_blender.py` (pinned `24c94691`) `_gn_tree` lines 85-104: the `GeometryNodeMeshBoolean` node (UNION, EXACT, Self Intersection) fed by `join -> weld(1e-5)` is the first stage whose output carries duplicate undirected keys. Lines 182-183 (`dissolve_limit`, `triangulate`) carry them on and expand them. Line 189 counts the expanded set as the receipt.
- `tools/blender/fbx_readback.py` and `tools/methods/methods_metrics.py`: they read the post-`Mesh.validate` mesh (39,446), as #743 showed. `docs/methods/building-body/results.jsonl` R11 is unchanged by this report.
- `docs/domain/areas/body.md` BODY-I (outward, complete visible faces), BODY-J (duplicate ceiling at 0.002 m) and BODY-N (triangulated export, read back) are the rules these twins touch. Nothing here certifies or fails them.
- Evidence (outside git): `G:/Мой диск/AGR-evidence/t_f3e77f4a-body-gn-duplicate-stage/` (scripts, `run1/`, `run2/` census JSON + logs + FBX, `SHA256SUMS.txt`, `FROZEN_SHA256SUMS.txt`). Working copy: `C:/x/t_f3e77f4a/`. Frozen script hashes: `census.py 61bdfae6…`, `instrument.py 8b3d2213…`, `fbxraw.py 06e9c4ff…`, `openings.py 57481688…`, `detail.py` / `instrument2.py` in `FROZEN_SHA256SUMS.txt`.

## Proposed next tasks

1. **Probe why the exact union keeps band interfaces (no writer change).** Scope: on scratch copies of `contours.json` `92a83fc9…`, evaluate the weld->boolean interval on copies and record the row-8 census for each probe. Probes: (a) the pinned settings; (b) *Hole Tolerant* on; (c) the band `z0` snapped to the float32 value that Extrude Mesh produces for the band below; (d) one band pair only (6.9 m). Decision boundary: this task only reports which input property makes the boolean keep the twins. Picking a repair, changing tolerances, or rebuilding rows is left to the user. Value: it names the actual mechanism, which is the input for any writer fix. Effort **S**. Advances #727.
2. **Writer repair candidate, gated on proposal 1 and a user decision.** Scope: change only the stage that proposal 1 names. Accept the change only when row 8 extras = 0, the 797-class triangle extras = 0, raw FBX polygons = public readback triangles, and openings and volume stay equal on R3/R7/R11. Decision boundary: the user chooses (i) whether a changed GN writer replaces the R11 method row or is added as a new variant, and (ii) which winding/surface is correct where an interface is a real exterior ledge (BODY-S). This report does not choose. Effort **M**. Advances #727.

## Open questions for the user

- At the band interfaces where a lower band is wider (real ledges, BODY-S), only part of each interface is exterior. Should a future fix keep the exterior part with an up-facing normal and drop the internal part? Or should the GN variant stay as measured, as evidence of a solver limitation?
- The 797 triangle extras from non-identical n-gons (13.7 m, 69.45 m and others) are coplanar overlaps that cycle keys miss before triangulation. Should a later pass measure overlap area per level, rather than keys?
- Should the receipt keep counting post-triangulate polygons with twins (54,388)? #743 asks the same question; this report does not answer it.

## Reproduction

```text
BL="C:/Program Files/Blender Foundation/Blender 5.1/blender.exe"   # 5.1.2 ec6e62d40fa9
"$BL" --background --factory-startup --python-exit-code 1 --python C:/x/t_f3e77f4a/instrument.py -- \
  C:/x/t_f3e77f4a/in/contours.json C:/x/t_f3e77f4a/run1/SM_Vyatskaya_Vl_47_49_013.fbx SM_Vyatskaya_Vl_47_49_013 \
  C:/x/t_f3e77f4a/run1/census.json C:/x/t_f3e77f4a/in/SM_Vyatskaya_Vl_47_49_013.fbx
# run 2: same with instrument2.py and run2/ (adds detail.py and the triangulate provenance on a bm.copy())
"$BL" --background --factory-startup --python-exit-code 1 --python tools/blender/fbx_readback.py -- \
  C:/x/t_f3e77f4a/run1/SM_Vyatskaya_Vl_47_49_013.fbx C:/x/t_f3e77f4a/run1/public_readback.json
```

`instrument.py` is the pinned `gn_union` copied line by line, with `rec_*` calls between stages and `tap_eval(me, tap)` for the six GN node outputs. `cut_openings` is reduced to a guard that raises if the TOW02 schedule is not empty (it is empty: `SCHEDULE 0`). `fbxraw.py` is the #743 `fbx_duplicate_keys.py` parser (`parse_property`, `walk`) plus a `read()` that returns coordinates and polygon index lists. Both are in the evidence folder. The classifier and the GN tap are below.

### `census.py` (frozen classifier)

```python
from collections import Counter
QUANT = 1e-6

def canon_dir(c):
    c = list(c); i = c.index(min(c)); return tuple(c[i:] + c[:i])

def _classify(cycles):
    dirs = [canon_dir(c) for c in cycles]
    und = [min(d, canon_dir(list(reversed(d)))) for d in dirs]
    seen, same, opp = {}, 0, 0
    for d, u in zip(dirs, und):
        prev = seen.setdefault(u, [])
        if prev:
            if d in prev: same += 1
            else: opp += 1
        prev.append(d)
    cd, cu = Counter(dirs), Counter(und)
    return {"directed_extras": sum(n - 1 for n in cd.values() if n > 1), "undirected_unique": len(cu),
            "undirected_extras": sum(n - 1 for n in cu.values() if n > 1), "same_dir_extras": same, "opp_dir_extras": opp}

def census(coords, polys):
    ar = Counter(len(p) for p in polys)
    out = {"verts": len(coords), "polys": len(polys), "arity": dict(ar),
           "degenerate_idx": sum(1 for p in polys if len(set(p)) != len(p)), "idx": _classify(polys)}
    q, qid = {}, []
    for x, y, z in coords:
        qid.append(q.setdefault((round(x / QUANT), round(y / QUANT), round(z / QUANT)), len(q)))
    cp = [[qid[i] for i in p] for p in polys]
    out["degenerate_coord"] = sum(1 for p in cp if len(set(p)) != len(p))
    out["coord"] = _classify([p for p in cp if len(set(p)) == len(p)])
    if polys and all(len(p) == 3 for p in polys):
        cs = Counter(tuple(sorted(p)) for p in polys)
        out["sorted_tri_extras"] = sum(n - 1 for n in cs.values() if n > 1)
    return out
```

### GN tap (inside `instrument.py`)

```python
def tap_eval(me, tap):                       # tap in flip, extrude, join, weld, boolean, merge
    cme = me.copy()                          # copy of the cap mesh incl. band_h; live mesh untouched
    o = bpy.data.objects.new(f"tap_{tap}", cme); bpy.context.scene.collection.objects.link(o)
    mod = o.modifiers.new("tap", "NODES"); mod.node_group = _gn_tree(tap)   # pinned tree, output re-routed
    ev = o.evaluated_get(bpy.context.evaluated_depsgraph_get())
    m = ev.to_mesh(); rec_me(f"GN tap: {tap}", m); ev.to_mesh_clear()
    bpy.data.objects.remove(o); bpy.data.meshes.remove(cme)
# _gn_tree(tap): identical nodes/settings to pinned lines 72-106; last line
#   links.new({"extrude": ext.outputs["Mesh"], "flip": flip.outputs[0], "join": join.outputs[0],
#              "weld": weld.outputs[0], "boolean": boo.outputs[0], "merge": merge.outputs[0]}[tap], gout.inputs[0])
```

### Triangulate provenance (run 2, on a copy)

```python
cp = bm.copy(); lay = cp.faces.layers.int.new("src")
for i, f in enumerate(cp.faces): f[lay] = i
bmesh.ops.triangulate(cp, faces=cp.faces)      # same call as the live bm, which is triangulated right after
# group triangles by undirected key; classify each extra by whether its two source n-gons were an
# undirected-duplicate pair at the dissolve stage -> 14,145 / 797 / 0 / 0
```
