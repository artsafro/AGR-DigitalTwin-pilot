"""library/materials/maps_v001.json [D239]: rows are well-formed; files on the drive match when it is mounted."""
import hashlib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "library/materials"
MANIFEST = json.loads((LIB / "maps_v001.json").read_text(encoding="utf-8"))
DRIVE = Path(MANIFEST["root"])
MAPS = {"d", "o", "m", "r", "n", "erm", "mask"}
PROFILES = {"npm", "vpm", "flora_source"}
PREFIXES = ("materials/v001/", "materials/placeholders/v001/", "flora/v003/maps/")


def table_ids():
    ids = set()
    for name in ("materials_v002.json", "ground_v001.json"):
        ids |= {r["library_id"] for r in json.loads((LIB / name).read_text(encoding="utf-8"))["materials"]}
    return ids


def test_rows_are_well_formed():
    rows = MANIFEST["maps"]
    assert rows and MANIFEST["decision"] == "D239"
    assert len({r["path"] for r in rows}) == len(rows)
    new = {r["library_id"]: r["key"] for r in MANIFEST["new_library_ids"]}
    assert not set(new) & table_ids(), "a new library id collides with the tables"
    known = table_ids() | set(new)
    for r in rows:
        p = r["path"]
        assert p.startswith(PREFIXES) and p.endswith(".png") and p.isascii(), p
        assert r["map"] in MAPS and r["profile"] in PROFILES, p
        assert r["mode"] == "RGB" or (r["mode"] == "L" and r["map"] == "o"), p  # binary star opacity is grey
        assert r["width"] == r["height"] and r["width"] & (r["width"] - 1) == 0, p
        assert len(r["sha256"]) == 64 and r["bytes"] > 0, p
        assert r["source"]["msg_id"] and len(r["source"]["sha256"]) == 64, p
        assert r["verdict"] and r["checks"] == "pass", p
        assert r["px_per_m"] is None or r["px_per_m_basis"], p  # never a size without its basis
        if r["library_id"] is not None:
            assert r["library_id"] in known, p
        if p.startswith("materials/v001/"):
            assert p.split("/")[2] == str(r["library_id"]), p  # materials\v001\<library_id>\
        if r["profile"] == "npm":
            assert r["bytes"] <= 3 * 1024 * 1024 and r["map"] != "n", p  # [D015], [D014]
        if p.startswith("materials/placeholders/"):
            assert r["width"] == {"npm": 128, "vpm": 256}[r["profile"]], p  # TEX-09 / TEX-12
        if r["profile"] == "vpm" and not p.startswith("materials/placeholders/"):
            assert r["width"] in (2048, 4096), p  # TEX-10


def test_skipped_maf_atlas_is_not_processed():
    skipped = {s["msg_id"] for s in MANIFEST["skipped"]}
    assert {53407, 53408} <= skipped
    assert not {r["source"]["msg_id"] for r in MANIFEST["maps"]} & skipped


def test_flora_candidates_name_species_only_when_confident():
    rows = {r["path"] for r in MANIFEST["maps"]}
    maps = json.loads((ROOT / "library/flora/maps.json").read_text(encoding="utf-8"))
    catalogue = json.loads((ROOT / "library/flora/catalogue.json").read_text(encoding="utf-8"))
    species = {s["latin"] for s in catalogue["species"]}
    cands = MANIFEST["flora_candidates"]
    assert cands
    for c in cands:
        assert c["confidence"] in ("high", "medium", "unconfirmed"), c["slug"]
        assert (c["latin"] is not None) == (c["confidence"] == "high"), c["slug"]  # no guessed Latin names
        atlas = [p for p in rows if p.startswith(f"flora/v003/maps/{c['slug']}/") and "_atlas_" in p]
        assert len(atlas) == 2 * c["variants"], c["slug"]  # one d + one o per plant
        assert c["latin"] not in species, "maps-only candidates are not catalogue species"
        if c["latin"]:
            record = maps[c["latin"]]
            assert record["review_status"] in ("pending_review", "approved")  # approved only by the user [D242]
            for key in ("diffuse", "opacity"):
                assert record[key].split("AGR-assets/", 1)[1] in rows, record[key]


@pytest.mark.skipif(not DRIVE.is_dir(), reason="AGR-assets drive not mounted")
def test_files_on_drive_match_manifest():
    for r in MANIFEST["maps"]:
        data = (DRIVE / r["path"]).read_bytes()
        assert len(data) == r["bytes"] and hashlib.sha256(data).hexdigest() == r["sha256"], r["path"]
    inbox = DRIVE / MANIFEST["inbox"]
    items = {i["msg_id"]: i for i in json.loads((inbox / "manifest.json").read_text(encoding="utf-8"))["items"]}
    for msg in {r["source"]["msg_id"] for r in MANIFEST["maps"]}:  # inbox originals untouched
        item = items[msg]
        assert hashlib.sha256((inbox / item["file"]).read_bytes()).hexdigest() == item["sha256"], item["file"]
