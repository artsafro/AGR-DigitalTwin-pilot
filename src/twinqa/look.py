"""Look-finished modelling checks on the work-FBX readback (tools/blender/fbx_readback.py).

new-case: report-only decor-embed and edge-loop checks for the look-finished gate [D199], [D200].

Both checks are ``review`` when they find a defect and ``pass`` when clean, never ``fail``:
the user fixes these by hand ("look-finished"), so they report rather than block a hand-off.

- "decor embed" [D199]: decor / attachments (arches, light fixtures, frames and similar) must
  embed 10-20 mm into the facade they sit on instead of standing off and floating. The check
  measures the minimum gap between each attachment mesh (every non-UCX mesh that is not the
  ``_Main`` facade and not ``_MainGlass``) and the ``_Main`` facade; a gap larger than
  ``DECOR_FLOAT_TOL_M`` is a floating stand-off and is reported. The exact 10-20 mm embed depth
  is not graded here (the measured minimum gap is what decides floating vs embedded).
- "edge loop continuity" [D200]: edge loops and rings continue through the mesh; a loop that
  starts and stops mid-run is a defect even on a closed mesh. The check counts T-junctions (a
  vertex of one polygon lying strictly on the edge of another polygon, within ``TJUNCTION_TOL_M``),
  the concrete artefact of a loop that is welded but not carried on.

Missing face geometry is ``not_run`` and never a pass. The vertex-triangle distance is the exact
helper from ``twinqa.geometry.ucx_audit``; it is O(attachments x facade triangles) on the decor
check and O(vertices x edges) on the T-junction count, which is fine for a small work-FBX decor set.
"""
from __future__ import annotations

import math

from twinqa.geometry.ucx_audit import point_triangle_distance
from twinqa.report import Finding

DECOR_FLOAT_TOL_M = 1e-3  # a stand-off gap larger than 1 mm is floating, not embedded [D199]
TJUNCTION_TOL_M = 2e-5    # geometry.md: T-junctions (20 um) are a loop that ends mid-run [D200]

_FACADE_SUFFIX = "_Main"
_GLASS_SUFFIX = "_MainGlass"


def _f(status: str, name: str, observed: str, expected: str, src: str) -> Finding:
    return Finding(name, status, observed, expected, [], f"{src}; {name}")


def _is_ucx(name: str) -> bool:
    return name.upper().startswith("UCX_")


def _triangles(polygons):
    """Fan-triangulate each polygon index list; works for quads, triangles and n-gons."""
    out = []
    for poly in polygons:
        for i in range(1, len(poly) - 1):
            out.append((poly[0], poly[i], poly[i + 1]))
    return out


def _vertices(mesh) -> list:
    shape = mesh.get("face_geometry") or {}
    verts = shape.get("vertices")
    return verts if isinstance(verts, list) else []


def _polygons(mesh) -> list:
    shape = mesh.get("face_geometry") or {}
    polys = shape.get("polygons")
    return polys if isinstance(polys, list) else []


def _min_distance(a_mesh, b_mesh) -> float:
    """Minimum distance from every vertex of ``a_mesh`` to the surface of ``b_mesh`` (m)."""
    b_verts = _vertices(b_mesh)
    b_tris = _triangles(_polygons(b_mesh))
    if not b_tris:
        return math.inf
    best = math.inf
    for p in _vertices(a_mesh):
        if not (isinstance(p, (list, tuple)) and len(p) >= 3):
            return math.inf
        for ia, ib, ic in b_tris:
            try:
                d = point_triangle_distance(p, b_verts[ia], b_verts[ib], b_verts[ic])
            except (IndexError, TypeError):
                return math.inf
            if d < best:
                best = d
    return best


def decor_embed_findings(meshes: list[dict], src: str) -> list[Finding]:
    """Report floating decor/attachments (min gap to the facade > DECOR_FLOAT_TOL_M) [D199]."""
    expected = (f"decor/attachments embed into the facade, no floating stand-off "
                f"(gap <= {DECOR_FLOAT_TOL_M * 1000:g} mm) [D199]")
    render = [m for m in meshes if not _is_ucx(m["name"])]
    facade = [m for m in render if m["name"].endswith(_FACADE_SUFFIX)]
    attachments = [m for m in render
                   if not m["name"].endswith(_FACADE_SUFFIX) and not m["name"].endswith(_GLASS_SUFFIX)]
    if not facade:
        return [_f("not_run", "decor embed", f"{src}: no facade {_FACADE_SUFFIX} mesh", expected, src)]
    if not attachments:
        return [_f("pass", "decor embed", f"{src}: no attachment meshes", expected, src)]
    facade_mesh = facade[0]
    if not _vertices(facade_mesh) or not _polygons(facade_mesh):
        return [_f("not_run", "decor embed", f"{src}: facade has no face geometry", expected, src)]
    floating = []
    embedded = []
    for mesh in attachments:
        gap = _min_distance(mesh, facade_mesh)
        if not math.isfinite(gap):
            return [_f("not_run", "decor embed",
                       f"{src}: {mesh['name']} has no measurable face geometry", expected, src)]
        (floating if gap > DECOR_FLOAT_TOL_M else embedded).append((mesh["name"], gap))
    if floating:
        shown = ", ".join(f"{name} gap {gap * 1000:.2f} mm" for name, gap in sorted(floating))
        return [_f("review", "decor embed", f"{src}: floating attachment(s): {shown}", expected, src)]
    worst = min((gap for _, gap in embedded), default=0.0)
    return [_f("pass", "decor embed",
               f"{src}: {len(embedded)} attachment(s) embedded/touching, closest gap {worst * 1000:.2f} mm",
               expected, src)]


