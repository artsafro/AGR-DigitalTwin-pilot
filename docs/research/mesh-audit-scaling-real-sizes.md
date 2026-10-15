# Research: mesh checks at real model sizes — which are super-linear, and does it matter?

Card t_88727c5d (research, no GitHub issue). Follows the PR #109 review finding P2 / issue #110.
Measured on `main` at 8255c4b. PR #109 is **merged** (head `improve/hyp-93`), so its
`component_volume.py` was measured on `main`, read-only. Synthetic data only; nothing from `data/` was read.

## Summary

- 14 per-mesh routines were classified and timed on synthetic closed meshes (subdivided box; bipyramid with two
  high-valence apexes and long sliver triangles) at 1k / 5k / 20k / 50k faces, one process per run, 60 s cap.
- **Three are super-linear and matter at real sizes**:
  `near_parallel_overlaps` (O(F²), 20.5 s at 20k, >60 s at 50k), which makes the whole `check_mesh` O(F²);
  `check_orientation` / `_orientation_hits` (fixed 64×64 bin grid: O(F²) on even meshes, 26 s at 20k, and
  13.9 s already at **1k** sliver faces); and `component_volume._check_single_vertex_fans` (O(V·F),
  44.7 s at 4.8k, >60 s at 20k).
- Real sizes in the repo: KPP1 NPM 24 262–24 298 tris, PSU275 24 876 tris, FACADES-ATLAS objects 11.7k–30.1k
  faces, OBJ03 source parts up to 113 279 tris, NPM limit 150 000 tris per FBX. At 24k–30k
  `check_mesh` + `check_orientation` cost ~1–2 minutes per run (extrapolated); at 113k–150k, tens of minutes.
- `component_signed_volumes` is not called by any runner on `main` (tests only), so #110 does not hurt today; it
  becomes unusable (≥20 min at 24k) the day it is wired in.
- Everything else (weld, edge_uses, parts, fan_vertices, open_loops, winding_bad_edges, mesh_audit
  `inspect_mesh`) is ≈ linear and below 2 s at 50k.
- Three fixes proposed, ranked: spatial pruning in `near_parallel_overlaps` (S–M), adaptive orientation bins
  (S–M), vertex→triangle incidence for #110 (S).

## Method (verified: ran it)

- Script: appendix A (kept out of the branch; card scope is docs only). One call =
  `python bench_one.py <check> <shape> <faces>`, timed with `time.perf_counter()` around the routine only
  (mesh build and welding excluded). Each run in its own process under `timeout 60`; after a timeout the
  larger sizes of that check/shape were skipped.
- `box`: closed axis box 10 m, each side an n×n quad grid split into 2 triangles (12 n² triangles: 972, 4 800,
  20 172, 50 700), outward winding, welded vertices. `bipy`: n-gon ring of radius 10 m plus two apexes
  (2n triangles: 1 000 … 50 000), long slivers and two vertices of valence n. Both verified closed and
  outward before timing: `check_orientation` value 0, `component_signed_volumes` eligible with positive
  volume (box: exactly 1000.0 m³).
- Tolerances from `benchmark/bench-b01-box/tolerances.json` (`geometry`), `weld_m = 0.003`.
- Machine: Windows 11, AMD64 Family 25 (Zen 3), Python 3.14.7, numpy 2.5.3, shapely 2.1.2, single run each
  (no repeats; ±20 % noise is plausible on the sub-second rows).
- Extrapolations to real sizes use the measured exponent between the two largest finished sizes
  (power law); they are estimates, not measurements, and are marked "≈".

## Findings

### Table

F = triangles, V = vertices, D = 49 ray directions, B = 64 bins per side, R = rays. "—" = not run
(earlier size hit the cap). Times in seconds; `>60` = killed by the 60 s cap.

