"""AC08 L4 end-to-end driver (#753): fail-closed source parity, material map, pivot, delivered comparison, outputs.

Synthetic readback reports are built from the hash-pinned real AC08 Max dump (jobs/TEC26-OKS/AC08/max-dump-008.json);
they are marked synthetic: no Blender, no 3ds Max.
"""
from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
DRIVER = ROOT / "jobs" / "TEC26-OKS" / "AC08" / "l4-e2e-v001" / "run_e2e.py"
EVIDENCE = DRIVER.parent / "evidence"
_spec = importlib.util.spec_from_file_location("ac08_l4_e2e", DRIVER)
e2e = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = e2e
_spec.loader.exec_module(e2e)
InputError = e2e.InputError


@pytest.fixture(scope="module")
def dump_nodes():
    return e2e._dump_node()


def synthetic_source_report(dump_nodes):
    """SYNTHETIC readback report shaped like tools/blender/fbx_readback.py output, from the pinned dump."""
    node, ucx = dump_nodes
    names = {e["id"]: e["name"] for e in node["multisub"]}
    uvv, uvf = node["uv1"]["verts"], node["uv1"]["faces"]
    body = {"vertices": [list(map(float, v)) for v in node["vertices"]],
            "polygons": [list(f) for f in node["faces"]],
            "polygon_material": [names[i] for i in node["mat_ids"]],
            "polygon_uv": [[list(uvv[j][:2]) for j in f] for f in uvf]}
    hull = {"vertices": [list(map(float, v)) for v in ucx["vertices"]], "polygons": [list(f) for f in ucx["faces"]]}
    return {"readback_ok": True, "synthetic": True,
            "meshes": [{"name": e2e.BODY_NODE, "materials": [], "face_geometry": body},
                       {"name": e2e.UCX_NODE, "materials": [], "face_geometry": hull}]}


def delivered_from(report, offset):
    """SYNTHETIC delivered report: the source body and hull moved by `offset`, under the delivered names."""
    d = copy.deepcopy(report)
    for m, name in zip(d["meshes"], (e2e.DELIVERED_BODY, e2e.DELIVERED_UCX)):
        m["name"] = name
        m["face_geometry"]["vertices"] = (np.asarray(m["face_geometry"]["vertices"]) + offset).tolist()
    return d


def test_pinned_dump_shaped_source_passes_with_one_to_one_material_map(dump_nodes):
    rows, mat_map = e2e.source_parity(synthetic_source_report(dump_nodes))
    assert rows["passed"] and rows["polygons"] == 180 and rows["max_corner_dev_m"] == 0.0
    assert mat_map == {"Material #2": 1, "Material #4": 2, "Material #5": 3}


def _mut(report, case):
    body = report["meshes"][0]["face_geometry"]
    if case == "extra_mesh":
        report["meshes"].append({"name": "Box001", "materials": [], "face_geometry": copy.deepcopy(body)})
    elif case == "missing_ucx":
        report["meshes"].pop()
    elif case == "duplicate_mesh":
        report["meshes"].append(copy.deepcopy(report["meshes"][0]))
    elif case == "nan_vertex":
        body["vertices"][5][0] = float("nan")
    elif case == "inf_uv":
        body["polygon_uv"][3][0][0] = float("inf")
    elif case == "empty_polygons":
        body["polygons"] = []
    elif case == "partial_materials":
        body["polygon_material"] = body["polygon_material"][:-1]
    elif case == "partial_uv":
        body["polygon_uv"] = body["polygon_uv"][:-1]
    elif case == "material_missing_on_one_polygon":
        body["polygon_material"][7] = None
    elif case == "ambiguous_material":      # one name now used for two Max ids
        k = next(i for i, n in enumerate(body["polygon_material"]) if n == "Material #4")
        body["polygon_material"][k] = "Material #2"
    elif case == "renamed_material":        # name -> id is one-to-one but disagrees with the dump multisub
        body["polygon_material"] = [{"Material #2": "Material #4", "Material #4": "Material #2"}.get(n, n)
                                    for n in body["polygon_material"]]
    elif case == "polygon_dropped":
        body["polygons"].pop()
    elif case == "vertex_at_threshold":
        body["vertices"][0][2] += e2e.SOURCE_DEV_TOL_M
    elif case == "vertex_moved_2e-5":
        body["vertices"][0][2] += 2e-5
    elif case == "ucx_moved":
        report["meshes"][1]["face_geometry"]["vertices"][0][0] += 1e-3
    elif case == "readback_not_ok":
        report["readback_ok"] = False
    return report


@pytest.mark.parametrize("case", ["extra_mesh", "missing_ucx", "duplicate_mesh", "nan_vertex", "inf_uv",
                                  "empty_polygons", "partial_materials", "partial_uv",
                                  "material_missing_on_one_polygon", "ambiguous_material", "renamed_material",
                                  "polygon_dropped", "vertex_at_threshold", "vertex_moved_2e-5", "ucx_moved",
                                  "readback_not_ok"])
def test_source_parity_fails_closed(dump_nodes, case):
    with pytest.raises(InputError):
        e2e.source_parity(_mut(synthetic_source_report(dump_nodes), case))


def test_unmapped_material_in_state_is_an_error_naming_it(dump_nodes):
    rep = synthetic_source_report(dump_nodes)
    _, mat_map = e2e.source_parity(rep)
    del mat_map["Material #5"]
    with pytest.raises(InputError, match="Material #5"):
        e2e.state_from_source(rep, mat_map)


