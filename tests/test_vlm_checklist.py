"""new-case: fail-closed scoring of the advisory VLM checklist (#768); no VLM call here."""
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("vlm_checklist", ROOT / "tools/qa/vlm_checklist.py")
vc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vc)

FAC = {"south": "2-1", "north": "1-2", "east": "Б-А", "west": "А-Б"}
LABELS = sorted(FAC.values())
KNOWN = ["rib_count:1-2", "rib_count:2-1", "rib_count:А-Б", "rib_count:Б-А",
         "frame_color", "plinth_color", "field_outline"]


def _items():
    return vc.checklist_a(FAC)


def _ans(items, flagged=()):
    return [{"id": i["id"], "defect": i["id"] in flagged} for i in items]


def test_checklist_a_has_8_to_12_items_and_per_facade_ribs():
    items = _items()
    assert 8 <= len(items) <= 12
    assert sorted(i["facade"] for i in items if i["category"] == "rib_count") == LABELS
    with pytest.raises(vc.ChecklistError, match="east"):
        vc.checklist_a({k: v for k, v in FAC.items() if k != "east"})


@pytest.mark.parametrize("bad, msg", [
    ([], "missing answers"),
    ("x", "not a list"),
    ([{"id": "A01", "defect": "yes"}], "not a boolean"),
    ([{"id": "A01", "defect": None}], "not a boolean"),
    ([{"id": "A01", "defect": float("nan")}], "not a boolean"),
    ([{"id": "A01", "defect": 1}], "not a boolean"),
    ([{"id": "Z99", "defect": True}], "unknown answer id"),
])
def test_parse_answers_fails_closed(bad, msg):
    with pytest.raises(vc.ChecklistError, match=msg):
        vc.parse_answers(_items(), bad)


def test_parse_answers_rejects_duplicate_and_partial():
    items = _items()
    full = _ans(items)
    with pytest.raises(vc.ChecklistError, match="duplicate"):
        vc.parse_answers(items, full + full[:1])
    with pytest.raises(vc.ChecklistError, match="missing answers"):
        vc.parse_answers(items, full[:-1])


def test_order_inconsistent_answers_are_dropped_and_count_as_missed():
    items = _items()
    fw = vc.parse_answers(items, _ans(items, {"A02", "A03", "A04"}))
    rv = vc.parse_answers(items, _ans(items, {"A02", "A04", "A11"}))
    kept, dropped = vc.consistent(fw, rv)
    assert dropped == ["A03", "A11"] and len(kept) == 10
    s = vc.score(items, kept, KNOWN, LABELS)
    assert "plinth_color" in s["missed"] and s["false_positives"] == 0
    assert s["detected"] == ["frame_color", "rib_count:1-2"]


def test_recall_and_false_positives_exact_threshold():
    items = _items()
    all_known = {"A02", "A03", "A04", "A05", "A06", "A07", "A08"}
    kept = vc.parse_answers(items, _ans(items, all_known | {"A12"}))
    s = vc.score(items, kept, KNOWN, LABELS)
    assert s["recall"] == 1.0 and s["false_positive_items"] == ["A12"]
    kept = vc.parse_answers(items, _ans(items, {"A02", "A03", "A04", "A05", "A06"}))
    s = vc.score(items, kept, KNOWN, LABELS)
    assert s["recall"] == pytest.approx(5 / 7) and s["recall"] < 0.8   # 5/7 below the 80 % bar
    kept = vc.parse_answers(items, _ans(items, {"A02", "A03", "A04", "A05", "A06", "A07"}))
    assert vc.score(items, kept, KNOWN, LABELS)["recall"] == pytest.approx(6 / 7)


def test_accepted_object_every_flag_is_a_false_positive():
    items = _items()
    kept = vc.parse_answers(items, _ans(items, {"A01", "A09"}))
    s = vc.score(items, kept, [], LABELS)
    assert s["false_positives"] == 2 and s["recall"] is None


def test_unlabelled_object_reports_flags_without_recall():
    items = _items()
    s = vc.score(items, vc.parse_answers(items, _ans(items, {"A10"})), None, LABELS)
    assert s["flagged"] == ["A10"] and "recall" not in s