| Check / routine | file:line | Complexity (from code) | box 1k | 5k | 20k | 50k | bipy 1k | 5k | 20k | 50k | Verdict at real sizes (24k–30k / 113k–150k) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `weld` (+ `_pairs_within`) | src/twinqa/geometry/mesh.py:66, :96 | O(V log V) grid + sort; Python loop over groups with near pairs only | 0.001 | 0.006 | 0.014 | 0.036 | | | | | OK |
| `edge_uses` | src/twinqa/geometry/mesh.py:123 | O(F log F) (`np.unique` on edges) | 0.001 | 0.007 | 0.035 | 0.118 | | | | | OK |
| `parts` | src/twinqa/geometry/mesh.py:131 | O(F α) union-find, Python loop | 0.003 | 0.017 | 0.072 | 0.172 | | | | | OK |
| `fan_vertices` (non-manifold vertex, #57) | src/twinqa/geometry/checks.py:283 | O(F α) dict union-find, Python | 0.018 | 0.064 | 0.287 | 1.162 | 0.015 | 0.086 | 0.371 | 0.974 | OK (≈4–6 s at 113k–150k) |
| `open_loops` (closed mesh: no open edges) | src/twinqa/geometry/checks.py:136 | O(open edges) + shapely per loop × levels | 0.0001 | 0.0003 | 0.001 | 0.004 | | | | | OK on closed meshes; cost follows open-edge count, not measured with open edges |
| `near_parallel_overlaps` (inside `check_mesh`; also `tools/qa/check_clearance.py`) | src/twinqa/clearance.py:26 | **O(F²)**: a full numpy pass over all F faces for every face, then shapely on candidates | 0.204 | 1.284 | 20.48 | >60 | 0.135 | 0.821 | 14.81 | >60 | **Matters**: ≈29–44 s at 24k–30k, ≈9.5–16 min at 113k–150k |
| `check_mesh` (all of the above + overlaps) | src/twinqa/geometry/checks.py:313 | O(F²), dominated by `near_parallel_overlaps` | 0.232 | 1.319 | 18.75 | >60 | 0.194 | 1.028 | 19.40 | >60 | **Matters** (same as the line above) |
| `winding_bad_edges` | src/twinqa/geometry/checks.py:834 | O(F log F) per mesh (`np.unique`), re-welds per mesh | 0.004 | 0.025 | 0.093 | 0.267 | | | | | OK |
| `_orientation_hits` / `_first_back_hits` | src/twinqa/geometry/checks.py:978, :895 | per direction: Σ over bins of (triangles in bin × rays in bin); B fixed at 64 (`_ORI_BINS`, :823) and R = 1024 + F, so **O(D·F²/B²)** for even meshes, and **O(D·Σ bbox-bins × rays)** for slivers, whose bbox covers up to B² bins | 0.243 | 1.347 | 26.05 | >60 | | | | | **Matters** |
| `check_orientation` | src/twinqa/geometry/checks.py:1051 | winding + `_orientation_hits` | 0.219 | 1.277 | 27.77 | >60 | **13.86** | >60 | — | — | **Matters**: ≈41–65 s at 24k–30k even meshes, ≈19–34 min at 113k–150k; sliver-heavy meshes (strips, belts, rails) can exceed 60 s at ~5k |
| `_partition_components` | src/twinqa/geometry/component_volume.py:85 | O(F) dict + BFS, Python | 0.005 | 0.028 | 0.102 | 0.429 | | | | | OK |
| `_check_single_vertex_fans` (#110) | src/twinqa/geometry/component_volume.py:123 | **O(V·F)**: for every vertex, `v in triangles[t]` over all component triangles (:127) | 0.861 | 44.75 | >60 | — | 0.911 | 43.60 | >60 | — | Not run by any runner today; would be ≥20 min at 24k if wired in (F² lower bound from 4.8k) |
| `component_signed_volumes` | src/twinqa/geometry/component_volume.py:224 | O(V·F) via `_check_eligibility` (:163) → `_check_single_vertex_fans` | 0.859 | 45.55 | >60 | — | 0.951 | 48.96 | >60 | — | same as the line above |
| `inspect_mesh` (mesh_audit: bowtie/self-crossing polygons, near-duplicates, winding, components) | technical_library/mesh_audit/core.py:56 | O(F·k²) (k = polygon size; `_has_proper_crossing` :7 is O(k³) per polygon); near-duplicates O(V) grid, worst case O(V²) if many points fall in one 1 mm cell | 0.029 | 0.100 | 0.560 | 1.756 | 0.024 | 0.108 | 0.469 | 1.362 | OK for triangles/quads; an n-gon of k ≫ 10 costs k³ (not measured) |

Not timed, classified from the code only:

- `check_complexity` — src/twinqa/geometry/complexity.py:51. Linear in triangles, but **O(meshes × objects)** in
  Python: `next(ob ... for ob in objects ...)` runs inside the loops over meshes at :63 and :77. It scales with
  the object count of a scene (e.g. RailClone/decor instances), not with faces. With thousands of instances this
  is quadratic; the face-count benchmark above does not exercise it.
- `_seat` (checks.py:451), `_slab_boxes` (:470), the slab block in `check_mesh` (:347–:381): one shapely union
  per open loop / per slab level over the matching flat triangles — O(L·F) with L loops/levels, small L in
  practice. Only on the `from_source` path with open loops; not exercised by closed synthetic meshes.
- `check_decor` (:632), `check_opening_planes` (:521), `check_floor_areas` (:58), `check_silhouettes` (:103):
  spec-driven checks (per decor element / opening / section), not per-mesh topology; out of scope here.

### Why the three are super-linear (verified: read the code)

1. `near_parallel_overlaps` (src/twinqa/clearance.py:35–:44): `dot = normals @ n` and the centre/bbox filter run
   over **all** faces for each face `i`. The vectorised inner step hides it, but it is F numpy passes of length F.
   The measured exponent is 1.93 (box) / 2.09 (bipy) between 5k and 20k. Exact results are already pruned by
   plane distance and bbox; only the candidate search is quadratic.
2. `_first_back_hits` (src/twinqa/geometry/checks.py:895): candidates come from a 64×64 grid per direction. Rays
   are 32² grid rays **plus one per triangle**, so rays per bin grow with F, and triangles per bin grow with F:
   pairs ≈ F²/B² per direction × 49 directions. A sliver triangle's bbox covers whole rows/columns of bins
   (`_enumerate_bins`, :878), so on the bipyramid each triangle is paired with a large share of all rays:
   13.9 s at 1 000 faces. Measured exponent 2.06–2.14 on the box.
3. `_check_single_vertex_fans` (src/twinqa/geometry/component_volume.py:127): `incident_tris = [t for t in
   comp_tri_ids if v_idx in triangles[t]]` per vertex — O(V·F) Python, with a numpy row membership test per
   pair. Measured exponent 2.4–2.5 between 1k and 5k. Matches the #110 probe (2 000 faces = 3.8 s; here 4 800
   faces = 44.7 s).

### Where these checks run (verified: grep on `main`)

- `checks.run` (checks.py:1072) calls `check_mesh` and `check_orientation`; `run` is used by
  `tools/qa/run_benchmark.py:31`, `tools/qa/check_geometry.py:19` and `tools/qa/run_from_source.py:82` (imported
  source readback, e.g. K01 KPP1, ~24k tris). So every K01-class run already pays ≈1–2 min for these two
  checks (extrapolated, not measured on the real readback — that needs `data/`).
- `near_parallel_overlaps` also runs in `tools/qa/check_clearance.py:41`.
- `component_signed_volumes`: no caller outside `tests/` (grep of `src/` and `tools/`).
- `inspect_mesh`: `technical_library/mesh_audit/blender.py:38` (inside Blender; not run here).

### Real face counts used (from tracked metadata, never `data/`)

| Source | Size |
|---|---|
| `benchmark/*/tolerances.json` `triangles_max` (= `standards/NPM_STANDARD.yaml` oks_triangles_per_fbx_max) | 150 000 |
| `jobs/KPP1/STATE.md:237` (v007 run) | Main 24 298 tris; NPM 24 262 + 76 |
| `jobs/PSU275/export-safety-evidence.json:42` | 24 876 tris |
| `jobs/FACADES-ATLAS/verification.json:7, :25, :43` | 18 125 / 11 714 / 30 073 faces |
| `jobs/OBJ03/modules/modules.json` (source parts) | max 113 279 tris (RailClone2146 slot 8), 95 504, 53 744 …; 417 330 summed over parts |

### External sources (claims only; not verified by running them)

- Shapely 2.x `STRtree.query` takes an array of geometries and returns all (input, tree) index pairs whose
  bounding boxes intersect, optionally with a predicate — a bulk candidate search instead of a per-face full scan.
  https://shapely.readthedocs.io/en/2.1.2/strtree.html (shapely 2.1.2 is the version in this repo's venv —
  verified).
