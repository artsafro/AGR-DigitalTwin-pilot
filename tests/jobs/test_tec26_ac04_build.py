"""new-case: TEC26 AC04 build (#561) on the AC08 v010 recipe - several panel fields per facade (two containers on the
long facades, door-split short walls), rib count per field from presentation slide 31, ID1 roof split (RAL 7004),
glass ID -> MainGlass, one-panel fields wider than the user texture's own joint period, source findings (twisted tiny
quads, near vertex pairs) inherited, never fixed."""
import copy
import importlib.util
import json
import random
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "jobs/TEC26-OKS/scripts"
AC04 = ROOT / "jobs/TEC26-OKS/AC04"
sys.path.insert(0, str(SCRIPTS))
import compare_facades  # noqa: E402
import finish_map as fm  # noqa: E402
import joint_count  # noqa: E402
import make_textures  # noqa: E402
import qa_packages  # noqa: E402

_s = importlib.util.spec_from_file_location("ac08_pilot", Path(__file__).with_name("test_tec26_ac08_pilot.py"))
ac08 = importlib.util.module_from_spec(_s)
_s.loader.exec_module(ac08)

SPEC = fm.load(AC04 / "vpm_textures.json")
KPP = fm.load(ROOT / "jobs/KPP1/scripts/vpm_textures.json")
DUMP = fm.load(AC04 / "max-dump-004.json")
BODY = next(n for n in DUMP["nodes"] if n["multisub"])
V, F, M = BODY["vertices"], BODY["faces"], BODY["mat_ids"]
SHEET = fm.load(AC04 / "sheet-facades.json")
SLIDE = Path(SPEC["presentation"]["image"])
needs_slide = pytest.mark.skipif(not SLIDE.exists(), reason="slide 31 image not on this PC")
# slide 31, counted by hand on the 4x/6x crops: А-В small container 5 + large 9 joint lines, В-А mirrored 9 + 5,
# 1-2 two lines at the door edges, 2-1 one line + two ladder stringers in front of the wall
SLIDE_TRUTH = {"А-В": [5, 9], "В-А": [9, 5], "1-2": [2], "2-1": [1]}


def test_spec_valid_and_every_polygon_mapped():
    assert fm.validate_spec(SPEC, KPP)
    fins = fm.assign_finishes(V, F, M, SPEC)
    assert len(fins) == len(F) == 2552
    assert fins.count(fm.GLASS) == 2 and {M[i] for i, f in enumerate(fins) if f == fm.GLASS} == {3}
    assert {fins[i] for i in range(len(F)) if M[i] == 5} == {"Railing_RAL1021"}
    assert {fins[i] for i in range(len(F)) if M[i] == 4} == {"Door_RAL7004"}
    # ID1: roof decks (up-facing, z >= 3.2) grey 7004 (Gate-1), everything else blue 5015 incl. the drop below ±0.000
    roof = [i for i, f in enumerate(fins) if f == "Roof_RAL7004"]
    assert roof and all(M[i] == 1 and min(V[k][2] for k in F[i]) >= 3.2 for i in roof)
    assert sum(1 for i in range(len(F)) if M[i] == 1 and fins[i] == "Frame_RAL5015") == 439 - len(roof)
    below = [i for i in range(len(F)) if M[i] == 1 and min(V[k][2] for k in F[i]) <= -1.0]   # the drop faces
    assert below and all(fins[i] == "Frame_RAL5015" for i in below)


def test_fields_per_facade_real_building():
    fins = fm.assign_finishes(V, F, M, SPEC)
    lo, hi = fm.body_plan_bbox(V, 0.0)
    _, rep = fm.field_frames(V, F, fins, SPEC, lo, hi)
    assert sorted(rep) == sorted(SPEC["facades"])
    for name, r in rep.items():
        fc = SPEC["facades"][name]
        assert abs(r["field_m"] - fc["field_m"]) <= 1e-3 and r["ribs"] == fc["ribs"]
        assert fc["span"][0] - 1e-3 <= r["field_lo"] and r["field_hi"] <= fc["span"][1] + 1e-3
    # contract per slide facade = slide 31 counts: joints inside fields + touching field edges
    for slide_name, want in SLIDE_TRUTH.items():
        key, groups = compare_facades.field_groups(SPEC, slide_name)
        assert [g["joints_expected"] for g in groups] == want, slide_name


