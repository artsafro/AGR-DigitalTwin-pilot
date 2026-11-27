"""#2066: User Proxy (separate from the evaluator), stage-task set dev/holdout, per-run metrics.

Pattern: n/a | new-case: tests/tools/test_user_proxy.py - user proxy isolation, stage set, run metrics.

The proxy answers a practice-run stop ONLY with an approved answer (verbatim from a cited D-row, job decision,
fact export or delivery key fact); otherwise it records UNRESOLVED. It never sees the hidden key or the evaluator
criteria (isolation tested like the trainer key-leak guards)."""
import ast
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/trainer"))
import trainer as T  # noqa: E402
import user_proxy as U  # noqa: E402

PROXY = ROOT / "tools/trainer/user_proxy.py"


def bank():
    return json.loads((ROOT / "docs/trainer/etalons.json").read_text(encoding="utf-8"))


def entries():
    return {e["id"]: e for e in bank()["etalons"]}


def pack(answers):
    return {"schema": "user-proxy-pack/1", "task": "t", "answers": answers}


ANS = {"id": "A1", "match": [["curb"], ["kerb"]], "answer": "Curbs: not modelled",
       "source": "jobs/x/STATE.md#user-decisions", "source_kind": "job_decision", "stop_class": "customer_decision"}


def ask(tmp_path, p, question, *extra):
    (tmp_path / "pack.json").write_text(json.dumps(p), encoding="utf-8")
    r = subprocess.run([sys.executable, str(PROXY), "ask", "--pack", str(tmp_path / "pack.json"), "--log",
                        str(tmp_path / "log.jsonl"), *extra, question], capture_output=True, text=True,
                       encoding="utf-8")
    log = [json.loads(x) for x in (tmp_path / "log.jsonl").read_text(encoding="utf-8").splitlines()] \
        if (tmp_path / "log.jsonl").exists() else []
    return r, log


