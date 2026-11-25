"""Form check v1 (tools/qa/form_check): detector, Artem's rules, judge aggregation, report. Synthetic inputs only.

new-case: tests/test_form_check.py - form check v1 tests
"""
import json

import pytest

from tools.qa.form_check import detector as D
from tools.qa.form_check import rules as R


def _edges_item(observed, key=(1.0, 3.0)):
    de = max(max(abs(o[0] - key[0]), abs(o[1] - key[1])) for o in observed)
    return {"status": "pass" if de <= 0.03 else "fail", "basis": f"max edge delta {de:.3f}",
            "observed": [list(o) for o in observed], "key": list(key)}


# --- rule NARROW: openings narrower than the Revit window are expected (Artem 2026-11-20, 63B stage 2) --------------

def test_narrow_opening_is_expected_not_defect():
    items = {"opening:W1:edges": _edges_item([(1.087, 2.931), (1.087, 2.931)])}
    out = R.apply(items, accepted=[])
    assert out["opening:W1:edges"]["status"] == "expected"
    assert "2026-11-20" in out["opening:W1:edges"]["basis"]
    assert D.verdict(out) == "ok"


def test_wider_opening_still_fails():
    items = {"opening:W1:edges": _edges_item([(0.90, 3.0), (0.90, 3.0)])}
    out = R.apply(items, accepted=[])
    assert out["opening:W1:edges"]["status"] == "fail"
    assert D.verdict(out) == "defect"


def test_shifted_opening_same_width_still_fails():
    items = {"opening:W1:edges": _edges_item([(1.10, 3.10), (1.10, 3.10)])}
    assert R.apply(items, accepted=[])["opening:W1:edges"]["status"] == "fail"


def test_d341_clip_is_accepted_with_citation():
    items = {"opening:W2:edges": _edges_item([(1.0, 2.80), (1.0, 2.80)]),
             "band_contour@18.2": {"status": "fail", "basis": "two-sided max 0.087 m", "dev_m": 0.087, "at": [5.0, 5.0]}}
    acc = [{"item": "band_contour@18.2", "near_xy": [5.0, 5.0], "radius_m": 0.2, "max_dev_m": 0.1,
            "rule": "D341", "basis": "D341 step-corner clip, #57 floor_A.json vertex 44"}]
    out = R.apply(items, accepted=acc)
    assert out["band_contour@18.2"]["status"] == "expected"
    assert "D341" in out["band_contour@18.2"]["basis"]


def test_accepted_deviation_does_not_hide_a_far_or_larger_fail():
    acc = [{"item": "contour@16.85", "near_xy": [0.0, 0.0], "radius_m": 0.2, "max_dev_m": 0.1, "rule": "D341",
            "basis": "x"}]
    far = {"contour@16.85": {"status": "fail", "basis": "", "dev_m": 0.08, "at": [3.0, 0.0]}}
    big = {"contour@16.85": {"status": "fail", "basis": "", "dev_m": 0.5, "at": [0.0, 0.0]}}
    assert R.apply(far, acc)["contour@16.85"]["status"] == "fail"
    assert R.apply(big, acc)["contour@16.85"]["status"] == "fail"


# --- detector -----------------------------------------------------------------------------------------------------

def _wall(y, x0, x1):
    return [[x0, y], [x1, y]]


def _key(depth=0.15):
    ring = [{"ring_index": 0, "xy": [0.0, 0.0]}, {"ring_index": 1, "xy": [10.0, 0.0]}]
    return {"box_xy_m": [-1, -1, 11, 1], "contour_vertices_in_box": ring,
            "openings": [{"id": "W1", "contour_segment": [0, 1], "edge_s_m": [4.0, 6.0], "reveal_depth_m": depth,
                          "sill_head_z_m": [1.0, 2.5]}],
            "profile": {"contour_z": ["0.5"], "opening_z": ["1.5"], "rim_z0": [0.9, 1.1]}}


def _cand(e0=4.0, e1=6.0, rim_d=-0.15, facade_y=0.0, recess=None):
    band = [_wall(facade_y, 0, e0), _wall(facade_y, e1, 10), [[e0, facade_y], [e0, rim_d]], [[e1, facade_y], [e1, rim_d]]]
    low = [_wall(facade_y, 0, 10)]
    if recess:
        x0, x1, d = recess
        low = [_wall(facade_y, 0, x0), [[x0, facade_y], [x0, -d]], _wall(-d, x0, x1), [[x1, -d], [x1, facade_y]],
               _wall(facade_y, x1, 10)]
    loops = [{"c": [(e0 + e1) / 2, rim_d], "z": [1.0, 2.5], "n": 4, "w": e1 - e0}]
    return {"sections": {"0.5": low, "1.5": band}, "loops": loops, "objects": [{"name": "body"}]}


def _ksec():
    return {"0.5": [_wall(0.0, 0, 10)], "1.5": _cand()["sections"]["1.5"]}


