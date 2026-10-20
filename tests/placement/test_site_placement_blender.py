"""DCC half of the site placement wrapper in a real background Blender (#296, opt-in `-m blender`).

Synthetic Ground and library meshes (generated here, never user files): facts -> engine -> plan -> Blender
instancing -> readback; the scene must equal the engine output, carry the seed and the run record, delete only
the proven bottom faces and sink every instance 10 cm at its pivot.
"""
import json
import subprocess
from pathlib import Path

import pytest

from dt_ai.placement import engine
from tools import placement_site as ps
from twinqa.scene import find_blender

pytestmark = pytest.mark.blender

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "blender" / "placement_instance.py"
OFFSET = [100.0, 200.0, 0.0]


def blender(*args):
    exe = find_blender()
    if exe is None:
        pytest.skip("Blender not installed")
    r = subprocess.run([exe, "--background", "--factory-startup", "--python-exit-code", "1", "--python",
                        str(SCRIPT), "--", *map(str, args)], capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]


def box(lo, hi):
    x0, y0, z0 = lo
    x1, y1, z1 = hi
    v = [[x0, y0, z0], [x1, y0, z0], [x1, y1, z0], [x0, y1, z0], [x0, y0, z1], [x1, y0, z1], [x1, y1, z1],
         [x0, y1, z1]]
    f = [[0, 3, 2, 1], [4, 5, 6, 7], [0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7]]
    return {"vertices": v, "faces": f}


def ground_mesh(n=8, size=40.0, z0=10.0, slope=0.02):
    vs, fs = [], []
    for j in range(n + 1):
        for i in range(n + 1):
            x, y = 80.0 + size * i / n, 180.0 + size * j / n
            vs.append([x, y, z0 + slope * (x - 80.0)])
    for j in range(n):
        for i in range(n):
            a = j * (n + 1) + i
            fs += [[a, a + 1, a + n + 2], [a, a + n + 2, a + n + 1]]
    return vs, fs


def test_blender_scene_equals_engine_output(tmp_path):
    vs, fs = ground_mesh()
    libs = [{"id": "TREE", "mesh": box([-1, -1, 0.5], [1, 1, 5.5]), "base_scale": 1.0},
            {"id": "BUSH", "mesh": box([-0.5, -0.5, 0], [0.5, 0.5, 0.9]), "base_scale": 1.12},
            {"id": "BENCH", "mesh": box([-0.9, -0.25, 0], [0.9, 0.25, 0.8])}]
    spec = {"libraries": libs,
            "ground": {"mesh": {"vertices": [[x - OFFSET[0], y - OFFSET[1], z - OFFSET[2]] for x, y, z in vs],
                                "faces": fs}}}
    (tmp_path / "spec.json").write_text(json.dumps(spec), encoding="utf-8")
    blender("facts", tmp_path / "spec.json", tmp_path / "facts.json")
    facts = json.loads((tmp_path / "facts.json").read_text(encoding="utf-8"))
    assert facts["BUSH"]["bbox_max"][2] == pytest.approx(0.9 * 1.12, abs=1e-5)
    assert [f["index"] for f in facts["BENCH"]["bottom_faces"]] == [0]
    lib = [ps.flora_entry("TREE", facts["TREE"], (4.5, 5.5)), ps.flora_entry("BUSH", facts["BUSH"], (1.0, 1.5)),
           ps.maf_entry("BENCH", facts["BENCH"], [1.8, 0.5, 0.8])]
    pts = [{"x": 90.0 + 3 * k, "y": 190.0 + 2 * (k % 5), "z": 0.0, "label": ["T", "B", "M"][k % 3],
            "handle": f"P{k:02d}", "inside": True, "rotation": 17.0 * k, "position": None} for k in range(9)]
    assign = {"T": "TREE", "B": "BUSH", "M": "BENCH"}
    keep, excl = ps.select_points(pts, assign)
    rep = engine.place(keep, vs, fs, lib, 4242, label_map=assign)
    plan = ps.make_plan(rep, facts, OFFSET)
    assert any(it["delete_polygons"] for it in plan["instances"])
    (tmp_path / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
    spec["run_record"] = {"seed": rep["seed"], "engine_report_sha256": ps.report_sha256(rep),
                          "input_hashes": rep["input_hashes"]}
    (tmp_path / "spec.json").write_text(json.dumps(spec), encoding="utf-8")
    blend = tmp_path / "out_v001.blend"
    blender("instance", tmp_path / "spec.json", tmp_path / "plan.json", blend, tmp_path / "rb.json")
    rb = json.loads((tmp_path / "rb.json").read_text(encoding="utf-8"))
    assert blend.is_file()
    assert ps.compare_scene(rep, rb, facts, OFFSET, tol=1e-4) == []
    assert rb["seed"] == 4242 and rb["run_record"]["engine_report_sha256"] == ps.report_sha256(rep)
    s = ps.sinking(rb, kind_of={"TREE": "flora", "BUSH": "flora", "BENCH": "maf"})
    assert s["ok"], s
    assert s["measured"] == 9
    # a second save onto the same path is refused (new versioned paths only)
    r = subprocess.run([find_blender(), "--background", "--factory-startup", "--python-exit-code", "1",
                        "--python", str(SCRIPT), "--", "instance", str(tmp_path / "spec.json"),
                        str(tmp_path / "plan.json"), str(blend), str(tmp_path / "rb2.json")],
                       capture_output=True, text=True, timeout=600)
    assert r.returncode != 0 and not (tmp_path / "rb2.json").exists()
