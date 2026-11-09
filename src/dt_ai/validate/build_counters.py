"""Fail-closed gate for skipped/failed counters in a build report (#1031).

new-case: a build script's own report counter of skipped or failed elements
(``face_create_fail``, ``skipped``, ``plate_miss``, ...) above 0 fails the build;
an exception passes only with the exact count and the user's source.

Stdlib only, so a DCC build script (Blender ``bpy``) can import it after putting
``<repo>/src`` on ``sys.path`` and call :func:`enforce` with its report dict.
Run Blender with ``--python-exit-code 1`` so the ``SystemExit(1)`` reaches the shell.

CLI (exit 0 pass, 1 fail, 2 unusable input)::

    uv run python -m dt_ai.validate.build_counters --report g3_report.json \
        --counter face_create_fail [--accepted exceptions.json] \
        [--source-count 412 --output-count 411] [--out gate.json]

Count parity alone (independent-checker, no build counter)::

    uv run python -m dt_ai.validate.build_counters --source-count 412 --output-count 411

Run as a ``RunRecord.run_stage`` argv, a nonzero exit records the stage ``failed``.
"""
import argparse
import json
import math
import os
from pathlib import Path
import re
import sys

FAIL_TOKENS = frozenset({
    "fail", "fails", "failed", "failure", "failures",
    "skip", "skips", "skipped",
    "miss", "misses", "missed", "missing",
    "drop", "drops", "dropped",
})


def is_fail_counter_name(name):
    """True when a key names a skipped/failed counter (token match, not substring)."""
    split = re.sub(r"(?<=[a-z])(?=[A-Z])|(?<=[A-Za-z])(?=\d)", "_", str(name))
    return any(token in FAIL_TOKENS for token in re.split(r"[^a-z0-9]+", split.lower()))