- SciPy `scipy.sparse.csgraph.connected_components` labels the components of a sparse graph in compiled code —
  an option for per-vertex fan components built from a triangle-adjacency sparse matrix.
  https://docs.scipy.org/doc/scipy/reference/generated/scipy.sparse.csgraph.connected_components.html
- trimesh builds a vertex×face sparse incidence once (`faces_sparse`, `vertex_faces`) and derives per-vertex
  face lists from it — the standard pattern #110 asks for.
  https://github.com/mikedh/trimesh/blob/main/trimesh/base.py

## How it applies to this repository

- `src/twinqa/clearance.py` — the O(F²) candidate loop; fix 1.
- `src/twinqa/geometry/checks.py` — `check_mesh` inherits fix 1; `_first_back_hits` / `_ORI_BINS` (:823, :895)
  is fix 2. Results must stay identical: binning is only the candidate filter, the barycentric join decides.
- `src/twinqa/geometry/component_volume.py` — issue #110; fix 3.
- `src/twinqa/geometry/complexity.py:63, :77` — O(meshes × objects) lookups; a one-line `mesh -> group` dict
  would remove it (mentioned, not ranked; only matters with thousands of instances).
- `docs/domain/validation.md` and `benchmark/README.md` have no runtime budget for QA checks; the numbers above
  are the first scaling evidence.

