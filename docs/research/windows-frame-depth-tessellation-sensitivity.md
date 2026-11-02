# Window frame depth and tessellation

Status: report-only research on synthetic meshes. `delivery_passed=false`. No gate, threshold, estimator, C25/C35 decision, or delivery change.

## Summary

Coplanar subdivision of one face, and duplicated seam indices, both change `windows_glazing.frame_depth_m` while the continuous surface and the design normal thickness stay fixed.
A centred welded 1 x 1 x 0.07 m cuboid reads 0.07 m; the same surface with an off-centre conforming patch reads 0.0896, 0.1061, 0.0993 and 0.0754 m at grid densities 1, 4, 16 and 64.
Giving every triangle its own corner indices, still 12 triangles and the same 8 positions, reads 0.0 / 0.0 / 0.0 m.
The 4 x 4 conforming mesh and the same triangles with a duplicated patch boundary are both 62 polygons; the readout moves from 0.1061 m to 0.0 / 0.0515 / 0.103 m.
Exact 90-degree rotations, translations and vertex or face permutations leave every rounded triple unchanged. Unrounded drift on those copies stays at most 2.498e-16 m.
A flat ring and the committed zero-thickness test box read 0.0 m. Two separate cuboids read 0.03 / 0.05 / 0.07 m.
Stored rows R2 and R10 still say 0.07 m. They were read from `results.jsonl` and were not recomputed from benchmark assets.
The PCA range and the design normal thickness are different definitions. This report does not choose between them.

## Findings

### Sources

Verified-by-read at HEAD `91af46b8ffd6d7c8fc678ac6ca0f669aa550f348` (worktree HEAD file and branch ref; git was not executed):

| Path | Role | SHA-256 |
|---|---|---|
| `tools/methods/methods_metrics.py` | `windows_glazing`, `_components` | `3fff60eaba5999e2eb2076767695e52a64ea0c742159f95550762579d7792dc7` |
| `tests/methods/test_windows_glazing.py` | synthetic 0.07 m and 0.0 m frame boxes | `88f55060412eed40c4e25c0d10c67b2b8efa74f57c2c97dde44703099fdc1d73` |
| `docs/methods/README.md` | row-field definition | `8ce01b9c28f9789e824ea960a1faf9046b681e4706d67142cfaaab6c27e0f593` |
| `docs/methods/windows-glazing/WHEN.md` | stored-row rules | `d5fd42b60bce739a6e11e48d90d06a7eebf19f0b51c2645692c51b76d7070093` |
| `docs/methods/windows-glazing/VARIANTS.md` | `solidify` 70 mm builder | `07c94c30ac0734b5eb693314b7de2dfb0a95640618a71396b81166ba84e72764` |
| `docs/methods/windows-glazing/results.jsonl` | committed metric rows | `8309648225f9f1d053b598184e6818837e6193aa5b40e3c6f60c6885a7c7cef5` |
| `docs/domain/areas/windows.md` | L1 window sheet; no PCA rule | `7c0d860033cf4babf9e6786fdcdf1d00ebe9d33d91a50a4127373c68d3f2d10f` |

Claimed by the code, `tools/methods/methods_metrics.py` lines 466-468 and 502-517: frame polygons are those whose slot name contains `FRAME`; components share a vertex index; one component's depth is the max-minus-min of its centred vertices along `svd(..., full_matrices=False)[2][-1]`; the reported value is `round` of min, `statistics.median` and max to 4 decimals. The docstring calls that axis "the opening normal for a frame ring". `docs/methods/README.md` states the same PCA extent (min / median / max m).

Claimed by `VARIANTS.md`: `modelled-frames` solidifies 70 mm, centred on the glass plane. Claimed by `WHEN.md`: modelled-frames frame depth is 0.07 m on R2 and R10; inset-glass-trim reads 0.0 m on R4 and R12. Claimed by `test_windows_glazing.py`: a frame box of thickness 0.07 m returns `{min: 0.07, median: 0.07, max: 0.07}`, and thickness 0.0 returns max 0.0.

`docs/domain/areas/windows.md` does not define this readout. WIN-06 records the open C35 question (bake relief up to 5 cm versus `mid` frame geometry). C25 stays open there too. Nothing below decides either conflict.

The card's `#723` does not appear in `docs/`. `#721` appears as a comment on the windows-glazing class. Neither was checked against an issue tracker.

### Frozen corpus and checks

Runtime, both process runs: CPython 3.14.7, NumPy 2.5.3. `2 * 0.035 == 0.07` and `2 * 0.015 == 0.03` are true. Hex of that 0.07 float is `0x1.1eb851eb851ecp-4`.

The design normal thickness is the distance between a pair of known planes. It is the support of the component's vertices along that construction normal after the same exact rotation applied to the points. That support is not an SVD.

| Geometry | Planes and surface | Indices |
|---|---|---|
| `base_cuboid` | corners at all sign combinations of `(0.5, 0.5, 0.035)`; planes `z = ±0.035` | 8 shared corners, 12 triangles, 1 index component |
| `conforming_n` | same cuboid; `+Z` face replaced by an off-centre patch `[1/8, 3/8] x [-3/8, -1/8]` on an `n x n` grid, `n` in `{1, 4, 16, 64}`, boundary vertices shared | one index component; `+Z` area exactly 1; outer boundary is the face rectangle |
| `seam_split_4` | same triangles as `conforming_4`; patch-boundary positions stored twice | 62 triangles, 2 index components, 1 position component |
| `unwelded_seams` | same 12 triangles and the same 8 positions; each triangle has its own 3 indices | 36 indices, 12 index components, 1 position component |
| `flat_ring` | plane `z = 0`; outer square `[-0.5, 0.5]^2`; inner square `[-0.25, 0.25]^2` | 8 triangles, area `3/4`, 1 index component |
| `two_cuboids` | one cuboid on `z = ±0.015`, another on `z = ±0.035` shifted by `x += 2` | 2 index components and 2 position components; z supports 0.03 m and 0.07 m |

Side and bottom faces of every subdivided cuboid stay two triangles each. Their areas match the original rectangles (top and bottom area 1, each side area 0.07). Every `+Z` triangle is strictly counter-clockwise. The patch centre is `(0.25, -0.25)`; the face centre is `(0, 0)`. These checks are assertions in the probe; both runs exited 0, so they passed.

The independent index union-find matched `methods_metrics._components` on every evaluated component list. The probe raises if those groupings differ.

### Reproduction

Scratch JSON lives under `C:/x/t_0cc8ce45/`, outside the repo. Two process runs wrote byte-identical 226655-byte files, SHA-256 `ba18966fb43549b754519b0ee07b590e767b6814ad389b0e619aed9a78c7fbe1`. Command:

```
uv run python C:\x\t_0cc8ce45\probe_frame_depth.py C:\x\t_0cc8ce45\probe_run_a.json
```

