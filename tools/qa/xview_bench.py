"""Frozen benchmark for the xView-exact overlap check (#553 autoresearch): parity with stored 3ds Max xView lists + CPU time.

  uv run python tools/qa/xview_bench.py --candidate baseline|<module> [--reps 5] [--out result.json]

A candidate is `baseline` (the current `dt_ai.ops.inv_xview.part_report`) or an importable module with
`xview_lists(vertices: ndarray (n, 3) float, faces: tuple[tuple[int, ...]], tol: XviewTolerance) -> dict` returning
1-based sorted tuples `xview_faces` (xView Overlapping Faces selection), `vertices` (xView Overlapping Vertices
selection) and `vertex_pairs` ((a, b, d) with a < b).

Fixtures (all must match exactly; the oracle is the stored xView list, never a previous candidate output):
- tow02_v005  TOW02 export-v005 (35 407 polys) vs `xview/ours_v005.keep`: 185 faces / 0 vertices.
- tow02_user05 the user's TOW02 `_05` node 013 (73 594 tris) vs `xview/user_fbx05.keep`: 0 faces / 10 vertices.
- ground_v014_npm, ground_v014_npm_poly  Ground v014 headless-Max dumps (`docs/research/xview-parity-ground-v014.md`):
  146 faces / 0 vertices and 351 faces / 118 vertices.
- synthetic edge cases of `docs/domain/validation.md` with hand-derived lists: boundary contact counted, normal limit
  at 0.81 deg (flagged) / 0.815 deg (not), face distance exactly 5 mm (flagged) / 5.1 mm (not), vertex distance exactly
  2 mm (flagged, kernel fail-closed policy) / 2.1 mm (not).

Metric: `cpu_s` = median of `--reps` `time.process_time()` runs of the candidate on tow02_v005 (single process);
`wall_s` = median `time.perf_counter()` for information. Data root: `--data` or env `XVIEW_BENCH_DATA`
(default the primary checkout's git-ignored outputs on this PC); SHA-256 of every input is printed.
Vertex pairs are checked as a full list against `oracle_pairs` (an independent sort-and-sweep derivation of the rule,
which must reproduce the stored xView vertex selection, else exit 2): exact ids and order, each distance equal to the
geometry within 1e-12 m and within the tolerance. Mesh inventories are strict (integer arrays, contiguous spans that
cover every loop record); xView ids must be unique integers in range.
Exit 0: every fixture equal; 1: a parity mismatch or a candidate error; 2: missing / malformed input, an input that
changed during the run, or `--out` that is an input or the bench itself (checked before anything is written).
Pattern: none | new-case: frozen parity + CPU benchmark for the xView-exact overlap check (#553).
"""
import argparse
import hashlib
import importlib
import json
import os
import statistics
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dt_ai.ops.inv_xview import XviewTolerance, part_report  # noqa: E402
from dt_ai.ops.inv_quads import PolyMesh  # noqa: E402

DEFAULT_DATA = "C:/Users/artsafro/.AGR-DigitalTwin_pilot"
TOW = "jobs/vyatskaya-tow02/outputs/review-v002"
GROUND = "C:/Users/artsafro/AppData/Local/Temp/agr-max-t_3013550d"


class BenchError(Exception):
    pass


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def baseline_lists(vertices, faces, tol):
    r = part_report("bench", PolyMesh(np.asarray(vertices, float), tuple(tuple(f) for f in faces)), tol)
    return {"xview_faces": r.xview_faces, "vertices": r.vertices,
            "vertex_pairs": tuple((a, b, d) for a, b, d in r.vertex_pairs)}


def _int_array(z, key: str, p: Path) -> np.ndarray:
    a = z[key]
    if a.ndim != 1 or a.dtype == bool or not np.issubdtype(a.dtype, np.integer):
        raise BenchError(f"{p.name}: {key} must be a 1-D integer array, got {a.dtype} {a.shape}")
    return a.astype(np.int64)


