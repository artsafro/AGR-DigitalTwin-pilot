"""#1416 [D308]: fail-closed probes for the KPP1 Ground copy v003 plan (names, bridge, output paths)."""
import importlib.util
import json
import math
import random
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "ground_copy_plan", ROOT / "jobs/KPP1/ground-budget-1416/ground_copy_plan.py")
plan = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(plan)
MAPPING = ROOT / "jobs/KPP1/delivered-1371/mapping.json"


def test_customer_names_map_to_v012_grammar():
    names = ["SM_77_05_0009005_117_Flora", "SM_77_05_0009005_117_Ground", "SM_77_05_0009005_117_GroundEl"]
    assert plan.rename_map(names) == {n: "SM_Kpp_1_" + n.rsplit("_", 1)[1] for n in names}


@pytest.mark.parametrize("bad", ["SM_77_05_0009005_117_Tree", "SM_Other_Ground", "Flora", "SM_77_05_0009005_117_"])
def test_unmapped_name_is_an_error_naming_it(bad):
    with pytest.raises(plan.PlanError, match=bad):
        plan.rename_map(["SM_77_05_0009005_117_Ground", bad])


def test_empty_or_duplicated_names_fail():
    with pytest.raises(plan.PlanError):
        plan.rename_map([])
    with pytest.raises(plan.PlanError):
        plan.rename_map(["SM_77_05_0009005_117_Ground"] * 2)


def test_bridge_row_and_column_forms_agree_and_land_kpp_on_r1():
    rot, t = plan.load_bridge(MAPPING)
    col = plan.column_matrix(rot, t)
    rng = random.Random(1416)
    for _ in range(200):
        p = [rng.uniform(-250, 250), rng.uniform(-150, 150), rng.uniform(-5, 40)]
        a = plan.apply_bridge(p, rot, t)
        b = [sum(col[j][k] * p[k] for k in range(3)) + col[j][3] for j in range(3)]
        assert max(abs(x - y) for x, y in zip(a, b)) < 1e-9
    # KPP local centre (#1371 REPORT: X 82.784..116.019, Y 85.002..101.308) -> R1 absolute X~8056, Y~-9581
    x, y, _ = plan.apply_bridge([99.4, 93.2, 0.0], rot, t)
    assert 8040 < x < 8075 and -9600 < y < -9570


@pytest.mark.parametrize("mutate", ["nan", "inf", "mirror", "short", "skew"])
def test_bad_bridge_fails_closed(tmp_path, mutate):
    data = json.loads(MAPPING.read_text(encoding="utf-8"))
    fb = data["frame_bridge"]
    if mutate == "nan":
        fb["translation"][0] = math.nan
    elif mutate == "inf":
        fb["rotation_row"][1][1] = math.inf
    elif mutate == "mirror":
        fb["rotation_row"][2] = [-x for x in fb["rotation_row"][2]]
    elif mutate == "short":
        fb["translation"] = fb["translation"][:2]
    else:
        fb["rotation_row"][0][1] += 0.01
    p = tmp_path / "m.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises((plan.PlanError, ValueError)):
        plan.load_bridge(p)


def test_output_dir_guards(tmp_path):
    src = tmp_path / "in" / "g.fbx"
    src.parent.mkdir()
    src.write_bytes(b"x")
    for bad in (src, src.parent, src.parent / "sub"):
        with pytest.raises(plan.PlanError):
            plan.check_out_dir(str(bad), [str(src)])
    (tmp_path / "old").mkdir()
    (tmp_path / "new.partial").mkdir()
    for bad in ("old", "new"):
        with pytest.raises(plan.PlanError):
            plan.check_out_dir(str(tmp_path / bad), [str(src)])
    assert plan.check_out_dir(str(tmp_path / "fresh"), [str(src)]).endswith("fresh")
    assert src.read_bytes() == b"x"
