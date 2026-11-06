"""new-case: TEC26 AC08 #1016 - apply AGR Tools ucx.triangulate to a delivered VPM copy; SINTEZ before/after table.

Pure stdlib, importable from Blender and from pytest.
* `triangulate_piece` runs the AGR Tools ucx.triangulate core (`adapters/max/agr_tools/geom_core.py::ucx_plan`,
  nonconvex='report', 0.1 mm convexity tolerance) on one UCX piece and returns its triangle list. It fails closed:
  an empty, non-finite, open or still non-convex piece raises ValueError naming the piece; it never falls back to a
  hull or to the source faces.
* `check_paths` refuses an output that already exists, aliases an input or lies inside a protected (accepted) folder.
* `summarize` / `diff_failed` turn the run_agr_checker.py dump (agr_check.json) into the counts and the failed-item
  table used in PILOT_REPORT (verified / failed / undefined per hp = VPM and lp = NPM).
"""
from __future__ import annotations

import importlib.util
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
GEOM_CORE = os.path.join(ROOT, "adapters", "max", "agr_tools", "geom_core.py")
STATES = ("verified", "failed", "undefined")


def geom_core():
    name = "agr_tools_geom_core"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, GEOM_CORE)
    assert spec is not None and spec.loader is not None, GEOM_CORE
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def degrees(polygons) -> dict:
    """{corner count: polygon count} of a polygon list."""
    out = {}
    for p in polygons:
        out[len(p)] = out.get(len(p), 0) + 1
    return dict(sorted(out.items()))


def triangulate_piece(name: str, points, polygons) -> dict:
    """ucx.triangulate on one piece -> {'name', 'action', 'tris', 'before', 'after', 'convex', 'closed', 'flips'}.

    Raises ValueError (naming the piece) for no faces, a polygon with < 3 corners or an index out of range,
    non-finite coordinates, or a result that is not closed and convex within geom_core.CONVEX_TOL_M."""
    gc = geom_core()
    points = [tuple(float(c) for c in p) for p in points]
    polygons = [[int(v) for v in p] for p in polygons]
    if not points or not polygons:
        raise ValueError(f"{name}: UCX piece without vertices or faces")
    for p in points:
        if len(p) != 3 or not all(math.isfinite(c) for c in p):
            raise ValueError(f"{name}: non-finite or malformed vertex {p}")
    for poly in polygons:
        if len(poly) < 3 or any(v < 0 or v >= len(points) for v in poly):
            raise ValueError(f"{name}: bad polygon {poly}")
    try:
        plan = gc.ucx_plan(points, polygons, gc.CONVEX_TOL_M, nonconvex="report")
    except ValueError as exc:
        raise ValueError(f"{name}: {exc}") from exc
    tris = [tuple(t) for t in plan["tris"]] if plan["action"] in ("diagonals", "mesh") else \
        [tuple(p) for p in polygons]
    post = gc._ucx_core().convexity(points, tris, gc.CONVEX_TOL_M)
    if not plan["convex"] or not post.get("ok"):
        raise ValueError(f"{name}: not a closed convex piece after ucx.triangulate: {plan['reason']} {post}")
    if any(len(t) != 3 for t in tris):
        raise ValueError(f"{name}: n-gon left after ucx.triangulate")
    return {"name": name, "action": plan["action"], "tris": [list(t) for t in tris],
            "before": degrees(polygons), "after": degrees(tris), "vertices": len(points),
            "convex": bool(post.get("convex", plan["convex"])), "closed": bool(post.get("closed", True)),
            "flips": len(plan["flips"])}


def _real(p: str) -> str:
    return os.path.normcase(os.path.realpath(os.path.abspath(p)))


def check_paths(inputs, out_dir: str, protected) -> None:
    """Refuse (ValueError) an existing output, an output equal to / inside / containing an input, or an output
    inside a protected folder (the accepted pilot-v010 delivery)."""
    out = _real(out_dir)
    if os.path.lexists(out_dir):
        raise ValueError(f"output exists: {out_dir}")
    for p in list(inputs) + list(protected):
        r = _real(p)
        if out == r or out.startswith(r + os.sep) or r.startswith(out + os.sep):
            raise ValueError(f"output {out_dir} aliases {p}")


def summarize(agr_check: dict) -> dict:
    """run_agr_checker.py dump -> {'hp'|'lp': {state: count}, 'failed': {'hp'|'lp': [{'req','name','errors'}]}}.

    A checker error, a missing profile list or an unknown item state raises ValueError (never a pass)."""
    if agr_check.get("error"):
        raise ValueError(f"checker error: {str(agr_check['error'])[:200]}")
    out = {"failed": {}}
    for side in ("hp", "lp"):
        items = agr_check.get(side)
        if not items:
            raise ValueError(f"checker dump without {side} items")
        counts = dict.fromkeys(STATES, 0)
        for it in items:
            if it.get("state") not in counts:
                raise ValueError(f"{side} {it.get('req_num')}: unknown state {it.get('state')!r}")
            counts[it["state"]] += 1
        out[side] = counts
        out["failed"][side] = [{"req": it["req_num"], "name": it["name"], "errors": it["errors"]}
                               for it in items if it["state"] == "failed"]
    return out


def diff_failed(before: dict, after: dict) -> list[dict]:
    """Rows {'side', 'req', 'before', 'after', 'errors_after'} for every item failed in either summary."""
    rows = []
    for side in ("hp", "lp"):
        b = {f["req"]: f for f in before["failed"][side]}
        a = {f["req"]: f for f in after["failed"][side]}
        for req in sorted(set(b) | set(a), key=lambda r: [int(x) for x in r.split(".") if x.isdigit()]):
            rows.append({"side": side, "req": req, "name": (a.get(req) or b[req])["name"],
                         "before": "failed" if req in b else "not failed",
                         "after": "failed" if req in a else "not failed",
                         "errors_after": a[req]["errors"].strip() if req in a else ""})
    return rows


def table_md(before: dict, after: dict) -> str:
    lines = ["| profile | item | name | pilot-v010 | ucx-tri | errors after |", "|---|---|---|---|---|---|"]
    for r in diff_failed(before, after):
        side = "VPM" if r["side"] == "hp" else "NPM"
        err = " ".join(r["errors_after"].split())[:120]
        lines.append(f"| {side} | {r['req']} | {r['name']} | {r['before']} | {r['after']} | {err} |")
    for side, label in (("hp", "VPM"), ("lp", "NPM")):
        cb, ca = before[side], after[side]
        lines.append(f"| {label} | total | verified/failed/undefined | {cb['verified']}/{cb['failed']}/"
                     f"{cb['undefined']} | {ca['verified']}/{ca['failed']}/{ca['undefined']} | |")
    return "\n".join(lines)


if __name__ == "__main__":  # python ucx_tri_core.py <before agr_check.json> <after agr_check.json> <out.json>
    import json
    b_path, a_path, out_path = sys.argv[1:4]
    if os.path.lexists(out_path) or _real(out_path) in (_real(b_path), _real(a_path)):
        sys.exit(f"refused: output exists or aliases an input: {out_path}")
    before = summarize(json.load(open(b_path, encoding="utf-8")))
    after = summarize(json.load(open(a_path, encoding="utf-8")))
    res = {"before": before, "after": after, "rows": diff_failed(before, after)}
    with open(out_path, "x", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=1)
    print(table_md(before, after))
