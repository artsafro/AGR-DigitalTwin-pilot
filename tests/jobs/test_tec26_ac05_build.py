"""new-case: TEC26 AC05 build (#562) on the AC08 pilot-v010 recipe - presentation slide 35 is the authority [D171]:
rib count per facade counted on the slide pixels (1-2 / 2-1: 44 joints, Б-А: 13; А-Б is the grey gate, no sandwich
field), the binding legend (5015 ribbed / 5015 frame / 7004 doors+gate / 7004 roof from Gate 1), the mixed ID1 split
`roof` (roof plane grey, frame band and perimeter drop blue) and the facade `plain` override (А-Б field strips)."""
import copy
import hashlib
import json
import math
import random
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "jobs/TEC26-OKS/scripts"
AC05 = ROOT / "jobs/TEC26-OKS/AC05"
AC08 = ROOT / "jobs/TEC26-OKS/AC08"
sys.path.insert(0, str(SCRIPTS))
import compare_facades  # noqa: E402
import finish_map as fm  # noqa: E402

SPEC = fm.load(AC05 / "vpm_textures.json")
KPP = fm.load(ROOT / "jobs/KPP1/scripts/vpm_textures.json")
BODY = next(n for n in fm.load(AC05 / "max-dump-005.json")["nodes"] if n["multisub"])
SHEET = fm.load(AC05 / "sheet-facades.json")
SLIDE = Path(SPEC["presentation"]["image"])
SLIDE49 = Path(fm.load(AC08 / "vpm_textures.json")["presentation"]["image"])
needs_slide = pytest.mark.skipif(not (SLIDE.exists() and SLIDE49.exists()), reason="slide images not on this PC")
BUILD = Path("C:/x/tec26-oks/AC05/build-v004")


def _assign(spec=SPEC):
    return fm.assign_finishes(BODY["vertices"], BODY["faces"], BODY["mat_ids"], spec)


def test_spec_valid_legend_and_kpp_colours():
    assert fm.validate_spec(SPEC, KPP)
    rows = {f: r["ral"] for r in SPEC["legend"] for f in r["finishes"]}
    assert rows == {"PanelVJ45_RAL5015": "5015", "PanelVJ14_RAL5015": "5015", "Frame_RAL5015": "5015",
                    "Door_RAL7004": "7004", "Roof_RAL7004": "7004"}


def test_assign_real_building_matches_gate1():
    """Gate 1 (#562): ID1 = 15 roof polygons grey + 112 frame/drop polygons blue; ID2 = sandwich field (long +-x 16,
    Б-А +y 3) and the А-Б strips (-y 3, plain); ID3/ID4 = door/gate RAL 7004. Every polygon gets exactly one finish."""
    fins = _assign()
    got = {}
    for m, f in zip(BODY["mat_ids"], fins):
        got[(m, f)] = got.get((m, f), 0) + 1
    assert got == {(1, "Roof_RAL7004"): 15, (1, "Frame_RAL5015"): 112, (2, "PanelVJ45_RAL5015"): 16,
                   (2, "PanelVJ14_RAL5015"): 3, (2, "Frame_RAL5015"): 3, (3, "Door_RAL7004"): 476,
                   (4, "Door_RAL7004"): 1}
    assert len(fins) == len(BODY["faces"]) == 626
    V = BODY["vertices"]
    for f, fin in zip(BODY["faces"], fins):          # the drop to -2.004 m stays wall colour, never the roof
        if min(V[k][2] for k in f) < -1.0:
            assert fin == "Frame_RAL5015"


@pytest.mark.parametrize("mutate,match", [
    (lambda s: s["source_ids"]["1"].pop("roof_z_m"), "roof_z_m"),
    (lambda s: s["source_ids"]["1"].update(roof_z_m=float("nan")), "roof_z_m"),
    (lambda s: s["source_ids"]["1"].update(roof_z_m=float("inf")), "roof_z_m"),
    (lambda s: s["source_ids"]["1"].update(roof_z_m=True), "roof_z_m"),
    (lambda s: s["source_ids"]["1"].update(roof="Roof_RAL9999"), "not declared"),
    (lambda s: s["source_ids"]["1"].pop("rest"), "not declared"),
    (lambda s: s["source_ids"]["1"].update(split="roofs"), "unsupported split"),
    (lambda s: s["source_ids"]["2"]["plain"].update({"+x": "Frame_RAL5015"}), "plain override"),
    (lambda s: s["source_ids"]["2"].update(plain={"-z": "Frame_RAL5015"}), "plain override"),
    (lambda s: s["source_ids"]["2"].update(plain={"-y": "Glass_RAL5015"}), "not declared"),
    (lambda s: s["source_ids"].pop("4"), None),
])
def test_spec_fail_closed(mutate, match):
    s = copy.deepcopy(SPEC)
    mutate(s)
    with pytest.raises(ValueError, match=match):
        fm.validate_spec(s, KPP)
        _assign(s)                                    # ID4 unmapped -> error naming it, never a default


