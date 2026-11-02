# Building-body GN: where 54,388 writer triangles become 39,446 on readback

`delivery_passed=false`. Report-only. No metric, gate, benchmark row, or writer change.

## Summary

The preserved R11 FBX is the file named by the committed row. Its SHA-256 is `b8b2f4d3431e444b37e0cf3732a7dbf00d17cff24bddc906a8e64469c60550a0` (907,948 bytes), the same value as `24c94691:docs/methods/building-body/results.jsonl` row R11 `output_sha256` and `24c94691:docs/methods/building-body/SHA256SUMS`. The variant receipt beside it says `"triangles": 54388`. The committed row and a fresh public readback both say 39,446.

Those two numbers are two counts of one mesh. The binary FBX stores 54,388 triangles, all arity 3, none with a repeated index, none with fan area `<= 1e-12`. 14,942 of them are a second polygon on a vertex triple that already has a polygon: 14,938 are the opposite winding, 4 repeat the same directed cycle. `Mesh.validate(clean_customdata=False)` in Blender 5.1.2 keeps exactly one polygon per undirected vertex key and returns 39,446 polygons and 39,446 loop triangles. The FBX importer calls that validate (`import_fbx.py:1924`). The public reader then counts `len(mesh.loop_triangles)`.

The writer receipt matches the on-disk polygon count, so this gap is not a stale total. The exporter wrote all 54,388 polygons, so this gap is not export filtering. Evaluated-mesh counts after import stay 39,446. The first divergent stage is import-time `Mesh.validate`. Vertex count stays 16,185. Every undirected key present before validate is present once after it. The extra copies add 3,786.039 m² of area on corners that already contribute 3,786.039 m² to the kept surface; the kept unique-key area is 18,036.298 m². Dropping the opposite winding is a real change of stored orientation, and this report does not claim shell or xView equivalence of the 54,388-face file with the 39,446-face readback.

The GN writer was not run again. The preserved FBX is already that writer's output. Inputs were byte-identical after the probes.

## Findings

Labels: **verified by me (command/code)** or **source claims**.

### Definitions

**Source claims**, pinned commit `24c94691` (`methods/building-body: combined regression of the round-1 and round-2 guards on one input (#727 review 2, P1-2)`). A separate #729 review document was not in this worktree. The task card attributes the question to #729. The unexplained gap is the pinned variants text.

- Writer polygon count. `tools/methods/body/body_blender.py:183-189` triangulates with `bmesh.ops.triangulate`, writes `bm.to_mesh(obj.data)`, and returns `len(obj.data.polygons)`. `body_blender.py:213` stores that integer as `triangles` in `<out>.fbx.variant.json`. Export options are `body_blender.py:52-55`: selection only, `MESH`, `apply_unit_scale=True`, `FBX_SCALE_UNITS`, `mesh_smooth_type="FACE"`, `use_mesh_modifiers=True`, no leaf bones, no animation. `use_triangles` stays the exporter default `False` (`Blender 5.1.2` `export_fbx_bin.py:3669`).
- Public loop-triangle count. Current `tools/blender/fbx_readback.py:66-79` calls `mesh.calc_loop_triangles()` and stores `len(mesh.loop_triangles)` as `triangles` and `len(mesh.polygons)` as `polygons`. The same two lines are at `24c94691:tools/blender/fbx_readback.py:68-79`. `src/twinqa/scene.py:59-63` launches that script. `tools/methods/methods_metrics.py:40-57` sums `triangles` over meshes whose names do not start with `UCX_`.
- On-disk FBX polygon. FBX 7400 `PolygonVertexIndex`: a negative int32 ends a polygon and its vertex is `~index`. One negative value, one polygon. This is the file, before Blender import.
- Importer validate. Installed Blender 5.1.2 (`ec6e62d40fa9`, 2026-05-19) `5.1/scripts/addons_core/io_scene_fbx/import_fbx.py:1924` calls `mesh.validate(clean_customdata=False)` after it has created vertices, loops, and polygons (`import_fbx.py:1843-1867`).

A quad shows why the two Blender counts can differ. One 4-gon has `polygons == 1` and `loop_triangles == 2` (`n - 2`). R11 does not use that path: every stored polygon is already a triangle, and after validate the two counts are equal.

### Artifact identity

**Verified by me** (`Get-FileHash SHA256` before the probes and again after them):

| File | SHA-256 | Bytes |
|---|---|---|
| `C:/x/methods/building-body/tow02/blender-gn-union/SM_Vyatskaya_Vl_47_49_013.fbx` | `b8b2f4d3431e444b37e0cf3732a7dbf00d17cff24bddc906a8e64469c60550a0` | 907,948 |
| `.../SM_Vyatskaya_Vl_47_49_013.fbx.variant.json` | `a3382904001873501de4d8f6cdfad5a64ec4cccf4ca3ffe3cf3751da60f9321f` | 111 |
| `C:/x/methods/building-body/tow02/contours.json` | `92a83fc90efd039126f8b86b57ff7fae1002bea72868d7193e27b2904535152e` | 67,137 |