Each `windows_glazing` call was repeated immediately; the return value matched and a deep copy of `rb` and `extra` matched the inputs. The nine corpus geometries were then evaluated a second time inside the process, including every transform, and the rounded triples and unrounded extents matched. The two replay scenes were covered by the two byte-identical process runs. 264 records per run: 11 geometries x 6 rigid transforms x 4 permutations. No pytest and no DCC.

The embedded script is the frozen corpus.

```python
"""Synthetic probe: does tessellation change windows_glazing.frame_depth_m?

Research only. Builds a frozen float64 corpus, checks planarity, coverage and
index-vs-position connectivity, then calls tools/methods/methods_metrics.py
windows_glazing. The independent oracle is support along the construction
normal (known plane equations). No second SVD. delivery_passed is false.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import math
import statistics
import sys
from collections import Counter
from fractions import Fraction
from pathlib import Path

import numpy as np

ROOT = Path(r"C:\Users\artsafro\agr-pilot\AGR-DigitalTwin\.worktrees\t_0cc8ce45")
METRIC_PATH = ROOT / "tools" / "methods" / "methods_metrics.py"
GIT_DIR = Path(r"C:\Users\artsafro\agr-pilot\AGR-DigitalTwin\.git")
OUT = Path(r"C:\x\t_0cc8ce45")

# Frozen corpus parameters. XY are dyadic; thickness uses the decimal literals.
Z_HALF_07 = 0.035  # 2 * 0.035 == 0.07 in this runtime (asserted)
Z_HALF_03 = 0.015  # 2 * 0.015 == 0.03
FACE_LO = Fraction(-1, 2)
FACE_HI = Fraction(1, 2)
# Off-centre patch on the +Z face. Face centre is (0, 0); patch centre is (1/4, -1/4).
PATCH_X0, PATCH_X1 = Fraction(1, 8), Fraction(3, 8)
PATCH_Y0, PATCH_Y1 = Fraction(-3, 8), Fraction(-1, 8)
RING_INNER = Fraction(1, 4)
DESIGN_NORMAL = (0.0, 0.0, 1.0)

RZ90 = ((0.0, -1.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0))
RX90 = ((1.0, 0.0, 0.0), (0.0, 0.0, -1.0), (0.0, 1.0, 0.0))
RY90 = ((0.0, 0.0, 1.0), (0.0, 1.0, 0.0), (-1.0, 0.0, 0.0))
I3 = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
TRANSFORMS = (
    ("identity", I3, (0.0, 0.0, 0.0)),
    ("translate", I3, (4.0, -2.0, 0.5)),
    ("rot_z90", RZ90, (0.0, 0.0, 0.0)),
    ("rot_x90", RX90, (0.0, 0.0, 0.0)),
    ("rot_y90", RY90, (0.0, 0.0, 0.0)),
    ("rot_x90_translate", RX90, (1.0, 2.0, 3.0)),
)
PERMS = ("none", "vertex_cycle", "face_reverse", "vertex_cycle_and_face_reverse")

# Committed test-scene literals (tests/methods/test_methods_catalog.py and test_windows_glazing.py).
BOX_T = [(0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7), (0, 1, 5), (0, 5, 4), (1, 2, 6), (1, 6, 5),
         (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7)]


def load_metrics():
    spec = importlib.util.spec_from_file_location("methods_metrics", METRIC_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["methods_metrics"] = mod
    spec.loader.exec_module(mod)
    return mod


def head_sha() -> str:
    head = (GIT_DIR / "worktrees" / "t_0cc8ce45" / "HEAD").read_text(encoding="utf-8").strip()
    if not head.startswith("ref: "):
        return head
    return (GIT_DIR / head.split(" ", 1)[1]).read_text(encoding="utf-8").strip()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assert_rotations():
    for name, r in (("RZ90", RZ90), ("RX90", RX90), ("RY90", RY90), ("I3", I3)):
        m = np.array(r, float)
        if abs(np.linalg.det(m) - 1.0) > 0.0 or not np.array_equal(m.T @ m, np.eye(3)):
            raise SystemExit(f"rotation {name} is not an exact proper rotation")


def tri_cross_z(a, b, c) -> Fraction:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def fan(poly: list[int]) -> list[tuple[int, int, int]]:
    return [(poly[0], poly[k], poly[k + 1]) for k in range(1, len(poly) - 1)]


def add_quad(idxs, normal, verts) -> list[tuple[int, int, int]]:
    a, b, c, d = idxs
    cand = [(a, b, c), (a, c, d)]
    pa, pb, pc = (np.array(verts[i], float) for i in cand[0])
    if float(np.dot(np.cross(pb - pa, pc - pa), np.array(normal, float))) < 0.0:
        cand = [(a, c, b), (a, d, c)]
    for i, j, k in cand:
        n = np.cross(np.array(verts[j], float) - verts[i], np.array(verts[k], float) - verts[i])
        if float(np.dot(n, np.array(normal, float))) <= 0.0:
            raise SystemExit(f"quad winding failed for normal {normal}")
    return cand


def edge_counts(tris):
    counts = Counter()
    for a, b, c in tris:
        for e in ((a, b), (b, c), (c, a)):
            counts[tuple(sorted(e))] += 1
    if any(v > 2 for v in counts.values()):
        raise SystemExit("non-manifold edge (count > 2)")
    boundary = [e for e, v in counts.items() if v == 1]
    return counts, boundary


def xy_key(xy):
    return (xy[0], xy[1])


def boundary_position_keys(boundary, xy):
    keys = []
    for a, b in boundary:
        keys.append(tuple(sorted((xy_key(xy[a]), xy_key(xy[b])))))
    return keys


class Builder:
    def __init__(self):
        self.verts: list[list[float]] = []
        self.xy: list[tuple[Fraction, Fraction]] = []
        self.z: list[float] = []
        self.tris: list[tuple[int, int, int]] = []
        self.tags: list[str] = []

    def add_vert(self, x: Fraction, y: Fraction, z: float) -> int:
        i = len(self.verts)
        self.xy.append((x, y))
        self.z.append(z)
        self.verts.append([float(x), float(y), float(z)])
        return i

    def add_tris(self, tris, tag: str):
        for t in tris:
            self.tris.append(tuple(t))
            self.tags.append(tag)


def base_corners(b: Builder, z_lo: float, z_hi: float, x_shift: Fraction = Fraction(0)):
    xy = ((FACE_LO, FACE_LO), (FACE_HI, FACE_LO), (FACE_HI, FACE_HI), (FACE_LO, FACE_HI))
    lo, hi = [], []
    for x, y in xy:
        lo.append(b.add_vert(x + x_shift, y, z_lo))
        # hi appended after all lo so index layout stays explicit below
    # rebuild hi in the same XY order; lo was interleaved. Keep a clearer layout:
    return  # placeholder, replaced by explicit function


def make_cuboid(z_half: float, x_shift: Fraction = Fraction(0)):
    """8 centrosymmetric corners. Thickness is 2*z_half along Z. Returns builder parts."""
    b = Builder()
    z_lo, z_hi = -z_half, z_half
    xy = ((FACE_LO, FACE_LO), (FACE_HI, FACE_LO), (FACE_HI, FACE_HI), (FACE_LO, FACE_HI))
    lo, hi = [], []
    for x, y in xy:
        lo.append(b.add_vert(x + x_shift, y, z_lo))
    for x, y in xy:
        hi.append(b.add_vert(x + x_shift, y, z_hi))
    # Outward faces. +Z is CCW in XY.
    faces = {
        "pz": (hi, (0.0, 0.0, 1.0)),
        "nz": ([lo[0], lo[3], lo[2], lo[1]], (0.0, 0.0, -1.0)),
        "py": ([lo[3], lo[2], hi[2], hi[3]], (0.0, 1.0, 0.0)),
        "ny": ([lo[0], hi[0], hi[1], lo[1]], (0.0, -1.0, 0.0)),
        "px": ([lo[1], hi[1], hi[2], lo[2]], (1.0, 0.0, 0.0)),
        "nx": ([lo[0], lo[3], hi[3], hi[0]], (-1.0, 0.0, 0.0)),
    }
    for tag, (idxs, normal) in faces.items():
        b.add_tris(add_quad(idxs, normal, b.verts), tag)
    return b, {"lo": lo, "hi": hi, "z_lo": z_lo, "z_hi": z_hi, "x_shift": x_shift}


def subdivide_top(nx: int, ny: int, seam_duplicate: bool):
    """Replace the +Z quad by an off-centre conforming grid. Seam mode copies boundary indices."""
    b, info = make_cuboid(Z_HALF_07)
    hi = info["hi"]
    a, bb, c, d = hi
    keep = [i for i, t in enumerate(b.tags) if t != "pz"]
    b.tris = [b.tris[i] for i in keep]
    b.tags = [b.tags[i] for i in keep]
    x0, x1, y0, y1 = PATCH_X0, PATCH_X1, PATCH_Y0, PATCH_Y1
    grid = []
    for j in range(ny + 1):
        row = []
        for i in range(nx + 1):
            x = x0 + (x1 - x0) * i / nx
            y = y0 + (y1 - y0) * j / ny
            row.append(b.add_vert(x, y, info["z_hi"]))
        grid.append(row)

    def gid(i, j):
        return grid[j][i]

    grid_tris = []
    for j in range(ny):
        for i in range(nx):
            p00, p10 = gid(i, j), gid(i + 1, j)
            p11, p01 = gid(i + 1, j + 1), gid(i, j + 1)
            grid_tris.append((p00, p10, p11))
            grid_tris.append((p00, p11, p01))
    bottom = [a, bb] + [gid(i, 0) for i in range(nx, -1, -1)]
    right = [bb, c] + [gid(nx, j) for j in range(ny, -1, -1)]
    top = [c, d] + [gid(i, ny) for i in range(0, nx + 1)]
    left = [d, a] + [gid(0, j) for j in range(0, ny + 1)]
    annulus = fan(bottom) + fan(right) + fan(top) + fan(left)
    if seam_duplicate:
        dup = {}
        for j in range(ny + 1):
            for i in range(nx + 1):
                if i in (0, nx) or j in (0, ny):
                    src = gid(i, j)
                    dup[src] = b.add_vert(b.xy[src][0], b.xy[src][1], b.z[src])
        grid_tris = [tuple(dup.get(v, v) for v in t) for t in grid_tris]
    for t in grid_tris + annulus:
        pa, pb, pc = b.xy[t[0]], b.xy[t[1]], b.xy[t[2]]
        if tri_cross_z(pa, pb, pc) <= 0:
            raise SystemExit(f"top triangle not strictly CCW: {t}")
        if any(b.z[v] != info["z_hi"] for v in t):
            raise SystemExit("top triangle left the +Z plane")
        b.add_tris([t], "pz")
    meta = {
        "nx": nx, "ny": ny, "seam_duplicate": seam_duplicate,
        "patch": [str(x0), str(x1), str(y0), str(y1)],
        "z_hi": info["z_hi"], "z_lo": info["z_lo"],
        "hi_corners": hi, "grid_origin_count": (nx + 1) * (ny + 1),
    }
    return b, meta


def make_ring():
    b = Builder()
    z = 0.0
    outer = [b.add_vert(x, y, z) for x, y in (
        (FACE_LO, FACE_LO), (FACE_HI, FACE_LO), (FACE_HI, FACE_HI), (FACE_LO, FACE_HI))]
    inner = [b.add_vert(x, y, z) for x, y in (
        (-RING_INNER, -RING_INNER), (RING_INNER, -RING_INNER), (RING_INNER, RING_INNER), (-RING_INNER, RING_INNER))]
    a, bb, c, d = outer
    p, q, r, s = inner
    for poly in ([a, bb, q, p], [bb, c, r, q], [c, d, s, r], [d, a, p, s]):
        for t in fan(poly):
            if tri_cross_z(b.xy[t[0]], b.xy[t[1]], b.xy[t[2]]) <= 0:
                raise SystemExit("ring triangle not CCW")
            b.add_tris([t], "pz")
    return b


def make_two():
    b1, _ = make_cuboid(Z_HALF_03, Fraction(0))
    b2, _ = make_cuboid(Z_HALF_07, Fraction(2))
    shift = len(b1.verts)
    b1.verts += b2.verts
    b1.xy += b2.xy
    b1.z += b2.z
    b1.tris += [tuple(i + shift for i in t) for t in b2.tris]
    b1.tags += b2.tags
    return b1


def make_unwelded():
    src, _ = make_cuboid(Z_HALF_07)
    b = Builder()
    for t, tag in zip(src.tris, src.tags):
        ids = []
        for v in t:
            ids.append(b.add_vert(src.xy[v][0], src.xy[v][1], src.z[v]))
        b.add_tris([tuple(ids)], tag)
    return b


def xy_area(tris, xy) -> Fraction:
    total = Fraction(0)
    for a, b, c in tris:
        total += tri_cross_z(xy[a], xy[b], xy[c])
    return total / 2


def index_components(tris):
    parent = list(range(len(tris)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    owner = {}
    for i, poly in enumerate(tris):
        for v in poly:
            if v in owner:
                parent[find(i)] = find(owner[v])
            else:
                owner[v] = i
    groups = {}
    for i in range(len(tris)):
        groups.setdefault(find(i), []).append(i)
    return sorted((tuple(v) for v in groups.values()), key=min)


def position_components(tris, verts):
    parent = list(range(len(tris)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    owner = {}
    for i, poly in enumerate(tris):
        for v in poly:
            key = tuple(verts[v])
            if key in owner:
                parent[find(i)] = find(owner[key])
            else:
                owner[key] = i
    groups = {}
    for i in range(len(tris)):
        groups.setdefault(find(i), []).append(i)
    return len(groups)


def verify_top(b: Builder, nx: int, ny: int, seam: bool):
    top = [t for t, tag in zip(b.tris, b.tags) if tag == "pz"]
    if any(b.z[v] != Z_HALF_07 for t in top for v in t):
        raise SystemExit("planarity: +Z vertex z is not the frozen +0.035")
    for t in top:
        for v in t:
            x, y = b.xy[v]
            if not (FACE_LO <= x <= FACE_HI and FACE_LO <= y <= FACE_HI):
                raise SystemExit("coverage: top vertex outside the face rectangle")
    area = xy_area(top, b.xy)
    if area != 1:
        raise SystemExit(f"coverage: +Z area {area} != 1")
    counts, boundary = edge_counts(top)
    if seam:
        # Two disks on +Z: the patch and the annulus. Positions still form one surface.
        if position_components(b.tris, b.verts) != 1:
            raise SystemExit("seam split is not one continuous position-surface")
        if len(index_components(b.tris)) != 2 or len(index_components(top)) != 2:
            raise SystemExit("seam split did not make two index components")
    else:
        if len(index_components(top)) != 1:
            raise SystemExit("conforming +Z is not one index component")
        pos_keys = boundary_position_keys(boundary, b.xy)
        outer = []
        corners = [(FACE_LO, FACE_LO), (FACE_HI, FACE_LO), (FACE_HI, FACE_HI), (FACE_LO, FACE_HI)]
        loop = corners + [corners[0]]
        for p, q in zip(loop, loop[1:]):
            outer.append(tuple(sorted((p, q))))
        if sorted(pos_keys) != sorted(outer):
            raise SystemExit(f"conforming boundary is not the face rectangle: {pos_keys}")
        if any(v != 2 for v in counts.values() if v != 1):
            raise SystemExit("conforming edge count is not 1 or 2")
    # Side and bottom faces stay the original two triangles each.
    for tag, expect in (("nz", 1), ("px", Z_HALF_07 * 2), ("nx", Z_HALF_07 * 2),
                         ("py", Z_HALF_07 * 2), ("ny", Z_HALF_07 * 2)):
        tris = [t for t, tg in zip(b.tris, b.tags) if tg == tag]
        if len(tris) != 2:
            raise SystemExit(f"{tag} triangle count {len(tris)} != 2")
        area3 = 0.0
        for i, j, k in tris:
            n = np.cross(np.array(b.verts[j]) - b.verts[i], np.array(b.verts[k]) - b.verts[i])
            area3 += 0.5 * float(np.linalg.norm(n))
        if abs(area3 - expect) > 1e-15:
            raise SystemExit(f"{tag} area {area3!r} != {expect!r}")
    return {
        "top_triangles": len(top),
        "top_area": str(area),
        "top_index_components": len(index_components(top)),
        "top_position_components": position_components(top, b.verts),
        "nx": nx, "ny": ny, "seam_duplicate": seam,
    }


def verify_base(b: Builder, thickness: float):
    if len(b.verts) != 8 or len(b.tris) != 12:
        raise SystemExit("base cuboid is not 8 vertices and 12 triangles")
    corners = np.array(b.verts, float)
    centre = corners.mean(axis=0)
    if np.max(np.abs(centre)) != 0.0:
        raise SystemExit(f"corners are not centred: {centre}")
    reflected = {tuple(np.round(2 * centre - p, 12)) for p in corners}  # exact path below
    # Exact central symmetry: negation of every corner is a corner.
    keys = {tuple(p) for p in b.verts}
    if {tuple(-np.array(p)) for p in b.verts} != keys and thickness == Z_HALF_07 * 2:
        # vertices are stored as lists; negation uses floats
        neg = {tuple(float(-c) for c in p) for p in b.verts}
        if neg != keys:
            raise SystemExit("corner set is not centrosymmetric about the origin")
    if abs((max(v[2] for v in b.verts) - min(v[2] for v in b.verts)) - thickness) > 0.0:
        raise SystemExit("base z support does not equal the design thickness")
    if len(index_components(b.tris)) != 1 or position_components(b.tris, b.verts) != 1:
        raise SystemExit("base cuboid is not one component")
    return {"vertices": 8, "triangles": 12, "index_components": 1, "position_components": 1}


def verify_ring(b: Builder):
    area = xy_area(b.tris, b.xy)
    if area != Fraction(3, 4):
        raise SystemExit(f"ring area {area} != 3/4")
    if any(z != 0.0 for z in b.z):
        raise SystemExit("ring is not in the plane z=0")
    _counts, boundary = edge_counts(b.tris)
    keys = boundary_position_keys(boundary, b.xy)
    outer_c = [(FACE_LO, FACE_LO), (FACE_HI, FACE_LO), (FACE_HI, FACE_HI), (FACE_LO, FACE_HI)]
    inner_c = [(-RING_INNER, -RING_INNER), (RING_INNER, -RING_INNER), (RING_INNER, RING_INNER), (-RING_INNER, RING_INNER)]

    def loop(cs):
        cs = cs + [cs[0]]
        return [tuple(sorted((p, q))) for p, q in zip(cs, cs[1:])]

    if sorted(keys) != sorted(loop(outer_c) + loop(inner_c)):
        raise SystemExit("ring boundary is not the outer rectangle plus the inner rectangle")
    if len(index_components(b.tris)) != 1:
        raise SystemExit("ring is not one index component")
    return {"area": "3/4", "plane": "z=0", "index_components": 1, "triangles": len(b.tris)}


def verify_unwelded(b: Builder, welded_positions: int):
    if len(b.tris) != 12 or len(b.verts) != 36:
        raise SystemExit("unwelded cuboid should be 12 triangles and 36 corner indices")
    if len(index_components(b.tris)) != 12:
        raise SystemExit("unwelded index components != 12")
    if position_components(b.tris, b.verts) != 1:
        raise SystemExit("unwelded position-surface is not one component")
    if len({tuple(v) for v in b.verts}) != welded_positions:
        raise SystemExit("unwelded unique positions != 8")
    return {"index_components": 12, "position_components": 1, "unique_positions": 8, "indices": 36}


def verify_two(b: Builder):
    if len(index_components(b.tris)) != 2 or position_components(b.tris, b.verts) != 2:
        raise SystemExit("two cuboids are not two components")
    groups = index_components(b.tris)
    supports = []
    for g in groups:
        zs = [b.verts[v][2] for i in g for v in b.tris[i]]
        supports.append(max(zs) - min(zs))
    if sorted(supports) != [0.03, 0.07]:
        raise SystemExit(f"two-cuboid z supports {supports} != [0.03, 0.07]")
    return {"index_components": 2, "position_components": 2, "z_supports": sorted(supports)}


def support_along(verts, tris, normal) -> float:
    idx = sorted({v for t in tris for v in t})
    pts = np.array([verts[i] for i in idx], float)
    n = np.array(normal, float)
    proj = pts @ n
    return float(proj.max() - proj.min())


def scene_of(verts, tris, slots=("M_Synth_Main_Frame",)):
    glass_verts = [[2.0, 0.0, 0.0], [3.0, 0.0, 0.0], [3.0, 1.0, 0.0], [2.0, 1.0, 0.0]]
    glass_tris = [[0, 1, 2], [0, 2, 3]]
    frame = {
        "name": "SM_Synth_Main",
        "vertices": len(verts),
        "polygons": len(tris),
        "triangles": len(tris),
        "materials": list(slots),
        "face_geometry": {"vertices": [list(map(float, v)) for v in verts],
                          "polygons": [list(t) for t in tris]},
    }
    glass = {
        "name": "SM_Synth_MainGlass",
        "vertices": 4, "polygons": 2, "triangles": 2,
        "materials": ["M_Synth_MainGlass_1"],
        "face_geometry": {"vertices": glass_verts, "polygons": glass_tris},
    }
    rb = {"readback_ok": True, "blender": "synthetic", "meshes": [frame, glass],
          "other_objects": [], "images": [], "materials": []}
    extra = {"ok": True, "meshes": {
        "SM_Synth_Main": {"slots": list(slots), "polygon_material_index": [0] * len(tris)},
        "SM_Synth_MainGlass": {"slots": ["M_Synth_MainGlass_1"], "polygon_material_index": [0, 0]},
    }}
    return rb, extra


def replay_scene(depth: float):
    def box(lo, hi):
        (x0, y0, z0), (x1, y1, z1) = lo, hi
        return [[x0, y0, z0], [x1, y0, z0], [x1, y1, z0], [x0, y1, z0],
                [x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1]]

    wall = box((0, 0, 0), (4, 0.3, 3))
    fr = box((1, -depth, 1), (2, 0, 2))
    verts = wall + fr
    tris = [list(t) for t in BOX_T] + [[a + 8, b + 8, c + 8] for a, b, c in BOX_T]
    mat = [0] * len(BOX_T) + [1] * len(BOX_T)
    frame_name, glass_name = "SM_Test_Main", "SM_Test_MainGlass"
    glass_verts = [[1, -0.035, 1], [2, -0.035, 1], [2, -0.035, 2], [1, -0.035, 2]]
    glass_tris = [[0, 1, 2], [0, 2, 3]]
    main = {
        "name": frame_name, "vertices": len(verts), "polygons": len(tris), "triangles": len(tris),
        "materials": ["M_Test_Main_1", "M_Test_Main_Frame"],
        "face_geometry": {"vertices": verts, "polygons": [list(t) for t in tris]},
    }
    glass = {
        "name": glass_name, "vertices": 4, "polygons": 2, "triangles": 2,
        "materials": ["M_Test_MainGlass_1"],
        "face_geometry": {"vertices": glass_verts, "polygons": glass_tris},
    }
    rb = {"readback_ok": True, "blender": "synthetic", "meshes": [main, glass],
          "other_objects": [], "images": [], "materials": []}
    extra = {"ok": True, "meshes": {}}
    for mesh, idx in ((main, mat), (glass, [0, 0])):
        extra["meshes"][mesh["name"]] = {
            "slots": list(mesh["materials"]),
            "polygon_material_index": list(idx),
        }
    return rb, extra, tris, mat


def apply_rt(verts, rotation, translation):
    r = np.array(rotation, float)
    t = np.array(translation, float)
    out = []
    for v in verts:
        p = r @ np.array(v, float) + t
        out.append([float(p[0]), float(p[1]), float(p[2])])
    return out


def apply_perm(verts, tris, mat, kind: str):
    verts = [list(v) for v in verts]
    tris = [list(t) for t in tris]
    mat = list(mat)
    if kind in ("vertex_cycle", "vertex_cycle_and_face_reverse"):
        n = len(verts)
        # new_verts[i] = old_verts[(i+1) mod n]; polygon indices follow.
        old_of_new = [(i + 1) % n for i in range(n)]
        new_of_old = [0] * n
        for new_i, old_i in enumerate(old_of_new):
            new_of_old[old_i] = new_i
        verts = [verts[old_of_new[i]] for i in range(n)]
        tris = [[new_of_old[i] for i in t] for t in tris]
    if kind in ("face_reverse", "vertex_cycle_and_face_reverse"):
        tris = list(reversed(tris))
        mat = list(reversed(mat))
    return verts, tris, mat


class SvdTap:
    def __init__(self):
        self.calls = []
        self._real = np.linalg.svd

    def __enter__(self):
        tap = self

        def wrapped(a, full_matrices=True, compute_uv=True, hermitian=False):
            out = tap._real(a, full_matrices=full_matrices, compute_uv=compute_uv, hermitian=hermitian)
            if compute_uv:
                _u, s, vh = out
                axis = vh[-1]
                along = a @ axis
                tap.calls.append({
                    "singular_values": [float(x) for x in s],
                    "axis": [float(x) for x in axis],
                    "extent": float(along.max() - along.min()),
                    "points": int(a.shape[0]),
                })
            return out

        np.linalg.svd = wrapped
        return self

    def __exit__(self, *args):
        np.linalg.svd = self._real


def design_support_extents(mm, verts, tris, normal):
    """Per production index component, support along the known design normal. Not an SVD."""
    out = []
    groups = mm._components([list(t) for t in tris])
    own = index_components(tris)
    if sorted(tuple(sorted(g)) for g in groups) != sorted(tuple(sorted(g)) for g in own):
        raise SystemExit("independent index components differ from production _components")
    for group in groups:
        faces = [tris[i] for i in group]
        out.append(support_along(verts, faces, normal))
    return out


def metric_once(mm, rb, extra):
    snap_rb, snap_ex = copy.deepcopy(rb), copy.deepcopy(extra)
    tap = SvdTap()
    with tap:
        first = mm.windows_glazing(rb, extra)
    if rb != snap_rb or extra != snap_ex:
        raise SystemExit("windows_glazing mutated its input")
    with SvdTap():
        second = mm.windows_glazing(rb, extra)
    if first != second:
        raise SystemExit("second call differed")
    if rb != snap_rb or extra != snap_ex:
        raise SystemExit("windows_glazing mutated its input on the second call")
    return first, tap.calls


def rounded_from(extents):
    return {
        "min": round(min(extents), 4),
        "median": round(statistics.median(extents), 4),
        "max": round(max(extents), 4),
    }


def frame_only(tris, mat):
    return [tuple(t) for t, k in zip(tris, mat) if k == 1]


def evaluate_case(mm, name, verts, tris, mat, normal, design_thickness):
    records = []
    for tname, rotation, translation in TRANSFORMS:
        moved = apply_rt(verts, rotation, translation)
        n = np.array(rotation, float) @ np.array(normal, float)
        n = (float(n[0]), float(n[1]), float(n[2]))
        for pname in PERMS:
            pv, pt, pm = apply_perm(moved, tris, mat, pname)
            if name.startswith("replay_"):
                rb, extra = replay_pack(pv, pt, pm, name)
            else:
                rb, extra = scene_of(pv, pt)
            got, calls = metric_once(mm, rb, extra)
            extents = [c["extent"] for c in calls]
            if got["frame_depth_m"] != rounded_from(extents):
                raise SystemExit(f"{name} {tname} {pname}: API rounding != captured extents")
            supports = design_support_extents(mm, pv, frame_tris_of(pt, pm, name), n)
            if len(supports) != len(extents):
                raise SystemExit("oracle component count != SVD calls")
            dots = []
            for call in calls:
                dots.append(abs(float(np.dot(call["axis"], n))))
            depth = got["frame_depth_m"]
            records.append({
                "geometry": name,
                "transform": tname,
                "perm": pname,
                "frame_depth_m": depth,
                "frame_components": got["frame_components"],
                "frame_polygons": got["frame_polygons"],
                "glass_objects": got["glass_objects"],
                "glass_triangles": got["glass_triangles"],
                "unrounded_extents": extents,
                "design_support_extents": supports,
                "axis_abs_dot_design_normal": dots,
                "singular_values": [c["singular_values"] for c in calls] if (tname, pname) == ("identity", "none") else None,
                "axes": [c["axis"] for c in calls] if (tname, pname) == ("identity", "none") else None,
                "points": [c["points"] for c in calls] if (tname, pname) == ("identity", "none") else None,
                "design_thickness_m": design_thickness,
                "depth_minus_design_min": None if depth is None else depth["min"] - (design_thickness if not isinstance(design_thickness, list) else min(design_thickness)),
            })
    return records


def frame_tris_of(tris, mat, name):
    if name.startswith("replay_"):
        return [tuple(t) for t, k in zip(tris, mat) if k == 1]
    return [tuple(t) for t in tris]


def replay_pack(verts, tris, mat, name):
    depth = 0.0 if name.endswith("_0") else 0.07
    # Rebuild the glass the way the committed test does; frame/wall vertices are the permuted ones.
    _rb, extra_template, _tris, _mat = replay_scene(depth)
    glass = _rb["meshes"][1]
    main = {
        "name": "SM_Test_Main", "vertices": len(verts), "polygons": len(tris), "triangles": len(tris),
        "materials": ["M_Test_Main_1", "M_Test_Main_Frame"],
        "face_geometry": {"vertices": verts, "polygons": [list(t) for t in tris]},
    }
    rb = {"readback_ok": True, "blender": "synthetic", "meshes": [main, glass],
          "other_objects": [], "images": [], "materials": []}
    extra = {"ok": True, "meshes": {
        "SM_Test_Main": {"slots": ["M_Test_Main_1", "M_Test_Main_Frame"], "polygon_material_index": list(mat)},
        "SM_Test_MainGlass": extra_template["meshes"]["SM_Test_MainGlass"],
    }}
    return rb, extra


def replay_rows():
    path = ROOT / "docs" / "methods" / "windows-glazing" / "results.jsonl"
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        w = row["class_metrics"]["windows"]
        rows.append({
            "row": row["row"], "benchmark": row["benchmark"], "variant": row["variant"],
            "frame_components": w.get("frame_components"),
            "frame_polygons": w.get("frame_polygons"),
            "frame_depth_m": w.get("frame_depth_m"),
            "frame_reason": w.get("frame_reason"),
        })
    return rows


def main():
    assert_rotations()
    if (2 * Z_HALF_07) != 0.07 or (2 * Z_HALF_03) != 0.03:
        raise SystemExit("frozen half-thickness literals do not double to 0.07 and 0.03")
    mm = load_metrics()
    base, _ = make_cuboid(Z_HALF_07)
    checks = {"base": verify_base(base, 0.07)}
    geometries = [("base_cuboid", base, 0.07)]
    for n in (1, 4, 16, 64):
        built, _meta = subdivide_top(n, n, False)
        checks[f"conforming_{n}"] = verify_top(built, n, n, False)
        geometries.append((f"conforming_{n}", built, 0.07))
    seam, _meta = subdivide_top(4, 4, True)
    checks["seam_split_4"] = verify_top(seam, 4, 4, True)
    geometries.append(("seam_split_4", seam, 0.07))
    conf4 = geometries[2][1]
    if len(seam.tris) != len(conf4.tris):
        raise SystemExit("seam_split_4 and conforming_4 polygon counts differ")
    unwelded = make_unwelded()
    checks["unwelded"] = verify_unwelded(unwelded, 8)
    geometries.append(("unwelded_seams", unwelded, 0.07))
    ring = make_ring()
    checks["ring"] = verify_ring(ring)
    geometries.append(("flat_ring", ring, 0.0))
    two = make_two()
    checks["two"] = verify_two(two)
    geometries.append(("two_cuboids", two, [0.03, 0.07]))

    all_records = []
    for name, built, thickness in geometries:
        mat = [0] * len(built.tris)
        # one internal pair of calls happens inside metric_once; the loop itself is one pass
        all_records.extend(evaluate_case(
            mm, name, built.verts, built.tris, mat, DESIGN_NORMAL, thickness))

    for depth, label, thickness, normal in (
            (0.07, "replay_test_0_07", 0.07, (0.0, 1.0, 0.0)),
            (0.0, "replay_test_0", 0.0, (0.0, 1.0, 0.0))):
        rb0, _ex, tris, mat = replay_scene(depth)
        verts = rb0["meshes"][0]["face_geometry"]["vertices"]
        all_records.extend(evaluate_case(mm, label, verts, tris, mat, normal, thickness))

    # Second full pass, identity+none only, must match the first pass bitwise.
    repeat_ok = True
    first_id = {(r["geometry"], r["transform"], r["perm"]): r for r in all_records}
    for name, built, thickness in geometries:
        mat = [0] * len(built.tris)
        again = evaluate_case(mm, name, built.verts, built.tris, mat, DESIGN_NORMAL, thickness)
        for rec in again:
            prev = first_id[(rec["geometry"], rec["transform"], rec["perm"])]
            if rec["frame_depth_m"] != prev["frame_depth_m"] or rec["unrounded_extents"] != prev["unrounded_extents"]:
                repeat_ok = False
    if not repeat_ok:
        raise SystemExit("full-corpus repeat differed")

    def ident(name):
        return next(r for r in all_records if r["geometry"] == name and r["transform"] == "identity" and r["perm"] == "none")

    def depth_tuple(rec):
        d = rec["frame_depth_m"]
        return (d["min"], d["median"], d["max"])

    invariance = []
    for name, _b, _t in geometries:
        base_rec = ident(name)
        others = [r for r in all_records if r["geometry"] == name]
        rounded_same = all(depth_tuple(r) == depth_tuple(base_rec) for r in others)
        unrounded_deltas = []
        for r in others:
            a = sorted(base_rec["unrounded_extents"])
            b = sorted(r["unrounded_extents"])
            unrounded_deltas.append(max(abs(x - y) for x, y in zip(a, b)))
        invariance.append({
            "geometry": name,
            "rounded_invariant_under_rigid_and_perm": rounded_same,
            "max_abs_unrounded_delta": max(unrounded_deltas),
            "identity_depth": base_rec["frame_depth_m"],
            "identity_unrounded": base_rec["unrounded_extents"],
            "identity_design_support": base_rec["design_support_extents"],
            "identity_axis_abs_dot": base_rec["axis_abs_dot_design_normal"],
            "identity_polygons": base_rec["frame_polygons"],
            "identity_components": base_rec["frame_components"],
        })

    committed = replay_rows()
    payload = {
        "delivery_passed": False,
        "python": sys.version,
        "numpy": np.__version__,
        "head_sha": head_sha(),
        "source_sha256": {
            "methods_metrics.py": sha256_file(METRIC_PATH),
            "test_windows_glazing.py": sha256_file(ROOT / "tests" / "methods" / "test_windows_glazing.py"),
            "WHEN.md": sha256_file(ROOT / "docs" / "methods" / "windows-glazing" / "WHEN.md"),
            "VARIANTS.md": sha256_file(ROOT / "docs" / "methods" / "windows-glazing" / "VARIANTS.md"),
            "results.jsonl": sha256_file(ROOT / "docs" / "methods" / "windows-glazing" / "results.jsonl"),
            "windows.md": sha256_file(ROOT / "docs" / "domain" / "areas" / "windows.md"),
            "README_methods.md": sha256_file(ROOT / "docs" / "methods" / "README.md"),
        },
        "float_literals": {
            "0.035": float.hex(0.035), "2*0.035": float.hex(2 * 0.035),
            "0.07": float.hex(0.07), "0.015": float.hex(0.015), "0.03": float.hex(0.03),
            "two_times_0.035_eq_0.07": (2 * 0.035) == 0.07,
            "two_times_0.015_eq_0.03": (2 * 0.015) == 0.03,
        },
        "corpus_checks": checks,
        "invariance": invariance,
        "identity_details": [ident(name) for name, _b, _t in list(geometries) + [
            ("replay_test_0_07", None, None), ("replay_test_0", None, None)]],
        "committed_results_jsonl": committed,
        "repeat_bitwise_equal": repeat_ok,
        "records": all_records,
    }
    out_path = Path(sys.argv[1]) if len(sys.argv) > 1 else OUT / "probe_run.json"
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    summary = {
        "head_sha": payload["head_sha"],
        "numpy": np.__version__,
        "python": sys.version.split()[0],
        "repeat_bitwise_equal": repeat_ok,
        "invariance": invariance,
        "committed": committed,
        "identity_axes": {
            rec["geometry"]: {
                "axes": rec["axes"],
                "singular_values": rec["singular_values"],
                "points": rec["points"],
                "unrounded": rec["unrounded_extents"],
                "support": rec["design_support_extents"],
                "depth": rec["frame_depth_m"],
                "polygons": rec["frame_polygons"],
                "components": rec["frame_components"],
                "dots": rec["axis_abs_dot_design_normal"],
            }
            for rec in payload["identity_details"]
        },
    }
    summary_path = out_path.with_name(out_path.stem + "_summary.json")
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(summary_path)
    print(json.dumps({"invariance": invariance, "committed_depths": [
        {k: row[k] for k in ("row", "variant", "benchmark", "frame_depth_m", "frame_components", "frame_polygons")}
        for row in committed
    ]}, indent=2))


if __name__ == "__main__":
    main()
```

