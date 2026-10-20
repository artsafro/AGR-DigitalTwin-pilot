"""Local CI receipt (D122). Stdlib only.

Print a fenced ``CI-RECEIPT v1`` block for the PR body, or check a pasted block:

    uv run python tools/ci_receipt.py [--issue N] [--basetemp PATH] [--out PATH]
    uv run python tools/ci_receipt.py --verify FILE --sha FULL_SHA [--out PATH]

Agreed commands, each started with PYTHONPATH, PYTHONHOME and VIRTUAL_ENV removed:
``uv run -q pytest -q``, ``uv run dt profiles check``, ``uv run dt schemas --check``.
On Windows, pytest receives ``--basetemp`` under ``C:/x/ci-receipt-<sha>/<unique>``
unless ``--basetemp`` is set. Missing ancestors of that default path are created
before pytest; the leaf itself is left for pytest. Other platforms keep pytest's
own basetemp unless ``--basetemp`` is set. With ``--issue N`` the ready-gate
command is also run;
without it that command is ``not_run``. PASS only when every run command exits 0,
pytest collected at least one test, failed and errors are 0, and
``git status --porcelain`` is empty. ``--verify`` does not rewrite its input.
An ``--out`` path that resolves to that input or to ``--basetemp``, or whose
parent directory is missing, exits nonzero and writes nothing.
"""
import argparse
import math
import os
import platform
import re
import shlex
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

PYTEST_CMD = "uv run -q pytest -q"
PROFILES_CMD = "uv run dt profiles check"
SCHEMAS_CMD = "uv run dt schemas --check"
GATE_NOT_RUN = "uv run -q python tools/check_ready_gate.py --repo artsafro/AGR-DigitalTwin-pilot"
GATE_RUN = "uv run -q python tools/check_ready_gate.py --issue {issue} --repo artsafro/AGR-DigitalTwin-pilot"
REQUIRED = (PYTEST_CMD, PROFILES_CMD, SCHEMAS_CMD)
COUNT_KEYS = ("passed", "failed", "errors", "skipped", "deselected", "xfailed", "xpassed")
HEADER_KEYS = (
    "commit", "branch", "dirty", "started_utc", "duration_s", "os", "python", "uv", "scrubbed",
)
SCRUB_KEYS = frozenset({"PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"})
SCRUBBED = "PYTHONPATH,PYTHONHOME,VIRTUAL_ENV"
_NONFINITE_BASETEMP = re.compile(r"(?i)^[+-]?(?:nan|inf|infinity)$")
UTC_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
SHA_RE = re.compile(r"[0-9a-f]{40}")
ISSUE_RE = re.compile(r"[1-9][0-9]*")
COUNT_RE = re.compile(r"0|[1-9][0-9]*")
_WORD = r"passed|failed|errors|error|skipped|deselected|xfailed|xpassed|warnings|warning"
SUMMARY_RE = re.compile(
    rf"^(?:={3,}\s*)?(?:(?P<no>no tests ran)|(?P<counts>(?:\d+ (?:{_WORD})(?:, )?)+))"
    rf" in [\d.]+s(?: \([^)]*\))?\s*(?:={3,})?\s*$"
)
_WORD_RE = re.compile(rf"(\d+) ({_WORD})")
_COLLECTED = ("passed", "failed", "errors", "skipped", "xfailed", "xpassed")


def child_env(base=None):
    """Environment for a child process with parent PYTHONPATH, PYTHONHOME and VIRTUAL_ENV removed."""
    source = os.environ if base is None else base
    return {key: value for key, value in source.items() if key.upper() not in SCRUB_KEYS}


def _platform_name():
    return os.name


def _normalize_basetemp(value):
    text = value.replace("\\", "/")
    drive = ""
    rest = text
    if len(text) >= 2 and text[1] == ":":
        drive = text[:2]
        rest = text[2:]
    parts = []
    for part in rest.split("/"):
        if part in {"", "."}:
            continue
        if part == "..":
            if parts:
                parts.pop()
            continue
        parts.append(part)
    tail = "/".join(parts)
    if drive:
        return f"{drive}/{tail}" if tail else drive
    return tail