def test_every_source_polygon_lands_in_a_part(dump_nodes):
    rep = synthetic_source_report(dump_nodes)
    state, drops = e2e.state_from_source(rep, e2e.source_parity(rep)[1])
    got = sorted(k for p in state.values() for k in p["source_faces"])
    assert got == list(range(180))
    assert [d["element"] for d in drops] == [e2e.UCX_NODE]


@pytest.mark.parametrize("meta", [{}, {"pivot_revit_internal_m": [1.0, 2.0]},
                                  {"pivot_revit_internal_m": [1.0, float("nan"), 0.0]},
                                  {"pivot_revit_internal_m": "33,0,0"}])
def test_pivot_meta_fails_closed(tmp_path, meta):
    p = tmp_path / "export_meta.json"
    p.write_text(json.dumps(meta), encoding="utf-8")
    with pytest.raises((InputError, ValueError)):
        e2e.pivot_offset(p)


def _state(dump_nodes):
    rep = synthetic_source_report(dump_nodes)
    return rep, e2e.state_from_source(rep, e2e.source_parity(rep)[1])[0]


def test_delivered_comparison_passes_only_with_the_declared_pivot(dump_nodes):
    rep, state = _state(dump_nodes)
    off = np.array([-33.9534, -0.1134, 0.0])
    deliv = delivered_from(rep, off)
    ok = e2e.compare_delivered(state, rep, deliv, None, off)
    assert ok["passed"] and ok["kernel_to_delivered_max_m"] < 1e-9
    assert all(v["iou"] == 1.0 for v in ok["silhouettes"].values())
    bad = e2e.compare_delivered(state, rep, deliv, None, None)
    assert not bad["passed"] and not bad["checks"]["surface_distance"]


@pytest.mark.parametrize("dz, passed", [(0.5e-3, True), (2e-3, False)])
def test_delivered_vertex_moved_by_tolerance(dump_nodes, dz, passed):
    rep, state = _state(dump_nodes)
    deliv = delivered_from(rep, np.zeros(3))
    v = deliv["meshes"][0]["face_geometry"]["vertices"]
    k = int(np.argmax(np.asarray(v)[:, 2]))       # a roof corner: moving it changes the surface
    v[k][2] += dz
    assert e2e.compare_delivered(state, rep, deliv, None, None)["checks"]["surface_distance"] is passed


def test_delivered_wrong_mesh_names_fail(dump_nodes):
    rep, state = _state(dump_nodes)
    with pytest.raises(InputError, match="delivered FBX"):
        e2e.compare_delivered(state, rep, rep, None, None)


def test_outputs_refuse_existing_and_aliases(tmp_path):
    src = tmp_path / "in.fbx"
    src.write_bytes(b"x")
    (tmp_path / "exists").mkdir()
    with pytest.raises(InputError, match="exists"):
        e2e._require_new([src], tmp_path / "exists")
    with pytest.raises(InputError, match="alias"):
        e2e._require_new([src], tmp_path / "w", tmp_path / "w")
    nested = tmp_path / "new" / "in.fbx"           # work dir that does not exist yet but would contain an input
    with pytest.raises(InputError, match="alias"):
        e2e._require_new([nested], tmp_path / "new")
    with pytest.raises(InputError):
        e2e._require_new([src], src)


def test_cli_fresh_process_refuses_existing_work_and_writes_nothing(tmp_path):
    pkg = tmp_path / "package-vpm"
    (pkg / "SM").mkdir(parents=True)
    fbx = pkg / "SM" / "SM.fbx"
    fbx.write_bytes(b"x")
    (pkg / "export_meta.json").write_text("{}", encoding="utf-8")
    src = tmp_path / "src.fbx"
    src.write_bytes(b"y")
    work, ev = tmp_path / "work", tmp_path / "ev"
    work.mkdir()
    before = sorted(p.relative_to(tmp_path) for p in tmp_path.rglob("*"))
    p = subprocess.run([sys.executable, str(DRIVER), "--source-fbx", str(src), "--delivered-fbx", str(fbx),
                        "--work", str(work), "--evidence", str(ev)], capture_output=True, text=True, cwd=ROOT)
    assert p.returncode == 2 and "exists" in p.stderr
    assert sorted(p.relative_to(tmp_path) for p in tmp_path.rglob("*")) == before


def test_committed_evidence_is_current():
    r = json.loads((EVIDENCE / "e2e.json").read_text(encoding="utf-8"))
    assert (EVIDENCE / "e2e.md").read_text(encoding="utf-8") == e2e.markdown(r)
    assert r["gates"] == json.loads(json.dumps(e2e.gates(r)))
    assert r["inputs"][e2e._key(e2e.rko.SOURCE)] == e2e.rko.SOURCE_SHA256
    g = r["gates"]
    # the real numbers this card reports (#753): source = pinned dump, kernel refuses every op, delivered matches
    assert g["source_fbx_equals_pinned_dump"]["passed"] and g["delivered_fbx_comparison"]["passed"]
    assert not g["kernel_invariants_on_source"]["passed"] and not g["kernel_ops_applied"]["passed"]
    assert sum(bool(o["applied"]) for o in r["ops"]) == 0 and len(r["ops"]) == 19
    assert r["before_visibility"]["no_visible_back_faces"]["count"] == 3107
