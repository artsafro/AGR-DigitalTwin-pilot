"""Trainer v0 [D387] (#1855): bank, prompt isolation, step verdicts, calibration ranking, ledger headline."""
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
        assert "[D389]" in text and "accoreconsole" in text and "3ds Max is NOT available" in text


def test_d389_row_recorded_once():
    rows = [ln for ln in (T.ROOT / "docs/decisions.md").read_text(encoding="utf-8").splitlines()
            if ln.startswith("| D389 |")]
    assert len(rows) == 1 and "AutoCAD Core Console" in rows[0] and "3ds Max" in rows[0]


def test_task_text_states_practice_self_gates_d391():
    """[D391]: practice runs self-confirm Gate 1 / BM-12 with a hash-bound, labelled record; not acceptance."""
    for e in bank()["etalons"]:
        if not e["practice_ready"]:
            continue
        text = T.task_text(e, Path("C:/x/in"), Path("C:/x/out"))
        assert "[D391]" in text and "gate1=practice-self" in text and "bm12=practice-self" in text
        assert "approval_sha256" in text and "not acceptance" in text and "agr trainer run" in text
        # r81 finding: 6/6 agents reported `review` is not a PartsList status (draft|confirmed)
        assert "status draft" in text and "status review" not in text


def test_d391_row_recorded_once():
    rows = [ln for ln in (T.ROOT / "docs/decisions.md").read_text(encoding="utf-8").splitlines()
            if ln.startswith("| D391 |")]
    assert len(rows) == 1 and "gate1=practice-self" in rows[0] and "Real jobs" in rows[0]


def test_dwg_practice_prompt_requires_intake_and_stops_on_failure():
    entries = {e["id"]: e for e in bank()["etalons"]}
    text = T.task_text(entries["kpp1-v004"], Path("i"), Path("o"))
    assert "--timeout 60" in text
    assert text.index("dxf_intake.py") < text.index("plan_from_dxf.py")
    assert "stop at sources-dwg" in text and "do not escalate" in text
    assert "dxf_intake.py" not in T.task_text(entries["g22-k2-stage1"], Path("i"), Path("o"))


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


# ---------------------------------------------------------------- r1 P1-1: form-check v2 step
def _row(v, pair="G22 k2", variant="built"):
    return {"pair": pair, "variant": variant, "verdict": v, "summary": {}}


@pytest.mark.parametrize("det,status", [
    ([_row("ok")], "pass"), ([_row("defect")], "fail"), ([_row("not_measured")], "not_measured"),
    ([_row("pass")], "error"), ([_row(None)], "error"), ([], "error"), ([_row("ok"), _row("ok")], "error"),
    ([_row("ok", variant="v002r1")], "error"), ([_row("ok", pair="63B")], "error"), ({"rows": []}, "error")])
def test_form_v2_verdict_maps_detector_vocabulary(det, status):
    assert T.form_v2_verdict(det, "G22 k2")["status"] == status


class _P:
    def __init__(self, rc=0, err=""):
        self.returncode, self.stdout, self.stderr = rc, "", err


def _stub(verdict=None, rc=0, crash=False):
    def detect(pairs_json, out):
        if crash:
            raise RuntimeError("blender died")
        cfg = json.loads(Path(pairs_json).read_text(encoding="utf-8"))
        v = cfg["pairs"][0]["variants"][0]
        assert v["name"] == "built" and len(v["sha"]) == 64  # r1: KeyError 'sha' witness
        if verdict is not None:
            Path(out).mkdir(parents=True)
            (Path(out) / "detector.json").write_text(json.dumps([_row(verdict)]), encoding="utf-8")
        return _P(rc, "Traceback\nModuleNotFoundError: No module named 'tools'" if rc else "")
    return detect


@pytest.mark.parametrize("kw,status", [
    ({"verdict": "ok"}, "pass"), ({"verdict": "defect"}, "fail"), ({"verdict": "not_measured"}, "not_measured"),
    ({"crash": True}, "error"), ({"verdict": "ok", "rc": 1}, "error"), ({}, "error")])
