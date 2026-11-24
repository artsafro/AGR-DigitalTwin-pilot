"""#1867 step 0 `agr scene prepare`: split a customer Revit FBX into logical layers [D390].

Unit tests run on a synthetic `revit-fbx-dump/1` (known families and positions); the integration test builds a
small synthetic FBX in Blender 4.4 and runs the whole command (skipped when Blender 4.4 is not installed).
"""
import hashlib
import json
import math
import os
import subprocess
import sys
from pathlib import Path

import pytest

from dt_ai.intake import scene_prepare as sp

ROOT = Path(__file__).resolve().parents[1]
RULES = ROOT / "library/scene_layers/revit_layers_v001.json"
BLENDER44 = Path(os.environ.get("AGR_SCENE_BLENDER", "C:/Program Files/Blender Foundation/Blender 4.4/blender.exe"))


def box(name, x0, y0, x1, y1, z0, z1):
    return {"name": name, "verts": 8, "tris": 12, "z": [z0, z1], "hull": [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]}


def synthetic_dump():
    """10 x 10 m one-storey building (walls 0..4 m, roof deck at 4 m) plus one object of each layer."""
    objs = [
        box("Базовая стена ADSK_Наружная_уте_0000001", 0, 0, 10, 0.3, 0, 4.2),
        box("Базовая стена ADSK_Наружная_уте_0000002", 9.7, 0, 10, 10, 0, 4.2),
        box("Базовая стена ADSK_Наружная_уте_0000003", 0, 9.7, 10, 10, 0, 4.2),
        box("Базовая стена ADSK_Наружная_уте_0000004", 0, 0, 0.3, 10, 0, 4.2),
        box("Перекрытие ADSK_Перекрытие_Плит_0000005", 0, 0, 10, 10, -0.2, 0.0),
        box("Базовая крыша ADSK_Плоская_Покр_0000006", 0, 0, 10, 10, 3.8, 4.0),
        box("WB_Окно_1Створка_1Фрамуга 1100х2400 _0000007", 4, -0.05, 5.1, 0.3, 1.0, 2.4),
        box("AC_Дверь_Однопольная_Стальная 1 [100]", 6, -0.05, 7, 0.3, 0.0, 2.1),
        box("Системная панель ADSK_Cтеклопак_0000009", 1, 0.0, 2, 0.1, 0.5, 3.0),
        box("Панель фасадная 2 Фигурная [101]", 2.5, -0.3, 3.5, 0.0, 0.5, 3.5),
        box("Ограждение ADSK_Стандартное_h 1200 [102]", 3, 3, 6, 3.1, 0.0, 1.2),
        box("ADSK_КолоннаНесущая_Труба_ГОСТ 3 [103]", 5, 5, 5.1, 5.1, 4.0, 6.5),
        box("Базовая стена ADSK_Внутренняя_Г_000000a", 5, 1, 5.2, 9, 0, 3.8),
        box("Базовая стена ADSK_Наружная_уте_000000b", 20, 20, 24, 20.3, 0, 1.0),
    ]
    return {"schema": "revit-fbx-dump/1", "source": "synthetic.fbx", "sha256": "0" * 64, "objects": objs}


EXPECTED = {
    "Базовая стена ADSK_Наружная_уте_0000001": "BODY",
    "Перекрытие ADSK_Перекрытие_Плит_0000005": "BODY",
    "Базовая крыша ADSK_Плоская_Покр_0000006": "BODY",
    "WB_Окно_1Створка_1Фрамуга 1100х2400 _0000007": "WINDOWS",
    "AC_Дверь_Однопольная_Стальная 1 [100]": "DOORS",
    "Системная панель ADSK_Cтеклопак_0000009": "CURTAIN_WALL",
    "Панель фасадная 2 Фигурная [101]": "DECOR",
    "Ограждение ADSK_Стандартное_h 1200 [102]": "RAILINGS",
    "ADSK_КолоннаНесущая_Труба_ГОСТ 3 [103]": "ROOF_EQUIPMENT",
    "Базовая стена ADSK_Внутренняя_Г_000000a": "INTERIOR_OUT",
    "Базовая стена ADSK_Наружная_уте_000000b": "SITE",
}


