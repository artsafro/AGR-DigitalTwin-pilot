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
            assert "photo not measured" not in zone["colour_source"]
            assert ("RAL" in zone["colour_source"]) or ("colour assumed" in zone["colour_source"])
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


def _board_and_tube():
    """A flat board and a separate square post. Counts are the input faces."""
    verts = [
        (0.0, 0.0, 0.45), (1.0, 0.0, 0.45), (1.0, 0.30, 0.45), (0.0, 0.30, 0.45),
        (0.0, 0.0, 0.0), (0.04, 0.0, 0.0), (0.04, 0.04, 0.0), (0.0, 0.04, 0.0),
        (0.0, 0.0, 0.40), (0.04, 0.0, 0.40), (0.04, 0.04, 0.40), (0.0, 0.04, 0.40),
    ]
    faces = [
        (0, 1, 2), (0, 2, 3),
        (4, 5, 9), (4, 9, 8),
        (5, 6, 10), (5, 10, 9),
        (6, 7, 11), (6, 11, 10),
        (7, 4, 8), (7, 8, 11),
    ]
    return {"vertices": verts, "faces": faces}


def _policy():
    return {"slab": "wood_light", "shell": "wood_light", "tube": "paint_ral7047", "fastener": "cap_black"}


def test_split_keeps_every_face_and_ids_below_udim(z, catalogue):
    mesh = _board_and_tube()
    out = z.split_mesh(mesh, _policy(), catalogue)
    assert out["vertices"] == mesh["vertices"]
    assert out["faces"] == mesh["faces"]
    assert out["dropped"] == []
    assert len(out["material_ids"]) == len(mesh["faces"])
    assert set(out["material_ids"]) == {14, 4}
    assert all(isinstance(i, int) and 1 <= i < 1001 for i in out["material_ids"])
    assert out["zone_faces"]["slab"] == 2
    assert out["zone_faces"]["tube"] == 8
    assert sum(out["zone_faces"].values()) == len(mesh["faces"])


def test_split_probe_random_meshes_keep_counts_and_legal_ids(z, catalogue):
    """Brute force: a split never adds or drops a vertex or a face and never emits ID >= 1001."""
    rng = random.Random(889)
    policy = _policy()
    for n in range(1, 36):
        verts = [(rng.uniform(-1.0, 2.0), rng.uniform(-1.0, 2.0), rng.uniform(0.0, 1.5))
                 for _ in range(n + 3)]
        faces = [tuple(rng.randrange(len(verts)) for _ in range(3)) for _ in range(n)]
        mesh = {"vertices": verts, "faces": faces}
        out = z.split_mesh(mesh, policy, catalogue)
        assert out["vertices"] == verts
        assert out["faces"] == faces
        assert len(out["material_ids"]) == n
        assert out["dropped"] == []
        assert sum(out["zone_faces"].values()) == n
        assert all(isinstance(i, int) and 1 <= i < z.UDIM_AS_MATERIAL_ID for i in out["material_ids"])


def test_coplanar_faces_share_a_group_and_a_sharp_edge_splits(z):
    flat = {
        "vertices": [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0), (2, 0, 0), (2, 1, 0)],
        "faces": [(0, 1, 2), (0, 2, 3), (1, 4, 5), (1, 5, 2)],
    }
    assert len(set(z.face_groups(flat["vertices"], flat["faces"]))) == 1
    bent = {
        "vertices": [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0), (0, 0, 1), (1, 0, 1)],
        "faces": [(0, 1, 2), (0, 2, 3), (0, 4, 5), (0, 5, 1)],
    }
    assert len(set(z.face_groups(bent["vertices"], bent["faces"]))) == 2


def test_unmapped_kind_nan_and_empty_fail(z, catalogue):
    mesh = _board_and_tube()
    with pytest.raises(z.ZoneError, match="slab"):
        z.split_mesh(mesh, {"tube": "paint_ral7047", "shell": "wood_light", "fastener": "cap_black"}, catalogue)
    bad = copy.deepcopy(mesh)
    bad["vertices"][0] = (math.nan, 0.0, 0.0)
    with pytest.raises(z.ZoneError, match="not a finite"):
        z.split_mesh(bad, _policy(), catalogue)
    with pytest.raises(z.ZoneError, match="empty"):
        z.split_mesh({"vertices": [(0, 0, 0)], "faces": []}, _policy(), catalogue)