**Source claims.** The same three hashes are the tow02 `blender-gn-union` lines of `24c94691:docs/methods/building-body/SHA256SUMS`. Receipt text: `{"ok": true, "mode": "gn-union", "blender": "5.1.2", "openings": [], "wall_time_s": 23.064, "triangles": 54388}`. Committed R11 (`results.jsonl` line 11, `RESULTS.md:18`): `triangles.model` 39,446, `output_sha256` the FBX hash above, `file_size_bytes` 907,948, `wall_time_s` 23.064, one model mesh, `ucx` 0. `VARIANTS.md:66-68` says the driver reports 54,388 and the FBX reads back as 39,446, and that the gap was not explained there.

Post-probe hashes of those three preserved files were unchanged. Probes read a scratch copy at `C:/x/t_cc1dc013/r11_copy.fbx` (same SHA-256).

### Controls (frozen before the R11 cause)

**Verified by me.** Blender 5.1.2 `--background --factory-startup --python-exit-code 1 --python C:/x/t_cc1dc013/control_counts.py`. Export settings match the writer. Readback in that script is a second factory import, then `len(polygons)` and `len(loop_triangles)`.

| Control | Independent count | bmesh faces | `len(polygons)` | loop triangles before update, after `mesh.update`, evaluated | Reimport polygons / loop triangles |
|---|---|---|---|---|---|
| Triangulated cube (6 quads) | 12 triangles | 12 | 12 | 12 / 12 / 12 | 12 / 12, arity `{3: 12}`, 1 mesh |
| One square, not triangulated | 1 polygon, 2 loop triangles | 1 | 1 | loop triangles 2 at all three stages | 1 / 2, arity `{4: 1}` |
| Collinear triangle, area 0 | 1 polygon | 1 | 1 | loop triangles 1 at all three stages | 1 / 1, arity `{3: 1}` |

The cube path agrees at every stage. The quad path keeps polygon count and loop-triangle count apart, by the independent `n - 2` triangulation. The zero-area triangle survives export and import in this build, so a zero-area filter does not explain a drop of 14,942 faces.

### R11 stage table

**Verified by me** unless the row says source. First divergent stage is in bold.

| Stage | Count | What was measured |
|---|---|---|
| Variant receipt | 54,388 | Source claim, hash-matched file. Writer `len(polygons)` after triangulate. |
| FBX `PolygonVertexIndex` | 54,388 polygons, arity `{3: 54388}`, 16,185 vertices, 163,164 index values | `fbx_polygon_count.py` on the scratch copy. Fan area sum 21,822.337. Repeated-index polygons 0. Fan area `<= 1e-12`: 0. |
| Undirected vertex keys in that array | 39,446 unique, 14,942 extras | `fbx_duplicate_keys.py`. Multiplicity `{1: 24504, 2: 14942}`. Of the 14,942 doubled keys: 14,938 opposite winding, 4 the same directed cycle. |
| Mesh built from those indices, before `validate` | 54,388 polygons, 163,164 loops, 16,185 vertices | `r11_validate_probe.py` |
| **`Mesh.validate(clean_customdata=False)`** | **39,446 polygons, 39,446 loop triangles, 118,338 loops, 16,185 vertices, arity `{3: 39446}`** | Same probe. Return value `True`. `r11_validate_keys.py`: `missing_keys` 0, `new_keys` 0, every kept key has count 1. |
| `bpy.ops.import_scene.fbx` on the copy | 39,446 / 39,446 | One mesh, `SM_Vyatskaya_Vl_47_49_013_Main`. No other objects. |
| Evaluated mesh (`evaluated_get` → `to_mesh`) | 39,446 / 39,446 | No further change. |
| Unchanged public `tools/blender/fbx_readback.py` | `triangles` 39,446, `polygons` 39,446, degrees `{3: 39446}`, `readback_ok` true, Blender `5.1.2` | Fresh count, not a replay of the historical JSON. |
| Committed R11 `triangles.model` | 39,446 | Source claim. Equals this fresh readback. |

Area of the first copy of each undirected key: 18,036.29750659839. Area of the extra copies: 3,786.03911881018. Their sum matches the full fan-area sum. The extra area sits on vertex indices that already have a polygon.

Object inventory after import: one mesh object, name above, parent none, one material slot `M_SM_Vyatskaya_Vl_47_49_013_Main_1` (public readback). No UCX object, so `methods_metrics.counts` adds the whole `triangles` field to `model`.

### What this does and does not establish

The 39,446 readback faces are the undirected keys of the 54,388 file faces, one each. No unique key disappeared, and no new key appeared (`r11_validate_keys.py`). The 14,938 opposite-winding partners are absent after validate, so stored facing on those triples is one-sided in the readback. The historical row's `xview.overlapping_faces` 3,533 (**source claim**, R11) was computed from readback polygons, which are already the deduplicated set. This report does not recompute xView, shell closure, or normals, and it does not treat 39,446 == 39,446 as surface equivalence with the pre-validate mesh.

Sibling files, on-disk census only (no second Blender import). Hashes match the pinned `SHA256SUMS`.