@pytest.fixture(scope="module")
def rules():
    return sp.load_rules(RULES)


def test_rules_file_is_the_fixed_layer_list(rules):
    assert [la["id"] for la in rules["layers"]] == list(sp.LAYERS)
    assert all(la["ru"] and len(la["color"]) == 3 for la in rules["layers"])


def test_family_strips_revit_id_suffixes():
    assert sp.family_of("Базовая стена ADSK_Внутренняя_Г_295225a") == "Базовая стена ADSK_Внутренняя_Г"
    assert sp.family_of("Прямоугольный импост 50х100 мм [1844810]") == "Прямоугольный импост 50х100 мм"
    assert sp.family_of("Ограждение ADSK_МГН_h 900 [2275445]_[16826].002") == "Ограждение ADSK_МГН_h 900 [2275445]_[16826]"


def test_classify_known_layers(rules):
    census = sp.classify(synthetic_dump(), rules)
    got = {o["name"]: o["layer"] for o in census["objects"]}
    for name, layer in EXPECTED.items():
        assert got[name] == layer, name
    assert census["unclassified"] == []
    assert sum(la["count"] for la in census["layers"]) == len(synthetic_dump()["objects"])
    assert [la["id"] for la in census["layers"]] == list(sp.LAYERS)


def test_unmatched_family_is_unclassified_and_listed(rules):
    dump = synthetic_dump()
    dump["objects"].append(box("Скамья_парковая_0000abc", 30, 30, 31, 31, 0, 0.5))
    census = sp.classify(dump, rules)
    assert census["unclassified"] == [{"name": "Скамья_парковая_0000abc", "family": "Скамья_парковая"}]
    layer = {la["id"]: la for la in census["layers"]}["UNCLASSIFIED"]
    assert layer["count"] == 1 and layer["families"] == [{"family": "Скамья_парковая", "count": 1}]


def test_object_without_geometry_goes_to_drop_list(rules):
    dump = synthetic_dump()
    dump["objects"].append({"name": "WB_Окно_пустое_0000abd", "verts": 0, "tris": 0, "z": None, "hull": []})
    census = sp.classify(dump, rules)
    assert census["dropped"] == [{"name": "WB_Окно_пустое_0000abd", "reason": "no_geometry"}]
    assert sum(la["count"] for la in census["layers"]) + len(census["dropped"]) == len(dump["objects"])


@pytest.mark.parametrize("bad", [
    {"z": [float("nan"), 1.0]}, {"z": [0.0, float("inf")]}, {"hull": [[0, 0], [float("nan"), 1], [1, 1]]},
    {"z": [2.0, 1.0]}, {"z": [1.0]}, {"hull": [[0, 0]]},
])
def test_malformed_record_is_an_error_naming_it(rules, bad):
    dump = synthetic_dump()
    rec = dict(box("WB_Окно_битое_0000abe", 4, 0, 5, 0.3, 1, 2), **bad)
    dump["objects"].append(rec)
    with pytest.raises(sp.ScenePrepareError, match="WB_Окно_битое_0000abe"):
        sp.classify(dump, rules)


def test_duplicate_object_name_is_an_error(rules):
    dump = synthetic_dump()
    dump["objects"].append(dict(dump["objects"][0]))
    with pytest.raises(sp.ScenePrepareError, match="duplicate"):
        sp.classify(dump, rules)


def test_empty_or_wrong_schema_dump_is_an_error(rules):
    with pytest.raises(sp.ScenePrepareError, match="no objects"):
        sp.classify({"schema": "revit-fbx-dump/1", "sha256": "0", "objects": []}, rules)
    with pytest.raises(sp.ScenePrepareError, match="schema"):
        sp.classify({"schema": "revit-obb/1", "objects": synthetic_dump()["objects"]}, rules)