def test_committed_zone_table_splits_without_changing_counts():
    report = json.loads((ROOT / "jobs" / "VATUTINO-SITE" / "maf" / "site-maf-zones.json").read_text(encoding="utf-8"))
    assert report["photo_status"] == "not_required"
    assert report["geometry_rewrite"] is False
    by = {pos["set_id"]: pos for pos in report["positions"]}
    assert set(by) == set(SHOW)
    assert {z["zone"] for z in by["VAT_MAF_T3510_07"]["zones"]} >= {"boards", "frame"}
    assert {z["zone"] for z in by["VAT_MAF_T3510_31"]["zones"]} >= {"boards", "frame"}
    assert len(by["VAT_MAF_T3510_02"]["zones"]) == 1
    assert len(by["VAT_MAF_T3510_32"]["zones"]) == 1
    zones_16 = {z["zone"]: z for z in by["VAT_MAF_T3510_16"]["zones"]}
    assert zones_16["frame"]["id"] == 4
    assert zones_16["boards"]["id"] == 14
    assert by["VAT_MAF_T3510_16"]["profiles"]["npm"]["zone_faces"]["frame"] > 0
    assert by["VAT_MAF_T3510_16"]["profiles"]["npm"]["zone_faces"]["boards"] > 0
    assert "share one schedule finish" not in (by["VAT_MAF_T3510_16"].get("split_note") or "")
    assert report.get("max_exit_code") == 4294967166
    assert report.get("apply_marker") == "APPLIED"
    for pos in report["positions"]:
        for zone in pos["zones"]:
            assert isinstance(zone["id"], int) and 1 <= zone["id"] < 1001
            assert "photo not measured" not in zone["colour_source"]
            assert ("RAL" in zone["colour_source"]) or ("colour assumed" in zone["colour_source"])
        for prof in ("npm", "vpm"):
            geo = pos["profiles"][prof]
            assert geo["vertices_before"] == geo["vertices_after"]
            assert geo["faces_before"] == geo["faces_after"]
            assert sum(geo["zone_faces"].values()) == geo["faces_before"]


def test_position_16_policy_paints_tube_faces_id_4(z, catalogue):
    """ДП 090 schedule is steel RAL 7047 + larch. Tube groups take paint ID 4."""
    mesh = _board_and_tube()
    out = z.split_mesh(mesh, z.POSITION_POLICY["VAT_MAF_T3510_16"], catalogue)
    assert out["material_ids"][:2] == [14, 14]
    assert out["material_ids"][2:] == [4] * 8
    assert out["zone_faces"]["tube"] == 8
    assert 4 in out["material_ids"]


def test_two_schedule_finishes_cannot_end_as_one_zone(z, catalogue):
    """A schedule that names two finishes must not compile as a single zone."""
    row = _pos("VAT_MAF_T3510_16", faces=4, verts=6)
    row["zones"] = [row["zones"][0]]
    for prof in ("npm", "vpm"):
        row["profiles"][prof]["zone_faces"] = {"boards": 4}
    row["schedule_finishes"] = ["wood_light", "paint_ral7047"]
    with pytest.raises(z.ZoneError, match="VAT_MAF_T3510_16"):
        z.compile_zones(["VAT_MAF_T3510_16"], [row], catalogue)
    kept = _pos("VAT_MAF_T3510_16", faces=4, verts=6)
    kept["schedule_finishes"] = ["wood_light", "paint_ral7047"]
    assert z.compile_zones(["VAT_MAF_T3510_16"], [kept], catalogue)["ok"] is True


def test_finish_colour_uses_schedule_ral_or_marks_assumed(z, catalogue):
    steel = z.finish_colour("steel_ral7047", catalogue)
    assert steel["id"] == 4
    assert steel["colour"] == "#D0D0D0"
    assert "RAL 7047" in steel["colour_source"]
    assert "colour assumed" not in steel["colour_source"]
    assert "photo not measured" not in steel["colour_source"]
    wood = z.finish_colour("larch_light_oak", catalogue)
    assert wood["id"] == 14
    assert wood["colour"] == "#C49A6C"
    assert "colour assumed" in wood["colour_source"]
    assert "light oak" in wood["colour_source"]
    rope = z.finish_colour("rope_pp", catalogue)
    assert "colour assumed" in rope["colour_source"]
    hpl = z.finish_colour("hpl_satin_wood", catalogue)
    assert "colour assumed" in hpl["colour_source"]
    assert hpl["id"] < 1001
    with pytest.raises(z.ZoneError, match="missing_slot"):
        z.finish_colour("missing_slot", catalogue)