def _point_segment_distance(p, a, b) -> float:
    """Distance from point p to segment a-b (pure Python, no numpy)."""
    ax, ay, az = a
    bx, by, bz = b
    abx, aby, abz = bx - ax, by - ay, bz - az
    den = abx * abx + aby * aby + abz * abz
    if den < 1e-18:
        t = 0.0
    else:
        t = max(0.0, min(1.0, ((p[0] - ax) * abx + (p[1] - ay) * aby + (p[2] - az) * abz) / den))
    cx, cy, cz = ax + abx * t, ay + aby * t, az + abz * t
    return math.sqrt((p[0] - cx) ** 2 + (p[1] - cy) ** 2 + (p[2] - cz) ** 2)


def _point_distance(a, b) -> float:
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2)


def _edge_cell_size(vertices, edge_polys) -> float:
    """Spatial-hash cell size = the median edge length (at least 1 um), so each edge spans ~1 cell."""
    lengths = []
    for (a, b) in edge_polys:
        lengths.append(_point_distance(vertices[a], vertices[b]))
    if not lengths:
        return 1.0
    lengths.sort()
    return max(lengths[len(lengths) // 2], 1e-6)


def _t_junction_count(vertices, polygons, tol: float) -> int:
    """Number of vertices lying strictly on an edge of a *different* polygon (T-junctions).

    O(V + E) via a uniform spatial hash: each edge is bucketed into the grid cells its
    (tol-expanded) bounding box overlaps, and a vertex queries only its own cell. A vertex within
    ``tol`` of an edge is guaranteed to share a cell with it, so no candidate is missed. The cell
    size is the median edge length, so each edge lands in a handful of cells and each vertex tests
    a few edges instead of every edge in the mesh (the previous O(V*E) scan took ~115 s on a clean
    60x60 grid and would stall ``--master`` on a real work FBX).
    """
    edge_polys = {}   # (a, b) -> set of polygon indices containing that edge
    vert_polys = {}   # vertex -> set of polygon indices containing that vertex
    for pi, poly in enumerate(polygons):
        if not isinstance(poly, (list, tuple)) or len(poly) < 2:
            continue
        for i in range(len(poly)):
            a, b = poly[i], poly[(i + 1) % len(poly)]
            edge_polys.setdefault((min(a, b), max(a, b)), set()).add(pi)
        for v in poly:
            vert_polys.setdefault(v, set()).add(pi)

    cell = _edge_cell_size(vertices, edge_polys)
    grid = {}
    for (a, b) in edge_polys:
        va, vb = vertices[a], vertices[b]
        lo = [min(va[i], vb[i]) - tol for i in range(3)]
        hi = [max(va[i], vb[i]) + tol for i in range(3)]
        k0 = (int(math.floor(lo[0] / cell)), int(math.floor(lo[1] / cell)), int(math.floor(lo[2] / cell)))
        k1 = (int(math.floor(hi[0] / cell)), int(math.floor(hi[1] / cell)), int(math.floor(hi[2] / cell)))
        for ix in range(k0[0], k1[0] + 1):
            for iy in range(k0[1], k1[1] + 1):
                for iz in range(k0[2], k1[2] + 1):
                    grid.setdefault((ix, iy, iz), []).append((a, b))

    count = 0
    for v_idx, p in enumerate(vertices):
        if not (isinstance(p, (list, tuple)) and len(p) >= 3) or v_idx not in vert_polys:
            continue
        key = (int(math.floor(p[0] / cell)), int(math.floor(p[1] / cell)), int(math.floor(p[2] / cell)))
        for (a, b) in grid.get(key, ()):
            if v_idx == a or v_idx == b:
                continue
            if vert_polys[v_idx] & edge_polys[(a, b)]:
                continue  # same polygon: a collinear corner, not a T-junction
            va, vb = vertices[a], vertices[b]
            if _point_distance(p, va) < tol or _point_distance(p, vb) < tol:
                continue  # coincident with an endpoint = a welded corner, not a T-junction
            if _point_segment_distance(p, va, vb) < tol:
                count += 1
    return count


def edge_loop_findings(meshes: list[dict], src: str) -> list[Finding]:
    """Count T-junctions (edge loops that end mid-run) on the work FBX [D200]."""
    expected = f"edge loops continue through the mesh, no T-junctions ({TJUNCTION_TOL_M * 1e6:g} um) [D200]"
    render = [m for m in meshes if not _is_ucx(m["name"])]
    if not render:
        return [_f("not_run", "edge loop continuity", f"{src}: no render mesh", expected, src)]
    missing = [m["name"] for m in render if not _vertices(m) or not _polygons(m)]
    if len(missing) == len(render):
        return [_f("not_run", "edge loop continuity", f"{src}: no face geometry", expected, src)]
    total = 0
    per_mesh = []
    for mesh in render:
        verts, polys = _vertices(mesh), _polygons(mesh)
        if not verts or not polys:
            continue
        n = _t_junction_count(verts, polys, TJUNCTION_TOL_M)
        total += n
        if n:
            per_mesh.append(f"{mesh['name']}={n}")
    if missing:
        shown = f"; unmeasured: {', '.join(missing[:5])}"
        return [_f("review" if total else "not_run", "edge loop continuity",
                   f"{src}: {total} T-junction(s) {per_mesh[:5] or ''}{shown}", expected, src)]
    if total:
        return [_f("review", "edge loop continuity",
                   f"{src}: {total} T-junction(s): {', '.join(per_mesh[:5])}", expected, src)]
    return [_f("pass", "edge loop continuity", f"{src}: no T-junctions", expected, src)]