def test_no_envelope_family_is_an_error(rules):
    dump = synthetic_dump()
    dump["objects"] = [o for o in dump["objects"] if "Наружная" not in o["name"] and "Перекрытие" not in o["name"]
                       and "крыша" not in o["name"]]
    with pytest.raises(sp.ScenePrepareError, match="envelope"):
        sp.classify(dump, rules)


@pytest.mark.parametrize("mutate,msg", [
    (lambda r: r["rules"].append({"family": "X", "layer": "NOPE"}), "NOPE"),
    (lambda r: r["rules"].append({"family": "X", "by_place": {"inside": "BODY", "face": "BODY", "roof": "BODY"}}), "out"),
    (lambda r: r["rules"].append({"family": "(", "layer": "BODY"}), "regex"),
    (lambda r: r["rules"].append({"family": "X", "layer": "BODY", "by_place": {}}), "exactly one"),
    (lambda r: r["layers"].pop(), "layers"),
    (lambda r: r["rules"].append({"family": "X", "layer": "UNCLASSIFIED"}), "UNCLASSIFIED"),
])
def test_invalid_rules_file_is_an_error(tmp_path, mutate, msg):
    data = json.loads(RULES.read_text(encoding="utf-8"))
    mutate(data)
    p = tmp_path / "rules.json"
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(sp.ScenePrepareError, match=msg):
        sp.load_rules(p)


def test_place_thresholds_are_exact(rules):
    """face band is strict `< face_m` of the footprint boundary (same as census_v007 FACE_M)."""
    face_m = rules["envelope"]["face_m"]
    dump = synthetic_dump()
    # centroid exactly face_m outside the outer face x=10 -> out; just inside the band -> face
    dump["objects"].append(box("Панель фасадная 2 Фигурная [201]", 10 + face_m - 0.05, 4, 10 + face_m + 0.05, 5, 1, 2))
    dump["objects"].append(box("Панель фасадная 2 Фигурная [202]", 10 + face_m - 0.06, 6, 10 + face_m + 0.04, 7, 1, 2))
    places = {o["name"]: o["place"] for o in sp.classify(dump, rules)["objects"]}
    assert places["Панель фасадная 2 Фигурная [201]"] == "out"
    assert places["Панель фасадная 2 Фигурная [202]"] == "face"


def test_census_markdown_has_one_row_per_layer(rules):
    md = sp.census_markdown(sp.classify(synthetic_dump(), rules), rules)
    for la in rules["layers"]:
        assert f"| {la['ru']} |" in md
    assert "Неклассифицировано: 0" in md


def test_compare_v007_family_by_family(rules):
    census = sp.classify(synthetic_dump(), rules)
    v007 = {"schema": "revit-census/1", "families": [
        {"family": "Базовая стена ADSK_Наружная_уте", "count": 5},
        {"family": "Нет такой", "count": 2}]}
    rows = {r["family"]: r for r in sp.compare_census(census, v007)}
    assert rows["Базовая стена ADSK_Наружная_уте"]["count_match"] is True
    assert rows["Нет такой"]["count_match"] is False and rows["Нет такой"]["layers"] == {}


def _cli(*args):
    return subprocess.run([sys.executable, "-m", "dt_ai.intake.scene_prepare", *map(str, args)],
                          capture_output=True, text=True, encoding="utf-8", cwd=ROOT)


def test_cli_refuses_existing_out_and_out_equal_to_source(tmp_path):
    src = tmp_path / "a.fbx"
    src.write_bytes(b"fbx")
    (tmp_path / "out").mkdir()
    r = _cli("prepare", src, "--out", tmp_path / "out")
    assert r.returncode == 2 and "exists" in r.stderr
    r = _cli("prepare", src, "--out", src)
    assert r.returncode == 2
    assert src.read_bytes() == b"fbx" and not (tmp_path / "out.partial").exists()