def load_npz(p: Path):
    """Strict mesh inventory: integer corner/start/total arrays, contiguous spans covering every loop record."""
    with np.load(p, allow_pickle=False) as z:
        for k in ("vertices", "loop_vert", "loop_start", "loop_total"):
            if k not in z.files:
                raise BenchError(f"{p.name}: missing array {k}")
        v = z["vertices"]
        lv, st, tot = (_int_array(z, k, p) for k in ("loop_vert", "loop_start", "loop_total"))
    if v.ndim != 2 or v.shape[1] != 3 or not np.issubdtype(v.dtype, np.floating) or not np.isfinite(v).all():
        raise BenchError(f"{p.name}: vertices must be a finite float (n, 3) array, got {v.dtype} {v.shape}")
    if len(st) != len(tot) or not len(st):
        raise BenchError(f"{p.name}: loop_start ({len(st)}) / loop_total ({len(tot)}) lengths differ or are empty")
    if (tot < 3).any():
        raise BenchError(f"{p.name}: polygon {int(np.argmax(tot < 3))} has fewer than 3 corners")
    expect = np.concatenate(([0], np.cumsum(tot)[:-1]))
    if (st != expect).any():
        i = int(np.argmax(st != expect))
        raise BenchError(f"{p.name}: loop_start[{i}]={int(st[i])} is not contiguous (expected {int(expect[i])})")
    if int(tot.sum()) != len(lv):
        raise BenchError(f"{p.name}: spans cover {int(tot.sum())} of {len(lv)} loop records")
    if len(lv) and (lv.min() < 0 or lv.max() >= len(v)):
        raise BenchError(f"{p.name}: loop_vert index out of range 0..{len(v) - 1}")
    lv = lv.tolist()
    return np.asarray(v, float), tuple(tuple(lv[s:s + t]) for s, t in zip(st.tolist(), tot.tolist()))


def _is_int(x) -> bool:
    return isinstance(x, (int, np.integer)) and not isinstance(x, (bool, np.bool_))


def _ids(items, n: int, what: str, p: Path) -> tuple:
    ids = [i[0] if isinstance(i, list) and i else i for i in items]
    if not all(_is_int(i) and 1 <= i <= n for i in ids) or len(set(ids)) != len(ids):
        raise BenchError(f"{p.name}: {what} ids must be unique integers in 1..{n}")
    return tuple(sorted(int(i) for i in ids))


def load_keep(p: Path, nv: int, nf: int):
    d = json.loads(p.read_bytes().decode("cp1251"))
    if d.get("verts") != nv or d.get("faces") != nf:
        raise BenchError(f"{p.name}: keep counts {d.get('verts')}/{d.get('faces')} != mesh {nv}/{nf}")
    vc, fc = d["verticesCheck"], d["facesCheck"]
    if vc.get("type") != "vertices" or fc.get("type") != "faces" or vc["count"] != len(vc["items"]) \
            or fc["count"] != len(fc["items"]):
        raise BenchError(f"{p.name}: partial or failed xView result")
    tol = XviewTolerance(vertex_m=float(d["tolVerts"]), face_m=float(d["tolFaces"])).validate()
    return _ids(fc["items"], nf, "face", p), _ids(vc["items"], nv, "vertex", p), tol


def load_dump(p: Path):
    import xview_parity
    d = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(d.get("nodes"), list) or len(d["nodes"]) != 1:
        raise BenchError(f"{p.name}: expected one node")
    m = xview_parity._num(d, "m_per_unit")
    tol = XviewTolerance(vertex_m=xview_parity._num(d, "tol_v_units") * m,
                         face_m=xview_parity._num(d, "tol_f_units") * m).validate()
    mesh, mv, mf = xview_parity._node(d["nodes"][0])
    return mesh.vertices, mesh.faces, tuple(sorted(mf)), tuple(sorted(mv)), tol


def _quad(x0=0.0, y0=0.0, s=1.0, z=0.0):
    return [(x0, y0, z), (x0 + s, y0, z), (x0 + s, y0 + s, z), (x0, y0 + s, z)], [(0, 1, 2, 3)]


def _join(*parts):
    v, f = [], []
    for pv, pf in parts:
        f += [tuple(i + len(v) for i in t) for t in pf]
        v += list(pv)
    return np.asarray(v, float), tuple(f)


def _tilted(th_deg):
    t = np.tan(np.radians(th_deg)) * 2.5
    return _join(_quad(0, 0, 4), ([(0.5, 0.5, 0.001), (3, 0.5, 0.001 + t), (3, 1.5, 0.001 + t)], [(0, 1, 2)]))


