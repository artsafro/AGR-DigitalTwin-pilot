"""Synthetic tests for the MAF library planner (issue #183)."""

import importlib.util
import json
import random
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location("maf_catalogue", ROOT / "tools" / "library" / "maf_catalogue.py")
cat = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(cat)


def _box(x, y, z, sx=1.0, sy=1.0, sz=1.0):
    return ((x, y, z), (x + sx, y + sy, z + sz))


def _brute_clusters(boxes, gap):
    n = len(boxes)
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for i in range(n):
        for j in range(i + 1, n):
            if cat.box_gap(boxes[i], boxes[j]) <= gap:
                union(i, j)
    buckets = {}
    for i in range(n):
        buckets.setdefault(find(i), []).append(i)
    groups = [sorted(members) for members in buckets.values()]
    groups.sort(key=lambda group: group[0])
    return groups


def test_box_gap_and_cluster_thresholds():
    near = [_box(0, 0, 0), _box(1.4, 0, 0)]
    assert cat.box_gap(near[0], near[1]) == pytest.approx(0.4)
    assert cat.cluster_boxes(near, 0.5) == [[0, 1]]

    far = [_box(0, 0, 0), _box(1.6, 0, 0)]
    assert cat.box_gap(far[0], far[1]) == pytest.approx(0.6)
    assert cat.cluster_boxes(far, 0.5) == [[0], [1]]


def test_cluster_chain_is_transitive_and_empty_is_empty():
    chain = [_box(0, 0, 0), _box(1.4, 0, 0), _box(2.8, 0, 0)]
    assert cat.box_gap(chain[0], chain[2]) == pytest.approx(1.8)
    assert cat.cluster_boxes(chain, 0.5) == [[0, 1, 2]]
    assert cat.cluster_boxes([], 0.5) == []


def test_cluster_sweep_matches_all_pairs():
    rng = random.Random(123)
    boxes = []
    for _ in range(300):
        x, y, z = (rng.uniform(0, 30) for _ in range(3))
        boxes.append(_box(x, y, z, rng.uniform(0.1, 2), rng.uniform(0.1, 2), rng.uniform(0.1, 2)))
    for gap in (0.0, 0.25, 0.5, 1.0):
        assert cat.cluster_boxes(boxes, gap) == _brute_clusters(boxes, gap)


def _obj(name, handle, cls, tris=None, elements=None, bbox=None, mat_ids=None, material="wood"):
    row = {
        "name": name,
        "handle": handle,
        "class": cls,
        "super": "GeometryClass",
        "layer": "MAF",
        "parent": None,
        "material": material,
    }
    if tris is not None:
        row["tris"] = tris
    if mat_ids is not None:
        row["mat_ids"] = mat_ids
    if bbox is not None:
        row["bbox"] = bbox
    if elements is not None:
        row["elements"] = elements
    return row


def _element(first_face, tris, bbox):
    return {"first_face": first_face, "tris": tris, "bbox": bbox}


def _scene(*objects):
    return {"scene": "library.max", "units": "meters", "unit_to_m": 1.0, "objects": list(objects)}