### Measured identity readouts

Verified-by-run. `frame_depth_m` is the public return value. Unrounded extents and axes were taken from the singular vector that this same `np.linalg.svd` call returned to `windows_glazing` (`vh[-1]`), then max-minus-min on the centred points passed into that call. Singular values are that return's `s`, recorded so they are not mistaken for the depth: on the welded cuboid the smallest singular value is `0.09899494936611666` and the extent is `0.07`.

| Geometry | Polygons | Components | Unrounded extents (m) | `frame_depth_m` | Support on the design normal (m) | abs dot(axis, design normal) |
|---|---:|---:|---|---|---|---|
| `base_cuboid` | 12 | 1 | 0.07 | 0.07 / 0.07 / 0.07 | 0.07 | 1 |
| `conforming_1` | 20 | 1 | 0.08957273567162075 | 0.0896 / 0.0896 / 0.0896 | 0.07 | 0.999904156743349 |
| `conforming_4` | 62 | 1 | 0.1060702099537145 | 0.1061 / 0.1061 / 0.1061 | 0.07 | 0.9996742705891889 |
| `conforming_16` | 590 | 1 | 0.0992810177602631 | 0.0993 / 0.0993 / 0.0993 | 0.07 | 0.9997854125025137 |
| `conforming_64` | 8462 | 1 | 0.07544259365122902 | 0.0754 / 0.0754 / 0.0754 | 0.07 | 0.9999925931051434 |
| `seam_split_4` | 62 | 2 | 0.10302482909530182, 0.0 | 0.0 / 0.0515 / 0.103 | 0.07, 0.0 | 0.9997269872395248, 1 |
| `unwelded_seams` | 12 | 12 | 0.0 twelve times | 0.0 / 0.0 / 0.0 | 0.0 on four horizontal triangles, 0.07 on eight vertical triangles | 1 on the horizontal triangles, 0 on the vertical triangles |
| `flat_ring` | 8 | 1 | 0.0 | 0.0 / 0.0 / 0.0 | 0.0 | 1 |
| `two_cuboids` | 24 | 2 | 0.03, 0.07 | 0.03 / 0.05 / 0.07 | 0.03, 0.07 | 1, 1 |
| `replay_test_0_07` | 12 | 1 | 0.07 | 0.07 / 0.07 / 0.07 | 0.07 along Y | 1; axis `(0, 1, 0)` |
| `replay_test_0` | 12 | 1 | 0.0 | 0.0 / 0.0 / 0.0 | 0.0 | 1; captured axis `(-0.0, -1.0, -0.0)` |

