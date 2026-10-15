"""Flora checks (#191) through the scene findings seam: fixed readbacks (RED / GREEN) plus a real
background-Blender roundtrip for the material map facts (skipped without Blender)."""
import random
import subprocess

import pytest

from test_validator import PROFILES
from twinqa.scene import find_blender, readback, scene_findings

SRC = "C:/x/SM_Test_Ground.fbx"


def mesh(name, tris=100, lo=(0, 0, 0), hi=(1, 1, 1), materials=()):
    return {"name": name, "triangles": tris, "polygon_degrees": {"3": tris}, "rotation_euler_deg": [0, 0, 0],
            "scale": [1, 1, 1], "uv_channels": 1, "mirrored_uv_triangles": 0, "udim_tiles": [1001],
            "location": [0, 0, 0], "bounds_m": [list(lo), list(hi)], "materials": list(materials)}


def plant(name, height, crown, tris=100, materials=("M_Test_Flora_1",)):
    """A plant whose bbox height includes the 10 cm sunk into the Ground."""
    return mesh(name, tris, lo=(-crown / 2, -crown / 2, -0.10), hi=(crown / 2, crown / 2, height),
                materials=materials)


def mat(name="M_Test_Flora_1", **sockets):
    return {"name": name, "maps": [{"image": img, "output": "Color", "socket": s.replace("_", " ")}
                                   for s, img in sockets.items()]}


GOOD_MAT = mat(Base_Color="T_Test_Flora_d_1", Alpha="T_Test_Flora_o_1")


def rb(*meshes, materials=(GOOD_MAT,)):
    return {"source": SRC, "readback_ok": True, "meshes": list(meshes), "other_objects": [], "images": [],
            "materials": list(materials)}


def named(found, stage, prefix):
    return {f.name: f.status for f in found.get(stage, []) if f.name.startswith(prefix)}


SCHEDULE = {"SM_Test_Flora_Acer_01": {"height_m": 5.0, "crown_m": 3.0}}


# --- Dimensions vs schedule (V015) ---

def test_dimensions_green_inside_20_percent_after_sinking():
    found = scene_findings(rb(plant("SM_Test_Flora_Acer_01", 5.9, 2.5)), "vpm", "ground", PROFILES.vpm,
                           flora_schedule=SCHEDULE)
    assert named(found, "V015", "Flora dimensions") == {"Flora dimensions: SM_Test_Flora_Acer_01": "pass"}


@pytest.mark.parametrize("height,crown", [(6.1, 3.0), (3.9, 3.0), (5.0, 3.7), (5.0, 2.3)])
def test_dimensions_red_beyond_20_percent(height, crown):
    found = scene_findings(rb(plant("SM_Test_Flora_Acer_01", height, crown)), "npm", "ground", PROFILES.npm,
                           flora_schedule=SCHEDULE)
    assert named(found, "V015", "Flora dimensions")["Flora dimensions: SM_Test_Flora_Acer_01"] == "fail"


def test_dimensions_sinking_is_subtracted():
    # bbox 6.05 m tall: 5.95 m above the Ground passes (+19 %); without the 10 cm it would be +21 %.
    m = mesh("SM_Test_Flora_Acer_01", lo=(-1.5, -1.5, -0.10), hi=(1.5, 1.5, 5.95))
    found = scene_findings(rb(m), "vpm", "ground", PROFILES.vpm, flora_schedule=SCHEDULE)
    assert named(found, "V015", "Flora")["Flora dimensions: SM_Test_Flora_Acer_01"] == "pass"
    m = mesh("SM_Test_Flora_Acer_01", lo=(-1.5, -1.5, -0.10), hi=(1.5, 1.5, 4.0 - 0.10 - 0.01))
    found = scene_findings(rb(m), "vpm", "ground", PROFILES.vpm, flora_schedule=SCHEDULE)
    assert named(found, "V015", "Flora")["Flora dimensions: SM_Test_Flora_Acer_01"] == "fail"


def test_dimensions_blender_duplicate_suffix_and_missing_plant():
    schedule = {**SCHEDULE, "SM_Test_Flora_Tilia_02": {"height_m": 8, "crown_m": 4}}
    found = scene_findings(rb(plant("SM_Test_Flora_Acer_01.001", 5, 3)), "vpm", "ground", PROFILES.vpm,
                           flora_schedule=schedule)
    assert named(found, "V015", "Flora") == {"Flora dimensions: SM_Test_Flora_Acer_01": "pass",
                                             "Flora dimensions: SM_Test_Flora_Tilia_02": "review"}