def test_detector_clean_candidate_passes():
    res = D.score(_key(), _ksec(), _cand())
    assert D.summarize(res["items"])["fail"] == 0
    assert res["items"]["opening:W1:reveal_depth"]["depth_m"] == pytest.approx(0.15)


def test_detector_extra_recess_110mm_caught_by_contour():
    res = D.score(_key(), _ksec(), _cand(recess=(7.0, 9.0, 0.11)))
    assert res["items"]["contour@0.5"]["status"] == "fail"


def test_band_contour_c1_catches_shallow_recess_in_band():
    cand = _cand()
    cand["sections"]["1.5"] = [_wall(0.0, 0, 4.0), [[4.0, 0.0], [4.0, -0.15]], [[6.0, 0.0], [6.0, -0.15]],
                               _wall(0.0, 6.0, 7.0), [[7.0, 0], [7.0, -0.06]], _wall(-0.06, 7.0, 9.0),
                               [[9.0, -0.06], [9.0, 0]], _wall(0.0, 9.0, 10)]
    res = D.score(_key(), _ksec(), cand)
    assert res["items"]["band_contour@1.5"]["status"] == "fail"
    assert res["items"]["openings:no_extra_in_box"]["status"] == "pass"  # 0.06 m < 0.12 m search band: frozen blind


def test_depth_is_relative_to_own_facade_not_key_line():
    res = D.score(_key(), _ksec(), _cand(facade_y=-0.10, rim_d=-0.25))
    assert res["items"]["opening:W1:reveal_depth"]["depth_m"] == pytest.approx(0.15)


def test_depth_not_measured_without_flank():
    cand = _cand()
    cand["sections"]["1.5"] = [s for s in cand["sections"]["1.5"] if s != _wall(0.0, 6.0, 10)]
    res = D.score(_key(), _ksec(), cand)
    item = res["items"]["opening:W1:reveal_depth"]
    assert item["status"] in ("not_measured", "fail") and item["status"] != "pass"


def test_rim_fallback_used_when_rim_far_from_gap_mid():
    res = D.score(_key(depth=0.71), _ksec(), _cand(rim_d=-0.71))
    assert res["openings_obs"]["W1"]["rim_source"] == "fallback"
    assert res["items"]["opening:W1:reveal_depth"]["status"] == "pass"


def test_missing_opening_fails_present():
    cand = _cand()
    cand["sections"]["1.5"] = [_wall(0.0, 0, 10)]
    res = D.score(_key(), _ksec(), cand)
    assert res["items"]["opening:W1:present"]["status"] == "fail"
    assert D.verdict(res["items"]) == "defect"


# --- judge aggregation (#41/#45/#49 rig: keep only order-consistent verdicts) --------------------------------------

from tools.qa.form_check import judge as J  # noqa: E402


@pytest.mark.parametrize("ab,ba,want", [("Same", "Same", "Same"), ("Different", "Different", "Different"),
                                        ("Same", "Different", "no_decision"), ("Unsure", "Same", "no_decision"),
                                        (None, "Same", "not_measured")])
def test_equivalence_order_consistency(ab, ba, want):
    assert J.cell_equivalence(ab, ba) == want


@pytest.mark.parametrize("ab,ba,want", [("X", "Y", "A"), ("Y", "X", "B"), ("None", "None", "None"),
                                        ("X", "X", "no_decision"), ("Unsure", "Y", "no_decision")])
def test_recess_order_consistency_maps_positions_back(ab, ba, want):
    # AB: X=A, Y=B; BA: X=B, Y=A
    assert J.cell_recess(ab, ba) == want


def test_prompts_never_ask_matches_the_drawing():
    for p in (J.equivalence_prompt(), J.recess_prompt()):
        assert "drawing" not in p.lower() and "required form" not in p.lower()
    assert "5 cm" in J.equivalence_prompt()


def test_parse_answer_takes_last_json_object():
    assert J.parse('noise {"form":"Same"} more {"form":"Different"}') == {"form": "Different"}
    assert J.parse("no json") is None


# --- report -------------------------------------------------------------------------------------------------------

from tools.qa.form_check import report as P  # noqa: E402


def test_agree_column():
    assert P.agree("defect", "rejected") == "yes"
    assert P.agree("ok", "accepted") == "yes"
    assert P.agree("ok", "rejected") == "no"
    assert P.agree("not_measured", "accepted") == "n/a"


def test_table_rows_roundtrip(tmp_path):
    rows = [{"pair": "G22 k2", "variant": "v001", "detector": "defect", "judge": "Different", "artem": "rejected",
             "agree_detector": "yes", "agree_judge": "yes", "not_measured": "-"}]
    md = P.markdown_table(rows)
    assert "G22 k2" in md and md.count("\n") >= 3
    p = tmp_path / "t.json"
    p.write_text(json.dumps(rows), encoding="utf-8")
    assert json.loads(p.read_text(encoding="utf-8"))[0]["pair"] == "G22 k2"