def test_form_v2_step_stubbed_detector(tmp_path, kw, status):
    fbx = tmp_path / "b.fbx"
    fbx.write_bytes(b"Kaydara FBX Binary  \0x")
    work = tmp_path / "w"
    work.mkdir()
    s = T.form_v2_step({"form_check_pair": "G22 k2"}, fbx, work, detect=_stub(**kw))
    assert s["status"] == status, s


def test_form_v2_step_unknown_or_ledger_pair_is_error(tmp_path):
    fbx = tmp_path / "b.fbx"
    fbx.write_bytes(b"x")
    assert T.form_v2_step({"form_check_pair": "nope"}, fbx, tmp_path)["status"] == "error"
    assert T.form_v2_step({"form_check_pair": "Sokolniki"}, fbx, tmp_path)["status"] == "error"
    assert T.form_v2_step({}, fbx, tmp_path)["status"] == "not_applicable"


def test_form_v2_detect_subprocess_imports_tools(tmp_path):
    """r1: the real subprocess must import `tools` (calib2 logged ModuleNotFoundError)."""
    p = T._form_v2_detect(tmp_path / "missing.json", tmp_path / "o")
    assert "ModuleNotFoundError" not in p.stderr and p.returncode != 0


_G22 = {v["name"]: v for p in json.loads((ROOT / "tools/qa/form_check/pairs_v1.json").read_text(encoding="utf-8"))
        ["pairs"] if p["id"] == "G22 k2" for v in p["variants"]}


@pytest.mark.parametrize("name,status", [("v002r1", "pass"), ("v001", "fail")])
@pytest.mark.skipif(not all(Path(v["fbx"]).is_file() for v in _G22.values()), reason="G22 review FBX not on this PC")
def test_form_v2_step_real_g22_accepted_pass_rejected_fail(tmp_path, name, status):
    s = T.form_v2_step({"form_check_pair": "G22 k2"}, _G22[name]["fbx"], tmp_path)
    assert s["status"] == status, s


# ---------------------------------------------------------------- r1 P1-2: practice worktree isolation
_E = {"key": {"path": "C:/x/review-k2/K2_v002r1_body_quad.fbx", "sha256": "ab" * 32},
      "rejected": [{"path": "C:/x/review-k2/k2_v001_body_quad.fbx", "sha256": "cd" * 32}],
      "hidden_repo_paths": ["jobs/G22"]}


def _repo(tmp_path, files):
    wt = tmp_path / "wt"
    for rel, text in files.items():
        (wt / rel).parent.mkdir(parents=True, exist_ok=True)
        (wt / rel).write_text(text, encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(wt)], check=True)
    subprocess.run(["git", "-C", str(wt), "add", "-A"], check=True)
    return wt


def test_scrub_removes_every_file_naming_the_key_and_keeps_clean_ones(tmp_path):
    wt = _repo(tmp_path, {
        "docs/a.md": "see k2_v002r1_body_quad.fbx",           # basename, other case
        "docs/b.md": "rejected C:\\x\\review-k2\\k2_v001_body_quad.fbx",  # backslash path
        "docs/c.json": '{"sha": "abababababab"}',              # 12-char sha prefix
        "docs/clean.md": "nothing about the answer",
        "docs/trainer/etalons.json": "{}", "tools/qa/form_check/pairs_v1.json": "{}",
        "tools/qa/form_check/pairs.py": "clean", "jobs/G22/README.md": "history"})
    removed = T.scrub_worktree(wt, _E)
    left = sorted(p.relative_to(wt).as_posix() for p in wt.rglob("*") if p.is_file() and ".git" not in p.parts)
    assert left == ["docs/clean.md", "tools/qa/form_check/pairs.py"]
    assert len(removed) == 6 and any(r.startswith("docs/trainer") for r in removed)
    assert T.leaking_files(wt, T.scan_tokens(_E)) == {}


def test_scrub_clean_control_removes_only_always_hidden(tmp_path):
    wt = _repo(tmp_path, {"docs/clean.md": "x", "README.md": "y"})
    assert T.scrub_worktree(wt, _E) == []
    assert (wt / "docs/clean.md").is_file() and (wt / "README.md").is_file()


def test_scrub_refuses_when_a_leak_survives(tmp_path, monkeypatch):
    wt = _repo(tmp_path, {"docs/a.md": "k2_v001_body_quad.fbx"})
    real = T.leaking_files
    monkeypatch.setattr(T, "leaking_files", lambda w, t: real(w, t) or {"docs/a.md": [t[0]]})
    with pytest.raises(T.TrainerError, match="docs/a.md"):
        T.scrub_worktree(wt, _E)


