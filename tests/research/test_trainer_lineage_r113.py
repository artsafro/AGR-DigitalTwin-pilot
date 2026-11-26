"""new-case: #113 lineage-scrub harness fails closed (review r1 P1.1 / P1.2)."""
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
BANK = ROOT / "docs/trainer/etalons.json"


@pytest.fixture()
def m(monkeypatch):
    spec = importlib.util.spec_from_file_location(
        "r113_measure", ROOT / "docs/research/trainer_lineage_r113/measure.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    calls = []

    def fake_build(e, dst, candidate):
        Path(dst).mkdir(parents=True)
        calls.append(("build", e["id"], candidate))
        return [], 0.0

    def fake_m113(tree, toks):
        calls.append(("m113", Path(tree).name))
        return 0, [], {}

    monkeypatch.setattr(mod, "build", fake_build)
    monkeypatch.setattr(mod, "m113", fake_m113)
    mod.calls = calls
    return mod


def stored_tree(root, run="63a-stage1-codex-r111-1", text="x"):
    wt = Path(root) / run / "wt"
    wt.mkdir(parents=True)
    (wt / "a.md").write_text(text, encoding="utf-8")
    return wt


def test_bank_with_extra_newline_is_rejected_before_any_build(m, tmp_path):
    bank = tmp_path / "bank.json"
    bank.write_bytes(BANK.read_bytes() + b"\n")
    json.loads(bank.read_text(encoding="utf-8"))  # still valid JSON, only the digest differs
    out = tmp_path / "out"
    with pytest.raises(SystemExit) as ex:
        m.main(["--out", str(out), "--bank", str(bank), "--stored-root", str(tmp_path / "none")])
    assert "bank" in str(ex.value.code) and "PREFLIGHT FAILED" in str(ex.value.code)
    assert not out.exists() and m.calls == []


def test_unchanged_inputs_pass_preflight(m, tmp_path):
    inputs, stored = m.preflight(BANK, m.trainer.__file__, tmp_path / "none")
    assert inputs == {"bank_sha256": m.FROZEN_INPUTS["bank"], "trainer_py_sha256": m.FROZEN_INPUTS["trainer_py"]}
    assert stored is None  # absent stored trees -> not_measured, not an error


def test_stored_tree_bound_to_frozen_manifest(m, tmp_path):
    wt = stored_tree(tmp_path)
    good = {wt.parent.name: m.tree_manifest(wt)}
    assert m.preflight(BANK, m.trainer.__file__, tmp_path, manifest=good)[1] == [wt]
    (wt / "a.md").write_text("y", encoding="utf-8")
    with pytest.raises(SystemExit, match="stored tree 63a-stage1-codex-r111-1"):
        m.preflight(BANK, m.trainer.__file__, tmp_path, manifest=good)
    with pytest.raises(SystemExit, match="frozen inventory"):
        m.preflight(BANK, m.trainer.__file__, tmp_path, manifest={"other-codex-r111-9": "0" * 64})


def test_zero_reps_refused(m, tmp_path):
    with pytest.raises(SystemExit):
        m.main(["--out", str(tmp_path / "out"), "--reps", "0", "--stored-root", str(tmp_path / "none")])
    assert not (tmp_path / "out").exists() and m.calls == []


def test_incomplete_series_is_partial_not_finished(m, tmp_path):
    out = tmp_path / "out"
    rc = m.main(["--out", str(out), "--reps", "1", "--stored-root", str(tmp_path / "none")], clock=lambda: 0.0)
    rec = json.loads((out / "receipt.json").read_text(encoding="utf-8"))
    assert rc == 3 and rec["run_status"] == "partial" and rec["hypothesis"] == "inconclusive"
    assert rec["perturb"] == rec["stored_r111"] == "not_run (partial)"


def test_budget_stop_writes_receipt_and_skips_later_scans(m, tmp_path, monkeypatch):
    wt = stored_tree(tmp_path / "stored")
    monkeypatch.setattr(m, "STORED_MANIFEST", {wt.parent.name: m.tree_manifest(wt)})
    ticks = iter(range(0, 10_000, 10))
    out = tmp_path / "out"
    rc = m.main(["--out", str(out), "--cap-s", "1", "--stored-root", str(tmp_path / "stored")],
                clock=lambda: next(ticks))
    rec = json.loads((out / "receipt.json").read_text(encoding="utf-8"))
    assert rc == 3 and rec["run_status"] == "budget_stop" and rec["hypothesis"] == "inconclusive"
    assert len(rec["series"]) == 1 and rec["stored_r111"] == "not_run (budget_stop)"
    assert ("m113", "wt") not in m.calls and not (out / "perturb").exists()


def test_complete_series_finishes(m, tmp_path, monkeypatch):
    wt = stored_tree(tmp_path / "stored")
    monkeypatch.setattr(m, "STORED_MANIFEST", {wt.parent.name: m.tree_manifest(wt)})
    out = tmp_path / "out"
    rc = m.main(["--out", str(out), "--stored-root", str(tmp_path / "stored")], clock=lambda: 0.0)
    rec = json.loads((out / "receipt.json").read_text(encoding="utf-8"))
    assert rc == 0 and rec["run_status"] == "finished" and len(rec["series"]) == 9
    assert [r["run"] for r in rec["stored_r111"]] == [wt.parent.name]
    assert all(p["ok"] for p in rec["perturb"].values())
