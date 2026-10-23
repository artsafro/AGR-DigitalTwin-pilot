"""v005 MAF material IDs approved as the first working version (issue #557, [D181])."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
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


def test_material_ids_pointer_is_v005():
    pointer = json.loads(POINTER.read_text(encoding="utf-8"))
    assert pointer["active"] == "v005"
    assert pointer["path"].replace("\\", "/") == "library/maf/material_ids_v005.json"
    target = ROOT / pointer["path"]
    assert hashlib.sha256(target.read_bytes()).hexdigest() == pointer["sha256"]


def test_d181_is_logged_once():
    text = DECISIONS.read_text(encoding="utf-8")
    rows = [line for line in text.splitlines() if line.startswith("| D181 |")]
    assert len(rows) == 1
    row = rows[0]
    assert DATE in row and QUOTE in row
    assert re.search(r"new version", row, re.IGNORECASE)