# ---------------------------------------------------------------- proxy process isolation
def test_proxy_is_a_separate_module_that_never_sees_the_evaluator():
    src = PROXY.read_text(encoding="utf-8")
    tree = ast.parse(src)
    imported = {n.names[0].name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import)} | \
        {(n.module or "").split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert not imported & {"trainer", "trainer_ab", "dt_ai", "twinqa", "surface_dev"}
    for evaluator_word in ("etalons.json", "1855-trainer-v0", "TOL", "score(", "key_markers", "pairs_v1"):
        assert evaluator_word not in src


def test_answer_is_verbatim_from_the_pack_and_cites_its_source(tmp_path):
    r, log = ask(tmp_path, pack([ANS]), "Should I model the curbs along the paths?")
    assert r.returncode == 0
    assert "Curbs: not modelled" in r.stdout and "jobs/x/STATE.md#user-decisions" in r.stdout
    assert log[-1]["verdict"] == "answered" and log[-1]["answer_id"] == "A1"
    assert log[-1]["stop_class"] == "customer_decision" and log[-1]["stop_group"] == "justified"


def test_no_approved_answer_records_unresolved_and_invents_nothing(tmp_path):
    r, log = ask(tmp_path, pack([ANS]), "Which lawn texture resolution do you want?", "--class",
                 "allowed_technical_choice")
    assert r.returncode == 0 and r.stdout.startswith("UNRESOLVED")
    assert "not modelled" not in r.stdout
    assert log[-1]["verdict"] == "unresolved" and log[-1]["answer"] is None and log[-1]["source"] is None
    assert log[-1]["stop_class"] == "allowed_technical_choice" and log[-1]["stop_group"] == "unnecessary"


def test_ambiguous_match_is_unresolved_never_a_guess(tmp_path):
    other = dict(ANS, id="A2", match=[["paths"]], answer="Paths: paving ID02")
    r, log = ask(tmp_path, pack([ANS, other]), "Curbs along the paths?")
    assert r.stdout.startswith("UNRESOLVED")
    assert log[-1]["verdict"] == "unresolved" and sorted(log[-1]["candidates"]) == ["A1", "A2"]


def test_unknown_class_is_refused_and_unclassified_is_the_default(tmp_path):
    r, _ = ask(tmp_path, pack([ANS]), "q?", "--class", "whatever")
    assert r.returncode == 2
    r, log = ask(tmp_path, pack([ANS]), "Anything else?")
    assert log[-1]["stop_class"] == "unclassified" and log[-1]["stop_group"] == "unclassified"


@pytest.mark.parametrize("field", ["key", "sha256", "tolerances", "steps", "rejected", "score"])
def test_pack_carrying_evaluator_or_key_fields_is_refused(tmp_path, field):
    r, log = ask(tmp_path, pack([dict(ANS, **{field: "x"})]), "curbs?")
    assert r.returncode == 2 and "refused" in r.stderr and log == []
    p = pack([ANS])
    p[field] = "x"
    r, _ = ask(tmp_path, p, "curbs?")
    assert r.returncode == 2


@pytest.mark.parametrize("hint", ["run tools/ground/build.py", "use agr body --lattice", "see src/dt_ai/x.py",
                                  "the hidden key says so", "trainer tolerance 5 cm"])
def test_pack_answer_hinting_the_method_or_criteria_is_refused(tmp_path, hint):
    r, _ = ask(tmp_path, pack([dict(ANS, answer=hint)]), "curbs?")
    assert r.returncode == 2 and "refused" in r.stderr


def test_answer_without_a_cited_source_is_refused(tmp_path):
    r, _ = ask(tmp_path, pack([dict(ANS, source="")]), "curbs?")
    assert r.returncode == 2


def test_stop_class_table_matches_the_approved_plan():
    assert U.STOP_CLASSES == {
        "missing_source_data": "justified", "customer_decision": "justified", "irreversible_sanction": "justified",
        "answer_in_repo": "unnecessary", "allowed_technical_choice": "unnecessary",
        "tool_broken": "harness", "instructions_contradict": "context"}


# ---------------------------------------------------------------- trainer side: pack building
def test_bank_proxy_packs_are_verbatim_and_never_leak_key_or_criteria():
    built = 0
    for e in bank()["etalons"]:
        if "proxy_answers" not in e:
            continue
        p = T.proxy_pack(e)
        text = json.dumps(p, ensure_ascii=False).lower()
        assert not [t for t in T.scan_tokens(e) if t in text]
        for crit in [*T.TOL, "form_v2", "surface_dev", "pairs_v1", "etalon"]:
            assert crit.lower() not in text
        assert U.pack_problems(p) == []
        built += 1
    assert built >= 2


def test_pack_refuses_an_invented_answer_not_in_the_cited_source():
    e = entries()["moskovsky-ground-v002"]
    bad = dict(e, proxy_answers=[dict(e["proxy_answers"][0], answer="Curbs: model them 150 mm high")])
    with pytest.raises(T.TrainerError, match="not verbatim"):
        T.proxy_pack(bad)


def test_pack_refuses_unknown_drow_and_missing_job_file():
    e = entries()["kpp1-ucx-v004"]
    a = e["proxy_answers"][0]
    with pytest.raises(T.TrainerError, match="unknown decision"):
        T.proxy_pack(dict(e, proxy_answers=[dict(a, source="D99999")]))
    with pytest.raises(T.TrainerError, match="source file"):
        T.proxy_pack(dict(e, proxy_answers=[dict(a, source="jobs/NOPE/STATE.md", source_kind="job_decision")]))


def test_pack_refuses_an_answer_naming_the_key():
    e = entries()["kpp1-ucx-v004"]
    a = dict(e["proxy_answers"][0], answer=Path(e["key"]["path"]).name)
    with pytest.raises(T.TrainerError, match="names the key|not verbatim"):
        T.proxy_pack(dict(e, proxy_answers=[a]))


def test_install_proxy_writes_only_the_proxy_and_its_pack(tmp_path):
    e = entries()["moskovsky-ground-v002"]
    d = T.install_proxy(tmp_path / "run", e)
    assert sorted(p.name for p in d.iterdir()) == ["ask.py", "pack.json"]
    assert (d / "ask.py").read_bytes() == PROXY.read_bytes()
    assert not T.leaking_files(d, T.scan_tokens(e))


def test_task_text_with_proxy_names_the_ask_command_not_the_pack():
    e = entries()["moskovsky-ground-v002"]
    plain = T.task_text(e, Path("i"), Path("o"))
    text = T.task_text(e, Path("i"), Path("o"), proxy=Path("C:/x/run/proxy"))
    assert "nobody answers questions" in plain and "ask.py" not in plain
    assert "C:/x/run/proxy/ask.py" in text.replace("\\", "/") and "nobody answers questions" not in text
    assert "pack.json" not in text and "UNRESOLVED" in text
    for a in e["proxy_answers"]:
        assert a["answer"] not in text


# ---------------------------------------------------------------- stage-task set
def test_stage_set_is_dev_plus_unfamiliar_holdout():
    b = bank()
    assert T.bank_problems(b) == []
    st = T.stage_tasks(b)
    dev = [s for s in st if s["set"] == "dev"]
    hold = [s for s in st if s["set"] == "holdout"]
    assert 3 <= len(st) <= 5 and dev and hold
    assert 0.2 <= len(hold) / len(st) <= 0.34
    ents = entries()
    assert all(ents[s["id"]]["practice_ready"] for s in st)
    assert any(not s["familiar"] for s in hold)
    dev_projects = {s["project"] for s in dev}
    assert all(s["project"] not in dev_projects for s in hold if not s["familiar"])


@pytest.mark.parametrize("mutate,needle", [
    (lambda b: b["stage_tasks"]["tasks"][0].__setitem__("set", "train"), "set must be dev|holdout"),
    (lambda b: b["stage_tasks"]["tasks"][0].__setitem__("id", "nope"), "unknown etalon"),
    (lambda b: b["stage_tasks"]["tasks"][0].__setitem__("metrics", ["vibes"]), "unknown metric"),
    (lambda b: [t.__setitem__("familiar", True) for t in b["stage_tasks"]["tasks"]], "unfamiliar holdout"),
    (lambda b: [t.__setitem__("set", "dev") for t in b["stage_tasks"]["tasks"]], "unfamiliar holdout"),
])
def test_stage_set_fail_closed(mutate, needle):
    b = bank()
    mutate(b)
    assert any(needle in p for p in T.bank_problems(b))


def test_holdout_stage_on_a_tuning_etalon_is_refused():
    b = bank()
    hold = next(t for t in b["stage_tasks"]["tasks"] if t["set"] == "holdout")
    next(e for e in b["etalons"] if e["id"] == hold["id"])["split"] = "tuning"
    assert any("holdout needs split held_out" in p for p in T.bank_problems(b))


# ---------------------------------------------------------------- ucx metric
def _rb(meshes):
    return {"meshes": [{"name": n, "triangles": t, "polygons": t, "bounds_m": [[0, 0, 0], [1, 1, 1]]}
                       for n, t in meshes]}


def test_ucx_step_measures_presence_and_d012_budget():
    key = _rb([("SM_A_Main", 1000), ("UCX_SM_A_Main_001", 12), ("UCX_SM_A_Main_002", 12)])
    ok = T.ucx_step(_rb([("SM_A_Main", 1000), ("UCX_SM_A_Main_001", 12)]), key)
    assert ok["status"] == "pass" and ok["ucx_meshes"] == 1 and ok["key_ucx_meshes"] == 2
    assert ok["ucx_limit"] == 15000
    assert T.ucx_step(_rb([("SM_A_Main", 1000)]), key)["status"] == "fail"
    assert T.ucx_step(_rb([("SM_A_Main", 1000), ("UCX_SM_A_Main_001", 15001)]), key)["status"] == "fail"


# ---------------------------------------------------------------- per-run metrics
def _ev(item, t="item.completed"):
    return json.dumps({"type": t, "item": item})


def test_run_metrics_cover_the_approved_columns(tmp_path):
    run = tmp_path / "run"
    (run / "built").mkdir(parents=True)
    (run / "proxy").mkdir()
    (run / "run.json").write_text(json.dumps({"wall_s": 12.5, "exit": 0, "tokens": {
        "input_tokens": 1000, "cached_input_tokens": 200, "output_tokens": 50}}), encoding="utf-8")
    cmds = [_ev({"type": "command_execution", "command": "ls", "exit_code": 0}),
            _ev({"type": "command_execution", "command": "python build.py", "exit_code": 1}),
            _ev({"type": "command_execution", "command": "python build.py", "exit_code": 1}),
            _ev({"type": "command_execution", "command": "cat C:/x/run/proxy/pack.json", "exit_code": 0}),
            json.dumps({"type": "turn.completed", "usage": {"input_tokens": 1000, "output_tokens": 50}})]
    (run / "events.jsonl").write_text("\n".join(cmds) + "\n", encoding="utf-8")
    log = [{"verdict": "answered", "stop_class": "answer_in_repo", "stop_group": "unnecessary"},
           {"verdict": "unresolved", "stop_class": "customer_decision", "stop_group": "justified"},
           {"verdict": "unresolved", "stop_class": "tool_broken", "stop_group": "harness"}]
    (run / "proxy" / "log.jsonl").write_text("\n".join(json.dumps(x) for x in log) + "\n", encoding="utf-8")
    sc = tmp_path / "score.json"
    sc.write_text(json.dumps({"passed": False, "score": 0.5, "first_failing_step": "form"}), encoding="utf-8")
    m = T.stage_metrics(run, score_json=sc, usd_per_mtok=(1.0, 4.0))
    assert m["success"] is False and m["quality_score"] == 0.5 and m["first_failing_step"] == "form"
    assert m["human_interventions"] == 1 and m["unresolved"] == 2 and m["stops"] == 3
    assert m["unnecessary_stops"] == {"answer_in_repo": 1}
    assert m["stops_by_group"] == {"unnecessary": 1, "justified": 1, "harness": 1}
    assert m["tokens"]["input_tokens"] == 1000 and m["cost_usd"] == pytest.approx(0.0012)
    assert m["wall_s"] == 12.5
    assert m["repeated_commands"] == 1 and m["failed_commands"] == 2
    assert m["proxy_pack_reads"] == 1


def test_run_metrics_without_score_or_proxy_are_explicit_nones(tmp_path):
    run = tmp_path / "run"
    run.mkdir()
    (run / "run.json").write_text(json.dumps({"wall_s": 1, "exit": 0, "tokens": {
        "input_tokens": 0, "cached_input_tokens": 0, "output_tokens": 0}}), encoding="utf-8")
    m = T.stage_metrics(run)
    assert m["success"] is None and m["quality_score"] is None and m["cost_usd"] is None
    assert m["stops"] == 0 and m["proxy"] is False


# ---------------------------------------------------------------- one dry run per stage task
def test_dry_run_every_stage_task_with_the_proxy(tmp_path, capsys):
    b = T.load_bank()
    for s in T.stage_tasks(b):
        e = T.etalon(b, s["id"])
        if not all(Path(x["path"]).is_file() for x in e["sources"]):
            pytest.skip("Drive sources not reachable")
        a = SimpleNamespace(etalon=s["id"], lane="codex", out=str(tmp_path / s["id"]), timeout_s=1, dry_run=True,
                            proxy=True)
        assert T.cmd_run(a, b) == 0
        out = capsys.readouterr().out
        assert "ask.py" in out and not (tmp_path / s["id"]).exists()
        assert not [t for t in T.scan_tokens(e) if t in out.lower()]