def test_plan_splits_clusters_and_excludes_helpers():
    bench = _obj(
        "Лавка 1", 10, "Editable_mesh", tris=100, mat_ids=[2, 5], material="wood",
        bbox=[[0, 0, 0], [5, 1, 1]],
        elements=[
            _element(80, 10, [[0.2, 0, 0], [0.8, 0.5, 0.5]]),
            _element(1, 30, [[0, 0, 0], [1, 1, 1]]),
            _element(50, 60, [[4, 0, 0], [5, 1, 1]]),
        ],
    )
    urn = _obj(
        "Urn", 11, "Editable_mesh", tris=10, mat_ids=[1],
        bbox=[[0, 0, 0], [0.5, 0.5, 0.5]],
        elements=[_element(3, 10, [[0, 0, 0], [0.5, 0.5, 0.5]])],
    )
    plate = _obj(
        "Ground", 12, "Plane", tris=8, mat_ids=[0],
        bbox=[[0, 0, 0], [10, 10, 0.001]],
        elements=[_element(1, 8, [[0, 0, 0], [10, 10, 0.001]])],
    )
    label = _obj("Title", 13, "TextPlus", material=None)
    plan = cat.plan_library(_scene(bench, label, plate, urn))

    assert [e["id"] for e in plan["entries"]] == ["MAF_0001", "MAF_0002", "MAF_0003"]
    split = [e for e in plan["entries"] if e["source_object"] == "Лавка 1"]
    assert len(split) == 2
    assert all(e["split"] is True and e["cluster_count"] == 2 for e in split)
    assert [e["cluster_index"] for e in split] == [0, 1]
    assert split[0]["element_first_faces"] == [1, 80]
    assert split[0]["element_count"] == 2 and split[0]["tris"] == 40
    assert split[1]["element_first_faces"] == [50]
    assert split[0]["tris"] + split[1]["tris"] == 100
    assert split[0]["bbox"] == [[0.0, 0.0, 0.0], [1.0, 1.0, 1.0]]
    assert split[0]["dims_m"] == [1.0, 1.0, 1.0]
    assert split[0]["mat_ids_object"] == [2, 5]
    assert split[0]["slug"].startswith("MAF_0001_")
    assert split[0]["slug"].isascii() and len(split[0]["slug"]) <= 60
    assert "Lavka" in split[0]["slug"]

    single = plan["entries"][2]
    assert single["source_object"] == "Urn" and single["split"] is False
    assert single["cluster_count"] == 1 and single["element_count"] == 1

    reasons = {(row["name"], row["reason"]) for row in plan["excluded"]}
    assert reasons == {("Title", "non_geometry"), ("Ground", "helper_plane")}
    assert plan["counts"]["objects"] == 4
    assert plan["counts"]["maf_candidate"] == 2
    assert plan["counts"]["helper_plane"] == 1
    assert plan["counts"]["non_geometry"] == 1
    assert plan["counts"]["split_objects"] == 1
    assert plan["counts"]["maf_entries"] == 3
    assert plan["counts"]["tris_total"] == 110
    assert plan["gap_m"] == 0.5 and plan["scene"] == "library.max"


def test_plan_invariants_on_a_random_scene():
    rng = random.Random(7)
    gap = 0.5
    objects = []
    face_serial = 1
    for oi in range(5):
        centers = [(oi * 40.0 + c * 8.0, c * 6.0, 0.0) for c in range(rng.randint(1, 3))]
        elements = []
        for _ei in range(rng.randint(1, 7)):
            cx, cy, _cz = rng.choice(centers)
            x = cx + rng.uniform(0, 0.04)
            y = cy + rng.uniform(0, 0.04)
            z = rng.uniform(0, 0.02)
            s = rng.uniform(0.05, 0.12)
            elements.append(_element(
                face_serial, rng.randint(1, 20),
                [[x, y, z], [x + s, y + s, z + s]],
            ))
            face_serial += 10
        tris = sum(el["tris"] for el in elements)
        objects.append(_obj(
            f"obj{oi}", 100 + oi, "Editable_mesh", tris=tris, mat_ids=[1],
            bbox=[[0, 0, 0], [1, 1, 1]], elements=elements,
        ))
    objects.append(_obj("note", 1, "TextPlus"))
    plan = cat.plan_library(_scene(*objects), gap_m=gap)
    by_handle = {}
    for entry in plan["entries"]:
        by_handle.setdefault(entry["source_handle"], []).append(entry)

    candidate_tris = 0
    seen_faces = []
    for obj in objects:
        if cat.classify(obj) != "maf_candidate":
            continue
        candidate_tris += obj["tris"]
        entries = by_handle[obj["handle"]]
        faces = [face for entry in entries for face in entry["element_first_faces"]]
        assert sorted(faces) == sorted(el["first_face"] for el in obj["elements"])
        assert len(faces) == len(set(faces))
        assert sum(entry["tris"] for entry in entries) == obj["tris"]
        face_box = {el["first_face"]: el["bbox"] for el in obj["elements"]}
        for i in range(len(entries)):
            for j in range(i + 1, len(entries)):
                for fa in entries[i]["element_first_faces"]:
                    for fb in entries[j]["element_first_faces"]:
                        assert cat.box_gap(face_box[fa], face_box[fb]) > gap
        seen_faces.extend(faces)
    assert sum(entry["tris"] for entry in plan["entries"]) == candidate_tris
    assert len(seen_faces) == len(set(seen_faces)) == sum(
        len(obj["elements"]) for obj in objects if cat.classify(obj) == "maf_candidate"
    )


