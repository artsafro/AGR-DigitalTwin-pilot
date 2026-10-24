"""Read-only freshness check for a pinned docs/PROJECT_STATE.md snapshot.

Advisory CLI, not a gate and not delivery acceptance. It does not regenerate
the snapshot, choose who refreshes it, or change the open-list cap. Harness
capability lines are ignored. new-case: classify one pinned snapshot against
the git merge window and GitHub open state.

Source report: docs/research/project-state-snapshot-freshness.md
(pin dcb9237b08d0036df232fd4e061f34103bc0e9a7, blob
3f9c7474dfbe6905ce576b93e87d32525510ae2c, content commit
c5f5b5192709efbdbcf190b999eb0c7a4fdf8881; pilot PR #662).
Report proposal 2 is out of scope.

Open window: `gh pr list` is capped at 12. MERGED or CLOSED snapshot rows are
`stale_open`. Limit-12 numbers absent from the snapshot are
`open_window_mismatch` (stale). Snapshot rows that are still OPEN and outside
that full list are `truncated_open` when `total_count` is above 12; that flag
alone stays current. Outside numbers that are not snapshot rows are not
fetched, so a matching twelve-open list with `total_count` 29 is current and
`truncated_open_prs` is empty (#377 and #525 in the report are that case).
`wrong_head` (HEAD sha or origin slug) is never an age diagnostic and never
`current`. Empty, partial, non-finite, and non-integer threshold input is
`evidence_missing`.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

OPEN_LIMIT = 12
_NONFINITE = {
    "nan", "+nan", "-nan", "inf", "+inf", "-inf", "infinity", "+infinity", "-infinity",
}
_JSON_NONFINITE = re.compile(r"\bNaN\b|\bInfinity\b|\b-Infinity\b")
_SLUG = re.compile(r"^[\w.-]+/[\w.-]+$")
_REF = re.compile(r"^[A-Za-z0-9._/@~^+-]+$")
_REMOTE = re.compile(
    r"^(?:https://github\.com/|ssh://git@github\.com/|git://github\.com/|git@github\.com:)"
    r"(?P<slug>[\w.-]+/[\w.-]+?)(?:\.git)?/?$")
_MERGE = re.compile(r"^- `([0-9a-fA-F]{7,40})` Merge pull request #([1-9][0-9]*) from \S.*$")
_OPEN = re.compile(r"^- #([1-9][0-9]*) \S.* \[([^\[\]\s]+)\]( draft)?$")
_LOG = re.compile(r"^([0-9a-fA-F]{40})\tMerge pull request #([1-9][0-9]*) from \S.*$")
_SHA = re.compile(r"^[0-9a-f]{40}$")
_POS = re.compile(r"[1-9][0-9]*")


class _Partial(Exception):
    def __init__(self, reason):
        self.reason = reason
        super().__init__(reason)


def _now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _positive_int(text):
    if not isinstance(text, str):
        raise argparse.ArgumentTypeError("unsupported")
    token = text.strip()
    if token.casefold() in _NONFINITE or token.casefold() in {"true", "false"}:
        raise argparse.ArgumentTypeError("non-finite")
    if not re.fullmatch(r"[0-9]+", token):
        raise argparse.ArgumentTypeError("unsupported")
    value = int(token)
    if value < 1:
        raise argparse.ArgumentTypeError("threshold")
    return value


def _argv_allowed(argv):
    if not isinstance(argv, (list, tuple)) or not argv or any(type(part) is not str or part == "" for part in argv):
        return False
    if argv[0] == "git" and argv[1:] == ["rev-parse", "HEAD"]:
        return True
    if argv[0] == "git" and argv[1:] == ["remote", "get-url", "origin"]:
        return True
    if (len(argv) == 4 and argv[:3] == ["git", "rev-parse", "--verify"]
            and re.fullmatch(r"[A-Za-z0-9._/@~^+-]+\^\{commit\}", argv[3])):
        return True
    if len(argv) == 3 and argv[:2] == ["git", "show"] and re.fullmatch(r"[0-9a-f]{40}:docs/PROJECT_STATE\.md", argv[2]):
        return True
    if (len(argv) == 8 and argv[0] == "git" and argv[1] == "log" and _SHA.fullmatch(argv[2])
            and argv[3:6] == ["--merges", "--grep=^Merge pull request #", "-n"]
            and _POS.fullmatch(argv[6]) and argv[7] == "--format=%H%x09%s"):
        return True
    if (len(argv) == 7 and argv[:4] == ["git", "log", "-1", "--format=%cI"]
            and _SHA.fullmatch(argv[4]) and argv[5:] == ["--", "docs/PROJECT_STATE.md"]):
        return True
    if (len(argv) == 11 and argv[:3] == ["gh", "pr", "list"] and argv[3:5] == ["--repo", argv[4]]
            and _SLUG.fullmatch(argv[4]) and argv[5:] == [
                "--state", "open", "--limit", "12", "--json", "number,title,headRefName,isDraft"]):
        return True
    if (len(argv) == 3 and argv[:2] == ["gh", "api"]
            and re.fullmatch(r"search/issues\?q=repo:[\w.-]+/[\w.-]+\+is:pr\+is:open&per_page=1", argv[2])):
        return True
    if (len(argv) == 8 and argv[:3] == ["gh", "pr", "view"] and _POS.fullmatch(argv[3])
            and argv[4] == "--repo" and _SLUG.fullmatch(argv[5]) and argv[6:] == ["--json", "number,state"]):
        return True
    return False


def _cmd_arg(arg):
    """Keep cmd metacharacters literal across the outer cmd.exe and the .cmd shim."""
    return (arg.replace("%", "%%").replace("^", "^^").replace("&", "^^^&")
            .replace("|", "^^^|").replace("<", "^^^<").replace(">", "^^^>"))


def _resolve(argv):
    found = shutil.which(argv[0])
    if not found:
        raise OSError(argv[0])
    if found.lower().endswith((".cmd", ".bat")):
        comspec = os.environ.get("COMSPEC", "cmd.exe")
        return [comspec, "/d", "/c", found, *[_cmd_arg(part) for part in argv[1:]]]
    return [found, *argv[1:]]


def _run(argv, cwd, timeout):
    """Return (returncode, stdout). Timeout and OSError propagate to the caller."""
    if not _argv_allowed(list(argv)):
        return 2, ""
    completed = subprocess.run(
        _resolve(list(argv)), cwd=str(cwd), capture_output=True, timeout=timeout, check=False)
    return completed.returncode, completed.stdout.decode("utf-8", errors="replace")


def _loads(raw):
    if not isinstance(raw, str) or raw.strip() == "":
        raise _Partial("malformed_json")
    if _JSON_NONFINITE.search(raw):
        raise _Partial("non_finite")

    def pairs(items):
        seen = set()
        for key, _value in items:
            if key in seen:
                raise _Partial("partial_json")
            seen.add(key)
        return dict(items)

    def constant(_name):
        raise _Partial("non_finite")

    try:
        return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)
    except _Partial:
        raise
    except (json.JSONDecodeError, ValueError, TypeError) as exc:
        raise _Partial("malformed_json") from exc


def _parse_snapshot(text):
    if text.strip() == "":
        raise _Partial("empty")
    lines = [line.rstrip("\r") for line in text.splitlines()]
    try:
        prod = next(i for i, line in enumerate(lines) if line.strip() == "## In production")
        harness = next(i for i, line in enumerate(lines) if line.strip() == "## Harness")
    except StopIteration as exc:
        raise _Partial("unsupported_layout") from exc
    if harness < prod:
        raise _Partial("unsupported_layout")
    merges = []
    seen = set()
    for line in lines[prod + 1:harness]:
        if line.strip() == "" or not line.startswith("- "):
            continue
        match = _MERGE.match(line.strip())
        if match is None:
            raise _Partial("unsupported_layout")
        number = int(match.group(2))
        if number in seen:
            raise _Partial("duplicate_numbers")
        seen.add(number)
        merges.append({"sha": match.group(1).lower(), "number": number})
    if not merges:
        raise _Partial("unsupported_layout")
    marker = None
    for index, line in enumerate(lines[harness + 1:], start=harness + 1):
        if line.strip() == "Open pull requests:":
            marker = index
            break
        if line.startswith("## "):
            break
    if marker is None:
        raise _Partial("unsupported_layout")
    opens = []
    open_seen = set()
    body = []
    for line in lines[marker + 1:]:
        if line.strip() == "" or line.startswith("## "):
            break
        body.append(line.strip())
    if body == ["- (none)"]:
        return merges, []
    if not body:
        raise _Partial("unsupported_layout")
    for line in body:
        match = _OPEN.match(line)
        if match is None:
            raise _Partial("unsupported_layout")
        number = int(match.group(1))
        if number in open_seen:
            raise _Partial("duplicate_numbers")
        open_seen.add(number)
        opens.append(number)
    return merges, opens


def _parse_log(text, limit):
    rows = []
    seen = set()
    for line in text.splitlines():
        if line.strip() == "":
            continue
        match = _LOG.match(line.rstrip("\r"))
        if match is None:
            raise _Partial("git_failed")
        number = int(match.group(2))
        if number in seen:
            raise _Partial("duplicate_numbers")
        seen.add(number)
        rows.append({"sha": match.group(1).lower(), "number": number})
    if len(rows) > limit:
        raise _Partial("git_failed")
    if not rows:
        raise _Partial("empty")
    return rows


def _parse_list(raw):
    data = _loads(raw)
    if not isinstance(data, list):
        raise _Partial("partial_json")
    numbers = []
    seen = set()
    for item in data:
        if not isinstance(item, dict):
            raise _Partial("partial_json")
        if any(key not in item for key in ("number", "title", "headRefName", "isDraft")):
            raise _Partial("partial_json")
        number = item["number"]
        if isinstance(number, bool) or not isinstance(number, int) or number <= 0:
            raise _Partial("partial_json")
        if not isinstance(item["title"], str) or item["title"].strip() == "" or "\n" in item["title"]:
            raise _Partial("partial_json")
        if not isinstance(item["headRefName"], str) or item["headRefName"].strip() == "":
            raise _Partial("partial_json")
        if not isinstance(item["isDraft"], bool):
            raise _Partial("partial_json")
        if number in seen:
            raise _Partial("duplicate_numbers")
        seen.add(number)
        numbers.append(number)
    if len(numbers) > OPEN_LIMIT:
        raise _Partial("open_list_incomplete")
    return numbers


def _parse_search(raw):
    data = _loads(raw)
    if not isinstance(data, dict) or "total_count" not in data or "incomplete_results" not in data:
        raise _Partial("partial_json")
    total = data["total_count"]
    flag = data["incomplete_results"]
    if isinstance(total, bool) or not isinstance(total, int) or total < 0:
        raise _Partial("partial_json")
    if not isinstance(flag, bool):
        raise _Partial("partial_json")
    if flag:
        raise _Partial("incomplete_results")
    return total


def _parse_view(raw, expected):
    data = _loads(raw)
    if not isinstance(data, dict) or "number" not in data or "state" not in data:
        raise _Partial("partial_json")
    number = data["number"]
    state = data["state"]
    if isinstance(number, bool) or not isinstance(number, int) or number != expected:
        raise _Partial("partial_json")
    if state not in {"OPEN", "MERGED", "CLOSED"}:
        raise _Partial("partial_json")
    return state


def _merge_gap(window, snap):
    stale = []
    index = 0
    leftovers = []
    for row in snap:
        matched = False
        while index < len(window):
            candidate = window[index]
            index += 1
            if candidate["number"] == row["number"]:
                if not candidate["sha"].startswith(row["sha"]):
                    stale.append(candidate["number"])
                matched = True
                break
            stale.append(candidate["number"])
        if not matched:
            leftovers.append(row["number"])
    while index < len(window):
        stale.append(window[index]["number"])
        index += 1
    return stale, leftovers


def _opens(snap, states, listed, total):
    stale_open = []
    still = []
    for number in snap:
        state = states.get(number)
        if state in {"MERGED", "CLOSED"}:
            stale_open.append(number)
        elif state == "OPEN":
            still.append(number)
    listed_set = set(listed)
    missing = [number for number in listed if number not in set(snap)]
    outside = [number for number in still if number not in listed_set]
    diags = []
    truncated = False
    truncated_prs = []
    if stale_open:
        diags.append("stale_open")
    if missing or (outside and not (total > OPEN_LIMIT and len(listed) == OPEN_LIMIT and set(listed) <= set(still))):
        diags.append("open_window_mismatch")
    elif total > OPEN_LIMIT and len(listed) == OPEN_LIMIT and set(listed) <= set(still) and not missing:
        truncated = True
        truncated_prs = outside
    if set(listed) & set(stale_open):
        raise _Partial("open_list_incomplete")
    return diags, stale_open, truncated, truncated_prs


def _payload(checked, repo, expected, **fields):
    data = {
        "pin": None, "repo": repo, "expected_origin": expected, "origin": None, "head": None,
        "source_timestamp": None, "checked_at": checked, "status": "evidence_missing",
        "diagnostics": [], "wrong_head": False, "truncated_open": False, "stale_open_prs": [],
        "stale_merges_prs": [], "truncated_open_prs": [], "evidence_missing": [],
    }
    data.update(fields)
    return data


def _capture(argv, cwd, timeout, problems, reason):
    try:
        code, out = _run(argv, cwd, timeout)
    except subprocess.TimeoutExpired:
        problems.append("timeout")
        return None
    except TimeoutError:
        problems.append("timeout")
        return None
    except OSError:
        problems.append("gh_failed" if argv and argv[0] == "gh" else "git_failed")
        return None
    if code != 0:
        problems.append(reason)
        return None
    return out


def _sha(text):
    token = (text or "").strip().lower()
    return token if _SHA.fullmatch(token) else None


def evaluate(repo, ref, expected_origin, max_merges, timeout):
    checked = _now()
    problems = []
    try:
        repo_text = str(Path(repo).resolve())
    except (OSError, RuntimeError, ValueError):
        repo_text = None
        problems.append("invalid_args")
    if type(ref) is not str or _REF.fullmatch(ref) is None:
        problems.append("invalid_args")
    if type(expected_origin) is not str or _SLUG.fullmatch(expected_origin) is None:
        problems.append("invalid_args")
    if isinstance(max_merges, bool) or type(max_merges) is not int or max_merges < 1:
        problems.append("invalid_args")
    if isinstance(timeout, bool) or type(timeout) is not int or timeout < 1:
        problems.append("invalid_args")
    if problems or repo_text is None:
        return _payload(checked, repo_text, expected_origin if type(expected_origin) is str else None,
                        evidence_missing=sorted(set(problems or ["invalid_args"])))

    pin = head = origin = stamp = None
    merges = opens = window = None
    listed = total = None
    states = {}
    verified = _capture(
        ["git", "rev-parse", "--verify", f"{ref}^{{commit}}"], repo_text, timeout, problems, "unresolvable_ref")
    if verified is not None:
        pin = _sha(verified)
        if pin is None:
            problems.append("unresolvable_ref")
    head_raw = _capture(["git", "rev-parse", "HEAD"], repo_text, timeout, problems, "git_failed")
    if head_raw is not None:
        head = _sha(head_raw)
        if head is None:
            problems.append("git_failed")
    remote = _capture(["git", "remote", "get-url", "origin"], repo_text, timeout, problems, "git_failed")
    if remote is not None:
        match = _REMOTE.fullmatch(remote.strip().splitlines()[0].strip() if remote.strip() else "")
        if match is None:
            problems.append("unsupported_origin")
        else:
            origin = match.group("slug")
    if pin is not None:
        blob = _capture(["git", "show", f"{pin}:docs/PROJECT_STATE.md"], repo_text, timeout, problems, "missing_blob")
        if blob is not None:
            try:
                merges, opens = _parse_snapshot(blob)
            except _Partial as exc:
                problems.append(exc.reason)
        log = _capture(
            ["git", "log", pin, "--merges", "--grep=^Merge pull request #", "-n", str(max_merges),
             "--format=%H%x09%s"],
            repo_text, timeout, problems, "git_failed")
        if log is not None:
            try:
                window = _parse_log(log, max_merges)
            except _Partial as exc:
                problems.append(exc.reason)
        stamped = _capture(
            ["git", "log", "-1", "--format=%cI", pin, "--", "docs/PROJECT_STATE.md"],
            repo_text, timeout, problems, "git_failed")
        if stamped is not None:
            stamp = stamped.strip()
            if stamp == "" or stamp.casefold() in _NONFINITE:
                problems.append("empty" if stamp == "" else "non_finite")
                stamp = None
    if origin is not None and opens is not None:
        raw_list = _capture(
            ["gh", "pr", "list", "--repo", origin, "--state", "open", "--limit", "12",
             "--json", "number,title,headRefName,isDraft"],
            repo_text, timeout, problems, "gh_failed")
        if raw_list is not None:
            try:
                listed = _parse_list(raw_list)
            except _Partial as exc:
                problems.append(exc.reason)
        raw_search = _capture(
            ["gh", "api", f"search/issues?q=repo:{origin}+is:pr+is:open&per_page=1"],
            repo_text, timeout, problems, "gh_failed")
        if raw_search is not None:
            try:
                total = _parse_search(raw_search)
            except _Partial as exc:
                problems.append(exc.reason)
        for number in opens:
            raw_view = _capture(
                ["gh", "pr", "view", str(number), "--repo", origin, "--json", "number,state"],
                repo_text, timeout, problems, "gh_failed")
            if raw_view is None:
                continue
            try:
                states[number] = _parse_view(raw_view, number)
            except _Partial as exc:
                problems.append(exc.reason)
    diags = []
    stale_merges = []
    stale_open = []
    truncated = False
    truncated_prs = []
    if merges is not None and window is not None:
        stale_merges, leftovers = _merge_gap(window, merges)
        if stale_merges or leftovers:
            diags.append("stale_merges")
    if opens is not None and listed is not None and total is not None and not any(
            item in problems for item in ("gh_failed", "timeout", "partial_json", "malformed_json",
                                          "non_finite", "duplicate_numbers", "incomplete_results",
                                          "open_list_incomplete")):
        if total < len(listed) or (len(listed) == 0 and total != 0) or (
                total > len(listed) and len(listed) != OPEN_LIMIT):
            problems.append("total_count_short" if total < len(listed) else "open_list_incomplete")
        elif len(opens) != len(states):
            problems.append("partial_json")
        else:
            try:
                open_diags, stale_open, truncated, truncated_prs = _opens(opens, states, listed, total)
            except _Partial as exc:
                problems.append(exc.reason)
            else:
                diags.extend(open_diags)
    wrong = bool(pin and head and pin != head) or bool(origin and origin.casefold() != expected_origin.casefold())
    evidence = sorted(set(problems))
    diags = sorted(set(diags))
    if evidence:
        status = "evidence_missing"
        truncated = False
        truncated_prs = []
    elif diags or wrong:
        status = "stale"
    else:
        status = "current"
    return _payload(
        checked, repo_text, expected_origin, pin=pin, origin=origin, head=head, source_timestamp=stamp,
        status=status, diagnostics=diags, wrong_head=wrong, truncated_open=truncated,
        stale_open_prs=stale_open, stale_merges_prs=stale_merges, truncated_open_prs=truncated_prs,
        evidence_missing=evidence)


def _exit(payload):
    if payload["status"] == "evidence_missing" or payload["evidence_missing"]:
        return 2
    if payload["status"] != "current" or payload["wrong_head"]:
        return 1
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="Read-only PROJECT_STATE freshness check.")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--ref", required=True)
    parser.add_argument("--expected-origin", required=True)
    parser.add_argument("--max-merges", type=_positive_int, default=12)
    parser.add_argument("--timeout", type=_positive_int, default=30)
    args = parser.parse_args(argv)
    payload = evaluate(args.repo, args.ref, args.expected_origin, args.max_merges, args.timeout)
    sys.stdout.write(json.dumps(payload, sort_keys=True) + "\n")
    return _exit(payload)


if __name__ == "__main__":
    sys.exit(main())
