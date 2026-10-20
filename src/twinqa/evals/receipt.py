"""Read-only regression receipt verification. Pattern: new-case (harness tooling, #302)."""
import json
import math
import re
from pathlib import Path

_RECEIPT = re.compile(
    r"Regression evals: (?P<path>[^;\r\n]+); "
    r"(?P<p>[0-9]+) passed(?P<sep> / |, )(?P<f>[0-9]+) failed(?P=sep)"
    r"(?P<n>[0-9]+) not measured \((?P<reason>[^\r\n]+)\)"
)
_KEYS = {"selector", "evidence_overrides", "main_checkout", "branch", "created", "passed", "failed",
         "not_measured", "exit_code", "checks"}
_COUNTS = ("passed", "failed", "not_measured")


def _nonfinite(value):
    raise ValueError(f"non-finite report value: {value}")


def _finite_float(value):
    number = float(value)
    if not math.isfinite(number):
        _nonfinite(value)
    return number


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate report key: {key}")
        result[key] = value
    return result


def check_receipt(receipt, output):
    """Raise ValueError on any unverified receipt; never write, rerun or alter the report.

    Both the card's slash separator and WORKFLOW's comma separator are accepted. A valid
    receipt attests counts only: failed or unmeasured checks are not converted into passes.
    """
    match = _RECEIPT.fullmatch(receipt)
    if match is None or not match["reason"].strip():
        raise ValueError("not a dt evals receipt")
    if output is None:
        raise ValueError("report directory required: --output")
    path = Path(output) / "report.json"
    if not path.is_file():
        raise ValueError(f"report missing: {path}")
    named = Path(match["path"].strip())
    if not named.is_file() or not named.samefile(path):
        raise ValueError(f"report path differs: {named}; expected {path}")
    try:
        report = json.loads(path.read_text(encoding="utf-8"), parse_constant=_nonfinite,
                            parse_float=_finite_float, object_pairs_hook=_object)
    except (OSError, UnicodeError, ValueError) as exc:
        raise ValueError(f"invalid report: {exc}") from exc
    if not isinstance(report, dict):
        raise ValueError("report must be an object")
    unknown = set(report) - _KEYS
    if unknown:
        raise ValueError(f"unknown report keys: {sorted(unknown)}")
    selector = report.get("selector")
    if not isinstance(selector, dict) or selector.get("suite") != "regression":
        raise ValueError("report suite must be regression")
    counts = []
    for key in _COUNTS:
        value = report.get(key)
        if type(value) is not int or value < 0:
            raise ValueError(f"report {key} must be a non-negative integer")
        counts.append(value)
    rows = report.get("checks")
    if not isinstance(rows, list):
        raise ValueError("report checks must be a list")
    if not rows or not sum(counts):
        raise ValueError("empty report: counts and rows must be greater than zero")
    if sum(counts) != len(rows):
        raise ValueError("report counts differ from number of rows")
    actual = [0, 0, 0]
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or "passed" not in row:
            raise ValueError(f"report checks[{index}] missing passed verdict")
        verdict = row["passed"]
        if verdict is True:
            actual[0] += 1
        elif verdict is False:
            actual[1] += 1
        elif verdict is None:
            actual[2] += 1
        else:
            raise ValueError(f"report checks[{index}].passed unsupported: {verdict!r}")
    if actual != counts:
        raise ValueError("report counts differ from row verdicts")
    claimed = [int(match[key]) for key in ("p", "f", "n")]
    if claimed != counts:
        raise ValueError(f"counts differ: receipt {claimed}; report {counts}")