def test_find_duplicates_treats_z_rotation_as_the_same_footprint():
    entries = [
        {"id": "MAF_0002", "tris": 100, "dims_m": [2.0, 1.0, 0.5]},
        {"id": "MAF_0001", "tris": 100, "dims_m": [1.0, 2.0, 0.5]},
        {"id": "MAF_0003", "tris": 101, "dims_m": [1.0, 2.0, 0.5]},
        {"id": "MAF_0004", "tris": 100, "dims_m": [1.0, 2.0, 0.53]},
    ]
    assert cat.find_duplicates(entries) == [["MAF_0001", "MAF_0002"]]


def test_find_overlaps_ignores_same_object_and_touching_faces():
    entries = [
        {"id": "MAF_0001", "source_object": "a", "source_handle": 1, "bbox": [[0, 0, 0], [1, 1, 1]]},
        {"id": "MAF_0002", "source_object": "a", "source_handle": 1, "bbox": [[0.2, 0.2, 0.2], [0.8, 0.8, 0.8]]},
        {"id": "MAF_0003", "source_object": "b", "source_handle": 2, "bbox": [[0.2, 0.2, 0.2], [0.8, 0.8, 0.8]]},
        {"id": "MAF_0004", "source_object": "c", "source_handle": 3, "bbox": [[1, 0, 0], [2, 1, 1]]},
    ]
    assert cat.find_overlaps(entries) == [["MAF_0001", "MAF_0003"], ["MAF_0002", "MAF_0003"]]


def test_normalize_name_and_match_npm():
    blend_name = "C_Meb2043_Parkoviy stol Skver.001"
    source = "Meb2043_Parkoviy stol Skver"
    assert cat.normalize_name(blend_name) == cat.normalize_name(source)
    assert cat.normalize_name("CRP_Foo.012") == "foo"
    assert cat.normalize_name(blend_name) == "meb2043 parkoviy stol skver"

    entries = [
        {"id": "MAF_0001", "source_object": source, "tris": 500, "dims_m": [1.2, 0.8, 0.75]},
        {"id": "MAF_0002", "source_object": "Other bench", "tris": 800, "dims_m": [2.0, 0.5, 0.4]},
        {"id": "MAF_0004", "source_object": "Alpha bench", "tris": 10, "dims_m": [1.0, 1.0, 1.0]},
        {"id": "MAF_0005", "source_object": "Beta", "tris": 10, "dims_m": [1.05, 1.0, 1.0]},
        {"id": "MAF_0006", "source_object": "Big Parkoviy stol model", "tris": 40, "dims_m": [0.4, 0.4, 0.9]},
    ]
    blend = {"objects": [
        {"name": blend_name, "type": "MESH", "collections": ["NPM"], "tris": 200, "dims": [1.2, 0.8, 0.75]},
        {"name": "SomeOther", "type": "MESH", "collections": ["NPM"], "tris": 900, "dims": [0.51, 2.01, 0.4]},
        {"name": "Nope", "type": "MESH", "collections": [], "tris": 1, "dims": [9, 9, 9]},
        {"name": "Almost", "type": "MESH", "collections": [], "tris": 1, "dims": [1.2, 0.8, 0.86]},
        {"name": "Alpha bench", "type": "MESH", "collections": ["NPM"], "tris": 12, "dims": [1.05, 1.0, 1.0]},
        {"name": "C_Parkoviy_stol.001", "type": "MESH", "collections": ["NPM"], "tris": 4, "dims": [0.4, 0.4, 0.9]},
        {"name": "Camera", "type": "CAMERA", "collections": [], "tris": 0, "dims": [1, 1, 1]},
    ]}
    rows = cat.match_npm(entries, blend)
    assert [row["blend_name"] for row in rows] == [obj["name"] for obj in blend["objects"] if obj["type"] == "MESH"]

    named = rows[0]
    assert named["method"] == "name+dims"
    assert named["maf_id"] == "MAF_0001"
    assert named["source_object"] == source
    assert named["score_m"] == pytest.approx(0.0)
    assert named["n_candidates"] == 1
    assert named["light_pair"] is True
    assert named["collections"] == ["NPM"]

    dims_only = rows[1]
    assert dims_only["method"] == "dims" and dims_only["maf_id"] == "MAF_0002"
    assert dims_only["score_m"] == pytest.approx(0.01)
    assert dims_only["light_pair"] is False

    assert rows[2]["method"] == "none" and rows[2]["maf_id"] is None and rows[2]["n_candidates"] == 0
    assert rows[3]["method"] == "none" and rows[3]["n_candidates"] == 0

    preferred = rows[4]
    assert preferred["method"] == "name+dims" and preferred["maf_id"] == "MAF_0004"
    assert preferred["n_candidates"] == 2

    contained = rows[5]
    assert contained["method"] == "name+dims" and contained["maf_id"] == "MAF_0006"


