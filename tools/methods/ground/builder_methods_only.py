"""Methods-only Ground builder run: build_ground.py unchanged, its gate verdict recorded but not enforced (#733).

Pattern: new-case: methods-catalog gate bypass for one measured row, never a delivery.

    uv run python tools/methods/ground/builder_methods_only.py <adapter.json> --out <new dir> [build_ground.py args]

User decision (Artem 2026-11-02, option (b), #733 / PR #734 only, [D188]): the second builder setting is a METHODS-ONLY
build; it skips the Ground quality gate, lists every failed gate, and is never a delivery. No new [D150] exception;
jobs/VATUTINO-SITE/ and its gates stay unchanged.

How: jobs/VATUTINO-SITE/build_ground.py is loaded from its file and its `main` runs in this process with the
module-global `acceptance_gates` wrapped: the real verdicts are kept aside and `main` sees them as passed, so it
writes the mesh masters it would otherwise withhold. Afterwards ground_report.json gets the REAL gates back plus
`methods_only = {delivery: false, gates_skipped: true, failed_gates: [...], decision}`. The wrapper is restored
after the run. Exit: the builder's own code when it refused/failed before the gates; 1 when the gates never ran
(nothing to record, no methods_only block written); 0 otherwise.
"""
from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BUILD_GROUND = ROOT / "jobs" / "VATUTINO-SITE" / "build_ground.py"
DECISION = ("Artem 2026-11-02 option (b) on #733: methods-only build, Ground gate skipped, failed gates listed, "
            "never a delivery")


def load_builder():
    spec = importlib.util.spec_from_file_location("vatutino_build_ground_methods_only", BUILD_GROUND)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run(mod, argv: list[str]) -> int:
    orig = mod.acceptance_gates
    real: list[dict] = []

    def recorded(rep, exceptions=None):
        gates = orig(rep, exceptions)
        real.append(copy.deepcopy(gates))
        return {k: {**v, "pass": True} for k, v in gates.items()}

    mod.acceptance_gates = recorded
    try:
        code = mod.main(argv)
    finally:
        mod.acceptance_gates = orig
    if code not in (0, None):
        return int(code)
    if len(real) != 1:
        print(f"BUILDER_METHODS_ONLY error: acceptance_gates ran {len(real)} times, expected 1", file=sys.stderr)
        return 1
    out = Path(argv[argv.index("--out") + 1])
    report = out / "ground_report.json"
    rep = json.loads(report.read_text(encoding="utf-8"))
    rep["gates"] = real[0]
    failed = sorted(k for k, v in real[0].items() if not v["pass"])
    rep["methods_only"] = {"delivery": False, "gates_skipped": True, "failed_gates": failed, "decision": DECISION}
    report.write_text(json.dumps(rep, indent=1, ensure_ascii=False, default=float), encoding="utf-8")
    print(f"BUILDER_METHODS_ONLY written, NOT a delivery; failed gates {failed}")
    return 0


if __name__ == "__main__":
    sys.exit(run(load_builder(), sys.argv[1:]))