Identity axes of the conforming patch, captured from the production call:

| Geometry | Axis `(x, y, z)` | Points in the component |
|---|---|---:|
| `base_cuboid` | `(0, 0, 1)` | 8 |
| `conforming_1` | `(-0.009789722349793181, 0.009789722349793126, 0.999904156743349)` | 12 |
| `conforming_4` | `(-0.018046505506235613, 0.018046505506235655, 0.9996742705891889)` | 33 |
| `conforming_16` | `(-0.014648019442543583, 0.014648019442543542, 0.9997854125025137)` | 297 |
| `conforming_64` | `(-0.0027215560669344766, 0.0027215560669344996, 0.9999925931051434)` | 4233 |

`seam_split_4` orders the shell first (24 points, tilted axis, unrounded extent `0.10302482909530182`) and the coplanar patch second (25 points, axis `(0, 0, 1)`, extent `0.0`). `statistics.median` of those two extents is `0.05151241454765091`, and `round(..., 4)` is `0.0515`. Median of the two-cuboid extents `0.03` and `0.07` is the float `0.05`.

The welded cuboid, the flat ring and the committed test boxes are the cases where the captured axis is exactly the design normal and the rounded depth equals the design thickness. The off-centre conforming grids are counterexamples to treating those two numbers as the same quantity: the design support stays `0.07` while the rounded PCA depth does not. Density is not monotone on this patch. `n = 4` is the largest rounded depth in the set (`0.1061`); `n = 64` is the closest (`0.0754`) and still differs in the fourth decimal.

