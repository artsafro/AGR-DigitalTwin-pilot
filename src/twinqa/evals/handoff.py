"""Read-only PR handoff evidence check before review_requested. Pattern: new-case (harness tooling, #584).

The author's PR body must carry, exactly once each, the evidence lines that reviewers kept finding
missing (#124, #247, #311, #583): ``Affected tests:`` on the exact head (the changed modules' tests,
the tests that import them and the new regressions), ``Regression evals:`` verified by
:func:`twinqa.evals.receipt.check_receipt`, ``Before (RED):`` on a commit before the head,
``After (GREEN):`` on the head, and ``Sample output:`` (or ``n/a: <reason>``). The full suite runs once
in the merge batch before main [D297]: ``Full suite:`` is optional, and when present it is either
exactly ``deferred to merge batch (D297)`` or a real ``suite_slot.py`` run on the head or an ancestor.
A missing, duplicated, placeholder or "not run" line is a problem, never a pass; a body that hands
the tests to the reviewer is a problem wherever the sentence stands. Nothing is written.
"""
import re
import subprocess
from pathlib import Path

from twinqa.evals.receipt import check_receipt

FULL, EVALS, RED, GREEN, SAMPLE, AFFECTED = (
    "Full suite", "Regression evals", "Before (RED)", "After (GREEN)", "Sample output", "Affected tests")
REQUIRED = (AFFECTED, EVALS, RED, GREEN, SAMPLE)  # Full suite is optional: merge batch [D297]
FULL_DEFERRED = "deferred to merge batch (D297)"
_DEFERRED = re.compile(r"deferred to merge batch \((?:D297|rule 68)\)")  # exact wording (review r1 P3)
_ALIASES = {"full suite": FULL, "regression evals": EVALS, "before (red)": RED, "red": RED,
            "after (green)": GREEN, "green": GREEN, "sample output": SAMPLE, "affected tests": AFFECTED}
_LABEL = re.compile(r"(?P<label>" + "|".join(re.escape(k) for k in sorted(_ALIASES, key=len, reverse=True))
                    + r")(?:\s*(?P<note>\([^()\n]*\)))?\s*:(?P<value>.*)", re.IGNORECASE)
_SHA = re.compile(r"^[0-9a-f]{40}$")
_HEX = re.compile(r"(?<![0-9A-Za-z])[0-9a-f]{7,40}(?![0-9A-Za-z])")
_PLACEHOLDER = re.compile(r"<[^<>\n]+>")
_NA = re.compile(r"n/a\s*:\s*(?P<reason>.*)", re.IGNORECASE)
_OMISSION = re.compile(r"\b(?:not (?:re-?)?run|not measured|pending|todo|tbd|none|omitted|delegated)\b"
                       r"|(?<![0-9] )\bskipped\b|^\s*n/a\b", re.IGNORECASE)
# Any tests, not only the full suite, stay with the author (review r1 P1, PR #1401). ``tests/x.py`` and
# ``test_x`` are paths/names, not the noun; ``the reviewer's P1`` is a possessive, not a recipient.
_TESTS = (r"(?:full[- ]suite|(?:test[- ])?suite|test[- ]files?|tests?(?![/\\.]\w)|pytest)\b")
_REVIEWER = r"\breviewers?\b(?!['’]s)"
_DELEGATION = (
    re.compile(_REVIEWER + r"(?P<gap>[^.;\n]{0,40}?)\b"
               r"(?:run|runs|rerun|reruns|re-run|re-runs|execute|executes|(?P<inspection>verify|verifies|check|checks))"
               r"\s+(?:(?:the|all|any|remaining|affected|rest of the|full|other|new|my|these|those)\s+){0,3}"
               + _TESTS, re.IGNORECASE),
    re.compile(r"\b" + _TESTS + r"[^.;\n]{0,30}\b(?:delegated|deferred|left|handed|passed on)\b"
               r"[^.;\n]{0,30}" + _REVIEWER, re.IGNORECASE),
    re.compile(r"\b" + _TESTS + r"(?:\s+(?:are|is|go|goes|were|remain|remains|stay|stays|run|over))*"
               r"\s+(?:to|for|by) (?:the )?" + _REVIEWER, re.IGNORECASE),
    re.compile(r"\b(?:delegat|leav|hand|pass)\w*\b[^.;\n]{0,40}\b" + _TESTS + r"[^.;\n]{0,20}\b(?:to|for)\s+"
               r"(?:the )?" + _REVIEWER, re.IGNORECASE),
    re.compile(r"\b" + _TESTS + r"\s+(?:(?:are|is)\s+to|to|will)\s+be\s+"
               r"(?:run|executed|checked|verified)\s+by\s+(?:the\s+)?" + _REVIEWER, re.IGNORECASE),
    re.compile(r"\b" + _TESTS + r"\s*:\s*(?:the\s+)?" + _REVIEWER
               + r"(?=\s*(?:[.;!?\n]|$))", re.IGNORECASE),
    re.compile(r"\bdelegat\w*\b[^.\n]{0,40}\bfull[- ]suite\b", re.IGNORECASE),
)
_EXECUTION_TESTS = re.compile(
    r"\b(?:run|runs|rerun|reruns|re-run|re-runs|execute|executes)\s+"
    r"(?:(?:the|all|any|remaining|affected|rest of the|full|other|new|my|these|those)\s+){0,3}"
    + _TESTS, re.IGNORECASE)
