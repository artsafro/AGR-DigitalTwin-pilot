"""new-case: MAF colour zones for the 13 Vatutino showcase positions (#889).

Material IDs come from the approved v005 list. A face ID >= 1001 is an error.
Geometry counts are unchanged by the assignment. Unmapped positions, zones and
materials are errors that name the missing key. Empty, partial, non-finite and
exactly-at-threshold input fail. An output path that is an input writes nothing.
"""
import copy
import json
import math
import random
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SET = ROOT / "jobs" / "VATUTINO-SITE" / "maf" / "site-maf-set.json"
COUNTS = ROOT / "jobs" / "VATUTINO-SITE" / "maf" / "site-maf-zone-counts.json"
IDS = ROOT / "library" / "maf" / "material_ids_v005.json"
SHOW = ("VAT_MAF_T3510_01", "VAT_MAF_T3510_02", "VAT_MAF_T3510_07", "VAT_MAF_T3510_09",
        "VAT_MAF_T3510_11", "VAT_MAF_T3510_12", "VAT_MAF_T3510_16", "VAT_MAF_T3510_26",
        "VAT_MAF_T3510_27", "VAT_MAF_T3510_28", "VAT_MAF_T3510_29", "VAT_MAF_T3510_31",
        "VAT_MAF_T3510_32")


@pytest.fixture(scope="module")
def z():
    sys.path.insert(0, str(ROOT / "tools" / "review"))
    import maf_colour_zones as mod
    return mod


@pytest.fixture()
def catalogue(z):
    return z.load_id_catalogue(json.loads(IDS.read_text(encoding="utf-8")))


def _pos(set_id="VAT_MAF_T3510_01", faces=4, verts=6):
    return {
        "set_id": set_id,
        "zones": [
            {"zone": "boards", "id_key": "wood_light",
             "colour_source": "schedule finish light oak; v005 target, photo not measured"},
            {"zone": "frame", "id_key": "paint_ral7047",
             "colour_source": "schedule RAL 7047; v005 target, photo not measured"},
        ],
        "profiles": {
            "npm": {"vertices_before": verts, "faces_before": faces,
                    "vertices_after": verts, "faces_after": faces,
                    "zone_faces": {"boards": 1, "frame": faces - 1}},
            "vpm": {"vertices_before": verts, "faces_before": faces,
                    "vertices_after": verts, "faces_after": faces,
                    "zone_faces": {"boards": 1, "frame": faces - 1}},
        },
    }


def test_assign_keeps_counts_and_ids_below_udim(z, catalogue):
    faces = ["boards", "frame", "frame", "boards"]
    ids = z.assign_face_ids(faces, {"boards": "wood_light", "frame": "paint_ral7047"}, catalogue)
    assert len(ids) == len(faces)
    assert ids == [14, 4, 4, 14]
    assert all(isinstance(i, int) and 1 <= i < z.UDIM_AS_MATERIAL_ID for i in ids)


def test_geometry_probe_random_faces_stay_complete(z, catalogue):
    """Brute force: assignment never drops a face, never adds one, never emits ID >= 1001."""
    rng = random.Random(889)
    zones = {"boards": "wood_light", "frame": "paint_ral7047", "rope": "rope_pp"}
    for n in range(1, 41):
        mesh = {
            "vertices": [(rng.random(), rng.random(), rng.random()) for _ in range(n + 3)],
            "faces": [rng.choice(tuple(zones)) for _ in range(n)],
        }
        out = z.apply_zone_ids(mesh, zones, catalogue)
        assert len(out["vertices"]) == len(mesh["vertices"])
        assert len(out["faces"]) == len(mesh["faces"]) == n
        assert out["vertices"] == mesh["vertices"]
        assert out["faces"] == mesh["faces"]
        assert len(out["material_ids"]) == n
        assert out["dropped"] == []
        assert all(isinstance(i, int) and 1 <= i < z.UDIM_AS_MATERIAL_ID for i in out["material_ids"])
        used = {out["material_ids"][i] for i in range(n)}
        assert used <= {catalogue[key]["id"] for key in zones.values()}


