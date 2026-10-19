"""Local CI receipt (D122): injected commands and a temporary git repo, never the real suite."""
import importlib.util
import os
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_YML = ROOT / ".github" / "workflows" / "python-app.yml"
WORKFLOW_MD = ROOT / "docs" / "agents" / "WORKFLOW.md"

SHA = "a" * 40
PYTEST_CMD = "uv run -q pytest -q"
PROFILES_CMD = "uv run dt profiles check"
SCHEMAS_CMD = "uv run dt schemas --check"
GATE_NOT_RUN = "uv run -q python tools/check_ready_gate.py --repo artsafro/AGR-DigitalTwin-pilot"
GATE_318 = (
    "uv run -q python tools/check_ready_gate.py --issue 318 --repo artsafro/AGR-DigitalTwin-pilot"
)

# Synthetic sentinels. None of these are paths from a real object.
ENV_SENTINELS = (
    "SECRET-EMPTY",
    "SECRET SPACE",
    "SECRET-DOTDOT-..",
    "SECRET-SLASH-/",
    "SECRET-NAN",
    "SECRET-INF",
    "SECRET-NEG-INF",
    "SECRET-PY-PATH",
    "C:/synthetic/secret",
    "C:\\synthetic\\secret",
    "SECRET" * 20,
    "${PYTHONPATH}",
    "SECRET-NONE",
    "SECRET-ZERO-0",
    "SECRET-UNKNOWN",
)

UNPARSEABLE_SUMMARIES = (
    "",
    "all good",
    "passed",
    "1 passed",
    "1.5 passed in 0.01s",
    "nan passed in 0.01s",
    "inf failed in 0.01s",
    "1 passed in nan s",
    "1 passed in inf s",
    "collected 5 items",
    "=== junk ===",
    "1 passed, 0 failed",
    "no tests collected",
    "NaN",
    "inf",
)

ZERO_COLLECTED_SUMMARIES = (
    "no tests ran in 0.01s",
    "0 passed in 0.01s",
    "0 failed, 0 passed in 0.01s",
    "3 deselected in 0.01s",
    "1 warning in 0.01s",
    "0 skipped, 0 xfailed, 0 xpassed in 0.01s",
)

BAD_ISSUES = ("0", "00", "-1", "+1", "1.5", "nan", "inf", "NaN", "-inf", "1e2", " 1", "1 ", "True")

COUNT_KEYS = ("passed", "failed", "errors", "skipped", "deselected", "xfailed", "xpassed")


class Completed:
    def __init__(self, code, out="", err=""):
        self.returncode = code
        self.stdout = out
        self.stderr = err


def load():
    path = ROOT / "tools" / "ci_receipt.py"
    spec = importlib.util.spec_from_file_location("ci_receipt", path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"missing {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def git_env():
    env = os.environ.copy()
    env.update({
        "GIT_AUTHOR_NAME": "CI Receipt Test",
        "GIT_AUTHOR_EMAIL": "ci-receipt@example.com",
        "GIT_COMMITTER_NAME": "CI Receipt Test",
        "GIT_COMMITTER_EMAIL": "ci-receipt@example.com",
        "GIT_CONFIG_GLOBAL": "NUL" if os.name == "nt" else "/dev/null",
        "GIT_CONFIG_SYSTEM": "NUL" if os.name == "nt" else "/dev/null",
    })
    for key in ("PYTHONPATH", "VIRTUAL_ENV"):
        env.pop(key, None)
    return env


def git(repo, *args, env=None):
    subprocess.run(
        ["git", *args], cwd=repo, env=env or git_env(), check=True,
        capture_output=True, text=True,
    )


def init_repo(path):
    path.mkdir(parents=True, exist_ok=True)
    env = git_env()
    git(path, "init", env=env)
    (path / "tracked.txt").write_text("seed\n", encoding="utf-8")
    (path / ".gitignore").write_text("ignored.tmp\n", encoding="utf-8")
    git(path, "add", "tracked.txt", ".gitignore", env=env)
    git(path, "commit", "-m", "seed", env=env)
    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=path, env=env, check=True,
        capture_output=True, text=True,
    ).stdout.strip()
    branch = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=path, env=env, check=True,
        capture_output=True, text=True,
    ).stdout.strip()
    return sha, branch


