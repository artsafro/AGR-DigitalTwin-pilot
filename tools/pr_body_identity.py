"""new-case: offline PR body identity snapshot check (repo + PR + card + branch + head + body hash).

Diagnostic only (docs/research/pr-body-cross-card-contamination.md F1/F3, proposed task 1). Compares an
expected publication identity with an observed PR snapshot, both local JSON files supplied by the caller:

    python tools/pr_body_identity.py --expected expected.json --observed observed.json

expected.json: {"repo": "OWNER/REPO", "pr": <positive int>, "card": "t_<8 hex>", "branch": "<name>",
                "head_commit": "<40 hex>", "body_sha256": "<64 hex>"}
observed.json: {"repo": "OWNER/REPO", "pr": <positive int>, "headRefName": "<name>",
                "headRefOid": "<40 hex>", "body": "<PR body>"}

Checks: exact repo, PR number, branch and full head SHA; SHA-256 of the body encoded as UTF-8 with no
newline normalisation; exactly one ``Card: t_...`` declaration inside exactly one ``Agent trace`` section
(card mentions elsewhere are ignored) equal to the expected card.

Exit 0 = identity_match true; 1 = mismatch; 2 = invalid input (missing/unknown/malformed field, duplicate
JSON key, unreadable file, missing or ambiguous trace card). The JSON report goes to stdout; nothing is
written to disk, no network or subprocess is used. The snapshots are NOT authenticated evidence: a match
does not authorize publication and does not certify review or readiness.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path

NOTE = (
    "snapshot comparison of caller-supplied local files; not authenticated evidence; "
    "does not authorize publication and does not certify review or readiness"
)

REPO_RE = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
CARD_RE = re.compile(r"t_[0-9a-f]{8}")
SHA1_RE = re.compile(r"[0-9a-f]{40}")
SHA256_RE = re.compile(r"[0-9a-f]{64}")

FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
CLOSE_FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})[ \t]*$")
HEADING_RE = re.compile(r"^ {0,3}(#{1,6})(?:[ \t]+(.*?))?[ \t]*$")
# CommonMark: an optional closing '#' run must be preceded by a space or tab.
HEADING_CLOSE_RE = re.compile(r"(?:^|[ \t]+)#+[ \t]*$")
# CommonMark raw HTML blocks: type 1 ends at its closing tag, types 6/7 at a
# blank line. Their content is HTML, never a Markdown list item.
HTML1_START_RE = re.compile(r"^ {0,3}<(pre|script|style|textarea)(?=[\s>]|$)", re.I)
HTML6_START_RE = re.compile(
    r"^ {0,3}</?(address|article|aside|base|basefont|blockquote|body|caption|"
    r"center|col|colgroup|dd|details|dialog|dir|div|dl|dt|fieldset|figcaption|"
    r"figure|footer|form|frame|frameset|h[1-6]|head|header|hr|html|iframe|"
    r"legend|li|link|main|menu|menuitem|nav|noframes|ol|optgroup|option|p|"
    r"param|search|section|summary|table|tbody|td|tfoot|th|thead|title|tr|"
    r"track|ul)(?=[\s>]|/>|$)",
    re.I,
)
HTML7_START_RE = re.compile(
    r"^ {0,3}(?:<[A-Za-z][A-Za-z0-9-]*(?:\s+[A-Za-z_:][\w.:-]*"
    r"(?:\s*=\s*(?:[^\s\"'=<>`]+|'[^']*'|\"[^\"]*\"))?)*\s*/?>"
    r"|</[A-Za-z][A-Za-z0-9-]*\s*>)[ \t]*$"
)
BLANK_RE = re.compile(r"^[ \t]*$")
TRACE_TITLE_RE = re.compile(r"agent trace", re.IGNORECASE)
DECL_RE = re.compile(
    r"^ {0,3}(?:[-*+]\s+)?(?:\*\*)?Card:(?:\*\*)?\s*(.*)$", re.IGNORECASE
)
DECL_ID_RE = re.compile(r"(t_[0-9a-f]{8})(?=$|[;,\s])")
ANY_ID_RE = re.compile(r"\bt_[0-9a-f]{8}\b")


class _DuplicateKey(ValueError):
    pass


def _diag(code: str, field: str, message: str, expected=None, observed=None) -> dict:
    d: dict[str, object] = {"code": code, "field": field, "message": message}
    if expected is not None or observed is not None:
        d["expected"] = expected
        d["observed"] = observed
    return d


def _no_dupes(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise _DuplicateKey(key)
        out[key] = value
    return out


def _load(path: Path, label: str, diags: list) -> dict | None:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        diags.append(
            _diag(
                "unreadable_file", label, f"cannot read {path}: {exc.strerror or exc}"
            )
        )
        return None
    try:
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=_no_dupes)
    except _DuplicateKey as exc:
        diags.append(
            _diag("duplicate_key", f"{label}.{exc.args[0]}", "duplicate JSON key")
        )
        return None
    except (UnicodeDecodeError, ValueError) as exc:
        diags.append(_diag("invalid_json", label, f"not UTF-8 JSON: {exc}"))
        return None
    if not isinstance(data, dict):
        diags.append(
            _diag("not_an_object", label, "top-level JSON value must be an object")
        )
        return None
    return data


def _is_str(v) -> bool:
    return isinstance(v, str)


def _pos_int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool) and v > 0


EXPECTED_SCHEMA = {
    "repo": (
        lambda v: _is_str(v) and REPO_RE.fullmatch(v) is not None,
        "OWNER/REPO string",
    ),
    "pr": (_pos_int, "positive integer (not bool)"),
    "card": (
        lambda v: _is_str(v) and CARD_RE.fullmatch(v) is not None,
        "card id t_<8 lowercase hex>",
    ),
    "branch": (lambda v: _is_str(v) and v != "", "non-empty string"),
    "head_commit": (
        lambda v: _is_str(v) and SHA1_RE.fullmatch(v) is not None,
        "full 40-hex lowercase SHA",
    ),
    "body_sha256": (
        lambda v: _is_str(v) and SHA256_RE.fullmatch(v) is not None,
        "64-hex lowercase SHA-256",
    ),
}
OBSERVED_SCHEMA = {
    "repo": EXPECTED_SCHEMA["repo"],
    "pr": EXPECTED_SCHEMA["pr"],
    "headRefName": EXPECTED_SCHEMA["branch"],
    "headRefOid": EXPECTED_SCHEMA["head_commit"],
    "body": (_is_str, "string"),
}


def _validate(data: dict, schema: dict, label: str, diags: list) -> bool:
    ok = True
    for key in schema:
        if key not in data:
            diags.append(
                _diag("missing_field", f"{label}.{key}", "required field is missing")
            )
            ok = False
    for key in data:
        if key not in schema:
            diags.append(
                _diag(
                    "unknown_field", f"{label}.{key}", "field is not part of the schema"
                )
            )
            ok = False
    for key, (check, what) in schema.items():
        if key in data and not check(data[key]):
            diags.append(
                _diag(
                    "invalid_field",
                    f"{label}.{key}",
                    f"must be {what}",
                    observed=repr(data[key]),
                )
            )
            ok = False
    return ok


def _strip_html_comments(line: str, in_comment: bool) -> tuple[str | None, bool]:
    """Remove HTML comment spans; return (visible text or None, still-in-comment)."""
    out = []
    i = 0
    while i <= len(line):
        if in_comment:
            j = line.find("-->", i)
            if j < 0:
                break
            in_comment, i = False, j + 3
            continue
        j = line.find("<!--", i)
        if j < 0:
            out.append(line[i:])
            break
        out.append(line[i:j])
        in_comment, i = True, j + 4
    visible = "".join(out)
    if not visible.strip() and (in_comment or "<!--" in line or "-->" in line):
        return None, in_comment
    return visible, in_comment


def trace_cards(body: str) -> tuple[list[str], list[dict]]:
    """Return card ids declared in the single Agent trace section, plus invalid diagnostics."""
    lines = [line.rstrip("\r") for line in body.split("\n")]
    sections: list[list[str]] = []
    fence: str | None = None
    current: list[str] | None = None
    level = 0
    in_comment = False
    html_end: re.Pattern | None = None  # closing tag regex, or BLANK_RE
    for line in lines:
        if html_end is not None:
            if html_end is BLANK_RE:
                if not line.strip():
                    html_end = None
            elif html_end.search(line):
                html_end = None
            continue
        if fence is not None:
            # CommonMark: a closer is the same char, at least as long, nothing but
            # trailing whitespace after it (an info string means it is NOT a closer).
            c = CLOSE_FENCE_RE.match(line)
            if c and c.group(1)[0] == fence[0] and len(c.group(1)) >= len(fence):
                fence = None
            continue
        line, in_comment = _strip_html_comments(line, in_comment)
        if line is None:
            continue
        m = FENCE_RE.match(line)
        if m and not (m.group(1)[0] == "`" and "`" in m.group(2)):
            fence = m.group(1)
            continue
        t1 = HTML1_START_RE.match(line)
        if t1:
            end = re.compile(rf"</{t1.group(1)}>", re.I)
            if not end.search(line, t1.end()):
                html_end = end
            continue
        if HTML6_START_RE.match(line) or HTML7_START_RE.match(line):
            html_end = BLANK_RE
            continue
        h = HEADING_RE.match(line)
        if h:
            hlevel = len(h.group(1))
            title = HEADING_CLOSE_RE.sub("", h.group(2) or "")
            if TRACE_TITLE_RE.fullmatch(title):
                current, level = [], hlevel
                sections.append(current)
                continue
            if current is not None and hlevel <= level:
                current = None
            continue
        if current is not None:
            current.append(line)
    if not sections:
        return [], [
            _diag(
                "trace_section_missing", "observed.body", "no '## Agent trace' section"
            )
        ]
    if len(sections) > 1:
        return [], [
            _diag(
                "trace_section_multiple",
                "observed.body",
                f"{len(sections)} Agent trace sections",
            )
        ]
    cards: list[str] = []
    diags: list[dict] = []
    for line in sections[0]:
        d = DECL_RE.match(line)
        if not d:
            continue
        rest = d.group(1)
        first = DECL_ID_RE.match(rest)
        ids = ANY_ID_RE.findall(rest)
        if not first:
            diags.append(
                _diag(
                    "trace_card_malformed",
                    "observed.body",
                    f"malformed Card declaration: {line!r}",
                )
            )
            continue
        cards.extend(ids if ids else [first.group(1)])
    if not diags and not cards:
        diags.append(
            _diag(
                "trace_card_missing",
                "observed.body",
                "no 'Card: t_...' line in Agent trace",
            )
        )
    elif not diags and len(cards) > 1:
        diags.append(
            _diag(
                "trace_card_multiple",
                "observed.body",
                f"{len(cards)} card declarations: {cards}",
            )
        )
    return cards, diags


def verify(expected_path: Path, observed_path: Path) -> dict:
    diags: list[dict] = []
    try:
        same = os.path.samefile(expected_path, observed_path)
    except OSError:
        same = os.path.normcase(os.path.abspath(expected_path)) == os.path.normcase(
            os.path.abspath(observed_path)
        )
    if same:
        diags.append(
            _diag(
                "same_input_file",
                "observed",
                "expected and observed resolve to the same file",
            )
        )
        return _report("invalid", diags, None)
    exp = _load(expected_path, "expected", diags)
    obs = _load(observed_path, "observed", diags)
    if exp is not None:
        _validate(exp, EXPECTED_SCHEMA, "expected", diags)
    if obs is not None:
        _validate(obs, OBSERVED_SCHEMA, "observed", diags)
    if exp is None or obs is None or diags:
        return _report("invalid", diags, None)

    try:
        body_bytes = obs["body"].encode("utf-8")
    except UnicodeEncodeError as exc:
        diags.append(
            _diag(
                "invalid_field",
                "observed.body",
                f"not encodable as UTF-8: {exc.reason}",
            )
        )
        return _report("invalid", diags, None)
    cards, trace_diags = trace_cards(obs["body"])
    if trace_diags:
        return _report("invalid", trace_diags, None)
    card = cards[0]

    pairs = [
        ("repo_mismatch", "repo", exp["repo"], obs["repo"]),
        ("pr_mismatch", "pr", exp["pr"], obs["pr"]),
        ("branch_mismatch", "branch", exp["branch"], obs["headRefName"]),
        ("head_mismatch", "head_commit", exp["head_commit"], obs["headRefOid"]),
        (
            "body_sha256_mismatch",
            "body_sha256",
            exp["body_sha256"],
            hashlib.sha256(body_bytes).hexdigest(),
        ),
        ("card_mismatch", "card", exp["card"], card),
    ]
    for code, field, want, got in pairs:
        if want != got:
            diags.append(
                _diag(code, field, f"{field} differs", expected=want, observed=got)
            )
    return _report("mismatch" if diags else "match", diags, card)


def _report(status: str, diags: list, card: str | None) -> dict:
    return {
        "identity_match": status == "match",
        "status": status,
        "observed_card": card,
        "diagnostics": diags,
        "note": NOTE,
    }


EXIT = {"match": 0, "mismatch": 1, "invalid": 2}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Offline PR body identity snapshot check (diagnostic only)."
    )
    parser.add_argument("--expected", required=True, type=Path)
    parser.add_argument("--observed", required=True, type=Path)
    args = parser.parse_args(argv)
    report = verify(args.expected, args.observed)
    sys.stdout.write(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    return EXIT[report["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