_NEGATION = re.compile(r"\b(?:not|never|no)\b|n't\b", re.IGNORECASE)
# "the reviewer, not the author, runs the tests" negates the author, not the hand-over.
_NOT_AUTHOR = re.compile(r"\b(?:not|never)\s+(?:by\s+)?(?:the\s+)?authors?\b", re.IGNORECASE)


def _negated(line, match):
    """Negation in the same clause, or an explicit empty reviewer assignment (``: none``)."""
    if re.match(r"\s*:\s*none\b(?=\s*(?:[.;!?\n]|$))", line[match.end():], re.IGNORECASE):
        return True
    before = re.split(r"[.;:!?]", line[max(0, match.start() - 40):match.start()])[-1]
    return any(_NEGATION.search(_NOT_AUTHOR.sub(" ", text)) for text in (before, match[0]))


def delegation(line):
    """The first non-negated "tests handed to the reviewer" match in ``line``, or None.

    Every match is tried (``finditer``), so a negated phrase earlier on the line cannot hide a real
    delegation after it; negation does not reach across a clause boundary (review r2 witness).
    A match is negated by not/never/no before it in its clause or inside it
    (``tests are not left to the reviewer``).
    """
    for pattern in _DELEGATION:
        for match in pattern.finditer(line):
            # Checking completed author work is review; requesting another run is delegation.
            if match.groupdict().get("inspection") and re.match(
                    r"\s+(?:I|we|the\s+author)\s+(?:ran|executed|checked|verified)\b",
                    line[match.end():], re.IGNORECASE):
                # Exempt only the inspection, not a subsequent execution in the same clause.
                boundary = re.search(r"[.;!?\n]", line[match.end():])
                end = match.end() + boundary.start() if boundary else len(line)
                for execution in _EXECUTION_TESTS.finditer(line, match.end(), end):
                    if not _negated(line, execution):
                        return execution
                continue
            if not _negated(line, match):
                return match
    return None


def _delegation_problem(match, raw):
    what = "full suite" if re.search(r"full[- ]suite", match[0], re.IGNORECASE) else "tests"
    return (f"{what} delegated to the reviewer: {raw.strip()[:80]!r}; the author runs the affected tests "
            "and the full suite runs in the merge batch (D297)")

_COUNT_TOKEN = re.compile(r"(?:^|(?<=[\s(\[:>,;]))(?P<token>[^\s(\[:>,;]+(?:,\d+)*)\s+"
                          r"(?P<word>passed|failed|errors?)\b", re.IGNORECASE)
_INTEGER = re.compile(r"\d+|\d{1,3}(?:,\d{3})+")
# Scientific notation (``1e00003``) is a malformed count even when it also has the shape of a short hex
# commit id; it is tested before the commit exemption, so it can never default to zero (review r2).
_SCIENTIFIC = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)[eE][-+]?\d+")
_NUMERIC = re.compile(r"^[-+.]?\d|^[-+]?(?:nan|inf(?:inity)?)$", re.IGNORECASE)