def test_every_position_and_zone_must_be_mapped(z, catalogue):
    rows = [_pos(sid) for sid in SHOW]
    report = z.compile_zones(list(SHOW), rows, catalogue)
    assert report["ok"] is True
    assert sorted(p["set_id"] for p in report["positions"]) == sorted(SHOW)
    for sid in SHOW:
        kept = [row for row in rows if row["set_id"] != sid]
        with pytest.raises(z.ZoneError, match=sid):
            z.compile_zones(list(SHOW), kept, catalogue)
    for sid in SHOW:
        zrows = [p for p in report["positions"] if p["set_id"] == sid]
        assert len(zrows) == 1
        assert {item["zone"] for item in zrows[0]["zones"]} == {"boards", "frame"}
        assert all(item["id"] < 1001 for item in zrows[0]["zones"])


def test_missing_position_zone_and_material_name_the_key(z, catalogue):
    rows = [_pos(sid) for sid in SHOW]
    with pytest.raises(z.ZoneError, match="VAT_MAF_T3510_16"):
        z.compile_zones(list(SHOW), [row for row in rows if row["set_id"] != "VAT_MAF_T3510_16"], catalogue)
    extra = rows + [_pos("VAT_MAF_GHOST")]
    with pytest.raises(z.ZoneError, match="VAT_MAF_GHOST"):
        z.compile_zones(list(SHOW), extra, catalogue)
    bad = copy.deepcopy(rows)
    bad[0]["zones"][0]["id_key"] = "not_a_material"
    with pytest.raises(z.ZoneError, match="not_a_material"):
        z.compile_zones(list(SHOW), bad, catalogue)
    faces = ["boards", "hinge"]
    with pytest.raises(z.ZoneError, match="hinge"):
        z.assign_face_ids(faces, {"boards": "wood_light"}, catalogue)


@pytest.mark.parametrize("case", ["empty", "partial", "nan", "inf", "id_1001", "id_0", "no_colour", "zero_faces"])
def test_fail_closed(z, catalogue, case):
    rows = [_pos(sid) for sid in SHOW]
    if case == "empty":
        with pytest.raises(z.ZoneError, match="empty"):
            z.compile_zones([], [], catalogue)
        return
    if case == "partial":
        rows[3]["profiles"]["npm"].pop("faces_after")
        match = "faces_after"
    elif case == "nan":
        rows[1]["profiles"]["vpm"]["vertices_before"] = math.nan
        match = "not a finite"
    elif case == "inf":
        rows[2]["profiles"]["npm"]["faces_before"] = math.inf
        match = "not a finite"
    elif case == "id_1001":
        cat = copy.deepcopy(catalogue)
        cat["paint_udim"] = {"id": 1001, "key": "paint_udim", "target": "#111111", "ral": None, "name": "tile"}
        rows[0]["zones"][0]["id_key"] = "paint_udim"
        with pytest.raises(z.ZoneError, match="1001"):
            z.compile_zones(list(SHOW), rows, cat)
        return
    elif case == "id_0":
        cat = copy.deepcopy(catalogue)
        cat["paint_zero"] = {"id": 0, "key": "paint_zero", "target": "#111111", "ral": None, "name": "zero"}
        rows[0]["zones"][0]["id_key"] = "paint_zero"
        with pytest.raises(z.ZoneError, match="paint_zero"):
            z.compile_zones(list(SHOW), rows, cat)
        return
    elif case == "no_colour":
        rows[4]["zones"][1]["colour_source"] = "  "
        match = "colour"
    else:
        rows[5]["profiles"]["npm"]["faces_before"] = 0
        rows[5]["profiles"]["npm"]["faces_after"] = 0
        rows[5]["profiles"]["npm"]["zone_faces"] = {"boards": 0, "frame": 0}
        match = "empty"
    with pytest.raises(z.ZoneError, match=match):
        z.compile_zones(list(SHOW), rows, catalogue)


