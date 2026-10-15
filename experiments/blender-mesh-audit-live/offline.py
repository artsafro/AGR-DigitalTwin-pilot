"""Fixtures + offline side of the mesh_audit live-vs-offline experiment (SYNTHETIC defects).

    uv run python experiments/blender-mesh-audit-live/offline.py fixtures <out dir>
    uv run python experiments/blender-mesh-audit-live/offline.py audit <out dir>

`fixtures` builds the engine (from_spec) `body` mesh of B01/B02/B02t and 4 defect copies each:
  flip1   - one facade quad reversed
  del1    - one facade quad deleted
  dup05   - one corner of a facade quad re-pointed to a new vertex 0.5 mm off (+X)
  bowtie  - one extra self-intersecting quad (4 new vertices, order a-b-d-c) 0.3 m in front of a wall
`audit` runs, offline, (1) technical_library/mesh_audit/core.inspect_mesh on the fixture arrays,
(2) the same core on faces re-indexed from tools/blender/export_faces.py style output written by Blender
(<stem>__faces.json; points only, welded by exact coordinates), (3) the pure-Python `extra_checks`
port of the bmesh checks. Median of 5 runs each. Writes offline.json.
"""
import json
import math
import statistics
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "technical_library" / "mesh_audit"))
from core import inspect_mesh  # noqa: E402

BENCHES = ["bench-b01-box", "bench-b02-corner-niche", "bench-b02t-terrace"]
DEFECTS = ["clean", "flip1", "del1", "dup05", "bowtie"]


def _sub(a, b):
    return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]


