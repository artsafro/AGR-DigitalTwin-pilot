"""pipeline_gate: a job status above draft needs spec + extractor report + checker report (HARNESS_PLAN §16)."""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("pipeline_gate", ROOT / "tools/git-hooks/pipeline_gate.py")
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)
HOOK = ROOT / ".claude/hooks/pipeline_gate.py"

SPEC = json.dumps({"id": "obj", "levels": []})
REPORT = json.dumps({"parts": 3, "questions": []})
CHECK_PASS = json.dumps({"passed": True, "failed": [], "not_measured": [], "checks": []})
CHECK_FAIL = json.dumps({"passed": False, "failed": ["bbox"], "not_measured": [], "checks": []})
BACKLOG = "# Backlog\n\n- **EG1** Facade decor.\n"


def state(status):
    return f"# State\n\nPipeline status: {status}\n"


def reader(files):
    return lambda path: files.get(path)


def job(files, status, **pipeline):
    files = dict(files)
    files["jobs/J/STATE.md"] = state(status)
    for name, text in pipeline.items():
        files[f"jobs/J/pipeline/{name.replace('_', '.')}"] = text
    return files


@pytest.mark.parametrize("text, expected", [
    ("Pipeline status: built\n", ("built", None)),
    ("Pipeline status: `checked`\n", ("checked", None)),
    ("Pipeline status: **draft**\n", ("draft", None)),
    ("no status here\n", (None, None)),
])
def test_status_line(text, expected):
    assert gate.status_of(text) == expected


def test_status_line_rejects_unknown_and_twice():
    assert "is not 'Pipeline status" in gate.status_of("Pipeline status: accepted\n")[1]
    assert "one 'Pipeline status" in gate.status_of("Pipeline status: draft\nPipeline status: built\n")[1]


def test_draft_needs_nothing():
    assert gate.job_errors("J", reader(job({}, "draft")), require_line=True) == []


def test_built_without_spec_is_blocked():
    errors = gate.job_errors("J", reader(job({}, "built")), require_line=True)
    assert any("spec.json missing" in e for e in errors)
    assert any("spec.report.json missing" in e for e in errors)
    assert any("check.json missing" in e for e in errors)


def test_hand_written_spec_without_extractor_report_is_blocked():
    files = job({}, "built", spec_json=SPEC, check_json=CHECK_PASS,
                spec_report_json=json.dumps({"note": "written by hand"}))
    assert any("no `dt spec extract` report" in e for e in gate.job_errors("J", reader(files), True))


def test_built_with_all_files_passes_even_when_checks_fail():
    files = job({}, "built", spec_json=SPEC, spec_report_json=REPORT, check_json=CHECK_FAIL)
    assert gate.job_errors("J", reader(files), True) == []


def test_checked_needs_a_passing_report():
    files = job({}, "checked", spec_json=SPEC, spec_report_json=REPORT, check_json=CHECK_FAIL)
    assert any("failed ['bbox']" in e for e in gate.job_errors("J", reader(files), True))
    files = job({}, "delivered", spec_json=SPEC, spec_report_json=REPORT,
                check_json=json.dumps({"passed": False, "failed": [], "not_measured": ["uv"]}))
    assert any("not measured ['uv']" in e for e in gate.job_errors("J", reader(files), True))
    files = job({}, "delivered", spec_json=SPEC, spec_report_json=REPORT, check_json=CHECK_PASS)
    assert gate.job_errors("J", reader(files), True) == []


@pytest.mark.parametrize("status", ["built", "checked", "delivered"])
def test_a_stopped_extractor_report_backs_no_status(status):
    """Review 1 of #80: a --collect-stops report (stops listed) beside an older spec and a passing check."""
    stopped = json.dumps({"parts": 3, "questions": [], "stops": [{"stage": "roof", "level": None, "message": "x"}]})
    files = job({}, status, spec_json=SPEC, spec_report_json=stopped, check_json=CHECK_PASS)
    assert any("1 extractor stop(s)" in e for e in gate.job_errors("J", reader(files), True))


def test_check_report_shape():
    files = job({}, "built", spec_json=SPEC, spec_report_json=REPORT, check_json=json.dumps({"ok": True}))
    assert any("no checker report" in e for e in gate.job_errors("J", reader(files), True))


def test_missing_line_only_when_required():
    files = {"jobs/J/STATE.md": "# State\nStatus: accepted by the user\n"}
    assert gate.job_errors("J", reader(files), require_line=False) == []
    assert "no 'Pipeline status" in gate.job_errors("J", reader(files), require_line=True)[0]


def test_script_must_name_a_listed_gap():
    assert "names the engine gap" in gate.script_errors("jobs/J/scripts/a.py", "print(1)\n", BACKLOG)[0]
    assert "not an engine gap" in gate.script_errors("jobs/J/scripts/a.py", '"""Engine gap: EG9"""\n', BACKLOG)[0]
    assert gate.script_errors("jobs/J/scripts/a.py", '"""Decor.\n\nEngine gap: EG1\n"""\n', BACKLOG) == []
    late = "\n" * gate.GAP_HEAD_LINES + "# Engine gap: EG1\n"
    assert gate.script_errors("jobs/J/scripts/a.py", late, BACKLOG)


def test_is_job_script():
    assert gate.is_job_script("jobs/J/scripts/build.py")
    assert gate.is_job_script("jobs/J/scripts/sub/run.sh")
    assert not gate.is_job_script("jobs/J/scripts/__pycache__/build.cpython-313.pyc")
    assert not gate.is_job_script("jobs/J/scripts/data.json")
    assert not gate.is_job_script("jobs/J/STATE.md")


# --- git: pre-commit (--staged) and delivery (--job) ---------------------------------------------------

def git(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True)


