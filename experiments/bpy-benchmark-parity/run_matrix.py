"""Run the synthetic bpy-vs-blender.exe matrix. delivery_passed=false.

    uv run python experiments/bpy-benchmark-parity/run_matrix.py <work> [--blender PATH] [--wheel PATH] [--reps 2]

Dumps are read from <work>/common. The wheel interpreter is --wheel or DT_BPY_PYTHON.
blender.exe stays the default (DT_BLENDER or the Blender 5.1 install path).
"""
import argparse
import sys
from pathlib import Path

import parity_lib


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("work", type=Path)
    parser.add_argument("--blender", default=None)
    parser.add_argument("--wheel", default=None)
    parser.add_argument("--reps", type=int, default=2)
    args = parser.parse_args(argv)
    blender, wheel = parity_lib.resolve_lanes(args.blender, args.wheel)
    parity_lib.run_matrix(args.work, blender, wheel, reps=args.reps)
    return 0


if __name__ == "__main__":
    sys.exit(main())
