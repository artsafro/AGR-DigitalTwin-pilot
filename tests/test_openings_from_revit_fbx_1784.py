"""#1784 shared Revit-FBX openings step (tools/methods/body/openings_from_revit_fbx.py)."""
import json
import math
import random
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "methods" / "body"))
import openings_from_revit_fbx as m  # noqa: E402

FIX = ROOT / "tests" / "fixtures" / "revit_fbx_openings"
SCRIPT = ROOT / "tools" / "methods" / "body" / "openings_from_revit_fbx.py"
CFG = {"rules": [["WIN", "surrounds"], ["DOOR", "doors"], ["CW", "curtain"], ["EXT", "wall"],
                 ["INT", "drop", "interior wall"], ["CAGE", "inset", "rooftop cage"]],
       "interior": ["INT"]}


def rect(x0, y0, x1, y1):
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


def box_dump(extra=()):
    """20 x 10 m box, walls 0.4 m outside the line y=0 / y=10 / x=0 / x=20, interior walls inside."""
    objs = [
        {"name": "EXT_S", "z": [0, 6], "hull": rect(0, -0.4, 20, 0)},
        {"name": "EXT_N", "z": [0, 6], "hull": rect(0, 10, 20, 10.4)},
        {"name": "EXT_W", "z": [0, 6], "hull": rect(-0.4, 0, 0, 10)},
        {"name": "EXT_E", "z": [0, 6], "hull": rect(20, 0, 20.4, 10)},
        {"name": "INT_1", "z": [0, 3], "hull": rect(5, 0, 5.2, 10)},
        {"name": "INT_2", "z": [0, 3], "hull": rect(15, 0, 15.2, 10)},
        {"name": "INT_3", "z": [0, 3], "hull": rect(0, 5, 20, 5.2)},
        {"name": "WIN_S1", "z": [1, 2.5], "hull": rect(2, -0.3, 3.5, -0.1)},   # south, near x=0
        {"name": "DOOR_N1", "z": [0, 2.2], "hull": rect(16, 10.1, 17.2, 10.3)},  # north, near x=20
        {"name": "CAGE_1", "z": [6, 9], "hull": rect(8, 3, 8.2, 3.2)},
    ]
    return {"schema": "revit-fbx-dump/1", "source": "synthetic", "sha256": "0", "objects": objs + list(extra)}


def facade(doc, normal):
    return [f for f in doc["facades"] if abs((f["normal_deg"] - normal + 180) % 360 - 180) < 1.0]


def test_box_outward_normals_and_left_to_right_u():
    doc = m.extract(box_dump(), CFG)
    assert sorted(round(f["normal_deg"]) % 360 for f in doc["facades"]) == [0, 90, 180, 270]
    assert not any(f["side_tie"] for f in doc["facades"])
    s = facade(doc, 270)[0]  # south seen from outside: west (x=0) is on the left
    u = doc["spec"][s["id"]]["surrounds"][0]["rect"]
    assert u[0] == pytest.approx(2.0, abs=1e-6) and u[1] == pytest.approx(3.5, abs=1e-6) and u[2:] == [1, 2.5]
    n = facade(doc, 90)[0]  # north seen from outside: east (x=20) is on the left
    d = doc["spec"][n["id"]]["doors"][0]["rect"]
    assert d[0] == pytest.approx(20 - 17.2, abs=1e-6) and d[1] == pytest.approx(20 - 16, abs=1e-6)
    assert [i["name"] for i in doc["insets"]] == ["CAGE_1"]


def test_every_object_accounted_once_on_both_real_sources():
    for dump, cfg in (("sokolniki_east_slice.json", ROOT / "jobs" / "sokolniki-uvk1000" / "openings_config.json"),
                      ("a63A_east_slice.json", FIX / "a63A_config.json")):
        d = json.loads((FIX / dump).read_text(encoding="utf-8"))
        doc = m.extract(d, json.loads(Path(cfg).read_text(encoding="utf-8")))
        c = doc["counts"]
        assert c["in_spec"] + c["walls"] + c["insets"] + c["dropped"] == c["objects"] == len(d["objects"])
        for fs in doc["spec"].values():
            for key, items in fs.items():
                assert key in {"surrounds", "doors", "features", "grilles"}
                for it in items:
                    r = it["rect"]
                    assert all(math.isfinite(v) for v in r) and r[0] < r[1] and r[2] < r[3]


def test_sokolniki_east_facade_of_south_block():
    d = json.loads((FIX / "sokolniki_east_slice.json").read_text(encoding="utf-8"))
    cfg = json.loads((ROOT / "jobs" / "sokolniki-uvk1000" / "openings_config.json").read_text(encoding="utf-8"))
    doc = m.extract(d, cfg)
    east = [f for f in facade(doc, 0) if f["length"] > 20]
    assert len(east) == 1 and east[0]["length"] == pytest.approx(28.2, abs=0.05) and not east[0]["side_tie"]
    assert east[0]["counts"] == {"surrounds": 18, "doors": 2}