def test_scan_tokens_cover_key_rejected_and_skip_short():
    toks = T.scan_tokens(_E)
    assert "k2_v002r1_body_quad.fbx" in toks and "k2_v001_body_quad.fbx" in toks and "ab" * 6 in toks
    assert all(len(t) >= 6 for t in toks)


# ---------------------------------------------------------------- r2 P1: practice dir has no shared history
def _git(wt, *args, check=True):
    return subprocess.run(["git", "-C", str(wt), *args], capture_output=True, text=True, check=check)


def _src_repo(tmp_path):
    src = _repo(tmp_path, {"docs/clean.md": "ordinary repo file\n",
                           "docs/trainer/etalons.json": '{"key": "C:/x/review-k2/K2_v002r1_body_quad.fbx"}',
                           "docs/research/old.md": "k2_v001_body_quad.fbx was rejected",
                           "jobs/G22/README.md": "history"})
    for k, v in (("user.email", "t@t"), ("user.name", "t")):
        _git(src, "config", k, v)
    _git(src, "commit", "-q", "-m", "one")
    (src / "docs/later.md").write_text("abababababab sha prefix\n", encoding="utf-8")
    _git(src, "add", "-A")
    _git(src, "commit", "-q", "-m", "two")
    _git(src, "remote", "add", "origin", "https://example.invalid/r.git")
    return src


def test_practice_tree_is_a_fresh_one_commit_repo_without_the_key(tmp_path):
    src = _src_repo(tmp_path)
    head = _git(src, "rev-parse", "HEAD").stdout.strip()
    dst = tmp_path / "practice"
    removed = T.practice_tree(src, head, dst, _E)
    assert removed and any(r.startswith("docs/trainer") for r in removed)
    assert _git(dst, "status", "--porcelain").stdout == ""
    assert len(_git(dst, "log", "--all", "--oneline").stdout.splitlines()) == 1
    assert _git(dst, "remote").stdout.strip() == ""
    assert _git(dst, "show", "HEAD:docs/trainer/etalons.json", check=False).returncode != 0
    objs = subprocess.run(["git", "-C", str(dst), "cat-file", "--batch-all-objects", "--batch"],
                          capture_output=True, check=True).stdout.decode("utf-8", "replace").lower()
    assert not [t for t in T.scan_tokens(_E) if t in objs]
    assert (dst / "docs/clean.md").read_bytes() == (src / "docs/clean.md").read_bytes()  # control unchanged
    assert (dst / ".git").is_dir()  # own repository, not a linked worktree (.git file)
    assert len(_git(src, "worktree", "list").stdout.splitlines()) == 1  # no linked worktree added to src


def test_practice_tree_refuses_existing_dst_and_survivor(tmp_path, monkeypatch):
    src = _src_repo(tmp_path)
    dst = tmp_path / "practice"
    dst.mkdir()
    with pytest.raises(T.TrainerError, match="exists"):
        T.practice_tree(src, "HEAD", dst, _E)
    real = T.leaking_files
    monkeypatch.setattr(T, "leaking_files", lambda w, t: real(w, t) or {"docs/clean.md": [t[0]]})
    with pytest.raises(T.TrainerError, match="docs/clean.md"):
        T.practice_tree(src, "HEAD", tmp_path / "p2", _E)
    assert not (tmp_path / "p2" / ".git").exists()  # refused before any commit


def test_cmd_run_does_not_use_git_worktree():
    src = Path(T.__file__).read_text(encoding="utf-8")
    assert '"worktree", "add"' not in src and "practice_tree(ROOT" in src


# ---------------------------------------------------------------- #1861: bank paths live on Drive, not C:/x
def _etalon_file_paths(e):
    paths = [s.get("path") for s in e.get("sources", [])]
    key = e.get("key") or {}
    paths.append(key.get("path"))
    for k, v in key.items():
        if k.startswith("package_") and not k.endswith("_sha256"):
            paths.append(v)
    for field in ("rejected", "superseded"):
        paths.extend(x.get("path") for x in e.get(field, []))
    for field in ("stage2_key", "calibration_accepted"):
        if isinstance(e.get(field), dict):
            paths.append(e[field].get("path"))
    return [p for p in paths if p is not None]


