"""Tests for tools/state/kpi_kind_overlay.py (offline advisory candidate-kind overlay).

All fixtures are synthetic (small frozen dictionaries); none is real board data.
"""
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "state" / "kpi_kind_overlay.py"


def _load():
    spec = importlib.util.spec_from_file_location("kpi_kind_overlay", SCRIPT)
    assert spec is not None and SCRIPT.is_file(), f"missing module {SCRIPT}"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _card(cid, title, kind="issue", implementer="w-a", minutes=1.0, **extra):
    row = {"id": cid, "kind": kind, "implementer": implementer, "minutes": minutes}
    if title is not _MISSING:
        row["title"] = title
    row.update(extra)
    return row


_MISSING = object()

# Synthetic acceptance fixture: stored kind + title -> expected candidate label.
ACCEPT = [
    (_card("t_plan", "Plan: next tasks", minutes=2.5), "plan"),
    (_card("t_hyps", "Hypotheses: 2026-10-15", minutes=0.5), "hypotheses"),
    (_card("t_ready", "Readiness: #12", minutes=1.0), "readiness"),
    (_card("t_tri", "Triage: pilot issues", implementer="w-b", minutes=0.25), "triage"),
    (_card("t_adopt", "Adopt: #83 bijective facade", minutes=10.0), "adopt"),
    (_card("t_650", "#650 ordinary issue", minutes=30.0), "issue"),
    (_card("t_race", "Plan: looks like plan", kind="race", minutes=4.0), "race"),
    (_card("t_harn", "#127 guardrails", kind="harness", implementer="w-b", minutes=6.0), "harness"),
    (_card("t_gh69", "#69 pilot", minutes=7.0, idempotency_key="gh-69-pilot"), "issue"),
    (_card("t_none", _MISSING, minutes=3.0), "unknown"),
    (_card("t_empty", "   ", implementer="w-b", minutes=1.5), "unknown"),
    (_card("t_other", "Measure opening x_m", minutes=2.0), "unlabeled"),
]

TOTALS = {
    "w-a": {"cards": 9.0, "first_pass": 1.0, "minutes": 61.0},
    "w-a|issue": {"cards": 7.0, "first_pass": 1.0, "minutes": 51.0},
    "w-b": {"cards": 3.0, "first_pass": 0.0, "minutes": 7.75},
}

EXPECTED_GROUPS = {
    "w-a": {
        "adopt": {"cards": 1, "minutes": 10.0},
        "hypotheses": {"cards": 1, "minutes": 0.5},
        "issue": {"cards": 2, "minutes": 37.0},
        "plan": {"cards": 1, "minutes": 2.5},
        "race": {"cards": 1, "minutes": 4.0},
        "readiness": {"cards": 1, "minutes": 1.0},
        "unknown": {"cards": 1, "minutes": 3.0},
        "unlabeled": {"cards": 1, "minutes": 2.0},
    },
    "w-b": {
        "harness": {"cards": 1, "minutes": 6.0},
        "triage": {"cards": 1, "minutes": 0.25},
        "unknown": {"cards": 1, "minutes": 1.5},
    },
}


def _doc(cards=None, totals=None):
    return {
        "generated": "2026-01-01 00:00",
        "board": "synthetic",
        "cards": [c for c, _ in ACCEPT] if cards is None else cards,
        "totals": TOTALS if totals is None else totals,
    }


def _write(tmp_path, doc, name="kpi.json"):
    p = tmp_path / name
    p.write_text(json.dumps(doc) if not isinstance(doc, str) else doc, encoding="utf-8")
    return p


def _run(*args, cwd):
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, cwd=cwd, timeout=60)


def test_module_exists():
    assert SCRIPT.is_file()
    _load()


@pytest.mark.parametrize("card,label", ACCEPT, ids=[c["id"] for c, _ in ACCEPT])
def test_candidate_label(card, label):
    mod = _load()
    assert mod.candidate_label(card["kind"], card.get("title")) == label


def test_overlay_groups_rows_and_totals_unchanged():
    mod = _load()
    doc = _doc()
    before = json.dumps(doc, sort_keys=True)
    rep = mod.build_report(doc, source_sha256="0" * 64, source_path="x")
    assert json.dumps(doc, sort_keys=True) == before  # input object not mutated
    assert rep["advisory"] is True
    assert rep["original_totals"] == TOTALS
    assert rep["groups"] == EXPECTED_GROUPS
    got = {r["id"]: (r["stored_kind"], r["candidate_label"]) for r in rep["rows"]}
    assert got == {c["id"]: (c["kind"], lab) for c, lab in ACCEPT}
    # no rates or grades are published
    blob = json.dumps(rep)
    for word in ("first_pass_rate", "rate", "grade"):
        assert f'"{word}"' not in blob


