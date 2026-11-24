"""Trainer v0 [D385] (#1855): bank, prompt isolation, step verdicts, calibration ranking, ledger headline."""
import json
import math
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/trainer"))
import trainer as T  # noqa: E402


def bank():
    return json.loads((ROOT / "docs/trainer/etalons.json").read_text(encoding="utf-8"))


def test_bank_lists_every_named_object_and_is_valid():
    b = bank()
    assert T.bank_problems(b) == []
    ids = {e["id"] for e in b["etalons"]}
    for want in ("kpp1-v004", "g22-k2-stage1", "63a-stage1", "63b-stage1", "63c-stage1-2", "elv-delivered",
                 "sokolniki-body-v005", "vatutino-ground-v015", "tec26-ac08"):
        assert want in ids
    ready = [e for e in b["etalons"] if e["practice_ready"]]
    assert {e["id"] for e in ready} == {"kpp1-v004", "g22-k2-stage1", "63a-stage1"}
    assert all(e["split"] == "tuning" for e in ready)
    assert any(e["split"] == "held_out" and e["status"] == "complete" for e in b["etalons"])


@pytest.mark.parametrize("mutate,needle", [
    (lambda e: e.pop("key"), "missing key"),
    (lambda e: e.__setitem__("split", "train"), "split must be"),
    (lambda e: e["sources"][0].__setitem__("sha256", None), "has no sha256"),
    (lambda e: e["sources"][0].__setitem__("sha256", "abc"), "has no sha256"),
    (lambda e: e.__setitem__("status", "incomplete"), "practice_ready needs status complete"),
    (lambda e: e.__setitem__("rejected", [{"version": "v1", "path": "x.fbx"}]), "needs reason + date"),
])
def test_bank_fail_closed(mutate, needle):
    b = bank()
    mutate(b["etalons"][0])
    assert any(needle in p for p in T.bank_problems(b))


def test_bank_empty_and_duplicate():
    assert T.bank_problems({"etalons": []}) == ["etalons: missing or empty list"]
    b = bank()
    b["etalons"].append(dict(b["etalons"][0]))
    assert any("duplicate id" in p for p in T.bank_problems(b))


def test_task_text_never_contains_key_or_rejected():
    for e in bank()["etalons"]:
        if not e["practice_ready"]:
            continue
        text = T.task_text(e, Path("C:/x/in"), Path("C:/x/out"))
        for tok in T.secret_tokens(e):
            assert tok not in text, (e["id"], tok)
        assert e["key"]["sha256"] not in text


def test_task_text_refuses_a_leaking_task():
    e = next(x for x in bank()["etalons"] if x["id"] == "g22-k2-stage1")
    e["task"] += " Compare with k2_v002r1_body_quad.fbx."
    with pytest.raises(T.TrainerError, match="leak"):
        T.task_text(e, Path("i"), Path("o"))


def test_parse_events_tokens_commands_and_stages():
    lines = [json.dumps({"t": 1, "ev": {"type": "item.completed", "item": {"type": "command_execution",
                                                                          "command": "uv run agr body p.json out"}}}),
             json.dumps({"type": "item.completed", "item": {"type": "agent_message", "text": "ok?"}}),
             "not json",
             json.dumps({"type": "turn.completed", "usage": {"input_tokens": 10, "output_tokens": 3}}),
             json.dumps({"type": "turn.completed", "usage": {"input_tokens": 5, "cached_input_tokens": 2}})]
    tok, cmds, msgs = T.parse_events(lines)
    assert tok == {"input_tokens": 15, "cached_input_tokens": 2, "output_tokens": 3}
    assert cmds == ["uv run agr body p.json out"] and msgs == ["ok?"]
    used, bypassed = T.stages_used(cmds, ["inspect", "body", "validate", "udim"])
    assert used == ["body"] and bypassed == ["inspect", "validate", "udim"]


def test_first_failing_counts_only_pass():
    steps = {s: T.step("pass") for s in T.STEPS}
    steps["package"] = T.step("not_applicable")
    assert T.first_failing(steps) is None
    for bad in ("fail", "not_run", "not_measured", "error"):
        s = dict(steps, form=T.step(bad))
        assert T.first_failing(s) == "form"
    s = dict(steps, readback=T.step("not_run"), form=T.step("fail"))
    assert T.first_failing(s) == "readback"
    with pytest.raises(T.TrainerError):
        T.step("ok")


def _dev(p95, mx, n=10):
    return {"built_to_key": {"p95": p95, "max": mx, "n": n}, "key_to_built": {"p95": p95, "max": mx, "n": n}}


def test_form_step_thresholds_and_fail_closed():
    assert T.form_step(_dev(0.05, 0.30))["status"] == "pass"  # exactly at the tolerance passes (<=)
    assert T.form_step(_dev(0.0501, 0.1))["status"] == "fail"
    assert T.form_step(_dev(0.01, 0.3001))["status"] == "fail"
    for bad in (_dev(math.nan, 0.1), _dev(0.01, math.inf), _dev(0.01, 0.1, n=0), _dev(None, 0.1), {}):
        assert T.form_step(bad)["status"] == "error"


def _rb(lo, hi, polys, quads):
    return {"meshes": [{"bounds_m": [lo, hi], "polygons": polys, "polygon_degrees": {"4": quads}}]}