def test_build_catalogue_and_markdown():
    plan = cat.plan_library(_scene(
        _obj("Bench", 1, "Editable_mesh", tris=10, mat_ids=[3],
             bbox=[[0, 0, 0], [1, 1, 1]],
             elements=[_element(1, 10, [[0, 0, 0], [1, 1, 1]])]),
        _obj("Lamp", 2, "Editable_mesh", tris=4, mat_ids=[1],
             bbox=[[0.2, 0.2, 0.2], [0.6, 0.6, 1.2]],
             elements=[_element(1, 4, [[0.2, 0.2, 0.2], [0.6, 0.6, 1.2]])]),
    ))
    built = [{
        "id": "MAF_0001", "ok": True, "max_path": "a.max", "fbx_path": "a.fbx",
        "preview_path": "a.png", "mat_ids": [3], "tris_built": 10,
    }]
    matches = [
        {"blend_name": "C_Bench.001", "maf_id": "MAF_0001", "method": "name+dims"},
        {"blend_name": "Other", "maf_id": None, "method": "none"},
    ]
    duplicates = [["MAF_0001", "MAF_0009"]]
    overlaps = [["MAF_0001", "MAF_0002"]]
    catalogue = cat.build_catalogue(plan, built, matches, duplicates, overlaps)
    by_id = {entry["id"]: entry for entry in catalogue["entries"]}
    assert by_id["MAF_0001"]["ok"] is True
    assert by_id["MAF_0001"]["preview_path"] == "a.png"
    assert by_id["MAF_0001"]["npm_matches"] == ["C_Bench.001"]
    assert by_id["MAF_0001"]["dup_group"] == 0
    assert by_id["MAF_0001"]["overlaps_with"] == ["MAF_0002"]
    assert by_id["MAF_0002"]["ok"] is False and by_id["MAF_0002"]["error"] == "not built"
    assert by_id["MAF_0002"]["overlaps_with"] == ["MAF_0001"]
    counts = catalogue["counts"]
    assert counts["built_ok"] == 1 and counts["built_failed"] == 1
    assert counts["duplicates_groups"] == 1 and counts["duplicate_entries"] == 2
    assert counts["npm_rows"] == 2 and counts["npm_matched_name"] == 1
    assert counts["npm_matched_dims"] == 0 and counts["npm_unmatched"] == 1

    md = cat.render_markdown(catalogue)
    for entry in catalogue["entries"]:
        assert entry["id"] in md
    assert "a.png" in md
    assert "| id | source object | split | dims m | tris | mat IDs | dup | NPM match | preview |" in md


def test_contact_sheet(tmp_path):
    images = []
    entries = []
    for index, color in enumerate(((255, 0, 0), (0, 0, 255))):
        path = tmp_path / f"p{index}.png"
        Image.new("RGB", (8, 8), color).save(path)
        images.append(path)
        entries.append({"id": f"MAF_{index + 1:04d}", "preview_path": str(path)})
    entries.append({"id": "MAF_0003", "preview_path": str(tmp_path / "missing.png")})
    out = tmp_path / "sheet.png"
    assert cat.contact_sheet(entries, out, thumb=32, cols=2) == 2
    assert out.is_file() and out.stat().st_size > 0
    with Image.open(out) as sheet:
        assert sheet.size[0] == 64 and sheet.size[1] > 32

    empty = tmp_path / "empty.png"
    assert cat.contact_sheet([{"id": "MAF_0001", "preview_path": str(tmp_path / "nope.png")}], empty) == 0
    assert not empty.exists()