def _basetemp_problem(value, sha=None):
    """Fail closed for empty, partial, non-finite and shared-root basetemp paths."""
    if not isinstance(value, str):
        return "basetemp unsupported"
    if value.strip() == "":
        return "basetemp empty"
    if value != value.strip():
        return "basetemp partial"
    if _NONFINITE_BASETEMP.fullmatch(value):
        return "basetemp non-finite"
    if "\x00" in value:
        return "basetemp unsupported"
    normalized = _normalize_basetemp(value).casefold()
    if normalized in {"", "c:"}:
        return "basetemp unsupported"
    if normalized == "c:/x":
        return "basetemp at threshold"
    if sha and SHA_RE.fullmatch(sha):
        if normalized == f"c:/x/ci-receipt-{sha}".casefold():
            return "basetemp at threshold"
    return None


def _default_basetemp(sha):
    token = sha if SHA_RE.fullmatch(sha or "") else "unknown"
    leaf = f"{os.getpid()}-{time.time_ns()}-{uuid.uuid4().hex}"
    return f"C:/x/ci-receipt-{token}/{leaf}"


def _ensure_default_basetemp_parent(basetemp):
    """Create missing ancestors of the default basetemp. Leave the leaf for pytest."""
    leaf = Path(basetemp)
    parent = leaf.parent
    if parent == leaf:
        return "basetemp parent not created"
    try:
        parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        return "basetemp parent not created"
    if not parent.is_dir():
        return "basetemp parent not created"
    return None


def _pytest_command(basetemp):
    argv = ["uv", "run", "-q", "pytest", "-q"]
    if basetemp is not None:
        argv.extend(["--basetemp", basetemp])
    return shlex.join(argv)


def _classify_pytest(command, sha):
    try:
        argv = shlex.split(command, posix=True)
    except ValueError:
        return "bad-basetemp"
    if argv[:5] != ["uv", "run", "-q", "pytest", "-q"]:
        return "not-pytest"
    if len(argv) == 5:
        return "ok"
    if len(argv) == 7 and argv[5] == "--basetemp" and _basetemp_problem(argv[6], sha) is None:
        return "ok"
    return "bad-basetemp"


def planned_commands(issue):
    """Agreed checks. ``issue`` None keeps the ready gate as not_run."""
    commands = [(PYTEST_CMD, "run"), (PROFILES_CMD, "run"), (SCHEMAS_CMD, "run")]
    if issue is None:
        commands.append((GATE_NOT_RUN, "not_run"))
    else:
        commands.append((GATE_RUN.format(issue=issue), "run"))
    return commands


def default_runner(argv, env, cwd):
    return subprocess.run(
        argv, env=env, cwd=str(cwd), capture_output=True, text=True,
        encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL,
    )


