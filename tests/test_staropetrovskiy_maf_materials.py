"""New-case: the Staropetrovskiy material addition is separate from model publication."""

import hashlib
import json
from pathlib import Path
import runpy

import pytest

ROOT = Path(__file__).resolve().parents[1]
MAF = ROOT / "library/maf"
MATERIALS = ROOT / "library/materials"
SCRIPT = ROOT / "jobs/staropetrovskiy-maf-lib/scripts/maf_ids_v008.py"
KEYS = (
    "paint_ral1015", "paint_ral1002", "paint_ral8004", "concrete_beige",
    "glass_frosted_white", "glass_frosted_amber",
)


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_maf_v008_adds_six_without_changing_existing_ids():
    old = read_json(MAF / "material_ids_v007.json")
    new = read_json(MAF / "material_ids_v008.json")
    assert new["ids"][:33] == old["ids"]
    added = new["ids"][33:]
    assert [(row["id"], row["key"]) for row in added] == list(zip(range(34, 40), KEYS))
    assert added[2]["target"] == "#9E5A47"
    assert read_json(MAF / "material_ids.json")["active"] == "v007"


def test_shared_material_release_preserves_existing_rows_and_ground_reference():
    ptr = read_json(MATERIALS / "materials.json")
    assert ptr["current"] == "materials_v003.json"
    path = MATERIALS / ptr["current"]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == ptr["sha256"]
    old = read_json(MATERIALS / "materials_v002.json")
    new = read_json(path)
    assert new["ground_ref"] == old["ground_ref"]
    verona = next(row for row in old["materials"] if row["key"] == "larch_light_oak_boards")
    old_path = "C:" "/x/vatutino-maf/gen-v001/atlas-v006-2/verona_boards_11.png"
    drive_path = "G:/Мой диск/AGR-assets/maf/projects/vatutino/gen-v001/atlas-v006-2/verona_boards_11.png"
    assert old_path in verona["source"]["evidence"]
    verona["source"]["evidence"] = verona["source"]["evidence"].replace(old_path, drive_path)
    assert new["materials"][:len(old["materials"])] == old["materials"]
    assert [(row["library_id"], row["key"]) for row in new["materials"][len(old["materials"]):]] == list(
        zip(range(54, 60), KEYS)
    )


def test_v008_replay_sources_use_durable_evidence():
    change = read_json(MAF / "material_ids_v008_change.json")
    new = read_json(MAF / "material_ids_v008.json")
    assert new["inputs"]["job_sources"] == change["job_sources"]
    assert new["inputs"]["change"]["sha256"] == hashlib.sha256(
        (MAF / "material_ids_v008_change.json").read_bytes()
    ).hexdigest()
    for source in change["job_sources"].values():
        assert source["path"].startswith("G:/Мой диск/AGR-")
        assert len(source["sha256"]) == 64


def test_historical_missing_map_inventory_preserves_diagnostics():
    old = read_json(MAF / "material_ids_v007.json")["inventory"]["missing"]
    new = read_json(MAF / "material_ids_v008.json")["inventory"]["missing"]
    changed = [a for a, b in zip(old, new, strict=True) if a != b]
    assert len(changed) == 10
    for a, b in zip(old, new, strict=True):
        if a != b:
            assert a["name"].startswith("T_Letnaya_ZU_71_6_Ground_Diffuse_")
            assert b == dict(a, referenced_path="Unresolved historical reference; see material_ids_v007.json")


@pytest.mark.parametrize("case", ["match", "wrong bytes", "absent hash", "inconsistent prior path"])
def test_inherited_path_hash_binding(case, tmp_path):
    module = runpy.run_path(str(SCRIPT))
    relocated = tmp_path / "atlas.png"
    relocated.write_bytes(b"synthetic atlas")
    digest = hashlib.sha256(b"synthetic atlas").hexdigest()
    old = "old/atlas.png"
    document = {"input": {"path": old, "sha256": digest}, "observations": [{"path": old}]}
    sources = {digest: relocated.as_posix()}
    if case == "match":
        md = module["relocate_evidence"](document, f"`{old}`", sources)
        assert md == f"`{relocated.as_posix()}`"
        assert document["input"] == {"path": relocated.as_posix(), "sha256": digest}
        assert document["observations"] == [{"path": relocated.as_posix()}]
        return
    if case == "wrong bytes":
        relocated.write_bytes(b"changed")
        error = "does not match its recorded SHA256"
    elif case == "absent hash":
        sources = {"0" * 64: relocated.as_posix()}
        error = "hash absent from the prior list"
    else:
        document["observations"][0]["sha256"] = "0" * 64
        error = "inconsistent recorded SHA256"
    with pytest.raises(module["ChangeError"], match=error):
        module["relocate_evidence"](document, f"`{old}`", sources)
