"""new-case: MAF colour zones for the 13 Vatutino showcase positions (#889).

Material IDs come from the approved v006 list (v005 + ID 32 HPL, D229). A face ID >= 1001 is an error.
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
IDS = ROOT / "library" / "maf" / "material_ids_v006.json"  # v006 = v005 + ID 32 (D229)
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
    # Atlas-only single-slot rows cannot certify a multi-finish schedule.
    for row in rows:
        sid = row["set_id"]
        if len(row["zones"]) == 1 and len(z.SCHEDULE_FINISHES[sid]) >= 2:
            with pytest.raises(z.ZoneError, match=f"{sid}: schedule names"):
                z.compile_zones([sid], [row], catalogue)
        else:
            assert z.compile_zones([sid], [row], catalogue)["ok"] is True
    applied_rows = json.loads(ZONES_JSON.read_text(encoding="utf-8"))["positions"]
    compiled = z.compile_zones(list(SHOW), applied_rows, catalogue)
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
    # The applied table retains single zones only for single-finish positions.
    single = [p["set_id"] for p in compiled["positions"] if len(p["zones"]) == 1]
    assert set(single) == {"VAT_MAF_T3510_02", "VAT_MAF_T3510_32"}


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


def test_rows_from_set_rejects_collapsed_schedule(z, catalogue):
    report_in = json.loads(SET.read_text(encoding="utf-8"))
    pos = next(p for p in report_in["positions"] if p["set_id"] == "VAT_MAF_T3510_16")
    # Synthetic collapse: keep every face, but assign all to the wood atlas slot.
    for prof in ("npm", "vpm"):
        uv = pos[prof]["uv_slots"]
        uv["per_material"] = {"larch_light_oak": {"faces": uv["faces"]}}
    counts = json.loads(COUNTS.read_text(encoding="utf-8"))
    rows = z.rows_from_set({"positions": [pos]}, catalogue, counts)
    assert "schedule_finishes" not in rows[0]
    with pytest.raises(z.ZoneError, match="VAT_MAF_T3510_16: schedule names 2 finishes but one zone"):
        z.compile_zones([pos["set_id"]], rows, catalogue)


@pytest.mark.parametrize("set_id", SHOW)
@pytest.mark.parametrize("schedule_state", ["absent", "null"])
def test_schedule_fallback_exhaustive(z, catalogue, set_id, schedule_state):
    """All 13 real schedules: complete -> synthetic collapse -> complete reset."""
    doc = json.loads(ZONES_JSON.read_text(encoding="utf-8"))
    row = next(p for p in doc["positions"] if p["set_id"] == set_id)
    row.pop("schedule_finishes")
    if schedule_state == "null":
        row["schedule_finishes"] = None
    original = copy.deepcopy(row)
    assert z.compile_zones([set_id], [row], catalogue)["ok"] is True
    collapsed = copy.deepcopy(row)
    collapsed["zones"] = collapsed["zones"][:1]
    for geo in collapsed["profiles"].values():
        geo["zone_faces"] = {collapsed["zones"][0]["zone"]: geo["faces_before"]}
    for _ in range(2):
        if set_id in {"VAT_MAF_T3510_02", "VAT_MAF_T3510_32"}:
            assert z.compile_zones([set_id], [collapsed], catalogue)["ok"] is True
        else:
            with pytest.raises(z.ZoneError, match=f"{set_id}: schedule names .* finishes but one zone"):
                z.compile_zones([set_id], [collapsed], catalogue)
    assert z.compile_zones([set_id], [row], catalogue)["ok"] is True
    assert row == original


def test_missing_schedule_rejects_unknown_position(z, catalogue):
    with pytest.raises(z.ZoneError, match="^unmapped position: VAT_MAF_GHOST$"):
        z.compile_zones(["VAT_MAF_GHOST"], [_pos("VAT_MAF_GHOST")], catalogue)


@pytest.mark.parametrize("finishes", [[], "wood_light", ["ghost_finish"], [math.nan], [math.inf]])
def test_invalid_explicit_schedule(z, catalogue, finishes):
    row = _pos()
    row["schedule_finishes"] = finishes
    with pytest.raises(z.ZoneError):
        z.compile_zones([row["set_id"]], [row], catalogue)


def test_atlas_cli_rejects_missing_schedule_without_writes(tmp_path):
    out_json, out_md = tmp_path / "out.json", tmp_path / "out.md"
    out_json.write_text("stale report", encoding="utf-8")
    out_md.write_text("stale markdown", encoding="utf-8")
    inputs = {p: p.read_bytes() for p in (SET, IDS, COUNTS)}
    proc = subprocess.run(
        [sys.executable, str(ROOT / "tools/review/maf_colour_zones.py"),
         "--set", str(SET), "--ids", str(IDS), "--counts", str(COUNTS),
         "--out-json", str(out_json), "--out-md", str(out_md)],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert proc.returncode == 1
    assert "schedule names" in proc.stderr
    assert proc.stdout == ""
    assert out_json.read_text(encoding="utf-8") == "stale report"
    assert out_md.read_text(encoding="utf-8") == "stale markdown"
    assert {p: p.read_bytes() for p in inputs} == inputs


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


def _committed_one_zone(set_id):
    doc = json.loads(ZONES_JSON.read_text(encoding="utf-8"))
    row = next(p for p in doc["positions"] if p["set_id"] == set_id)
    row["zones"] = row["zones"][:1]
    for geo in row["profiles"].values():
        geo["zone_faces"] = {row["zones"][0]["zone"]: geo["faces_before"]}
    return row


@pytest.mark.parametrize("finishes", [["wood_light", "wood_light"], ["wood_light"]])
def test_explicit_schedule_cannot_understate_table_1185(z, catalogue, finishes):
    """#1185: an explicit row field may not hide a finish the canonical schedule names."""
    row = _committed_one_zone("VAT_MAF_T3510_16")
    row["schedule_finishes"] = finishes
    with pytest.raises(z.ZoneError, match="^VAT_MAF_T3510_16: schedule_finishes differ from schedule$"):
        z.compile_zones(["VAT_MAF_T3510_16"], [row], catalogue)


