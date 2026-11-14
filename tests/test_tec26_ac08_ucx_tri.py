"""#1016: AGR Tools ucx.triangulate on the AC08 pilot-v010 VPM copy, SINTEZ before/after table (ucx_tri_core)."""
import ast
import importlib.util
import json
import math
import random
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "jobs/TEC26-OKS/scripts"
EV = ROOT / "jobs/TEC26-OKS/AC08/ucx-tri-v001"


def _load():
    spec = importlib.util.spec_from_file_location("ucx_tri_core_t", SCRIPTS / "ucx_tri_core.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


core = _load()
CUBE = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0), (0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)]
QUADS = [[0, 3, 2, 1], [4, 5, 6, 7], [0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7]]
AC08 = [(-3.031, -1.221, -2.049), (3.031, 1.221, 2.552)]  # bbox of the v010 UCX box, metres


def _box(lo, hi):
    return [(hi[0] if x else lo[0], hi[1] if y else lo[1], hi[2] if z else lo[2])
            for z in (0, 1) for (x, y) in ((0, 0), (1, 0), (1, 1), (0, 1))]


def test_v010_box_six_quads_become_twelve_convex_closed_triangles():
    got = core.triangulate_piece("UCX_SM_Nku_1_Main_001", _box(*AC08), QUADS)
    assert got["before"] == {4: 6} and got["after"] == {3: 12}
    assert got["convex"] and got["closed"] and got["vertices"] == 8 and got["action"] == "diagonals"
    assert all(0 <= v < 8 for t in got["tris"] for v in t)


def test_generated_affine_boxes_and_raised_corners_all_convex():
    """Probe: 300 random affine images of the cube (planar quads, convex) and 100 cubes with one top corner
    raised (non-planar quad, convex only with the right diagonal) -> 400/400 triangulated and convex."""
    rnd = random.Random(1016)
    ok = 0
    for i in range(400):
        if i < 300:
            m = [[rnd.uniform(-3, 3) for _ in range(3)] for _ in range(3)]
            det = (m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1]) - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
                   + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0]))
            if abs(det) < 0.5:
                m = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
            pts = [tuple(sum(m[r][k] * p[k] for k in range(3)) + 100.0 for r in range(3)) for p in CUBE]
        else:
            pts = list(CUBE)
            c = 4 + rnd.randrange(4)
            pts[c] = (pts[c][0], pts[c][1], 1 + rnd.uniform(0.05, 0.6))
        got = core.triangulate_piece(f"UCX_p{i}", pts, QUADS)
        assert got["after"] == {3: 12} and got["convex"] and got["closed"], (i, got)
        ok += 1
    assert ok == 400


@pytest.mark.parametrize("pts,polys,needle", [
    ([], QUADS, "without vertices"),
    (CUBE, [], "without vertices"),
    ([(math.nan, 0, 0)] + CUBE[1:], QUADS, "non-finite"),
    ([(math.inf, 0, 0)] + CUBE[1:], QUADS, "non-finite"),
    (CUBE, QUADS[:5], "not a closed convex"),
    (CUBE, QUADS[:5] + [[3, 0, 4, 9]], "bad polygon"),
    (CUBE, QUADS[:5] + [[3, 0]], "bad polygon"),
])
def test_fail_closed_inputs_name_the_piece(pts, polys, needle):
    with pytest.raises(ValueError, match="UCX_bad.*" + needle):
        core.triangulate_piece("UCX_bad", pts, polys)


def test_nonconvex_piece_is_refused_not_hulled():
    # top corner 6 pulled down and inward: a dented piece no diagonal can make convex
    with pytest.raises(ValueError, match="UCX_dent: not a closed convex"):
        core.triangulate_piece("UCX_dent", [(0, 0, 0), (2, 0, 0), (2, 2, 0), (0, 2, 0),
                                            (0, 0, 2), (2, 0, 2), (1, 1, 0.5), (0, 2, 2)], QUADS)


def test_check_paths_refuses_existing_alias_and_protected(tmp_path):
    src = tmp_path / "in" / "VPM_export_tri.blend"
    src.parent.mkdir()
    src.write_bytes(b"x")
    prot = tmp_path / "pilot-v010"
    prot.mkdir()
    core.check_paths([src], str(tmp_path / "new" / "SM_A"), [prot])
    for bad in (src, src.parent, prot / "SM_A", tmp_path):
        with pytest.raises(ValueError):
            core.check_paths([src], str(bad), [prot])
    assert src.read_bytes() == b"x"