- kpp1 `blender-gn-union` FBX `ab96bb99ff285c6fd270d1610ec026035e4e3f07b6eae60e059b4e51ad99e560`: 9,784 triangles on disk, 0 repeated-index faces, 46 zero-area faces, 2,245 duplicate-key extras, 7,539 unique undirected keys. Receipt **source claim** `triangles` 9,784. Committed R3 `triangles.model` **source claim** 7,539. The unique-key count equals the row. Validate was not re-run on this file.
- ac08 `blender-gn-union` FBX `3e1df9ed2e3593e85128d8f36604e6c894b851df1e28c7f4d16d53ef5302137b`: 44 triangles, 0 extras, 44 unique keys. Receipt **source claim** 44. Committed R7 (`RESULTS.md:14`) **source claim** 44.

The GN rebuild was not required. The preserved R11 bytes already sit on both sides of the boundary: receipt and `PolygonVertexIndex` at 54,388, validate and public readback at 39,446.

## How it applies to this repository

- Receipt: pinned `tools/methods/body/body_blender.py:189` (`len(obj.data.polygons)` after `bmesh.ops.triangulate`).
- File the receipt describes: `C:/x/methods/building-body/tow02/blender-gn-union/SM_Vyatskaya_Vl_47_49_013.fbx`, hash-locked by `docs/methods/building-body/SHA256SUMS` at `24c94691`.
- Row: `docs/methods/building-body/results.jsonl` R11 and `RESULTS.md`, via `tools/methods/run_variant.py` → `twinqa.scene.readback` → `tools/blender/fbx_readback.py:79` → `tools/methods/methods_metrics.py:52-54`.
- The drop is in Blender's FBX importer (`import_fbx.py:1924`), which this repo runs unchanged inside the public readback. A quad in the same build keeps `polygons` and `loop_triangles` different; R11's polygons are already triangles, and the counts meet only after `validate` deletes the second copy of each undirected key.
- `docs/domain/areas/body.md` BODY-F / BODY-N: triangle budgets and export triangulation are judged on readback. The R11 budget share in the committed row (39,446 / 150,000) is the post-validate count. The receipt 54,388 is the pre-validate polygon count of the same file.

## Proposed next tasks

1. **Count the GN receipt the way readback counts.** Scope: when `body_blender.py` writes `triangles`, derive it from the mesh `Mesh.validate` leaves behind (or from unique undirected triangle keys), and record the pre-validate polygon count beside it. Do not change the exported bytes as part of this task. Value: the driver and `results.jsonl` stop quoting two layers of one file. Effort: **S**. Input: preserved R11 FBX `b8b2f4d3431e444b37e0cf3732a7dbf00d17cff24bddc906a8e64469c60550a0`. Expected: the published triangle field is 39,446 and equals `tools/blender/fbx_readback.py` `meshes[0].triangles`, while a raw `PolygonVertexIndex` count of that same file remains 54,388. Advances #729.

2. **Stop the GN union emitting a second polygon on the same vertex triple.** Scope: on a scratch copy of the preserved contours, find the first writer stage (boolean union, dissolve, or triangulate) that introduces an opposite-winding twin, and change that stage so the exported FBX has no duplicate undirected key. Leave the readback metric as it is. Value: 39,446 then means the file's polygon count, not a count that appears only because the importer deleted faces. Effort: **M**. Input: `contours.json` `92a83fc90efd039126f8b86b57ff7fae1002bea72868d7193e27b2904535152e`. Expected: `duplicate_polygon_extras == 0`, and on-disk polygon count equals unique undirected keys equals public `loop_triangles`. Advances #727.

## Open questions for the user

- Should the methods receipt keep publishing the pre-validate polygon count, with the readback count beside it, or should a future row show only the post-validate number?
- For the 14,938 opposite-winding pairs, which winding should a rebuilt shell keep? This pass checked key identity, not the sign of the kept normal.
- The historical xView pair count (379 / 3,533) is on the 39,446-face readback. Do you want a later pass to count overlaps on the 54,388-face file before validate?

## Reproduction

Blender: `C:\Program Files\Blender Foundation\Blender 5.1\blender.exe` 5.1.2, hash `ec6e62d40fa9`. Each process: `--background --factory-startup --python-exit-code 1`. Scratch: `C:/x/t_cc1dc013/`. Public readback command:

```text
blender.exe --background --factory-startup --python-exit-code 1 --python tools/blender/fbx_readback.py -- C:/x/t_cc1dc013/r11_copy.fbx C:/x/t_cc1dc013/r11_public_readback.json
```

`TWINQA_READBACK True`. Summary taken from that JSON: `readback_ok` true, one mesh, `triangles` 39446, `polygons` 39446, `polygon_degrees` `{"3": 39446}`.

### `fbx_polygon_count.py`