def test_explicit_schedule_matching_table_still_guards_1185(z, catalogue):
    row = _committed_one_zone("VAT_MAF_T3510_16")
    row["schedule_finishes"] = ["paint_ral7047", "wood_light"]
    with pytest.raises(z.ZoneError, match="schedule names 2 finishes but one zone"):
        z.compile_zones(["VAT_MAF_T3510_16"], [row], catalogue)
    full = json.loads(ZONES_JSON.read_text(encoding="utf-8"))
    full_row = next(p for p in full["positions"] if p["set_id"] == "VAT_MAF_T3510_16")
    full_row["schedule_finishes"] = ["paint_ral7047", "wood_light", "wood_light"]
    assert z.compile_zones(["VAT_MAF_T3510_16"], [full_row], catalogue)["ok"] is True


@pytest.mark.parametrize("set_id", SHOW)
def test_explicit_schedule_exhaustive_subsets_and_supersets_1185(z, catalogue, set_id):
    """Every proper subset / superset of every table schedule is rejected; the table itself passes."""
    import itertools
    table = set(z.SCHEDULE_FINISHES[set_id])
    keys = sorted(z.ZONE_OF_KEY)
    full = json.loads(ZONES_JSON.read_text(encoding="utf-8"))
    row = next(p for p in full["positions"] if p["set_id"] == set_id)
    checked = 0
    for n in range(1, 4):
        for combo in itertools.combinations(keys, n):
            cand = copy.deepcopy(row)
            cand["schedule_finishes"] = list(combo)
            if set(combo) == table:
                assert z.compile_zones([set_id], [cand], catalogue)["ok"] is True
            else:
                with pytest.raises(z.ZoneError, match=f"^{set_id}: schedule_finishes differ from schedule$"):
                    z.compile_zones([set_id], [cand], catalogue)
            checked += 1
    assert checked > len(keys)


def test_explicit_schedule_on_unmapped_position_is_error_1185(z, catalogue):
    row = _pos("VAT_MAF_GHOST")
    row["schedule_finishes"] = ["wood_light", "paint_ral7047"]
    with pytest.raises(z.ZoneError, match="^unmapped position: VAT_MAF_GHOST$"):
        z.compile_zones(["VAT_MAF_GHOST"], [row], catalogue)


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


ZONES_JSON = ROOT / "jobs" / "VATUTINO-SITE" / "maf" / "site-maf-zones.json"


def test_one_id_with_two_colours_across_the_set_fails(z):
    # #993: per-node checks passed while ID 14 was #C49A6C on 01..31 and #B4825A on 26.
    records = [("VAT_MAF_T3510_01/npm", 14, "#C49A6C"), ("VAT_MAF_T3510_26/npm", 14, "#B4825A")]
    with pytest.raises(z.ZoneError, match=r"material id 14 has two colours: #C49A6C .*_01.* #B4825A .*_26"):
        z.check_id_colours(records)
    assert z.check_id_colours(records[:1] + [("VAT_MAF_T3510_26/npm", 32, "#B4825A")]) == {
        14: "#C49A6C", 32: "#B4825A"}
    with pytest.raises(z.ZoneError, match="empty"):
        z.check_id_colours([])


def test_hpl_has_its_own_id_and_every_finish_id_one_colour(z, catalogue):
    hpl = z.finish_colour("hpl_satin_wood", catalogue)
    assert (hpl["id"], hpl["id_key"], hpl["colour"]) == (32, "wood_hpl_satin", "#B4825A")
    assert z.finish_colour("larch_light_oak", catalogue)["id"] == 14
    z.check_id_colours((slot, z.finish_colour(slot, catalogue)["id"], row["colour"])
                       for slot, row in z.FINISH.items())
    assert "wood_hpl_satin" in z.SCHEDULE_FINISHES["VAT_MAF_T3510_26"]


def test_committed_zone_table_has_one_colour_per_id(z):
    doc = json.loads(ZONES_JSON.read_text(encoding="utf-8"))
    got = z.check_id_colours((p["set_id"], zone["id"], zone["colour"])
                             for p in doc["positions"] for zone in p["zones"])
    assert got[14] == "#C49A6C" and got[32] == "#B4825A"


def test_compile_rejects_applied_report_with_two_colours_for_one_id(z):
    rows = [{"set_id": "A", "zones": [{"zone": "boards", "id_key": "wood_light", "id": 14, "colour": "#C49A6C"}]},
            {"set_id": "B", "zones": [{"zone": "hpl", "id_key": "wood_light", "id": 14, "colour": "#B4825A"}]}]
    with pytest.raises(z.ZoneError, match="material id 14 has two colours"):
        z.check_rows_id_colours(rows)