def test_cli_refuses_dump_of_another_source(tmp_path):
    src = tmp_path / "a.fbx"
    src.write_bytes(b"fbx")
    dump = tmp_path / "dump.json"
    dump.write_text(json.dumps(synthetic_dump()), encoding="utf-8")
    r = _cli("prepare", src, "--out", tmp_path / "o", "--dump", dump, "--no-blend")
    assert r.returncode == 2 and "sha256" in r.stderr
    assert not (tmp_path / "o").exists()


def test_cli_dump_only_path_writes_census(tmp_path):
    src = tmp_path / "a.fbx"
    src.write_bytes(b"fbx")
    d = synthetic_dump()
    d["sha256"] = hashlib.sha256(b"fbx").hexdigest()
    dump = tmp_path / "dump.json"
    dump.write_text(json.dumps(d), encoding="utf-8")
    out = tmp_path / "o"
    r = _cli("prepare", src, "--out", out, "--dump", dump, "--no-blend")
    assert r.returncode == 0, r.stderr
    census = json.loads((out / "census.json").read_text(encoding="utf-8"))
    assert census["schema"] == "agr-scene-census/1" and census["unclassified"] == []
    assert (out / "census.md").is_file() and (out / "sheet.png").is_file()
    assert not Path(str(out) + ".partial").exists()


def test_agr_facade_routes_scene_prepare():
    r = subprocess.run([sys.executable, "-m", "dt_ai.cli.agr", "scene", "--help"], capture_output=True, text=True,
                       encoding="utf-8", cwd=ROOT)
    assert r.returncode == 0 and "prepare" in r.stdout


SYNTH_FBX_SCRIPT = r'''
import bpy, sys, json
argv = sys.argv[sys.argv.index("--") + 1:]
spec, out = json.load(open(argv[0], encoding="utf-8")), argv[1]
bpy.ops.wm.read_factory_settings(use_empty=True)
for o in spec:
    x0, y0 = o["hull"][0]; x1, y1 = o["hull"][2]; z0, z1 = o["z"]
    bpy.ops.mesh.primitive_cube_add(size=1, location=((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2))
    ob = bpy.context.active_object
    ob.scale = (x1 - x0, y1 - y0, z1 - z0)
    ob.name = o["name"]
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
bpy.ops.export_scene.fbx(filepath=out, use_selection=False, apply_unit_scale=True, bake_space_transform=False)
'''


@pytest.mark.skipif(not BLENDER44.is_file(), reason="Blender 4.4 not installed")
def test_end_to_end_on_synthetic_fbx(tmp_path):
    spec = tmp_path / "spec.json"
    spec.write_text(json.dumps(synthetic_dump()["objects"], ensure_ascii=False), encoding="utf-8")
    script = tmp_path / "mk.py"
    script.write_text(SYNTH_FBX_SCRIPT, encoding="utf-8")
    fbx = tmp_path / "synthetic.fbx"
    subprocess.run([str(BLENDER44), "-b", "--factory-startup", "--python-exit-code", "1", "--python", str(script),
                    "--", str(spec), str(fbx)], check=True, capture_output=True)
    before = hashlib.sha256(fbx.read_bytes()).hexdigest()
    out = tmp_path / "prep"
    r = _cli("prepare", fbx, "--out", out, "--blender", BLENDER44)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]
    assert hashlib.sha256(fbx.read_bytes()).hexdigest() == before
    census = json.loads((out / "census.json").read_text(encoding="utf-8"))
    got = {o["name"]: o["layer"] for o in census["objects"]}
    for name, layer in EXPECTED.items():
        assert got[name] == layer, name
    blend = json.loads((out / "blend_report.json").read_text(encoding="utf-8"))
    assert blend["collections"]["WINDOWS"] == 1 and blend["missing"] == [] and blend["unassigned"] == []
    assert sum(blend["collections"].values()) == len(EXPECTED) + 3
    for f in ("scene_layers.blend", "sheet.png", "census.md", "dump.json"):
        assert (out / f).is_file(), f
    assert not math.isnan(census["envelope"]["area_m2"])
