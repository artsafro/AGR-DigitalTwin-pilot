"""Report stamps (standards digest, code commit) and --recheck of a stored report (issue #511).

recheck reads an old report.json and says whether its verdict still holds now:
current (standards and target unchanged), stale_standards (a rule file changed),
evidence_missing (the target is gone or changed). The old report is never rewritten.
"""
import json
import shutil
import struct
import subprocess
import sys
from pathlib import Path

import pytest

import validate_package as vp
from twinqa.io import digest, digest_text
from twinqa.profiles import DEFAULT_STANDARDS, load_profiles, standards_digest

OLD_KEYS = {"profile", "target", "target_sha256", "source_sha256", "source_pdf_verified", "passed", "exit_code",
            "machine_stage_counts", "manual_reviews_pending", "stages", "notes"}


def fbx(version=7400):
    return b"Kaydara FBX Binary  \x00\x1a\x00" + struct.pack("<I", version) + b"\x00" * 64


@pytest.fixture
def standards(tmp_path, monkeypatch):
    folder = tmp_path / "standards"
    shutil.copytree(DEFAULT_STANDARDS, folder, ignore=shutil.ignore_patterns("*.pdf"))
    lock_path = folder / "source/source-lock.json"
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    lock["pdf_default_location"] = str(tmp_path / "absent.pdf")
    lock_path.write_text(json.dumps(lock), encoding="utf-8")
    monkeypatch.delenv("TWINQA_REGULATION_PDF", raising=False)
    return folder


@pytest.fixture
def old(tmp_path, standards, capsys):
    """A stored report.json of a header-only FBX, written by the CLI."""
    target = tmp_path / "model.fbx"
    target.write_bytes(fbx())
    code = vp.main([str(target), "--json", "--standards", str(standards)])
    report = tmp_path / "report.json"
    report.write_text(capsys.readouterr().out, encoding="utf-8")
    assert code == 2
    return report


def edit_threshold(folder, relock=True):
    path = folder / "NPM_STANDARD.yaml"
    text = path.read_text(encoding="utf-8")
    assert "max_characters: 254" in text
    path.write_text(text.replace("max_characters: 254", "max_characters: 200"), encoding="utf-8")
    if relock:
        lock_path = folder / "source/source-lock.json"
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        lock["profiles"]["NPM_STANDARD.yaml"] = digest_text(path)
        lock_path.write_text(json.dumps(lock), encoding="utf-8")


def recheck(old, standards, out, *extra):
    return vp.main(["--recheck", str(old), "--output", str(out), "--standards", str(standards), *extra])


# --- stamps -------------------------------------------------------------------------------------------

def test_report_stamps_standards_digest_and_code_commit_keeping_old_keys(old, standards):
    data = json.loads(old.read_text(encoding="utf-8"))
    assert OLD_KEYS <= set(data)
    assert data["standards_sha256"] == standards_digest(standards) == load_profiles(standards).standards_sha256
    assert len(data["standards_sha256"]) == 64
    head = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True,
                          cwd=Path(vp.__file__).parent).stdout.strip()
    assert data["code_commit"] == head and len(head) == 40