A post-check on the saved axes, still without a second SVD, compared each shell extent to the support of the eight corners along that axis, `|ax| + |ay| + 0.07|az|`. The values match exactly for `base_cuboid`, `conforming_1`, `conforming_4`, `conforming_64` and the `seam_split_4` shell. `conforming_16` differs by one ulp (`1.3877787807814457e-17`). Added patch vertices lie on the existing `+Z` face, inside that corner hull. The depth increase is the hull's support on the tilted axis.

`unwelded_seams` keeps the polygon count of `base_cuboid` at 12 and the same eight positions. The rounded depth changes from `0.07` to `0.0`. Vertical triangles have design-normal support `0.07` and PCA extent `0.0`, with the captured axis along the face normal `(±1, 0, 0)` or `(0, -1, 0)`. `seam_split_4` keeps the polygon count of `conforming_4` at 62. The rounded triple changes from `0.1061 / 0.1061 / 0.1061` to `0.0 / 0.0515 / 0.103`. Polygon-count changes on the conforming series are the expected record of subdivision. The depth changes on the equal-polygon pairs are separate.

### Rigid copies and rounding

Verified-by-run. Transforms are the exact matrices `I`, `Rz90`, `Rx90`, `Ry90`, translation `(4, -2, 0.5)`, and `Rx90` plus translation `(1, 2, 3)`. Permutations are none, a vertex-index cycle, reversed face order, and both. Each matrix satisfies `det = 1` and `R.T @ R = I` in float64.