def make_runner(pytest_out="4 passed, 1 deselected in 0.02s\n", pytest_code=0,
                profiles_code=0, schemas_code=0, gate_code=0, missing=False, seen=None):
    def runner(argv, env, cwd):
        if seen is not None:
            seen.append((list(argv), dict(env), cwd))
        upper = {key.upper() for key in env}
        assert "PYTHONPATH" not in upper
        assert "VIRTUAL_ENV" not in upper
        key = " ".join(argv)
        if missing and argv[:1] == ["uv"]:
            raise FileNotFoundError("uv")
        if key == "uv --version":
            return Completed(0, "uv 0.0.0-test\n")
        if key == PYTEST_CMD:
            return Completed(pytest_code, pytest_out)
        if key == PROFILES_CMD:
            return Completed(profiles_code, "profiles ok\n")
        if key == SCHEMAS_CMD:
            return Completed(schemas_code, "schemas ok\n")
        if key.startswith("uv run -q python tools/check_ready_gate.py"):
            return Completed(gate_code, "gate ok\n")
        raise AssertionError(f"unexpected command {argv}")

    return runner


def run_mod(mod, repo, args, runner, monkeypatch, extra_env=None):
    monkeypatch.chdir(repo)
    if extra_env:
        for key, value in extra_env.items():
            monkeypatch.setenv(key, value)
    return mod.run(args, runner=runner)


def field(text, name):
    matches = re.findall(rf"(?m)^{re.escape(name)}: (.*)$", text)
    return matches[-1] if matches else None


def block(text):
    match = re.search(r"```ci-receipt\n(.*?)\n```", text, re.S)
    assert match, text
    body = match.group(1)
    assert body.startswith("CI-RECEIPT v1\n")
    assert body.strip().endswith("result: PASS") or body.strip().endswith("result: FAIL")
    return body


def valid_receipt(sha=SHA, failed="0", result="PASS", pytest_block=True, profiles=True,
                  duration="1.500", dirty="no", summary="4 passed, 1 deselected in 1.00s",
                  passed="4", version="CI-RECEIPT v1"):
    lines = [
        "```ci-receipt",
        version,
        f"commit: {sha}",
        "branch: feature/ci",
        f"dirty: {dirty}",
        "started_utc: 2026-10-19T17:00:00Z",
        f"duration_s: {duration}",
        "os: Windows-test",
        "python: 3.13.0",
        "uv: uv 0.0.0-test",
        "scrubbed: PYTHONPATH,VIRTUAL_ENV",
    ]
    if pytest_block:
        lines += [
            f"command: {PYTEST_CMD}",
            "exit_code: 0",
            "duration_s: 1.000",
            f"summary: {summary}",
            f"passed: {passed}",
            f"failed: {failed}",
            "errors: 0",
            "skipped: 0",
            "deselected: 1",
            "xfailed: 0",
            "xpassed: 0",
        ]
    if profiles:
        lines += [
            f"command: {PROFILES_CMD}",
            "exit_code: 0",
            "duration_s: 0.250",
            f"command: {SCHEMAS_CMD}",
            "exit_code: 0",
            "duration_s: 0.250",
        ]
    lines += [
        f"command: {GATE_NOT_RUN}",
        "status: not_run",
        "reason: --issue not given",
        f"result: {result}",
        "```",
        "",
    ]
    return "\n".join(lines)


def test_workflow_trigger_is_manual_dispatch_only():
    text = WORKFLOW_YML.read_text(encoding="utf-8")
    head, _, tail = text.partition("permissions:")
    assert "workflow_dispatch:" in head
    assert "push:" not in head
    assert "pull_request:" not in head
    assert "branches:" not in head
    assert "runs-on: ubuntu-latest" in tail
    assert "actions/checkout@v4" in text
    assert "python-version: \"3.10\"" in text
    assert "flake8" in text
    assert tail.strip().endswith("pytest")


