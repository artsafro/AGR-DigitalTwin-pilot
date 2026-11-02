"""Read-only PR handoff evidence check before review_requested. Pattern: new-case (harness tooling, #584).

The author's PR body must carry, exactly once each, the evidence lines that reviewers kept finding
missing (#124, #247, #311, #583): ``Full suite:`` run through ``suite_slot.py`` on the exact head,
``Regression evals:`` verified by :func:`twinqa.evals.receipt.check_receipt`, ``Before (RED):`` on
a commit before the head, ``After (GREEN):`` on the head, and ``Sample output:`` (or ``n/a: <reason>``).
A missing, duplicated, placeholder or "not run" line is a problem, never a pass; a body that hands
the full suite to the reviewer is a problem wherever the sentence stands. Nothing is written.
"""
import re
import subprocess
from pathlib import Path

from twinqa.evals.receipt import check_receipt

FULL, EVALS, RED, GREEN, SAMPLE, AFFECTED = (
    "Full suite", "Regression evals", "Before (RED)", "After (GREEN)", "Sample output", "Affected tests")
REQUIRED = (FULL, EVALS, RED, GREEN, SAMPLE)
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
_DELEGATION = (
    re.compile(r"\breviewers?\b(?P<gap>[^.\n]{0,60}?)\b(?:run|runs|rerun|re-run|execute|executes)\b"
               r"[^.\n]{0,30}\bfull[- ]suite", re.IGNORECASE),
    re.compile(r"\bfull[- ]suite\b[^.\n]{0,60}\b(?:delegated|deferred|left|handed|passed on)\b"
               r"[^.\n]{0,30}\breviewers?\b", re.IGNORECASE),
    re.compile(r"\bfull[- ]suite\b[^.\n]{0,30}\b(?:to|for|by) (?:the )?reviewers?\b", re.IGNORECASE),
    re.compile(r"\bdelegat\w*\b[^.\n]{0,40}\bfull[- ]suite\b", re.IGNORECASE),
)
_NEGATION = re.compile(r"\b(?:not|never|no)\b|n't\b", re.IGNORECASE)


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


def _full_suite(cwd, sha, value, affected, problems):
    if _OMISSION.search(value) or any(p.search(value) for p in _DELEGATION):
        if any(p.search(value) for p in _DELEGATION) or re.search(r"reviewer", value, re.IGNORECASE):
            problems.append("full suite delegated to the reviewer: the author runs it (rule 49)")
        else:
            problems.append(f"full suite is not evidence: {value[:80]!r}")
        return
    if "suite_slot" not in value:
        problems.append("full suite not run through suite_slot.py (rule 43)")
    commits = _commits(cwd, value)
    if not commits:
        problems.append("full suite names no commit")
    elif sha not in commits:
        older = [c for c in commits if _ancestor(cwd, c, sha)]
        if not older or not affected:
            problems.append(f"full suite not on head {sha[:12]} (a rework needs an Affected tests line on head)")
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
    for label in (*REQUIRED, AFFECTED):
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
        _full_suite(cwd, sha, one[FULL], affected is not None, problems)
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
        for pattern in _DELEGATION:
            match = pattern.search(line)
            negated = (_NEGATION.search(line[max(0, match.start() - 40):match.start()]) or
                       (match.groupdict().get("gap") and _NEGATION.search(match["gap"]))) if match else False
            if match and not negated:
                problems.append(f"full suite delegated to the reviewer: {raw.strip()[:80]!r}")
                break
    return list(dict.fromkeys(problems))


def check_handoff_file(path, sha, output, cwd="."):
    try:
        text = Path(path).read_bytes().decode("utf-8")
    except FileNotFoundError:
        return [f"body file missing: {path}"]
    except (OSError, UnicodeDecodeError) as exc:
        return [f"body file unreadable (UTF-8 required): {exc}"]
    return check_handoff(text, sha, output, cwd)
