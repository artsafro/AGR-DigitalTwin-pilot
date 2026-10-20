"""Extractor half of the FBX structure reader in a real background Blender (#339, opt-in `-m blender`).

A factory Blender process writes synthetic FBX files into the test's temp dir (never into git), then
`tools/blender/fbx_structure.py` reads them back and the converter builds the draft parts list.
"""
import json
import subprocess
from pathlib import Path

import pytest

from dt_ai.parts.model import PartsList
from dt_ai.parts.readers import fbx as reader
from twinqa.scene import find_blender

pytestmark = pytest.mark.blender

ROOT = Path(__file__).resolve().parents[2]
EXTRACTOR = ROOT / "tools" / "blender" / "fbx_structure.py"
SCHEMA = json.loads((ROOT / "schemas" / "PartsList.schema.json").read_text(encoding="utf-8"))

GENERATOR = r'''
import sys
from pathlib import Path
import bpy

out = Path(sys.argv[sys.argv.index("--") + 1])


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def box(name, location, size=1.0, mesh=None):
    if mesh is None:
        bpy.ops.mesh.primitive_cube_add(size=size, location=location)
        obj = bpy.context.active_object
        obj.name = name
        obj.data.name = name + "Mesh"
        return obj
    obj = bpy.data.objects.new(name, mesh)
    obj.location = location
    bpy.context.scene.collection.objects.link(obj)
    return obj


def collection(name):
    col = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(col)
    empty = bpy.data.objects.new(name, None)  # FBX keeps no collections: the layer travels as a parent empty
    col.objects.link(empty)
    return col, empty


def move(obj, col, empty):
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    col.objects.link(obj)
    obj.parent = empty


def export(name, **kw):
    bpy.ops.export_scene.fbx(filepath=str(out / name), use_selection=False, **kw)


# (a) two collections, three named objects, Column instanced twice (shared mesh data)
reset()
walls, walls_e = collection("Walls")
slabs, slabs_e = collection("Slabs")
move(box("Wall_North", (0, 0, 0)), walls, walls_e)
move(box("Slab_Roof", (10, 0, 0)), slabs, slabs_e)
col = box("Column", (20, 0, 0))
col.data.name = "ColumnMesh"
move(col, walls, walls_e)
move(box("Column.001", (30, 0, 0), mesh=col.data), walls, walls_e)
export("a_structured.fbx")

# (b) one multi-material cube, no structure
reset()
cube = box("Soup", (0, 0, 0))
for i in range(3):
    mat = bpy.data.materials.new(f"Mat{i}")
    cube.data.materials.append(mat)
for poly in cube.data.polygons:
    poly.material_index = poly.index // 2
export("b_soup.fbx")

# (c) two touching boxes
reset()
box("BoxA", (0, 0, 0))
box("BoxB", (1, 0, 0))
export("c_contact.fbx")

# no mesh: one empty only
reset()
bpy.context.scene.collection.objects.link(bpy.data.objects.new("Lonely", None))
export("nomesh.fbx", object_types={"EMPTY"})
print("GENERATED")
'''


@pytest.fixture(scope="module")
def blender():
    exe = find_blender()
    if not exe:
        pytest.skip("Blender not found (DT_BLENDER or the pinned installation)")
    return exe