def parse_counts(value):
    """``({"passed", "failed", "errors"} -> int or None, malformed)`` for one evidence value.

    A token before ``passed``/``failed``/``error(s)`` is a count only as a plain non-negative integer
    (``13,676`` thousands allowed). A numeric-looking token that is not one (``nan``, ``inf``, ``-1``,
    ``1.5``, ``1e3``, the hex-shaped ``1e00003``, ``0x1``) is reported in ``malformed`` and never counted, so it cannot default to
    zero; a word (``all tests passed``) is no count at all.
    """
    counts, malformed = {"passed": None, "failed": None, "errors": None}, []
    for match in _COUNT_TOKEN.finditer(value):
        token, word = match["token"], match["word"]
        key = "errors" if word.lower().startswith("error") else word.lower()
        if _INTEGER.fullmatch(token):
            counts[key] = (counts[key] or 0) + int(token.replace(",", ""))
        elif _SCIENTIFIC.fullmatch(token):
            malformed.append(f"{token} {word}")
        elif _HEX.fullmatch(token) and re.search(r"[a-f]", token):
            continue  # "3ff7e37 failed": a commit, not a count
        elif _NUMERIC.search(token):
            malformed.append(f"{token} {word}")
    return counts, malformed


def _counts(label, value, problems):
    """Parsed counts of a count-bearing line; each malformed count is a problem naming it."""
    counts, malformed = parse_counts(value)
    for bad in malformed:
        problems.append(f"{label}: malformed count '{bad}' (a non-negative integer is required)")
    return counts, bool(malformed)


def _git(cwd, *args):
    try:
        proc = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    return proc


def head_sha(cwd):
    proc = _git(cwd, "rev-parse", "HEAD")
    return proc.stdout.strip() if proc is not None and proc.returncode == 0 else None


def _resolve(cwd, token):
    proc = _git(cwd, "rev-parse", "--verify", "--quiet", token + "^{commit}")
    return proc.stdout.strip() if proc is not None and proc.returncode == 0 else None


def _commits(cwd, value):
    out = []
    for token in _HEX.findall(value):
        full = _resolve(cwd, token)
        if full and full not in out:
            out.append(full)
    return out


def _ancestor(cwd, older, newer):
    proc = _git(cwd, "merge-base", "--is-ancestor", older, newer)
    return proc is not None and proc.returncode == 0


def _evidence_lines(text):
    """Labelled lines outside fenced code blocks, list/bold/backtick markup removed."""
    found, fenced = {}, False
    for raw in text.splitlines():
        if raw.lstrip().startswith(("```", "~~~")):
            fenced = not fenced
            continue
        if fenced:
            continue
        line = re.sub(r"^[\s\-*+>`]+", "", raw.replace("**", ""))
        match = _LABEL.match(line)
        if match and match["value"].startswith("`"):
            continue  # "`Before (RED):`, `After (GREEN):` ..." mentions a label; it is not evidence
        if match:
            value = match["value"].strip().strip("`").strip()
            note = match["note"]
            if note:
                value = f"{note} {value}"  # `Full suite (suite_slot, head abc1234): ...`
            found.setdefault(_ALIASES[match["label"].lower()], []).append(value)
    return found


def _na(value, label, problems):
    """True when the value is an explicit n/a; records a problem when its reason is empty."""
    match = _NA.match(value)
    if match is None:
        return False
    if not match["reason"].strip():
        problems.append(f"{label}: n/a without a reason")
    return True


def _passing_run(cwd, sha, label, value, problems):
    """GREEN / Affected tests: names the head, >= 1 passed, 0 failed and 0 errors, no omission.

    ``n/a``, ``not run``, ``pending`` ... are not a run, even next to counts copied from elsewhere.
    """
    if delegation(value) is not None or re.search(_REVIEWER + r"[^.;\n]{0,40}\b(?:run|runs|rerun)\b",
                                                  value, re.IGNORECASE):
        problems.append(f"{label}: tests delegated to the reviewer: {value[:80]!r}; the author runs them on "
                        f"head {sha[:12]} (D297)")
        return
    if _NA.match(value) or _OMISSION.search(value):
        problems.append(f"{label} is not evidence: {value[:80]!r}; run the tests on head {sha[:12]}")
        return
    if sha not in _commits(cwd, value):
        problems.append(f"{label} not on head {sha[:12]}")
    counts, malformed = _counts(label, value, problems)
    if malformed:
        return
    if not counts["passed"]:
        problems.append(f"{label} shows no passed count")
    if (counts["failed"] or 0) + (counts["errors"] or 0) > 0:
        problems.append(f"{label} has failures")


