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


# --- review round 1 (P1-2): pairwise answer lists are validated before any dict is built ---

def _pa(items, better="first"):
    return [{"id": i["id"], "better": better} for i in items]


@pytest.mark.parametrize("mutate, msg", [
    (lambda a: a + [{"id": a[0]["id"], "better": "first"}, {"id": a[0]["id"], "better": "equal"}], "duplicate"),
    (lambda a: a + [dict(a[0])], "duplicate"),
    (lambda a: a[:-1], "missing"),
    (lambda a: [], "missing"),
    (lambda a: None, "not a list"),
    (lambda a: a + [{"id": "Z99", "better": "first"}], "unknown"),
    (lambda a: a[:-1] + [{"id": a[-1]["id"], "better": "both"}], "first/second/equal"),
    (lambda a: a[:-1] + [{"id": a[-1]["id"], "better": None}], "first/second/equal"),
    (lambda a: a[:-1] + [{"id": a[-1]["id"]}], "first/second/equal"),
    (lambda a: a[:-1] + ["A12"], "unknown"),
])
def test_parse_pairwise_answers_fails_closed(mutate, msg):
    items = _items()
    with pytest.raises(vc.ChecklistError, match=msg):
        vc.parse_pairwise_answers(items, mutate(_pa(items)))


def test_parse_pairwise_answers_valid_control():
    items = _items()
    assert vc.parse_pairwise_answers(items, _pa(items, "equal")) == {i["id"]: "equal" for i in items}


def _fake_driver(tmp_path, monkeypatch, dup_pair):
    """Mocked VLM (no paid call): checklist all-clean; pairwise optionally with conflicting duplicates."""
    import re
    rd = tmp_path / "r"
    rd.mkdir()
    for v in vc.VIEWS:
        (rd / f"{v}.png").write_bytes(b"x")
    slide = tmp_path / "s.png"
    slide.write_bytes(b"x")
    leg = tmp_path / "legend.json"
    leg.write_text(json.dumps({"legend": [{"material": "m", "ral": "5005", "texture": "t"}]}), encoding="utf-8")
    obj = {"renders": str(rd), "slide": str(slide), "facades": FAC, "legend": str(leg)}
    cfg = tmp_path / "c.json"
    cfg.write_text(json.dumps({"objects": {"x": {**obj, "known_defects": KNOWN}, "y": {**obj, "known_defects": []}},
                               "pairs": [["x", "y"]]}), encoding="utf-8")

    def fake(prompt, workdir, model):
        ids = re.findall(r"^([AB]\d\d): ", prompt, re.M)
        if "yes/no validation questions" in prompt:
            return {"parsed": {"questions": _q(8)}, "cost_usd": 0.0, "duration_s": 0.0}
        if "Two versions" in prompt:
            ans = [{"id": i, "better": "equal"} for i in ids]
            if dup_pair:
                ans += [{"id": ids[0], "better": "first"}, {"id": ids[0], "better": "equal"}]
            return {"parsed": {"answers": ans}, "cost_usd": 0.0, "duration_s": 0.0}
        return {"parsed": {"answers": [{"id": i, "defect": False} for i in ids]}, "cost_usd": 0.0, "duration_s": 0.0}

    monkeypatch.setattr(vc, "call_vlm", fake)
    return cfg


def test_runner_rejects_conflicting_duplicate_pairwise_answers(tmp_path, monkeypatch):
    """Reviewer input: complete list + first id again as 'first' then 'equal' -> named error, exit 1, no score."""
    cfg = _fake_driver(tmp_path, monkeypatch, dup_pair=True)
    out = tmp_path / "o"
    assert vc.main(["--config", str(cfg), "--out", str(out), "--workers", "1"]) == 1
    res = json.loads((out / "results.json").read_text(encoding="utf-8"))
    for var in ("A", "B"):
        p = res["pairs"][f"x~y/{var}"]
        assert "duplicate" in p["error"] and "consistent_share" not in p
        assert "duplicate" in res["errors"][f"x~y/{var}"]
    assert res["objects"]["x/A"]["recall"] == 0 and res["objects"]["y/A"]["false_positives"] == 0


def test_runner_valid_pairwise_control_exit_0(tmp_path, monkeypatch):
    cfg = _fake_driver(tmp_path, monkeypatch, dup_pair=False)
    out = tmp_path / "o"
    assert vc.main(["--config", str(cfg), "--out", str(out), "--workers", "1"]) == 0
    res = json.loads((out / "results.json").read_text(encoding="utf-8"))
    assert res["errors"] == {}
    assert res["pairs"]["x~y/A"]["consistent_share"] == 1.0 and res["pairs"]["x~y/A"]["dropped"] == []


# --- #781: primary-source provenance of the report -------------------------------------------------------
REPORT = ROOT / "docs/experiments/vlm-6view-checklist.md"
PROV_HEAD = "## Primary-source provenance (#781)"
STATUSES = {"paper-supported", "adapted", "own heuristic"}


def _provenance_section(text: str) -> str:
    assert PROV_HEAD in text, f"missing section {PROV_HEAD!r}"
    sec = text.split(PROV_HEAD, 1)[1]
    return sec.split("\n## ", 1)[0]


def test_report_has_no_unchecked_source_claim():
    assert "not re-checked" not in REPORT.read_text(encoding="utf-8")


def test_every_cited_arxiv_id_has_a_versioned_quoted_source_row():
    import re
    text = REPORT.read_text(encoding="utf-8")
    ids = set(re.findall(r"arXiv[: ]?(\d{4}\.\d{5})", text))
    assert ids, "report cites no arXiv id"  # fail closed: an empty citation set is not a pass
    sec = _provenance_section(text)
    for i in sorted(ids):
        rows = [ln for ln in sec.splitlines() if ln.startswith("|") and re.search(rf"\b{re.escape(i)}v\d+\b", ln)]
        assert rows, f"arXiv {i} cited but has no versioned row in {PROV_HEAD}"
        assert any(re.search(r"\u201c[^\u201d]{20,}\u201d", ln) for ln in rows), f"arXiv {i}: no quoted passage"


def test_every_method_element_is_attributed_with_a_known_status():
    sec = _provenance_section(REPORT.read_text(encoding="utf-8"))
    rows = [ln for ln in sec.splitlines() if ln.startswith("| M")]
    assert rows, "no method attribution rows (| M<n> ...)"
    seen = set()
    for ln in rows:
        cells = [c.strip() for c in ln.strip("|").split("|")]
        assert cells[2] in STATUSES, f"{cells[0]}: status {cells[2]!r} not in {sorted(STATUSES)}"
        seen.add(cells[2])
    assert "own heuristic" in seen and "paper-supported" in seen
