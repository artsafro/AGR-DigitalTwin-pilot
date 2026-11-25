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


def stepped_dump(setback=10, thickness=0.3):
    """Synthetic podium and set-back tower with independent closed wall rings."""
    d = flagged_dump()
    for o in d["objects"]:
        o["hull"] = [[x - 80, y] for x, y in o["hull"]]
    for tag, lo, hi, z0, z1, t in (
        ("podium", 0, 40, 0, 12, 0.3), ("tower", setback, 40 - setback, 12, 18, thickness),
    ):
        for side, bounds in enumerate(((lo, lo, hi, lo + t), (lo, hi - t, hi, hi),
                                       (lo, lo, lo + t, hi), (hi - t, lo, hi, hi))):
            d["objects"].append(box(f"Базовая стена Наружная {tag} [{side}]", *bounds, z0, z1))
        d["objects"].append(box(f"Базовая крыша {tag}", lo, lo, hi, hi, z1 - 0.2, z1))
    x = 20
    for prefix in ("WB_Окно", "импост 25х100", "Системная панель Cтеклопак"):
        d["objects"].append(box(f"{prefix} [501]", x, setback, x + 1, setback + 0.2, 14, 16))
    d["objects"] += [
        box("WB_Окно [502]", x, setback, x + 1, setback + 0.2, 8, 10),
        box("WB_Окно [503]", x, 19, x + 1, 20, 14, 16),
        box("WB_Окно [504]", x, 0, x + 1, 0.2, 8, 10),
        box("Люк terrace", x, 1, x + 1, 2, 12, 12.5),
        box("Панель фасадная thick-wall centroid", x, setback + thickness / 2 - 0.05,
            x + 1, setback + thickness / 2 + 0.05, 14, 16),
    ]
    return d


@pytest.mark.parametrize("thickness", [0.3, 1.6, 1.8])
def test_stepped_facade_and_controls(rules, thickness):
    objs = {o["name"]: (o["place"], o["layer"]) for o in sp.classify(stepped_dump(thickness=thickness), rules)["objects"]}
    assert {objs[f"Базовая стена Наружная tower [{i}]"] for i in range(4)} == {("face", "BODY")}
    for prefix, layer in (("WB_Окно", "WINDOWS"), ("импост 25х100", "CURTAIN_WALL"),
                          ("Системная панель Cтеклопак", "CURTAIN_WALL")):
        assert objs[f"{prefix} [501]"] == ("face", layer)
    assert objs["WB_Окно [502]"] == objs["WB_Окно [503]"] == ("inside", "INTERIOR_OUT")
    assert objs["WB_Окно [504]"] == ("face", "WINDOWS")
    assert objs["Люк terrace"] == ("roof", "ROOF_EQUIPMENT")
    assert objs["Панель фасадная thick-wall centroid"][0] == ("face" if thickness == 0.3 else "inside")
    assert objs["Базовая стена ADSK_Внутренняя_Г_000000d"] == ("roof", "INTERIOR_OUT")
    assert objs["Базовая стена ADSK_Внутренняя_Г_000000e"] == ("roof", "BODY")
    assert objs["ADSK_КаркасНесущий_Труба_ГОСТ 302 [301]"] == ("inside", "ROOF_EQUIPMENT")


@pytest.mark.parametrize("setback", range(3, 15))
def test_stepped_facade_probe(rules, setback):
    d = stepped_dump(setback=setback)
    for o in d["objects"]:
        o["hull"] = [[150 - y, x + 100] for x, y in o["hull"]]  # rotate and translate the whole fixture
    d["objects"].reverse()
    objs = {o["name"]: o["layer"] for o in sp.classify(d, rules)["objects"]}
    assert [objs[f"{p} [501]"] for p in ("WB_Окно", "импост 25х100", "Системная панель Cтеклопак")] == [
        "WINDOWS", "CURTAIN_WALL", "CURTAIN_WALL"]
    assert [objs[f"WB_Окно [{i}]"] for i in (502, 503, 504)] == ["INTERIOR_OUT", "INTERIOR_OUT", "WINDOWS"]