def test_63a_tower_a_east_facade():
    d = json.loads((FIX / "a63A_east_slice.json").read_text(encoding="utf-8"))
    doc = m.extract(d, json.loads((FIX / "a63A_config.json").read_text(encoding="utf-8")))
    f = [f for f in facade(doc, 8.35) if f["length"] > 4]
    assert len(f) == 1 and not f[0]["side_tie"] and f[0]["counts"] == {"surrounds": 54}
    out = [x["name"] for x in doc["dropped"] if x["why"] == "outside crop"]  # slice reaches past crop x 121
    assert out and all(n not in str(doc["spec"]) for n in out)


def test_min_rect_generated_probe():
    rnd = random.Random(1784)
    for _ in range(300):
        a = rnd.uniform(0, math.pi)
        ln, dp = rnd.uniform(0.5, 40), rnd.uniform(0.05, 0.45)
        ln, dp = max(ln, dp + 0.01), min(ln, dp)
        cx, cy = rnd.uniform(-100, 100), rnd.uniform(-100, 100)
        ux, uy = math.cos(a), math.sin(a)
        pts = [(cx + sa * ln / 2 * ux - sb * dp / 2 * uy, cy + sa * ln / 2 * uy + sb * dp / 2 * ux)
               for sa, sb in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        ang, c, L, D = m.min_rect(pts)
        assert L == pytest.approx(ln, abs=1e-6) and D == pytest.approx(dp, abs=1e-6)
        assert min(abs(ang - a), math.pi - abs(ang - a)) < 1e-6
        assert c[0] == pytest.approx(cx, abs=1e-6) and c[1] == pytest.approx(cy, abs=1e-6)


@pytest.mark.parametrize("mutate, msg", [
    (lambda d, c: d["objects"].append({"name": "ROOF_X_1234567", "z": [0, 1], "hull": rect(0, 0, 1, 1)}),
     "no rule for 1 object prefixes: \\['ROOF_X'\\]"),
    (lambda d, c: d.update(schema="other"), "schema"),
    (lambda d, c: d.update(objects=[]), "no objects"),
    (lambda d, c: c["rules"].append(["X", "drop"]), "needs a reason"),
    (lambda d, c: c["rules"].append(["", "wall"]), "must be \\[prefix"),
    (lambda d, c: c["rules"].append(["X", "window"]), "must be \\[prefix"),
    (lambda d, c: c.update(interior=["NOPE"]), "no object matches the interior"),
    (lambda d, c: c.pop("interior"), "config needs interior"),
    (lambda d, c: c.update(gap_m=float("nan")), "gap_m must be finite"),
    (lambda d, c: c.update(crop=[0, 0, 0, 1]), "crop"),
    (lambda d, c: d["objects"].append(dict(d["objects"][0])), "duplicate object names"),
    (lambda d, c: d["objects"][7].update(z=[1, float("nan")]), "WIN_S1.*z must be finite"),
    (lambda d, c: d["objects"][7].update(hull=[[2, float("inf")], [3, 0], [3, 1]]), "hull needs"),
])
def test_fail_closed(mutate, msg):
    d, c = box_dump(), json.loads(json.dumps(CFG))
    mutate(d, c)
    with pytest.raises(ValueError, match=msg):
        m.extract(d, c)


def test_empty_mesh_and_free_standing_are_reported_not_lost():
    extra = [{"name": "WIN_EMPTY", "z": None, "hull": []},
             {"name": "DOOR_FAR", "z": [0, 2], "hull": rect(50, 50, 51.2, 50.2)}]
    doc = m.extract(box_dump(extra), CFG)
    why = {d["name"]: d["why"] for d in doc["dropped"]}
    assert why["WIN_EMPTY"].startswith("no geometry") and "free-standing doors" in why["DOOR_FAR"]
    assert doc["counts"]["objects"] == 12


def test_cli_refuses_existing_or_aliased_output(tmp_path):
    dp, cp = tmp_path / "d.json", tmp_path / "c.json"
    dp.write_text(json.dumps(box_dump()), encoding="utf-8")
    cp.write_text(json.dumps(CFG), encoding="utf-8")
    before = dp.read_bytes()
    for out in (dp, cp):
        r = subprocess.run([sys.executable, str(SCRIPT), str(dp), str(cp), str(out)], capture_output=True, text=True)
        assert r.returncode == 2 and "refused" in r.stderr
    assert dp.read_bytes() == before
    out = tmp_path / "o.json"
    r = subprocess.run([sys.executable, str(SCRIPT), str(dp), str(cp), str(out)], capture_output=True, text=True)
    assert r.returncode == 0 and json.loads(out.read_text(encoding="utf-8"))["schema"] == "revit-openings/1"
    r = subprocess.run([sys.executable, str(SCRIPT), str(dp), str(cp), str(out)], capture_output=True, text=True)
    assert r.returncode == 2
    bad = tmp_path / "bad.json"
    bad.write_text('{"rules": [["WIN", "surrounds"]], "interior": ["INT"]}', encoding="utf-8")
    r = subprocess.run([sys.executable, str(SCRIPT), str(dp), str(bad), str(tmp_path / "o2.json")],
                       capture_output=True, text=True)
    assert r.returncode == 2 and "no rule for" in r.stderr and not (tmp_path / "o2.json").exists()