@pytest.mark.parametrize("alias_first", [True, False])
def test_dimensions_exact_name_wins_over_suffix_alias(alias_first):
    # review round 1, P1: alias height 5 must not mask the exact scheduled mesh at height 9 (+80 %)
    alias, exact = plant("SM_Test_Flora_Acer_01.001", 5, 3), plant("SM_Test_Flora_Acer_01", 9, 3)
    meshes = (alias, exact) if alias_first else (exact, alias)
    found = scene_findings(rb(*meshes), "vpm", "ground", PROFILES.vpm, flora_schedule=SCHEDULE)
    assert named(found, "V015", "Flora") == {"Flora dimensions: SM_Test_Flora_Acer_01": "fail"}
    f = next(x for x in found["V015"] if x.name == "Flora dimensions: SM_Test_Flora_Acer_01")
    assert "+80.0 %" in f.observed


def test_dimensions_ambiguous_suffix_aliases_are_review():
    found = scene_findings(rb(plant("SM_Test_Flora_Acer_01.001", 5, 3), plant("SM_Test_Flora_Acer_01.002", 9, 3)),
                           "vpm", "ground", PROFILES.vpm, flora_schedule=SCHEDULE)
    assert named(found, "V015", "Flora") == {"Flora dimensions: SM_Test_Flora_Acer_01": "review"}
    f = next(x for x in found["V015"] if x.name == "Flora dimensions: SM_Test_Flora_Acer_01")
    assert ".001" in f.observed and ".002" in f.observed


@pytest.mark.parametrize("entry", [{"height_m": 0, "crown_m": 3}, {"height_m": 5}, {"height_m": "5", "crown_m": 3}])
def test_dimensions_invalid_schedule_entry_is_review(entry):
    found = scene_findings(rb(plant("SM_Test_Flora_Acer_01", 5, 3)), "vpm", "ground", PROFILES.vpm,
                           flora_schedule={"SM_Test_Flora_Acer_01": entry})
    assert named(found, "V015", "Flora")["Flora dimensions: SM_Test_Flora_Acer_01"] == "review"


def test_dimensions_without_schedule_not_run_only_when_flora_present():
    found = scene_findings(rb(plant("SM_Test_Flora", 5, 3)), "vpm", "ground", PROFILES.vpm)
    assert named(found, "V015", "Flora") == {"Flora dimensions": "not_run"}
    found = scene_findings(rb(mesh("SM_Test_Ground")), "vpm", "ground", PROFILES.vpm)
    assert "V015" not in found


def test_flora_checks_skip_oks_and_light():
    for role in ("oks", "light"):
        found = scene_findings(rb(plant("SM_Test_Flora_Acer_01", 9, 9)), "npm", role, PROFILES.npm,
                               flora_schedule=SCHEDULE)
        assert not any(f.name.startswith("Flora") for fs in found.values() for f in fs)


def test_probe_dimension_boundary_brute_force():
    """Invariant: fail iff |measured / expected - 1| > 20 % for height (minus 10 cm) or crown."""
    rng, checked = random.Random(191), 0
    for _ in range(500):
        eh, ed = rng.uniform(0.3, 25), rng.uniform(0.3, 15)
        fh, fd = rng.choice([rng.uniform(0.5, 1.5), 0.8, 1.2, 0.8001, 1.1999, 0.7999, 1.2001]), rng.uniform(0.6, 1.4)
        m = plant("SM_Test_Flora_P", eh * fh, ed * fd)
        got = scene_findings(rb(m), "vpm", "ground", PROFILES.vpm,
                             flora_schedule={"SM_Test_Flora_P": {"height_m": eh, "crown_m": ed}})
        expect = "fail" if abs(fh - 1) > 0.2 + 1e-12 or abs(fd - 1) > 0.2 + 1e-12 else "pass"  # exact 20 % is inside
        assert named(got, "V015", "Flora")["Flora dimensions: SM_Test_Flora_P"] == expect, (eh, ed, fh, fd)
        checked += 1
    assert checked == 500


@pytest.mark.parametrize("factor,status", [(0.8, "pass"), (1.2, "pass"), (0.79, "fail"), (1.21, "fail")])
def test_dimensions_exact_20_percent_is_inside(factor, status):
    found = scene_findings(rb(plant("SM_Test_Flora_Acer_01", 5 * factor, 3)), "vpm", "ground", PROFILES.vpm,
                           flora_schedule=SCHEDULE)
    assert named(found, "V015", "Flora")["Flora dimensions: SM_Test_Flora_Acer_01"] == status


