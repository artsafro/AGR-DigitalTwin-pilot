"""new-case: publish a review scene: C:/x/review/<date>/<task>-<slug>/ plus pending.json (issue #348)."""
import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common
import max_adapter


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Publish an FBX or .max for visual review in 3ds Max")
    parser.add_argument("--task", required=True)
    parser.add_argument("--slug", required=True)
    parser.add_argument("--fbx", required=True, help="FBX to merge, or an existing .max to open")
    parser.add_argument("--png", action="append", default=[], help="preview PNG copied into the review folder")
    parser.add_argument("--what", required=True, help="one Russian line: what to look at")
    args = parser.parse_args(argv)
    try:
        adapter = max_adapter.default_adapter()
        return common.publish(
            task=args.task,
            slug=args.slug,
            source=args.fbx,
            what=args.what,
            pngs=args.png,
            review_root=common.REVIEW_ROOT,
            adapter=adapter,
            today=date.today(),
        )
    except (common.ReviewError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