def test_cli_round_trip(tmp_path, capsys):
    elements = _scene(
        _obj("Bench", 1, "Editable_mesh", tris=10, mat_ids=[3],
             bbox=[[0, 0, 0], [1, 1, 1]],
             elements=[_element(1, 10, [[0, 0, 0], [1, 1, 1]])]),
        _obj("Note", 2, "TextPlus"),
    )
    elements_path = tmp_path / "elements.json"
    plan_path = tmp_path / "plan.json"
    elements_path.write_text(json.dumps(elements), encoding="utf-8")
    assert cat.main(["plan", "--elements", str(elements_path), "--out", str(plan_path), "--gap", "0.5"]) == 0
    plan_summary = json.loads(capsys.readouterr().out.strip())
    assert plan_summary["maf_entries"] == 1
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    assert plan["entries"][0]["id"] == "MAF_0001"
    assert "\n  " in plan_path.read_text(encoding="utf-8")

    built_path = tmp_path / "built.jsonl"
    preview = tmp_path / "bench.png"
    Image.new("RGB", (4, 4), (10, 20, 30)).save(preview)
    built_path.write_text(json.dumps({
        "id": "MAF_0001", "ok": True, "max_path": "bench.max", "fbx_path": "bench.fbx",
        "preview_path": str(preview), "mat_ids": [3], "tris_built": 10,
    }) + "\n", encoding="utf-8")
    blend_path = tmp_path / "blend.json"
    blend_path.write_text(json.dumps({"objects": [
        {"name": "C_Bench.001", "type": "MESH", "collections": ["NPM"], "tris": 4, "dims": [1, 1, 1]},
    ]}), encoding="utf-8")
    out_json = tmp_path / "catalogue.json"
    out_md = tmp_path / "catalogue.md"
    sheet = tmp_path / "sheet.png"
    missing_built = tmp_path / "absent.jsonl"
    assert cat.main([
        "catalogue", "--plan", str(plan_path), "--built", str(missing_built),
        "--blend", str(blend_path), "--out-json", str(out_json), "--out-md", str(out_md),
    ]) == 0
    missing_summary = json.loads(capsys.readouterr().out.strip())
    assert missing_summary["built_failed"] == 1 and missing_summary["built_ok"] == 0

    assert cat.main([
        "catalogue", "--plan", str(plan_path), "--built", str(built_path),
        "--blend", str(blend_path), "--out-json", str(out_json), "--out-md", str(out_md),
        "--contact-sheet", str(sheet),
    ]) == 0
    summary = json.loads(capsys.readouterr().out.strip())
    assert summary["built_ok"] == 1 and summary["npm_matched_name"] == 1
    catalogue = json.loads(out_json.read_text(encoding="utf-8"))
    assert catalogue["entries"][0]["ok"] is True
    md = out_md.read_text(encoding="utf-8")
    assert "MAF_0001" in md and "Bench" in md
    assert sheet.is_file()


def test_parse_spec_dims_examples():
    chair = "Кресло «Кафе» Palissade\n\nДлина: 700 мм\nШирина: 800 мм\nВысота: 700 мм"
    got = cat.parse_spec_dims(chair)
    assert (got["l_m"], got["w_m"], got["h_m"]) == pytest.approx((0.7, 0.8, 0.7))

    box = "Контейнеры «ГРАТАН»\n\nАртикул: ГРАТАН\n\nДлина: 1 377 мм\nШирина: 1077 мм\nВысота: 1370 мм"
    got = cat.parse_spec_dims(box)
    assert (got["l_m"], got["w_m"], got["h_m"]) == pytest.approx((1.377, 1.077, 1.37))

    urn = "Урна\nДиаметр: 400 мм\nВысота: 750 мм"
    got = cat.parse_spec_dims(urn)
    assert (got["l_m"], got["w_m"], got["h_m"]) == pytest.approx((0.4, 0.4, 0.75))

    assert cat.parse_spec_dims("Кресло без размеров") is None
    assert cat.parse_spec_dims("Артикул: ГРАТАН") is None
    metres = cat.parse_spec_dims("Стол\nВысота: 0,75 м")
    assert metres["h_m"] == pytest.approx(0.75)
    assert metres["l_m"] is None and metres["w_m"] is None
    short = cat.parse_spec_dims("Стол\nД: 1000 мм\nШ: 500 мм\nВ: 450 мм")
    assert (short["l_m"], short["w_m"], short["h_m"]) == pytest.approx((1.0, 0.5, 0.45))


