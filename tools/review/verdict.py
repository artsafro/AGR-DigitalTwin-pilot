"""new-case: record ok|changes on a pending review entry (issue #348)."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Update a pending review entry")
    parser.add_argument("--task", required=True)
    parser.add_argument("--status", required=True, choices=("ok", "changes"))
    parser.add_argument("--note", required=True)
    args = parser.parse_args(argv)
    try:
        return common.verdict(task=args.task, status=args.status, note=args.note, review_root=common.REVIEW_ROOT)
    except common.ReviewError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
