"""Near-parallel face overlap check on a faces JSON or an FBX (via background Blender).

    py -3 tools/qa/check_clearance.py <faces.json | model.fbx> <report.json> [--profile vpm|npm] [--tolerance-m 0.005]

Exit 0 when no pair is found, 1 when pairs are found (they still need classifying:
deliberate embeds vs defects), 2 on input errors.
"""
import argparse
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from twinqa.clearance import near_parallel_overlaps, summary  # noqa: E402
from twinqa.profiles import load_profiles  # noqa: E402
from dt_ai.core.blender import run_blender  # noqa: E402

EXPORT_FACES = Path(__file__).resolve().parents[1] / "blender" / "export_faces.py"


def faces_from_fbx(fbx: Path) -> list[dict]:
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "faces.json"
        return run_blender(EXPORT_FACES, [fbx, out], outputs=[out],
                           log=fbx.with_name(fbx.name + '.clearance.log'),
                           timeout=900)[out]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("source", type=Path)
    ap.add_argument("report", type=Path)
    ap.add_argument("--profile", choices=["npm", "vpm"], default="vpm")
    ap.add_argument("--tolerance-m", type=float, help="default: geometry.near_coplanar_spacing_m.min of the profile")
    args = ap.parse_args(argv)
    if not args.source.is_file():
        print(f"Error: {args.source} does not exist", file=sys.stderr)
        return 2
    tol = args.tolerance_m or load_profiles().profile(args.profile)["geometry"]["near_coplanar_spacing_m"]["min"]
    faces = faces_from_fbx(args.source) if args.source.suffix.lower() == ".fbx" else json.loads(args.source.read_text(encoding="utf-8"))
    pairs = near_parallel_overlaps(faces, tol)
    result = summary(pairs, tol, len(faces))
    args.report.write_text(json.dumps({**result, "source": str(args.source), "pairs": pairs}, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 1 if pairs else 0


if __name__ == "__main__":
    sys.exit(main())
