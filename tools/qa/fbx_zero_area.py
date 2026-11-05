"""qa.zero_area after export, without Max: zero-area faces, zero-length edges and sliver faces of every mesh of an FBX.

    py -3 tools/qa/fbx_zero_area.py <model.fbx> [--angle 5] [--height-m 0.0002]

Prints the 0.7 report JSON of `zero_area` (suite_core contract) with one object per FBX mesh, by object NAME.
Binary FBX 7.4/7.5 and ASCII FBX are read with the stdlib (export_core.fbx_meshes); n-gons are fan-triangulated.
Coordinates are taken in file units (an AGR FBX is 1 unit = 1 m). Exit 0 pass, 1 findings, 2 unreadable input.
#979 (branch E3); idea of fbx_polygon_count.py (sha256 9b413662..., team-scripts audit T04), no code reproduced.
"""
import argparse
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / "adapters" / "max" / "agr_tools"
sys.path.insert(0, str(ROOT / "src"))


def _load(name, module):
    spec = importlib.util.spec_from_file_location(module, PKG / name)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module] = mod
    spec.loader.exec_module(mod)
    return mod


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("fbx", type=Path)
    ap.add_argument("--angle", type=float, default=None, help="sliver: smallest angle below this, degrees")
    ap.add_argument("--height-m", type=float, default=None, help="sliver: smallest altitude below this, metres")
    args = ap.parse_args(argv)
    _load("checks_core.py", "agr_tools_checks_core")
    suite = _load("suite_core.py", "agr_tools_suite_core_fbx")
    export = _load("export_core.py", "agr_tools_export_core_fbx")
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        meshes = export.fbx_meshes(args.fbx.read_bytes())
        if not meshes:
            raise ValueError("no mesh in the FBX")
    except (OSError, ValueError) as exc:
        print(f"Error: {args.fbx}: {exc}", file=sys.stderr)
        return 2
    rows = suite.fbx_rows(meshes)
    found, dropped, summary = suite.zero_area(
        rows, suite.SLIVER_ANGLE_DEG if args.angle is None else args.angle,
        suite.SLIVER_HEIGHT_M if args.height_m is None else args.height_m)
    summary = dict(summary, fbx=str(args.fbx))
    rep = suite.report("zero_area", rows, found, dropped, summary)
    print(json.dumps(rep, ensure_ascii=False, indent=1))
    return 0 if rep["status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