# --- Maps: diffuse + opacity only (V005, NPM) ---

def test_maps_green_diffuse_plus_opacity():
    found = scene_findings(rb(plant("SM_Test_Flora", 5, 3)), "npm", "ground", PROFILES.npm)
    assert named(found, "V005", "Flora maps") == {"Flora maps: M_Test_Flora_1": "pass"}


def test_maps_missing_opacity_is_review_pointing_to_open_conflict_18():
    found = scene_findings(rb(plant("SM_Test_Flora", 5, 3), materials=[mat(Base_Color="T_Test_Flora_d_1")]),
                           "npm", "ground", PROFILES.npm)
    f = next(f for f in found["V005"] if f.name == "Flora maps: M_Test_Flora_1")
    assert (f.status, f.conflicts, "no separate opacity map" in f.observed) == ("review", [18], True)


@pytest.mark.parametrize("material", [
    mat(Base_Color="T_Test_Flora_d_1", Alpha="T_Test_Flora_d_1"),                        # diffuse alpha channel
    mat(Base_Color="T_Test_Flora_d_1", Alpha="T_Test_Flora_o_1", Normal="T_Test_Flora_n_1"),  # extra map
    mat(Alpha="T_Test_Flora_o_1"),                                                       # no diffuse
    mat(Base_Color="T_Test_Flora_d_1", Alpha="T_Test_Flora_o_1", Roughness="T_r"),
])
def test_maps_red(material):
    found = scene_findings(rb(plant("SM_Test_Flora", 5, 3), materials=[material]), "npm", "ground", PROFILES.npm)
    assert named(found, "V005", "Flora maps") == {"Flora maps: M_Test_Flora_1": "fail"}


def test_maps_material_found_by_mesh_slot_and_ground_material_ignored():
    ground_mat = mat("M_Test_Ground_1", Base_Color="T_g", Normal="T_n")
    leaf = mat("M_Leaves", Base_Color="T_d", Alpha="T_o", Specular_IOR_Level="T_s")  # Flora mesh, no token
    found = scene_findings(rb(plant("SM_Test_Flora", 5, 3, materials=["M_Leaves"]),
                              mesh("SM_Test_Ground", materials=["M_Test_Ground_1"]),
                              materials=[ground_mat, leaf]), "npm", "ground", PROFILES.npm)
    assert named(found, "V005", "Flora maps") == {"Flora maps: M_Leaves": "fail"}


def test_maps_not_run_on_old_readback_and_vpm_not_checked():
    old = rb(plant("SM_Test_Flora", 5, 3))
    del old["materials"]
    assert named(scene_findings(old, "npm", "ground", PROFILES.npm), "V005", "Flora") == {"Flora maps": "not_run"}
    found = scene_findings(rb(plant("SM_Test_Flora", 5, 3), materials=[mat(Base_Color="d")]), "vpm", "ground",
                           PROFILES.vpm)
    assert "V005" not in found


def test_maps_flora_mesh_without_material_fails():
    found = scene_findings(rb(plant("SM_Test_Flora", 5, 3, materials=()), materials=[]), "npm", "ground",
                           PROFILES.npm)
    assert named(found, "V005", "Flora maps") == {"Flora maps: SM_Test_Flora": "fail"}


@pytest.mark.parametrize("bare_slots", [[], [None], [""], ["M_Test_Flora_1", None]])
@pytest.mark.parametrize("bare_first", [False, True])
def test_maps_good_neighbour_does_not_hide_unmaterialed_flora_mesh(bare_slots, bare_first):
    # review round 1, P1: coverage is per Flora mesh, not "any Flora material exists"
    good = plant("SM_Test_Flora_Good", 5, 3)
    bare = plant("SM_Test_Flora_Bare", 5, 3, materials=bare_slots)
    meshes = (bare, good) if bare_first else (good, bare)
    found = scene_findings(rb(*meshes), "npm", "ground", PROFILES.npm)
    assert named(found, "V005", "Flora maps") == {"Flora maps: M_Test_Flora_1": "pass",
                                                  "Flora maps: SM_Test_Flora_Bare": "fail"}
    bare_f = next(f for f in found["V005"] if f.name == "Flora maps: SM_Test_Flora_Bare")
    assert "SM_Test_Flora_Bare" in bare_f.observed and "no material" in bare_f.observed


