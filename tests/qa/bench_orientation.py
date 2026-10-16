"""Synthetic issue #203 timing/memory evidence, not a real object.

Pattern: n/a | new-case: issue-203 reproducible legacy/adaptive benchmark.
Run: uv run python tests/qa/bench_orientation.py --output tmp/orientation-benchmark.jsonl
"""
import argparse
import json
import time
import tracemalloc
from pathlib import Path

from test_orientation_scaling import box, bipyramid
import orientation_reference as ref
from twinqa.geometry import checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as out:
        def emit(record):
            text = json.dumps(record)
            out.write(text + "\n")
            out.flush()
            print(text, flush=True)

        for shape, size in [("box", 9), ("box", 20), ("box", 41), ("box", 65),
                            ("bipyramid", 1000), ("bipyramid", 5000)]:
            model = box(size) if shape == "box" else bipyramid(size)
            original = checks._first_back_hits
            for mode in ("before", "after"):
                checks._first_back_hits = ref._first_back_hits if mode == "before" else original
                try:
                    start = time.perf_counter()
                    result = checks.check_orientation(model, {"weld_m": 0.003})
                    elapsed = time.perf_counter() - start
                finally:
                    checks._first_back_hits = original
                emit(dict(shape=shape, size=size, faces=len(model.triangles), mode=mode,
                          seconds=elapsed, value=result["value"]))
        model = box(65)
        tracemalloc.start()
        checks.check_orientation(model, {"weld_m": 0.003})
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        emit(dict(shape="box", faces=len(model.triangles), mode="memory", peak_bytes=peak))


if __name__ == "__main__":
    main()