def test_bounds_and_topology_steps():
    k = _rb([0, 0, 0], [10, 10, 10], 100, 100)
    assert T.bounds_step(_rb([0, 0, 0], [10.1, 10, 10], 1, 1), k)["status"] == "pass"
    assert T.bounds_step(_rb([0, 0, 0], [10.11, 10, 10], 1, 1), k)["status"] == "fail"
    assert T.bounds_step(_rb([0, 0, math.nan], [10, 10, 10], 1, 1), k)["status"] == "error"
    assert T.topology_step(_rb([0] * 3, [1] * 3, 100, 98), k)["status"] == "pass"
    assert T.topology_step(_rb([0] * 3, [1] * 3, 100, 97), k)["status"] == "fail"
    assert T.topology_step(_rb([0] * 3, [1] * 3, 0, 0), k)["status"] == "error"


def test_rank_ok_needs_strictly_better_and_rejected_not_passing():
    acc = {"score": 0.7, "form_p95_m": 0.0, "first_failing_step": "vlm"}
    assert T.rank_ok(acc, {"score": 0.4, "form_p95_m": 0.3, "first_failing_step": "bounds"})
    assert not T.rank_ok(acc, {"score": 0.7, "form_p95_m": 0.0, "first_failing_step": "vlm"})  # tie
    assert T.rank_ok(acc, {"score": 0.7, "form_p95_m": 0.01, "first_failing_step": "vlm"})
    assert not T.rank_ok(acc, {"score": 0.4, "form_p95_m": 0.3, "first_failing_step": None})  # rejected passes
    assert not T.rank_ok({"score": 0.4, "form_p95_m": None, "first_failing_step": "x"},
                         {"score": 0.4, "form_p95_m": 0.2, "first_failing_step": "x"})


def test_headline_counts_first_try_only():
    rows = [{"etalon": "a", "date": "2026-11-24", "first_failing_step": "body"},
            {"etalon": "a", "date": "2026-11-25", "first_failing_step": None},
            {"etalon": "b", "date": "2026-11-24", "first_failing_step": None}]
    assert T.headline(rows) == {"etalons_tried": 2, "passed_first_try": 1, "share": 0.5}
    assert T.headline([])["share"] is None


def test_committed_ledger_headline():
    led = json.loads((ROOT / "docs/trainer/ledger.json").read_text(encoding="utf-8"))
    assert {r["etalon"] for r in led["rows"]} >= {"kpp1-v004", "g22-k2-stage1", "63a-stage1"}
    assert all(r["first_failing_step"] for r in led["rows"])  # smoke runs: expected to fail
    assert T.headline(led["rows"])["share"] == 0.0


def _cli(*args):
    return subprocess.run([sys.executable, str(ROOT / "tools/trainer/trainer.py"), *args], capture_output=True,
                          text=True, cwd=ROOT)


def test_cli_fresh_process_refusals(tmp_path):
    assert _cli("check").returncode == 0
    p = _cli("score", "nope", "--built", "x.fbx", "--out", str(tmp_path / "r.json"))
    assert p.returncode == 2 and "unknown etalon" in p.stderr
    built = tmp_path / "b.fbx"
    built.write_bytes(b"x")
    p = _cli("score", "g22-k2-stage1", "--built", str(built), "--out", str(built))
    assert p.returncode == 2 and built.read_bytes() == b"x"
    p = _cli("score", "g22-k2-stage1", "--built", str(built), "--out", str(tmp_path / "r.json"),
             "--png", str(built))
    assert p.returncode == 2 and not (tmp_path / "r.json").exists()
    p = _cli("run", "tec26-ac08", "--out", str(tmp_path / "run"))
    assert p.returncode == 2 and "not practice_ready" in p.stderr and not (tmp_path / "run").exists()
    p = _cli("run", "63a-stage1", "--lane", "nope", "--out", str(tmp_path / "run"))
    assert p.returncode == 2 and "unknown lane" in p.stderr


def test_score_refuses_the_key_as_built(tmp_path):
    e = next(x for x in bank()["etalons"] if x["id"] == "g22-k2-stage1")
    fake = tmp_path / "copy.fbx"
    fake.write_bytes(b"Kaydara FBX Binary  \x00")
    e = dict(e, key=dict(e["key"], path=str(fake), sha256=T.sha256(fake)))
    other = tmp_path / "built.fbx"
    other.write_bytes(fake.read_bytes())
    rep = T.score(e, str(other), tmp_path / "w")
    assert rep["steps"]["artifact"]["status"] == "fail" and rep["first_failing_step"] == "artifact"
    assert rep["passed"] is False


def test_score_empty_built_dir_fails_closed(tmp_path):
    e = next(x for x in bank()["etalons"] if x["id"] == "63a-stage1")
    (tmp_path / "built").mkdir()
    rep = T.score(e, str(tmp_path / "built"), tmp_path / "w")
    assert rep["first_failing_step"] == "artifact" and all(
        rep["steps"][s]["status"] == "not_run" for s in ("readback", "form", "vlm"))


def test_agr_alias_lists_trainer():
    from dt_ai.cli import agr
    assert agr.SCRIPTS["trainer"] == "tools/trainer/trainer.py"
def test_count_questions():
    assert T.count_questions("1. a?\n2) b\n- c\ntext") == 3
    assert T.count_questions("why?\nok\nhow?") == 2
    assert T.count_questions("") == 0
