"""MAF material-ID version series, one owner of `tools/library/maf_ids_version.py` (#1963 merge).

* v005 approved as the first working version (issue #557, [D181]);
* v006 = v005 + ID 32 `wood_hpl_satin` (D229, #993);
* v007 = v006 + ID 33 `wood_pine` (WOOD2, [D240], plan step 2.3) and the 512 atlas baked from 53407.
"""
import copy
import hashlib
import importlib.util
import json
import re
from pathlib import Path

import pytest

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
    assert v7["approval"]["decision"] == "D240"


def test_pine_decision_is_logged_once():
    text = (ROOT / "docs" / "decisions.md").read_text(encoding="utf-8")
    assert sum(1 for line in text.splitlines() if line.startswith("| D240 |")) == 1


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


def _bake_mod():
    spec = importlib.util.spec_from_file_location(
        "atlas_maf_from_source", ROOT / "jobs" / "maf-atlas-512" / "scripts" / "atlas_maf_from_source.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _flat_png(path, size, rgb):
    from PIL import Image
    Image.new("RGB", (size, size), rgb).save(path)
    return _tool().sha256_file(path)


@pytest.mark.parametrize("box", [[-2, -2, 8, 8], [0, 0, 9, 8], [4, 4, 4, 8], [6, 0, 2, 8], [0, 0, 8]])
def test_write_tile_rejects_crop_outside_the_source(tmp_path, box):
    # Codex review round 1 on PR #1187, P1: an out-of-image crop must fail, not pad with black, and write nothing
    t = _tool()
    src = tmp_path / "src.png"
    add = {"id": 33, "key": "k", "tile": {"file": "tiles/ID_33_k.png", "px": 8, "source": "probe",
                                          "crop": {"path": str(src), "sha256": _flat_png(src, 8, (120, 80, 40)),
                                                   "box": box}}}
    prev = {"ids": [], "evidence": {"tiles": []}}
    with pytest.raises(t.ChangeError, match="crop box"):
        t.write_tile(add, str(tmp_path / "in"), str(tmp_path / "out"), prev)
    assert not (tmp_path / "out").exists()


def test_bake_rejected_placement_writes_nothing_and_retry_works(tmp_path):
    # Codex review round 1 on PR #1187, P2 / #1199: placement is checked before any output exists
    b = _bake_mod()
    src = tmp_path / "src.png"
    sha = _flat_png(src, 128, (120, 80, 40))
    spec = {"source": {"path": str(src), "sha256": sha, "size": [128, 128], "id_map": {}},
            "ids": "library/maf/material_ids_v007.json", "atlas_size": 32, "padding_px": 8,
            "slots": [{"slot": 1, "text": "t", "id": 33, "key": "wood_pine", "kind": "patterned", "px": 64,
                       "box": [0, 0, 64, 64]}]}
    out = tmp_path / "out"
    with pytest.raises(b.BakeError, match="does not fit"):
        b.bake(spec, out)
    assert not out.exists()
    spec["atlas_size"] = 64
    assert b.bake(spec, out)["atlas"]["size"] == [64, 64]


# ================================================================ v005 approved ([D181], #557)

V005 = ROOT / "library" / "maf" / "material_ids_v005.json"
V005_MD = ROOT / "library" / "maf" / "material_ids_v005.md"
POINTER = ROOT / "library" / "maf" / "material_ids.json"
DECISIONS = ROOT / "docs" / "decisions.md"

QUOTE = (
    "Ну более-менее норм, по ID как первый вариант норм, "
    "потом будем тестить на проектах и корректировать"
)
DATE = "2026-10-22"
HDPE_REVIEW = "HDPE waste container (T3510#6)"
HPL_REVIEW = "Атласное дерево"


def _doc() -> dict:
    return json.loads(V005.read_text(encoding="utf-8"))


def status_problems(doc: dict) -> list[str]:
    """Every id status uses the approved-v1 prefix; a bare or leftover ``proposed`` is a violation."""
    problems = []
    if doc.get("status") != "approved-v1":
        problems.append("document status")
    approval = doc.get("approval") or {}
    if approval.get("date") != DATE or QUOTE not in str(approval.get("quote") or ""):
        problems.append("approval date/quote")
    ids = doc.get("ids") or []
    if len(ids) != 31:
        problems.append(f"id count {len(ids)}")
    for entry in ids:
        status = str(entry.get("status") or "")
        if status == "proposed" or status.startswith("proposed"):
            problems.append(f"id {entry.get('id')} still proposed")
        elif not status.startswith("approved-v1"):
            problems.append(f"id {entry.get('id')} status {status!r}")
    return problems


def test_v005_is_approved_v1_with_flat_terrazzo_and_review_flags():
    doc = _doc()
    assert status_problems(doc) == []
    terrazzo = next(entry for entry in doc["ids"] if entry["key"] == "terrazzo")
    assert "gap: no atlas cell" in terrazzo["status"]
    assert terrazzo["picked_patch"] is None
    tile = next(tile for tile in doc["evidence"]["tiles"] if tile["key"] == "terrazzo")
    assert tile["source"].startswith("GAP: target colour #C7C7C7")
    assert "patch" not in tile["source"]
    by_id = {entry["id"]: entry for entry in doc["ids"]}
    assert any(HDPE_REVIEW in item and "на проверку" in item for item in by_id[10]["review"])
    assert any(HPL_REVIEW in item and "на проверку" in item for item in by_id[14]["review"])
    md = V005_MD.read_text(encoding="utf-8")
    assert "Status: **approved-v1**" in md
    assert DATE in md and QUOTE in md
    assert "picked patch atlas_02" not in md
    assert "на проверку" in md


def test_status_invariant_probe_rejects_each_of_31_entries():
    """Brute-force: restoring ``proposed`` on any one entry is caught; 31/31."""
    doc = _doc()
    assert status_problems(doc) == []
    caught = 0
    for entry in doc["ids"]:
        broken = json.loads(json.dumps(doc))
        victim = next(item for item in broken["ids"] if item["id"] == entry["id"])
        status = victim["status"]
        victim["status"] = "proposed" + status[len("approved-v1"):]
        problems = status_problems(broken)
        assert any(f"id {entry['id']} still proposed" in problem for problem in problems), entry["id"]
        caught += 1
    assert caught == 31


def _canonical_sha(raw: bytes) -> str:
    """SHA256 of the LF (committed) form; CRLF checkouts hash the same."""
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def test_pointer_hash_matches_committed_lf_and_crlf_working_copy():
    import subprocess

    blob = subprocess.run(
        ["git", "show", "HEAD:" + json.loads(POINTER.read_text(encoding="utf-8"))["path"]],
        capture_output=True, check=True, cwd=Path(__file__).resolve().parents[1],
    ).stdout
    pointer = json.loads(Path("library/maf/material_ids.json").read_text(encoding="utf-8"))
    assert b"\r" not in blob
    assert _canonical_sha(blob) == pointer["sha256"]
    assert _canonical_sha(blob.replace(b"\n", b"\r\n")) == pointer["sha256"]
    assert _canonical_sha(blob + b" ") != pointer["sha256"]


def test_material_ids_pointer_is_v007():
    # v007 = v006 + ID 33 (D240); v005 itself stays unchanged.
    pointer = json.loads(POINTER.read_text(encoding="utf-8"))
    assert pointer["active"] == "v007"
    assert pointer["path"].replace("\\", "/") == "library/maf/material_ids_v007.json"
    target = ROOT / pointer["path"]
    assert _canonical_sha(target.read_bytes()) == pointer["sha256"]


def test_d181_is_logged_once():
    text = DECISIONS.read_text(encoding="utf-8")
    rows = [line for line in text.splitlines() if line.startswith("| D181 |")]
    assert len(rows) == 1
    row = rows[0]
    assert DATE in row and QUOTE in row
    assert re.search(r"new version", row, re.IGNORECASE)


# ================================================================ v006 (D229, #993)

def test_v006_is_v005_plus_id_32_and_reproducible():
    t = _tool()
    v5, v6, change = _load("material_ids_v005.json"), _load("material_ids_v006.json"), _load("material_ids_v006_change.json")
    assert len(v5["ids"]) == 31 and len(v6["ids"]) == 32
    by = {e["id"]: e for e in v6["ids"]}
    assert (by[32]["key"], by[32]["target"], by[32]["spec_rows"]) == ("wood_hpl_satin", "#B4825A", ["*T3510#26"])
    assert "*T3510#26" not in by[14]["spec_rows"] and "HPL" not in by[14]["name_ru"]
    assert all(m["from_key"] != "hpl_satin_wood" for m in v6["merges"])
    assert v6["approval"]["decision"] == "D229" and v6["approval"]["quote"] == "да"
    rebuilt = t.apply_change(v5, change)
    for key in ("ids", "merges", "spec_requirements", "version", "approval", "changelog"):
        assert rebuilt[key] == v6[key], key
    # every other id is untouched
    old = {e["id"]: e for e in v5["ids"]}
    assert all(by[i] == old[i] for i in old if i != 14)


def test_apply_change_refuses_a_taken_or_skipped_id():
    t = _tool()
    v5, change = _load("material_ids_v005.json"), _load("material_ids_v006_change.json")
    for mid, key in ((14, "x_new"), (33, "x_new"), (32, "wood_light")):
        bad = copy.deepcopy(change)
        bad["add"].update(id=mid, key=key)
        with pytest.raises(t.ChangeError):
            t.apply_change(v5, bad)


def test_site_512_set_has_one_cell_for_id_32():
    lay = _load("atlas_layout_v006.json")
    cells = lay["site_sets"]["vatutino"]["cells"]
    assert sorted(c["id"] for c in cells) == [4, 14, 29, 32]
    rows = [p for p in lay["site_sets"]["vatutino"]["positions"] if p["material"] == "hpl_satin_wood"]
    assert rows and all(p["id"] == 32 for p in rows)
    assert lay["inputs"]["ids"]["path"].replace("\\", "/") == "library/maf/material_ids_v006.json"


def test_hpl_decision_is_logged_once():
    text = (ROOT / "docs" / "decisions.md").read_text(encoding="utf-8")
    assert sum(1 for line in text.splitlines() if line.startswith("| D229 |")) == 1