def _git(args, cwd):
    try:
        proc = subprocess.run(
            ["git", "-c", "safe.directory=*", *args], cwd=str(cwd), env=child_env(),
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            stdin=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout


def parse_pytest_summary(text):
    """Last pytest summary line as counts, or None when the summary is unparseable.

    ``no tests ran`` and a summary that only deselects or warns are known zeros.
    A missing or garbled summary is None, never a fabricated zero.
    """
    matched = None
    raw = None
    for line in (text or "").splitlines():
        found = SUMMARY_RE.match(line.strip())
        if found:
            matched = found
            raw = line.strip()
    if matched is None:
        return None, "unknown"
    counts = {key: 0 for key in COUNT_KEYS}
    if matched.group("counts"):
        for number, word in _WORD_RE.findall(matched.group("counts")):
            key = {"error": "errors"}.get(word, word)
            if key in {"warning", "warnings"}:
                continue
            counts[key] = int(number)
    return counts, raw


def _collected(counts):
    return sum(counts[key] for key in _COLLECTED)


def _is_pytest(command):
    return "pytest" in shlex.split(command, posix=True)


def _duration(started):
    elapsed = time.perf_counter() - started
    if not math.isfinite(elapsed) or elapsed < 0:
        elapsed = 0.0
    return f"{elapsed:.3f}"


def _run_command(command, runner, cwd):
    argv = shlex.split(command, posix=True)
    started = time.perf_counter()
    try:
        completed = runner(argv, child_env(), cwd)
    except FileNotFoundError:
        return {
            "command": command, "found": False, "duration_s": _duration(started),
            "pytest": _is_pytest(command),
        }
    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    record = {
        "command": command, "found": True, "exit_code": int(completed.returncode),
        "duration_s": _duration(started), "pytest": _is_pytest(command),
    }
    if record["pytest"]:
        counts, summary = parse_pytest_summary(stdout + "\n" + stderr)
        record["counts"] = counts
        record["summary"] = summary
    return record


def _evaluate(records, dirty, git_ok, uv_known):
    reasons = []
    if not git_ok:
        reasons.append("git status unavailable")
    if dirty:
        reasons.append("dirty worktree")
    if not uv_known:
        reasons.append("uv version unknown")
    saw_pytest = False
    for record in records:
        if record.get("status") == "not_run":
            continue
        if not record.get("found", True):
            reasons.append("command not found")
            continue
        if record["exit_code"] != 0:
            reasons.append(f"command exit {record['exit_code']}")
        if not record.get("pytest"):
            continue
        saw_pytest = True
        counts = record.get("counts")
        if counts is None:
            reasons.append("pytest summary unparseable")
            continue
        if counts["failed"] != 0:
            reasons.append(f"pytest failed {counts['failed']}")
        if counts["errors"] != 0:
            reasons.append(f"pytest errors {counts['errors']}")
        if _collected(counts) <= 0:
            reasons.append("pytest collected 0")
    if not saw_pytest:
        reasons.append("pytest did not run")
    return reasons


def format_receipt(header, records, reasons):
    result = "FAIL" if reasons else "PASS"
    lines = ["```ci-receipt", "CI-RECEIPT v1"]
    for key in HEADER_KEYS:
        lines.append(f"{key}: {header[key]}")
    for record in records:
        lines.append(f"command: {record['command']}")
        if record.get("status") == "not_run":
            lines.append("status: not_run")
            lines.append(f"reason: {record['reason']}")
            continue
        if not record.get("found", True):
            lines.append(f"duration_s: {record['duration_s']}")
            lines.append("reason: command not found")
        else:
            lines.append(f"exit_code: {record['exit_code']}")
            lines.append(f"duration_s: {record['duration_s']}")
        if record.get("pytest"):
            counts = record.get("counts")
            lines.append(f"summary: {record.get('summary', 'unknown')}")
            for key in COUNT_KEYS:
                lines.append(f"{key}: {counts[key] if counts is not None else 'unknown'}")
    for reason in reasons:
        lines.append(f"reason: {reason}")
    lines.append(f"result: {result}")
    lines.append("```")
    return "\n".join(lines) + "\n"


def _same_path(left, right):
    left_path, right_path = Path(left), Path(right)
    try:
        if left_path.resolve() == right_path.resolve():
            return True
    except OSError:
        return False
    try:
        return left_path.exists() and right_path.exists() and os.path.samefile(left_path, right_path)
    except OSError:
        return False


def _out_problem(path):
    if path is None:
        return None
    if not str(path).strip():
        return "output path empty"
    dest = Path(path)
    if not dest.parent.exists() or not dest.parent.is_dir():
        return "output directory missing"
    if dest.exists() and dest.is_dir():
        return "output path is a directory"
    return None


def _write_out(path, text):
    problem = _out_problem(path)
    if problem:
        return problem
    destination = Path(path)
    temporary = destination.with_name(destination.name + ".ci-receipt-tmp")
    try:
        temporary.write_text(text, encoding="utf-8", newline="\n")
        os.replace(temporary, destination)
    except OSError:
        try:
            temporary.unlink()
        except OSError:
            pass
        return "output path not written"
    return None


def produce(issue, runner, cwd, basetemp=None):
    started_at = time.perf_counter()
    started_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    sha = (_git(["rev-parse", "HEAD"], cwd) or "").strip()
    effective = basetemp
    parent_problem = None
    if effective is None and _platform_name() == "nt":
        effective = _default_basetemp(sha)
        parent_problem = _ensure_default_basetemp_parent(effective)

    if parent_problem:
        uv_value = "unknown"
        records = []
    else:
        try:
            version = runner(["uv", "--version"], child_env(), cwd)
            uv_text = (version.stdout or version.stderr or "").strip().splitlines()
            uv_value = uv_text[0] if version.returncode == 0 and uv_text else "unknown"
        except FileNotFoundError:
            uv_value = "unknown"
        records = []
        for command, mode in planned_commands(issue):
            if mode == "not_run":
                records.append({
                    "command": command, "status": "not_run", "reason": "--issue not given", "pytest": False,
                })
                continue
            if command == PYTEST_CMD:
                command = _pytest_command(effective)
            records.append(_run_command(command, runner, cwd))
    branch = (_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd) or "").strip()
    status = _git(["status", "--porcelain"], cwd)
    git_ok = bool(SHA_RE.fullmatch(sha)) and bool(branch) and status is not None
    dirty = (not git_ok) or any(line.strip() for line in status.splitlines())
    header = {
        "commit": sha if git_ok else "unknown",
        "branch": branch if branch else "unknown",
        "dirty": "yes" if dirty else "no",
        "started_utc": started_utc,
        "duration_s": _duration(started_at),
        "os": platform.platform(),
        "python": platform.python_version(),
        "uv": uv_value,
        "scrubbed": SCRUBBED,
    }
    reasons = _evaluate(records, dirty, git_ok, uv_value != "unknown")
    if parent_problem:
        reasons.insert(0, parent_problem)
    return format_receipt(header, records, reasons), reasons


