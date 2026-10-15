"""Sash candidates from a Max mesh dump (issue #4). sashes and handing stay null."""
import copy
import json
import random
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "library"))
import window_sashes as ws  # noqa: E402

NOTE = ("Unconfirmed sash and handing readings with their reasons are in each entry's `unconfirmed` field "
        "(tools/library/window_sashes.py).")
SASH = ROOT / "library" / "windows" / "sources" / "win-typical-max-sashes-v001.json"
TYPES = ROOT / "library" / "windows" / "window_types.json"
V001 = ROOT / "library" / "windows" / "sources" / "win-typical-max-v001.json"


def _bars(x0, z0, x1, z1, t):
    """Four bars of a rectangular frame, overlapping at the corners."""
    return [(x0, z0, x1, z0 + t), (x0, z1 - t, x1, z1), (x0, z0, x0 + t, z1), (x1 - t, z0, x1, z1)]


def _dump(parts, back):
    """parts: (rectangles, Y, material id, flip to +Y). `back` is an ID 4 rectangle (x0, z0, x1, z1, y)."""
    verts, faces = [], []

    def add(x0, z0, x1, z1, y, mat, flip):
        i = len(verts)
        verts.extend([[x0, y, z0], [x1, y, z0], [x1, y, z1], [x0, y, z1]])
        if flip:                                               # winding for a +Y normal
            faces.extend([[i, i + 2, i + 1, mat], [i, i + 3, i + 2, mat]])
        else:
            faces.extend([[i, i + 1, i + 2, mat], [i, i + 2, i + 3, mat]])

    for rects, y, mat, flip in parts:
        for rect in rects:
            add(*rect, y, mat, flip)
    add(*back[:4], back[4], 4, False)
    return {"file": r"C:\synthetic\Win.max", "units": "meters",
            "objects": [{"name": "W", "verts": verts, "faces": faces}]}


def _read(parts, back=(0, 0, 1.2, 1.2, 0.2)):
    return ws.read_sashes(_dump(parts, back))["objects"][0]


def _frame(w=1.2, h=1.0, t=0.04, y=0.0):
    return _bars(0, 0, w, h, t), y, 1, False


def test_a_frame_alone_has_no_ring():
    got = _read([_frame()])
    assert got["reading"] == "no_ring" and got["rings"] == [] and got["overlap"] is False


def test_one_recessed_ring_in_one_of_two_fields():
    frame = _bars(0, 0, 1.2, 1.0, 0.04) + [(0.58, 0.04, 0.62, 0.96)]   # mullion between two fields
    ring = (0.08, 0.08, 0.54, 0.92)
    got = _read([(frame, 0.0, 1, False), (_bars(*ring, 0.04), 0.02, 1, False)])
    assert got["reading"] == "rings" and len(got["rings"]) == 1
    assert all(abs(a - b) <= 0.002 for a, b in zip(got["rings"][0]["rect_m"], ring))


def test_a_cross_bar_is_one_ring_with_two_holes():
    got = _read([_frame(1.0, 1.0), (_bars(0.1, 0.1, 0.9, 0.9, 0.04) + [(0.1, 0.48, 0.9, 0.52)], 0.02, 1, False)])
    assert len(got["rings"]) == 1 and got["rings"][0]["holes"] == 2


def test_a_solid_strip_is_ignored():
    got = _read([_frame(), ([(0.2, 0.2, 0.7, 0.35)], 0.02, 1, False)])
    assert got["reading"] == "no_ring" and got["rings"] == []


def test_two_levels_overlapping_by_30_mm():
    a, b = (0.10, 0.10, 0.70, 0.90), (0.40, 0.10, 1.00, 0.90)          # 300 mm of overlap in X
    got = _read([_frame(), (_bars(*a, 0.04), 0.02, 1, False), (_bars(*b, 0.04), 0.04, 1, False)])
    assert got["reading"] == "rings_overlap" and got["overlap"] is True and len(got["rings"]) == 2


def test_an_open_leaf_meeting_at_the_stile_overlaps():
    # the stile belongs to the closed leaf; the other leaf is three bars and only touches it
    closed = _bars(0.08, 0.15, 0.50, 0.85, 0.04)
    open_leaf = [(0.50, 0.81, 1.12, 0.85), (0.50, 0.15, 1.12, 0.19), (1.08, 0.15, 1.12, 0.85)]
    got = _read([_frame(), (closed, 0.02, 1, False), (open_leaf, 0.04, 1, False)])
    assert got["reading"] == "rings_overlap" and len(got["rings"]) == 2


def test_a_side_return_behind_the_back_plane_is_not_a_ring():
    decoy = _bars(0.2, 0.2, 0.8, 0.8, 0.04)                            # a ring, but behind the back plane
    got = _read([_frame(1.0, 1.0), (decoy, 0.10, 1, False)], back=(0, 0, 1.0, 1.0, 0.05))
    assert got["reading"] == "no_ring" and got["rings"] == []


def test_opaque_infill_and_back_facing_triangles_are_ignored():
    ring = _bars(0.15, 0.15, 0.85, 0.85, 0.04)
    assert _read([_frame(1.0, 1.0), (ring, 0.02, 5, False)])["rings"] == []
    assert _read([_frame(1.0, 1.0), (ring, 0.02, 1, True)])["rings"] == []


def _entry(id_, max_object=None, **extra):
    entry = {"id": id_, "name": id_, "sashes": None, "handing": None, "width_m": 1.0,
             "source": {"object": "synthetic"}}
    if max_object:
        entry["source"]["max_object"] = max_object
    entry.update(extra)
    return entry