def test_unmapped_id4_names_the_id():
    s = copy.deepcopy(SPEC)
    s["source_ids"].pop("4")
    with pytest.raises(ValueError, match="material ID 4 has no finish mapping"):
        _assign(s)


def test_roof_split_threshold_inclusive_and_orientation():
    """Exactly at roof_z_m = roof (inclusive), 1 mm below = rest; a downward or vertical face at the top = rest."""
    rule = {"1": {"split": "roof", "roof": "Roof_RAL7004", "rest": "Frame_RAL5015", "roof_z_m": 2.89}}
    spec = {"source_ids": rule, "zero_m": 0.0}
    sq = lambda z, down=False: ([[0, 0, z], [1, 0, z], [1, 1, z], [0, 1, z]][::-1 if down else 1])  # noqa: E731
    cases = [(sq(2.89), "Roof_RAL7004"), (sq(2.889), "Frame_RAL5015"), (sq(2.95, down=True), "Frame_RAL5015"),
             ([[0, 0, 2.9], [1, 0, 2.9], [1, 0, 3.0], [0, 0, 3.0]], "Frame_RAL5015")]
    for verts, want in cases:
        assert fm.assign_finishes(verts, [[0, 1, 2, 3]], [1], spec) == [want], (verts, want)
    with pytest.raises(ValueError, match="finite"):
        fm.assign_finishes([[0, 0, float("nan")], [1, 0, 3], [1, 1, 3]], [[0, 1, 2]], [1], spec)


def test_roof_split_probe_generated():
    """Brute force: 2000 random quads (random height, tilt, winding) - roof iff upward normal z > 0.999 and the lowest
    vertex >= roof_z_m; never any other finish."""
    rnd = random.Random(562)
    rule = {"split": "roof", "roof": "R", "rest": "W", "roof_z_m": 2.89}
    spec = {"source_ids": {"1": rule}, "zero_m": 0.0}
    for _ in range(2000):
        z = rnd.uniform(2.80, 2.98)
        tilt = rnd.choice([0.0, 0.0, 1e-4, 0.05, 1.0])
        q = [[0, 0, z], [1, 0, z + tilt], [1, 1, z + tilt], [0, 1, z]]
        if rnd.random() < 0.3:
            q = q[::-1]
        n = fm._newell(q)
        want = "R" if (n[2] > 0.999 and min(p[2] for p in q) >= 2.89) else "W"
        assert fm.assign_finishes(q, [[0, 1, 2, 3]], [1], spec) == [want]


def test_field_frames_rib_contract_real_building():
    V, F = BODY["vertices"], BODY["faces"]
    lo, hi = fm.body_plan_bbox(V, 0.0)
    _, rep = fm.field_frames(V, F, _assign(), SPEC, lo, hi)
    assert {k: (v["normal"], v["ribs"], len(v["joints_world"])) for k, v in rep.items()} == {
        "1-2": ("+x", 45, 44), "2-1": ("-x", 45, 44), "Б-А": ("+y", 14, 13)}
    for v in rep.values():
        assert abs(v["field_m"] - v["ribs"] * v["pitch_m"]) < 1e-5


@needs_slide
def test_slide_boxes_slide35_and_slide49_unchanged():
    """Slide 35 bodies cross the image centre (the long facades start at x 438 < W/2 = 445): column groups, not
    quadrants. Slide 49 (AC08 pilot-v010) keeps its exact boxes."""
    s35 = np.asarray(Image.open(SLIDE).convert("RGB"))
    s49 = np.asarray(Image.open(SLIDE49).convert("RGB"))
    b35 = [tuple(int(v) for v in b) for b in compare_facades.slide_boxes(s35)]
    assert b35 == [(111, 104, 205, 212), (438, 104, 797, 217), (111, 500, 205, 612), (438, 499, 797, 612)]
    assert [tuple(int(v) for v in b) for b in compare_facades.slide_boxes(s49)] == [
        (121, 81, 254, 223), (581, 81, 914, 223), (121, 484, 254, 626), (580, 484, 913, 626)]
    one = s35.copy()
    one[:371, :300] = 255                                  # only one body left in the top half
    with pytest.raises(ValueError, match="two blue facade bodies"):
        compare_facades.slide_boxes(one)


