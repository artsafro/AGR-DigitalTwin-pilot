"""Build-report fail counters are a failing gate, not a note (#1031)."""
import json
import math
import random
import subprocess
import sys
from pathlib import Path

import pytest

from dt_ai.core.run_record import RunRecord
from dt_ai.validate.build_counters import (
    check_build_counters,
    check_count_parity,
    enforce,
    main,
)

ROOT = Path(__file__).resolve().parents[1]

# Synthetic equivalent of the Kasatkino g3 report (the job branch is not in this clone):
# v007 caught one bm.faces.new ValueError, v008 built every face.
G3_V007 = {"step": "g3_build_mesh", "version": "v007", "faces_in": 412, "faces_out": 411,
           "face_create_fail": 1}
G3_V008 = {"step": "g3_build_mesh", "version": "v008", "faces_in": 412, "faces_out": 412,
           "face_create_fail": 0}


def _reasons(result):
    return {(row["counter"], row["reason"]) for row in result["failures"]}


def test_zero_counter_passes():
    result = check_build_counters({"face_create_fail": 0}, ["face_create_fail"])
    assert result["status"] == "pass"
    assert result["failures"] == []
    assert result["counters"] == {"face_create_fail": 0}


def test_one_counter_fails():
    result = check_build_counters({"face_create_fail": 1}, ["face_create_fail"])
    assert result["status"] == "fail"
    assert _reasons(result) == {("face_create_fail", "nonzero")}


def test_missing_declared_counter_fails():
    result = check_build_counters({"faces_out": 10}, ["face_create_fail"])
    assert result["status"] == "fail"
    assert _reasons(result) == {("face_create_fail", "missing")}


def test_kasatkino_g3_v007_fails_with_one_and_v008_passes():
    v007 = check_build_counters(G3_V007, ["face_create_fail"])
    v008 = check_build_counters(G3_V008, ["face_create_fail"])
    assert v007["status"] == "fail" and v007["counters"]["face_create_fail"] == 1
    assert v008["status"] == "pass" and v008["counters"]["face_create_fail"] == 0


def test_no_declared_counter_is_an_error():
    with pytest.raises(ValueError, match="no fail counter declared"):
        check_build_counters({"face_create_fail": 0}, [])
    with pytest.raises(ValueError, match="counter name"):
        check_build_counters({"face_create_fail": 0}, [""])


def test_report_must_be_an_object():
    with pytest.raises(ValueError, match="report must be an object"):
        check_build_counters([("face_create_fail", 0)], ["face_create_fail"])


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf, -1, 0.5, "0", None, True, False, {}])
def test_invalid_counter_value_fails(value):
    result = check_build_counters({"face_create_fail": value}, ["face_create_fail"])
    assert result["status"] == "fail"
    assert _reasons(result) == {("face_create_fail", "invalid")}


def test_integral_float_and_lists_count():
    assert check_build_counters({"skipped": 0.0}, ["skipped"])["status"] == "pass"
    assert check_build_counters({"skipped": []}, ["skipped"])["status"] == "pass"
    listed = check_build_counters({"skipped": ["face 17"]}, ["skipped"])
    assert listed["status"] == "fail" and listed["counters"]["skipped"] == 1


def test_nested_declared_counter_uses_dotted_path():
    report = {"stats": {"plates": {"miss": 2}}}
    result = check_build_counters(report, ["stats.plates.miss"])
    assert result["status"] == "fail"
    assert result["counters"] == {"stats.plates.miss": 2}


def test_undeclared_fail_like_counter_still_fails():
    report = {"face_create_fail": 0, "patch": {"uv_skipped": 3}, "edges_missing": ["e1"]}
    result = check_build_counters(report, ["face_create_fail"])
    assert result["status"] == "fail"
    assert _reasons(result) == {("patch.uv_skipped", "undeclared_nonzero"),
                                ("edges_missing", "undeclared_nonzero")}


def test_undeclared_invalid_fail_like_counter_fails():
    result = check_build_counters({"a": 0, "face_fail": math.nan}, ["a"])
    assert _reasons(result) == {("face_fail", "undeclared_invalid")}


def test_undeclared_zero_and_unrelated_keys_pass():
    report = {"a": 0, "weld_fail": 0, "skipped": [], "failsafe": 4, "mission": 2,
              "faces_out": 12, "note": "not ideal"}
    assert check_build_counters(report, ["a"])["status"] == "pass"