def _source(name, reading, rects):
    return {"objects": [{"object": name, "reading": reading,
                         "rings": [{"rect_m": r, "depth_m": -0.3, "holes": 1} for r in rects]}]}


def test_apply_sets_unconfirmed_without_touching_sashes_and_is_idempotent():
    doc = {"schema": "window-types/1", "note": "Base note.", "types": [
        _entry("WT-01", "A"), _entry("W01", kept=True)]}
    before = copy.deepcopy(doc)
    sources = [("library/windows/sources/s.json", _source("A", "rings", [[0.1, 0.2, 0.3, 0.4]]))]
    out = ws.apply_sashes(doc, sources)
    assert [t["id"] for t in out["types"]] == ["WT-01", "W01"]
    for old, new in zip(before["types"], out["types"]):
        assert {k: v for k, v in new.items() if k != "unconfirmed"} == old
        assert new["sashes"] is None and new["handing"] is None
        assert new["unconfirmed"]["sashes"]["reason"] and new["unconfirmed"]["handing"]["reason"]
    sash = out["types"][0]["unconfirmed"]
    assert sash["sashes"]["candidate"] == 1 and sash["sashes"]["rects_m"] == [[0.1, 0.2, 0.3, 0.4]]
    assert sash["sashes"]["source"] == "library/windows/sources/s.json"
    assert "inner frame" in sash["sashes"]["reason"]
    assert sash["handing"] == {"candidate": None,
                               "reason": "the Max scene has no handle, hinge or opening-direction geometry"}
    other = out["types"][1]["unconfirmed"]
    assert other["sashes"] == {"candidate": None, "reason": "the source has no sash data"}
    assert other["handing"] == {"candidate": None, "reason": "the source has no handing data"}
    assert out["note"].count(NOTE) == 1
    again = ws.apply_sashes(out, sources)
    assert json.dumps(again, ensure_ascii=False, indent=1) == json.dumps(out, ensure_ascii=False, indent=1)


@pytest.mark.parametrize("reading, fragment", [
    ("rings_overlap", "meeting stile"),
    ("no_ring", "fixed glazing"),
])
def test_apply_reasons_follow_the_reading(reading, fragment):
    doc = {"schema": "window-types/1", "note": "Base.", "types": [_entry("WT-01", "A")]}
    out = ws.apply_sashes(doc, [("p.json", _source("A", reading, [] if reading == "no_ring" else [[0, 0, 1, 1]]))])
    assert fragment in out["types"][0]["unconfirmed"]["sashes"]["reason"]
    assert out["types"][0]["unconfirmed"]["sashes"]["candidate"] == (0 if reading == "no_ring" else 1)


def test_an_unknown_max_object_stops_the_apply():
    doc = {"schema": "window-types/1", "note": "Base.", "types": [_entry("WT-01", "MISSING")]}
    with pytest.raises(SystemExit, match="MISSING"):
        ws.apply_sashes(doc, [("p.json", {"objects": []})])


def test_committed_types_carry_the_sash_reading():
    types = json.loads(TYPES.read_text(encoding="utf-8"))
    sash = json.loads(SASH.read_text(encoding="utf-8"))
    src = json.loads(V001.read_text(encoding="utf-8"))
    assert len(types["types"]) == 46 and types["note"].count(NOTE) == 1
    for t in types["types"]:
        assert t["sashes"] is None and t["handing"] is None
        assert t["unconfirmed"]["sashes"]["reason"] and t["unconfirmed"]["handing"]["reason"]
    assert [o["object"] for o in sash["objects"]] == [o["object"] for o in src["objects"]]
    for got, ref in zip(sash["objects"], src["objects"]):
        assert abs(got["width_m"] - ref["width_m"]) <= 0.002
        assert abs(got["height_m"] - ref["height_m"]) <= 0.002
    by = {o["object"]: o for o in sash["objects"]}
    wt = [t for t in types["types"] if t["id"].startswith("WT-")]
    assert len(wt) == 24
    for t in wt:
        assert t["unconfirmed"]["sashes"]["candidate"] == len(by[t["source"]["max_object"]]["rings"])
    path = "library/windows/sources/win-typical-max-sashes-v001.json"
    again = ws.apply_sashes(json.loads(json.dumps(types)), [(path, sash)])
    assert again == types


def test_random_rings_come_back_within_2_mm():
    rng = random.Random(1)
    t = 0.04
    for _ in range(200):
        cols = rng.randint(1, 4)
        openings = [rng.choice((0.40, 0.46, 0.52, 0.60)) for _ in range(cols)]
        height = rng.choice((0.90, 1.10, 1.30))
        fields, cursor = [], t
        for i, w in enumerate(openings):
            fields.append((cursor, cursor + w))
            cursor += w + (t if i < cols - 1 else 0)
        width = cursor + t
        frame = _bars(0, 0, width, height, t)
        frame += [(a[1], t, b[0], height - t) for a, b in zip(fields, fields[1:])]
        drawn, rects = [], []
        for x0, x1 in fields:
            if not rng.randrange(2):
                continue
            rect = (x0 + t, t + t, x1 - t, height - t - t)
            rects.append(rect)
            drawn.extend(_bars(*rect, t))
        back = (0, 0, width, height, 0.2)
        got = _read([(frame, 0.0, 1, False), (drawn, 0.02, 1, False)], back=back)
        assert got["reading"] == ("rings" if rects else "no_ring")
        assert len(got["rings"]) == len(rects)
        for ring, rect in zip(got["rings"], rects):
            assert all(abs(a - b) <= 0.002 for a, b in zip(ring["rect_m"], rect)), (ring["rect_m"], rect)