For every geometry, including both replay scenes, all 24 copies share the identity rounded triple. The largest absolute change in sorted unrounded extents is `2.498001805406602e-16` (`conforming_64`). `flat_ring` and `replay_test_0` have unrounded delta `0`.

`frame_depth_m` is `round(min, 4)`, `round(statistics.median, 4)`, `round(max, 4)` from the unrounded extents. On the identity rows the largest `|round(x, 4) - x|` is `4.259365122902259e-05` (`conforming_64`). That sits inside half a unit of the fourth decimal (`5e-5`). The conforming gaps from `0.07` are `0.01957273567162075`, `0.0360702099537145`, `0.0292810177602631` and `0.00544259365122902` m. Those gaps are larger than the `0.0001` m reporting step. No measured identity extent landed on a trailing-5 tie at the fourth decimal, so this run does not exercise a half-even boundary.

### Committed rows

Verified-by-read of `docs/methods/windows-glazing/results.jsonl`, not a new measurement of those FBX files:

| Row | Benchmark | Variant | `frame_depth_m` | Components | Polygons |
|---|---|---|---|---:|---:|
| R2 | kpp1 | modelled-frames | 0.07 / 0.07 / 0.07 | 24 | 768 |
| R4 | kpp1 | inset-glass-trim | 0.0 / 0.0 / 0.0 | 24 | 192 |
| R10 | tow02 | modelled-frames | 0.07 / 0.07 / 0.07 | 1192 | 65260 |
| R12 | tow02 | inset-glass-trim | 0.0 / 0.0 / 0.0 | 1192 | 9536 |