def test_match_spec_rotation_tolerance_and_name_hit():
    entries = [
        {"id": "MAF_0002", "source_object": "Other", "slug": "slug-other", "dims_m": [0.8, 0.7, 0.7]},
        {"id": "MAF_0001", "source_object": "Кресло", "slug": "slug-chair", "dims_m": [0.7, 0.8, 0.7]},
        {"id": "MAF_0003", "source_object": "Tall", "slug": "slug-tall", "dims_m": [0.7, 0.8, 0.81]},
        {"id": "MAF_0004", "source_object": "Urn", "slug": "slug-urn", "dims_m": [0.4, 0.4, 2.0]},
    ]
    rows = cat.match_spec(entries, [
        {
            "row": 5,
            "name": "Кресло «Кафе»",
            "type": "мебель",
            "availability": "да",
            "dims": {"l_m": 0.7, "w_m": 0.8, "h_m": 0.7},
            "max_names": ["Кресло"],
        },
        {
            "row": 6,
            "name": "Без размера",
            "type": "мебель",
            "availability": "нет",
            "dims": None,
            "max_names": ["missing"],
        },
        {
            "row": 8,
            "name": "Урна",
            "type": "урны",
            "availability": "да",
            "dims": {"l_m": 0.4, "w_m": 0.4, "h_m": None},
            "max_names": ["slug-urn"],
        },
        {
            "row": 9,
            "name": "Только высота",
            "type": "мебель",
            "availability": "да",
            "dims": {"l_m": None, "w_m": None, "h_m": 0.7},
            "max_names": [],
        },
    ])
    hit = rows[0]
    assert hit["n_candidates"] == 2
    assert [item["id"] for item in hit["best"]] == ["MAF_0001", "MAF_0002"]
    assert hit["best"][0]["score_m"] == pytest.approx(0.0)
    assert hit["name_hit"] is True
    assert hit["type"] == "мебель" and hit["availability"] == "да"
    assert "reason" not in hit
    missing = rows[1]
    assert missing["n_candidates"] == 0 and missing["reason"] == "no dims" and missing["best"] == []
    assert missing["name_hit"] is False
    urn = rows[2]
    assert [item["id"] for item in urn["best"]] == ["MAF_0004"]
    assert urn["name_hit"] is True
    assert urn["best"][0]["score_m"] == pytest.approx(0.0)
    height_only = rows[3]
    assert [item["id"] for item in height_only["best"]] == ["MAF_0001", "MAF_0002"]
    assert height_only["name_hit"] is False


def test_build_catalogue_records_spec_candidates():
    entries = [
        {
            "id": "MAF_0001", "source_object": "Bench", "slug": "s1", "dims_m": [1.0, 0.5, 0.4],
            "tris": 10, "split": False, "mat_ids_object": [1], "bbox": [[0, 0, 0], [1, 0.5, 0.4]],
        },
        {
            "id": "MAF_0002", "source_object": "Lamp", "slug": "s2", "dims_m": [0.2, 0.2, 1.0],
            "tris": 4, "split": False, "mat_ids_object": [], "bbox": [[2, 0, 0], [2.2, 0.2, 1]],
        },
    ]
    plan = {
        "gap_m": 0.5, "scene": "s.max", "unit_to_m": 1.0,
        "counts": {}, "excluded": [], "entries": entries,
    }
    matched = cat.match_spec(entries, [
        {
            "row": 2, "name": "Лавка", "type": "мебель", "availability": "да",
            "dims": {"l_m": 0.5, "w_m": 1.0, "h_m": 0.4}, "max_names": ["Bench"],
        },
        {
            "row": 3, "name": "Пусто", "type": "мебель", "availability": "нет",
            "dims": None, "max_names": [],
        },
    ])
    catalogue = cat.build_catalogue(plan, [], [], [], [], matched)
    by_id = {entry["id"]: entry for entry in catalogue["entries"]}
    assert by_id["MAF_0001"]["spec_candidates"] == [2]
    assert by_id["MAF_0002"]["spec_candidates"] == []
    counts = catalogue["counts"]
    assert counts["spec_rows"] == 2
    assert counts["spec_with_dims"] == 1
    assert counts["spec_rows_with_candidates"] == 1
    assert counts["spec_name_hits"] == 1
    md = cat.render_markdown(catalogue)
    assert "Specification candidates (dimension-only, not identification)" in md
    assert "2 | Лавка | 0.500 1.000 0.400 | MAF_0001" in md
    assert "Пусто" not in md


