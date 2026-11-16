"""Project zero command (`dt ground zero` / `agr zero`, #1406): h_relief = project zero (D279) and export Z check.

Pattern: n/a | new-case: CLI over dt_ai.core.heights.export_z_check (same core callable from Max Python).

Pointwise (review r1 P1-1): every ground-top vertex of the exported OBJ (groups `ground` / `ground_insetK` written
by `dt ground site`) is moved back to source XY (+ origin), its absolute Z (project zero + Z - FBX Z of ±0.000 -
K * step) is compared with the relief TIN at that XY within --tol-m. Relief from the site spec (its DXF, sha256
checked) or from a JSON list of absolute [x, y, z] points. A vertex outside the relief is refused, never passed.
Exit 0 pass, 1 fail, 2 refused input.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

from dt_ai.core.heights import export_z_check
from dt_ai.geometry import ground_site as gs


def _num(text: str) -> float:
    value = float(text)
    if not math.isfinite(value):
        raise argparse.ArgumentTypeError(f"{text!r} is not a finite number")
    return value


class _Refused(Exception):
    pass


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="dt ground zero", description="Project zero (h_relief, D279) and export Z check")
    ap.add_argument("--project-zero-m", type=_num, required=True, help="absolute mark of ±0.000 (h_relief, D279)")
    ap.add_argument("--zero-source", required=True, help="where the zero comes from (sheet / entity / answer)")
    ap.add_argument("--fbx-z-of-zero-m", type=_num, default=0.0, help="export Z of ±0.000 (default 0)")
    ap.add_argument("--obj", type=Path, required=True, help="OBJ exported by `dt ground site` (ground groups)")
    ap.add_argument("--spec", type=Path, help="site spec: relief from its DXF; origin_xy / step / snap from params")
    ap.add_argument("--relief-points", type=Path, help="JSON list of absolute [x, y, z] relief points")
    ap.add_argument("--origin-xy", type=_num, nargs=2, metavar=("X", "Y"), help="source XY of the OBJ origin")
    ap.add_argument("--step-m", type=_num, help="inset step per level (default: spec params.step or 0.006)")
    ap.add_argument("--snap-m", type=_num, help="relief margin = noding snap (default: spec params.snap or 0.001)")
    ap.add_argument("--tol-m", type=_num, default=0.01)
    try:
        ns = ap.parse_args(argv)
    except SystemExit as exc:
        return 2 if exc.code else 0
    try:
        if not ns.zero_source.strip():
            raise _Refused("--zero-source is empty: take the zero from the project or ask (D293)")
        if (ns.spec is None) == (ns.relief_points is None):
            raise _Refused("give exactly one of --spec or --relief-points")
        params: dict = {}
        if ns.spec is not None:
            relief, spec = gs.relief_from_spec(ns.spec)
            params = spec.get("params") or {}
        else:
            relief = gs.load_spec(ns.relief_points)
            if not isinstance(relief, list):
                raise _Refused("--relief-points must be a JSON list of [x, y, z]")
        origin = ns.origin_xy if ns.origin_xy is not None else params.get("origin_xy")
        if origin is None:
            raise _Refused("no origin: give --origin-xy (ground-report.json stages.sources.origin_xy_m)")
        step = ns.step_m if ns.step_m is not None else params.get("step", 0.006 if ns.spec is not None else 0.0)
        snap = ns.snap_m if ns.snap_m is not None else params.get("snap", 0.001)
        points = gs.ground_points(gs.read_obj(ns.obj), origin)
        out = export_z_check(ns.project_zero_m, ns.fbx_z_of_zero_m, points, gs.relief_z_at(relief, snap, origin),
                             step_m=step, tol_m=ns.tol_m)
    except (_Refused, OSError, ValueError, KeyError, TypeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    out.update(zero_source=ns.zero_source, origin_xy=list(origin), relief_points=len(relief))
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0 if out["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