def test_standards_digest_moves_with_a_threshold_and_ignores_line_endings(standards):
    before = standards_digest(standards)
    for name in ("NPM_STANDARD.yaml", "traceability.json"):
        p = standards / name
        p.write_bytes(p.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
    assert standards_digest(standards) == before
    edit_threshold(standards)
    assert standards_digest(standards) != before


def test_standards_digest_ignores_machine_pdf_location(standards):
    before = standards_digest(standards)
    lock_path = standards / "source/source-lock.json"
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    lock["pdf_default_location"] = "Z:/elsewhere.pdf"
    lock_path.write_text(json.dumps(lock), encoding="utf-8")
    assert standards_digest(standards) == before


def test_standards_digest_missing_rule_file_is_an_error(standards):
    (standards / "VPM_STANDARD.yaml").unlink()
    with pytest.raises(OSError):
        standards_digest(standards)


# --- recheck: the three verdicts ----------------------------------------------------------------------

def run_recheck(old, standards, out, capsys):
    before = old.read_bytes()
    code = recheck(old, standards, out, "--json")
    printed = capsys.readouterr().out
    assert old.read_bytes() == before  # old report byte-identical
    return code, printed


def test_recheck_unchanged_is_current(old, standards, tmp_path, capsys):
    out = tmp_path / "recheck.json"
    code, printed = run_recheck(old, standards, out, capsys)
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["status"] == "current" and json.loads(printed) == data
    assert code == data["exit_code"] == json.loads(old.read_text(encoding="utf-8"))["exit_code"] == 2
    assert data["recheck_of_sha256"] == digest(old.read_bytes())


def test_recheck_current_keeps_a_stored_pass(old, standards, tmp_path, capsys):
    data = json.loads(old.read_text(encoding="utf-8"))
    data["passed"], data["exit_code"] = True, 0
    old.write_text(json.dumps(data), encoding="utf-8")
    out = tmp_path / "recheck.json"
    code, _ = run_recheck(old, standards, out, capsys)
    new = json.loads(out.read_text(encoding="utf-8"))
    assert (code, new["status"], new["passed"]) == (0, "current", True)


@pytest.mark.parametrize("relock", [True, False])
def test_recheck_edited_threshold_is_stale_standards(old, standards, tmp_path, capsys, relock):
    edit_threshold(standards, relock)
    out = tmp_path / "recheck.json"
    code, printed = run_recheck(old, standards, out, capsys)
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["status"] == "stale_standards" and data["passed"] is False
    assert code == data["exit_code"] != 0


@pytest.mark.parametrize("change", ["delete", "modify"])
def test_recheck_target_gone_or_changed_is_evidence_missing(old, standards, tmp_path, capsys, change):
    target = tmp_path / "model.fbx"
    if change == "delete":
        target.unlink()
    else:
        target.write_bytes(fbx(7500))
    out = tmp_path / "recheck.json"
    code, _ = run_recheck(old, standards, out, capsys)
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["status"] == "evidence_missing" and data["passed"] is False
    assert code == data["exit_code"] != 0


def test_recheck_both_changed_reports_evidence_missing_with_both_reasons(old, standards, tmp_path, capsys):
    (tmp_path / "model.fbx").unlink()
    edit_threshold(standards)
    out = tmp_path / "recheck.json"
    code, _ = run_recheck(old, standards, out, capsys)
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["status"] == "evidence_missing" and code != 0
    assert len(data["reasons"]) == 2


@pytest.mark.parametrize("break_it", ["stale", "missing"])
def test_stale_or_missing_text_never_prints_pass(old, standards, tmp_path, capsys, break_it):
    data = json.loads(old.read_text(encoding="utf-8"))
    data["passed"], data["exit_code"] = True, 0  # even a stored pass is not re-confirmed
    old.write_text(json.dumps(data), encoding="utf-8")
    if break_it == "stale":
        edit_threshold(standards)
    else:
        (tmp_path / "model.fbx").unlink()
    code = recheck(old, standards, tmp_path / "r.json")
    text = capsys.readouterr().out
    assert code != 0 and "pass" not in text.lower()
    assert json.loads((tmp_path / "r.json").read_text(encoding="utf-8"))["passed"] is False


def test_legacy_report_without_standards_digest_is_stale(old, standards, tmp_path, capsys):
    data = json.loads(old.read_text(encoding="utf-8"))
    del data["standards_sha256"]
    old.write_text(json.dumps(data), encoding="utf-8")
    out = tmp_path / "recheck.json"
    code, _ = run_recheck(old, standards, out, capsys)
    assert json.loads(out.read_text(encoding="utf-8"))["status"] == "stale_standards" and code != 0


# --- recheck: output is a new file, inputs are never touched -----------------------------------------

@pytest.mark.parametrize("alias", ["old", "target", "existing", "old_partial", "target_partial"])
def test_output_aliasing_an_input_or_existing_file_is_refused(old, standards, tmp_path, alias, capsys):
    target = tmp_path / "model.fbx"
    if alias == "existing":
        out = tmp_path / "exists.json"
        out.write_text("keep", encoding="utf-8")
    elif alias == "old":
        out = tmp_path / "." / "report.json"
    elif alias == "target":
        out = target
    elif alias == "old_partial":  # out.partial would be the old report
        old2 = tmp_path / "x.json.partial"
        old2.write_bytes(old.read_bytes())
        old, out = old2, tmp_path / "x.json"
    else:
        data = json.loads(old.read_text(encoding="utf-8"))
        data["target"] = str(tmp_path / "t.fbx.partial")
        (tmp_path / "t.fbx.partial").write_bytes(target.read_bytes())
        data["target_sha256"] = digest(target.read_bytes())
        old.write_text(json.dumps(data), encoding="utf-8")
        out = tmp_path / "t.fbx"
    snapshot = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    assert recheck(old, standards, out) != 0
    assert {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()} == snapshot
    assert "pass" not in capsys.readouterr().out.lower()


@pytest.mark.parametrize("body", ["", "[]", "{}", "{not json", '{"recheck_of": "a"}'])
def test_malformed_old_report_is_an_error_and_writes_nothing(standards, tmp_path, body, capsys):
    old = tmp_path / "bad.json"
    old.write_text(body, encoding="utf-8")
    out = tmp_path / "r.json"
    assert recheck(old, standards, out) != 0
    assert not out.exists() and not Path(str(out) + ".partial").exists()
    assert "pass" not in capsys.readouterr().out.lower()


@pytest.mark.parametrize("field, value", [("passed", "true"), ("exit_code", 7), ("exit_code", True),
                                          ("target_sha256", "abc"), ("target", ""), ("passed", None),
                                          ("standards_sha256", 5)])
def test_old_report_with_bad_field_types_is_an_error(old, standards, tmp_path, field, value):
    data = json.loads(old.read_text(encoding="utf-8"))
    data[field] = value
    old.write_text(json.dumps(data), encoding="utf-8")
    out = tmp_path / "r.json"
    assert recheck(old, standards, out) != 0 and not out.exists()


def test_inconsistent_passed_and_exit_code_is_an_error(old, standards, tmp_path):
    data = json.loads(old.read_text(encoding="utf-8"))
    data["passed"] = True  # exit_code stays 2
    old.write_text(json.dumps(data), encoding="utf-8")
    assert recheck(old, standards, tmp_path / "r.json") != 0 and not (tmp_path / "r.json").exists()


def test_recheck_requires_output_and_excludes_a_target(old, standards, tmp_path):
    with pytest.raises(SystemExit) as exc:
        vp.main(["--recheck", str(old), "--standards", str(standards)])
    assert exc.value.code != 0
    with pytest.raises(SystemExit) as exc:
        vp.main([str(tmp_path / "model.fbx"), "--recheck", str(old), "--output", str(tmp_path / "r.json")])
    assert exc.value.code != 0


def test_recheck_in_a_fresh_process(old, standards, tmp_path):
    edit_threshold(standards)
    out = tmp_path / "r.json"
    script = Path(vp.__file__)
    proc = subprocess.run([sys.executable, str(script), "--recheck", str(old), "--output", str(out),
                           "--standards", str(standards)], capture_output=True, text=True, encoding="utf-8")
    assert proc.returncode != 0 and "pass" not in proc.stdout.lower(), proc.stderr
    assert json.loads(out.read_text(encoding="utf-8"))["status"] == "stale_standards"


@pytest.mark.parametrize("cwd, status", [("tmp", "current"), ("standards", "evidence_missing")])
def test_relative_target_resolves_against_cwd_like_validate(old, standards, tmp_path, capsys, monkeypatch,
                                                            cwd, status):
    data = json.loads(old.read_text(encoding="utf-8"))
    data["target"] = "model.fbx"
    old.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.chdir(tmp_path if cwd == "tmp" else standards)
    out = tmp_path / "r.json"
    run_recheck(old, standards, out, capsys)
    assert json.loads(out.read_text(encoding="utf-8"))["status"] == status


# --- probe: every combination of target x standards x stored verdict ---------------------------------

@pytest.mark.parametrize("stored_ok", [True, False])
@pytest.mark.parametrize("std", ["same", "edited", "edited_unlocked", "legacy"])
@pytest.mark.parametrize("tgt", ["same", "changed", "deleted"])
def test_probe_recheck_matrix(old, standards, tmp_path, capsys, tgt, std, stored_ok):
    data = json.loads(old.read_text(encoding="utf-8"))
    data["passed"], data["exit_code"] = stored_ok, 0 if stored_ok else 1
    if std == "legacy":
        del data["standards_sha256"], data["code_commit"]
    old.write_text(json.dumps(data), encoding="utf-8")
    if std.startswith("edited"):
        edit_threshold(standards, relock=std == "edited")
    target = tmp_path / "model.fbx"
    if tgt == "changed":
        target.write_bytes(target.read_bytes() + b"\x00")
    elif tgt == "deleted":
        target.unlink()
    before = old.read_bytes()
    out = tmp_path / "probe.json"
    code = recheck(old, standards, out)
    text = capsys.readouterr().out
    new = json.loads(out.read_text(encoding="utf-8"))
    expected = "evidence_missing" if tgt != "same" else "stale_standards" if std != "same" else "current"
    assert old.read_bytes() == before and new["status"] == expected
    if expected == "current":
        assert code == new["exit_code"] == data["exit_code"] and new["passed"] is stored_ok
    else:
        assert code == new["exit_code"] in (3, 4) and new["passed"] is False and "pass" not in text.lower()


def test_missing_standards_folder_is_an_error_and_writes_nothing(old, tmp_path):
    out = tmp_path / "r.json"
    assert recheck(old, tmp_path / "no-standards", out) == 2 and not out.exists()


def test_output_case_alias_of_old_report_is_refused(old, standards, tmp_path):
    before = old.read_bytes()
    assert recheck(old, standards, tmp_path / "REPORT.JSON") != 0
    assert old.read_bytes() == before