def _direct_spec_score(entry_dims, spec_dims):
    diffs = []
    horiz = [spec_dims[key] for key in ("l_m", "w_m") if spec_dims.get(key) is not None]
    if len(horiz) >= 2:
        eh = sorted((float(entry_dims[0]), float(entry_dims[1])))
        sh = sorted((float(horiz[0]), float(horiz[1])))
        diffs.append(abs(eh[0] - sh[0]))
        diffs.append(abs(eh[1] - sh[1]))
    elif len(horiz) == 1:
        side = float(horiz[0])
        diffs.append(min(abs(float(entry_dims[0]) - side), abs(float(entry_dims[1]) - side)))
    height = spec_dims.get("h_m")
    if height is not None:
        diffs.append(abs(float(entry_dims[2]) - float(height)))
    if not diffs:
        return None
    return max(diffs)


def test_match_spec_brute_force_recall():
    rng = random.Random(183)
    tol = 0.10
    entries = []
    for i in range(200):
        entries.append({
            "id": f"MAF_{i:04d}",
            "source_object": f"obj-{i}",
            "slug": f"slug-{i}",
            "dims_m": [round(rng.uniform(0.3, 4.0), 3) for _ in range(3)],
        })
    for i in range(8):
        entries[i]["dims_m"] = [1.0 + i * 0.01, 2.0, 0.5]
    spec_rows = []
    for i in range(200):
        src = entries[rng.randrange(len(entries))]
        mode = i % 5
        dims = None
        names = []
        if mode == 1:
            d = src["dims_m"]
            if rng.random() < 0.5:
                dims = {"l_m": d[1], "w_m": d[0], "h_m": d[2]}
            else:
                dims = {"l_m": d[0], "w_m": d[1], "h_m": d[2]}
            names = [src["source_object"]]
        elif mode == 2:
            dims = {
                "l_m": src["dims_m"][0] + rng.uniform(-0.05, 0.05),
                "w_m": src["dims_m"][1] + rng.uniform(-0.05, 0.05),
                "h_m": src["dims_m"][2] + rng.uniform(-0.05, 0.05),
            }
        elif mode == 3:
            dims = {
                "l_m": src["dims_m"][0] + 0.25,
                "w_m": src["dims_m"][1] + 0.25,
                "h_m": src["dims_m"][2] + 0.25,
            }
        elif mode == 4:
            if i % 2 == 0:
                dims = {"l_m": None, "w_m": None, "h_m": src["dims_m"][2]}
            else:
                side = src["dims_m"][0]
                dims = {"l_m": side, "w_m": side, "h_m": None}
        spec_rows.append({
            "row": i + 2,
            "name": f"spec-{i}",
            "type": "МАФ",
            "availability": "да",
            "dims": dims,
            "max_names": names,
        })
    spec_rows.append({
        "row": 900,
        "name": "cluster",
        "type": "МАФ",
        "availability": "да",
        "dims": {"l_m": 1.0, "w_m": 2.0, "h_m": 0.5},
        "max_names": ["obj-3"],
    })
    reported = cat.match_spec(entries, spec_rows, tol_m=tol)
    assert len(reported) == len(spec_rows)
    for spec, row in zip(spec_rows, reported):
        expect_hit = any(
            name == entry.get("source_object") or name == entry.get("slug")
            for name in spec["max_names"]
            for entry in entries
        )
        assert row["name_hit"] is expect_hit
        dims = spec["dims"]
        if not dims or all(dims.get(key) is None for key in ("l_m", "w_m", "h_m")):
            assert row["n_candidates"] == 0 and row["reason"] == "no dims"
            assert row["best"] == []
            continue
        within = []
        for entry in entries:
            score = _direct_spec_score(entry["dims_m"], dims)
            if score is not None and score <= tol + 1e-6:
                within.append((score, entry["id"]))
        within.sort()
        assert row["n_candidates"] == len(within)
        assert len(row["best"]) == min(5, len(within))
        for item, (score, eid) in zip(row["best"], within[:5]):
            assert item["id"] == eid
            assert item["score_m"] == pytest.approx(score)
            assert item["score_m"] <= tol + 1e-6
        reported_ids = {item["id"] for item in row["best"]}
        assert reported_ids == {eid for _score, eid in within[:5]}
        outside = [
            entry["id"] for entry in entries
            if entry["id"] not in {eid for _score, eid in within}
        ]
        assert not (set(item["id"] for item in row["best"]) & set(outside))
    cluster = reported[-1]
    assert cluster["n_candidates"] >= 8
    assert len(cluster["best"]) == 5
    assert cluster["name_hit"] is True
    assert [item["id"] for item in cluster["best"]] == [
        f"MAF_{i:04d}" for i in range(5)
    ]


