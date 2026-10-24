"""new-case: list old C:/x scratch directories. Dry-run is the default; --apply deletes (issue #348)."""
import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="List old ci-receipt-* and t_* directories under C:/x")
    parser.add_argument("--days", required=True, help="delete only directories strictly older than this many days")
    parser.add_argument("--apply", action="store_true", help="delete the listed directories; omitted means dry-run")
    args = parser.parse_args(argv)
    try:
        days = float(args.days)
    except ValueError:
        print("days must be a finite number greater than 0", file=sys.stderr)
        return 1
    try:
        rows = common.cleanup(
            days=days,
            scratch=common.SCRATCH_ROOT,
            manifests=common.default_manifests(),
            now=datetime.now(),
            apply=args.apply,
        )
    except common.ReviewError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print("deleted" if args.apply else "dry-run")
    for row in rows:
        print(Path(row).resolve().as_posix())
    return 0


if __name__ == "__main__":
    sys.exit(main())
