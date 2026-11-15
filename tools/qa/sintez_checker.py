"""`agr checker`: run SINTEZ AGR Checker 1.6.1 on a folder of AGR ZIPs and summarise its findings (#1379).

Pattern: n/a | new-case: the route command of the SINTEZ stage over the one Blender-side launch
tools/blender/sintez_checker.py (started only through src/dt_ai/core/blender_runner.py).

    agr checker FOLDER --output NEW.json [--blender EXE] [--timeout SECONDS]

FOLDER holds at most one VPM ZIP (`SM_*.zip`, checker side hp) and at most one NPM ZIP (`NNNN_*.zip`, side lp) and
nothing else ending in .zip. The input folder is never written: the ZIPs are copied into a new work folder
`<NEW>.checker/` (the checker unpacks them and writes AGRChecker_data there), the Blender log goes to
`<NEW>.blender.log`, and the summary is written to NEW.json last (via `<NEW>.json.partial`).
Evidence rules (fail closed): Blender 5.1.2 and extension 1.6.1 exactly; the input ZIP bytes must not change during
the run; each given side must have been detected by the checker (has_hp / has_lp) and carry rows; a checker run
error, a malformed report or a report with no measured automatic rule is unusable evidence.
Statuses per rule come from adapters/max/agr_tools/qa9_core.py::sintez_verdicts (pass / review / fail /
not_measured). The checker is evidence, not the norm (docs/domain/validation.md, D104): this command never sets a
delivery `passed`.
Exit: 0 no automatic rule failed, 1 at least one failed, 2 bad input or unusable evidence (NEW.json not written).
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "adapters" / "max" / "agr_tools"))

from dt_ai.core.blender_runner import BlenderRunError, run_blender  # noqa: E402
from qa9_core import sintez_verdicts  # noqa: E402

OWNER = ROOT / "tools" / "blender" / "sintez_checker.py"
BLENDER_VERSION = "5.1.2"
CHECKER_VERSION = "1.6.1"
SIDES = {"hp": re.compile(r"^SM_.+\.zip$", re.I), "lp": re.compile(r"^[0-9]{4}_.+\.zip$", re.I)}


class InputError(ValueError):
    """Bad input or unusable evidence: exit 2, NEW.json not written."""


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def classify(folder):
    """{side: Path} of the ZIPs in FOLDER; anything ambiguous or unsupported raises InputError naming it."""
    folder = Path(folder)
    if not folder.is_dir():
        raise InputError(f"input folder not found: {folder}")
    zips = sorted(p for p in folder.iterdir() if p.suffix.lower() == ".zip")
    sides = {}
    for path in zips:
        if not path.is_file():
            raise InputError(f"not a file: {path}")
        side = next((s for s, rx in SIDES.items() if rx.match(path.name)), None)
        if side is None:
            raise InputError(f"unsupported ZIP name {path.name!r}: expected SM_*.zip (VPM) or NNNN_*.zip (NPM)")
        if side in sides:
            raise InputError(f"two {side} ZIPs ({sides[side].name}, {path.name}): one VPM and one NPM ZIP per run")
        sides[side] = path
    if not sides:
        raise InputError(f"no AGR ZIP in {folder}")
    return sides


def plan_paths(folder, output):
    """-> (output, work, log, partial); every path is new and outside the input folder."""
    folder, output = Path(folder).resolve(), Path(output).resolve()
    if output.suffix.lower() != ".json":
        raise InputError(f"--output must be a new .json file: {output}")
    if output == folder or folder in output.parents:
        raise InputError(f"--output must be outside the input folder (the input is never written): {output}")
    if not output.parent.is_dir():
        raise InputError(f"--output folder not found: {output.parent}")
    stem = output.with_suffix("")
    paths = (output, Path(str(stem) + ".checker"), Path(str(stem) + ".blender.log"), Path(str(output) + ".partial"))
    for path in paths:
        if path.exists():
            raise InputError(f"refusing to reuse an existing path (evidence is never overwritten): {path}")
    return paths


def summarise(report, sides):
    """Checker JSON -> summary dict; unusable evidence raises InputError."""
    if not isinstance(report, dict):
        raise InputError("checker report is not a JSON object")
    if report.get("blender") != BLENDER_VERSION or report.get("extension_version") != CHECKER_VERSION:
        raise InputError(f"Blender {BLENDER_VERSION} / SINTEZ {CHECKER_VERSION} required, got Blender "
                         f"{report.get('blender')!r} / SINTEZ {report.get('extension_version')!r}")
    for side, path in sides.items():
        if report.get("has_" + side) is not True:
            raise InputError(f"the checker did not detect {path.name} (has_{side} is not true)")
        if not isinstance(report.get(side), list) or not report[side]:
            raise InputError(f"the checker report has no {side} rows for {path.name}")
    try:
        verdicts = sintez_verdicts(report)
    except ValueError as exc:
        raise InputError(str(exc)) from None
    counts = {side: {} for side in sides}
    rules = []
    for (side, req), row in sorted(verdicts.items()):
        if side not in sides:   # a side without an input ZIP carries the checker's empty template only
            continue
        counts[side][row["status"]] = counts[side].get(row["status"], 0) + 1
        rules.append({"side": side, "req": req, "status": row["status"], **row["raw"]})
    for side, path in sorted(sides.items()):
        if not any(r["side"] == side and r["status"] != "not_measured" for r in rules):
            raise InputError(f"SINTEZ report: no measured automatic rule for {path.name} ({side})")
    failed = [f"{r['side']} {r['req']}" for r in rules if r["status"] == "fail"]
    return {"checker_verdict": "fail" if failed else "no_failed_automatic_rule", "failed": failed,
            "counts": counts, "rules": rules}


def run(folder, output, blender=None, timeout=900):
    """Run the checker on a private copy of FOLDER's ZIPs; return (exit code, summary)."""
    sides = classify(folder)
    output, work, log, partial = plan_paths(folder, output)
    before = {side: _sha256(path) for side, path in sides.items()}
    work.mkdir()
    for path in sides.values():
        shutil.copyfile(path, work / path.name)
    raw = work / "checker.json"
    try:
        report = run_blender(OWNER, [work, raw], executable=blender, output_json=raw, log_path=log, timeout=timeout)
    except BlenderRunError as exc:
        raise InputError(f"Blender run failed ({exc.envelope.get('code')}): {exc.envelope.get('message')}; "
                         f"log {log}") from None
    after = {side: _sha256(path) for side, path in sides.items()}
    if after != before:
        raise InputError("an input ZIP changed during the run: " +
                         ", ".join(sides[s].name for s in sides if after[s] != before[s]))
    copies = {side: _sha256(work / path.name) for side, path in sides.items()}
    if copies != before:
        raise InputError("the checker changed its working copy of an input ZIP")
    summary = summarise(report, sides)
    summary = {"command": "agr checker", "issue": "#1379", "blender": report["blender"],
               "extension_version": report["extension_version"],
               "inputs": [{"side": s, "path": str(p), "sha256": before[s]} for s, p in sorted(sides.items())],
               "checker_report": str(raw), "log": str(log), "work": str(work),
               "note": "SINTEZ findings are evidence, not a delivery verdict (D104); no passed flag is set",
               **summary}
    text = json.dumps(summary, ensure_ascii=False, indent=1, allow_nan=False)   # NaN/inf: ValueError before any write
    with open(partial, "x", encoding="utf-8") as fh:
        fh.write(text)
    os.replace(partial, output)
    return (1 if summary["failed"] else 0), summary


def main(argv=None):
    ap = argparse.ArgumentParser(prog="agr checker", description="SINTEZ AGR Checker 1.6.1 on a folder of AGR ZIPs (#1379)")
    ap.add_argument("folder", type=Path, help="folder with one SM_*.zip and/or one NNNN_*.zip")
    ap.add_argument("--output", type=Path, required=True, help="new summary JSON (never reused)")
    ap.add_argument("--blender", help="Blender 5.1.2 executable (default: TWINQA_BLENDER or the pinned install)")
    ap.add_argument("--timeout", type=float, default=900)
    args = ap.parse_args(argv)
    try:
        code, summary = run(args.folder, args.output, blender=args.blender, timeout=args.timeout)
    except (ValueError, OSError) as exc:   # InputError is a ValueError
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    for side, counts in sorted(summary["counts"].items()):
        print(f"{side}: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())))
    print(f"checker_verdict={summary['checker_verdict']} failed={len(summary['failed'])} -> {args.output}")
    return code


if __name__ == "__main__":
    sys.exit(main())