def test_generated_rib_question_for_all_facades_covers_four_defects_and_unknown_facade_errors():
    q = {"id": "B01", "category": "rib_count", "facade": "all", "question": "?"}
    assert vc.defect_keys(q, LABELS) == {f"rib_count:{f}" for f in LABELS}
    with pytest.raises(vc.ChecklistError, match="unknown facade"):
        vc.defect_keys({**q, "facade": "3-4"}, LABELS)


def _q(n, **kw):
    return [{"id": f"B{i:02d}", "category": "panel_color", "facade": "all", "question": "Blue?", **kw}
            for i in range(n)]


@pytest.mark.parametrize("qs, msg", [
    (_q(7), "8-12"), (_q(13), "8-12"), ([], "8-12"), (None, "8-12"),
    (_q(8, category="roofing"), "unknown category"),
    (_q(8, question=" "), "empty question"),
    (_q(8, facade=None), "not a string"),
    (_q(7) + _q(1), "duplicate"),
])
def test_generated_questions_fail_closed(qs, msg):
    with pytest.raises(vc.ChecklistError, match=msg):
        vc.validate_questions(qs)


def test_generated_questions_at_bounds_pass():
    assert len(vc.validate_questions(_q(8))) == 8
    assert len(vc.validate_questions(_q(12))) == 12


def test_pairwise_keeps_only_order_consistent_winners():
    items = _items()[:3]
    ab = {"A01": "second", "A02": "first", "A03": "equal"}   # a first
    ba = {"A01": "first", "A02": "first", "A03": "equal"}    # b first
    p = vc.pairwise(items, ab, ba, "v007", "v010")
    assert p["kept"] == {"A01": "v010", "A03": "equal"} and p["dropped"] == ["A02"]
    assert p["consistent_share"] == pytest.approx(2 / 3)
    with pytest.raises(vc.ChecklistError, match="first/second/equal"):
        vc.pairwise(items, {**ab, "A03": "both"}, ba, "a", "b")
    with pytest.raises(vc.ChecklistError, match="pairwise run items"):
        vc.pairwise(items, {"A01": "first"}, ba, "a", "b")


def test_brute_force_recall_matches_set_definition():
    """Probe: every subset of flagged rib/colour items -> recall == covered known / 7, fp == 0."""
    items = _items()
    ids = ["A02", "A03", "A04", "A05", "A06", "A07", "A08"]
    for mask in range(1 << len(ids)):
        fl = {ids[k] for k in range(len(ids)) if mask >> k & 1}
        s = vc.score(items, vc.parse_answers(items, _ans(items, fl)), KNOWN, LABELS)
        assert s["recall"] == pytest.approx(len(fl) / 7) and s["false_positives"] == 0


def test_output_overlapping_input_is_refused_and_nothing_written(tmp_path):
    rd = tmp_path / "renders"
    rd.mkdir()
    cfg = {"objects": {"x": {"renders": str(rd), "slide": str(tmp_path / "s.png")}}}
    for out in (rd, rd / "out", tmp_path):
        with pytest.raises(vc.ChecklistError, match="overlaps input"):
            vc._check_out(out, cfg)
    assert list(rd.iterdir()) == []
    busy = tmp_path / "busy"
    busy.mkdir()
    (busy / "results.json").write_text("{}")
    with pytest.raises(vc.ChecklistError, match="not empty"):
        vc._check_out(busy, cfg)


def test_cli_refuses_missing_view_before_any_call(tmp_path):
    rd = tmp_path / "r"
    rd.mkdir()
    cfg = tmp_path / "c.json"
    cfg.write_text(json.dumps({"objects": {"x": {"renders": str(rd), "slide": str(tmp_path / "s.png"),
                                                 "facades": FAC}}}), encoding="utf-8")
    out = tmp_path / "o"
    assert vc.main(["--config", str(cfg), "--out", str(out)]) == 2
    assert not out.exists()


def test_config_ground_truth_fixed():
    cfg = json.loads((ROOT / "docs/experiments/vlm-6view-checklist.objects.json").read_text(encoding="utf-8"))
    o = cfg["objects"]
    assert sorted(o["AC08-v007"]["known_defects"]) == sorted(KNOWN)
    assert o["AC08-v010"]["known_defects"] == [] and o["AC09-build-v001"]["known_defects"] is None