def _count(value):
    """Return a non-negative int count, or None when the value is not a count."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, float):
        if math.isfinite(value) and value >= 0 and value.is_integer():
            return int(value)
        return None
    if isinstance(value, (list, tuple)):
        return len(value)
    return None


def _resolve(report, dotted):
    node = report
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return False, None
        node = node[part]
    return True, node


def _walk(node, path, inherited, declared, found):
    """Collect undeclared fail-like counters as {path: count or None}."""
    if path in declared:
        return
    if isinstance(node, dict):
        for key, value in node.items():
            child = f"{path}.{key}" if path else str(key)
            _walk(value, child, inherited or is_fail_counter_name(key), declared, found)
        return
    if isinstance(node, list) and not inherited:
        for index, value in enumerate(node):
            if isinstance(value, (dict, list)):
                _walk(value, f"{path}[{index}]", False, declared, found)
        return
    if not inherited:
        return
    if isinstance(node, bool):
        found[path] = int(node)
    else:
        found[path] = _count(node)


def check_build_counters(report, counters, *, accepted=None):
    """Check declared and detected fail counters of one build report.

    ``counters``: declared counter names (dotted paths for nested keys); at least one.
    ``accepted``: optional ``{counter: {"count": N, "source": "<user quote/date>"}}``;
    an exception passes only when N equals the measured count.
    Every other fail-like key in the report with a nonzero or invalid value also fails.
    """
    if not isinstance(report, dict):
        raise ValueError("report must be an object")
    names = list(counters or [])
    if not names:
        raise ValueError("no fail counter declared")
    for name in names:
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"invalid counter name: {name!r}")
    if accepted is None:
        accepted = {}
    if not isinstance(accepted, dict):
        raise ValueError("accepted must be an object")

    failures, values, measured = [], {}, {}
    for name in names:
        present, raw = _resolve(report, name)
        if not present:
            failures.append({"counter": name, "value": None, "reason": "missing"})
            continue
        count = _count(raw)
        values[name] = count if count is not None else repr(raw)
        if count is None:
            failures.append({"counter": name, "value": repr(raw), "reason": "invalid"})
        else:
            measured[name] = count

    found = {}
    _walk(report, "", False, set(names), found)
    undeclared = {}
    for path, count in sorted(found.items()):
        if count is None:
            failures.append({"counter": path, "value": None, "reason": "undeclared_invalid"})
        elif count:
            undeclared[path] = count
            measured[path] = count

    accepted_rows = []
    for name, exception in accepted.items():
        if name not in measured:
            failures.append({"counter": name, "value": None, "reason": "accepted_unknown_counter"})
            continue
        count = exception.get("count") if isinstance(exception, dict) else None
        source = exception.get("source") if isinstance(exception, dict) else None
        if (isinstance(count, bool) or not isinstance(count, int) or count <= 0
                or not isinstance(source, str) or not source.strip()):
            failures.append({"counter": name, "value": measured[name], "reason": "accepted_invalid"})
        elif count != measured[name]:
            failures.append({"counter": name, "value": measured[name], "reason": "accepted_mismatch",
                             "accepted_count": count})
        else:
            accepted_rows.append({"counter": name, "count": count, "source": source})
    excused = {row["counter"] for row in accepted_rows}

    for name, count in measured.items():
        if count and name not in excused:
            reason = "nonzero" if name in values else "undeclared_nonzero"
            failures.append({"counter": name, "value": count, "reason": reason})

    return {"status": "fail" if failures else "pass", "counters": values,
            "undeclared": undeclared, "accepted": accepted_rows, "failures": failures}


def check_count_parity(source_count, output_count, *, label="faces"):
    """Source element count (spec faces/plans) against the read-back output count."""
    def valid(value):
        return not isinstance(value, bool) and isinstance(value, int) and value >= 0

    if not (valid(source_count) and valid(output_count)):
        return {"status": "fail", "label": label, "source_count": repr(source_count),
                "output_count": repr(output_count), "reason": "invalid"}
    missing = source_count - output_count
    return {"status": "pass" if missing == 0 else "fail", "label": label,
            "source_count": source_count, "output_count": output_count, "missing": missing,
            "reason": None if missing == 0 else ("missing" if missing > 0 else "extra")}


def enforce(report, counters, *, accepted=None, stream=None):
    """Return the result on pass; print it and raise ``SystemExit(1)`` on fail."""
    result = check_build_counters(report, counters, accepted=accepted)
    if result["status"] != "pass":
        print("BUILD_COUNTER_GATE_FAIL " + json.dumps(result, ensure_ascii=False),
              file=stream or sys.stderr)
        raise SystemExit(1)
    return result


def _read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Fail-closed gate for build-report fail counters.")
    parser.add_argument("--report")
    parser.add_argument("--counter", action="append", default=[])
    parser.add_argument("--accepted")
    parser.add_argument("--source-count", type=int)
    parser.add_argument("--output-count", type=int)
    parser.add_argument("--label", default="faces")
    parser.add_argument("--out")
    try:
        args = parser.parse_args(argv)
    except SystemExit:
        return 2

    def unusable(message):
        print(f"build_counters: {message}", file=sys.stderr)
        return 2

    if (args.source_count is None) != (args.output_count is None):
        return unusable("--source-count and --output-count go together")
    if args.report is None and args.source_count is None:
        return unusable("give --report with --counter, or --source-count with --output-count")
    if args.report is None and (args.counter or args.accepted):
        return unusable("--counter/--accepted need --report")
    inputs = [Path(args.report).resolve()] if args.report else []
    if args.accepted:
        inputs.append(Path(args.accepted).resolve())
    out = partial = None
    if args.out:
        out = Path(args.out).resolve()
        partial = out.with_name(out.name + ".partial")
        if out in inputs or partial in inputs:
            return unusable(f"--out resolves to an input: {out}")
        if out.exists() or partial.exists():
            return unusable(f"--out already exists, use a new versioned path: {out}")
    counters = None
    if inputs:
        try:
            report = _read_json(inputs[0])
            accepted = _read_json(inputs[1]) if args.accepted else None
            counters = check_build_counters(report, args.counter, accepted=accepted)
        except (OSError, ValueError) as error:
            return unusable(str(error))

    parity = None
    if args.source_count is not None:
        parity = check_count_parity(args.source_count, args.output_count, label=args.label)
    passed = ((counters is None or counters["status"] == "pass")
              and (parity is None or parity["status"] == "pass"))
    result = {"status": "pass" if passed else "fail",
              "report": str(inputs[0]) if inputs else None,
              "counters": counters, "count_parity": parity}
    text = json.dumps(result, ensure_ascii=False)
    if out is not None and partial is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        partial.write_text(text + "\n", encoding="utf-8")
        os.replace(partial, out)
    print(text)
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