def test_stepped_facade_preserves_existing_exterior_and_roof_wall(rules):
    d = stepped_dump()
    d["objects"] += [
        # Set-back shell must not suppress a known exterior on the original footprint.
        box("Панель фасадная over podium edge", 20, 0, 21, 0.2, 11.9, 12.4),
        # Uncovered terrace side of the upper ring: preserve the roof-wall/parapet rule.
        box("Базовая стена ADSK_Внутренняя_Г terrace wall", 20, 9.7, 21, 9.9, 12, 14),
    ]
    objs = {o["name"]: (o["place"], o["layer"]) for o in sp.classify(d, rules)["objects"]}
    assert objs["Панель фасадная over podium edge"] == ("face", "DECOR")
    assert objs["Базовая стена ADSK_Внутренняя_Г terrace wall"] == ("roof", "BODY")


def test_census_markdown_has_one_row_per_layer(rules):
    md = sp.census_markdown(sp.classify(synthetic_dump(), rules), rules)
    for la in rules["layers"]:
        assert f"| {la['ru']} |" in md
    assert "Неклассифицировано: 0" in md


def reference_census(census):
    return {"schema": "revit-census/1", "source_sha256": census["source_sha256"], "objects": [
        {k: o[k] for k in ("name", "family", "place", "bbox")} for o in reversed(census["objects"])
    ]}


def test_compare_v007_family_by_family(rules):
    census = sp.classify(synthetic_dump(), rules)
    comparison = sp.compare_census(census, reference_census(census))
    rows = {r["family"]: r for r in comparison["families"]}
    assert comparison["objects_matched"] == len(census["objects"])
    wall = rows["Базовая стена ADSK_Наружная_уте"]
    assert wall["count_match"] is True and wall["layers"] == {"BODY": 4, "SITE": 1}


def test_compare_v007_explains_each_exterior_to_interior_shift(rules):
    census = sp.classify(stepped_dump(), rules)
    v007 = reference_census(census)
    expected = {"WB_Окно [502]": "face", "WB_Окно [503]": "roof",
                "Базовая стена ADSK_Внутренняя_Г_000000d": "roof"}
    for old in v007["objects"]:
        old["place"] = expected.get(old["name"], old["place"])
    # Include all actual face/roof→09 rows, even when the geometric place did not change.
    names = {o["name"]: o for o in census["objects"]}
    expected.update({o["name"]: o["place"] for o in census["objects"] if o["layer"] == "INTERIOR_OUT"
                     and o["place"] in {"face", "roof"}})
    comparison = sp.compare_census(census, v007)
    shifts = comparison["face_or_roof_to_interior"]
    assert {r["name"]: r["v007_place"] for r in shifts} == expected
    assert len(shifts) == len(expected)
    md = sp.compare_markdown(comparison, rules)
    for row in shifts:
        name = row["name"]
        assert row["step0_place"] == names[name]["place"]
        assert row["step0_layer"] == "INTERIOR_OUT" and row["bbox"] == names[name]["bbox"]
        assert row["rule"] and row["reason"] and name in md


@pytest.mark.parametrize("case,diagnostic", [
    ("wrong schema", "revit-census/1"), ("stale hash", "source_sha256"),
    ("empty", "no objects"), ("missing", "inventory mismatch"),
    ("duplicate", "duplicate"), ("alternate name", "inventory mismatch"),
    ("bad place", "place"), ("NaN bbox", "bbox"), ("relocated bbox", "bbox"),
])
def test_cli_rejects_bad_reference_before_writing(rules, tmp_path, case, diagnostic):
    src, dump_path, compare_path, out = (tmp_path / n for n in ("case.fbx", "dump.json", "old.json", "fresh"))
    src.write_bytes(b"synthetic dump-only test")
    dump = synthetic_dump()
    dump["sha256"] = hashlib.sha256(src.read_bytes()).hexdigest()
    dump_path.write_text(json.dumps(dump), encoding="utf-8")
    ref = reference_census(sp.classify(dump, rules))
    rows = ref["objects"]
    if case == "wrong schema":
        ref["schema"] = "revit-census/2"
    elif case == "stale hash":
        ref["source_sha256"] = "0" * 64
    elif case == "empty":
        rows.clear()
    elif case == "missing":
        rows.pop()
    elif case == "duplicate":
        rows.append(rows[0])
    elif case == "alternate name":
        rows[0]["name"] += ".001"
    elif case == "bad place":
        rows[0]["place"] = "Face"
    elif case == "NaN bbox":
        rows[0]["bbox"][0] = math.nan
    else:
        rows[0]["bbox"][0] -= 1
    compare_path.write_text(json.dumps(ref), encoding="utf-8")
    result = _cli("prepare", str(src), "--out", str(out), "--dump", str(dump_path),
                  "--compare", str(compare_path), "--no-blend")
    assert result.returncode == 2 and diagnostic in result.stderr
    assert not out.exists() and not out.with_suffix(".partial").exists()
    assert src.read_bytes() == b"synthetic dump-only test"