@needs_slide
def test_slide35_rib_counts_are_the_contract():
    assert hashlib.sha256(SLIDE.read_bytes()).hexdigest() == SPEC["presentation"]["image_sha256"]
    im = np.asarray(Image.open(SLIDE).convert("RGB"))
    boxes = dict(zip(SPEC["presentation"]["quadrants"], compare_facades.slide_boxes(im)))
    for name, fc in SPEC["facades"].items():
        r = compare_facades.slide_count(im, boxes[name], SHEET["facades"][name], frac=fc["slide_row_frac"],
                                        skip_inner=fc.get("slide_skip_inner", 0))
        assert r["joints"] == fc["ribs"] - 1 == fc["slide_joints"], (name, r)
        assert abs(r["height_scale_ratio"] - 1) < 0.03, (name, r)
    assert set(SPEC["presentation"]["quadrants"]) == set(SPEC["facades"]) | set(SPEC["facades_plain"])
    # a lost line and an extra line change the count; a bare row refuses
    box, f = boxes["1-2"], SHEET["facades"]["1-2"]
    base = compare_facades.slide_count(im, box, f)["joints"]
    y0, y1 = box[1] + 10, box[3] - 10
    lost = im.copy()
    lost[y0:y1, box[0] + 105:box[0] + 109] = (0, 124, 176)       # the joint line at box x + 106.5 px
    assert compare_facades.slide_count(lost, box, f)["joints"] == base - 1
    bare = im.copy()
    bare[y0:y1, box[0] - 4:box[2] + 4] = (0, 124, 176)
    with pytest.raises(ValueError, match="outline"):
        compare_facades.slide_count(bare, box, f)


@pytest.mark.skipif(not (BUILD / "compare/compare.json").exists(), reason="AC05 build-v001 not on this PC")
def test_build_v001_compare_counts():
    """The delivered VPM and NPM renders show the slide's joint count on every ribbed facade (read from the build's
    compare.json, written by compare_facades.py from the rendered pixels); А-Б is reported plain."""
    rep = json.loads((BUILD / "compare/compare.json").read_text(encoding="utf-8"))
    for name, fc in SPEC["facades"].items():
        c = rep["facades"][name]
        assert c["match"] and c["slide_joints"] == c["vpm_render_joints"] == c["npm_render_joints"] == fc["ribs"] - 1
    assert rep["facades"]["А-Б"]["plain"] is True
    qa = json.loads((BUILD / "qa_packages.json").read_text(encoding="utf-8"))
    assert qa["failed"] == [] and len(qa["checks"]) == 43
    assert math.isfinite(rep["px_per_m"])


@pytest.mark.parametrize("bad", [[2, 22], [2, 22, 300], [2.0, 22, 46], [True, 22, 46], [40, 110, 170]])
def test_joint_rgb_fail_closed(bad):
    s = copy.deepcopy(SPEC)
    s["finishes"]["PanelVJ45_RAL5015"]["joint_rgb"] = bad
    with pytest.raises(ValueError, match="joint_rgb"):
        fm.validate_spec(s, KPP)


@pytest.mark.parametrize("bad", [0, 31, 12.5, True, "12"])
def test_npm_joint_half_fail_closed(bad):
    s = copy.deepcopy(SPEC)
    s["finishes"]["PanelVJ14_RAL5015"]["npm_joint_half_mm"] = bad
    with pytest.raises(ValueError, match="npm_joint_half_mm"):
        fm.validate_spec(s, KPP)


def test_joint_rgb_paints_the_whole_joint_and_outline(tmp_path):
    """joint_rgb replaces Artem's joint colour over the full joint width and on the field outline rows; panel colour
    and noise stay his (SYNTHETIC stand-in texture, same layout)."""
    import make_textures
    rng = np.random.default_rng(5)
    img = np.clip(np.array((34, 113, 179), float) + rng.normal(0, 1.5, (4096, 4096, 3)), 0, 255)
    for c in range(266, 4096, 600):
        img[:, c:c + 8] = (12, 40, 63)
    src = tmp_path / "synthetic_panel.png"
    Image.fromarray(img.round().astype(np.uint8), "RGB").save(src)
    t = copy.deepcopy(SPEC["finishes"]["PanelVJ45_RAL5015"])
    t["source_texture"].update(path=str(src), sha256=hashlib.sha256(src.read_bytes()).hexdigest())
    dif = make_textures.make_user_vjoints(t, 4096)[0]
    Pp = t["P"][0] * 1000
    row = dif[2000].astype(int)
    jw = t["joint_half_mm"]
    for k in (1, 7, 20):
        c = int(round(k * Pp))
        assert (row[c - jw + 1:c + jw - 1] == t["joint_rgb"]).all(), k
    mid = int(round(0.5 * Pp))
    assert abs(row[mid] - np.array((34, 113, 179))).max() < 10
    zrow = int(round(4096 - t["outline_z_m"][0] * 1000)) - 2        # just inside the bottom outline
    assert (dif[zrow, mid] == t["joint_rgb"]).all()