def test_author_receipts_mentions_ci_receipt_once():
    text = WORKFLOW_MD.read_text(encoding="utf-8")
    section = text.split("### Author receipts in PR", 1)[1].split("\n## ", 1)[0]
    assert section.count("CI-RECEIPT v1") == 1
    assert "tools/ci_receipt.py" in section


def test_agreed_commands_and_gate_not_run_without_issue():
    mod = load()
    commands = mod.planned_commands(None)
    assert commands == [
        (PYTEST_CMD, "run"),
        (PROFILES_CMD, "run"),
        (SCHEMAS_CMD, "run"),
        (GATE_NOT_RUN, "not_run"),
    ]
    assert mod.planned_commands(318)[-1] == (GATE_318, "run")


def test_bad_issue_numbers_fail_and_write_nothing(tmp_path):
    mod = load()
    seen = []
    for issue in BAD_ISSUES:
        out = tmp_path / f"out-{issue.strip() or 'empty'}.txt"
        if out.exists():
            out.unlink()
        code = mod.run(
            ["--issue", issue, "--out", str(out)],
            runner=make_runner(seen=seen),
        )
        assert code != 0
        assert not out.exists()
    assert seen == []
    assert len(BAD_ISSUES) == 13


def test_pass_receipt_on_clean_repo(tmp_path, monkeypatch):
    mod = load()
    repo = tmp_path / "repo"
    sha, branch = init_repo(repo)
    seen = []
    code, text = _capture(mod, repo, [], make_runner(seen=seen), monkeypatch)
    body = block(text)
    assert code == 0
    assert field(body, "commit") == sha
    assert len(sha) == 40
    assert field(body, "branch") == branch
    assert field(body, "dirty") == "no"
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", field(body, "started_utc"))
    assert re.fullmatch(r"\d+\.\d{3}", field(body, "duration_s"))
    assert field(body, "python")
    assert field(body, "uv") == "uv 0.0.0-test"
    assert field(body, "scrubbed") == "PYTHONPATH,VIRTUAL_ENV"
    assert field(body, "os")
    assert f"command: {PYTEST_CMD}" in body
    assert field(body, "passed") == "4"
    assert field(body, "failed") == "0"
    assert field(body, "errors") == "0"
    assert field(body, "skipped") == "0"
    assert field(body, "deselected") == "1"
    assert field(body, "xfailed") == "0"
    assert field(body, "xpassed") == "0"
    assert "status: not_run" in body
    assert f"command: {GATE_NOT_RUN}" in body
    assert field(body, "result") == "PASS"
    assert all(item[0] != GATE_NOT_RUN.split() for item in seen)
    assert not any("check_ready_gate.py" in " ".join(item[0]) for item in seen)
    verify_code, reason = mod.verify_text(text, sha)
    assert verify_code == 0, reason


def _capture(mod, repo, args, runner, monkeypatch, extra_env=None):
    import io
    from contextlib import redirect_stderr, redirect_stdout
    stdout, stderr = io.StringIO(), io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = run_mod(mod, repo, args, runner, monkeypatch, extra_env)
    return code, stdout.getvalue() + stderr.getvalue()


def test_failing_command_and_failed_counts_fail(tmp_path, monkeypatch):
    mod = load()
    repo = tmp_path / "repo"
    init_repo(repo)
    cases = (
        make_runner(pytest_code=1),
        make_runner(profiles_code=1),
        make_runner(schemas_code=1),
        make_runner(pytest_out="1 failed, 2 passed in 0.02s\n", pytest_code=0),
        make_runner(pytest_out="1 error in 0.02s\n", pytest_code=0),
        make_runner(pytest_out="1 failed, 1 error, 1 passed in 0.02s\n", pytest_code=1),
    )
    for runner in cases:
        code, text = _capture(mod, repo, [], runner, monkeypatch)
        assert code != 0
        assert field(text, "result") == "FAIL"
    assert len(cases) == 6


