"""#1336: KPP1 openings extractor matches glass names spelling-robustly and reports every dropped object.

Synthetic fixture (not KPP1 data): one south surround with one curtain bay; object names mimic Revit FBX names.
"""
import importlib.util
import itertools
import json
import random
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "jobs/KPP1/scripts/extract_openings.py"
FT = 0.3048
LAT_C, CYR_S = "Cтеклопакет", "Стеклопакет"  # first letter U+0043 vs U+0421


def _load():
    spec = importlib.util.spec_from_file_location("kpp1_extract_openings", SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _bb(lo, hi):
    return {"min": dict(zip("xyz", (v / FT for v in lo))), "max": dict(zip("xyz", (v / FT for v in hi)))}


def _obj(name, lo, hi):
    return {"name": name, "min": list(lo), "max": list(hi)}


def _write(tmp_path, curtain, openings=()):
    src, cen = tmp_path / "src", tmp_path / "census"
    src.mkdir()
    cen.mkdir()
    side = {"types": [{"instances": [
        {"elementId": 10, "type": "ADSK_Обрамление витражей_1", "boundingBox": _bb((1, -0.4, 0), (5, 0.2, 3))},
        {"elementId": 11, "type": "ADSK_Витраж_Без разрезки", "boundingBox": _bb((1.1, -0.35, 0.1), (4.9, 0.1, 2.9))},
    ]}]}
    (src / "curtain.export.json").write_text(json.dumps(side, ensure_ascii=False), encoding="utf-8")
    (cen / "curtain.objects.json").write_text(json.dumps(list(curtain), ensure_ascii=False), encoding="utf-8")
    (cen / "openings.objects.json").write_text(json.dumps(list(openings), ensure_ascii=False), encoding="utf-8")
    return src, cen


def _run(tmp_path, curtain, openings=()):
    src, cen = _write(tmp_path, curtain, openings)
    _load().main(str(src), str(cen))
    spec = json.loads((cen / "openings_spec.json").read_text(encoding="utf-8"))
    drops = cen / "openings_dropped.json"
    dropped = json.loads(drops.read_text(encoding="utf-8")) if drops.exists() else None
    return spec, dropped


def _glass(name, i):
    x = 1.2 + 0.5 * i
    return _obj(name, (x, -0.3, 0.2), (x + 0.4, -0.29, 1.5))


def _bay(spec):
    return spec["S"]["surrounds"][0]["bays"][0]


def test_both_spellings_of_glass_are_kept(tmp_path):
    spec, _ = _run(tmp_path, [_glass(LAT_C + " 1200_abcdef1", 0), _glass(CYR_S + " 1200 [123]", 1)])
    assert len(_bay(spec)["glass"]) == 2


def test_unknown_family_in_bay_is_reported_not_skipped(tmp_path):
    spec, dropped = _run(tmp_path, [_glass(CYR_S + " A", 0), _glass("Неизвестное семейство X", 1)])
    assert len(_bay(spec)["glass"]) == 1
    assert [d["name"] for d in dropped] == ["Неизвестное семейство X"]
    assert "unknown family" in dropped[0]["reason"] and "11" in dropped[0]["reason"]


def test_homoglyph_mixes_generated(tmp_path):
    """Probe: every Latin/Cyrillic mix of the homoglyph letters in 'Стеклопакет' is glass."""
    rng = random.Random(1336)
    lat = {"С": "C", "е": "e", "о": "o", "а": "a", "к": "k", "Т": "T", "т": "t"}
    names = set()
    for _ in range(64):
        names.add("".join(lat[c] if c in lat and rng.random() < 0.5 else c for c in CYR_S))
    names |= {LAT_C, CYR_S, CYR_S.upper(), CYR_S.lower()}
    for i, n in enumerate(sorted(names)):
        d = tmp_path / str(i)
        d.mkdir()
        spec, dropped = _run(d, [_glass(n + " 1", 0)])
        assert len(_bay(spec)["glass"]) == 1, n
        assert dropped == [], n


def test_every_object_is_output_or_dropped(tmp_path):
    curtain = [
        _glass(LAT_C, 0), _glass(CYR_S, 1),
        _obj("MEP_Окно AGS68_0123abc", (3.0, -0.3, 0.2), (3.8, -0.2, 1.5)),
        _obj("Прямоугольный импост 200х75 [5]", (1.0, -0.3, 0.0), (1.05, -0.2, 3.0)),
        _obj("Панель X", (20, 5, 0), (21, 6, 1)),  # no facade
        _obj("Панель Y", (10, -0.3, 0), (11, -0.2, 1)),  # facade S, no surround
        _obj("Прочее Z", (1.0, -0.3, 2.95), (1.05, -0.2, 3.0)),  # in surround, outside every bay, not a mullion
    ]
    openings = [_obj("ADSK_Дверь_Двупольная [7]", (6, -0.3, 0), (7.5, -0.2, 2.1)),
                _obj("MEP_Веза_Р50 [8]", (8, -0.3, 1), (8.5, -0.2, 1.5))]
    spec, dropped = _run(tmp_path, curtain, openings)
    s = spec["S"]
    used = (len(_bay(spec)["glass"]) + len(_bay(spec)["windows"]) + len(s["surrounds"][0]["mullions"])
            + len(s["doors"]) + len(s["grilles"]))
    assert used == 6
    assert sorted(d["name"] for d in dropped) == ["Панель X", "Панель Y", "Прочее Z"]
    assert all(d["reason"] for d in dropped)
    assert used + len(dropped) == len(curtain) + len(openings)


def test_empty_dumps_give_empty_bays_and_no_drops(tmp_path):
    spec, dropped = _run(tmp_path, [])
    assert _bay(spec) == {"id": 11, "rect": [1.1, 4.9, 0.1, 2.9], "windows": [], "glass": []}
    assert dropped == []


def test_duplicate_bays_and_wrong_depth_are_explicit_drops(tmp_path):
    curtain = [_glass(CYR_S, 0), _obj(CYR_S + ' deep', (2, -.1, .2), (2.4, .5, 1.5))]
    src, cen = _write(tmp_path, curtain)
    source = src / 'curtain.export.json'
    side = json.loads(source.read_text(encoding='utf-8'))
    bay = dict(side['types'][0]['instances'][1], elementId=12)
    side['types'][0]['instances'].append(bay)
    source.write_text(json.dumps(side), encoding='utf-8')
    _load().main(str(src), str(cen))
    spec = json.loads((cen / 'openings_spec.json').read_text(encoding='utf-8'))
    drops = json.loads((cen / 'openings_dropped.json').read_text(encoding='utf-8'))
    assert sum(len(b['glass']) for s in spec['S']['surrounds'] for b in s['bays']) == 0
    assert len(drops) == 2
    assert 'multiple bays in 3D' in drops[0]['reason']
    assert 'no bay in 3D' in drops[1]['reason']


def test_duplicated_source_object_is_an_error(tmp_path):
    import pytest
    obj = _glass(CYR_S, 0)
    src, cen = _write(tmp_path, [obj, obj])
    with pytest.raises(ValueError, match='duplicate.*object'):
        _load().extract(str(src), str(cen))


def test_nonfinite_object_cannot_hide_as_outside_facade(tmp_path):
    import pytest
    for value, suffix in ((float('nan'), 'nan'), (float('inf'), 'inf')):
        root = tmp_path / suffix
        root.mkdir()
        malformed = _obj('Unknown', (value, value, value), (value, value, value))
        src, cen = _write(root, [_glass(CYR_S, 0), malformed])
        with pytest.raises(ValueError, match='Unknown'):
            _load().extract(str(src), str(cen))


def test_norm_maps_only_homoglyphs():
    mod = _load()
    assert mod.norm(LAT_C) == mod.norm(CYR_S) == "стеклопакет"
    assert mod.norm("Z") == "z" and mod.norm("ADSK") == mod.norm("АDSК")
    assert all(mod.norm(a) != mod.norm(b) for a, b in itertools.combinations(["Окно", "Дверь", "Стекло"], 2))