def _dump(hp, lp=(("1.1", "verified"),), error=None):
    mk = lambda xs: [{"req_num": r, "name": "n" + r, "state": s, "errors": "e" + r} for r, s in xs]
    return {"error": error, "hp": mk(hp), "lp": mk(lp)}


def test_summarize_fails_closed():
    with pytest.raises(ValueError, match="checker error"):
        core.summarize(_dump([("2.3.17", "verified")], error="Traceback"))
    with pytest.raises(ValueError, match="without lp"):
        core.summarize(_dump([("2.3.17", "verified")], lp=()))
    with pytest.raises(ValueError, match="unknown state"):
        core.summarize(_dump([("2.3.17", "passed")]))


def test_diff_keeps_every_item_failed_on_either_side():
    b = core.summarize(_dump([("2.3.17", "failed"), ("2.1.1", "failed"), ("2.13.1", "verified")]))
    a = core.summarize(_dump([("2.3.17", "verified"), ("2.1.1", "failed"), ("2.13.1", "failed")]))
    rows = {r["req"]: (r["before"], r["after"]) for r in core.diff_failed(b, a)}
    assert rows == {"2.1.1": ("failed", "failed"), "2.3.17": ("failed", "not failed"),
                    "2.13.1": ("not failed", "failed")}
    assert "| VPM | total | verified/failed/undefined | 1/2/0 | 1/2/0 |" in core.table_md(b, a)


def test_committed_rerun_evidence_matches_the_v010_baseline():
    base = json.loads((ROOT / "jobs/TEC26-OKS/AC08/pilot-v010/sintez-summary.json").read_text(encoding="utf-8"))
    diff = json.loads((EV / "sintez-diff.json").read_text(encoding="utf-8"))
    assert diff["before"]["hp"] == base["hp"] == {"verified": 62, "undefined": 54, "failed": 4}
    assert diff["before"]["lp"] == base["lp"] == diff["after"]["lp"]
    assert diff["after"]["hp"] == {"verified": 63, "failed": 3, "undefined": 54}
    after_failed = {f["req"] for f in diff["after"]["failed"]["hp"]}
    assert "2.3.17" not in after_failed and not any(r.startswith("2.13") for r in after_failed)
    assert after_failed == {"2.1.1", "2.2.1", "2.10.4.1"}
    ev = json.loads((EV / "evidence.json").read_text(encoding="utf-8"))
    tri = ev["ucx_triangulate"]
    assert tri["main_mesh_identical_after_readback"] and tri["ucx_vertex_set_identical"]
    assert [p["faces_by_corners"] for p in tri["readback_v010"]] == [{"4": 6}]
    assert all(p["faces_by_corners"] == {"3": 12} and p["convex"] and p["closed"] and not p["materials"]
               and not p["uv_layers"] for p in tri["readback_after"])
    assert ev["twinqa_scene"]["ucx-tri-v001"]["V003 triangulated"][0] == "pass"
    assert ev["twinqa_scene"]["ucx-tri-v001"]["V012 UCX names"][0] == "pass"
    one = ev["one_sided_main"]
    assert one["hulls"] == len(one["readback"]) == 7
    assert all(p["closed"] and p["convex"] and p["open_edges"] == 0 for p in one["readback"])
    assert one["main_to_ucx_max_m [D134 one-sided]"] <= 0.30


def _fbx_kwargs(path, owner=None):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if owner and isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == owner:
            return {k.arg: ast.unparse(k.value) for k in node.value.keywords}
        if not owner and isinstance(node, ast.Call) and ast.unparse(node.func) == "bpy.ops.export_scene.fbx":
            return {k.arg: ast.unparse(k.value) for k in node.keywords if k.arg != "filepath"}
    raise AssertionError(path)


def test_reexport_uses_the_export_vpm_fbx_arguments():
    assert _fbx_kwargs(SCRIPTS / "ucx_triangulate_vpm.py", "FBX_ARGS") == _fbx_kwargs(SCRIPTS / "export_vpm.py")