def _take(body, expected):
    if not body:
        return None, "partial receipt"
    key, sep, value = body[0].partition(": ")
    if sep != ": " or key != expected:
        return None, "partial receipt"
    body.pop(0)
    return value, None


def _finite_duration(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(number) and number >= 0


def _verify_reason(text, sha):
    if text is None or not str(text).strip():
        return "empty receipt"
    if not SHA_RE.fullmatch(sha or ""):
        return "sha mismatch"
    lines = str(text).splitlines()
    starts = [index for index, line in enumerate(lines) if line.strip().startswith("CI-RECEIPT")]
    if not starts:
        return "missing CI-RECEIPT v1"
    if len(starts) != 1:
        return "multiple receipts"
    if lines[starts[0]].strip() != "CI-RECEIPT v1":
        return "unsupported receipt version"
    body = []
    for line in lines[starts[0] + 1:]:
        if line.strip() == "```":
            break
        body.append(line.strip())
    header = {}
    for key in HEADER_KEYS:
        value, problem = _take(body, key)
        if problem:
            return problem
        header[key] = value
    if header["commit"] != sha:
        return "sha mismatch"
    if header["dirty"] not in {"yes", "no"}:
        return "partial receipt"
    if not header["branch"] or header["branch"] == "unknown":
        return "partial receipt"
    if not UTC_RE.fullmatch(header["started_utc"]):
        return "partial receipt"
    if not _finite_duration(header["duration_s"]):
        return "non-finite duration"
    if not header["os"] or not header["python"] or not header["uv"] or header["uv"] == "unknown":
        return "partial receipt"
    if header["scrubbed"] != SCRUBBED:
        return "partial receipt"
    commands = []
    while body and body[0].startswith("command: "):
        command = body.pop(0).split(": ", 1)[1]
        if not command:
            return "missing command"
        if _classify_pytest(command, header["commit"]) == "bad-basetemp":
            return "basetemp rejected"
        record = {"command": command}
        if not body:
            return "partial receipt"
        if body[0].startswith("status: "):
            status = body.pop(0).split(": ", 1)[1]
            reason, problem = _take(body, "reason")
            if problem or status != "not_run" or not reason:
                return "partial receipt"
            record["status"] = "not_run"
            commands.append(record)
            continue
        if body[0].startswith("reason: "):
            return "command not found"
        exit_code, problem = _take(body, "exit_code")
        if problem:
            return problem
        duration, problem = _take(body, "duration_s")
        if problem:
            return problem
        if not COUNT_RE.fullmatch(exit_code or ""):
            return "partial receipt"
        if not _finite_duration(duration):
            return "non-finite duration"
        record["exit_code"] = int(exit_code)
        if _is_pytest(command):
            summary, problem = _take(body, "summary")
            if problem:
                return problem
            counts = {}
            for key in COUNT_KEYS:
                token, problem = _take(body, key)
                if problem:
                    return problem
                if token == "unknown":
                    return "counts unknown"
                if not COUNT_RE.fullmatch(token or ""):
                    return "invalid count"
                counts[key] = int(token)
            parsed, raw = parse_pytest_summary(summary)
            if parsed is None or raw != summary:
                return "counts inconsistent with summary"
            if parsed != counts:
                return "counts inconsistent with summary"
            record["counts"] = counts
        commands.append(record)
    while body and body[0].startswith("reason: "):
        body.pop(0)
    if len(body) != 1 or not body[0].startswith("result: "):
        return "partial receipt"
    result = body[0].split(": ", 1)[1]
    if result != "PASS":
        return "result is not PASS"
    if header["dirty"] != "no":
        return "dirty worktree"
    by_command = {}
    for record in commands:
        if record["command"] in by_command:
            return "missing command"
        by_command[record["command"]] = record
    pytest_records = [
        record for record in commands
        if _classify_pytest(record["command"], header["commit"]) == "ok"
    ]
    if len(pytest_records) != 1:
        return f"missing command: {PYTEST_CMD}"
    pytest_record = pytest_records[0]
    if pytest_record.get("status") == "not_run" or "exit_code" not in pytest_record:
        return f"missing command: {PYTEST_CMD}"
    if pytest_record["exit_code"] != 0:
        return f"command exit {pytest_record['exit_code']}"
    for required in REQUIRED:
        if required == PYTEST_CMD:
            continue
        record = by_command.get(required)
        if record is None or record.get("status") == "not_run":
            return f"missing command: {required}"
        if record["exit_code"] != 0:
            return f"command exit {record['exit_code']}"
    counts = pytest_record["counts"]
    if counts["failed"] != 0 or counts["errors"] != 0:
        return "result PASS conflicts with failed"
    if _collected(counts) <= 0:
        return "pytest collected 0"
    gates = [record for record in commands if record["command"].startswith(
        "uv run -q python tools/check_ready_gate.py")]
    if len(gates) != 1:
        return "missing command"
    gate = gates[0]
    if gate.get("status") == "not_run":
        if gate["command"] != GATE_NOT_RUN:
            return "missing command"
    elif gate["exit_code"] != 0:
        return f"command exit {gate['exit_code']}"
    elif not (
        gate["command"] == GATE_NOT_RUN
        or re.fullmatch(
            r"uv run -q python tools/check_ready_gate.py --issue [1-9][0-9]* "
            r"--repo artsafro/AGR-DigitalTwin-pilot",
            gate["command"],
        )
    ):
        return "missing command"
    known = {pytest_record["command"], PROFILES_CMD, SCHEMAS_CMD, gate["command"]}
    if set(by_command) != known:
        return "unexpected command"
    return None


def verify_text(text, sha):
    reason = _verify_reason(text, sha)
    if reason:
        return 1, reason
    return 0, ""


def _parser():
    parser = argparse.ArgumentParser(description="Print or verify a local CI receipt (D122).")
    parser.add_argument("--issue", default=None)
    parser.add_argument("--verify", default=None)
    parser.add_argument("--sha", default=None)
    parser.add_argument("--basetemp", default=None)
    parser.add_argument("--out", default=None)
    return parser


def run(argv=None, runner=None):
    if runner is None:
        runner = default_runner
    try:
        args = _parser().parse_args(argv)
    except SystemExit as exc:
        return int(exc.code) if exc.code else 2
    if args.issue is not None and not ISSUE_RE.fullmatch(args.issue):
        print("reason: invalid issue", file=sys.stderr)
        return 2
    if args.out is not None and args.verify and _same_path(args.out, args.verify):
        print("reason: output path resolves to input", file=sys.stderr)
        return 2
    if args.verify:
        if not args.sha:
            print("reason: sha mismatch", file=sys.stderr)
            return 2
        path = Path(args.verify)
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            print("reason: missing receipt file", file=sys.stderr)
            return 2
        code, reason = verify_text(text, args.sha)
        if reason:
            print(f"reason: {reason}", file=sys.stderr)
        return code
    if args.basetemp is not None:
        head = (_git(["rev-parse", "HEAD"], Path.cwd()) or "").strip()
        problem = _basetemp_problem(args.basetemp, head)
        if problem:
            print(f"reason: {problem}", file=sys.stderr)
            return 2
        if args.out is not None and _same_path(args.out, args.basetemp):
            print("reason: output path resolves to input", file=sys.stderr)
            return 2
    problem = _out_problem(args.out)
    if problem:
        print(f"reason: {problem}", file=sys.stderr)
        return 2
    issue = int(args.issue) if args.issue is not None else None
    receipt, reasons = produce(issue, runner, Path.cwd(), basetemp=args.basetemp)
    print(receipt, end="")
    if args.out is not None:
        written = _write_out(args.out, receipt)
        if written:
            print(f"reason: {written}", file=sys.stderr)
            return 2
    return 1 if reasons else 0


def main(argv=None):
    return run(argv)


if __name__ == "__main__":
    sys.exit(main())
