"""Opt-in whole-call timing for #283 (synthetic, never delivery acceptance).

Pattern: primitive-first | new-case: paired first-group-index timing receipt.
Run: uv run python experiments/complexity-group-index/driver.py
Stdout JSON only; accepts no input/output/report paths and never writes files.
The original oracle lives in tests/qa/test_complexity_group_index.py.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import platform
import runpy
import statistics
import subprocess
import sys
from time import perf_counter_ns

ROOT = Path(__file__).resolve().parents[2]
ORACLE = ROOT / "tests/qa/test_complexity_group_index.py"


def verdict(rows):
    """Strict evidence boundary: malformed/partial/nonfinite evidence cannot support."""
    expected = {(phase, k, layout) for phase, ks in (("primary", (32, 256, 1024)),
                ("confirmation", (1024,))) for k in ks for layout in ("grouped", "interleaved")}
    if not isinstance(rows, list) or len(rows) != len(expected):
        return "INCONCLUSIVE"
    seen = set()
    ratios = []
    for row in rows:
        if not isinstance(row, dict):
            return "INCONCLUSIVE"
        key = (row.get("phase"), row.get("k"), row.get("layout"))
        if key not in expected or key in seen or row.get("parity") is not True:
            return "INCONCLUSIVE"
        seen.add(key)
        pairs = row.get("pairs")
        if not isinstance(pairs, list) or len(pairs) != (7 if key[0] == "primary" else 3):
            return "INCONCLUSIVE"
        for pair in pairs:
            if (not isinstance(pair, list) or len(pair) != 2 or
                any(type(x) not in (int, float) or not math.isfinite(x) or x <= 0 for x in pair)):
                return "INCONCLUSIVE"
        ratio = statistics.median(p[1] for p in pairs) / statistics.median(p[0] for p in pairs)
        ratios.append((key[1], ratio))
    # Equality deliberately does not support: conservative evidence gate, not checker policy.
    return "SUPPORTED" if all(r < (.8 if k == 1024 else 1.1) for k, r in ratios) else "REJECTED"


def measure(confirmation=False):
    ns = runpy.run_path(str(ORACLE))
    baseline, candidate = ns["reference_complexity"], ns["check_complexity"]
    serialize = ns["serialize"]
    tol = copy.deepcopy(ns["TOL"])
    rows = []
    for k in ((1024,) if confirmation else (32, 256, 1024)):
        for layout in ("grouped", "interleaved"):
            sc = ns["scene"](k, 10000)
            if layout == "grouped":
                sc["objects"].sort(key=lambda ob: int(ob["mesh"][1:]))
            frozen = serialize([sc, tol])
            expected = serialize(baseline(sc, tol))
            assert serialize(candidate(sc, tol)) == expected
            assert serialize([sc, tol]) == frozen
            pairs = []
            for i in range(3 if confirmation else 7):
                pair = [0.0, 0.0]
                for variant in ((0, 1) if i % 2 == 0 else (1, 0)):
                    fn = (baseline, candidate)[variant]
                    # Exactly three whole calls, excluding all serialization/fixture work.
                    start = perf_counter_ns()
                    outputs = [fn(sc, tol) for _ in range(3)]
                    pair[variant] = (perf_counter_ns() - start) / 3e9
                    assert all(serialize(out) == expected for out in outputs)
                    assert serialize([sc, tol]) == frozen
                pairs.append(pair)
            a, b = (statistics.median(p[j] for p in pairs) for j in (0, 1))
            rows.append({"phase": "confirmation" if confirmation else "primary", "k": k,
                         "layout": layout, "pairs": pairs, "A_seconds": a, "B_seconds": b,
                         "gain_percent": 100 * (1 - b / a), "parity": True,
                         "input_sha256": hashlib.sha256(frozen.encode()).hexdigest()})
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirmation", action="store_true", help="internal fresh-process block")
    args = parser.parse_args()
    rows = measure(args.confirmation)
    if args.confirmation:
        print(json.dumps(rows, allow_nan=False))
        return 0
    confirmation = subprocess.check_output([sys.executable, str(Path(__file__).resolve()), "--confirmation"],
                                           cwd=ROOT, text=True)
    rows.extend(json.loads(confirmation))
    status = verdict(rows)
    print(json.dumps({"verdict": status, "delivery_passed": False, "python": platform.python_version(),
                      "calls_per_sample": 3, "oracle_sha256": hashlib.sha256(ORACLE.read_bytes()).hexdigest(),
                      "source_sha256": hashlib.sha256((ROOT / "src/twinqa/geometry/complexity.py").read_bytes()).hexdigest(),
                      "rows": rows}, indent=2, allow_nan=False))
    return 0 if status == "SUPPORTED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