@pytest.fixture
def repo(tmp_path):
    git(tmp_path, "init", "-q")
    git(tmp_path, "config", "user.email", "t@example.com")
    git(tmp_path, "config", "user.name", "t")
    # under a long --basetemp the object paths pass MAX_PATH and git fails with "Filename too long"
    # (a Claude scratchpad basetemp, 2026-10-12); the gate itself is not about path length
    git(tmp_path, "config", "core.longpaths", "true")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/backlog.md").write_text(BACKLOG, encoding="utf-8")
    (tmp_path / "jobs/OLD").mkdir(parents=True)
    (tmp_path / "jobs/OLD/STATE.md").write_text("Status: accepted (before the gate)\n", encoding="utf-8")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-qm", "base")
    return tmp_path


def write(repo, rel, text):
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    git(repo, "add", rel)


def test_staged_built_without_files_is_blocked(repo):
    write(repo, "jobs/J/STATE.md", state("built"))
    assert any("spec.json missing" in e for e in gate.staged(repo))


def test_staged_built_with_files_passes(repo):
    write(repo, "jobs/J/STATE.md", state("built"))
    write(repo, "jobs/J/pipeline/spec.json", SPEC)
    write(repo, "jobs/J/pipeline/spec.report.json", REPORT)
    write(repo, "jobs/J/pipeline/check.json", CHECK_PASS)
    assert gate.staged(repo) == []


def test_staged_reads_the_index_not_the_working_tree(repo):
    write(repo, "jobs/J/STATE.md", state("built"))
    for name, text in (("spec.json", SPEC), ("spec.report.json", REPORT), ("check.json", CHECK_PASS)):
        (repo / "jobs/J/pipeline").mkdir(parents=True, exist_ok=True)
        (repo / "jobs/J/pipeline" / name).write_text(text, encoding="utf-8")     # on disk, not staged
    assert any("spec.json missing" in e for e in gate.staged(repo))


def test_staged_deleting_the_report_under_a_built_status_is_blocked(repo):
    write(repo, "jobs/J/STATE.md", state("built"))
    write(repo, "jobs/J/pipeline/spec.json", SPEC)
    write(repo, "jobs/J/pipeline/spec.report.json", REPORT)
    write(repo, "jobs/J/pipeline/check.json", CHECK_PASS)
    git(repo, "commit", "-qm", "built")
    git(repo, "rm", "-q", "jobs/J/pipeline/check.json")
    assert any("check.json missing" in e for e in gate.staged(repo))


def test_staged_old_state_untouched_passes_touched_needs_the_line(repo):
    write(repo, "jobs/OLD/notes.md", "x\n")
    assert gate.staged(repo) == []
    write(repo, "jobs/OLD/STATE.md", "Status: accepted, edited\n")
    assert any("no 'Pipeline status" in e for e in gate.staged(repo))


def test_staged_new_script_needs_a_gap(repo):
    write(repo, "jobs/J/scripts/build_decor.py", "import bpy\n")
    assert any("names the engine gap" in e for e in gate.staged(repo))
    write(repo, "jobs/J/scripts/build_decor.py", '"""Build decor.\n\nEngine gap: EG1\n"""\nimport bpy\n')
    assert gate.staged(repo) == []


def test_delivery_pyc_without_committed_source(repo):
    write(repo, "jobs/J/STATE.md", state("draft"))
    git(repo, "commit", "-qm", "j")
    pyc = repo / "jobs/J/scripts/__pycache__/build_decor.cpython-313.pyc"
    pyc.parent.mkdir(parents=True)
    pyc.write_bytes(b"\0")
    errors = gate.delivery(repo, "jobs/J")
    assert any("jobs/J/scripts/build_decor.py is not committed" in e for e in errors)
    write(repo, "jobs/J/scripts/build_decor.py", '"""Engine gap: EG1"""\n')
    git(repo, "commit", "-qm", "source")
    assert gate.delivery(repo, "jobs/J") == []


def test_delivery_requires_the_line(repo):
    assert any("no 'Pipeline status" in e for e in gate.delivery(repo, "jobs/OLD"))


def test_cli_exit_codes(repo):
    run = lambda *a: subprocess.run([sys.executable, str(ROOT / "tools/git-hooks/pipeline_gate.py"), *a],
                                    cwd=repo, capture_output=True, text=True)
    assert run("--staged").returncode == 0
    write(repo, "jobs/J/STATE.md", state("checked"))
    result = run("--staged")
    assert result.returncode == 1 and "blocked" in result.stderr
    assert run("--job", "nowhere").returncode == 2


@pytest.mark.parametrize("failing", ["diff", "ls-files", "cat-file"])
def test_git_failure_blocks_the_commit(repo, monkeypatch, failing):
    """Fail closed (2026-10-12): under a long path git once failed, the gate read an empty index and let
    a built status without pipeline/ through."""
    write(repo, "jobs/J/STATE.md", state("built"))
    real = gate._git

    def broken(root, *args):
        if args[0] == failing:
            return subprocess.CompletedProcess(args, 128, b"", b"error: Filename too long")
        return real(root, *args)
    monkeypatch.setattr(gate, "_git", broken)
    monkeypatch.chdir(repo)
    assert gate.main(["--staged"]) == 2


def test_unresolved_merge_blocks(repo):
    """Review 1 of #79: STATE.md only at merge stages 1-3 (no stage 0) is not 'absent'."""
    write(repo, "jobs/J/STATE.md", state("draft"))
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "draft")
    git(repo, "checkout", "-qb", "other")
    write(repo, "jobs/J/STATE.md", state("checked"))
    git(repo, "commit", "-qam", "checked")
    git(repo, "checkout", "-q", "-")
    write(repo, "jobs/J/STATE.md", state("built"))
    git(repo, "commit", "-qam", "built", "--no-verify")
    subprocess.run(["git", "merge", "-q", "other"], cwd=repo, capture_output=True)   # conflicts
    errors = gate.staged(repo)
    assert errors and all("unresolved merge" in e for e in errors)


def test_git_not_found_blocks(repo, monkeypatch):
    """Review 1 of #79: a git that cannot start is a controlled block (exit 2), not a traceback."""
    def missing(argv, **kw):
        raise FileNotFoundError(2, "git not found")
    monkeypatch.setattr(gate.subprocess, "run", missing)
    monkeypatch.chdir(repo)
    assert gate.main(["--staged"]) == 2


