"""Offline, advisory candidate-kind overlay for a frozen Worker KPI ``kpi.json``.

Report-only (research report #671, docs/research/kpi-card-kind-attribution-boundary.md, F2/F4/F5,
proposed next task 1). It reads one frozen ``kpi.json`` given explicitly with ``--input`` and prints a
JSON report to stdout. It writes no file, runs no collector and does not change the official ``kind``,
the totals or any grade:

    python tools/state/kpi_kind_overlay.py --input C:/path/to/kpi.json > overlay.json

Each row keeps its stored ``kind``; a candidate label is added next to it. A non-``issue`` stored kind
is preserved as the label. For stored ``issue``: an explicit ``Plan:`` / ``Hypotheses:`` /
``Readiness:`` / ``Triage:`` / ``Adopt:`` title prefix gives that label, a ``#<digits>`` title gives
``issue``, a missing or blank title gives ``unknown`` (no evidence), anything else ``unlabeled``.
Hidden keys (``idempotency_key`` etc.) are never used. Counts and minutes are grouped by implementer
and label; ``original_totals`` is the input ``totals`` unchanged. No rates or quality grades are
computed: taxonomy and denominators are the user's decision (report #671, O1-O4).

Invalid input (duplicate card id or JSON key, malformed cards/totals, a totals entry without
``cards``/``minutes`` or with an unsupported metric, NaN/inf, bool, negative or
non-numeric minutes) is an error: exit 2, message on stderr, nothing on stdout.

new-case: offline advisory overlay over a frozen KPI snapshot, stdout-only, no taxonomy change.
"""
import argparse
import datetime
import hashlib
import json
import math
import re
import sys
from collections import defaultdict

PREFIX_LABELS = {
    "Plan:": "plan",
    "Hypotheses:": "hypotheses",
    "Readiness:": "readiness",
    "Triage:": "triage",
    "Adopt:": "adopt",
}
ISSUE_RE = re.compile(r"#\d+(?!\w)")
NOTICE = ("advisory, report-only: candidate labels are not an official taxonomy; stored kind, totals "
          "and grades are unchanged; no rates are published (taxonomy/denominators are user-owned)")


class OverlayError(ValueError):
    """Invalid input; the CLI exits nonzero and prints nothing on stdout."""


# Metrics of a Worker KPI totals entry (frozen kpi.json shape); each entry needs at least cards+minutes.
TOTALS_REQUIRED = ("cards", "minutes")
TOTALS_METRICS = frozenset(TOTALS_REQUIRED + (
    "done", "first_pass", "review_rounds", "blocked_runs", "failed_runs"))


def candidate_label(stored_kind, title):
    if stored_kind != "issue":
        return stored_kind
    if title is None or not title.strip():
        return "unknown"
    for prefix, label in PREFIX_LABELS.items():
        if title.startswith(prefix):
            return label
    if ISSUE_RE.match(title):
        return "issue"
    return "unlabeled"


def _number(value, where, allow_negative=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise OverlayError(f"{where}: expected a number, got {type(value).__name__}")
    if not math.isfinite(value):
        raise OverlayError(f"{where}: non-finite value {value!r}")
    if value < 0 and not allow_negative:
        raise OverlayError(f"{where}: negative value {value!r}")
    return value


def _text(card, key, where):
    value = card.get(key)
    if not isinstance(value, str) or not value.strip():
        raise OverlayError(f"{where}: '{key}' must be a non-empty string")
    return value


def _validate_totals(totals):
    if not isinstance(totals, dict):
        raise OverlayError("'totals' must be an object")
    for key, entry in totals.items():
        if not isinstance(entry, dict):
            raise OverlayError(f"totals[{key!r}] must be an object")
        for metric in entry:
            if metric not in TOTALS_METRICS:
                raise OverlayError(f"totals[{key!r}]: unsupported metric {metric!r} "
                                   f"(supported: {', '.join(sorted(TOTALS_METRICS))})")
        for metric in TOTALS_REQUIRED:
            if metric not in entry:
                raise OverlayError(f"totals[{key!r}]: missing required metric {metric!r}")
        for metric, value in entry.items():
            _number(value, f"totals[{key!r}][{metric!r}]")
        if not float(entry["cards"]).is_integer():
            raise OverlayError(f"totals[{key!r}]['cards']: not a whole count {entry['cards']!r}")


def build_report(doc, source_sha256, source_path):
    if not isinstance(doc, dict):
        raise OverlayError("top level must be an object")
    for key in ("cards", "totals"):
        if key not in doc:
            raise OverlayError(f"missing '{key}'")
    cards = doc["cards"]
    if not isinstance(cards, list):
        raise OverlayError("'cards' must be a list")
    _validate_totals(doc["totals"])

    rows, seen = [], set()
    for i, card in enumerate(cards):
        where = f"cards[{i}]"
        if not isinstance(card, dict):
            raise OverlayError(f"{where}: must be an object")
        cid = _text(card, "id", where)
        if cid in seen:
            raise OverlayError(f"{where}: duplicate card id {cid!r}")
        seen.add(cid)
        kind = _text(card, "kind", where)
        who = _text(card, "implementer", where)
        if "minutes" not in card:
            raise OverlayError(f"{where}: missing 'minutes'")
        minutes = _number(card["minutes"], f"{where}.minutes")
        title = card.get("title")
        if title is not None and not isinstance(title, str):
            raise OverlayError(f"{where}: 'title' must be a string")
        rows.append({"id": cid, "title": title, "implementer": who, "stored_kind": kind,
                     "candidate_label": candidate_label(kind, title), "minutes": minutes})

    acc = defaultdict(lambda: defaultdict(list))
    for r in rows:
        acc[r["implementer"]][r["candidate_label"]].append(r["minutes"])
    groups = {who: {lab: {"cards": len(m), "minutes": round(math.fsum(m), 6)}
                    for lab, m in sorted(labels.items())}
              for who, labels in sorted(acc.items())}

    return {
        "advisory": True,
        "notice": NOTICE,
        "source": {"path": source_path, "sha256": source_sha256,
                   "generated": doc.get("generated"), "board": doc.get("board")},
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "label_rules": {"non_issue_stored_kind": "preserved", "prefixes": PREFIX_LABELS,
                        "#<digits>": "issue", "missing_or_blank_title": "unknown", "other": "unlabeled"},
        "rows": rows,
        "groups": groups,
        "original_totals": doc["totals"],
    }


def _no_duplicate_keys(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise OverlayError(f"duplicate JSON key {key!r}")
        out[key] = value
    return out


def _reject_constant(name):
    raise OverlayError(f"non-finite JSON constant {name}")


def load_source(path):
    with open(path, "rb") as fh:  # read once: hash and parse the same bytes
        raw = fh.read()
    try:
        doc = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=_no_duplicate_keys,
                         parse_constant=_reject_constant)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OverlayError(f"invalid JSON: {exc}") from exc
    return doc, hashlib.sha256(raw).hexdigest()


def main(argv=None):
    ap = argparse.ArgumentParser(description="Offline advisory candidate-kind overlay (stdout only).")
    ap.add_argument("--input", required=True, help="frozen kpi.json (read-only)")
    args = ap.parse_args(argv)
    try:
        doc, sha = load_source(args.input)
        report = build_report(doc, sha, args.input)
        text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    except (OverlayError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    sys.stdout.buffer.write(text.encode("utf-8"))
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
