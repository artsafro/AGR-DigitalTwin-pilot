"""Ground diffuse binding: plan table, fail-closed gates, geometry and density (issue #340)."""
import copy
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools" / "materials" / "bind_ground_textures.py"
V014_MATERIALS = [
    "M_Vatutino_Ground_CurbGarden",
    "M_Vatutino_Ground_FlowerBed",
    "M_Vatutino_Ground_Gravel",
    "M_Vatutino_Ground_LawnReinforced",
    "M_Vatutino_Ground_LawnRolled",
    "M_Vatutino_Ground_Mulch",
    "M_Vatutino_Ground_Pebbles",
    "M_Vatutino_Ground_Skirt",
    "M_Vatutino_Ground_Stairs",
    "M_Vatutino_Ground_TileDark",
    "M_Vatutino_Ground_TileLight",
    "M_Vatutino_Ground_TileRed",
]


def _load():
    spec = importlib.util.spec_from_file_location("bind_ground_textures", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bind = _load()


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _png(path: Path, size: int) -> None:
    Image.new("RGB", (size, size), (size % 255, 20, 30)).save(path)


def _readback(names):
    return {"materials": list(names), "triangles": 1}


def _names(slots):
    return [f"M_Vatutino_Ground_{slot}" for slot in slots]


def _scene(tmp_path, slots=None, mesh_slots=None, **edits):
    slots = list(slots or bind.REQUIRED_SLOTS)
    mesh = list(mesh_slots or slots)
    root = tmp_path / "textures"
    root.mkdir(parents=True)
    maps = []
    for slot in slots:
        for profile, size in (("npm", 2048), ("vpm", 4096)):
            filename = bind.texture_filename(slot, profile)
            path = root / filename
            _png(path, size)
            maps.append({
                "file": filename,
                "slot": slot,
                "profile": profile,
                "size": [size, size],
                "sha256": _sha(path),
            })
    manifest = {"address": "Vatutino", "maps": maps, "manifest_path": str(tmp_path / "manifest.json")}
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    sources = tmp_path / "sources"
    sources.mkdir()
    npm_fbx = sources / "npm-source.fbx"
    vpm_fbx = sources / "vpm-source.fbx"
    npm_fbx.write_bytes(b"npm-source")
    vpm_fbx.write_bytes(b"vpm-source")
    return {
        "root": root,
        "manifest": manifest,
        "npm_readback": _readback(_names(mesh)),
        "vpm_readback": _readback(_names(mesh)),
        "npm_fbx": npm_fbx,
        "vpm_fbx": vpm_fbx,
    }


def _use(tmp_path, monkeypatch, scene):
    out = tmp_path / "out"
    monkeypatch.setattr(bind, "TEXTURE_ROOT", scene["root"])
    monkeypatch.setattr(bind, "OUTPUT_DIR", out)
    return out


def _plan(scene):
    previous = bind.TEXTURE_ROOT
    bind.TEXTURE_ROOT = scene["root"]
    try:
        return bind.build_plan(
            scene["npm_readback"], scene["vpm_readback"], scene["manifest"], scene["root"],
            scene["npm_fbx"], scene["vpm_fbx"],
        )
    finally:
        bind.TEXTURE_ROOT = previous


def test_plan_assigns_exactly_one_verified_map_per_slot(tmp_path):
    scene = _scene(tmp_path)
    plan = _plan(scene)
    for profile, size in (("npm", 2048), ("vpm", 4096)):
        bindings = plan["bindings"][profile]
        assert [item["slot"] for item in bindings] == list(bind.REQUIRED_SLOTS)
        assert len(bindings) == len({item["slot"] for item in bindings}) == len(bind.REQUIRED_SLOTS) == 12
        for item in bindings:
            assert item["file"] == bind.texture_filename(item["slot"], profile)
            assert item["sha256"] == _sha(scene["root"] / item["file"])
            assert item["size"] == size
            assert item["material"] == f"M_Vatutino_Ground_{item['slot']}"
        assert plan["ground_slots_without_map"][profile] == []
        assert plan["manifest_slots_without_material"][profile] == []
    assert plan["sources"]["npm_fbx"]["sha256"] == _sha(scene["npm_fbx"])
    assert plan["sources"]["vpm_fbx"]["sha256"] == _sha(scene["vpm_fbx"])


def test_plan_lists_a_ground_slot_without_a_map_and_a_map_without_a_material(tmp_path):
    mesh = [slot for slot in bind.REQUIRED_SLOTS if slot != "Skirt"] + ["Decking"]
    scene = _scene(tmp_path, mesh_slots=mesh)
    plan = _plan(scene)
    assert plan["ground_slots_without_map"]["npm"] == ["Decking"]
    assert plan["manifest_slots_without_material"]["vpm"] == ["Skirt"]


def test_regression_v003_binds_every_v014_slot_once(tmp_path):
    """CurbGarden and Stairs are v003 maps. v002 is not a bind source."""
    assert bind.TEXTURE_ROOT == Path("C:/x/vatutino-ground-textures/v003")
    slots = [name.split("_Ground_", 1)[1] for name in V014_MATERIALS]
    assert len(bind.REQUIRED_SLOTS) == len(set(bind.REQUIRED_SLOTS)) == 12
    assert set(bind.REQUIRED_SLOTS) == set(slots)
    for slot in ("CurbGarden", "Stairs"):
        assert list(bind.REQUIRED_SLOTS).count(slot) == 1
    with pytest.raises(bind.BindError):
        bind.assert_texture_root(Path("C:/x/vatutino-ground-textures/v002"))
    scene = _scene(tmp_path, slots=slots, mesh_slots=slots)
    scene["npm_readback"] = _readback(V014_MATERIALS)
    scene["vpm_readback"] = _readback(V014_MATERIALS)
    plan = _plan(scene)
    for profile in ("npm", "vpm"):
        bound = [item["slot"] for item in plan["bindings"][profile]]
        assert bound == slots
        assert len(bound) == len(set(bound)) == 12
        assert plan["ground_slots_without_map"][profile] == []
        assert plan["manifest_slots_without_material"][profile] == []
        for item in plan["bindings"][profile]:
            assert item["file"].count(item["slot"]) == 1


def test_regression_v014_lists_curb_and_stairs_and_bind_writes_nothing(tmp_path, monkeypatch):
    """A v002 manifest, missing CurbGarden and Stairs, cannot bind the v014 mesh."""
    v002_slots = [slot for slot in bind.REQUIRED_SLOTS if slot not in {"CurbGarden", "Stairs"}]
    scene = _scene(
        tmp_path,
        slots=v002_slots,
        mesh_slots=[name.split("_Ground_", 1)[1] for name in V014_MATERIALS],
    )
    scene["npm_readback"] = _readback(V014_MATERIALS)
    scene["vpm_readback"] = _readback(V014_MATERIALS)
    with pytest.raises(bind.BindError, match="partial"):
        _plan(scene)
    out = _use(tmp_path, monkeypatch, scene)
    called = []
    with pytest.raises(bind.BindError, match="partial|CurbGarden"):
        bind.bind_delivery(
            scene["npm_readback"], scene["vpm_readback"], scene["manifest"], scene["root"],
            scene["npm_fbx"], scene["vpm_fbx"], out, dcc=lambda *args: called.append(args),
        )
    assert called == []
    assert not out.exists()
    assert scene["npm_fbx"].read_bytes() == b"npm-source"
    assert scene["vpm_fbx"].read_bytes() == b"vpm-source"


@pytest.mark.parametrize("slot", bind.REQUIRED_SLOTS)
def test_every_removed_mesh_slot_is_listed_and_blocks_the_fbx(tmp_path, monkeypatch, slot):
    scene = _scene(tmp_path, mesh_slots=[name for name in bind.REQUIRED_SLOTS if name != slot])
    plan = _plan(scene)
    assert plan["manifest_slots_without_material"]["npm"] == [slot]
    out = _use(tmp_path, monkeypatch, scene)
    with pytest.raises(bind.BindError, match=slot):
        bind.bind_delivery(
            scene["npm_readback"], scene["vpm_readback"], scene["manifest"], scene["root"],
            scene["npm_fbx"], scene["vpm_fbx"], out, dcc=lambda *_: (_ for _ in ()).throw(AssertionError("dcc")),
        )
    assert not out.exists()


@pytest.mark.parametrize("slot", bind.REQUIRED_SLOTS)
def test_every_duplicate_manifest_slot_errors(tmp_path, slot):
    scene = _scene(tmp_path)
    scene["manifest"]["maps"].append(copy.deepcopy(
        next(item for item in scene["manifest"]["maps"] if item["slot"] == slot and item["profile"] == "npm")
    ))
    with pytest.raises(bind.BindError, match="duplicate"):
        _plan(scene)


@pytest.mark.parametrize("slot", bind.REQUIRED_SLOTS)
def test_every_missing_required_manifest_slot_is_partial(tmp_path, slot):
    scene = _scene(tmp_path)
    scene["manifest"]["maps"] = [item for item in scene["manifest"]["maps"] if item["slot"] != slot]
    with pytest.raises(bind.BindError, match="partial"):
        _plan(scene)


def test_missing_map_file_writes_nothing(tmp_path, monkeypatch, capsys):
    scene = _scene(tmp_path)
    target = scene["root"] / bind.texture_filename("Mulch", "npm")
    target.unlink()
    out = _use(tmp_path, monkeypatch, scene)
    plan_path = tmp_path / "plan.json"
    code = bind.main([
        "plan", "--npm-readback", _write_json(tmp_path / "npm.json", scene["npm_readback"]),
        "--vpm-readback", _write_json(tmp_path / "vpm.json", scene["vpm_readback"]),
        "--manifest", str(tmp_path / "manifest.json"), "--textures", str(scene["root"]),
        "--out", str(plan_path),
    ])
    captured = capsys.readouterr()
    assert code == 2
    assert captured.err.startswith("error:")
    assert "missing" in captured.err
    assert not plan_path.exists()
    assert not out.exists()


def test_sha256_mismatch_writes_nothing(tmp_path, monkeypatch, capsys):
    scene = _scene(tmp_path)
    scene["manifest"]["maps"][0]["sha256"] = "ab" * 32
    (tmp_path / "manifest.json").write_text(json.dumps(scene["manifest"]), encoding="utf-8")
    out = _use(tmp_path, monkeypatch, scene)
    code = bind.main([
        "bind", "--npm-readback", _write_json(tmp_path / "npm.json", scene["npm_readback"]),
        "--vpm-readback", _write_json(tmp_path / "vpm.json", scene["vpm_readback"]),
        "--manifest", str(tmp_path / "manifest.json"), "--textures", str(scene["root"]),
        "--npm-fbx", str(scene["npm_fbx"]), "--vpm-fbx", str(scene["vpm_fbx"]),
        "--out", str(out),
    ])
    assert code == 2
    assert "sha256" in capsys.readouterr().err
    assert not out.exists()
    assert scene["npm_fbx"].read_bytes() == b"npm-source"


@pytest.mark.parametrize(("profile", "side"), [("npm", 16), ("vpm", 32)])
def test_wrong_profile_size_writes_nothing(tmp_path, monkeypatch, profile, side):
    scene = _scene(tmp_path)
    slot = "TileLight"
    filename = bind.texture_filename(slot, profile)
    path = scene["root"] / filename
    _png(path, side)
    for entry in scene["manifest"]["maps"]:
        if entry["file"] == filename:
            entry["sha256"] = _sha(path)
            entry["size"] = [bind.PROFILE_SIZE[profile], bind.PROFILE_SIZE[profile]]
    out = _use(tmp_path, monkeypatch, scene)
    with pytest.raises(bind.BindError, match="not"):
        _plan(scene)
    assert not out.exists()


def test_manifest_size_other_than_2048_or_4096_errors(tmp_path):
    scene = _scene(tmp_path)
    scene["manifest"]["maps"][0]["size"] = [1024, 1024]
    with pytest.raises(bind.BindError, match="2048"):
        _plan(scene)
    scene = _scene(tmp_path / "b")
    vpm = next(item for item in scene["manifest"]["maps"] if item["profile"] == "vpm")
    vpm["size"] = [2048, 2048]
    with pytest.raises(bind.BindError, match="4096"):
        _plan(scene)


def test_vpm_map_without_1001_writes_nothing(tmp_path, monkeypatch):
    scene = _scene(tmp_path)
    for entry in scene["manifest"]["maps"]:
        if entry["profile"] == "vpm" and entry["slot"] == "Gravel":
            entry["file"] = "T_Vatutino_Ground_Diffuse_Gravel.png"
    out = _use(tmp_path, monkeypatch, scene)
    with pytest.raises(bind.BindError, match="1001"):
        bind.bind_delivery(
            scene["npm_readback"], scene["vpm_readback"], scene["manifest"], scene["root"],
            scene["npm_fbx"], scene["vpm_fbx"], out,
        )
    assert not out.exists()


@pytest.mark.parametrize("name", [
    "M_Vatutino_TileLight",
    "M_Other_Ground_TileLight",
    "M_Vatutino_Ground_",
    "M_Vatutino_Ground_TileLight.001",
    "TileLight",
    "",
    None,
    float("nan"),
    float("inf"),
])
def test_slot_name_outside_the_mask_writes_nothing(tmp_path, monkeypatch, name):
    scene = _scene(tmp_path)
    scene["npm_readback"] = _readback([name, *_names(bind.REQUIRED_SLOTS)])
    out = _use(tmp_path, monkeypatch, scene)
    with pytest.raises(bind.BindError, match="slot name"):
        bind.bind_delivery(
            scene["npm_readback"], scene["vpm_readback"], scene["manifest"], scene["root"],
            scene["npm_fbx"], scene["vpm_fbx"], out,
        )
    assert not out.exists()


def test_output_that_resolves_to_an_input_writes_nothing(tmp_path, monkeypatch):
    scene = _scene(tmp_path)
    monkeypatch.setattr(bind, "TEXTURE_ROOT", scene["root"])
    monkeypatch.setattr(bind, "OUTPUT_DIR", scene["root"])
    before = sorted(path.name for path in scene["root"].iterdir())
    with pytest.raises(bind.BindError, match="texture input"):
        bind.bind_delivery(
            scene["npm_readback"], scene["vpm_readback"], scene["manifest"], scene["root"],
            scene["npm_fbx"], scene["vpm_fbx"], scene["root"],
        )
    assert sorted(path.name for path in scene["root"].iterdir()) == before
    monkeypatch.setattr(bind, "OUTPUT_DIR", scene["npm_fbx"])
    with pytest.raises(bind.BindError, match="input"):
        bind.bind_delivery(
            scene["npm_readback"], scene["vpm_readback"], scene["manifest"], scene["root"],
            scene["npm_fbx"], scene["vpm_fbx"], scene["npm_fbx"],
            extra_inputs=(scene["npm_fbx"],),
        )
    assert scene["npm_fbx"].read_bytes() == b"npm-source"


@pytest.mark.parametrize("alias", [True, False])
def test_blender_entrypoint_refuses_input_alias_and_existing_output(tmp_path, monkeypatch, alias):
    import runpy
    import sys
    from types import SimpleNamespace

    source = tmp_path / "source.fbx"
    source.write_bytes(b"source")
    output = source if alias else tmp_path / "existing.fbx"
    if not alias:
        output.write_bytes(b"existing")
    spec = tmp_path / "spec.json"
    spec.write_text("{}", encoding="utf-8")
    monkeypatch.setitem(sys.modules, "bpy", SimpleNamespace())
    script = ROOT / "tools/materials/bind_ground_textures_blender.py"
    monkeypatch.setattr(sys, "argv", [str(script), "--", "bind", str(source), str(spec), str(output)])
    with pytest.raises(ValueError, match="overwrite|existing"):
        runpy.run_path(str(script), run_name="__main__")
    assert source.read_bytes() == b"source"
    assert output.read_bytes() == (b"source" if alias else b"existing")


def test_default_dcc_stages_copies_only_inside_output_root(tmp_path, monkeypatch):
    source = tmp_path / "source.fbx"
    source.write_bytes(b"source")
    destination = tmp_path / "delivery" / "bound.fbx"
    destination.parent.mkdir()
    calls = []

    def run(script, args):
        calls.append(args)
        Path(args[-1]).write_text("{}", encoding="utf-8")

    monkeypatch.setattr(bind, "_run_blender", run)
    bind.default_dcc("npm", source, tmp_path, [], destination)
    staged_source = Path(calls[0][1])
    assert staged_source.is_relative_to(destination.parent)
    assert not staged_source.exists()
    assert source.read_bytes() == b"source"


def test_case_alias_of_an_input_is_refused(tmp_path):
    source = tmp_path / "SM_Vatutino_Ground.fbx"
    source.write_bytes(b"fbx")
    folded = tmp_path / "sm_vatutino_ground.fbx"
    assert bind._same(source, folded) is (os.name == "nt")
    if os.name == "nt":
        with pytest.raises(bind.BindError, match="source"):
            bind.stage_source_copy(source, folded)
        assert source.read_bytes() == b"fbx"


def test_v002_output_writes_nothing(tmp_path, monkeypatch):
    scene = _scene(tmp_path)
    monkeypatch.setattr(bind, "TEXTURE_ROOT", scene["root"])
    monkeypatch.setattr(bind, "OUTPUT_DIR", bind.V002_TEXTURES)
    before = {path.name: path.stat().st_mtime_ns for path in bind.V002_TEXTURES.iterdir()} if bind.V002_TEXTURES.is_dir() else {}
    with pytest.raises(bind.BindError, match="v002"):
        bind.bind_delivery(
            scene["npm_readback"], scene["vpm_readback"], scene["manifest"], scene["root"],
            scene["npm_fbx"], scene["vpm_fbx"], bind.V002_TEXTURES,
            dcc=lambda *_: (_ for _ in ()).throw(AssertionError("dcc")),
        )
    if before:
        after = {path.name: path.stat().st_mtime_ns for path in bind.V002_TEXTURES.iterdir()}
        assert after == before


def test_v001_texture_root_is_refused(tmp_path, monkeypatch):
    with pytest.raises(bind.BindError, match="v001"):
        bind.assert_texture_root(bind.V001_TEXTURES)
    with pytest.raises(bind.BindError, match="v001"):
        bind.assert_texture_root(bind.V001_TEXTURES / "T_Vatutino_Ground_Diffuse_Skirt.png")
    monkeypatch.setattr(bind, "TEXTURE_ROOT", bind.V001_TEXTURES)
    with pytest.raises(bind.BindError, match="v001"):
        bind.assert_texture_root(bind.V001_TEXTURES)


@pytest.mark.parametrize(("manifest", "message"), [
    ({}, "empty"),
    ({"maps": []}, "empty"),
    ({"maps": [{"slot": "TileLight", "profile": "udim", "file": "x", "sha256": "ab" * 32, "size": [2048, 2048]}]}, "unsupported"),
    ({"maps": "TileLight"}, "empty"),
    (None, "unsupported"),
    ([], "unsupported"),
])
def test_empty_partial_and_unsupported_manifests_error(manifest, message):
    with pytest.raises(bind.BindError, match=message):
        bind.build_plan({"materials": _names(bind.REQUIRED_SLOTS)}, {"materials": _names(bind.REQUIRED_SLOTS)}, manifest, bind.TEXTURE_ROOT)


@pytest.mark.parametrize("size", [[float("nan"), 2048], [2048, float("inf")], [float("-inf"), 2048], [True, 2048]])
def test_nonfinite_manifest_size_errors(tmp_path, size):
    scene = _scene(tmp_path)
    scene["manifest"]["maps"][0]["size"] = size
    with pytest.raises(bind.BindError, match="non-finite|2048"):
        _plan(scene)


@pytest.mark.parametrize("readback", [{}, {"materials": []}, {"meshes": [{"materials": []}]}, {"materials": [None]}, []])
def test_empty_or_unsupported_readback_errors(tmp_path, readback):
    scene = _scene(tmp_path)
    with pytest.raises(bind.BindError):
        bind.build_plan(readback, scene["vpm_readback"], scene["manifest"], scene["root"])


def test_final_ground_readback_keeps_materialless_ucx_out_of_binding_table():
    readback = {"meshes": [
        {"name": "SM_Vatutino_Ground", "materials": V014_MATERIALS},
        {"name": "UCX_SM_Vatutino_Ground_001", "materials": []},
    ]}
    assert bind.material_names(readback) == V014_MATERIALS
    readback["meshes"][1]["name"] = "SM_Unknown"
    with pytest.raises(bind.BindError, match="empty"):
        bind.material_names(readback)


def test_collision_geometry_change_fails_identity():
    base = _geometry()
    base["collision_geometry"] = [{"name": "UCX_SM_Vatutino_Ground_001", "vertices": [[0, 0, 0]]}]
    changed = copy.deepcopy(base)
    changed["collision_geometry"][0]["vertices"][0][0] = 1
    with pytest.raises(bind.BindError, match="collision"):
        bind.geometry_deltas(base, changed)


def test_raw_material_layer_and_topology_changes_are_rejected():
    base = _geometry()
    base["raw_material_layers"] = [{"mapping": "ByPolygon", "reference": "IndexToDirect", "ids": [0]}]
    base["polygons"] = [[0, 1, 2]]
    changed = copy.deepcopy(base)
    changed["raw_material_layers"][0]["ids"] = [1]
    with pytest.raises(bind.BindError, match="raw material"):
        bind.geometry_deltas(base, changed)
    changed = copy.deepcopy(base)
    changed["polygons"] = [[0, 2, 1]]
    with pytest.raises(bind.BindError, match="topology"):
        bind.geometry_deltas(base, changed)


def test_geometry_accepts_only_exact_zero_delta():
    base = _geometry()
    assert bind.geometry_deltas(base, copy.deepcopy(base)) == {"vertex": 0.0, "uv": 0.0, "triangles": 1}
    deltas = [0.0, math.nextafter(0.0, 1.0)]
    deltas.extend(i * 1e-9 for i in range(1, 201))
    for delta in deltas:
        mutated = copy.deepcopy(base)
        mutated["vertices"][0][0] += delta
        if delta == 0.0:
            assert bind.geometry_deltas(base, mutated)["vertex"] == 0.0
        else:
            with pytest.raises(bind.BindError, match="delta"):
                bind.geometry_deltas(base, mutated)
    shifted = copy.deepcopy(base)
    shifted["uvs"][1][1] = math.nextafter(shifted["uvs"][1][1], 2.0)
    with pytest.raises(bind.BindError, match="uv"):
        bind.geometry_deltas(base, shifted)
    retargeted = copy.deepcopy(base)
    retargeted["material_ids"][0] = 1
    with pytest.raises(bind.BindError, match="material"):
        bind.geometry_deltas(base, retargeted)
    counted = copy.deepcopy(base)
    counted["triangles"] = 2
    with pytest.raises(bind.BindError, match="triangle"):
        bind.geometry_deltas(base, counted)


@pytest.mark.parametrize("payload", [
    {"triangles": 0, "material_ids": [0], "vertices": [[0, 0, 0]], "uvs": [[0, 0]]},
    {"triangles": 1, "material_ids": [], "vertices": [[0, 0, 0]], "uvs": [[0, 0]]},
    {"triangles": 1, "material_ids": [0], "vertices": [], "uvs": [[0, 0]]},
    {"triangles": 1, "material_ids": [0], "vertices": [[0, 0, float("nan")]], "uvs": [[0, 0]]},
    {"triangles": 1, "material_ids": [0], "vertices": [[0, 0, float("inf")]], "uvs": [[0, 0]]},
    {"triangles": 1, "material_ids": [True], "vertices": [[0, 0, 0]], "uvs": [[0, 0]]},
    {"triangles": float("nan"), "material_ids": [0], "vertices": [[0, 0, 0]], "uvs": [[0, 0]]},
    {},
    [],
])
def test_bad_geometry_is_an_error(payload):
    with pytest.raises(bind.BindError):
        bind.geometry_deltas(payload, payload)


def test_density_grid_keeps_endpoints_and_rejects_the_outside():
    for step in range(0, 801):
        value = step / 10
        face = {"slot": "TileLight", "world_area_m2": 1.0, "uv_area": (value / 2048) ** 2 if value else 0.0}
        if 10 <= value <= 40:
            report = bind.density_report([face], "npm")
            assert report["TileLight"]["min"] == value
            assert report["TileLight"]["max"] == value
        else:
            with pytest.raises(bind.BindError):
                bind.density_report([face], "npm")
        for value in (10.0, 40.0, math.nextafter(10.0, 0.0), math.nextafter(40.0, 80.0)):
            face = {"slot": "CurbGarden", "world_area_m2": 1.0, "uv_area": (value / 2048) ** 2}
            if value in (10.0, 40.0):
                assert bind.density_report([face], "npm")["CurbGarden"]["min"] == value
            else:
                with pytest.raises(bind.BindError, match="outside"):
                    bind.density_report([face], "npm")
    for value in (512.0, 1706.0, math.nextafter(512.0, 0.0), math.nextafter(1706.0, 2000.0)):
        face = {"slot": "LawnRolled", "world_area_m2": 1.0, "uv_area": (value / 4096) ** 2}
        if value in (512.0, 1706.0):
            report = bind.density_report([face], "vpm")
            assert report["LawnRolled"]["min"] == value
            assert report["LawnRolled"]["max"] == value
        else:
            with pytest.raises(bind.BindError, match="outside"):
                bind.density_report([face], "vpm")


@pytest.mark.parametrize(("faces", "profile"), [
    ([], "npm"),
    ([{"slot": "TileLight", "world_area_m2": float("nan"), "uv_area": 1.0}], "npm"),
    ([{"slot": "TileLight", "world_area_m2": float("inf"), "uv_area": 1.0}], "npm"),
    ([{"slot": "TileLight", "world_area_m2": 0.0, "uv_area": 1.0}], "npm"),
    ([{"slot": "TileLight", "world_area_m2": 1.0, "uv_area": -1.0}], "vpm"),
    ([{"slot": "", "world_area_m2": 1.0, "uv_area": 1.0}], "npm"),
    ([{"world_area_m2": 1.0, "uv_area": 1.0}], "npm"),
    ("TileLight", "npm"),
    ([{"slot": "TileLight", "world_area_m2": 1.0, "uv_area": (30 / 2048) ** 2}], "udim"),
])
def test_empty_nonfinite_and_unsupported_density_errors(faces, profile):
    with pytest.raises(bind.BindError):
        bind.density_report(faces, profile)


def test_skirt_zero_uv_is_reported_outside_the_relief_band():
    """Perimeter skirt UV area is 0 on the #295 FBX. TEX-17 excludes it from [D097]."""
    skirt = {"slot": "Skirt", "world_area_m2": 1.0, "uv_area": 0.0}
    relief = {"slot": "TileLight", "world_area_m2": 1.0, "uv_area": (30 / 2048) ** 2}
    report = bind.density_report([skirt, relief], "npm", expected_slots=["Skirt", "TileLight"])
    assert report["Skirt"]["min"] == 0.0
    assert report["Skirt"]["max"] == 0.0
    assert report["TileLight"]["min"] == 30.0
    collapsed = {"slot": "TileLight", "world_area_m2": 1.0, "uv_area": 0.0}
    with pytest.raises(bind.BindError, match="outside"):
        bind.density_report([collapsed], "npm")
    for value in (0.0, math.nextafter(0.0, -1.0)):
        face = {"slot": "CurbGarden", "world_area_m2": 1.0, "uv_area": value}
        with pytest.raises(bind.BindError):
            bind.density_report([face], "npm")


def test_partial_density_slots_error():
    face = {"slot": "TileLight", "world_area_m2": 1.0, "uv_area": (30 / 2048) ** 2}
    with pytest.raises(bind.BindError, match="partial"):
        bind.density_report([face], "npm", expected_slots=bind.REQUIRED_SLOTS)


def test_readback_mismatches_are_zero_only_for_an_exact_table():
    bindings, observed = _observed()
    assert bind.accept_readback(bindings, observed) == 0
    for index, binding in enumerate(bindings):
        broken = copy.deepcopy(observed)
        broken["materials"][index]["maps"][0]["image"] = "other.png"
        assert bind.mismatch_count(bindings, broken) == 1
        with pytest.raises(bind.BindError, match="mismatches"):
            bind.accept_readback(bindings, broken)
    extra = copy.deepcopy(observed)
    extra["materials"].append({"name": "M_Vatutino_Ground_Unmapped", "maps": []})
    assert bind.mismatch_count(bindings, extra) == 1
    doubled = copy.deepcopy(observed)
    doubled["materials"][0]["maps"].append(dict(doubled["materials"][0]["maps"][0]))
    assert bind.mismatch_count(bindings, doubled) == 1
    sized = copy.deepcopy(observed)
    sized["images"][0]["size"] = [4096, 4096]
    assert bind.mismatch_count(bindings, sized) == 1


@pytest.mark.parametrize("readback", [{}, {"materials": [], "images": []}, {"materials": [{"name": "M"}], "images": []}])
def test_empty_readback_is_an_error_not_zero_mismatches(readback):
    bindings, _observed_ok = _observed()
    with pytest.raises(bind.BindError, match="empty"):
        bind.mismatch_count(bindings, readback)
    with pytest.raises(bind.BindError):
        bind.mismatch_count([], readback)


@pytest.mark.parametrize("fraction", [0.01, 0.5, 0.99])
def test_fractional_manifest_dimensions_are_rejected(fraction):
    entry = {"slot": "TileLight", "profile": "npm",
             "file": bind.texture_filename("TileLight", "npm"),
             "sha256": "ab" * 32, "size": [2048 + fraction, 2048]}
    with pytest.raises(bind.BindError, match="size|integer"):
        bind._manifest_maps({"maps": [entry]})


def test_duplicate_readback_material_cannot_hide_a_wrong_binding():
    bindings, observed = _observed()
    duplicate = copy.deepcopy(observed["materials"][0])
    observed["materials"][0]["maps"][0]["image"] = "wrong.png"
    observed["materials"].append(duplicate)
    with pytest.raises(bind.BindError, match="duplicate"):
        bind.accept_readback(bindings, observed)


def test_hardlink_input_alias_is_detected(tmp_path):
    source = tmp_path / "source.fbx"
    alias = tmp_path / "alias.fbx"
    source.write_bytes(b"source")
    os.link(source, alias)
    assert bind._same(source, alias)
    assert bind.output_conflicts(alias, [source])
    assert source.read_bytes() == b"source"


def test_nonfinite_image_size_errors():
    bindings, observed = _observed()
    observed["images"][0]["size"] = [float("nan"), 2048]
    with pytest.raises(bind.BindError, match="non-finite"):
        bind.mismatch_count(bindings, observed)


def test_existing_output_is_left_unchanged(tmp_path, monkeypatch):
    scene = _scene(tmp_path)
    out = _use(tmp_path, monkeypatch, scene)
    out.mkdir()
    marker = out / "keep.txt"
    marker.write_text("keep", encoding="utf-8")
    with pytest.raises(bind.BindError, match="already"):
        bind.bind_delivery(
            scene["npm_readback"], scene["vpm_readback"], scene["manifest"], scene["root"],
            scene["npm_fbx"], scene["vpm_fbx"], out, dcc=lambda *_: (_ for _ in ()).throw(AssertionError("dcc")),
        )
    assert marker.read_text(encoding="utf-8") == "keep"


def test_successful_bind_keeps_matching_geometry_and_a_zero_mismatch_readback(tmp_path, monkeypatch):
    scene = _scene(tmp_path)
    out = _use(tmp_path, monkeypatch, scene)

    def dcc(profile, source, root, bindings, out_fbx):
        assert source.read_bytes() == (b"npm-source" if profile == "npm" else b"vpm-source")
        out_fbx.parent.mkdir(parents=True, exist_ok=True)
        out_fbx.write_bytes(b"bound-" + profile.encode())
        px = bind.PROFILE_SIZE[profile]
        density = 30.0 if profile == "npm" else 1024.0
        geom = _geometry()
        geom["faces"] = [
            {"slot": item["slot"], "world_area_m2": 1.0, "uv_area": (density / px) ** 2}
            for item in bindings
        ]
        geom["triangles"] = len(bindings)
        geom["material_ids"] = list(range(len(bindings)))
        before = out_fbx.with_suffix(".source-fingerprint.json")
        after = out_fbx.with_suffix(".fingerprint.json")
        readback = out_fbx.with_suffix(".readback.json")
        before.write_text(json.dumps(geom), encoding="utf-8")
        after.write_text(json.dumps(geom), encoding="utf-8")
        readback.write_text(json.dumps({
            "materials": [
                {"name": item["material"], "maps": [{"image": item["file"], "socket": "Base Color", "output": "Color"}]}
                for item in bindings
            ],
            "images": [{"name": item["file"], "size": [item["size"], item["size"]]} for item in bindings],
        }), encoding="utf-8")
        return {"before": before, "after": after, "readback": readback}

    plan = bind.bind_delivery(
        scene["npm_readback"], scene["vpm_readback"], scene["manifest"], scene["root"],
        scene["npm_fbx"], scene["vpm_fbx"], out, dcc=dcc,
    )
    assert (out / "npm" / bind.FBX_NAME).read_bytes() == b"bound-npm"
    assert (out / "vpm" / bind.FBX_NAME).read_bytes() == b"bound-vpm"
    assert plan["density"]["npm"]["TileLight"]["min"] == 30.0
    assert plan["density"]["vpm"]["Skirt"]["max"] == 1024.0
    assert scene["npm_fbx"].read_bytes() == b"npm-source"
    assert scene["root"].is_dir()


@pytest.mark.parametrize("preexisting", [False, True])
def test_dcc_failure_never_leaves_a_partial_fbx(tmp_path, monkeypatch, preexisting):
    scene = _scene(tmp_path)
    out = _use(tmp_path, monkeypatch, scene)
    if preexisting:
        out.mkdir()

    def dcc(profile, source, root, bindings, out_fbx):
        out_fbx.write_bytes(b"partial")
        raise bind.BindError("incomplete DCC export")

    with pytest.raises(bind.BindError, match="incomplete"):
        bind.bind_delivery(
            scene["npm_readback"], scene["vpm_readback"], scene["manifest"], scene["root"],
            scene["npm_fbx"], scene["vpm_fbx"], out, dcc=dcc,
        )
    assert not list(out.rglob("*.fbx"))
    assert scene["npm_fbx"].read_bytes() == b"npm-source"


def test_geometry_mismatch_after_dcc_removes_the_fbx(tmp_path, monkeypatch):
    scene = _scene(tmp_path)
    out = _use(tmp_path, monkeypatch, scene)

    def dcc(profile, source, root, bindings, out_fbx):
        out_fbx.parent.mkdir(parents=True, exist_ok=True)
        out_fbx.write_bytes(b"partial")
        geom = _geometry()
        before = out_fbx.with_suffix(".source-fingerprint.json")
        after = out_fbx.with_suffix(".fingerprint.json")
        changed = copy.deepcopy(geom)
        changed["vertices"][0][2] = math.nextafter(0.0, 1.0)
        before.write_text(json.dumps(geom), encoding="utf-8")
        after.write_text(json.dumps(changed), encoding="utf-8")
        readback = out_fbx.with_suffix(".readback.json")
        readback.write_text("{}", encoding="utf-8")
        return {"before": before, "after": after, "readback": readback}

    with pytest.raises(bind.BindError, match="delta"):
        bind.bind_delivery(
            scene["npm_readback"], scene["vpm_readback"], scene["manifest"], scene["root"],
            scene["npm_fbx"], scene["vpm_fbx"], out, dcc=dcc,
        )
    assert not out.exists()


def test_cli_plan_writes_the_table(tmp_path, monkeypatch, capsys):
    scene = _scene(tmp_path)
    _use(tmp_path, monkeypatch, scene)
    plan_path = tmp_path / "plan.json"
    code = bind.main([
        "plan", "--npm-readback", _write_json(tmp_path / "npm.json", scene["npm_readback"]),
        "--vpm-readback", _write_json(tmp_path / "vpm.json", scene["vpm_readback"]),
        "--manifest", str(tmp_path / "manifest.json"), "--textures", str(scene["root"]),
        "--npm-fbx", str(scene["npm_fbx"]), "--vpm-fbx", str(scene["vpm_fbx"]),
        "--out", str(plan_path),
    ])
    assert code == 0
    assert capsys.readouterr().err == ""
    written = json.loads(plan_path.read_text(encoding="utf-8"))
    assert len(written["bindings"]["npm"]) == len(bind.REQUIRED_SLOTS) == 12
    assert written["bindings"]["vpm"][0]["file"].endswith(".1001.png")


def test_cli_plan_refuses_an_output_that_is_the_manifest(tmp_path, monkeypatch, capsys):
    scene = _scene(tmp_path)
    _use(tmp_path, monkeypatch, scene)
    manifest = tmp_path / "manifest.json"
    original = manifest.read_text(encoding="utf-8")
    code = bind.main([
        "plan", "--npm-readback", _write_json(tmp_path / "npm.json", scene["npm_readback"]),
        "--vpm-readback", _write_json(tmp_path / "vpm.json", scene["vpm_readback"]),
        "--manifest", str(manifest), "--textures", str(scene["root"]),
        "--out", str(manifest),
    ])
    assert code == 2
    assert "input" in capsys.readouterr().err
    assert manifest.read_text(encoding="utf-8") == original


def _write_json(path: Path, payload) -> str:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return str(path)


def _geometry():
    return {
        "triangles": 1,
        "material_ids": [0],
        "vertices": [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
        "uvs": [[0.0, 0.0], [1.0, 0.0], [0.0, 1.0]],
        "faces": [{"slot": "TileLight", "world_area_m2": 1.0, "uv_area": (30 / 2048) ** 2}],
    }


def _observed():
    bindings = []
    materials = []
    images = []
    for slot in bind.REQUIRED_SLOTS:
        filename = bind.texture_filename(slot, "npm")
        bindings.append({"slot": slot, "material": f"M_Vatutino_Ground_{slot}", "file": filename, "size": 2048})
        materials.append({"name": bindings[-1]["material"], "maps": [{"image": filename, "socket": "Base Color", "output": "Color"}]})
        images.append({"name": filename, "size": [2048, 2048]})
    return bindings, {"materials": materials, "images": images}