def flagged_dump():
    """synthetic_dump + the three spots flagged on the Sokolniki v002 sheet (orchestrator defaults 2026-11-25)."""
    d = synthetic_dump()
    d["objects"] += [
        # (2) pergola pipe frame on the roof terrace under an upper slab -> place `inside`; ground pipe column stays out
        box("Базовая крыша ADSK_Плоская_Покр_000000c", 6, 6, 9, 9, 7.0, 7.2),
        box("ADSK_КаркасНесущий_Труба_ГОСТ 302 [301]", 6.5, 7.0, 8.5, 7.1, 4.0, 4.1),
        box("ADSK_КолоннаНесущая_Труба_ГОСТ 3 [302]", 0.1, 5.0, 0.2, 5.1, 4.0, 4.15),
        box("ADSK_КолоннаНесущая_Труба_ГОСТ 3 [303]", 7.0, 3.0, 7.1, 3.1, 0.0, 3.8),
        # (3) interior walls standing on the roof: below the parapet top (4.2) -> hidden; above it -> body
        box("Базовая стена ADSK_Внутренняя_Г_000000d", 2, 2, 2.2, 8, 4.0, 4.15),
        box("Базовая стена ADSK_Внутренняя_Г_000000e", 3, 2, 3.2, 8, 4.0, 6.0),
        # (1) curtain-wall mullion on the face
        box("Прямоугольный импост 25х100 мм [304]", 1.0, 0.0, 1.1, 0.1, 0.5, 3.0),
    ]
    return d


def test_pergola_pipes_go_with_the_pergola_and_ground_pipe_stays(rules):
    layers = {o["name"]: o["layer"] for o in sp.classify(flagged_dump(), rules)["objects"]}
    assert layers["ADSK_КаркасНесущий_Труба_ГОСТ 302 [301]"] == "ROOF_EQUIPMENT"
    assert layers["ADSK_КолоннаНесущая_Труба_ГОСТ 3 [302]"] == "ROOF_EQUIPMENT"
    assert layers["ADSK_КолоннаНесущая_Труба_ГОСТ 3 [303]"] == "INTERIOR_OUT"
    assert layers["ADSK_КолоннаНесущая_Труба_ГОСТ 3 [103]"] == "ROOF_EQUIPMENT"


def test_roof_interior_walls_split_by_parapet_top(rules):
    objs = {o["name"]: o for o in sp.classify(flagged_dump(), rules)["objects"]}
    low, high = objs["Базовая стена ADSK_Внутренняя_Г_000000d"], objs["Базовая стена ADSK_Внутренняя_Г_000000e"]
    assert low["place"] == high["place"] == "roof"
    assert low["layer"] == "INTERIOR_OUT" and low["parapet_top"] == pytest.approx(4.2)
    assert high["layer"] == "BODY"


def test_roof_wall_at_exact_parapet_top_is_hidden_and_without_parapet_is_body(rules):
    d = flagged_dump()
    d["objects"].append(box("Базовая стена ADSK_Внутренняя_Г_000000f", 4, 2, 4.2, 8, 4.0, 4.2))
    objs = {o["name"]: o for o in sp.classify(d, rules)["objects"]}
    assert objs["Базовая стена ADSK_Внутренняя_Г_000000f"]["layer"] == "INTERIOR_OUT"
    # parapet higher than parapet_max_m above the roof is a storey wall, not a parapet -> no parapet -> BODY
    d = flagged_dump()
    for o in d["objects"]:
        if "Наружная_уте_000000" in o["name"] and o["name"][-1] in "1234":
            o["z"] = [0, 4.0 + rules["envelope"]["parapet_max_m"] + 0.01]
    objs = {o["name"]: o for o in sp.classify(d, rules)["objects"]}
    assert objs["Базовая стена ADSK_Внутренняя_Г_000000d"]["layer"] == "BODY"
    assert objs["Базовая стена ADSK_Внутренняя_Г_000000d"]["parapet_top"] is None