def test_bank_has_no_scratch_paths_and_complete_entries_live_on_drive():
    b = bank()
    assert "C:/x" not in json.dumps(b, ensure_ascii=False)
    for e in b["etalons"]:
        if e["status"] == "complete":
            paths = _etalon_file_paths(e)
            assert paths, e["id"]
            for p in paths:
                assert p.startswith("G:/Мой диск/AGR-"), (e["id"], p)


@pytest.mark.parametrize("mutate", [
    lambda e: e["sources"][0].__setitem__("path", "C:/x/ev_1619/g22_k2_src.npz"),
    lambda e: e["key"].__setitem__("path", "C:/x/review-k2/k2_v002r1_body_quad.fbx"),
    lambda e: e["key"].__setitem__("package_vpm", "C:/x/tmp/SM_Kpp_1.zip"),
    lambda e: e["key"].__setitem__("package_npm", "D:/other/0000_Kpp_1.zip"),
    lambda e: e["rejected"][0].__setitem__("path", "C:/x/review-k2/k2_v001_body_quad.fbx"),
    lambda e: e.__setitem__("superseded", [{"version": "v2", "path": "C:/x/review-k2/k2_v002.fbx"}]),
    lambda e: e.__setitem__("stage2_key", {"path": "C:/x/review-63A/63A_Stage2_v001.fbx"}),
    lambda e: e.__setitem__("calibration_accepted", {"path": "C:/x/review-k2/acc.fbx"}),
    lambda e: e["sources"][0].__setitem__("path", "G:/Мой диск/AGR-evidence/../../Windows/x.fbx"),
    lambda e: e["sources"][0].__setitem__("path", "G:/Мой диск/AGR-evidence/../other/x.fbx"),
    lambda e: e["sources"][0].__setitem__("path", r"G:/Мой диск/AGR-evidence\..\..\x.fbx"),
    lambda e: e["sources"][0].__setitem__("path", "G:/Мой диск/other/x.fbx"),
    lambda e: e["sources"][0].__setitem__("path", "G:/Мой диск/AGR-/x.fbx"),
    lambda e: e["sources"][0].__setitem__("path", "G:/Мой диск/AGR-evidence/"),
    lambda e: e["sources"][0].__setitem__("path", "jobs/KPP1/local.dwg"),
    lambda e: e["sources"][0].__setitem__("path", ""),
    lambda e: e["sources"][0].__setitem__("path", None),
])
def test_bank_flags_practice_ready_path_outside_drive(mutate):
    b = {"etalons": [json.loads(json.dumps(bank()["etalons"][0]))]}  # kpp1-v004: practice_ready on Drive
    assert T.bank_problems(b) == []
    mutate(b["etalons"][0])
    probs = T.bank_problems(b)
    assert any("G:/Мой диск/AGR-" in p for p in probs), probs


def test_bank_allows_non_practice_ready_non_drive_placeholder():
    e = json.loads(json.dumps(bank()["etalons"][0]))
    e["practice_ready"] = False
    e["sources"][0]["path"] = "jobs/VATUTINO-SITE/sources.json"
    assert T.bank_problems({"etalons": [e]}) == []


def test_cli_check_refuses_practice_ready_path_outside_drive(tmp_path):
    b = {"etalons": [json.loads(json.dumps(bank()["etalons"][0]))]}
    b["etalons"][0]["sources"][0]["path"] = "C:/x/scratch/a.dwg"
    bad = tmp_path / "bad_etalons.json"
    bad.write_text(json.dumps(b, ensure_ascii=False), encoding="utf-8")
    p = _cli("--bank", str(bad), "check")
    assert p.returncode == 2
    assert "G:/Мой диск/AGR-" in p.stderr and "C:/x/scratch/a.dwg" in p.stderr