@pytest.mark.parametrize("extra,reasons", [
    ({"faceCreateFail": 1}, {("faceCreateFail", "undeclared_nonzero")}),
    ({"skippedFaces": 2}, {("skippedFaces", "undeclared_nonzero")}),
    ({"fail2": 1}, {("fail2", "undeclared_nonzero")}),
    ({"UVSkipped": 1}, {("UVSkipped", "undeclared_nonzero")}),
    ({"UVSkip": 1}, {("UVSkip", "undeclared_nonzero")}),
    ({"IOFailures": 1}, {("IOFailures", "undeclared_nonzero")}),
    ({"HTTPFailCount": 1}, {("HTTPFailCount", "undeclared_nonzero")}),
    ({"2fail": 1}, {("2fail", "undeclared_nonzero")}),
    ({"faces2skip": 1}, {("faces2skip", "undeclared_nonzero")}),
])
def test_undeclared_camelcase_and_digit_suffixed_fail_counters(extra, reasons):
    report = {"face_create_fail": 0, **extra}
    result = check_build_counters(report, ["face_create_fail"])
    assert result["status"] == "fail"
    assert _reasons(result) == reasons


@pytest.mark.parametrize("extra", [{"failsafe": 1}, {"mission": 3}, {"Failsafe": 1}])
def test_undeclared_control_keys_still_pass(extra):
    report = {"face_create_fail": 0, **extra}
    assert check_build_counters(report, ["face_create_fail"])["status"] == "pass"


def test_undeclared_camelcase_zero_passes():
    report = {"face_create_fail": 0, "faceCreateFail": 0}
    assert check_build_counters(report, ["face_create_fail"])["status"] == "pass"


def test_undeclared_fail_key_in_list_of_dicts_still_fails():
    report = {"face_create_fail": 0, "layers": [{"uv_skip": 1}]}
    result = check_build_counters(report, ["face_create_fail"])
    assert result["status"] == "fail"
    assert _reasons(result) == {("layers[0].uv_skip", "undeclared_nonzero")}


def test_accepted_exception_needs_exact_count_and_source():
    report = {"face_create_fail": 1}
    ok = check_build_counters(report, ["face_create_fail"],
                              accepted={"face_create_fail": {"count": 1, "source": "Artem 2026-11-05: «ок»"}})
    assert ok["status"] == "pass"
    assert ok["accepted"] == [{"counter": "face_create_fail", "count": 1,
                               "source": "Artem 2026-11-05: «ок»"}]
    for exception in ({"count": 2, "source": "x"}, {"count": 1, "source": ""}, {"count": 1},
                      {"count": True, "source": "x"}, "yes"):
        bad = check_build_counters(report, ["face_create_fail"], accepted={"face_create_fail": exception})
        assert bad["status"] == "fail", exception
    stray = check_build_counters({"face_create_fail": 0}, ["face_create_fail"],
                                 accepted={"other_fail": {"count": 1, "source": "x"}})
    assert _reasons(stray) == {("other_fail", "accepted_unknown_counter")}


def test_count_parity():
    assert check_count_parity(412, 412)["status"] == "pass"
    gap = check_count_parity(412, 411, label="faces")
    assert gap["status"] == "fail" and gap["missing"] == 1
    assert check_count_parity(412, 413)["status"] == "fail"
    for bad in ((None, 1), (1, math.nan), (-1, -1), (True, 1), (1.5, 1.5)):
        assert check_count_parity(*bad)["status"] == "fail", bad


def test_enforce_exits_nonzero_on_failure_and_returns_on_pass(capsys):
    assert enforce(G3_V008, ["face_create_fail"])["status"] == "pass"
    with pytest.raises(SystemExit) as stop:
        enforce(G3_V007, ["face_create_fail"])
    assert stop.value.code == 1
    assert "face_create_fail" in capsys.readouterr().err


def test_probe_random_reports_fail_iff_any_counter_positive():
    rng = random.Random(1031)
    names = ["face_create_fail", "skipped", "plate_miss", "uv_failed"]
    for _ in range(500):
        report = {name: rng.choice([0, 0, 0, 1, 2, 7]) for name in names}
        declared = rng.sample(names, rng.randint(1, len(names)))
        expected = "fail" if any(report.values()) else "pass"
        assert check_build_counters(report, declared)["status"] == expected, (report, declared)