def test_flagged_spots_are_counted_for_the_sheet(rules, tmp_path):
    census = sp.classify(flagged_dump(), rules)
    flags = {f["key"]: f for f in census["flags"]}
    assert set(flags) == {"mullions", "pergola_pipes", "roof_interior_walls"}
    assert flags["mullions"]["layers"] == {"CURTAIN_WALL": 1}
    assert flags["pergola_pipes"]["layers"] == {"ROOF_EQUIPMENT": 3}
    assert flags["roof_interior_walls"]["layers"] == {"INTERIOR_OUT": 1, "BODY": 1}
    assert all(f["ru"] for f in census["flags"])
    md = sp.census_markdown(census, rules)
    assert "## Отмечено на листе" in md
    png = sp.make_sheet(census, tmp_path / "sheet.png")
    from PIL import Image
    assert Image.open(png).size == (2400, 2060)


def test_sheet_without_flags_keeps_the_short_layout(rules, tmp_path):
    d = synthetic_dump()
    d["objects"] = [o for o in d["objects"] if "Труба" not in o["name"]]
    census = sp.classify(d, rules)
    assert all(f["count"] == 0 for f in census["flags"])
    from PIL import Image
    assert Image.open(sp.make_sheet(census, tmp_path / "s.png")).size == (2400, 1500)


def test_kpp1_family_rules_and_generics_still_decided(rules):
    """KPP1 run 2026-11-25: furniture/ceilings/roof drains/stairs/grid axes get layers; generic models stay in 00."""
    d = synthetic_dump()
    d["objects"] += [
        box("MEP_Стул_Кухонный Офисный стул T [401]", 3, 6, 3.5, 6.5, 0, 0.9),
        box("Лавки 1000х350х480 (Скамейка СК-1-1000 [402]", 15, 15, 16, 15.4, 0, 0.5),
        box("TN_ПВХ Logicroof Walkway Puzzle_1 штк ПВХ Log [403]", 4, 4, 4.5, 4.5, 4.0, 4.02),
        box("Смонтированная лестница Лест [404]", 6, 2, 8, 3, 0, 3.0),
        box("Многослойный потолок ADSK_Подве [405]", 1, 1, 9, 9, 3.0, 3.05),
        box("Ось сетки 1 [406]", 2, 2, 2.01, 8, 0, 0.01),
        box("ADSK_ОбобщеннаяМодель_Прокат_По [407]", 4, 4, 4.2, 4.2, 1, 2),
    ]
    layers = {o["name"]: o["layer"] for o in sp.classify(d, rules)["objects"]}
    assert layers["MEP_Стул_Кухонный Офисный стул T [401]"] == "INTERIOR_OUT"
    assert layers["Лавки 1000х350х480 (Скамейка СК-1-1000 [402]"] == "SITE"
    assert layers["TN_ПВХ Logicroof Walkway Puzzle_1 штк ПВХ Log [403]"] == "ROOF_EQUIPMENT"
    assert layers["Смонтированная лестница Лест [404]"] == "INTERIOR_OUT"
    assert layers["Многослойный потолок ADSK_Подве [405]"] == "INTERIOR_OUT"
    assert layers["Ось сетки 1 [406]"] == "INTERIOR_OUT"
    assert layers["ADSK_ОбобщеннаяМодель_Прокат_По [407]"] == "UNCLASSIFIED"


@pytest.mark.parametrize("mutate,msg", [
    (lambda r: r["rules"].append({"family": "X", "layer": "BODY", "below_parapet": "NOPE"}), "NOPE"),
    (lambda r: r["rules"].append({"family": "X", "layer": "BODY", "min_z0_above_base_m": float("nan")}), "min_z0"),
    (lambda r: r["rules"].append({"family": "X", "layer": "BODY", "flag": {"key": "k"}}), "flag"),
    (lambda r: r["envelope"].pop("parapet_max_m"), "parapet_max_m"),
])
def test_invalid_new_rule_keys_are_errors(tmp_path, mutate, msg):
    data = json.loads(RULES.read_text(encoding="utf-8"))
    mutate(data)
    p = tmp_path / "rules.json"
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(sp.ScenePrepareError, match=msg):
        sp.load_rules(p)


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
