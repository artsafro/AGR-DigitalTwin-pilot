"""#298 review P1-1: the MAF (#185) and Flora (#191) checks get their inputs (synthetic data)."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("site_scene_checks", ROOT / "jobs/VATUTINO-SITE/scene_checks.py")
sc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sc)

META = {"LIB_MAF": {"kind": "maf", "spec": [1.8, 0.5, 0.72]},
        "LIB_GEN": {"kind": "maf", "spec": None, "spec_raw": "generated"},
        "Tree_NPM": {"kind": "flora", "h_m": [5.0, 5.5], "base_scale": 1.02},
        "Bush_NPM": {"kind": "flora", "h_m": [1.0, 2.0], "base_scale": 1.0}}
INST = [{"name": "LIB_MAF__A1", "library_id": "LIB_MAF"}, {"name": "LIB_GEN__B2", "library_id": "LIB_GEN"},
        {"name": "Tree_NPM__C3", "library_id": "Tree_NPM"}, {"name": "Bush_NPM__D4", "library_id": "Bush_NPM"},
        {"name": "X__E5", "library_id": "UNKNOWN"}]


def test_build_inputs_names_match_the_check_tokens():
    rename, flora, maf, gaps = sc.build_inputs(INST, META, {"Tree_NPM": 4.0})
    assert rename["LIB_MAF__A1"] == "LIB_MAF__A1_GroundEl"            # is_groundel: suffix _GroundEl
    assert rename["Tree_NPM__C3"] == "Flora_Tree_NPM__C3"              # is_flora: token Flora_
    assert maf == {"LIB_MAF__A1_GroundEl": [1.8, 0.5, 0.72]}           # no spec -> not in maf_sizes
    assert flora == {"Flora_Tree_NPM__C3": {"height_m": 5.25, "crown_m": 4.08}}
    assert any("LIB_GEN" in g for g in gaps) and any("Bush_NPM" in g for g in gaps)
    assert any("UNKNOWN" in g for g in gaps) and "X__E5" not in rename


def test_inputs_feed_the_twinqa_checks_to_a_verdict():
    """With the inputs, Flora dimensions and MAF sizes give pass/fail, not 'no planting schedule supplied'."""
    from twinqa.flora import dimension_findings
    from twinqa.maf_checks import maf_findings
    _, flora, maf, _ = sc.build_inputs(INST, META, {"Tree_NPM": 4.0})
    meshes = [{"name": "Flora_Tree_NPM__C3", "bounds_m": [[0, 0, -0.1], [4.0, 4.0, 5.2]], "triangles": 10},
              {"name": "LIB_MAF__A1_GroundEl", "bounds_m": [[0, 0, -0.1], [1.8, 0.5, 0.62]], "triangles": 10}]
    dims = dimension_findings(meshes, flora, "x.fbx")
    assert [f.status for f in dims] == ["pass"]
    sizes = [f for f in maf_findings(meshes, "ground", "x.fbx", maf_sizes=maf) if "specification" in f.name]
    assert sizes and sizes[0].status in ("pass", "fail")


def test_tables_count_band_and_tolerance():
    rename, flora, maf, _ = sc.build_inputs(INST, META, {"Tree_NPM": 4.0})
    meshes = [{"name": "Flora_Tree_NPM__C3", "bounds_m": [[0, 0, 0], [4.0, 4.0, 5.3]]},       # h 5.2 in band
              {"name": "LIB_MAF__A1_GroundEl", "bounds_m": [[0, 0, 0], [0.5, 2.0, 0.72]]}]    # plan off 0.2 m
    ft = sc.flora_table(meshes, flora, rename, INST, META)
    assert ft[0]["n"] == 1 and ft[0]["in_band"] == 1 and ft[0]["within_20pct"] == 1
    mt = sc.maf_table(meshes, maf, rename, INST)
    assert mt[0]["over_tol"] == 1 and mt[0]["max_plan_dev_m"] == 0.2 and mt[0]["max_z_dev_m"] == 0.0
