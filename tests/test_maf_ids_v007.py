"""v007 = v006 + ID 33 `wood_pine` (WOOD2, plan step 2.3, 2026-11-10) and the 512 atlas baked from 53407."""
import importlib.util
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "library" / "maf"
HEX = re.compile(r"^#[0-9A-F]{6}$")


def _load(name):
    return json.loads((LIB / name).read_text(encoding="utf-8"))


def _tool():
    spec = importlib.util.spec_from_file_location("maf_ids_version", ROOT / "tools" / "library" / "maf_ids_version.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_v007_is_well_formed():
    v7 = _load("material_ids_v007.json")
    assert v7["schema"] == "library-maf-material-ids" and v7["version"] == "v007"
    ids = [e["id"] for e in v7["ids"]]
    assert ids == list(range(1, 34))
    assert len({e["key"] for e in v7["ids"]}) == 33
    for e in v7["ids"]:
        assert {"id", "key", "name_ru", "kind", "target", "size", "atlas", "spec_rows", "status"} <= set(e), e["id"]
        assert HEX.match(e["target"].split()[-1]), e["id"]
    assert v7["derived_from"] == {"path": "library/maf/material_ids_v006.json", "version": "v006"}


def test_v007_adds_wood2_pine_and_nothing_else():
    t = _tool()
    v6, v7, change = _load("material_ids_v006.json"), _load("material_ids_v007.json"), _load("material_ids_v007_change.json")
    by = {e["id"]: e for e in v7["ids"]}
    assert (by[33]["key"], by[33]["kind"], by[33]["atlas"]) == ("wood_pine", "wood", True)
    assert "сосна" not in by[14]["name_ru"]
    assert all(m["from_key"] != "wood_pine" for m in v7["merges"])
    assert len(v7["merges"]) == len(v6["merges"]) - 1
    old = {e["id"]: e for e in v6["ids"]}
    assert all(by[i] == old[i] for i in old if i != 14)
    rebuilt = t.apply_change(v6, change)
    for key in ("ids", "merges", "spec_requirements", "version", "changelog"):
        assert rebuilt[key] == v7[key], key
    assert any(tile["key"] == "wood_pine" for tile in v7["evidence"]["tiles"])


def test_atlas_512_v007_record():
    rec = _load("atlas_512_v007.json")
    v7 = {e["id"]: e for e in _load("material_ids_v007.json")["ids"]}
    out = rec["atlas"]
    assert out["size"] == [512, 512] and out["mode"] == "RGB" and re.fullmatch(r"[0-9a-f]{64}", out["sha256"])
    slots = rec["slots"]
    assert [s["slot"] for s in slots] == list(range(1, 16))
    assert {s["slot"]: s["id"] for s in slots}[10] == 33
    for s in slots:
        assert v7[s["id"]]["key"] == s["key"]
    cells = rec["cells"]
    assert sorted(c["id"] for c in cells) == sorted(s["id"] for s in slots)
    pad = rec["padding_px"]
    assert pad >= 8
    boxes = [c["slot_px"] for c in cells]
    for i, (x, y, w, h) in enumerate(boxes):
        assert 0 <= x and 0 <= y and x + w <= 512 and y + h <= 512
        for x2, y2, w2, h2 in boxes[i + 1:]:
            assert x + w <= x2 or x2 + w2 <= x or y + h <= y2 or y2 + h2 <= y
    # r2 (review of PR #1187): the log end is a 256 cell from the label-cleaned 53407 log disc; r1 stays recorded
    assert rec["revision"] == "r2" and rec["atlas"]["path"].endswith("_r2.png")
    assert [p["revision"] for p in rec["previous"]] == ["r1"]
    assert rec["previous"][0]["atlas"]["sha256"] == "55e654a2e04ce2e828cd1f7a1f585d54263a01050f00cb60d5d3bab4f6d0cf6d"
    log = next(c for c in cells if c["id"] == 18)
    assert log["slot_px"][2] == 256
    assert {s["slot"]: s for s in slots}[15]["clean"]["method"] == "ring_clone"
    for c in cells:
        cx, cy, cw, ch = c["content_px"]
        x, y, w, h = c["slot_px"]
        assert cx - x == pad // 2 and cy - y == pad // 2 and cw == w - pad and ch == h - pad