def synthetic():
    """(name, vertices, faces, expected xview_faces, expected vertices); lists derived by hand from the rule."""
    tol = XviewTolerance()
    t_vertex = _join(_quad(), ([(1.0, 0.25, 0.0), (2.0, 0.25, 0.0), (2.0, 0.75, 0.0)], [(0, 1, 2)]))
    return [
        ("syn_boundary_contact", *t_vertex, (1, 2), (), tol),           # vertex exactly on the other's edge
        ("syn_normal_0.810deg", *_tilted(0.810), (1, 2), (), tol),
        ("syn_normal_0.815deg", *_tilted(0.815), (), (), tol),
        ("syn_face_5.000mm", *_join(_quad(), _quad(0.25, 0.25, 0.5, z=0.005)), (1, 2), (), tol),
        ("syn_face_5.100mm", *_join(_quad(), _quad(0.25, 0.25, 0.5, z=0.0051)), (), (), tol),
        ("syn_vertex_2.000mm", np.array([(0, 0, 0), (1, 0, 0), (0, 1, 0), (0.002, 0, 0), (1, 0, 1), (0, 1, 1.0)]),
         ((0, 1, 2), (3, 4, 5)), (), (1, 4), tol),
        ("syn_vertex_2.100mm", np.array([(0, 0, 0), (1, 0, 0), (0, 1, 0), (0.0021, 0, 0), (1, 0, 1), (0, 1, 1.0)]),
         ((0, 1, 2), (3, 4, 5)), (), (), tol),
    ]


def fixtures(root: Path, ground: Path):
    raw, xv = root / TOW / "xcheck/raw", root / TOW / "xview"
    inputs, out = [], []
    for name, arr, keep in (("tow02_v005", "arrays_ours.npz", "ours_v005.keep"),
                            ("tow02_user05", "arrays_user_inplace.npz", "user_fbx05.keep")):
        pa, pk = raw / arr, xv / keep
        for p in (pa, pk):
            if not p.is_file():
                raise BenchError(f"missing input {p}")
        v, f = load_npz(pa)
        of, ov, tol = load_keep(pk, len(v), len(f))
        out.append((name, v, f, of, ov, tol))
        inputs += [pa, pk]
    for name, dump in (("ground_v014_npm", "npm_xview.json"), ("ground_v014_npm_poly", "npm_poly_xview.json")):
        p = ground / dump
        if not p.is_file():
            raise BenchError(f"missing input {p}")
        out.append((name, *load_dump(p)))
        inputs.append(p)
    return out + synthetic(), inputs


def _aliases(out: Path, paths) -> bool:
    """`out` is one of `paths` (same resolved path, symlink or hardlink)."""
    ro = out.resolve()
    for p in paths:
        if ro == p.resolve() or (out.exists() and p.exists() and os.path.samefile(out, p)):
            return True
    return False


def run(fn, v, f, tol):
    c0, w0 = time.process_time(), time.perf_counter()
    r = fn(v, f, tol)
    return r, time.process_time() - c0, time.perf_counter() - w0


def oracle_pairs(v: np.ndarray, r: float) -> tuple:
    """Expected vertex pairs, derived independently of every candidate: sort-and-sweep on the widest axis, then the
    rule itself (two distinct indices at |v[a] - v[b]| <= r). 1-based (a, b) with a < b, lexicographic order."""
    v = np.asarray(v, float)
    n = len(v)
    if n < 2:
        return ()
    ax = int(np.argmax(np.ptp(v, axis=0)))
    order = np.argsort(v[:, ax], kind="stable")
    x = v[order, ax]
    hi = np.searchsorted(x, x + r, "right")
    cnt = hi - np.arange(n) - 1
    out = []
    for s in range(0, n, 4096):                     # bounded memory per block
        c = cnt[s:s + 4096]
        if not c.sum():
            continue
        i = np.repeat(np.arange(s, s + len(c)), c)
        j = i + 1 + (np.arange(c.sum()) - np.repeat(np.cumsum(c) - c, c))
        a, b = order[i], order[j]
        keep = np.linalg.norm(v[a] - v[b], axis=1) <= r
        out += list(zip(np.minimum(a, b)[keep].tolist(), np.maximum(a, b)[keep].tolist()))
    return tuple(sorted((a + 1, b + 1) for a, b in out))


def _pair_errors(vp, op, v, vertex_m) -> list:
    """Schema, id range, distance and exact identity of the candidate's vertex pairs against `op`."""
    if op is None or v is None or vertex_m is None:
        return ["no independent pair oracle"]
    v = np.asarray(v, float)
    err, ids = [], []
    for k, p in enumerate(vp):
        if not isinstance(p, (tuple, list)) or len(p) != 3 or not _is_int(p[0]) or not _is_int(p[1]) \
                or isinstance(p[2], (bool, np.bool_)) or not isinstance(p[2], (int, float, np.integer, np.floating)):
            err.append(f"pair {k}: not (int a, int b, float d): {p!r}"[:120])
            continue
        a, b, d = int(p[0]), int(p[1]), float(p[2])
        if not 1 <= a < b <= len(v):
            err.append(f"pair {k}: ids ({a}, {b}) not 1 <= a < b <= {len(v)}")
            continue
        true = float(np.linalg.norm(v[a - 1] - v[b - 1]))
        if not np.isfinite(d) or abs(d - true) > 1e-12 or true > vertex_m:
            err.append(f"pair {k}: ({a}, {b}) distance {d!r}, geometry {true!r}, limit {vertex_m}")
        ids.append((a, b))
    if tuple(ids) != tuple(op):
        err.append(f"pairs differ from the oracle: only candidate {sorted(set(ids) - set(op))[:10]}, "
                   f"only oracle {sorted(set(op) - set(ids))[:10]}, {len(ids)} vs {len(op)}")
    return err