def test_pre_commit_blocks_without_a_root(tmp_path):
    """Review 1 of #79: when git cannot name the repository root the hook must not skip its checks."""
    import shutil
    bash = "C:/Program Files/Git/bin/bash.exe" if Path("C:/Program Files/Git/bin/bash.exe").exists()         else shutil.which("bash")
    if not bash:
        pytest.skip("bash unavailable")
    env = {**__import__("os").environ, "GIT_DIR": str(tmp_path / "nowhere")}
    result = subprocess.run([bash, str(ROOT / "tools/git-hooks/pre-commit")], cwd=tmp_path, env=env,
                            capture_output=True, text=True)
    assert result.returncode == 1 and "blocked" in result.stderr


def test_pre_commit_blocks_when_root_lookup_fails_with_output(tmp_path):
    """Review 2 of #79: a failing `git rev-parse` that still prints a directory must block."""
    import shutil
    bash = "C:/Program Files/Git/bin/bash.exe" if Path("C:/Program Files/Git/bin/bash.exe").exists() \
        else shutil.which("bash")
    if not bash:
        pytest.skip("bash unavailable")
    fake = tmp_path / "bin"
    fake.mkdir()
    (fake / "git").write_text(f'#!/bin/sh\necho "{tmp_path.as_posix()}"\nexit 128\n', encoding="utf-8")
    hook = (ROOT / "tools/git-hooks/pre-commit").as_posix()
    bin_dir = fake.as_posix()
    if fake.drive:                                   # C:/x -> /c/x: a drive colon would split bash's PATH
        bin_dir = "/" + fake.drive[0].lower() + bin_dir[len(fake.drive):]
    result = subprocess.run([bash, "-c", f'PATH="{bin_dir}:$PATH"; command -v git; sh "{hook}"'],
                            cwd=tmp_path, capture_output=True, text=True)
    assert result.stdout.strip().startswith(bin_dir), result.stdout     # the fake git is the one run
    assert result.returncode == 1 and "blocked" in result.stderr


# --- Claude Code PreToolUse hook ------------------------------------------------------------------------

def hook(payload):
    # without CLAUDE_PROJECT_DIR the payload's cwd names the repository the call runs in (#128)
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_PROJECT_DIR"}
    result = subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload), env=env,
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"] if result.stdout.strip() else "allow"


def test_hook_denies_a_status_without_files(tmp_path):
    (tmp_path / ".git").mkdir()                       # the repository root (review 3 of PR #73)
    target = tmp_path / "jobs/J/STATE.md"
    payload = {"tool_name": "Write", "tool_input": {"file_path": str(target), "content": state("built")}}
    assert hook(payload) == "deny"
    payload["tool_input"]["content"] = state("draft")
    assert hook(payload) == "allow"


def test_hook_edit_applies_the_change(tmp_path):
    (tmp_path / ".git").mkdir()                       # the repository root (review 3 of PR #73)
    target = tmp_path / "jobs/J/STATE.md"
    target.parent.mkdir(parents=True)
    target.write_text(state("draft"), encoding="utf-8")
    edit = {"tool_name": "Edit", "tool_input": {"file_path": str(target), "old_string": "draft",
                                                "new_string": "delivered"}}
    assert hook(edit) == "deny"
    for name, text in (("spec.json", SPEC), ("spec.report.json", REPORT), ("check.json", CHECK_PASS)):
        (tmp_path / "jobs/J/pipeline").mkdir(exist_ok=True)
        (tmp_path / "jobs/J/pipeline" / name).write_text(text, encoding="utf-8")
    assert hook(edit) == "allow"


def test_hook_new_script_needs_a_gap(tmp_path):
    (tmp_path / ".git").mkdir()                       # the repository root (review 3 of PR #73)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/backlog.md").write_text(BACKLOG, encoding="utf-8")
    target = tmp_path / "jobs/J/scripts/build_decor.py"
    payload = {"tool_name": "Write", "tool_input": {"file_path": str(target), "content": "import bpy\n"}}
    assert hook(payload) == "deny"
    payload["tool_input"]["content"] = '"""Engine gap: EG1"""\nimport bpy\n'
    assert hook(payload) == "allow"


def test_hook_ignores_other_files(tmp_path):
    assert hook({"tool_name": "Write", "tool_input": {"file_path": str(tmp_path / "src/a.py"), "content": ""}}) == "allow"
    assert hook({"tool_name": "Bash", "tool_input": {"command": "ls"}}) == "allow"


# --- review 1 of PR #73 ------------------------------------------------------------------------------

@pytest.mark.parametrize("text", [
    "Pipeline status: draft\n**Pipeline status: built**\n",
    "Pipeline status: draft\npipeline STATUS: built\n",
    "Pipeline status: draft\n> - Pipeline status: built\n",
])
def test_a_second_formatted_status_line_counts(text):
    assert "one 'Pipeline status" in gate.status_of(text)[1]


@pytest.mark.parametrize("text", ["**Pipeline status: built**\n", "\ufeffPipeline status: built\n",
                                  "**Pipeline status:** built\n", "Pipeline status: Built\r\n"])
def test_formatted_single_status_is_read(text):
    assert gate.status_of(text) == ("built", None)


def test_missing_backlog_lists_no_gap():
    assert "backlog.md missing" in gate.script_errors("jobs/J/scripts/a.py", '"""Engine gap: EG999"""\n', None)[0]


def test_staged_backlog_deleted_unknown_gap_blocked(repo):
    git(repo, "rm", "-q", "docs/backlog.md")
    write(repo, "jobs/J/scripts/a.py", '"""Engine gap: EG999"""\n')
    assert any("backlog.md missing" in e for e in gate.staged(repo))


def test_staged_case_variant_of_state_is_blocked(repo):
    write(repo, "jobs/J/state.md", state("built"))
    assert any("name it STATE.md" in e for e in gate.staged(repo))