def test_unparseable_pytest_summary_is_unknown_not_zero(tmp_path, monkeypatch):
    mod = load()
    repo = tmp_path / "repo"
    init_repo(repo)
    hits = 0
    for sample in UNPARSEABLE_SUMMARIES:
        code, text = _capture(mod, repo, [], make_runner(pytest_out=sample + "\n"), monkeypatch)
        assert code != 0
        assert field(text, "result") == "FAIL"
        for key in COUNT_KEYS:
            assert field(text, key) == "unknown"
        assert re.search(r"(?m)^passed: 0$", text) is None
        hits += 1
    assert hits == len(UNPARSEABLE_SUMMARIES) == 15


def test_zero_collected_fails_at_threshold(tmp_path, monkeypatch):
    mod = load()
    repo = tmp_path / "repo"
    init_repo(repo)
    code, text = _capture(
        mod, repo, [], make_runner(pytest_out="1 passed in 0.01s\n"), monkeypatch,
    )
    assert code == 0 and field(text, "result") == "PASS"
    hits = 0
    for sample in ZERO_COLLECTED_SUMMARIES:
        code, text = _capture(mod, repo, [], make_runner(pytest_out=sample + "\n"), monkeypatch)
        assert code != 0
        assert field(text, "result") == "FAIL"
        assert field(text, "passed") != "unknown"
        hits += 1
    assert hits == len(ZERO_COLLECTED_SUMMARIES) == 6


def test_command_not_found_fails_with_reason(tmp_path, monkeypatch):
    mod = load()
    repo = tmp_path / "repo"
    init_repo(repo)
    code, text = _capture(mod, repo, [], make_runner(missing=True), monkeypatch)
    assert code != 0
    assert field(text, "result") == "FAIL"
    assert "command not found" in text


def test_dirty_worktree_fails_including_untracked(tmp_path, monkeypatch):
    mod = load()
    repo = tmp_path / "repo"
    init_repo(repo)
    cases = []
    (repo / "untracked.txt").write_text("x\n", encoding="utf-8")
    cases.append("untracked")
    code, text = _capture(mod, repo, [], make_runner(), monkeypatch)
    assert code != 0 and field(text, "dirty") == "yes" and field(text, "result") == "FAIL"
    (repo / "untracked.txt").unlink()
    nested = repo / "nested"
    nested.mkdir()
    (nested / "file.txt").write_text("x\n", encoding="utf-8")
    cases.append("nested-untracked")
    code, text = _capture(mod, repo, [], make_runner(), monkeypatch)
    assert code != 0 and field(text, "dirty") == "yes"
    (nested / "file.txt").unlink()
    tracked = repo / "tracked.txt"
    tracked.write_text("changed\n", encoding="utf-8")
    cases.append("modified")
    code, text = _capture(mod, repo, [], make_runner(), monkeypatch)
    assert code != 0 and field(text, "dirty") == "yes"
    git(repo, "add", "tracked.txt")
    cases.append("staged")
    code, text = _capture(mod, repo, [], make_runner(), monkeypatch)
    assert code != 0 and field(text, "dirty") == "yes"
    git(repo, "checkout", "--", "tracked.txt")
    assert len(cases) == 4


def test_ignored_file_does_not_dirty_the_receipt(tmp_path, monkeypatch):
    mod = load()
    repo = tmp_path / "repo"
    init_repo(repo)
    (repo / "ignored.tmp").write_text("ignore me\n", encoding="utf-8")
    code, text = _capture(mod, repo, [], make_runner(), monkeypatch)
    assert code == 0
    assert field(text, "dirty") == "no"
    assert field(text, "result") == "PASS"