## Proposed next tasks (ranked by value / effort)

1. **Spatial candidate search in `near_parallel_overlaps`** — value L, effort S–M.
   Replace the per-face full scan in `src/twinqa/clearance.py:35–:44` with a bulk candidate search: bucket faces by
   quantised dominant axis + plane offset (or sort by plane offset and take the ±tolerance window), then bbox-pair
   them (shapely `STRtree.query` on the 2D projected boxes, or a sort-and-sweep), and keep the existing exact
   tests (|cos| > 0.999999, plane distance, shapely intersection area). Acceptance: identical `pairs` output to the
   current function on the existing tests plus a randomized synthetic corpus (opposite/same direction, 5 mm insets,
   coplanar touching), and a descriptive scaling test: 50k box under 5 s. Speeds up every `check_mesh` and
   `tools/qa/check_clearance.py` run.
2. **Adaptive orientation bins with sliver-safe candidates** — value L, effort S–M.
   In `_first_back_hits` (checks.py:895) scale the bin count with the problem (e.g. `bins ≈ clip(sqrt(n_tri +
   n_rays), 64, 1024)`) and cap the bins a single triangle registers in by walking only the bins its projected
   triangle (not its bbox) covers, or by splitting long slivers' bbox into row spans. Results must be bit-identical
   (the binning only filters; the barycentric/depth ranking decides) — prove it on the current orientation tests,
   the D093 ground-cap cases and the #93/#109 inverted-box fixtures. Acceptance: 50k box < 10 s and 5k bipyramid
   < 5 s. Memory note: the pair arrays in `_first_back_hits` grow with the pair count; bounded bins also bound
   memory.
