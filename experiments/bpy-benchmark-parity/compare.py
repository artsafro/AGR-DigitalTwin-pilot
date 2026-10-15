"""Compare a synthetic bpy parity matrix and exit 1 when it is not ok. delivery_passed=false.

    uv run python experiments/bpy-benchmark-parity/compare.py <work>
"""
import argparse
import sys
from pathlib import Path

import parity_lib


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("work", type=Path)
    args = parser.parse_args(argv)
    result = parity_lib.compare(args.work)
    print("completion failures:", len(result["completion_fail"]))
    for check, bucket in result["summary"].items():
        shown = {cat: f"{magnitude:.3g}" for cat, magnitude in bucket["max"].items()}
        print(f"{check:32s} n={bucket['n']:3d} fail={bucket['fail']:3d} max={shown}")
    for row in result["rows"]:
        if not row["ok"]:
            print("FAIL", row["rep"], row["model"], row["exporter"], row["reader"], row["check"],
                  row["over"], row["discrete"][:2])
    print("synthetic delivery_passed=false ok=" + str(result["ok"]).lower())
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