def test_delivery_staged_source_is_not_committed(repo):
    write(repo, "jobs/J/STATE.md", state("draft"))
    git(repo, "commit", "-qm", "j")
    pyc = repo / "jobs/J/scripts/__pycache__/build.cpython-313.pyc"
    pyc.parent.mkdir(parents=True)
    pyc.write_bytes(b"\0")
    write(repo, "jobs/J/scripts/build.py", '"""Engine gap: EG1"""\n')      # staged only
    assert any("build.py is not committed" in e for e in gate.delivery(repo, "jobs/J"))


def test_delivery_dotted_cache_name(repo):
    write(repo, "jobs/J/STATE.md", state("draft"))
    write(repo, "jobs/J/scripts/build.decor.py", '"""Engine gap: EG1"""\n')
    git(repo, "commit", "-qm", "j")
    pyc = repo / "jobs/J/scripts/__pycache__/build.decor.cpython-313.pyc"
    pyc.parent.mkdir(parents=True)
    pyc.write_bytes(b"\0")
    assert gate.delivery(repo, "jobs/J") == []


def test_delivery_rejects_a_non_canonical_job_path(repo):
    (repo / "nested/jobs/J").mkdir(parents=True)
    with pytest.raises(ValueError):
        gate.delivery(repo, "nested/jobs/J")


def test_pre_commit_gate_sees_the_index_after_linking(repo):
    import shutil
    hooks = repo / ".git/hooks"
    shutil.copy(ROOT / "tools/git-hooks/pre-commit", hooks / "pre-commit")
    (repo / "tools/git-hooks").mkdir(parents=True)
    for name in ("pipeline_gate.py", "branch_names.py", "link_large_files.py"):
        shutil.copy(ROOT / "tools/git-hooks" / name, repo / "tools/git-hooks" / name)
    git(repo, "add", "tools")
    git(repo, "commit", "-qm", "hooks", "--no-verify")
    git(repo, "config", "twin.linkLargeMb", "0.001")
    write(repo, "jobs/J/STATE.md", state("built"))
    write(repo, "jobs/J/pipeline/spec.json", json.dumps({"id": "obj", "pad": "x" * 4000}))
    write(repo, "jobs/J/pipeline/spec.report.json", REPORT)
    write(repo, "jobs/J/pipeline/check.json", CHECK_PASS)
    result = subprocess.run(["git", "commit", "-qm", "built"], cwd=repo, capture_output=True, text=True)
    assert result.returncode != 0, result.stdout + result.stderr
    assert "spec.json missing" in result.stderr


def test_pre_commit_without_the_gate_blocks_jobs_only(repo):
    """Review 3 of #79: no pipeline_gate.py in the work tree - a commit touching jobs/ is blocked, any other
    commit has nothing to check and passes (branches older than #73)."""
    import shutil
    shutil.copy(ROOT / "tools/git-hooks/pre-commit", repo / ".git/hooks/pre-commit")
    write(repo, "jobs/J/STATE.md", state("built"))
    git(repo, "add", "-A")
    result = subprocess.run(["git", "commit", "-qm", "built"], cwd=repo, capture_output=True, text=True)
    assert result.returncode != 0 and "pipeline_gate.py is missing" in result.stderr, result.stderr
    git(repo, "reset", "-q")
    write(repo, "docs/note.md", "note\n")
    git(repo, "add", "docs/note.md")
    result = subprocess.run(["git", "commit", "-qm", "note"], cwd=repo, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_replace_refs_do_not_hide_the_staged_state(repo):
    """Review 3 of #79: `git replace` showing a draft for the staged built STATE.md must not fool the gate."""
    write(repo, "jobs/J/STATE.md", state("built"))
    git(repo, "add", "-A")
    staged = git(repo, "rev-parse", ":jobs/J/STATE.md").stdout.strip()
    draft = subprocess.run(["git", "hash-object", "-w", "--stdin"], cwd=repo, input=state("draft"),
                           capture_output=True, text=True, check=True).stdout.strip()
    git(repo, "replace", staged, draft)
    errors = gate.staged(repo)
    assert any("spec.json missing" in e for e in errors), errors


def test_hook_state_name_case_blind(tmp_path):
    (tmp_path / ".git").mkdir()                       # the repository root (review 3 of PR #73)
    target = tmp_path / "jobs/J/state.md"
    assert hook({"tool_name": "Write", "tool_input": {"file_path": str(target), "content": state("built")}}) == "deny"


@pytest.mark.parametrize("raw", ["[]", "null", '"x"', '{"tool_name": "Write", "tool_input": "x"}',
                                 '{"tool_name": "Write", "tool_input": {"file_path": 5}}'])
def test_hook_malformed_payload_passes(raw):
    result = subprocess.run([sys.executable, str(HOOK)], input=raw, capture_output=True, text=True)
    assert result.returncode == 0 and not result.stdout.strip(), result.stderr


def test_delivery_optimized_cache_name(repo):
    write(repo, "jobs/J/STATE.md", state("draft"))
    write(repo, "jobs/J/scripts/build.decor.py", '"""Engine gap: EG1"""\n')
    git(repo, "commit", "-qm", "j")
    pyc = repo / "jobs/J/scripts/__pycache__/build.decor.cpython-313.opt-1.pyc"
    pyc.parent.mkdir(parents=True)
    pyc.write_bytes(b"\0")
    assert gate.delivery(repo, "jobs/J") == []
    (pyc.parent / "other.cpython-313.opt-2.pyc").write_bytes(b"\0")
    assert any("other.py is not committed" in e for e in gate.delivery(repo, "jobs/J"))


# --- review 2 of PR #73 ------------------------------------------------------------------------------

@pytest.mark.parametrize("text", ["Pipeline status: draft\n# Pipeline status: built\n",
                                  "Pipeline status: draft\nPipeline **status**: built\n",
                                  "Pipeline status: draft\nThe pipeline status was built earlier.\n"])
def test_any_second_mention_of_the_status_is_an_error(text):
    assert "one 'Pipeline status" in gate.status_of(text)[1]


@pytest.mark.parametrize("text", ["## Pipeline status: built\n", "Pipeline **status**: built\n"])
def test_heading_or_inner_bold_status_is_read(text):
    assert gate.status_of(text) == ("built", None)


def test_unreadable_status_line_is_an_error():
    assert "is not 'Pipeline status" in gate.status_of("Pipeline status: built, mostly\n")[1]


def test_staged_folder_case_variant_is_blocked(repo):
    git(repo, "config", "core.ignorecase", "false")   # else git files it under the tracked jobs/ (checked there)
    write(repo, "Jobs/J/STATE.md", state("built"))
    write(repo, "Jobs/J/scripts/run.py", "print(1)\n")
    errors = gate.staged(repo)
    assert sum("the folder is jobs/" in e for e in errors) == 2


@pytest.mark.parametrize("payload", [
    {"tool_name": "Write", "tool_input": {"file_path": "C:/r/jobs/J/STATE.md", "content": 5}},
    {"tool_name": "Edit", "tool_input": {"file_path": "C:/r/jobs/J/STATE.md", "old_string": None, "new_string": None}},
    {"tool_name": "Write", "tool_input": {"file_path": "C:/r/jobs/J/scripts/new.py", "content": None}},
])
def test_hook_malformed_fields_pass(payload):
    result = subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload), capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