def test_geometry_mismatch_and_dropped_face_fail(z, catalogue):
    rows = [_pos(sid) for sid in SHOW]
    rows[0]["profiles"]["npm"]["faces_after"] = rows[0]["profiles"]["npm"]["faces_before"] + 1
    with pytest.raises(z.ZoneError, match="faces"):
        z.compile_zones(list(SHOW), rows, catalogue)
    rows = [_pos(sid) for sid in SHOW]
    rows[0]["profiles"]["vpm"]["zone_faces"]["boards"] = 0
    rows[0]["profiles"]["vpm"]["zone_faces"]["frame"] = 3
    with pytest.raises(z.ZoneError, match="boards"):
        z.compile_zones(list(SHOW), rows, catalogue)


def test_catalogue_rejects_bad_ids(z):
    doc = {"version": "v005", "ids": [{"id": 1001, "key": "tile", "target": "#000000", "ral": None, "name_ru": "t"}]}
    with pytest.raises(z.ZoneError, match="1001"):
        z.load_id_catalogue(doc)
    doc = {"version": "v005", "ids": []}
    with pytest.raises(z.ZoneError, match="empty"):
        z.load_id_catalogue(doc)
    doc = {"version": "v005", "ids": [
        {"id": 4, "key": "paint_ral7047", "target": "#D0D0D0", "ral": "7047", "name_ru": "a"},
        {"id": 4, "key": "paint_ral7047", "target": "#D0D0D0", "ral": "7047", "name_ru": "a"},
    ]}
    with pytest.raises(z.ZoneError, match="paint_ral7047"):
        z.load_id_catalogue(doc)


def test_output_path_equal_to_input_writes_nothing(tmp_path):
    counts = tmp_path / "counts.json"
    counts.write_text(COUNTS.read_text(encoding="utf-8"), encoding="utf-8")
    stamp = counts.read_text(encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "review" / "maf_colour_zones.py"),
         "--set", str(SET), "--ids", str(IDS), "--counts", str(counts),
         "--out-json", str(counts), "--out-md", str(tmp_path / "out.md")],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert proc.returncode != 0
    assert "same file" in proc.stderr
    assert counts.read_text(encoding="utf-8") == stamp
    assert not (tmp_path / "out.md").exists()


def test_real_showcase_table_maps_every_position(z, catalogue):
    report_in = json.loads(SET.read_text(encoding="utf-8"))
    counts = json.loads(COUNTS.read_text(encoding="utf-8"))
    rows = z.rows_from_set(report_in, catalogue, counts)
    compiled = z.compile_zones(list(SHOW), rows, catalogue)
    assert compiled["ok"] is True
    assert len(compiled["positions"]) == 13
    seen = []
    for pos in compiled["positions"]:
        assert pos["set_id"] in SHOW
        assert pos["zones"], pos["set_id"]
        for zone in pos["zones"]:
            assert isinstance(zone["id"], int) and 1 <= zone["id"] < 1001
            assert zone["id_key"] in catalogue
            assert zone["colour"].startswith("#")
            assert "photo not measured" in zone["colour_source"]
            seen.append((pos["set_id"], zone["zone"], zone["id"]))
        for prof in ("npm", "vpm"):
            geo = pos["profiles"][prof]
            assert geo["vertices_before"] == geo["vertices_after"]
            assert geo["faces_before"] == geo["faces_after"]
            assert sum(geo["zone_faces"].values()) == geo["faces_before"]
    assert len(seen) == len(set(seen))
    # The accepted set still has single-material meshes. Those stay one zone;
    # a second invented zone is not added.
    single = [p["set_id"] for p in compiled["positions"] if len(p["zones"]) == 1]
    assert "VAT_MAF_T3510_07" in single
    assert "VAT_MAF_T3510_01" not in single