def test_drop_is_checked_on_the_walls_not_the_railings():
    fins = fm.assign_finishes(V, F, M, SPEC)
    rep = fm.perimeter_drop(V, F, fins, "Frame_RAL5015", body_finishes=SPEC["drop_body_finishes"])
    assert all(s["ok"] for s in rep.values()) and rep["x-"]["length_m"] == 14.2
    whole = fm.perimeter_drop(V, F, fins, "Frame_RAL5015")        # bbox incl. the ladder: not a wall, fails
    assert not all(s["ok"] for s in whole.values())


@pytest.mark.parametrize("mutate, match", [
    (lambda s: s["facades"]["А-В/2"].__setitem__("span", [-3.0, 6.324871]), "field_m|overlaps"),
    (lambda s: s["facades"]["А-В/2"].update(span=[-1.8, 6.0], field_m=7.8), "overlaps|period"),
    (lambda s: s["facades"]["А-В/1"].pop("span"), "once each|span-less"),
    (lambda s: s["facades"]["1-2/1"].__setitem__("ribs", 0), "ribs must be an int >= 1"),
    (lambda s: s["facades"]["А-В/1"].__setitem__("span", [1.0, float("nan")]), "span must be"),
    (lambda s: s["source_ids"]["1"]["roof"].__setitem__("min_nz", 0), "roof needs"),
    (lambda s: s["source_ids"]["3"].__setitem__("finish", "Door_RAL7004"), "glass rule"),
    (lambda s: s.pop("glass"), "glass rule"),
])
def test_spec_fail_closed(mutate, match):
    s = copy.deepcopy(SPEC)
    mutate(s)
    with pytest.raises(ValueError, match=match):
        fm.validate_spec(s, KPP)


def test_facade_of_picks_one_span_or_fails():
    key, pts = "+x", [[-9.0044, -7.0, 1.0], [-9.0044, -2.0, 1.0]]
    assert fm.facade_of(SPEC, key, pts)[0] == "А-В/1"
    with pytest.raises(ValueError, match="2 field spans|0 field spans|lies in"):
        fm.facade_of(SPEC, key, [[-9.0044, -7.0, 1.0], [-9.0044, 3.0, 1.0]])    # straddles the two containers
    with pytest.raises(ValueError, match="lies in 0"):
        fm.facade_of(SPEC, key, [[-9.0044, -1.7, 1.0], [-9.0044, -1.6, 1.0]])   # in the frame between fields
    with pytest.raises(ValueError, match="vertices are needed"):
        fm.facade_of(SPEC, key)


def test_probe_random_faces_never_default():
    """Generated probe: random wall faces on every facade land in exactly the span that holds them or raise."""
    rnd = random.Random(4)
    ok = err = 0
    for _ in range(400):
        key = rnd.choice(["+x", "-x", "+y", "-y"])
        a = rnd.uniform(-12, 7)
        b = a + rnd.uniform(0.01, 3)
        ax = 1 if key in ("+x", "-x") else 0
        p1, p2 = [0.0, 0.0, 1.0], [0.0, 0.0, 1.0]
        p1[ax], p2[ax] = a, b
        hold = [n for n, f in SPEC["facades"].items() if f["normal"] == key
                and f["span"][0] - 1e-3 <= a and b <= f["span"][1] + 1e-3]
        try:
            assert fm.facade_of(SPEC, key, [p1, p2])[0] == hold[0] and len(hold) == 1
            ok += 1
        except ValueError:
            assert len(hold) != 1
            err += 1
    assert ok and err and ok + err == 400


def test_one_panel_field_wider_than_source_period_has_no_extra_joint(tmp_path):
    """RED at the pre-fold make_textures: a 1.7175 m period copied the source's own joints (0.60 m) as two extra dark
    lines inside the panel (build-v002 2-1: 3 joints rendered, slide 1)."""
    t = ac08.synthetic_user_texture(tmp_path)
    t.pop("outline_z_m")
    for P in (1.717502, 1.058223, 0.664059, 2.3):
        t["P"] = [P, P]
        d = make_textures.make_full(t, 4096)[0]
        assert np.array_equal(ac08._joint_columns(d), ac08._want_joint_columns(P)), P
    t["P"] = [2.5, 2.5]                                    # beyond the folded source panel: refused, not faked
    with pytest.raises(ValueError, match="wider than the folded"):
        make_textures.make_full(t, 4096)