def check(r, of, ov, op=None, v=None, vertex_m=None) -> dict:
    """Exact face list, vertex list and pair list (`op` = independent oracle pairs) parity; anything else fails."""
    xf, vs, vp = tuple(r["xview_faces"]), tuple(r["vertices"]), tuple(r["vertex_pairs"])
    typed = all(_is_int(x) for x in xf + vs)
    pe = _pair_errors(vp, op, v, vertex_m)
    return {"faces": len(xf), "oracle_faces": len(of), "vertices": len(vs), "oracle_vertices": len(ov),
            "vertex_pairs": len(vp), "oracle_pairs": None if op is None else len(op),
            "faces_only_candidate": sorted(set(xf) - set(of))[:20],
            "faces_only_oracle": sorted(set(of) - set(xf))[:20],
            "vertices_only_candidate": sorted(set(vs) - set(ov))[:20],
            "vertices_only_oracle": sorted(set(ov) - set(vs))[:20], "pair_errors": pe[:5],
            "equal": typed and xf == of and vs == ov and not pe}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidate", required=True)
    ap.add_argument("--reps", type=int, default=5)
    ap.add_argument("--data", default=os.environ.get("XVIEW_BENCH_DATA", DEFAULT_DATA))
    ap.add_argument("--ground", default=os.environ.get("XVIEW_BENCH_GROUND", GROUND))
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    if a.reps < 1:
        print("--reps must be >= 1", file=sys.stderr)
        return 2
    try:
        fx, inputs = fixtures(Path(a.data), Path(a.ground))
        before = {p.name: sha(p) for p in inputs}
        pairs = {}
        for name, v, _f, _of, ov, tol in fx:
            pairs[name] = oracle_pairs(v, tol.vertex_m)
            if tuple(sorted({i for p in pairs[name] for i in p})) != ov:
                raise BenchError(f"{name}: pairs derived from the rule do not reproduce the xView vertex selection")
        if a.out and _aliases(Path(a.out), inputs + [Path(__file__)]):
            raise BenchError(f"--out {a.out} is an input or the bench itself")
    except (BenchError, OSError, ValueError, KeyError) as e:
        print(f"bench input error: {e}", file=sys.stderr)
        return 2
    fn = baseline_lists if a.candidate == "baseline" else importlib.import_module(a.candidate).xview_lists
    res = {"candidate": a.candidate, "bench_sha256": sha(Path(__file__)),
           "inputs": before, "fixtures": {}}
    ok = True
    for name, v, f, of, ov, tol in fx:
        reps = a.reps if name == "tow02_v005" else 1
        cpu, wall, rows = [], [], None
        try:
            for _ in range(reps):
                r, c, w = run(fn, v, f, tol)
                row = check(r, of, ov, pairs[name], v, tol.vertex_m)
                if rows is not None and row != rows:
                    row["equal"] = False                      # a nondeterministic candidate never passes
                rows = row
                cpu.append(c)
                wall.append(w)
        except Exception as e:  # noqa: BLE001 - a crashing candidate is a failed fixture, never a pass
            rows = {"equal": False, "error": f"{type(e).__name__}: {e}"}
        rows.update({"cpu_s": round(statistics.median(cpu), 3) if cpu else None,
                     "wall_s": round(statistics.median(wall), 3) if wall else None, "reps": len(cpu)})
        ok &= rows["equal"]
        res["fixtures"][name] = rows
        print(name, json.dumps({k: x for k, x in rows.items() if x not in ([],)}), flush=True)
    if {p.name: sha(p) for p in inputs} != before:
        print("bench input error: an input changed during the run", file=sys.stderr)
        return 2
    t = res["fixtures"]["tow02_v005"]
    res.update({"parity": ok, "cpu_s": t["cpu_s"], "wall_s": t["wall_s"]})
    print(f"METRIC cpu_s={t['cpu_s']} wall_s={t['wall_s']} parity={'PASS' if ok else 'FAIL'}")
    if a.out:
        Path(a.out).write_text(json.dumps(res, indent=1), encoding="utf-8")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