def test_parent_pythonpath_and_virtual_env_never_reach_child(monkeypatch):
    mod = load()
    hits = 0
    for value in ENV_SENTINELS:
        monkeypatch.setenv("PYTHONPATH", value)
        monkeypatch.setenv("VIRTUAL_ENV", value)
        env = mod.child_env()
        upper = {key.upper(): item for key, item in env.items()}
        assert "PYTHONPATH" not in upper
        assert "VIRTUAL_ENV" not in upper
        assert value not in upper.values()
        hits += 1
    mixed = mod.child_env({"PythonPath": "SECRET-CASE", "virtual_env": "SECRET-CASE", "PATH": "C:/Windows"})
    assert mixed == {"PATH": "C:/Windows"}
    hits += 1
    assert hits == len(ENV_SENTINELS) + 1 == 16


def test_runner_child_env_has_no_parent_secrets(tmp_path, monkeypatch):
    mod = load()
    repo = tmp_path / "repo"
    init_repo(repo)
    seen = []
    monkeypatch.setenv("PYTHONPATH", "SECRET-PARENT-PATH")
    monkeypatch.setenv("VIRTUAL_ENV", "SECRET-PARENT-VENV")
    code, _text = _capture(mod, repo, [], make_runner(seen=seen), monkeypatch)
    assert code == 0
    assert seen
    for _argv, env, cwd in seen:
        assert cwd == repo
        assert "SECRET-PARENT-PATH" not in env.values()
        assert "SECRET-PARENT-VENV" not in env.values()
        assert "PYTHONPATH" not in {key.upper() for key in env}
        assert "VIRTUAL_ENV" not in {key.upper() for key in env}


def test_issue_runs_ready_gate_command(tmp_path, monkeypatch):
    mod = load()
    repo = tmp_path / "repo"
    sha, _branch = init_repo(repo)
    seen = []
    code, text = _capture(mod, repo, ["--issue", "318"], make_runner(seen=seen), monkeypatch)
    assert code == 0
    assert field(text, "result") == "PASS"
    assert any(" ".join(argv) == GATE_318 for argv, _env, _cwd in seen)
    assert "status: not_run" not in text
    assert mod.verify_text(text, sha)[0] == 0
    code, text = _capture(
        mod, repo, ["--issue", "318"], make_runner(gate_code=1), monkeypatch,
    )
    assert code != 0 and field(text, "result") == "FAIL"


def test_last_pytest_summary_wins(tmp_path, monkeypatch):
    mod = load()
    repo = tmp_path / "repo"
    init_repo(repo)
    sample = "1 failed, 1 passed in 0.01s\n4 passed, 2 skipped, 1 deselected, 1 xfailed, 1 xpassed in 0.02s\n"
    code, text = _capture(mod, repo, [], make_runner(pytest_out=sample), monkeypatch)
    assert code == 0
    assert field(text, "passed") == "4"
    assert field(text, "failed") == "0"
    assert field(text, "skipped") == "2"
    assert field(text, "deselected") == "1"
    assert field(text, "xfailed") == "1"
    assert field(text, "xpassed") == "1"
    assert field(text, "errors") == "0"


def test_verify_accepts_literal_pass_receipt(tmp_path):
    mod = load()
    path = tmp_path / "receipt.txt"
    path.write_text(valid_receipt(), encoding="utf-8")
    code, reason = _verify(mod, path, SHA)
    assert code == 0, reason


def test_verify_rejects_hand_edits(tmp_path):
    mod = load()
    edits = {
        "failed-but-pass": valid_receipt(failed="1"),
        "wrong-sha": valid_receipt(),
        "missing-command": valid_receipt(profiles=False),
        "missing-pytest": valid_receipt(pytest_block=False),
    }
    reasons = {}
    for name, body in edits.items():
        path = tmp_path / f"{name}.txt"
        path.write_text(body, encoding="utf-8")
        sha = "b" * 40 if name == "wrong-sha" else SHA
        code, reason = _verify(mod, path, sha)
        assert code != 0
        assert reason
        reasons[name] = reason
    assert "fail" in reasons["failed-but-pass"].lower() or "inconsist" in reasons["failed-but-pass"].lower()
    assert "sha" in reasons["wrong-sha"].lower()
    assert "command" in reasons["missing-command"].lower()
    assert "command" in reasons["missing-pytest"].lower()
    assert len(edits) == 4