def test_count_joints_single_panel_field():
    s = np.linspace(0, 1, 2001)
    lum = np.full(s.shape, 300.0)
    r = joint_count.count_joints(s, lum, 0.0, 1.0, 1, 0.003)
    assert r["ok"] and r["joints_found"] == 0 and joint_count.symmetric(r, 0.003)
    lum[1000:1008] = 100.0                                 # a joint inside a one-panel field: extra, never a crash
    r = joint_count.count_joints(s, lum, 0.0, 1.0, 1, 0.003)
    assert not r["ok"] and r["extra"] and not joint_count.symmetric(r, 0.003)


@needs_slide
def test_slide31_counts_measured_on_the_slide():
    im = np.asarray(Image.open(SLIDE).convert("RGB"))
    boxes = dict(zip(SPEC["presentation"]["quadrants"], compare_facades.slide_boxes_solid(im)))
    for name, want in SLIDE_TRUTH.items():
        sl = compare_facades.slide_fields(im, boxes[name], SHEET["facades"][name]["size_mm"][0], SHEET["slide_rows"])
        assert [f["joints"] for f in sl["fields"]] == want, name
    sl = compare_facades.slide_fields(im, boxes["2-1"], SHEET["facades"]["2-1"]["size_mm"][0], SHEET["slide_rows"])
    assert sl["fields"][0]["ladder_lines"] == 2
    # the thin blue pipe outline next to 1-2 is not part of its body (box 99 px = 2.97 m at the long facades' scale)
    x0, _, x1, _ = boxes["1-2"]
    assert 95 <= x1 - x0 <= 102


def test_slide_fields_fail_closed():
    blank = np.full((200, 400, 3), 255, np.uint8)
    blank[50:150, 100:300] = (0, 124, 176)
    with pytest.raises(ValueError, match="outline not found"):          # no outlines drawn
        compare_facades.slide_fields_row(blank, (100, 50, 300, 150), 6000, 0.5)
    with pytest.raises(ValueError, match="no row with outlines"):
        compare_facades.slide_fields(blank, (100, 50, 300, 150), 6000, [0.3, 0.6])


def test_twisted_source_quads_owned_by_their_corners_only():
    sv = np.asarray(V, float)
    geo = qa_packages._poly_geo(V, F)
    twisted = [i for i, (f, g) in enumerate(zip(F, geo)) if g and np.abs(sv[f] @ g["n"] - g["d"]).max() > 2e-4]
    assert len(twisted) == 26 and {M[i] for i in twisted} == {4}
    f = F[twisted[0]]
    tris = [[f[0], f[1], f[2]], [f[0], f[2], f[3]]]
    own = qa_packages.match_source_faces(V, F, V, tris, [0.0, 0.0, 0.0])
    assert all(o == (twisted[0],) for o in own)
    moved = [list(c) for c in V]
    moved[f[1]] = [moved[f[1]][0] + 0.01, moved[f[1]][1], moved[f[1]][2]]   # a corner off the polygon: no owner
    assert qa_packages.match_source_faces(V, F, moved, tris[:1], [0.0, 0.0, 0.0]) == [()]


def test_xview_inherited_only_when_the_source_has_the_same_pairs():
    s = qa_packages.source_xview(str(AC04 / "max-dump-004.json"), "VPM")
    assert s["vertex_pairs"] == 6 and s["face_pairs"] == 0
    assert qa_packages._dist_mm("mesh v1/v2: 1.85 mm") == 1.85


def test_glass_polygons_leave_main_coverage_but_not_unchecked():
    exp = ["A", fm.GLASS]
    faces = [[0, 1, 2], [3, 4, 5]]
    r = qa_packages.source_finish_report(exp, faces, [(0,)], ["A"])
    assert r["ok"] and r["source_polygons_not_covered"] == 0
    r = qa_packages.source_finish_report(["A", "B"], faces, [(0,)], ["A"])  # a non-glass polygon missing: fails
    assert not r["ok"]