# --- 63B lessons (#52 source-wall gap, bare-ring band key, D341 accepted, depth reference open) --------------------

def test_source_wall_gap_amendment_masks_contour_and_scores_gap():
    key = _key()
    key["openings"] = []
    key["amend"] = {"source_wall_gaps": [{"id": "g", "ring_seg": [0, 1], "span_m": [7.0, 9.0], "basis": "#52"}]}
    with_gap = _cand(recess=(7.0, 9.0, 0.6))      # candidate has the source gap (recess behind it)
    bridged = _cand()                              # candidate bridges it like the key ring
    r1 = D.score(key, _ksec(), with_gap)["items"]
    r2 = D.score(key, _ksec(), bridged)["items"]
    assert r1["contour@0.5"]["status"] == "pass"   # masked: the key is wrong there
    assert r1["source_gap:g"]["status"] == "pass"
    assert r2["source_gap:g"]["status"] == "fail" and r2["source_gap:g"]["dev_m"] > 1.9


def test_band_contour_not_measured_when_key_band_is_bare_ring():
    ksec = {"0.5": [_wall(0.0, 0, 10)], "1.5": [_wall(0.0, 0, 10)]}
    res = D.score(_key(), ksec, _cand())
    assert res["items"]["band_contour@1.5"]["status"] == "not_measured"


def test_depth_reference_open_reports_number_but_no_verdict():
    key = _key(depth=0.71)
    key["amend"] = {"reveal_depth_reference": {"status": "open", "basis": "#53"}}
    item = D.score(key, _ksec(), _cand())["items"]["opening:W1:reveal_depth"]
    assert item["status"] == "not_measured" and item["depth_m"] == pytest.approx(0.15)


def test_accepted_citation_wins_over_generic_narrow_rule():
    items = {"opening:W1:edges": _edges_item([(1.087, 2.931), (1.087, 2.931)])}
    out = R.apply(items, accepted=[{"item": "opening:W1:edges", "rule": "D341", "basis": "D341 clip (#57)"}])
    assert out["opening:W1:edges"]["rule"] == "D341"


def test_extra_gap_is_one_item_per_gap_with_location():
    cand = _cand()
    cand["sections"]["1.5"] = [s for s in cand["sections"]["1.5"] if s != _wall(0.0, 6.0, 10)] + [
        _wall(0.0, 6.0, 7.5), _wall(0.0, 8.5, 10)]
    items = D.score(_key(), _ksec(), cand)["items"]
    extra = [k for k in items if k.startswith("extra_gap:")]
    assert len(extra) == 1 and items[extra[0]]["at"] == [8.0, 0.0]


# --- pair runner pieces ---------------------------------------------------------------------------------------------

from tools.qa.form_check import pairs as PR  # noqa: E402


def test_key_from_contour_kpp1_edges_and_no_depth():
    spec = {"ring": [[5.2, 0.0], [0.0, 0.0], [0.0, -6.15]], "box": [-0.05, -6.1, 5.15, 0.05],
            "contour_z": ["0.55", "3.175"], "opening_z": ["1.75"], "rim_z0": [1.0, 1.2], "basis": "A",
            "openings": [{"id": "N", "seg": [0, 1], "axis": "x", "lo": 1.255, "hi": 4.635},
                         {"id": "W", "seg": [1, 2], "axis": "y", "lo": -5.955, "hi": -1.925}]}
    key, ksec = PR.key_from_contour(spec)
    edges = {o["id"]: o["edge_s_m"] for o in key["openings"]}
    assert edges["N"] == pytest.approx([0.565, 3.945]) and edges["W"] == pytest.approx([1.925, 5.955])
    assert all(o["reveal_depth_m"] is None for o in key["openings"]) and set(ksec) == {"0.55", "3.175"}


def test_sokolniki_ledger_v004_defects_v005_ok():
    c004 = {"opening_status_counts": {"window": {"missing": 7}}}
    f = {"D06": {"v004": {"mouth_area": 0.0, "iou": 0.0, "glass_not_cut": 314.4},
                 "v005": {"mouth_area": 308.0, "iou": 0.97, "glass_not_cut": 7.2}}}
    c005 = {"opening_status_counts": {"v005": {"window/present": 178}}, "f05": f,
            "facades_worse_explained": {"F04": {"new_mouths": 7, "revit_wall_inside_new_mouths_m2": 2.874}},
            "mouths": {"v005": {"unverified": []}}, "f13": [], "f13_seats_v005": {}}
    assert D.verdict(PR.ledger_items("v004", c004, c005)) == "defect"
    assert D.verdict(PR.ledger_items("v005", c004, c005)) == "ok"


def test_judge_aggregate_controls_do_not_invent_recess_cell():
    recs = [{"pair": "p|control", "judge": j, "question": "equivalence", "order": o, "answer": "Same"}
            for j in ("claude", "codex") for o in ("AB", "BA")]
    agg = J.aggregate(recs)["p|control"]
    assert agg["consensus"] == {"equivalence": "Same"}