Rows without a frame slot (R1, R3, R5, R6, R7, R8, R9, R11) store `frame_depth_m: null`, `frame_components: 0`, `frame_polygons: 0`. The stored R2 and R10 numbers agree with the `WHEN.md` sentence. The synthetic replay agrees with the unit-test box. Neither fact is a measurement of the kpp1 or tow02 meshes. This report does not call those stored 0.07 m rows wrong.

## How it applies to this repository

`tools/methods/methods_metrics.py` `windows_glazing` is the readout behind `class_metrics.windows` in `tools/methods/run_variant.py` and the Frame depth column of `docs/methods/windows-glazing/RESULTS.md`. The number is the rounded PCA range of each index-connected vertex set on slots whose names contain `Frame`.

`WHEN.md` uses that number as "frame depth" for the 70 mm `solidify` in `VARIANTS.md`. On the welded synthetic cuboid and on the committed test box, the PCA range equals that 0.07 m thickness. On the off-centre conforming patch, and on duplicated seam indices, it does not. A later edit to frame welding or face tessellation can change the column without moving the design planes `z = ±0.035`.

`docs/domain/areas/windows.md` is unchanged by this. C25 and C35 remain open user choices. No L2 window check gains a threshold from these measurements.

Required semantic choice, left open: whether text and later comparisons may treat `frame_depth_m` as design normal thickness, or only as the PCA extent implemented in `windows_glazing`. A second open choice is whether a component continues to mean shared vertex indices when coordinates on a seam are duplicated. This report adopts neither choice, and it adopts no replacement estimator.