def _cross(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def _wall(v, polys):
    """Index of the largest vertical quad (a facade wall)."""
    best = None
    for i, p in enumerate(polys):
        n = _cross(_sub(v[p[1]], v[p[0]]), _sub(v[p[2]], v[p[0]]))
        a = math.sqrt(sum(c * c for c in n))
        if a > 0 and abs(n[2]) / a < 1e-6 and (best is None or a > best[0]):
            best = (a, i, n)
    return best[1], best[2]


def variants(v, polys):
    wi, n = _wall(v, polys)
    out = {"clean": (v, polys)}
    p = [list(q) for q in polys]
    p[wi] = p[wi][::-1]
    out["flip1"] = (v, p)
    out["del1"] = (v, [q for i, q in enumerate(polys) if i != wi])
    vv = [list(x) for x in v]
    p = [list(q) for q in polys]
    src = p[wi][0]
    vv.append([v[src][0] + 0.0005, v[src][1], v[src][2]])
    p[wi][0] = len(vv) - 1
    out["dup05"] = (vv, p)
    c = [sum(v[i][k] for i in polys[wi]) / len(polys[wi]) for k in range(3)]
    ln = math.sqrt(sum(x * x for x in n))
    off = [c[k] + 0.3 * n[k] / ln for k in range(3)]
    u = [-n[1] / ln, n[0] / ln, 0.0]  # horizontal in-wall axis
    a = [off[k] - 0.2 * u[k] for k in range(3)]
    b = [off[k] + 0.2 * u[k] for k in range(3)]
    q = [list(x) for x in v] + [a, b, [a[0], a[1], a[2] + 0.4], [b[0], b[1], b[2] + 0.4]]
    m = len(v)
    out["bowtie"] = (q, [list(x) for x in polys] + [[m, m + 1, m + 2, m + 3]])  # a, b, a+z, b+z: edges cross
    return out


def extra_checks(v, polys, near_m=0.001):
    """Pure-Python port of the bmesh checks run live (see live.py)."""
    loops = defaultdict(list)
    for p in polys:
        for a, b in zip(p, p[1:] + p[:1]):
            loops[(min(a, b), max(a, b))].append(a)  # start vertex of the loop on that edge
    inconsistent = sum(len(s) == 2 and s[0] == s[1] for s in loops.values())
    non_manifold = sum(len(s) != 2 for s in loops.values())
    used = {i for p in polys for i in p}
    # near duplicates: grid hash at near_m, compare neighbour cells
    cell = defaultdict(list)
    for i, x in enumerate(v):
        cell[tuple(int(math.floor(c / near_m)) for c in x)].append(i)
    near = set()
    for key, ids in cell.items():
        for d in [(dx, dy, dz) for dx in (-1, 0, 1) for dy in (-1, 0, 1) for dz in (-1, 0, 1)]:
            for j in cell.get((key[0] + d[0], key[1] + d[1], key[2] + d[2]), ()):
                for i in ids:
                    if i < j and sum((v[i][k] - v[j][k]) ** 2 for k in range(3)) <= near_m ** 2:
                        near.add(j)
    # self-intersecting polygon: two fan triangles with opposite normals (bowtie)
    bow = 0
    for p in polys:
        tn = [_cross(_sub(v[p[k]], v[p[0]]), _sub(v[p[k + 1]], v[p[0]])) for k in range(1, len(p) - 1)]
        if any(sum(a[i] * b[i] for i in range(3)) < 0 for a in tn for b in tn):
            bow += 1
    return {"inconsistent_edges": inconsistent, "non_manifold_edges": non_manifold,
            "near_dup_verts_1mm": len(near), "loose_verts": len(v) - len(used), "bowtie_faces": bow}


def weld(faces):
    """export_faces output (points only) -> indexed arrays, exact-coordinate weld."""
    index, verts, polys = {}, [], []
    for f in faces:
        p = []
        for pt in f["points"]:
            k = tuple(pt)
            if k not in index:
                index[k] = len(verts)
                verts.append(list(pt))
            p.append(index[k])
        polys.append(p)
    return verts, polys


def med(fn, n=5):
    ts = []
    for _ in range(n):
        t = time.perf_counter()
        r = fn()
        ts.append((time.perf_counter() - t) * 1000)
    return r, round(statistics.median(ts), 2)


def build_fixtures(out):
    from dt_ai.geometry.from_spec import BuildInputs, build
    from dt_ai.spec.model import Spec
    out.mkdir(parents=True, exist_ok=True)
    for bench in BENCHES:
        d = ROOT / "benchmark" / bench
        spec = Spec.model_validate(json.loads((d / "spec.json").read_text(encoding="utf-8")))
        obj = json.loads((d / "object.json").read_text(encoding="utf-8"))
        body = build(spec, BuildInputs.from_object(obj))["meshes"][0]
        for name, (v, p) in variants(body["vertices"], body["polygons"]).items():
            (out / f"{bench}__{name}.json").write_text(json.dumps({"vertices": v, "polygons": p}),
                                                       encoding="utf-8")
            print(bench, name, len(v), len(p))


def audit(out):
    rows = {}
    for bench in BENCHES:
        for name in DEFECTS:
            stem = f"{bench}__{name}"
            fx = json.loads((out / f"{stem}.json").read_text(encoding="utf-8"))
            v, p = fx["vertices"], fx["polygons"]
            core, t_core = med(lambda: inspect_mesh(v, p))
            extra, t_extra = med(lambda: extra_checks(v, p))
            row = {"core": core, "core_ms": t_core, "extra": extra, "extra_ms": t_extra}
            fp = out / f"{stem}__faces.json"
            if fp.exists():
                faces = json.loads(fp.read_text(encoding="utf-8"))
                (wv, wp), t_weld = med(lambda: weld(faces))
                row["exported"] = inspect_mesh(wv, wp)
                row["exported_extra"] = extra_checks(wv, wp)
                row["weld_ms"] = t_weld
            rows[stem] = row
    (out / "offline.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    print("rows", len(rows))


if __name__ == "__main__":
    {"fixtures": build_fixtures, "audit": audit}[sys.argv[1]](Path(sys.argv[2]))