# --- review 3 of PR #73 ------------------------------------------------------------------------------

@pytest.mark.parametrize("path", ["jobs/J/scripts/run.bat", "jobs/J/scripts/__pycache__/run.py", "jobs/J/scripts/run"])
def test_any_file_under_scripts_is_a_script(path):
    assert gate.is_job_script(path)


@pytest.mark.parametrize("path", ["jobs/J/scripts/__pycache__/run.cpython-313.pyc", "jobs/J/scripts/table.json"])
def test_bytecode_and_data_are_not_scripts(path):
    assert not gate.is_job_script(path)


def test_staged_batch_script_needs_a_gap(repo):
    write(repo, "jobs/J/scripts/run.bat", "@echo off\n")
    assert any("names the engine gap" in e for e in gate.staged(repo))


def test_hook_dotdot_path_is_resolved(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / "jobs/J/sub").mkdir(parents=True)
    target = str(tmp_path / "jobs/J/sub/../STATE.md")
    assert hook({"tool_name": "Write", "tool_input": {"file_path": target, "content": state("built")}}) == "deny"


def test_hook_root_is_the_repository_not_a_deeper_jobs_folder(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/backlog.md").write_text(BACKLOG, encoding="utf-8")
    target = str(tmp_path / "jobs/J/scripts/jobs/new.py")
    assert hook({"tool_name": "Write", "tool_input": {"file_path": target, "content": "import bpy\n"}}) == "deny"


def test_hook_malformed_script_content_passes_silently(tmp_path):
    (tmp_path / ".git").mkdir()
    target = str(tmp_path / "jobs/J/scripts/new.py")
    raw = json.dumps({"tool_name": "Write", "tool_input": {"file_path": target, "content": None}})
    result = subprocess.run([sys.executable, str(HOOK)], input=raw, capture_output=True, text=True)
    assert result.returncode == 0 and not result.stdout.strip()


# --- #128: attempts limit (pipeline/state.json) ----------------------------------------------------------

STATE_PATH = "jobs/J/pipeline/state.json"
STOP = {"item": "module:M01", "tried": "pattern A, split at kink", "numbers": "bbox 0.12 m, 0.08 m",
        "next_step": "review round with Codex"}


def fail(cause, item="module:M01", kind="checker"):
    return {"item": item, "kind": kind, "cause": cause, "detail": "bbox off"}


def attempts(*failures, stops=()):
    return json.dumps({"failures": list(failures), "stops": list(stops)})


def test_two_failures_with_different_causes_are_not_locked():
    assert gate.locked_items(json.loads(attempts(fail("code"), fail("tool")))) == {}


def test_second_failure_with_the_same_cause_locks():
    assert gate.locked_items(json.loads(attempts(fail("code"), fail("code")))) == \
        {"module:M01": "2 open failures with cause 'code'"}


def test_third_failure_of_one_item_locks():
    doc = json.loads(attempts(fail("code"), fail("tool"), fail("test", kind="test")))
    assert gate.locked_items(doc) == {"module:M01": "3 open failures"}
    other = json.loads(attempts(fail("code"), fail("tool"), fail("test", item="check:bbox")))
    assert gate.locked_items(other) == {}


def test_a_stop_record_lifts_the_lock():
    doc = json.loads(attempts(fail("code"), fail("code"), stops=[{**STOP, "after": 2}]))
    assert gate.locked_items(doc) == {}
    doc = json.loads(attempts(fail("code"), fail("code"), fail("code"), stops=[{**STOP, "after": 1}]))
    assert "module:M01" in gate.locked_items(doc)


@pytest.mark.parametrize("doc, needle", [
    ([], "is not a JSON object"),
    ({"failures": {}}, "failures is not a list"),
    ({"failures": [{"item": "M01", "kind": "checker", "cause": "code"}]}, "failures[0].item"),
    ({"failures": [{"item": "module:M01", "kind": "lint", "cause": "code"}]}, "failures[0].kind"),
    ({"failures": [{"item": "module:M01", "kind": "checker", "cause": "luck"}]}, "failures[0].cause"),
    ({"failures": [fail("code")], "stops": [{**STOP, "after": 2}]}, "stops[0].after"),
    ({"failures": [fail("code")], "stops": [{**STOP, "after": 1, "numbers": " "}]}, "stops[0].numbers"),
])
def test_state_shape_errors_name_the_path(doc, needle):
    errors = gate.state_shape_errors(doc, STATE_PATH)
    assert any(needle in e and STATE_PATH in e for e in errors), errors


def test_state_shape_of_a_valid_or_empty_state():
    assert gate.state_shape_errors({}, STATE_PATH) == []
    assert gate.state_shape_errors(json.loads(attempts(fail("code"), stops=[{**STOP, "after": 1}])), STATE_PATH) == []


def test_attempt_errors_recording_the_locking_failure_is_allowed():
    old = reader({STATE_PATH: attempts(fail("code"))})
    new = reader({STATE_PATH: attempts(fail("code"), fail("code"))})
    assert gate.attempt_errors("J", old, new) == []


def test_attempt_errors_a_further_failure_of_a_locked_item_is_denied():
    old = reader({STATE_PATH: attempts(fail("code"), fail("code"))})
    new = reader({STATE_PATH: attempts(fail("code"), fail("code"), fail("tool"))})
    errors = gate.attempt_errors("J", old, new)
    assert errors and "module:M01 failure #3 appended while locked" in errors[0] and gate.ESCALATION in errors[0]
    stopped = reader({STATE_PATH: attempts(fail("code"), fail("code"), fail("tool"),
                                           stops=[{**STOP, "after": 2}])})
    assert gate.attempt_errors("J", old, stopped) == []


def test_attempt_errors_check_and_status_writes_while_locked():
    locked = attempts(fail("code"), fail("tool"), fail("test"))
    old = reader(job({STATE_PATH: locked}, "draft", check_json=CHECK_FAIL))
    rerun = reader(job({STATE_PATH: locked}, "draft", check_json=CHECK_PASS))
    assert any("check.json rewritten while module:M01 is locked (3 open failures)" in e
               for e in gate.attempt_errors("J", old, rerun))
    status = reader(job({STATE_PATH: locked}, "built", check_json=CHECK_FAIL))
    assert any("status write while module:M01 is locked" in e for e in gate.attempt_errors("J", old, status))
    unlocked = attempts(fail("code"), fail("tool"), fail("test"), stops=[{**STOP, "after": 3}])
    assert gate.attempt_errors("J", old, reader(job({STATE_PATH: unlocked}, "built", check_json=CHECK_PASS))) == []


def test_attempt_errors_malformed_state_blocks():
    errors = gate.attempt_errors("J", reader({}), reader({STATE_PATH: "{not json"}))
    assert errors and "is not JSON" in errors[0]


def hook_repo(tmp_path, files):
    (tmp_path / ".git").mkdir()
    for rel, text in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return tmp_path


def test_hook_attempts_limit_on_state_json(tmp_path):
    root = hook_repo(tmp_path, {STATE_PATH: attempts(fail("code"))})
    target = str(root / STATE_PATH)
    write_state = lambda text: hook({"tool_name": "Write", "tool_input": {"file_path": target, "content": text}})
    assert write_state(attempts(fail("code"), fail("tool"))) == "allow"        # two causes
    assert write_state(attempts(fail("code"), fail("code"))) == "allow"        # the locking failure itself
    (root / STATE_PATH).write_text(attempts(fail("code"), fail("code")), encoding="utf-8")
    assert write_state(attempts(fail("code"), fail("code"), fail("tool"))) == "deny"
    assert write_state(attempts(fail("code"), fail("code"), fail("tool"), stops=[{**STOP, "after": 2}])) == "allow"
    assert write_state("{broken") == "deny"


def test_hook_third_failure_then_check_and_status_writes(tmp_path):
    locked = attempts(fail("code"), fail("tool"), fail("test"))
    root = hook_repo(tmp_path, {STATE_PATH: locked, "jobs/J/STATE.md": state("draft"),
                                "jobs/J/pipeline/check.json": CHECK_FAIL})
    check = {"tool_name": "Write", "tool_input": {"file_path": str(root / "jobs/J/pipeline/Check.json"),
                                                  "content": CHECK_PASS}}
    assert hook(check) == "deny"
    status = {"tool_name": "Edit", "tool_input": {"file_path": str(root / "jobs/J/STATE.md"),
                                                  "old_string": "draft", "new_string": "built"}}
    for name, text in (("spec.json", SPEC), ("spec.report.json", REPORT)):
        (root / "jobs/J/pipeline" / name).write_text(text, encoding="utf-8")
    assert hook(status) == "deny"
    (root / STATE_PATH).write_text(attempts(fail("code"), fail("tool"), fail("test"), stops=[{**STOP, "after": 3}]),
                                   encoding="utf-8")
    assert hook(check) == "allow"
    assert hook(status) == "allow"


def test_staged_attempts_limit(repo):
    write(repo, "jobs/J/STATE.md", state("draft"))
    git(repo, "commit", "-qm", "draft")
    write(repo, STATE_PATH, attempts(fail("code")))
    assert gate.staged(repo) == []                                   # HEAD has no state.json yet
    write(repo, STATE_PATH, attempts(fail("code"), fail("tool")))
    assert gate.staged(repo) == []
    write(repo, STATE_PATH, attempts(fail("code"), fail("tool"), fail("code")))
    assert gate.staged(repo) == []                                   # the locking failure itself
    git(repo, "commit", "-qm", "locked")
    write(repo, STATE_PATH, attempts(fail("code"), fail("tool"), fail("code"), fail("test")))
    errors = gate.staged(repo)
    assert any("module:M01 failure #4 appended while locked (2 open failures with cause 'code')" in e
               for e in errors), errors
    write(repo, "jobs/J/pipeline/check.json", CHECK_PASS)
    write(repo, STATE_PATH, attempts(fail("code"), fail("tool"), fail("code")))
    assert any("check.json rewritten" in e for e in gate.staged(repo))
    write(repo, STATE_PATH, attempts(fail("code"), fail("tool"), fail("code"), fail("test"),
                                     stops=[{**STOP, "after": 3}]))
    assert gate.staged(repo) == []


def test_staged_malformed_state_blocks(repo):
    write(repo, STATE_PATH, json.dumps({"failures": [{"item": "module:M01", "kind": "checker", "cause": "x"}]}))
    assert any("failures[0].cause" in e for e in gate.staged(repo))


def test_staged_initial_commit_without_head(tmp_path):
    git(tmp_path, "init", "-q")
    git(tmp_path, "config", "core.longpaths", "true")
    write(tmp_path, STATE_PATH, attempts(fail("code"), fail("code")))
    assert gate.staged(tmp_path) == []
    write(tmp_path, "jobs/J/STATE.md", state("draft"))               # a status write while locked
    assert any("status write while module:M01 is locked" in e for e in gate.staged(tmp_path))


def test_attempt_errors_deleting_a_valid_state_is_denied():
    old = reader({STATE_PATH: attempts(fail("code"), fail("code"))})
    errors = gate.attempt_errors("J", old, reader({}))
    assert errors == [f"{STATE_PATH} deleted; the failure record is append-only (#128)"]


def test_attempt_errors_removing_an_earlier_failure_is_denied():
    old = reader({STATE_PATH: attempts(fail("code"), fail("code"))})
    errors = gate.attempt_errors("J", old, reader({STATE_PATH: attempts(fail("code"))}))
    assert any("failures[1] changed or removed" in e for e in errors), errors
    errors = gate.attempt_errors("J", old, reader({STATE_PATH: attempts(fail("code"), fail("tool"))}))
    assert any("failures[1] changed or removed" in e for e in errors), errors


def test_attempt_errors_rewriting_an_earlier_cause_is_denied():
    old = reader({STATE_PATH: attempts(fail("code"), fail("code"))})
    errors = gate.attempt_errors("J", old, reader({STATE_PATH: attempts(fail("tool"), fail("code"))}))
    assert any("failures[0] changed or removed" in e for e in errors), errors


def test_attempt_errors_removing_a_stop_is_denied():
    old = reader({STATE_PATH: attempts(fail("code"), fail("code"), stops=[{**STOP, "after": 2}])})
    errors = gate.attempt_errors("J", old, reader({STATE_PATH: attempts(fail("code"), fail("code"))}))
    assert any("stops[0] changed or removed" in e for e in errors), errors


def test_attempt_errors_appending_to_an_unlocked_item_passes():
    old = reader({STATE_PATH: attempts(fail("code"))})
    new = reader({STATE_PATH: attempts(fail("code"), fail("tool", item="check:bbox"))})
    assert gate.attempt_errors("J", old, new) == []


def test_staged_deleting_the_state_is_blocked(repo):
    write(repo, STATE_PATH, attempts(fail("code"), fail("code")))
    git(repo, "commit", "-qm", "locked")
    git(repo, "rm", "-q", STATE_PATH)
    assert any("state.json deleted; the failure record is append-only" in e for e in gate.staged(repo))


@pytest.mark.parametrize("path, needle", [("jobs/J/Pipeline/State.json", "name it pipeline/state.json"),
                                          ("jobs/J/pipeline/CHECK.json", "name it pipeline/check.json")])
def test_staged_case_variant_of_pipeline_files_is_blocked(repo, path, needle):
    git(repo, "config", "core.ignorecase", "false")
    write(repo, path, attempts(fail("code")) if "tate" in path else CHECK_PASS)
    assert any(needle in e for e in gate.staged(repo))


def test_delivery_blocks_a_locked_item(repo):
    write(repo, "jobs/J/STATE.md", state("draft"))
    write(repo, STATE_PATH, attempts(fail("code"), fail("code")))
    git(repo, "commit", "-qm", "j")
    errors = gate.delivery(repo, "jobs/J")
    assert any("module:M01 is locked" in e and gate.ESCALATION in e for e in errors), errors
    (repo / STATE_PATH).write_text(attempts(fail("code"), fail("code"), stops=[{**STOP, "after": 2}]), encoding="utf-8")
    assert gate.delivery(repo, "jobs/J") == []


# --- #128 fix 1: every appended failure is judged on its own prefix -------------------------------------

def appended(old_causes, new_causes, stops=()):
    """attempt_errors for a batch that appends failures; old_causes None means there was no state.json."""
    old = reader({} if old_causes is None else {STATE_PATH: attempts(*[fail(c) for c in old_causes])})
    new = reader({STATE_PATH: attempts(*[fail(c) for c in new_causes], stops=stops)})
    return gate.attempt_errors("J", old, new)


@pytest.mark.parametrize("old, new, locking", [
    (None, ["code", "code"], None),                           # the locking failure itself is allowed
    (None, ["code", "tool"], None),                           # two different causes
    (None, ["code", "code", "tool"], 3),
    (None, ["code", "code", "tool", "test"], 3),              # one batch cannot walk past the limit
    (["code"], ["code", "code"], None),
    (["code"], ["code", "code", "tool", "test"], 3),
    (["code", "tool"], ["code", "tool", "test"], None),       # the third failure is the exact threshold
    (["code", "tool"], ["code", "tool", "test", "source"], 4),
])
def test_each_appended_failure_is_checked(old, new, locking):
    errors = appended(old, new)
    if locking is None:
        assert errors == []
    else:
        assert len(errors) == 1 and gate.ESCALATION in errors[0], errors
        assert f"module:M01 failure #{locking} appended while locked" in errors[0]


def test_a_stop_must_cover_the_position_where_the_item_locked():
    assert appended(["code"], ["code", "code", "tool", "test"], stops=[{**STOP, "after": 2}]) == []
    late = appended(["code"], ["code", "code", "tool", "test"], stops=[{**STOP, "after": 4}])
    assert len(late) == 1 and "failure #3 appended while locked" in late[0], late


def test_hook_denies_a_batch_appended_past_the_locking_point(tmp_path):
    root = hook_repo(tmp_path, {STATE_PATH: attempts(fail("code"))})
    target = str(root / STATE_PATH)
    write_state = lambda text: hook({"tool_name": "Write", "tool_input": {"file_path": target, "content": text}})
    four = [fail("code"), fail("code"), fail("tool"), fail("test")]
    assert write_state(attempts(*four)) == "deny"
    assert write_state(attempts(*four, stops=[{**STOP, "after": 2}])) == "allow"


def test_hook_denies_four_failures_written_without_an_old_state(tmp_path):
    root = hook_repo(tmp_path, {})
    target = str(root / STATE_PATH)
    write_state = lambda text: hook({"tool_name": "Write", "tool_input": {"file_path": target, "content": text}})
    four = [fail("code"), fail("code"), fail("tool"), fail("test")]
    assert write_state(attempts(*four)) == "deny"
    assert write_state(attempts(*four, stops=[{**STOP, "after": 2}])) == "allow"


def test_staged_denies_a_batch_appended_past_the_locking_point(repo):
    write(repo, STATE_PATH, attempts(fail("code")))
    git(repo, "commit", "-qm", "one failure")
    four = [fail("code"), fail("code"), fail("tool"), fail("test")]
    write(repo, STATE_PATH, attempts(*four))
    assert any("module:M01 failure #3 appended while locked" in e for e in gate.staged(repo))
    write(repo, STATE_PATH, attempts(*four, stops=[{**STOP, "after": 2}]))
    assert gate.staged(repo) == []


def test_staged_denies_four_failures_in_the_first_commit_of_the_state(repo):
    four = [fail("code"), fail("code"), fail("tool"), fail("test")]
    write(repo, STATE_PATH, attempts(*four))
    assert any("module:M01 failure #3 appended while locked" in e for e in gate.staged(repo))
    write(repo, STATE_PATH, attempts(*four, stops=[{**STOP, "after": 2}]))
    assert gate.staged(repo) == []


# --- #128 fix 2: the run itself is gated, not only the writes --------------------------------------------

@pytest.mark.parametrize("command, jobs", [
    ("uv run dt build --job jobs/J", {"J"}),
    ('dt build --job "jobs\\J"', {"J"}),
    ("py -3 jobs/J/scripts/run.py", {"J"}),
    ("python -m dt_ai.cli.main validate --archive C:/r/jobs/J/outputs/npm.zip", {"J"}),
    ("uv run dt from-source --output ./jobs/J/pipeline/v002", {"J"}),
    ("cat jobs/J/pipeline/state.json", set()),
    ("git diff jobs/J", set()),
    ("uv run dt profiles check", set()),
    ("Get-Content jobs/J/STATE.md", set()),
    ("cat jobs/J/scripts/run.py", set()),                       # a script name is not a python run
    ("C:/Python314/python.exe jobs/J/scripts/run.py", {"J"}),
    ("cd x && blender -b -P jobs/J/scripts/m01.py", {"J"}),
])
def test_command_jobs(command, jobs):
    assert gate.command_jobs(command) == jobs


def test_run_errors_reads_the_working_tree(tmp_path):
    (tmp_path / "jobs/J/pipeline").mkdir(parents=True)
    (tmp_path / STATE_PATH).write_text(attempts(fail("code"), fail("code")), encoding="utf-8")
    errors = gate.run_errors(tmp_path, "J")
    assert len(errors) == 1 and "a run of jobs/J while module:M01 is locked" in errors[0]
    assert gate.ESCALATION in errors[0]
    (tmp_path / STATE_PATH).write_text("{broken", encoding="utf-8")
    assert any("is not JSON" in e for e in gate.run_errors(tmp_path, "J"))
    (tmp_path / STATE_PATH).write_text(attempts(fail("code")), encoding="utf-8")
    assert gate.run_errors(tmp_path, "J") == []


def test_hook_denies_a_run_of_a_locked_job(tmp_path):
    root = hook_repo(tmp_path, {STATE_PATH: attempts(fail("code"), fail("code")),
                                "jobs/J/STATE.md": state("draft")})
    run = lambda tool, command: hook({"tool_name": tool, "tool_input": {"command": command}, "cwd": str(root)})
    assert run("Bash", "uv run dt build --job jobs/J") == "deny"
    assert run("PowerShell", "uv run dt build --job jobs/J") == "deny"
    assert run("Bash", "cat jobs/J/pipeline/state.json") == "allow"      # a read is not a run
    (root / STATE_PATH).write_text(attempts(fail("code"), fail("code"), stops=[{**STOP, "after": 2}]),
                                   encoding="utf-8")
    assert run("Bash", "uv run dt build --job jobs/J") == "allow"
    (root / STATE_PATH).write_text(attempts(fail("code")), encoding="utf-8")
    assert run("Bash", "uv run dt build --job jobs/J") == "allow"        # one failure: not locked


class _Report:
    development_checks_passed = True
    checks = []


def cli_repo(tmp_path):
    """A root `dt` runs in: standards/ for repo_root(), the real gate beside it and a job folder."""
    (tmp_path / "standards").mkdir()
    (tmp_path / "standards/DELIVERY_VALIDATOR.yaml").write_text("", encoding="utf-8")
    (tmp_path / "tools/git-hooks").mkdir(parents=True)
    for name in ("pipeline_gate.py", "branch_names.py"):
        shutil.copy(ROOT / "tools/git-hooks" / name, tmp_path / "tools/git-hooks" / name)
    (tmp_path / "jobs/J/pipeline").mkdir(parents=True)
    return tmp_path


def test_dt_build_refuses_to_start_inside_a_locked_job(tmp_path, monkeypatch):
    from dt_ai.cli import main as cli
    root = cli_repo(tmp_path)
    monkeypatch.chdir(root)
    built = []
    monkeypatch.setattr(cli, "build", lambda *a: built.append(a) or root / "outputs/npm.zip")
    monkeypatch.setattr(cli, "validate", lambda *a: _Report())
    argv = ["build", "--job", "jobs/J", "--output", str(tmp_path / "out")]
    (root / STATE_PATH).write_text(attempts(fail("code"), fail("code")), encoding="utf-8")
    assert cli.main(argv) == 2 and built == []
    (root / STATE_PATH).write_text(attempts(fail("code"), fail("code"), stops=[{**STOP, "after": 2}]),
                                   encoding="utf-8")
    assert cli.main(argv) == 0 and len(built) == 1
    (root / STATE_PATH).write_text(attempts(fail("code")), encoding="utf-8")
    assert cli.main(argv) == 0 and len(built) == 2


def test_settings_register_the_gate_for_runs_and_writes():
    entries = json.loads((ROOT / ".claude/settings.json").read_text(encoding="utf-8"))["hooks"]["PreToolUse"]
    matchers = [e["matcher"] for e in entries if any("pipeline_gate.py" in h["command"] for h in e["hooks"])]
    assert len(matchers) == 1, matchers
    assert {"Bash", "PowerShell", "Write", "Edit"} <= set(matchers[0].split("|"))