def test_empty_report():
    mod = _load()
    rep = mod.build_report({"cards": [], "totals": {}}, source_sha256="0" * 64, source_path="x")
    assert rep["rows"] == [] and rep["groups"] == {} and rep["original_totals"] == {}


BAD = {
    "duplicate_id": _doc(cards=[_card("t1", "#1"), _card("t1", "#2")]),
    "cards_not_list": _doc(cards={"t1": {}}),
    "card_not_dict": _doc(cards=["t1"]),
    "missing_id": _doc(cards=[{"kind": "issue", "implementer": "w", "minutes": 1.0}]),
    "empty_kind": _doc(cards=[_card("t1", "#1", kind="")]),
    "missing_implementer": _doc(cards=[{"id": "t1", "kind": "issue", "minutes": 1.0}]),
    "title_not_str": _doc(cards=[_card("t1", 5)]),
    "bool_minutes": _doc(cards=[_card("t1", "#1", minutes=True)]),
    "negative_minutes": _doc(cards=[_card("t1", "#1", minutes=-0.1)]),
    "str_minutes": _doc(cards=[_card("t1", "#1", minutes="1")]),
    "missing_minutes": _doc(cards=[{"id": "t1", "kind": "issue", "implementer": "w"}]),
    "totals_not_dict": _doc(totals=[]),
    "totals_entry_not_dict": _doc(totals={"w": 3}),
    "totals_bool": _doc(totals={"w": {"cards": False}}),
    "missing_cards": {"totals": {}},
    "missing_totals": {"cards": []},
    "top_not_dict": [],
}


@pytest.mark.parametrize("name", sorted(BAD))
def test_invalid_input_raises(name):
    mod = _load()
    with pytest.raises(mod.OverlayError):
        mod.build_report(BAD[name], source_sha256="0" * 64, source_path="x")


def _snapshot(dirpath):
    return sorted((p.relative_to(dirpath).as_posix(), p.stat().st_size) for p in Path(dirpath).rglob("*"))


def test_cli_positive_fresh_process(tmp_path):
    src = _write(tmp_path, _doc())
    raw = src.read_bytes()
    before_dir = _snapshot(tmp_path)
    work = tmp_path / "cwd"
    work.mkdir()
    proc = _run("--input", str(src), cwd=work)
    assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")
    rep = json.loads(proc.stdout.decode("utf-8"))
    assert rep["source"]["sha256"] == hashlib.sha256(raw).hexdigest()
    assert rep["source"]["generated"] == "2026-01-01 00:00"
    assert rep["generated_at"]
    assert rep["groups"] == EXPECTED_GROUPS
    assert rep["original_totals"] == TOTALS
    assert src.read_bytes() == raw  # input bytes unchanged
    assert list(work.iterdir()) == []  # no implicit output files in cwd
    assert _snapshot(tmp_path) == sorted(before_dir + [("cwd", 0)])


@pytest.mark.parametrize(
    "text",
    [
        json.dumps(BAD["duplicate_id"]),
        json.dumps(BAD["negative_minutes"]),
        '{"cards": [{"id": "t1", "kind": "issue", "implementer": "w", "minutes": NaN}], "totals": {}}',
        '{"cards": [{"id": "t1", "kind": "issue", "implementer": "w", "minutes": Infinity}], "totals": {}}',
        '{"cards": [], "totals": {"w": {"minutes": -Infinity}}}',
        '{"cards": [], "cards": [], "totals": {}}',
        '{"cards": [',
        "",
    ],
    ids=["dup_id", "negative", "nan", "inf", "neg_inf_totals", "dup_json_key", "truncated", "empty_file"],
)
def test_cli_invalid_input_nonzero_no_stdout(tmp_path, text):
    src = _write(tmp_path, text)
    raw = src.read_bytes()
    proc = _run("--input", str(src), cwd=tmp_path)
    assert proc.returncode != 0
    assert proc.stdout == b""  # never partial success
    assert b"error" in proc.stderr.lower()
    assert src.read_bytes() == raw
    assert {p.name for p in tmp_path.iterdir()} == {"kpi.json"}


def test_cli_missing_input_and_no_arg(tmp_path):
    proc = _run("--input", str(tmp_path / "absent.json"), cwd=tmp_path)
    assert proc.returncode != 0 and proc.stdout == b""
    proc = _run(cwd=tmp_path)
    assert proc.returncode != 0 and proc.stdout == b""
    assert list(tmp_path.iterdir()) == []


def test_cli_rejects_directory_input(tmp_path):
    proc = _run("--input", str(tmp_path), cwd=tmp_path)
    assert proc.returncode != 0 and proc.stdout == b""
    assert os.listdir(tmp_path) == []