```python
"""Count polygons stored in a binary FBX, independent of Blender import.

Reads Geometry Vertices (float64 xyz) and PolygonVertexIndex (int32, negative = end of polygon).
Classifies each polygon: repeated indices, zero area (cross-product length), duplicate keys.
Does not modify the file.
"""
import hashlib
import json
import struct
import sys
import zlib
from collections import Counter
from pathlib import Path

ARRAY_TYPES = {
    b"f": 4,
    b"d": 8,
    b"i": 4,
    b"l": 8,
    b"b": 1,
}


def _parse_property(data, pos):
    kind = data[pos:pos + 1]
    pos += 1
    if kind in ARRAY_TYPES:
        count, enc, clen = struct.unpack_from("<III", data, pos)
        pos += 12
        raw = data[pos:pos + clen]
        pos += clen
        payload = zlib.decompress(raw) if enc == 1 else raw
        return kind, count, payload, pos
    sizes = {b"Y": 2, b"C": 1, b"I": 4, b"F": 4, b"D": 8, b"L": 8}
    if kind in sizes:
        n = sizes[kind]
        return kind, None, data[pos:pos + n], pos + n
    if kind in (b"S", b"R"):
        n = struct.unpack_from("<I", data, pos)[0]
        pos += 4
        return kind, None, data[pos:pos + n], pos + n
    raise ValueError(f"unknown property type {kind!r} at {pos - 1}")


def walk(data, pos, end, version, out):
    is64 = version >= 7500
    while pos < end:
        if is64:
            end_off, nprops, _plen = struct.unpack_from("<QQQ", data, pos)
            pos += 24
        else:
            end_off, nprops, _plen = struct.unpack_from("<III", data, pos)
            pos += 12
        name_len = data[pos]
        pos += 1
        if end_off == 0:
            break
        name = data[pos:pos + name_len]
        pos += name_len
        props = []
        for _ in range(nprops):
            kind, count, payload, pos = _parse_property(data, pos)
            props.append((kind, count, payload))
        if name in (b"Vertices", b"PolygonVertexIndex") and props:
            out.append((name, props[0]))
        pos = walk(data, pos, end_off, version, out)
        if pos != end_off:
            pos = end_off
    return pos


def polygons_of(verts, indices):
    polys = []
    cursor = []
    for raw in indices:
        if raw < 0:
            cursor.append(~raw)
            polys.append(cursor)
            cursor = []
        else:
            cursor.append(raw)
    if cursor:
        raise ValueError("polygon stream did not end on a negative index")
    return polys


def main():
    path = Path(sys.argv[1])
    data = path.read_bytes()
    if not data.startswith(b"Kaydara FBX Binary"):
        raise SystemExit("not a binary FBX")
    version = struct.unpack_from("<I", data, 23)[0]
    found = []
    walk(data, 27, len(data), version, found)
    geometries = []
    pending_verts = None
    for name, (kind, count, payload) in found:
        if name == b"Vertices":
            pending_verts = struct.unpack(f"<{count}d", payload) if kind == b"d" else None
        elif name == b"PolygonVertexIndex" and kind == b"i":
            indices = struct.unpack(f"<{count}i", payload)
            geometries.append((pending_verts, indices))
            pending_verts = None
    report = {"path": str(path), "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data),
              "fbx_version": version, "geometries": []}
    for vi, (verts, indices) in enumerate(geometries):
        if verts is None:
            raise SystemExit(f"geometry {vi} has polygons without vertices")
        nverts = len(verts) // 3
        polys = polygons_of(verts, indices)
        arity = Counter(len(p) for p in polys)
        repeated = zero = positive = 0
        area_sum = 0.0
        keys = []
        for poly in polys:
            if len(set(poly)) < 3:
                repeated += 1
                keys.append(tuple(sorted(poly)))
                continue
            pts = [(verts[3 * i], verts[3 * i + 1], verts[3 * i + 2]) for i in poly]
            ax = ay = az = 0.0
            x0, y0, z0 = pts[0]
            for (x1, y1, z1), (x2, y2, z2) in zip(pts[1:], pts[2:]):
                ux, uy, uz = x1 - x0, y1 - y0, z1 - z0
                vx, vy, vz = x2 - x0, y2 - y0, z2 - z0
                ax += uy * vz - uz * vy
                ay += uz * vx - ux * vz
                az += ux * vy - uy * vx
            area = 0.5 * (ax * ax + ay * ay + az * az) ** 0.5
            area_sum += area
            if area <= 1e-12:
                zero += 1
            else:
                positive += 1
            keys.append(tuple(sorted(poly)))
        counts = Counter(keys)
        duplicate_extras = sum(n - 1 for n in counts.values() if n > 1)
        report["geometries"].append({
            "index": vi,
            "vertices": nverts,
            "index_values": len(indices),
            "polygons": len(polys),
            "negative_indices": sum(1 for v in indices if v < 0),
            "arity": {str(k): arity[k] for k in sorted(arity)},
            "repeated_index_polygons": repeated,
            "zero_area_polygons": zero,
            "positive_area_polygons": positive,
            "area_sum": area_sum,
            "duplicate_polygon_extras": duplicate_extras,
            "unique_index_keys": len(counts),
        })
    json.dump(report, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
```

### `fbx_duplicate_keys.py`