@pytest.mark.parametrize("order", [0, 1, 2])
def test_mixed_scene_bare_mesh_alias_and_exact_any_order(order):
    # combined: bare Flora mesh + good neighbour + .001 alias of a scheduled exact mesh, permuted
    items = [plant("SM_Test_Flora_Acer_01.001", 5, 3), plant("SM_Test_Flora_Acer_01", 9, 3),
             plant("SM_Test_Flora_Bare", 5, 3, materials=[])]
    items = items[order:] + items[:order]
    found = scene_findings(rb(*items), "npm", "ground", PROFILES.npm, flora_schedule=SCHEDULE)
    assert named(found, "V015", "Flora") == {"Flora dimensions: SM_Test_Flora_Acer_01": "fail"}
    assert named(found, "V005", "Flora maps") == {"Flora maps: M_Test_Flora_1": "pass",
                                                  "Flora maps: SM_Test_Flora_Bare": "fail"}


def test_probe_coverage_and_exact_name_any_order_brute_force():
    """Invariants: every bare Flora mesh gets its own fail, whatever the neighbours/order; the exact
    scheduled mesh is always the one measured when present; a sole alias is used otherwise."""
    rng, cases = random.Random(191), 0
    for _ in range(400):
        meshes, bare = [], set()
        for i in range(rng.randint(1, 5)):
            nm = f"SM_Test_Flora_P{i}"
            slots = rng.choice([["M_Test_Flora_1"], [], [None], ["M_Test_Flora_1", None]])
            if not all(slots) or not slots:
                bare.add(nm)
            meshes.append(plant(nm, 5, 3, materials=slots))
        exact_h, alias_h = rng.choice([None, 5.0, 9.0]), rng.choice([None, 5.0, 9.0])
        if exact_h:
            meshes.append(plant("SM_Test_Flora_Acer_01", exact_h, 3))
        if alias_h:
            meshes.append(plant("SM_Test_Flora_Acer_01.001", alias_h, 3))
        rng.shuffle(meshes)
        found = scene_findings(rb(*meshes), "npm", "ground", PROFILES.npm, flora_schedule=SCHEDULE)
        maps = named(found, "V005", "Flora maps")
        assert {k for k, v in maps.items() if v == "fail"} == {f"Flora maps: {b}" for b in bare}
        measured = exact_h or alias_h
        want = "review" if measured is None else "pass" if measured == 5.0 else "fail"
        assert named(found, "V015", "Flora") == {"Flora dimensions: SM_Test_Flora_Acer_01": want}
        cases += 1
    assert cases == 400


# --- Budget: Flora share 70 000, Ground total 180 000 (V003, NPM) ---

def test_budget_green_and_report_numbers():
    found = scene_findings(rb(plant("SM_Test_Flora", 5, 3, tris=70_000), mesh("SM_Test_Ground", tris=110_000)),
                           "npm", "ground", PROFILES.npm)
    share = next(f for f in found["V003"] if f.name == "Flora triangle share")
    assert share.status == "pass"
    assert "Flora 70000 of share 70000" in share.observed and "Ground total 180000 of 180000" in share.observed
    assert {f.name: f.status for f in found["V003"]}["triangle count"] == "pass"


def test_budget_red_over_share_is_review_ground_over_limit_fails_triangle_count():
    found = scene_findings(rb(plant("SM_Test_Flora", 5, 3, tris=70_001), mesh("SM_Test_Ground", tris=110_000),
                              mesh("UCX_SM_Test_Ground_001", tris=9_999)), "npm", "ground", PROFILES.npm)
    st = {f.name: f for f in found["V003"]}
    assert st["Flora triangle share"].status == "review"
    assert "Ground total 180001 of 180000 (over)" in st["Flora triangle share"].observed  # UCX excluded
    assert st["triangle count"].status == "fail"


def test_budget_custom_share_and_vpm_not_reported():
    found = scene_findings(rb(plant("SM_Test_Flora", 5, 3, tris=50_000)), "npm", "ground", PROFILES.npm,
                           flora_share=40_000)
    assert {f.name: f.status for f in found["V003"]}["Flora triangle share"] == "review"
    found = scene_findings(rb(plant("SM_Test_Flora", 5, 3, tris=900_000)), "vpm", "ground", PROFILES.vpm)
    assert "Flora triangle share" not in {f.name for f in found["V003"]}


