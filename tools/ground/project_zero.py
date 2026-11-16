"""Project zero command (`dt ground zero` / `agr zero`, #1406): h_relief = project zero (D279) and export Z check.

Pattern: n/a | new-case: CLI over dt_ai.core.heights.export_z_check (same core callable from Max Python).

Reads the ground-top Z of an exported mesh (OBJ group `ground` written by `dt ground site`, or every vertex of
another OBJ) and checks it against the absolute relief range. Exit 0 pass, 1 fail, 2 refused input.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

from dt_ai.core.heights import export_z_check
from dt_ai.geometry.ground_site import read_obj


def _num(text: str) -> float:
    value = float(text)
    if not math.isfinite(value):
        raise argparse.ArgumentTypeError(f"{text!r} is not a finite number")
    return value


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="dt ground zero", description="Project zero (h_relief, D279) and export Z check")
    ap.add_argument("--project-zero-m", type=_num, required=True, help="absolute mark of ±0.000 (h_relief, D279)")
    ap.add_argument("--zero-source", required=True, help="where the zero comes from (sheet / entity / answer)")
    ap.add_argument("--fbx-z-of-zero-m", type=_num, default=0.0, help="export Z of ±0.000 (default 0)")
    ap.add_argument("--obj", type=Path, help="exported OBJ; group 'ground' if present, else all vertices")
    ap.add_argument("--z", type=_num, nargs="+", help="ground Z values instead of --obj")
    ap.add_argument("--relief-range", type=_num, nargs=2, metavar=("MIN", "MAX"), required=True,
                    help="absolute relief marks of the source (m)")
    ap.add_argument("--tol-m", type=_num, default=0.01)
    ns = ap.parse_args(argv)
    if not ns.zero_source.strip():
        print("ERROR: --zero-source is empty: take the zero from the project or ask (D293)", file=sys.stderr)
        return 2
    if (ns.obj is None) == (ns.z is None):
        print("ERROR: give exactly one of --obj or --z", file=sys.stderr)
        return 2
    try:
        if ns.obj is not None:
            back = read_obj(ns.obj)
            zs = back["z_values"].get("ground") or [z for v in back["z_values"].values() for z in v]
        else:
            zs = ns.z
        out = export_z_check(ns.project_zero_m, ns.fbx_z_of_zero_m, zs, ns.relief_range, ns.tol_m)
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    out["zero_source"] = ns.zero_source
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0 if out["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
