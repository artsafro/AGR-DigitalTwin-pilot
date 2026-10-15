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