## Proposed next tasks

1. **Pin the current PCA witnesses.** Scope: add tests, later and separately, that build the welded 8-corner cuboid and the 36-index unwelded copy and assert today's public return. No change to `windows_glazing`. Literal pairs, identity, slot name containing `Frame`: welded 12 triangles, 8 positions -> `frame_depth_m = {min: 0.07, median: 0.07, max: 0.07}`, `frame_components = 1`, `frame_polygons = 12`. Unwelded 12 triangles, 36 indices, 8 positions -> `{min: 0.0, median: 0.0, max: 0.0}`, `frame_components = 12`, `frame_polygons = 12`. Value: a later weld or plane-thickness change has to edit the assertion on purpose. Effort S. `Archive: no roadmap link`.

2. **Keep the WHEN.md 0.07 m sentence tied to the stored rows until the wording choice.** Scope: a short note next to `docs/methods/windows-glazing/WHEN.md`, after the user chooses, quoting the two equal-polygon witnesses. No threshold, no new metric, no C25 or C35 text. Literal pairs: `conforming_4` (patch `[1/8, 3/8] x [-3/8, -1/8]`, shared indices) -> `{min: 0.1061, median: 0.1061, max: 0.1061}`, `frame_components = 1`, `frame_polygons = 62`, design support along Z `0.07`. `seam_split_4` (those 62 triangles, patch-boundary indices duplicated) -> `{min: 0.0, median: 0.0515, max: 0.103}`, `frame_components = 2`, `frame_polygons = 62`. Value: the stored R2/R10 figure and the PCA definition stay distinguishable. Effort S. `Archive: no roadmap link`.

## Open questions for the user

- Should `frame_depth_m` stay the PCA range of index-connected vertices, including where that range and the design normal thickness differ?
- Should a seam of duplicated coordinates stay split until indices are welded?
- The stored 0.07 m values on R2 and R10 were not recomputed from the benchmark FBX files. Is a later asset replay wanted as its own task?
- C25 and C35 are untouched here. They stay with you.