```python
"""Break the 14,942 extra R11 polygons into duplicate-key classes. Read-only."""
import json
import struct
import sys
import zlib
from collections import Counter
from pathlib import Path

ARRAY_TYPES = {b"f": 4, b"d": 8, b"i": 4, b"l": 8, b"b": 1}


def parse_property(data, pos):
    kind = data[pos:pos + 1]
    pos += 1
    if kind in ARRAY_TYPES:
        count, enc, clen = struct.unpack_from("<III", data, pos)
        pos += 12
        raw = data[pos:pos + clen]
        payload = zlib.decompress(raw) if enc == 1 else raw
        return kind, count, payload, pos + clen
    sizes = {b"Y": 2, b"C": 1, b"I": 4, b"F": 4, b"D": 8, b"L": 8}
    if kind in sizes:
        n = sizes[kind]
        return kind, None, data[pos:pos + n], pos + n
    if kind in (b"S", b"R"):
        n = struct.unpack_from("<I", data, pos)[0]
        pos += 4
        return kind, None, data[pos:pos + n], pos + n
    raise ValueError(kind)


def walk(data, pos, end, version, out):
    is64 = version >= 7500
    while pos < end:
        if is64:
            end_off, nprops, _plen = struct.unpack_from("<QQQ", data, pos)
            pos += 24
        else:
            end_off, nprops, _plen = struct.unpack_from("<III", data, pos)
            pos += 12
        name_len = data[pos]
        pos += 1
        if end_off == 0:
            break
        name = data[pos:pos + name_len]
        pos += name_len
        props = []
        for _ in range(nprops):
            kind, count, payload, pos = parse_property(data, pos)
            props.append((kind, count, payload))
        if name in (b"Vertices", b"PolygonVertexIndex") and props:
            out.append((name, props[0]))
        walk(data, pos, end_off, version, out)
        pos = end_off
    return pos


def canon_dir(poly):
    i = poly.index(min(poly))
    return tuple(poly[i:] + poly[:i])


def main():
    data = Path(sys.argv[1]).read_bytes()
    version = struct.unpack_from("<I", data, 23)[0]
    found = []
    walk(data, 27, len(data), version, found)
    verts = indices = None
    for name, (kind, count, payload) in found:
        if name == b"Vertices":
            verts = struct.unpack(f"<{count}d", payload)
        elif name == b"PolygonVertexIndex":
            indices = struct.unpack(f"<{count}i", payload)
    polys = []
    cur = []
    for raw in indices:
        if raw < 0:
            cur.append(~raw)
            polys.append(cur)
            cur = []
        else:
            cur.append(raw)
    sorted_keys = [tuple(sorted(p)) for p in polys]
    directed = [canon_dir(p) for p in polys]
    undirected = []
    for p in polys:
        fwd = canon_dir(p)
        rev = canon_dir(list(reversed(p)))
        undirected.append(fwd if fwd <= rev else rev)
    def hist(keys):
        counts = Counter(keys)
        mult = Counter(counts.values())
        return {
            "unique": len(counts),
            "extras": sum(n - 1 for n in counts.values() if n > 1),
            "multiplicity_histogram": {str(k): mult[k] for k in sorted(mult)},
        }
    area_unique = 0.0
    area_extra = 0.0
    seen = set()
    for poly, key in zip(polys, sorted_keys):
        pts = [(verts[3 * i], verts[3 * i + 1], verts[3 * i + 2]) for i in poly]
        x0, y0, z0 = pts[0]
        ax = ay = az = 0.0
        for (x1, y1, z1), (x2, y2, z2) in zip(pts[1:], pts[2:]):
            ux, uy, uz = x1 - x0, y1 - y0, z1 - z0
            vx, vy, vz = x2 - x0, y2 - y0, z2 - z0
            ax += uy * vz - uz * vy
            ay += uz * vx - ux * vz
            az += ux * vy - uy * vx
        area = 0.5 * (ax * ax + ay * ay + az * az) ** 0.5
        if key in seen:
            area_extra += area
        else:
            seen.add(key)
            area_unique += area
    by_sorted = {}
    same_dir = flipped = mixed = 0
    for poly, key, direc in zip(polys, sorted_keys, directed):
        by_sorted.setdefault(key, []).append(direc)
    for dirs in by_sorted.values():
        if len(dirs) == 1:
            continue
        kinds = set(dirs)
        rev = set()
        for d in kinds:
            rev.add(canon_dir(list(reversed(d))))
        if len(kinds) == 1:
            same_dir += 1
        elif kinds <= rev and len(kinds) == 2:
            flipped += 1
        else:
            mixed += 1
    report = {
        "polygons": len(polys),
        "sorted_vertex_key": hist(sorted_keys),
        "directed_cycle": hist(directed),
        "undirected_cycle": hist(undirected),
        "duplicated_sorted_keys": {
            "same_directed_cycle": same_dir,
            "opposite_winding_only": flipped,
            "mixed_or_other": mixed,
        },
        "area_first_copy": area_unique,
        "area_extra_copies": area_extra,
    }
    json.dump(report, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
```

### `control_counts.py`