def test_read_spec_xlsx(tmp_path, capsys):
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Ведомость"
    ws.append(["n", "type", "availability", "name", "url", "x", "max", "y", "vpm", "npm"])
    ws.append([
        1, "урны", "да",
        "Урна\nДиаметр: 400 мм\nВысота: 750 мм",
        "https://example.test/urn",
        None,
        "Urn_high\nUrn_low",
        None,
        1200,
        300,
    ])
    ws.append([2, "skip", "нет", None, None, None, None, None, None, None])
    ws.append([
        3, "прочее", "нет",
        "Без цифр",
        None, None, "Ghost", None, None, None,
    ])
    path = tmp_path / "spec.xlsx"
    wb.save(path)
    wb.close()

    rows = cat.read_spec_xlsx(path)
    assert [row["row"] for row in rows] == [2, 4]
    urn = rows[0]
    assert urn["type"] == "урны" and urn["availability"] == "да"
    assert urn["name"] == "Урна"
    assert (urn["dims"]["l_m"], urn["dims"]["w_m"], urn["dims"]["h_m"]) == pytest.approx((0.4, 0.4, 0.75))
    assert urn["url"] == "https://example.test/urn"
    assert urn["max_names"] == ["Urn_high", "Urn_low"]
    assert urn["tris_vpm"] == 1200 and urn["tris_npm"] == 300
    assert rows[1]["name"] == "Без цифр" and rows[1]["dims"] is None
    assert rows[1]["tris_vpm"] is None and rows[1]["tris_npm"] is None

    plan = {
        "gap_m": 0.5,
        "scene": "s.max",
        "unit_to_m": 1.0,
        "counts": {"maf_entries": 1},
        "excluded": [],
        "entries": [{
            "id": "MAF_0001",
            "source_object": "Urn_high",
            "source_handle": 1,
            "slug": "MAF_0001_urn",
            "tris": 10,
            "dims_m": [0.4, 0.4, 0.75],
            "bbox": [[0, 0, 0], [0.4, 0.4, 0.75]],
            "split": False,
            "mat_ids_object": [],
        }],
    }
    plan_path = tmp_path / "plan.json"
    blend_path = tmp_path / "blend.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    blend_path.write_text(json.dumps({"objects": []}), encoding="utf-8")
    out_json = tmp_path / "catalogue.json"
    out_md = tmp_path / "catalogue.md"
    spec_json = tmp_path / "spec.json"
    assert cat.main([
        "catalogue", "--plan", str(plan_path), "--built", str(tmp_path / "absent.jsonl"),
        "--blend", str(blend_path), "--out-json", str(out_json), "--out-md", str(out_md),
        "--spec", str(path), "--spec-json", str(spec_json),
    ]) == 0
    summary = json.loads(capsys.readouterr().out.strip())
    assert summary["spec_rows"] == 2 and summary["spec_with_dims"] == 1
    assert summary["spec_rows_with_candidates"] == 1 and summary["spec_name_hits"] == 1
    dumped = json.loads(spec_json.read_text(encoding="utf-8"))
    assert dumped[0]["spec_row"] == 2 and dumped[0]["best"][0]["id"] == "MAF_0001"
    assert dumped[0]["name_hit"] is True
    assert dumped[1]["reason"] == "no dims"
    catalogue = json.loads(out_json.read_text(encoding="utf-8"))
    assert catalogue["entries"][0]["spec_candidates"] == [2]
    md = out_md.read_text(encoding="utf-8")
    assert "Specification candidates (dimension-only, not identification)" in md
    assert "MAF_0001" in md and "Урна" in md