# ---------------------------------------------------------------- #1955: held-out keys dir isolation by context
def _run_dir(tmp_path, commands, events=True):
    run = tmp_path / "run"
    (run / "built").mkdir(parents=True)
    (run / "run.json").write_text('{"schema": "trainer-run/1"}', encoding="utf-8")
    if events:
        lines = [json.dumps({"type": "item.completed", "item": {"type": "command_execution", "command": c}})
                 for c in commands]
        (run / "events.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return run


@pytest.mark.parametrize("cmd", [
    r'type "G:\Мой диск\AGR-evidence\1855-trainer-v0\keys\heldout-key-v001.json"',
    "cat '/g/Мой диск/AGR-evidence/1855-trainer-v0/KEYS/heldout-sections-v002.json'",
    "ls G:/Мой диск/AGR-evidence/1855-trainer-v0/keys",
    # review #1970 P1-2: key reads without the literal keys-dir string
    'cd "G:/Мой диск/AGR-evidence/1855-trainer-v0" && cat keys/heldout-key-v001.json',
    'Get-Content (Join-Path "G:/Мой диск/AGR-evidence/1855-trainer-v0" "keys/heldout-key-v001.json")',
    'cat "G:/Мой диск/AGR-evidence/1855-trainer-v0/k"*/heldout-key-v001.json',
    'find "G:/Мой диск/AGR-evidence" -name "heldout-*.json" -exec cat {} +',
    'cd "G:/Мой диск/AGR-evidence/1855-trainer-v0" && ls k*',
    'cd "G:/Мой диск/AGR-evidence/1855-trainer-v0"; Get-ChildItem keys',
    "certutil -hashfile x.json | findstr 843197137db10cdc"])
def test_holdout_audit_fails_a_run_whose_builder_read_the_keys_dir(tmp_path, cmd):
    run = _run_dir(tmp_path, ["ls inputs", cmd])
    assert T.key_dir_reads(run) == [cmd]
    rep = T.score(next(x for x in bank()["etalons"] if x["id"] == "g22-k2-stage1"), str(run / "built"), tmp_path / "w")
    assert rep["steps"]["holdout"]["status"] == "fail" and rep["first_failing_step"] == "holdout"
    assert rep["passed"] is False


def test_holdout_audit_passes_a_clean_transcript_and_skips_a_non_run(tmp_path):
    e = next(x for x in bank()["etalons"] if x["id"] == "g22-k2-stage1")
    run = _run_dir(tmp_path, ["ls inputs", "type G:/Мой диск/AGR-evidence/1855-trainer-v0/bank/README.md",
                              'cd "G:/Мой диск/AGR-evidence/1855-trainer-v0" && ls bank/g22-k2-stage1/k2_v002r1',
                              "python tools/trainer/kit.py --keep-going"])
    assert T.key_dir_reads(run) == []
    assert T.score(e, str(run / "built"), tmp_path / "w")["steps"]["holdout"]["status"] == "pass"
    (tmp_path / "loose").mkdir()
    assert T.score(e, str(tmp_path / "loose"), tmp_path / "w2")["steps"]["holdout"]["status"] == "not_applicable"


def test_holdout_audit_errors_when_a_run_has_no_transcript(tmp_path):
    run = _run_dir(tmp_path, [], events=False)
    e = next(x for x in bank()["etalons"] if x["id"] == "g22-k2-stage1")
    rep = T.score(e, str(run / "built"), tmp_path / "w")
    assert rep["steps"]["holdout"]["status"] == "error" and rep["passed"] is False


def test_task_text_never_names_the_keys_dir():
    e = next(x for x in bank()["etalons"] if x["id"] == "g22-k2-stage1")
    with pytest.raises(T.TrainerError, match="keys"):
        T.task_text(dict(e, task=e["task"] + "\nsee " + r"G:\AGR-evidence\1855-trainer-v0\keys" + "\\"), Path("i"), Path("o"))


def test_scrub_hides_the_scorer_that_names_the_keys_dir(tmp_path):
    wt = _repo(tmp_path, {"tools/trainer/trainer.py": f"KEYS_DIR = {T.KEYS_DIR!r}", "docs/clean.md": "x",
                          "tests/t.py": r"p = 'G:\AGR-evidence\1855-trainer-v0\KEYS\k.json'"})
    removed = T.scrub_worktree(wt, _E)
    assert "tools/trainer/" in removed and any(r.startswith("tests/t.py") for r in removed)
    assert sorted(p.name for p in wt.rglob("*") if p.is_file() and ".git" not in p.parts) == ["clean.md"]