def test_verify_fail_closed_empty_partial_unsupported_nonfinite(tmp_path):
    mod = load()
    probes = {
        "empty": "",
        "partial": "```ci-receipt\nCI-RECEIPT v1\ncommit: " + SHA + "\n```\n",
        "unsupported": valid_receipt(version="CI-RECEIPT v2"),
        "nan-duration": valid_receipt(duration="nan"),
        "inf-duration": valid_receipt(duration="inf"),
        "neg-inf-duration": valid_receipt(duration="-inf"),
        "zero-collected": valid_receipt(summary="no tests ran in 0.01s", passed="0"),
        "dirty-pass": valid_receipt(dirty="yes"),
        "unknown-pass": valid_receipt(passed="unknown", summary="garbage"),
        "negative-failed": valid_receipt(failed="-1"),
        "blank": "   \n",
        "prose-only": "See the log.\n",
    }
    hits = 0
    for name, body in probes.items():
        path = tmp_path / f"{name}.txt"
        path.write_text(body, encoding="utf-8")
        code, reason = _verify(mod, path, SHA)
        assert code != 0, name
        assert reason, name
        assert "PASS" != reason.strip()
        hits += 1
    assert hits == len(probes) == 12


def test_output_resolving_to_input_writes_nothing(tmp_path):
    mod = load()
    target = tmp_path / "receipt.txt"
    target.write_text("SENTINEL-DO-NOT-TOUCH\n", encoding="utf-8")
    alias = tmp_path / "alias.txt"
    try:
        os.link(target, alias)
        linked = True
    except OSError:
        alias.write_text("SENTINEL-DO-NOT-TOUCH\n", encoding="utf-8")
        linked = False
    before = target.read_text(encoding="utf-8")
    code = mod.run(["--verify", str(target), "--sha", SHA, "--out", str(alias)])
    assert code != 0
    assert target.read_text(encoding="utf-8") == before
    assert alias.read_text(encoding="utf-8") == "SENTINEL-DO-NOT-TOUCH\n"
    missing_parent = tmp_path / "missing" / "out.txt"
    code = mod.run(["--out", str(missing_parent)], runner=make_runner())
    assert code != 0
    assert not missing_parent.exists()
    assert linked or alias.exists()


def test_verify_file_roundtrip_and_surrounding_prose(tmp_path, monkeypatch):
    mod = load()
    repo = tmp_path / "repo"
    sha, _branch = init_repo(repo)
    code, text = _capture(mod, repo, [], make_runner(), monkeypatch)
    assert code == 0
    wrapped = tmp_path / "pr-body.md"
    wrapped.write_text("Intro\n\n" + text + "\nThanks\n", encoding="utf-8")
    assert mod.run(["--verify", str(wrapped), "--sha", sha]) == 0
    assert mod.run(["--verify", str(wrapped), "--sha", "c" * 40]) != 0


def _verify(mod, path, sha):
    import io
    from contextlib import redirect_stderr, redirect_stdout
    stdout, stderr = io.StringIO(), io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = mod.run(["--verify", str(path), "--sha", sha])
    return code, (stderr.getvalue() or stdout.getvalue()).strip()


def test_nonfinite_count_tokens_never_verify(tmp_path):
    mod = load()
    tokens = ("nan", "inf", "-inf", "NaN", "+inf", "1.0", "-0", "+4", "4.5", "", "1e2")
    hits = 0
    for token in tokens:
        path = tmp_path / f"count-{hits}.txt"
        path.write_text(valid_receipt(passed=token), encoding="utf-8")
        code, reason = _verify(mod, path, SHA)
        assert code != 0
        assert reason
        hits += 1
    assert hits == len(tokens) == 11