```python
"""Freeze the two count definitions before any R11 cause is proposed.

Control box: a cube triangulated the same way the pinned GN writer finishes
(bmesh triangulate, to_mesh, len(polygons), the writer's FBX export settings).
Independent count: 6 quads * 2 = 12 triangles.

Control quad: one square polygon, not triangulated. Independent loop triangulation
of an n-gon is n-2, so 1 polygon and 2 loop triangles.

Control collinear: one triangle whose three points are collinear. Independent
polygon count is 1; its area is 0.
"""
import json
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector

OUT = Path(sys.argv[sys.argv.index("--") + 1])


def export_selected(obj, path):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.export_scene.fbx(
        filepath=str(path), use_selection=True, object_types={"MESH"},
        apply_unit_scale=True, apply_scale_options="FBX_SCALE_UNITS", mesh_smooth_type="FACE",
        use_mesh_modifiers=True, add_leaf_bones=False, bake_anim=False)


def stage_counts(obj):
    mesh = obj.data
    before = {"polygons": len(mesh.polygons)}
    mesh.calc_loop_triangles()
    before["loop_triangles"] = len(mesh.loop_triangles)
    mesh.update()
    mesh.calc_loop_triangles()
    updated = {"polygons": len(mesh.polygons), "loop_triangles": len(mesh.loop_triangles)}
    deps = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(deps).to_mesh()
    ev.calc_loop_triangles()
    evaluated = {"polygons": len(ev.polygons), "loop_triangles": len(ev.loop_triangles)}
    obj.evaluated_get(deps).to_mesh_clear()
    return {"before_update": before, "after_update": updated, "evaluated": evaluated}


def reimport(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(path))
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    rows = []
    for obj in meshes:
        obj.data.calc_loop_triangles()
        arity = {}
        for poly in obj.data.polygons:
            arity[len(poly.vertices)] = arity.get(len(poly.vertices), 0) + 1
        rows.append({"name": obj.name, "type": obj.type, "polygons": len(obj.data.polygons),
                     "loop_triangles": len(obj.data.loop_triangles),
                     "arity": {str(k): v for k, v in sorted(arity.items())}})
    others = [{"name": o.name, "type": o.type} for o in bpy.context.scene.objects if o.type != "MESH"]
    return {"mesh_objects": len(meshes), "other_objects": others, "meshes": rows}


def make_object(name, bm):
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    n_bm = len(bm.faces)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    return obj, n_bm


report = {"blender": bpy.app.version_string, "controls": []}

bpy.ops.wm.read_factory_settings(use_empty=True)
bm = bmesh.new()
bmesh.ops.create_cube(bm, size=2.0)
raw_quads = len(bm.faces)
bmesh.ops.triangulate(bm, faces=bm.faces)
raw_tris = len(bm.faces)
obj, n_bm = make_object("Box", bm)
stages = stage_counts(obj)
writer_count = len(obj.data.polygons)
export_selected(obj, OUT / "control_box.fbx")
readback = reimport(OUT / "control_box.fbx")
report["controls"].append({
    "name": "triangulated_box",
    "independent_triangles": 12,
    "raw_quads_before_triangulate": raw_quads,
    "bmesh_faces_after_triangulate": raw_tris,
    "bmesh_faces_at_to_mesh": n_bm,
    "writer_len_polygons": writer_count,
    "stages": stages,
    "readback": readback,
})

bpy.ops.wm.read_factory_settings(use_empty=True)
bm = bmesh.new()
verts = [bm.verts.new(Vector(c)) for c in ((0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0))]
bm.faces.new(verts)
obj, n_bm = make_object("Quad", bm)
stages = stage_counts(obj)
export_selected(obj, OUT / "control_quad.fbx")
report["controls"].append({
    "name": "single_quad",
    "independent_loop_triangles": 2,
    "independent_polygons": 1,
    "bmesh_faces_at_to_mesh": n_bm,
    "writer_len_polygons": len(obj.data.polygons),
    "stages": stages,
    "readback": reimport(OUT / "control_quad.fbx"),
})

bpy.ops.wm.read_factory_settings(use_empty=True)
bm = bmesh.new()
verts = [bm.verts.new(Vector(c)) for c in ((0, 0, 0), (1, 0, 0), (2, 0, 0))]
bm.faces.new(verts)
obj, n_bm = make_object("Collinear", bm)
area = obj.data.polygons[0].area if obj.data.polygons else None
stages = stage_counts(obj)
export_selected(obj, OUT / "control_collinear.fbx")
report["controls"].append({
    "name": "collinear_triangle",
    "independent_polygons": 1,
    "polygon_area": area,
    "bmesh_faces_at_to_mesh": n_bm,
    "writer_len_polygons": len(obj.data.polygons),
    "stages": stages,
    "readback": reimport(OUT / "control_collinear.fbx"),
})

(OUT / "control_counts.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print("CONTROL_DONE")
```

### `r11_validate_probe.py`

