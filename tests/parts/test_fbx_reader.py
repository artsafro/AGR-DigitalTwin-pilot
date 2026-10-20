"""Converter half of the FBX structure reader: structure.json -> draft PartsList [D111, D124, D125] (#339).

All facts are synthetic dicts generated here; no FBX, no Blender.
"""
import hashlib
import itertools
import json
import math
import random
from pathlib import Path
from typing import get_args

import pytest

from dt_ai.parts.model import PartClass, PartsList
from dt_ai.parts.readers import fbx as reader
from dt_ai.parts.readers.geometry import bbox_gap, contacts

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads((ROOT / "schemas" / "PartsList.schema.json").read_text(encoding="utf-8"))
SHA = "a" * 64


def obj(name, *, tris=12, collections=(), parent=None, mesh=None, mats=None, bbox=((0, 0, 0), (1, 1, 1)),
        kind="MESH"):
    mats = mats or {0: tris}
    return {"name": name, "type": kind, "parent": parent, "collections": list(collections),
            "mesh": (mesh or name + "_mesh") if kind == "MESH" else None,
            "material_slots": [f"M{i}" for i in range(max(mats) + 1)] if kind == "MESH" else [],
            "face_material_counts": {str(k): v // 2 for k, v in mats.items()} if kind == "MESH" else {},
            "triangle_material_counts": {str(k): v for k, v in mats.items()} if kind == "MESH" else {},
            "triangles": tris if kind == "MESH" else 0, "polygons": tris // 2 if kind == "MESH" else 0,
            "bbox": {"min": list(bbox[0]), "max": list(bbox[1])}, "connected_components": 1}


def facts(objects, *, components=(), contact_pairs=(), name="model.fbx", sha=SHA):
    return {"format": "fbx_structure/1", "source": {"name": name, "path": "C:/x/" + name, "sha256": sha, "bytes": 10},
            "blender": "5.1.2", "units": {"system": "METRIC", "scale_length": 1.0, "length_unit": "METERS"},
            "sections": "not_in_fbx", "contact_tolerance_m": 0.002, "objects": objects,
            "components": [{"mesh": m, "objects": list(o)} for m, o in components],
            "contacts": [{"a": a, "b": b, "gap_m": g} for a, b, g in contact_pairs]}


def scene_a():
    """Three named objects in two collections; Column is instanced twice (shared mesh) -> 4 objects."""
    far = lambda i: ((10 * i, 0, 0), (10 * i + 1, 1, 1))  # noqa: E731 - no contacts in this scene
    return facts([obj("Wall_North", collections=["Walls"], bbox=far(0)),
                  obj("Slab_Roof", collections=["Slabs"], bbox=far(1)),
                  obj("Column", collections=["Walls"], mesh="ColumnMesh", bbox=far(2)),
                  obj("Column.001", collections=["Walls"], mesh="ColumnMesh", bbox=far(3))],
                 components=[("ColumnMesh", ["Column", "Column.001"])])


def scene_b():
    return facts([obj("Soup", tris=36, mats={0: 12, 1: 12, 2: 12})])


def scene_c():
    return facts([obj("BoxA", bbox=((0, 0, 0), (1, 1, 1))), obj("BoxB", bbox=((1, 0, 0), (2, 1, 1)))],
                 contact_pairs=[("BoxA", "BoxB", 0.0)])


def schema_ok(parts: PartsList):
    data = json.loads(parts.model_dump_json())
    assert reader.schema_errors(data, SCHEMA) == []
    PartsList.model_validate(data)
    return data


def kinds(part):
    return {(s.kind, s.reference) for s in part.sources}


# ---- acceptance (a), (b), (c) ----

def test_a_named_objects_in_collections_with_instance_give_four_parts_tier_b():
    parts = reader.convert(scene_a(), synthetic=True)
    schema_ok(parts)
    assert parts.status == "draft" and parts.gate1 is None and parts.source_tier == "B"
    assert len(parts.parts) == 4
    by = {p.id: p for p in parts.parts}
    assert ("layer", "Walls") in kinds(by["Wall_North"]) and ("layer", "Slabs") in kinds(by["Slab_Roof"])
    assert ("component", "ColumnMesh") in kinds(by["Column"])
    assert ("component", "ColumnMesh") in kinds(by["Column_001"])
    assert ("component", "ColumnMesh") not in kinds(by["Wall_North"])
    assert by["Wall_North"].part_class == "wall" and by["Slab_Roof"].part_class == "slab"
    assert by["Column"].part_class == "other"
    assert all(p.operation == "keep" and p.legend_item is None for p in parts.parts)
    assert parts.triangle_budget.npm == parts.triangle_budget.vpm == 48
    assert all(p.triangle_budget.npm == p.triangle_budget.vpm == 12 for p in parts.parts)
    assert parts.joints == [] and parts.questions == []
    assert parts.synthetic is True
    src = parts.sources[0]
    assert (src.kind, src.reference, src.sha256) == ("model", "model.fbx", SHA)


def test_b_single_object_three_material_ids_splits_by_material_tier_c():
    parts = reader.convert(scene_b(), synthetic=True)
    schema_ok(parts)
    assert parts.source_tier == "C" and len(parts.parts) == 3
    refs = sorted(s.reference for p in parts.parts for s in p.sources if s.kind == "material_id")
    assert refs == ["0:M0", "1:M1", "2:M2"]
    assert all(("object", "Soup") in kinds(p) for p in parts.parts)
    assert [p.triangle_budget.npm for p in parts.parts] == [12, 12, 12]
    assert parts.triangle_budget.npm == 36


def test_c_contact_becomes_one_question_naming_both_never_a_joint():
    parts = reader.convert(scene_c(), synthetic=True)
    schema_ok(parts)
    assert parts.joints == []
    assert len(parts.questions) == 1
    text = parts.questions[0].text
    assert "BoxA" in text and "BoxB" in text and "weld or embed" in text
    assert parts.questions[0].answer is None


def test_single_object_single_material_is_one_part_tier_c():
    parts = reader.convert(facts([obj("Soup")]), synthetic=False)
    schema_ok(parts)
    assert parts.source_tier == "C" and len(parts.parts) == 1 and parts.synthetic is False


def test_one_object_under_layer_empty_is_structure_not_split():
    data = facts([obj("Group", kind="EMPTY"), obj("Box", parent="Group", tris=24, mats={0: 12, 1: 12})])
    parts = reader.convert(data, synthetic=True)
    schema_ok(parts)
    assert parts.source_tier == "B" and len(parts.parts) == 1
    assert ("layer", "Group") in kinds(parts.parts[0])


def test_name_rule_table():
    assert reader.part_class_for("Wall_North") == "wall"
    assert reader.part_class_for("glass_panel_3") == "glazing"
    assert reader.part_class_for("Window.004") == "window"
    assert reader.part_class_for("Стена_1") == "wall"
    assert reader.part_class_for("Cube.001") == "other"
    assert reader.part_class_for("Swallow") == "other"  # whole tokens only, "wall" inside a word is not a wall
    for _pattern, part_class in reader.NAME_RULES:
        assert part_class in get_args(PartClass)


def test_sanitised_collision_is_disambiguated():
    parts = reader.convert(facts([obj("A-1", bbox=((0, 0, 0), (1, 1, 1))), obj("A_1", bbox=((5, 0, 0), (6, 1, 1)))]),
                           synthetic=True)
    ids = [p.id for p in parts.parts]
    assert len(set(ids)) == 2 and "A_1" in ids
    schema_ok(parts)


def test_cyrillic_and_digit_names_get_valid_ids():
    data = facts([obj("Стена", bbox=((0, 0, 0), (1, 1, 1))), obj("1 этаж", bbox=((5, 0, 0), (6, 1, 1)))])
    schema_ok(reader.convert(data, synthetic=True))


# ---- CLI ----

def test_cli_writes_valid_parts_list(tmp_path):
    src, out = tmp_path / "structure.json", tmp_path / "parts.json"
    src.write_text(json.dumps(scene_a()), encoding="utf-8")
    assert reader.main([str(src), str(out), "--synthetic", "--object-id", "SYNTH_FBX"]) == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert reader.schema_errors(data, SCHEMA) == []
    assert PartsList.model_validate(data).object_id == "SYNTH_FBX"


def test_cli_fbx_sha_match_passes(tmp_path):
    fbx = tmp_path / "model.fbx"
    fbx.write_bytes(b"synthetic fbx bytes")
    sha = hashlib.sha256(fbx.read_bytes()).hexdigest()
    src, out = tmp_path / "structure.json", tmp_path / "parts.json"
    src.write_text(json.dumps(facts([obj("Soup")], sha=sha)), encoding="utf-8")
    assert reader.main([str(src), str(out), "--fbx", str(fbx), "--synthetic"]) == 0
    assert out.exists()


# ---- fail-closed: non-zero exit, no output file ----

def _fail(tmp_path, content, *extra):
    src, out = tmp_path / "structure.json", tmp_path / "parts.json"
    if content is not None:
        src.write_bytes(content if isinstance(content, bytes) else json.dumps(content).encode())
    code = reader.main([str(src), str(out), "--synthetic", *extra])
    assert code != 0
    assert not out.exists()
    return code


def test_fail_missing_file(tmp_path):
    _fail(tmp_path, None)


def test_fail_empty_file(tmp_path):
    _fail(tmp_path, b"")


def test_fail_truncated_json(tmp_path):
    _fail(tmp_path, json.dumps(scene_a()).encode()[:200])


def test_fail_non_json(tmp_path):
    _fail(tmp_path, b"Kaydara FBX Binary  \x00\x1a\x00")


def test_fail_non_object_json(tmp_path):
    _fail(tmp_path, [1, 2, 3])


def test_fail_zero_mesh_objects(tmp_path):
    _fail(tmp_path, facts([obj("Root", kind="EMPTY")]))
    _fail(tmp_path, facts([]))


def test_fail_only_zero_triangle_object(tmp_path):
    _fail(tmp_path, facts([obj("Empty", tris=0, mats={0: 0})]))


def test_fail_duplicate_ids_that_cannot_be_disambiguated(tmp_path):
    _fail(tmp_path, facts([obj("Wall"), obj("Wall", bbox=((5, 0, 0), (6, 1, 1)))]))


def test_fail_sha_mismatch_with_named_fbx(tmp_path):
    fbx = tmp_path / "model.fbx"
    fbx.write_bytes(b"other bytes")
    _fail(tmp_path, facts([obj("Soup")]), "--fbx", str(fbx))


def test_fail_fbx_name_mismatch(tmp_path):
    fbx = tmp_path / "other.fbx"
    fbx.write_bytes(b"x")
    sha = hashlib.sha256(b"x").hexdigest()
    _fail(tmp_path, facts([obj("Soup")], sha=sha), "--fbx", str(fbx))


def test_fail_missing_fbx(tmp_path):
    _fail(tmp_path, facts([obj("Soup")]), "--fbx", str(tmp_path / "model.fbx"))


@pytest.mark.parametrize("mutate", [
    lambda d: d.update(format="fbx_readback"),
    lambda d: d.update(sections="present"),
    lambda d: d["source"].update(sha256="xyz"),
    lambda d: d["objects"][0].update(triangles=-1),
    lambda d: d["objects"][0].update(triangles=True),
    lambda d: d["objects"][0]["bbox"].update(min=[0, 0, "nan"]),
    lambda d: d["objects"][0]["bbox"].update(min=[2, 2, 2]),
    lambda d: d["objects"][0].update(triangle_material_counts={"0": 5}),
    lambda d: d.update(error="import failed"),
    lambda d: d["contacts"].append({"a": "Soup", "b": "Ghost", "gap_m": 0.0}),
    lambda d: d["components"].append({"mesh": "X", "objects": ["Soup", "Ghost"]}),
])
def test_fail_malformed_facts(tmp_path, mutate):
    data = facts([obj("Soup")])
    mutate(data)
    _fail(tmp_path, data)


def test_fail_nonfinite_literal(tmp_path):
    text = json.dumps(facts([obj("Soup")])).replace('"bytes": 10', '"bytes": NaN')
    _fail(tmp_path, text.encode())


def test_fail_output_is_input(tmp_path):
    src = tmp_path / "structure.json"
    src.write_text(json.dumps(scene_a()), encoding="utf-8")
    before = src.read_bytes()
    assert reader.main([str(src), str(src), "--synthetic"]) != 0
    assert src.read_bytes() == before


def test_schema_validator_rejects_bad_instances():
    good = json.loads(reader.convert(scene_a(), synthetic=True).model_dump_json())
    for mutate in (lambda d: d.update(extra=1), lambda d: d.pop("parts"),
                   lambda d: d["parts"][0].update(id="1bad"), lambda d: d.update(source_tier="D"),
                   lambda d: d["triangle_budget"].update(npm=-1), lambda d: d.update(parts=[])):
        bad = json.loads(json.dumps(good))
        mutate(bad)
        assert reader.schema_errors(bad, SCHEMA), mutate
    with pytest.raises(ValueError):
        reader.schema_errors({}, {"type": "object", "unevaluatedProperties": False})


# ---- invariant probes ----

def test_probe_contacts_within_2mm_brute_force():
    """bbox gap <= 2 mm is a contact (inclusive), > 2 mm is not; checked against a brute-force axis gap."""
    rng = random.Random(339)
    n = 0
    for _ in range(500):
        boxes = {}
        for i in range(5):
            lo = [rng.choice([0.0, 1.0, 1.001, 1.002, 1.0021, 1.5]) + rng.randint(0, 2) for _ in range(3)]
            size = [rng.choice([0.5, 1.0]) for _ in range(3)]
            boxes[f"B{i}"] = (lo, [a + s for a, s in zip(lo, size)])
        got = {(c["a"], c["b"]) for c in contacts(boxes, 0.002)}
        for a, b in itertools.combinations(sorted(boxes), 2):
            (amin, amax), (bmin, bmax) = boxes[a], boxes[b]
            gap = math.sqrt(sum(max(0.0, bmin[k] - amax[k], amin[k] - bmax[k]) ** 2 for k in range(3)))
            assert ((a, b) in got) == (gap <= 0.002 + 1e-9), (a, b, gap)
            n += 1
    assert n == 5000
    assert bbox_gap(([0, 0, 0], [1, 1, 1]), ([1.002, 0, 0], [2, 1, 1])) == pytest.approx(0.002)


UNIT = ([0, 0, 0], [1, 1, 1])


@pytest.mark.parametrize("offset,gap,touch", [
    ((0, 0, 0), 0.0, True),                        # face-touching
    ((0.002, 0, 0), 0.002, True),                  # axial, exactly the tolerance
    ((0.0021, 0, 0), 0.0021, False),               # axial, just over
    ((0.0012, 0.0016, 0), 0.002, True),            # 2-axis, Euclidean exactly the tolerance
    ((0.0015, 0.0015, 0), 0.0015 * math.sqrt(2), False),   # 2-axis, each axis < 2 mm, diagonal > 2 mm
    ((0.001, 0.001, 0.001), 0.001 * math.sqrt(3), True),   # 3-axis, 1.73 mm
    ((0.002, 0.002, 0.002), 0.002 * math.sqrt(3), False),  # 3-axis, 3.46 mm (review round 1)
    ((-0.5, 0.0019, 0), 0.0019, True),             # overlap on x, gap on y only
])
def test_bbox_gap_is_euclidean_norm_of_axis_gaps(offset, gap, touch):
    other = ([1 + o if o >= 0 else o for o in offset], [2 + o if o >= 0 else 1 + o for o in offset])
    assert bbox_gap(UNIT, other) == pytest.approx(gap, abs=1e-12)
    assert bool(contacts({"A": UNIT, "B": other}, 0.002)) is touch


def test_diagonal_boxes_3_46mm_apart_give_no_contact_and_no_question():
    """Review round 1: [0,0,0]..[1,1,1] and [1.002]*3..[2]*3 are 3.4641 mm apart -> 0 contacts, 0 questions."""
    f = facts([obj("BoxA", bbox=UNIT), obj("BoxB", bbox=((1.002, 1.002, 1.002), (2, 2, 2)))])
    parts = reader.convert(f, synthetic=True)
    assert parts.questions == [] and parts.joints == []
    with pytest.raises(reader.StructureError):  # an extractor claiming the contact disagrees with the boxes
        reader.convert(facts(f["objects"], contact_pairs=[("BoxA", "BoxB", 0.002)]), synthetic=True)


# ---- publication never touches the input or unrelated files (review round 1) ----

def test_input_named_like_output_partial_is_preserved(tmp_path):
    src, out = tmp_path / "parts.json.partial", tmp_path / "parts.json"
    src.write_text(json.dumps(scene_a()), encoding="utf-8")
    before = src.read_bytes()
    assert reader.main([str(src), str(out), "--synthetic"]) == 0
    assert src.read_bytes() == before
    assert PartsList.model_validate_json(out.read_text(encoding="utf-8")).parts
    assert sorted(p.name for p in tmp_path.iterdir()) == ["parts.json", "parts.json.partial"]


def test_unrelated_partial_sentinel_is_preserved(tmp_path):
    src, out = tmp_path / "structure.json", tmp_path / "parts.json"
    src.write_text(json.dumps(scene_a()), encoding="utf-8")
    sentinel = tmp_path / "parts.json.partial"
    sentinel.write_bytes(b"sentinel")
    assert reader.main([str(src), str(out), "--synthetic"]) == 0
    assert sentinel.read_bytes() == b"sentinel"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["parts.json", "parts.json.partial", "structure.json"]


def test_normal_publication_leaves_no_temporary_files(tmp_path):
    src, out = tmp_path / "structure.json", tmp_path / "parts.json"
    src.write_text(json.dumps(scene_a()), encoding="utf-8")
    out.write_bytes(b"old")
    assert reader.main([str(src), str(out), "--synthetic"]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["status"] == "draft"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["parts.json", "structure.json"]


def test_failed_conversion_leaves_no_temporary_files(tmp_path):
    src, out = tmp_path / "structure.json", tmp_path / "parts.json"
    src.write_text(json.dumps(facts([])), encoding="utf-8")
    assert reader.main([str(src), str(out)]) != 0
    assert sorted(p.name for p in tmp_path.iterdir()) == ["structure.json"]


def test_probe_every_conversion_is_valid_and_budget_adds_up():
    """Random structures: ids unique, both validators pass, total = sum of parts = sum of object triangles."""
    rng = random.Random(1339)
    for trial in range(200):
        names = rng.sample(["Wall", "wall", "Slab-1", "Slab_1", "Окно", "Glass", "Box.001", "Box_001", "9x", "A"],
                           rng.randint(1, 6))
        objects = []
        for i, name in enumerate(names):
            k = rng.randint(1, 3)
            mats = {m: rng.randint(1, 20) * 2 for m in range(k)}
            objects.append(obj(name, tris=sum(mats.values()), mats=mats,
                               collections=[rng.choice(["L1", "L2"])] if rng.random() < .5 else [],
                               bbox=((3 * i, 0, 0), (3 * i + 1, 1, 1))))
        data = facts(objects)
        try:
            parts = reader.convert(data, synthetic=True)
        except reader.StructureError as exc:
            assert "duplicate" in str(exc).lower(), exc
            continue
        schema_ok(parts)
        total = sum(o["triangles"] for o in objects)
        assert parts.triangle_budget.npm == total == sum(p.triangle_budget.npm for p in parts.parts)
        assert len({p.id for p in parts.parts}) == len(parts.parts)
        assert parts.joints == []
