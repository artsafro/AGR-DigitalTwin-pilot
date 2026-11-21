"""NPM -> VPM placement readback: every placed MAF / Flora instance sits at its accepted NPM position minus the
package pivot (#1731, [D018] VPM pivot, [D329] placement owner = ``dt_ai.placement``).

Pattern: none (new-case: pure position gate between the accepted NPM placement and the VPM assembly scene, run
before the VPM export; the Blender reader is ``tools/blender/vpm_placement_readback.py``).

Incident (Staropetrovskiy VPM v001, 2026-11-20): after appending the MAF library in Blender the assembly read a
stale ``matrix_world`` (identity until the depsgraph update) and subtracted the pivot a second time; every MAF
stood one pivot (17.6 km) off. Nothing compared the VPM positions with the NPM placement.

Contract (pure Python, no DCC):
- ``npm``: ``{handle: [x, y, z]}`` accepted NPM world positions (project coordinates, m);
- ``scene``: ``{handle: [x, y, z]}`` VPM world positions READ AFTER ``view_layer.update()`` (labelled mode,
  ``check``) or an unlabelled list of scene points, e.g. loose-part centres of a joined mesh (``check_points``);
- expected VPM position = NPM position - pivot; an instance passes when its deviation is STRICTLY below
  ``tol_m`` (default ``TOL_M`` = 1 cm; exactly at the tolerance fails).
Fail-closed: empty NPM input, a non-finite / non-numeric coordinate, a bad pivot or tolerance, a duplicate
handle, a handle missing from the scene or an extra labelled scene handle all give ``status: fail`` with the
reason. Every NPM handle ends either in ``ok`` or in ``offenders`` with its diagnosis
(``pivot subtracted twice`` / ``pivot not subtracted`` / ``off`` / ``missing in scene``). Rotation is out of scope.
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Any, Iterable, Mapping

SCHEMA = "vpm_placement_readback/1"
TOL_M = 0.01


class PlacementReadbackFailed(RuntimeError):
    """Raised by ``require_pass``: the VPM scene does not equal the NPM placement minus the pivot."""

    def __init__(self, report: dict):
        self.report = report
        lines = [f"{o['handle']}: {o['diagnosis']} (dev {o['dev_m']})" for o in report.get("offenders", [])]
        super().__init__("VPM placement readback failed: " + "; ".join(report.get("errors", []) + lines[:20]))


def _num(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _vec(v: Any) -> list[float] | None:
    if isinstance(v, (str, bytes)) or not hasattr(v, "__len__") or len(v) != 3 or not all(_num(c) for c in v):
        return None
    return [float(c) for c in v]


def _dist(a, b) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def _sub(a, b) -> list[float]:
    return [x - y for x, y in zip(a, b)]


def records_to_map(records: Iterable[Mapping]) -> tuple[dict[str, Any], list[str]]:
    """``[{handle, position}]`` -> ``({handle: position}, errors)``; a duplicate or empty handle is an error."""
    out: dict[str, Any] = {}
    errors = []
    for r in records:
        h = r.get("handle")
        if not isinstance(h, str) or not h:
            errors.append(f"record without handle: {r!r}"[:200])
            continue
        if h in out:
            errors.append(f"duplicate handle {h}")
            continue
        out[h] = r.get("position")
    return out, errors


def _base(npm: Mapping, pivot: Any, tol_m: Any, input_errors: Iterable[str] = ()
          ) -> tuple[dict, list[str], list[float] | None, dict]:
    errors = list(input_errors)
    p = _vec(pivot)
    if p is None:
        errors.append(f"bad pivot {pivot!r}")
    if not (_num(tol_m) and tol_m > 0):
        errors.append(f"bad tolerance {tol_m!r}")
    if not isinstance(npm, Mapping) or not npm:
        errors.append("no NPM instances")
        npm = {}
    good = {}
    for h, v in npm.items():
        q = _vec(v)
        if q is None:
            errors.append(f"{h}: bad NPM position {v!r}"[:200])
        else:
            good[h] = q
    report = {"schema": SCHEMA, "status": "fail", "tol_m": tol_m, "pivot": p, "n_npm": len(npm), "n_scene": 0,
              "n_ok": 0, "ok": [], "offenders": [], "errors": errors, "rule": "scene == npm - pivot, |dev| < tol_m"}
    return good, errors, p, report


def _diagnose(got, npm_pos, exp, pivot, tol) -> str:
    if any(pivot) and _dist(got, _sub(exp, pivot)) < tol:
        return "pivot subtracted twice"
    if any(pivot) and _dist(got, npm_pos) < tol:
        return "pivot not subtracted"
    return "off"


def _finish(report: dict) -> dict:
    report["n_ok"] = len(report["ok"])
    report["status"] = "pass" if not report["errors"] and not report["offenders"] and report["n_ok"] else "fail"
    return report


def check(npm: Mapping, scene: Mapping, pivot: Any, tol_m: float = TOL_M, input_errors: Iterable[str] = ()) -> dict:
    """Labelled scene (``{handle: position}``, the same handles as the NPM placement). ``input_errors`` (e.g. the
    duplicate handles ``records_to_map`` found) fail the report."""
    good, errors, p, rep = _base(npm, pivot, tol_m, input_errors)
    if not isinstance(scene, Mapping):
        errors.append("scene is not a handle -> position map")
        scene = {}
    rep["n_scene"] = len(scene)
    for h in sorted(set(scene) - set(npm)):
        errors.append(f"extra in scene {h}")
    if p is None or not (_num(tol_m) and tol_m > 0) or errors and not good:
        return _finish(rep)
    for h in sorted(good):
        exp = _sub(good[h], p)
        if h not in scene:
            rep["offenders"].append({"handle": h, "npm": good[h], "expected": exp, "got": None, "dev_m": None,
                                     "diagnosis": "missing in scene"})
            continue
        got = _vec(scene[h])
        if got is None:
            rep["offenders"].append({"handle": h, "npm": good[h], "expected": exp, "got": scene[h], "dev_m": None,
                                     "diagnosis": "bad scene position"})
            continue
        dev = _dist(got, exp)
        if dev < tol_m:
            rep["ok"].append(h)
        else:
            rep["offenders"].append({"handle": h, "npm": good[h], "expected": exp, "got": got, "dev_m": dev,
                                     "diagnosis": _diagnose(got, good[h], exp, p, tol_m)})
    return _finish(rep)


class _Grid:
    def __init__(self, pts: list[list[float]], cell: float):
        self.pts, self.cell, self.cells = pts, cell, {}
        for i, q in enumerate(pts):
            self.cells.setdefault(self._key(q), []).append(i)

    def _key(self, q):
        return tuple(math.floor(c / self.cell) for c in q)

    def near(self, q, r):
        k = self._key(q)
        out = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    for i in self.cells.get((k[0] + dx, k[1] + dy, k[2] + dz), ()):
                        d = _dist(self.pts[i], q)
                        if d < r:
                            out.append((d, i))
        return sorted(out)


def check_points(npm: Mapping, scene_points: Iterable, pivot: Any, tol_m: float = TOL_M,
                 input_errors: Iterable[str] = ()) -> dict:
    """Unlabelled scene (e.g. loose-part centres of the joined VPM Ground mesh). Each NPM handle takes the nearest
    unused scene point strictly within ``tol_m`` of NPM - pivot (handles in sorted order); scene points no NPM handle
    takes (Ground relief, other parts) are counted in ``n_scene_unmatched``, never matched twice."""
    good, errors, p, rep = _base(npm, pivot, tol_m, input_errors)
    pts = []
    for q in scene_points if scene_points is not None else ():
        v = _vec(q)
        if v is None:
            errors.append(f"bad scene point {q!r}"[:200])
        else:
            pts.append(v)
    rep["n_scene"] = len(pts)
    rep["mode"] = "nearest scene point"
    if p is None or not _num(tol_m) or tol_m <= 0 or errors and not good:
        return _finish(rep)
    grid = _Grid(pts, tol_m)
    used: set[int] = set()
    for h in sorted(good):
        exp = _sub(good[h], p)
        hit = [(d, i) for d, i in grid.near(exp, tol_m) if i not in used]
        if hit:
            used.add(hit[0][1])
            rep["ok"].append(h)
            continue
        got, diag = None, "missing in scene"
        for where, name in ((_sub(exp, p), "pivot subtracted twice"), (good[h], "pivot not subtracted")):
            near = grid.near(where, tol_m) if any(p) else []
            if near:
                got, diag = pts[near[0][1]], name
                break
        rep["offenders"].append({"handle": h, "npm": good[h], "expected": exp, "got": got,
                                 "dev_m": None if got is None else _dist(got, exp), "diagnosis": diag})
    rep["n_scene_unmatched"] = len(pts) - len(used)
    return _finish(rep)


def require_pass(report: dict) -> dict:
    """Gate before the VPM export: return the report on pass, raise ``PlacementReadbackFailed`` otherwise."""
    if report.get("status") != "pass":
        raise PlacementReadbackFailed(report)
    return report


def same_path(a: Path, b: Path) -> bool:
    try:
        return a.resolve() == b.resolve() or (a.exists() and b.exists() and os.path.samefile(a, b))
    except OSError:
        return False


def write_report(report: dict, out: str | os.PathLike, inputs: Iterable[str | os.PathLike] = ()) -> Path:
    """Write the report via ``<out>.partial``; an output (or its temp) that is an input raises and writes nothing."""
    out = Path(out)
    tmp = out.with_name(out.name + ".partial")
    for i in inputs:
        if same_path(out, Path(i)) or same_path(tmp, Path(i)):
            raise ValueError(f"report path {out} is an input ({i})")
    tmp.write_text(json.dumps(report, indent=1, sort_keys=True), encoding="utf-8")
    os.replace(tmp, out)
    return out
