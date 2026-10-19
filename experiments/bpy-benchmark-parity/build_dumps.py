"""Write synthetic engine dumps for the bpy parity harness. delivery_passed=false.

    uv run python experiments/bpy-benchmark-parity/build_dumps.py <out>
"""
import argparse
import sys
from pathlib import Path

import parity_lib


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("out", type=Path)
    args = parser.parse_args(argv)
    info = parity_lib.build_dumps(args.out)
    print("synthetic", {key: info["triangles"][key] for key in info["triangles"]},
          "delivery_passed=false")
    return 0


if __name__ == "__main__":
    sys.exit(main())