def _write(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_cli_exit_codes(tmp_path, capsys):
    v007 = _write(tmp_path / "g3_v007.json", G3_V007)
    v008 = _write(tmp_path / "g3_v008.json", G3_V008)
    assert main(["--report", str(v008), "--counter", "face_create_fail"]) == 0
    assert main(["--report", str(v007), "--counter", "face_create_fail"]) == 1
    printed = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert printed["status"] == "fail"
    assert main(["--report", str(v007), "--counter", "face_create_fail",
                 "--source-count", "412", "--output-count", "411"]) == 1
    assert main(["--report", str(v008), "--counter", "face_create_fail",
                 "--source-count", "412", "--output-count", "411"]) == 1
    assert main(["--report", str(v008), "--counter", "face_create_fail",
                 "--source-count", "412", "--output-count", "412"]) == 0


def test_cli_count_parity_alone_catches_silent_skip(capsys):
    assert main(["--source-count", "412", "--output-count", "411"]) == 1
    printed = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert printed["count_parity"]["missing"] == 1 and printed["counters"] is None
    assert main(["--source-count", "412", "--output-count", "412"]) == 0
    assert main(["--source-count", "-1", "--output-count", "-1"]) == 1
    assert main(["--source-count", "nan", "--output-count", "1"]) == 2
    assert main([]) == 2
    assert main(["--counter", "face_create_fail", "--source-count", "1", "--output-count", "1"]) == 2


def test_rule_is_written_in_workflow_skills_and_checker():
    flat = lambda rel: " ".join((ROOT / rel).read_text(encoding="utf-8").split())
    for rel in ("docs/agents/WORKFLOW.md", ".agents/skills/run-evidence/SKILL.md",
                ".agents/skills/validate-delivery/SKILL.md", ".claude/skills/run-evidence/SKILL.md",
                ".claude/skills/validate-delivery/SKILL.md", ".claude/agents/independent-checker.md"):
        text = flat(rel)
        assert "#1031" in text and "dt_ai.validate.build_counters" in text, rel
    loop = flat("docs/agents/WORKFLOW.md").split("## Loop", 1)[1].split("## Before requesting review", 1)[0]
    assert "is a failing gate, not a note" in loop
    assert "the user accepts the listed exceptions" in loop
    assert "source_count" in flat(".claude/agents/independent-checker.md")


def test_cli_unusable_input_exits_2_and_writes_nothing(tmp_path):
    report = _write(tmp_path / "r.json", G3_V008)
    broken = tmp_path / "broken.json"
    broken.write_text("{", encoding="utf-8")
    assert main(["--report", str(tmp_path / "absent.json"), "--counter", "x"]) == 2
    assert main(["--report", str(broken), "--counter", "x"]) == 2
    assert main(["--report", str(report)]) == 2
    assert main(["--report", str(report), "--counter", "face_create_fail", "--source-count", "1"]) == 2
    before = report.read_bytes()
    assert main(["--report", str(report), "--counter", "face_create_fail", "--out", str(report)]) == 2
    alias = tmp_path / "." / "r.json"
    assert main(["--report", str(report), "--counter", "face_create_fail", "--out", str(alias)]) == 2
    assert report.read_bytes() == before
    existing = _write(tmp_path / "old.json", {"keep": 1})
    assert main(["--report", str(report), "--counter", "face_create_fail", "--out", str(existing)]) == 2
    assert json.loads(existing.read_text(encoding="utf-8")) == {"keep": 1}
    assert sorted(p.name for p in tmp_path.iterdir()) == ["broken.json", "old.json", "r.json"]


def test_cli_writes_result_file(tmp_path):
    report = _write(tmp_path / "r.json", G3_V007)
    out = tmp_path / "gate" / "counters.json"
    assert main(["--report", str(report), "--counter", "face_create_fail", "--out", str(out)]) == 1
    assert json.loads(out.read_text(encoding="utf-8"))["status"] == "fail"
    assert not out.with_name(out.name + ".partial").exists()


def test_fresh_process_cli_and_runrecord_marks_stage_failed(tmp_path):
    report = _write(tmp_path / "g3_v007.json", G3_V007)
    out = tmp_path / "gate.json"
    argv = [sys.executable, "-m", "dt_ai.validate.build_counters", "--report", str(report),
            "--counter", "face_create_fail", "--out", str(out)]
    assert subprocess.run(argv, cwd=ROOT, capture_output=True).returncode == 1
    out.unlink()
    record = RunRecord.create(tmp_path / "runs", "g3-v007", {"report": str(report)})
    returned = record.run_stage("counter_gate", argv, {"gate": str(out)}, cwd=ROOT)
    stage = record.read()["attempts"][-1]["stages"]["counter_gate"]
    assert returned["status"] == "failed"
    assert stage["status"] == "failed"
    assert stage["returncode"] == 1