```python
"""Separate on-disk polygons, Mesh.validate, and the FBX importer.

Builds one mesh from the binary FBX vertices and polygon indices with the same
loop/polygon calls the importer uses, records counts, then calls
Mesh.validate(clean_customdata=False). A second factory scene imports the file
through bpy.ops.import_scene.fbx and records the mesh the public reader sees.
"""
import json
import struct
import sys
import zlib

import bpy

SRC = sys.argv[sys.argv.index("--") + 1]
OUT = sys.argv[sys.argv.index("--") + 2]
ARRAY_TYPES = {b"f": 4, b"d": 8, b"i": 4, b"l": 8, b"b": 1}


def parse_property(data, pos):
    kind = data[pos:pos + 1]
    pos += 1
    if kind in ARRAY_TYPES:
        count, enc, clen = struct.unpack_from("<III", data, pos)
        pos += 12
        raw = data[pos:pos + clen]
        payload = zlib.decompress(raw) if enc == 1 else raw
        return kind, count, payload, pos + clen
    sizes = {b"Y": 2, b"C": 1, b"I": 4, b"F": 4, b"D": 8, b"L": 8}
    if kind in sizes:
        n = sizes[kind]
        return kind, None, data[pos:pos + n], pos + n
    n = struct.unpack_from("<I", data, pos)[0]
    pos += 4
    return kind, None, data[pos:pos + n], pos + n


def walk(data, pos, end, version, found):
    is64 = version >= 7500
    while pos < end:
        if is64:
            end_off, nprops, _plen = struct.unpack_from("<QQQ", data, pos)
            pos += 24
        else:
            end_off, nprops, _plen = struct.unpack_from("<III", data, pos)
            pos += 12
        name_len = data[pos]
        pos += 1
        if end_off == 0:
            break
        name = data[pos:pos + name_len]
        pos += name_len
        props = []
        for _ in range(nprops):
            kind, count, payload, pos = parse_property(data, pos)
            props.append((kind, count, payload))
        if name in (b"Vertices", b"PolygonVertexIndex") and props:
            found.append((name, props[0]))
        walk(data, pos, end_off, version, found)
        pos = end_off


def load_geometry(path):
    data = open(path, "rb").read()
    version = struct.unpack_from("<I", data, 23)[0]
    found = []
    walk(data, 27, len(data), version, found)
    verts = indices = None
    for name, (kind, count, payload) in found:
        if name == b"Vertices":
            verts = struct.unpack(f"<{count}d", payload)
        elif name == b"PolygonVertexIndex":
            indices = struct.unpack(f"<{count}i", payload)
    polys = []
    cur = []
    for raw in indices:
        if raw < 0:
            cur.append(~raw)
            polys.append(cur)
            cur = []
        else:
            cur.append(int(raw))
    return verts, polys


def counts(mesh):
    arity = {}
    for poly in mesh.polygons:
        n = len(poly.vertices)
        arity[n] = arity.get(n, 0) + 1
    mesh.calc_loop_triangles()
    return {
        "vertices": len(mesh.vertices),
        "polygons": len(mesh.polygons),
        "loops": len(mesh.loops),
        "loop_triangles": len(mesh.loop_triangles),
        "arity": {str(k): v for k, v in sorted(arity.items())},
    }


verts, polys = load_geometry(SRC)
bpy.ops.wm.read_factory_settings(use_empty=True)
mesh = bpy.data.meshes.new("from_disk_indices")
mesh.vertices.add(len(verts) // 3)
mesh.attributes["position"].data.foreach_set("vector", [verts[i] for i in range(len(verts))])
loop_verts = [i for poly in polys for i in poly]
starts = []
cursor = 0
for poly in polys:
    starts.append(cursor)
    cursor += len(poly)
mesh.loops.add(len(loop_verts))
mesh.attributes[".corner_vert"].data.foreach_set("value", loop_verts)
mesh.polygons.add(len(polys))
mesh.polygons.foreach_set("loop_start", starts)
before = {"vertices": len(mesh.vertices), "polygons": len(mesh.polygons), "loops": len(mesh.loops)}
changed = mesh.validate(clean_customdata=False)
after = counts(mesh)

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=SRC)
imported = []
for obj in bpy.context.scene.objects:
    row = {"name": obj.name, "type": obj.type}
    if obj.type == "MESH":
        row["data"] = counts(obj.data)
        deps = bpy.context.evaluated_depsgraph_get()
        ev = obj.evaluated_get(deps).to_mesh()
        row["evaluated"] = counts(ev)
        obj.evaluated_get(deps).to_mesh_clear()
    imported.append(row)

report = {
    "blender": bpy.app.version_string,
    "disk_polygons": len(polys),
    "disk_vertices": len(verts) // 3,
    "built_before_validate": before,
    "validate_clean_customdata_false_returned": changed,
    "built_after_validate": after,
    "importer_objects": imported,
}
with open(OUT, "w", encoding="utf-8") as handle:
    json.dump(report, handle, indent=2)
print("VALIDATE_PROBE", before["polygons"], after["polygons"], after["loop_triangles"], changed)
```

Observed print: `VALIDATE_PROBE 54388 39446 39446 True`.

### `r11_validate_keys.py`

