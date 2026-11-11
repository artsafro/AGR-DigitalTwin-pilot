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
        assert r["mode"] == "RGB" and r["width"] == r["height"] and r["width"] & (r["width"] - 1) == 0, p
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


def test_manifest_records_the_root_it_wrote_under(tmp_path):
    """#1188 review P1: a run under another root records that root; every path/hash resolves under it."""
    import importlib.util

    from PIL import Image
    loader = importlib.util.spec_from_file_location("inbox_maps", ROOT / "tools/materials/inbox_maps.py")
    inbox_maps = importlib.util.module_from_spec(loader)
    loader.loader.exec_module(inbox_maps)
    assets = tmp_path / "assets"
    inbox = assets / "_inbox" / "synthetic"
    inbox.mkdir(parents=True)
    Image.new("RGB", (256, 256), (57, 57, 57)).save(inbox / "1_flat.png")  # synthetic, not a real map
    digest = hashlib.sha256((inbox / "1_flat.png").read_bytes()).hexdigest()
    (inbox / "manifest.json").write_text(json.dumps(
        {"items": [{"msg_id": 1, "file": "1_flat.png", "sha256": digest}]}), encoding="utf-8")
    spec = tmp_path / "spec.json"
    spec.write_text(json.dumps({"inbox": "_inbox/synthetic", "sources": [{
        "src": 1, "key": "synthetic", "verdict": "test",
        "outputs": [{"path": "materials/placeholders/v001/synthetic_d_{size}.png", "op": "flat", "size": 128,
                     "map": "d", "profile": "npm"}]}]}), encoding="utf-8")
    out = tmp_path / "maps.json"
    assert inbox_maps.main(["--spec", str(spec), "--root", str(assets), "--out", str(out)]) == 0
    manifest = json.loads(out.read_text(encoding="utf-8"))
    assert Path(manifest["root"]) == assets
    for row in manifest["maps"]:
        written = (Path(manifest["root"]) / row["path"]).read_bytes()
        assert hashlib.sha256(written).hexdigest() == row["sha256"], row["path"]


def _drive_mounted() -> bool:
    try:  # a sandbox may raise PermissionError instead of returning False
        return DRIVE.is_dir()
    except OSError:
        return False


@pytest.mark.skipif(not _drive_mounted(), reason="AGR-assets drive not mounted or not readable")
def test_files_on_drive_match_manifest():
    for r in MANIFEST["maps"]:
        data = (DRIVE / r["path"]).read_bytes()
        assert len(data) == r["bytes"] and hashlib.sha256(data).hexdigest() == r["sha256"], r["path"]
    inbox = DRIVE / MANIFEST["inbox"]
    items = {i["msg_id"]: i for i in json.loads((inbox / "manifest.json").read_text(encoding="utf-8"))["items"]}
    for msg in {r["source"]["msg_id"] for r in MANIFEST["maps"]}:  # inbox originals untouched
        item = items[msg]
        assert hashlib.sha256((inbox / item["file"]).read_bytes()).hexdigest() == item["sha256"], item["file"]
