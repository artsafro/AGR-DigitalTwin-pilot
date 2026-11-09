"""v006 = v005 + ID 32 `wood_hpl_satin` (D229, #993); derived by tools/library/maf_ids_version.py."""
import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "library" / "maf"


def _tool():
    spec = importlib.util.spec_from_file_location("maf_ids_version", ROOT / "tools" / "library" / "maf_ids_version.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load(name):
    return json.loads((LIB / name).read_text(encoding="utf-8"))


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