@pytest.fixture(scope="module")
def fbx_dir(blender, tmp_path_factory):
    out = tmp_path_factory.mktemp("fbx")
    script = out / "generate.py"
    script.write_text(GENERATOR, encoding="utf-8")
    run = subprocess.run([blender, "--background", "--factory-startup", "--python-exit-code", "1", "--python",
                          str(script), "--", str(out)], capture_output=True, text=True, timeout=600,
                         encoding="utf-8", errors="replace")
    assert run.returncode == 0 and "GENERATED" in run.stdout, run.stdout[-2000:] + run.stderr[-2000:]
    data = (out / "a_structured.fbx").read_bytes()
    (out / "corrupt.fbx").write_bytes(data[: len(data) // 3])
    return out


def extract(blender, fbx: Path, out: Path):
    return subprocess.run([blender, "--background", "--factory-startup", "--python-exit-code", "1", "--python",
                           str(EXTRACTOR), "--", str(fbx), str(out)], capture_output=True, text=True, timeout=600,
                          encoding="utf-8", errors="replace")


def parts_for(blender, fbx_dir, name, tmp_path) -> tuple[dict, PartsList]:
    structure, parts_path = tmp_path / (name + ".structure.json"), tmp_path / (name + ".parts.json")
    run = extract(blender, fbx_dir / name, structure)
    assert run.returncode == 0, run.stdout[-2000:] + run.stderr[-2000:]
    facts = json.loads(structure.read_text(encoding="utf-8"))
    assert facts["sections"] == "not_in_fbx" and facts["blender"].startswith("5.")
    assert facts["units"]["scale_length"] == 1.0 and facts["units"]["fbx"]["unit_scale_factor"] is not None
    code = reader.main([str(structure), str(parts_path), "--fbx", str(fbx_dir / name), "--synthetic"])
    assert code == 0
    data = json.loads(parts_path.read_text(encoding="utf-8"))
    assert reader.schema_errors(data, SCHEMA) == []
    parts = PartsList.model_validate(data)
    assert parts.synthetic and parts.sources[0].kind == "model" and parts.sources[0].reference == name
    assert parts.sources[0].sha256 == facts["source"]["sha256"]
    print(name, json.dumps({"parts": [(p.id, p.part_class, [(s.kind, s.reference) for s in p.sources],
                                       p.triangle_budget.npm) for p in parts.parts],
                            "tier": parts.source_tier, "questions": [q.text for q in parts.questions]}))
    return facts, parts


def test_structured_fbx_gives_four_parts_with_layers_and_component(blender, fbx_dir, tmp_path):
    facts, parts = parts_for(blender, fbx_dir, "a_structured.fbx", tmp_path)
    assert parts.source_tier == "B" and len(parts.parts) == 4
    by = {p.id: {(s.kind, s.reference) for s in p.sources} for p in parts.parts}
    assert ("layer", "Walls") in by["Wall_North"] and ("layer", "Slabs") in by["Slab_Roof"]
    shared = [m for m in facts["components"] if sorted(m["objects"]) == ["Column", "Column.001"]]
    assert shared, facts["components"]
    assert ("component", shared[0]["mesh"]) in by["Column"] and ("component", shared[0]["mesh"]) in by["Column_001"]
    assert parts.questions == [] and parts.joints == []


def test_multi_material_soup_splits_into_three_parts(blender, fbx_dir, tmp_path):
    facts, parts = parts_for(blender, fbx_dir, "b_soup.fbx", tmp_path)
    assert parts.source_tier == "C" and len(parts.parts) == 3
    assert sorted(s.reference for p in parts.parts for s in p.sources if s.kind == "material_id") == \
        ["0:Mat0", "1:Mat1", "2:Mat2"]
    assert [p.triangle_budget.npm for p in parts.parts] == [4, 4, 4]


def test_touching_boxes_give_one_question(blender, fbx_dir, tmp_path):
    facts, parts = parts_for(blender, fbx_dir, "c_contact.fbx", tmp_path)
    assert len(facts["contacts"]) == 1 and parts.joints == []
    assert len(parts.questions) == 1
    assert "BoxA" in parts.questions[0].text and "BoxB" in parts.questions[0].text


@pytest.mark.parametrize("name,code", [("corrupt.fbx", 1), ("nomesh.fbx", 2)])
def test_bad_fbx_exits_nonzero_and_writes_nothing(blender, fbx_dir, tmp_path, name, code):
    out = tmp_path / "structure.json"
    run = extract(blender, fbx_dir / name, out)
    print(name, run.returncode, [line for line in run.stdout.splitlines() if "FBX_STRUCTURE_ERROR" in line])
    assert run.returncode == code
    assert "FBX_STRUCTURE_ERROR" in run.stdout
    assert not out.exists()


def test_output_equal_to_input_is_refused(blender, fbx_dir):
    fbx = fbx_dir / "c_contact.fbx"
    before = fbx.read_bytes()
    run = extract(blender, fbx, fbx)
    assert run.returncode == 1 and fbx.read_bytes() == before