def _full_suite(cwd, sha, value, problems):
    """Optional ``Full suite:`` line [D297]: the exact deferral, or a real suite_slot run on head/ancestor."""
    delegated = any(p.search(value) for p in _DELEGATION) or re.search(r"reviewer", value, re.IGNORECASE)
    if delegated or _OMISSION.search(value):
        if delegated:
            problems.append("full suite delegated to the reviewer: the author runs the affected tests and "
                            "the full suite runs in the merge batch (D297)")
        else:
            problems.append(f"full suite is not evidence: {value[:80]!r}")
        return
    if _DEFERRED.fullmatch(value):
        return
    if re.search(r"\bdeferr", value, re.IGNORECASE):
        problems.append(f"full suite deferral must read exactly '{FULL_DEFERRED}': {value[:80]!r}")
        return
    if "suite_slot" not in value:
        problems.append("full suite not run through suite_slot.py (rule 43)")
    commits = _commits(cwd, value)
    if not commits:
        problems.append("full suite names no commit")
    elif sha not in commits and not any(_ancestor(cwd, c, sha) for c in commits):
        problems.append(f"full suite not on head {sha[:12]} or an ancestor of it")
    counts, malformed = _counts(FULL, value, problems)
    if malformed:
        return
    if not counts["passed"]:
        problems.append("full suite shows no passed count")
    bad = (counts["failed"] or 0) + (counts["errors"] or 0)
    if bad and not re.search(r"known #\d+", value):
        problems.append(f"full suite has {bad} failed/errors without a known #<issue> owner")


def check_handoff(text, sha, output, cwd="."):
    """Return the list of handoff evidence problems (empty = complete). Never writes."""
    problems = []
    if not isinstance(sha, str) or not _SHA.fullmatch(sha):
        return [f"sha must be a full 40-hex commit: {sha!r}"]
    if _resolve(cwd, sha) != sha:
        return [f"sha is not a commit in {Path(cwd).resolve()}: {sha}"]
    found = _evidence_lines(text)
    for label in (*REQUIRED, FULL):
        values = found.get(label, [])
        if label in REQUIRED and not values:
            problems.append(f"missing {label}: line")
        if len(values) > 1:
            problems.append(f"duplicate {label}: line ({len(values)})")
    for label, values in found.items():
        for value in values:
            if (hole := _PLACEHOLDER.search(value)) is not None:
                problems.append(f"{label}: unfilled template placeholder {hole[0]}")
    one = {label: values[0] for label, values in found.items() if len(values) == 1}
    affected = one.get(AFFECTED)
    if affected is not None:
        _passing_run(cwd, sha, AFFECTED, affected, problems)
    if FULL in one:
        _full_suite(cwd, sha, one[FULL], problems)
    if EVALS in one:
        try:
            check_receipt(f"{EVALS}: {one[EVALS]}", output)
        except (ValueError, OSError) as exc:
            problems.append("regression evals: " + " ".join(str(exc).splitlines()))
    if RED in one and not _na(one[RED], RED, problems):
        commits = _commits(cwd, one[RED])
        if not commits:
            problems.append("RED names no commit")
        elif not any(c != sha and _ancestor(cwd, c, sha) for c in commits):
            problems.append("RED is not on a commit before head")
        counts, malformed = _counts(RED, one[RED], problems)
        if not malformed and not ((counts["failed"] or 0) + (counts["errors"] or 0)):
            problems.append("RED shows no failure count")
    if GREEN in one:  # GREEN has no n/a: the head always has tests to run (review r1, PR #612)
        _passing_run(cwd, sha, "GREEN", one[GREEN], problems)
    if SAMPLE in one and not _na(one[SAMPLE], SAMPLE, problems):
        if not one[SAMPLE] or _OMISSION.search(one[SAMPLE]):
            problems.append(f"{SAMPLE}: no evidence ({one[SAMPLE]!r}); give a path/inline output or n/a: <reason>")
    fenced = False
    for raw in text.splitlines():
        if raw.lstrip().startswith(("```", "~~~")):
            fenced = not fenced
            continue
        # Quoted literals (fenced blocks, `inline code`) are examples, not the author's statement.
        line = "" if fenced else re.sub(r"`[^`\n]*`", "``", raw)
        if (match := delegation(line)) is not None:
            problems.append(_delegation_problem(match, raw))
    return list(dict.fromkeys(problems))


def check_handoff_file(path, sha, output, cwd="."):
    try:
        text = Path(path).read_bytes().decode("utf-8")
    except FileNotFoundError:
        return [f"body file missing: {path}"]
    except (OSError, UnicodeDecodeError) as exc:
        return [f"body file unreadable (UTF-8 required): {exc}"]
    return check_handoff(text, sha, output, cwd)