3. **Vertex→triangle incidence for component fans (issue #110)** — value S today (no runner calls it), effort S.
   Build incidence once (argsort of `triangles.ravel()`, or a sparse vertex×face matrix) and run the per-vertex fan
   BFS only on each vertex's own triangles; keep exact per-component semantics and deterministic output; add the
   disconnected-fan and vertex-only-touching-boxes controls #110 lists. Do it before `component_signed_volumes` is
   wired into `checks.run` or any runner.

## Open questions for the user

1. Is there a runtime budget for one QA run (e.g. `run_from_source` on a 24k K01 readback, or a 150k NPM FBX)? It
   decides whether fixes 1–2 are needed now or only before OBJ03-size imports.
2. Should `check_orientation` / `check_mesh` run on each OBJ03 source part (up to 113k tris) or only on the
   delivered NPM/VPM readback? At part level the current code is ≈10–20 min per part (extrapolated).
3. Is `component_signed_volumes` planned to be wired into `checks.run` (it is report-only and unused now)? If not,
   fix 3 can wait.

## Appendix A — benchmark script (scratch, synthetic only)

Kept outside the branch (`$TMPDIR/mesh_bench/bench_one.py`); run from the worktree root with
`.venv/Scripts/python.exe bench_one.py <check> <box|bipy> <faces> .` under `timeout 60`.

```python
import json, sys, time
from pathlib import Path
import numpy as np
REPO = Path(sys.argv[4]) if len(sys.argv) > 4 else Path.cwd()
sys.path[:0] = [str(REPO / "src"), str(REPO / "technical_library" / "mesh_audit")]
from twinqa.geometry.mesh import Soup, weld, edge_uses, parts
from twinqa.geometry import checks
from twinqa.clearance import near_parallel_overlaps

def box(n, size=10.0):            # closed box, n x n quads per side -> 12 n^2 triangles, outward
    verts, index, tris = [], {}, []
    def vid(p):
        key = tuple(round(c, 9) for c in p)
        if key not in index:
            index[key] = len(verts); verts.append(key)
        return index[key]
    g = np.linspace(0.0, size, n + 1)
    for axis in range(3):
        for side in (0.0, size):
            u, w = [k for k in range(3) if k != axis]
            for i in range(n):
                for j in range(n):
                    q = []
                    for a, b in ((i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1)):
                        p = [0.0, 0.0, 0.0]; p[axis], p[u], p[w] = side, g[a], g[b]; q.append(vid(p))
                    t1, t2 = (q[0], q[1], q[2]), (q[0], q[2], q[3])
                    if (side == 0.0) == ((u - axis) % 3 == 1):
                        t1, t2 = t1[::-1], t2[::-1]
                    tris += [t1, t2]
    return np.array(verts, float), np.array(tris, int)

def bipyramid(faces):              # ring of faces/2 vertices + 2 apexes: slivers, valence faces/2
    m = max(faces // 2, 3)
    a = np.linspace(0, 2 * np.pi, m, endpoint=False)
    v = np.vstack([np.stack([10 * np.cos(a), 10 * np.sin(a), np.zeros(m)], 1), [[0, 0, 10.0]], [[0, 0, -10.0]]])
    t = [(i, (i + 1) % m, m) for i in range(m)] + [((i + 1) % m, i, m + 1) for i in range(m)]
    return v, np.array(t, int)

check, shape, faces = sys.argv[1], sys.argv[2], int(sys.argv[3])
v, t = box(max(1, round((faces / 12) ** 0.5))) if shape == "box" else bipyramid(faces)
soup = Soup(v, t, np.full(len(t), 1), np.full(len(t), 3), {}, 0, ("model",), np.zeros(len(t), int))
tol = json.loads((REPO / "benchmark/bench-b01-box/tolerances.json").read_text())["geometry"]; tol["weld_m"] = 0.003
ranges = checks.load_ranges(); ids = weld(v, tol["weld_m"]); _, counts, side = edge_uses(t, ids)
skip = np.zeros(len(t), bool)
run = {
    "weld": lambda: weld(v, tol["weld_m"]), "edge_uses": lambda: edge_uses(t, ids), "parts": lambda: parts(t, ids),
    "fan_vertices": lambda: checks.fan_vertices(t, ids, side, skip),
    "open_loops": lambda: checks.open_loops(soup, ids, counts, side, skip, tol, ranges),
    "near_parallel_overlaps": lambda: near_parallel_overlaps(
        [{"object": "model", "index": i, "points": x.tolist()} for i, x in enumerate(soup.corners())], tol["weld_m"]),
    "check_mesh": lambda: checks.check_mesh(soup, tol, ranges),
    "winding_bad_edges": lambda: checks.winding_bad_edges(soup, tol["weld_m"]),
    "orientation_hits": lambda: checks._orientation_hits(soup),
    "check_orientation": lambda: checks.check_orientation(soup, tol),
}
# component_volume: _partition_components(t); _check_single_vertex_fans(t, list(range(len(t))), sorted(unique(t)));
# component_signed_volumes([{"name", "vertices", "triangles"}]); mesh_audit: core.inspect_mesh(v.tolist(), t.tolist())
start = time.perf_counter(); run[check](); dt = time.perf_counter() - start
print(json.dumps({"check": check, "shape": shape, "faces": int(len(t)), "seconds": round(dt, 4)}))
```