def test_probe_budget_share_brute_force():
    """Invariant: share finding is review iff Flora triangles > share; Ground total = all non-UCX meshes."""
    rng = random.Random(1910)
    for _ in range(300):
        share = rng.randint(1, 100_000)
        flora = [rng.randint(0, 40_000) for _ in range(rng.randint(0, 4))]
        other = [rng.randint(0, 60_000) for _ in range(rng.randint(1, 3))]
        meshes = [plant(f"SM_Test_Flora_{i}", 5, 3, tris=t) for i, t in enumerate(flora)]
        meshes += [mesh(f"SM_Test_Ground_{i}", tris=t) for i, t in enumerate(other)]
        found = scene_findings(rb(*meshes), "npm", "ground", PROFILES.npm, flora_share=share)
        f = next(f for f in found["V003"] if f.name == "Flora triangle share")
        assert f.status == ("review" if sum(flora) > share else "pass")
        assert f"Flora {sum(flora)} of share {share}; Ground total {sum(flora) + sum(other)} of 180000" in f.observed


# --- Real Blender roundtrip: material map facts through tools/blender/fbx_readback.py ---

BLENDER = find_blender()
MAKE_FLORA = """
import bpy, sys
out, variant = sys.argv[sys.argv.index('--') + 1], sys.argv[-1]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.mesh.primitive_plane_add(size=3, location=(0, 0, 0), rotation=(1.5707963, 0, 0))
o = bpy.context.object; o.name = 'SM_Test_Flora'
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
o.data.transform(__import__('mathutils').Matrix.Translation((0, 0, 1.4)))
bpy.ops.object.modifier_add(type='TRIANGULATE'); bpy.ops.object.modifier_apply(modifier='Triangulate')
def img(name):
    i = bpy.data.images.new(name, 8, 8)
    i.filepath_raw = out[:-4] + '_' + name + '.png'; i.file_format = 'PNG'; i.save(); i.pack(); return i
m = bpy.data.materials.new('M_Test_Flora_1'); m.use_nodes = True
nt = m.node_tree; bsdf = nt.nodes['Principled BSDF']
d = nt.nodes.new('ShaderNodeTexImage'); d.image = img('T_Test_Flora_d_1')
nt.links.new(d.outputs['Color'], bsdf.inputs['Base Color'])
if variant == 'good':
    a = nt.nodes.new('ShaderNodeTexImage'); a.image = img('T_Test_Flora_o_1')
    nt.links.new(a.outputs['Color'], bsdf.inputs['Alpha'])
else:
    n = nt.nodes.new('ShaderNodeTexImage'); n.image = img('T_Test_Flora_n_1')
    nm = nt.nodes.new('ShaderNodeNormalMap'); nt.links.new(n.outputs['Color'], nm.inputs['Color'])
    nt.links.new(nm.outputs['Normal'], bsdf.inputs['Normal'])
o.data.materials.append(m)
bpy.ops.export_scene.fbx(filepath=out, path_mode='COPY', embed_textures=True)
"""


@pytest.mark.blender
@pytest.mark.skipif(BLENDER is None, reason="Blender not installed")
@pytest.mark.parametrize("variant", ["good", "bad"])
def test_blender_roundtrip_flora_maps_and_dimensions(tmp_path, variant):
    fbx_path = tmp_path / "SM_Test_Ground.fbx"
    subprocess.run([BLENDER, "--background", "--factory-startup", "--python-exit-code", "1",
                    "--python-expr", MAKE_FLORA, "--", str(fbx_path), variant], check=True, capture_output=True,
                   timeout=300)
    data = readback(fbx_path)
    maps = {m["socket"] for x in data["materials"] if x["name"] == "M_Test_Flora_1" for m in x["maps"]}
    # A 3 m plane standing from -0.10 to 2.90 m: 2.9 m above the Ground after the 10 cm sinking.
    schedule = {"SM_Test_Flora": {"height_m": 2.9 if variant == "good" else 2.0, "crown_m": 3.0}}
    found = scene_findings(data, "npm", "ground", PROFILES.npm, flora_schedule=schedule)
    if variant == "good":
        assert maps == {"Base Color", "Alpha"}
        assert named(found, "V005", "Flora") == {"Flora maps: M_Test_Flora_1": "pass"}
        assert named(found, "V015", "Flora") == {"Flora dimensions: SM_Test_Flora": "pass"}
    else:
        assert maps == {"Base Color", "Normal"}
        assert named(found, "V005", "Flora") == {"Flora maps: M_Test_Flora_1": "fail"}  # Normal map
        assert named(found, "V015", "Flora") == {"Flora dimensions: SM_Test_Flora": "fail"}
    assert named(found, "V003", "Flora") == {"Flora triangle share": "pass"}