```python
"""Check that Mesh.validate keeps exactly one polygon per undirected vertex key."""
import json
import struct
import sys
import zlib
from collections import Counter

import bpy

SRC = sys.argv[sys.argv.index("--") + 1]
OUT = sys.argv[sys.argv.index("--") + 2]
ARRAY_TYPES = {b"f": 4, b"d": 8, b"i": 4, b"l": 8, b"b": 1}


def parse_property(data, pos):
    kind = data[pos:pos + 1]
    pos += 1
    if kind in ARRAY_TYPES:
        count, enc, clen = struct.unpack_from("<III", data, pos)
        pos += 12
        raw = data[pos:pos + clen]
        payload = zlib.decompress(raw) if enc == 1 else raw
        return kind, count, payload, pos + clen
    sizes = {b"Y": 2, b"C": 1, b"I": 4, b"F": 4, b"D": 8, b"L": 8}
    if kind in sizes:
        n = sizes[kind]
        return kind, None, data[pos:pos + n], pos + n
    n = struct.unpack_from("<I", data, pos)[0]
    pos += 4
    return kind, None, data[pos:pos + n], pos + n


def walk(data, pos, end, version, found):
    is64 = version >= 7500
    while pos < end:
        if is64:
            end_off, nprops, _plen = struct.unpack_from("<QQQ", data, pos)
            pos += 24
        else:
            end_off, nprops, _plen = struct.unpack_from("<III", data, pos)
            pos += 12
        name_len = data[pos]
        pos += 1
        if end_off == 0:
            break
        name = data[pos:pos + name_len]
        pos += name_len
        props = []
        for _ in range(nprops):
            kind, count, payload, pos = parse_property(data, pos)
            props.append((kind, count, payload))
        if name == b"PolygonVertexIndex" and props:
            found.append(props[0])
        walk(data, pos, end_off, version, found)
        pos = end_off


data = open(SRC, "rb").read()
version = struct.unpack_from("<I", data, 23)[0]
found = []
walk(data, 27, len(data), version, found)
_kind, count, payload = found[0]
indices = struct.unpack(f"<{count}i", payload)
keys = []
cur = []
for raw in indices:
    if raw < 0:
        cur.append(~raw)
        keys.append(tuple(sorted(cur)))
        cur = []
    else:
        cur.append(int(raw))
before = Counter(keys)

found_v = []


def walk_v(data, pos, end, version, found):
    is64 = version >= 7500
    while pos < end:
        if is64:
            end_off, nprops, _plen = struct.unpack_from("<QQQ", data, pos)
            pos += 24
        else:
            end_off, nprops, _plen = struct.unpack_from("<III", data, pos)
            pos += 12
        name_len = data[pos]
        pos += 1
        if end_off == 0:
            break
        name = data[pos:pos + name_len]
        pos += name_len
        props = []
        for _ in range(nprops):
            kind, count, payload, pos = parse_property(data, pos)
            props.append((name, kind, count, payload))
        for item in props:
            if item[0] == b"Vertices":
                found.append(item)
        walk_v(data, pos, end_off, version, found)
        pos = end_off


walk_v(data, 27, len(data), version, found_v)
_name, _kind, vcount, vpayload = found_v[0]
verts = struct.unpack(f"<{vcount}d", vpayload)

bpy.ops.wm.read_factory_settings(use_empty=True)
mesh = bpy.data.meshes.new("keys")
mesh.vertices.add(len(verts) // 3)
mesh.attributes["position"].data.foreach_set("vector", list(verts))
loop_verts = []
starts = []
cursor = 0
cur = []
for raw in indices:
    if raw < 0:
        cur.append(~raw)
        starts.append(cursor)
        loop_verts.extend(cur)
        cursor += len(cur)
        cur = []
    else:
        cur.append(int(raw))
mesh.loops.add(len(loop_verts))
mesh.attributes[".corner_vert"].data.foreach_set("value", loop_verts)
mesh.polygons.add(len(starts))
mesh.polygons.foreach_set("loop_start", starts)
mesh.validate(clean_customdata=False)
after = Counter(tuple(sorted(int(i) for i in poly.vertices)) for poly in mesh.polygons)
missing = [k for k in before if k not in after]
extra = [k for k in after if k not in before]
kept_not_one = sum(1 for k, n in after.items() if n != 1)
report = {
    "before_polygons": sum(before.values()),
    "after_polygons": sum(after.values()),
    "unique_before": len(before),
    "unique_after": len(after),
    "missing_keys": len(missing),
    "new_keys": len(extra),
    "kept_keys_whose_count_is_not_1": kept_not_one,
}
with open(OUT, "w", encoding="utf-8") as handle:
    json.dump(report, handle, indent=2)
print("KEYS", json.dumps(report))
```

Observed print: `KEYS {"before_polygons": 54388, "after_polygons": 39446, "unique_before": 39446, "unique_after": 39446, "missing_keys": 0, "new_keys": 0, "kept_keys_whose_count_is_not_1": 0}`.

The script that was executed also assigned `loop_verts` once from the sorted keys and then replaced that list by walking `indices` again. The mesh was built from the second walk. The listing above keeps only that walk.
