"""Point-domain band height and opt-in z0 snap for the building-body GN writer.

Recorded on TOW02 (Blender 5.1.2, experiments/body-gn-full-snap-edge-locator-rerun):
self-intersect unbalanced edges are 7 (face domain, no snap), 3 (face domain, full snap)
and 0 (point domain, full snap). The face domain stays the default until a TOW02
export/readback passes.

Flags: height_domain "face"|"point" (default "face"); z0_snap "off"|"on" (default "off").
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
from collections import defaultdict
from pathlib import Path

import pytest

np = pytest.importorskip("numpy")

ROOT = Path(__file__).resolve().parents[2]
CONTOURS_PY = ROOT / "tools" / "methods" / "body" / "contours.py"
BODY_BLENDER_PY = ROOT / "tools" / "methods" / "body" / "body_blender.py"
TOW02_CONTOURS = Path(r"C:/x/methods/building-body/tow02/contours.json")
TOW02_SNAP = Path(r"C:/x/t_ad9bc345/snapped_contours.json")
TOW02_SHA256 = "92a83fc90efd039126f8b86b57ff7fae1002bea72868d7193e27b2904535152e"
SNAP_SHA256 = "21bbc3e2422c409ed2a24b9fbede247274340589b3837ab83172f92d7fecc532"
SCRATCH = Path(r"C:/x/t_636d03d6")
PROBE_N = 200
BLENDER_DEFAULT = Path(r"C:/Program Files/Blender Foundation/Blender 5.1/blender.exe")

BLENDER_SCRIPT = r"""
import json, sys, traceback
from collections import defaultdict
from pathlib import Path

import bpy
import numpy as np

ROOT = Path(__ROOT__)
OUT = Path(sys.argv[sys.argv.index("--") + 1])
BODY = ROOT / "tools" / "methods" / "body" / "body_blender.py"


def load_body_blender():
    lines = BODY.read_text(encoding="utf-8").splitlines()
    while lines and not lines[-1].strip():
        lines.pop()
    if lines and lines[-1].strip() == "main()":
        lines.pop()
    while lines and not lines[-1].strip():
        lines.pop()
    if lines and lines[-1].strip() == 'if __name__ == "__main__":':
        lines.pop()
    ns = {"__name__": "body_blender_lib", "__file__": str(BODY)}
    exec(compile("\n".join(lines) + "\n", str(BODY), "exec"), ns)
    return ns


def read_co32(me):
    arr = np.zeros(len(me.vertices) * 3, dtype=np.float32)
    me.vertices.foreach_get("co", arr)
    return arr.reshape(-1, 3)


def eval_tap(bb, me, height_domain, tap):
    cme = me.copy()
    obj = bpy.data.objects.new("tap", cme)
    bpy.context.scene.collection.objects.link(obj)
    ng = bb["_gn_tree"](height_domain=height_domain, tap=tap)
    if tap == "extrude":
        ext = next(n for n in ng.nodes if n.bl_idname == "GeometryNodeExtrudeMesh")
        st = ng.nodes.new("GeometryNodeStoreNamedAttribute")
        st.data_type = "BOOLEAN"
        st.domain = "FACE"
        st.inputs["Name"].default_value = "is_top"
        sp = next((n for n in ng.nodes if n.bl_idname == "GeometryNodeSetPosition"), None)
        if sp is not None:
            link = sp.inputs["Geometry"].links[0]
            src = link.from_socket
            ng.links.remove(link)
            ng.links.new(src, st.inputs["Geometry"])
            ng.links.new(ext.outputs["Top"], st.inputs["Value"])
            ng.links.new(st.outputs["Geometry"], sp.inputs["Geometry"])
        else:
            gout = next(n for n in ng.nodes if n.bl_idname == "NodeGroupOutput")
            link = gout.inputs[0].links[0]
            src = link.from_socket
            ng.links.remove(link)
            ng.links.new(src, st.inputs["Geometry"])
            ng.links.new(ext.outputs["Top"], st.inputs["Value"])
            ng.links.new(st.outputs["Geometry"], gout.inputs[0])
    obj.modifiers.new("tap", "NODES").node_group = ng
    ev = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    m = ev.to_mesh()
    coords = [tuple(v.co) for v in m.vertices]
    polys = [list(p.vertices) for p in m.polygons]
    co32 = read_co32(m)
    is_top = band = None
    if tap == "extrude":
        is_top = np.zeros(len(m.polygons), dtype=bool)
        band = np.zeros(len(m.polygons), dtype=np.int32)
        m.attributes["is_top"].data.foreach_get("value", is_top)
        m.attributes["band_id"].data.foreach_get("value", band)
    ev.to_mesh_clear()
    bpy.data.objects.remove(obj)
    bpy.data.meshes.remove(cme)
    bpy.data.node_groups.remove(ng)
    return coords, polys, co32, is_top, band


def unbalanced(coords, polys):
    tot = defaultdict(int)
    for p in polys:
        for i in range(len(p)):
            a, b = p[i], p[(i + 1) % len(p)]
            k = (a, b) if a < b else (b, a)
            tot[k] += 1 if a < b else -1
    return sum(1 for v in tot.values() if v != 0)


def self_intersect(coords, polys):
    me = bpy.data.meshes.new("weld_copy")
    me.from_pydata([tuple(c) for c in coords], [], polys)
    obj = bpy.data.objects.new("weld_copy", me)
    bpy.context.scene.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.intersect(mode="SELECT", separate_mode="NONE", solver="EXACT")
    bpy.ops.object.mode_set(mode="OBJECT")
    out_coords = [tuple(v.co) for v in obj.data.vertices]
    out_polys = [list(p.vertices) for p in obj.data.polygons]
    bpy.data.objects.remove(obj)
    bpy.data.meshes.remove(me)
    return out_coords, out_polys


def point_top(z0, z1):
    return np.float32(np.float32(z0) + np.float32(float(z1) - float(z0)))


def measure_tops(bb, contours, height_domain):
    me, ids = bb["_build_cap"](contours, "cap", height_domain=height_domain)
    me.attributes.new("band_id", "INT", "FACE").data.foreach_set("value", ids)
    _coords, _polys, co32, is_top, band = eval_tap(bb, me, height_domain, "extrude")
    bpy.data.meshes.remove(me)
    bands_out = []
    for bi, b in enumerate(contours["bands"]):
        zs = {}
        n = 0
        for fi, p in enumerate(_polys):
            if not is_top[fi] or int(band[fi]) != bi:
                continue
            for v in p:
                key = co32[v, 2].tobytes()
                zs[key] = zs.get(key, 0) + 1
                n += 1
        expect = point_top(b["z0"], b["z1"])
        bands_out.append({
            "band": bi,
            "n_top_z": len(zs),
            "n_top_verts": n,
            "z_hex": [k.hex() for k in zs],
            "expect_hex": expect.tobytes().hex(),
            "ok": n > 0 and len(zs) == 1 and next(iter(zs)) == expect.tobytes(),
        })
    return bands_out


def locate(bb, contours, height_domain):
    me, _ids = bb["_build_cap"](contours, "cap", height_domain=height_domain)
    coords, polys, _co, _top, _band = eval_tap(bb, me, height_domain, "weld")
    bpy.data.meshes.remove(me)
    sc, sp = self_intersect(coords, polys)
    return unbalanced(sc, sp)


def main():
    report = {"ok": False}
    try:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bb = load_body_blender()
        for fn in ("_gn_tree", "_build_cap", "gn_union"):
            try:
                if fn == "_gn_tree":
                    bb[fn](height_domain="nope")
                elif fn == "_build_cap":
                    bb[fn]({"bands": []}, "cap", height_domain="nope")
                else:
                    bb[fn]({"bands": []}, Path(r"C:/x/t_636d03d6/unused.fbx"), "cap", height_domain="nope")
            except ValueError as exc:
                if "nope" not in str(exc):
                    raise
            else:
                raise AssertionError(f"{fn} accepted unknown height_domain")
        contours = json.loads(Path(__TOW02__).read_text(encoding="utf-8"))
        snapped = json.loads(Path(__SNAP__).read_text(encoding="utf-8"))
        tops = measure_tops(bb, contours, "point")
        report["tops"] = tops
        report["tops_ok"] = all(t["ok"] for t in tops)
        if not report["tops_ok"]:
            raise AssertionError("band top z is not one float32 value")
        counts = {
            "face_nosnap": locate(bb, contours, "face"),
            "face_snap": locate(bb, snapped, "face"),
            "point_snap": locate(bb, snapped, "point"),
        }
        report["unbalanced"] = counts
        expect = {"face_nosnap": 7, "face_snap": 3, "point_snap": 0}
        if counts != expect:
            raise AssertionError(f"unbalanced {counts} != {expect}")
        report["ok"] = True
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
        traceback.print_exc()
    OUT.write_text(json.dumps(report), encoding="utf-8")
    print("GN_POINT_DOMAIN", json.dumps(report), flush=True)
    sys.exit(0 if report.get("ok") else 1)


main()
"""


def load_contours():
    spec = importlib.util.spec_from_file_location("body_contours_z0_snap", CONTOURS_PY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def blender_executable():
    for key in ("DT_BLENDER", "TWINQA_BLENDER"):
        env = os.environ.get(key)
        if env and Path(env).is_file():
            return str(Path(env))
    if BLENDER_DEFAULT.is_file():
        return str(BLENDER_DEFAULT)
    return None


def point_top(z0, z1):
    return float(np.float32(np.float32(z0) + np.float32(float(z1) - float(z0))))


def face_mean(h, n):
    acc = np.float32(0)
    hf = np.float32(h)
    for _ in range(int(n)):
        acc = np.float32(acc + hf)
    return np.float32(acc * np.float32(np.float32(1.0) / np.float32(n)))


def parents_of(bands):
    by_z1 = defaultdict(list)
    for j, band in enumerate(bands):
        by_z1[float(band["z1"])].append(j)
    parents = {}
    for i, band in enumerate(bands):
        lowers = [j for j in by_z1[float(band["z0"])] if j != i]
        if len(lowers) == 1:
            parents[i] = lowers[0]
    return parents


def test_z0_snap_flag_defaults_off_and_names_unknown_values():
    import inspect
    mod = load_contours()
    assert inspect.signature(mod.contours).parameters["z0_snap"].default == "off"
    with pytest.raises(ValueError, match="nope"):
        mod.contours({}, z0_snap="nope")


def test_snap_band_z0_rejects_empty_and_nonfinite_z0():
    mod = load_contours()
    with pytest.raises(ValueError, match="empty bands"):
        mod.snap_band_z0({"bands": []})
    with pytest.raises(ValueError, match="empty bands"):
        mod.snap_band_z0({})
    with pytest.raises(ValueError, match="z0"):
        mod.snap_band_z0({"bands": [{"z0": float("nan"), "z1": 1.0, "tag": 0}]})
    with pytest.raises(ValueError, match="z0"):
        mod.snap_band_z0({"bands": [{"z0": float("inf"), "z1": 1.0, "tag": 0}]})
    with pytest.raises(ValueError, match="z0"):
        mod.snap_band_z0({"bands": [{"z0": float("-inf"), "z1": 1.0, "tag": 0}]})


def test_snap_band_z0_is_idempotent_and_keeps_every_band():
    mod = load_contours()
    original = {"schema": "body-contours/1", "bands": [
        {"z0": 0.0, "z1": 6.9, "tag": "a", "polygons": [{"exterior": [[0, 0], [1, 0], [1, 1]]}]},
        {"z0": 6.9, "z1": 10.3, "tag": "b", "polygons": [{"exterior": [[0, 0]]}]},
        {"z0": 10.3, "z1": 13.7, "tag": "c", "polygons": []},
        {"z0": 30.7, "z1": 65.4, "tag": "orphan", "polygons": [{"kept": True}]},
    ]}
    once = mod.snap_band_z0(original)
    twice = mod.snap_band_z0(once)
    assert twice == once
    assert [b["tag"] for b in once["bands"]] == [b["tag"] for b in original["bands"]]
    assert [b["z1"] for b in once["bands"]] == [b["z1"] for b in original["bands"]]
    assert [b["polygons"] for b in once["bands"]] == [b["polygons"] for b in original["bands"]]
    assert once["bands"][0]["z0"] == original["bands"][0]["z0"]
    assert once["bands"][3]["z0"] == original["bands"][3]["z0"]
    assert once["bands"][1]["z0"] == point_top(once["bands"][0]["z0"], once["bands"][0]["z1"])
    # two lowers at the same z1: the upper band is kept and not snapped
    tied = {"bands": [
        {"z0": 0.0, "z1": 1.0, "tag": "lo", "polygons": [1]},
        {"z0": 0.0, "z1": 1.0, "tag": "lo2", "polygons": [2]},
        {"z0": 1.0, "z1": 3.0, "tag": "up", "polygons": [3]},
    ]}
    kept = mod.snap_band_z0(tied)
    assert [b["tag"] for b in kept["bands"]] == ["lo", "lo2", "up"]
    assert kept["bands"][2]["z0"] == 1.0
    with pytest.raises(ValueError, match="cycle"):
        mod.snap_band_z0({"bands": [
            {"z0": 1.0, "z1": 2.0, "tag": "a"},
            {"z0": 2.0, "z1": 1.0, "tag": "b"},
        ]})


def test_snap_band_z0_point_top_is_one_z_for_random_valences():
    """Each snapped band has one point-domain top, for every sampled valence."""
    mod = load_contours()
    rng = np.random.default_rng(63603)
    splits = 0
    for _ in range(PROBE_N):
        n_bands = int(rng.integers(1, 8))
        bands = []
        z = float(rng.uniform(-20.0, 20.0))
        for i in range(n_bands):
            height = float(rng.uniform(0.05, 40.0))
            bands.append({
                "z0": z, "z1": z + height, "tag": i,
                "polygons": [{"i": i}],
            })
            z = bands[-1]["z1"]
        original = {"bands": bands}
        once = mod.snap_band_z0(original)
        twice = mod.snap_band_z0(once)
        assert twice == once
        assert [b["tag"] for b in once["bands"]] == list(range(n_bands))
        assert [b["polygons"] for b in once["bands"]] == [b["polygons"] for b in bands]
        linked = parents_of(bands)
        for i, band in enumerate(once["bands"]):
            if i not in linked:
                assert band["z0"] == bands[i]["z0"]
            else:
                lo = once["bands"][linked[i]]
                assert band["z0"] == point_top(lo["z0"], lo["z1"])
            height = float(band["z1"]) - float(band["z0"])
            top = np.float32(np.float32(band["z0"]) + np.float32(height))
            assert float(top) == point_top(band["z0"], band["z1"])
            seen = {top.tobytes()}
            for valence in rng.integers(1, 17, size=4):
                mean = face_mean(height, int(valence))
                face_top = np.float32(np.float32(band["z0"]) + mean)
                if face_top.tobytes() != top.tobytes():
                    splits += 1
                seen.add(top.tobytes())
            assert seen == {top.tobytes()}
    assert splits > 0


def test_tow02_point_domain_one_top_and_locator_counts():
    blender = blender_executable()
    if blender is None:
        pytest.skip("Blender not installed (DT_BLENDER, TWINQA_BLENDER or the pinned installation)")
    if not TOW02_CONTOURS.is_file() or not TOW02_SNAP.is_file():
        pytest.skip("TOW02 contours fixture not on this machine")
    assert hashlib.sha256(TOW02_CONTOURS.read_bytes()).hexdigest() == TOW02_SHA256
    assert hashlib.sha256(TOW02_SNAP.read_bytes()).hexdigest() == SNAP_SHA256
    SCRATCH.mkdir(parents=True, exist_ok=True)
    script = SCRATCH / "gn_point_domain_check.py"
    out = SCRATCH / "gn_point_domain_check.json"
    script.write_text(
        BLENDER_SCRIPT.replace("__ROOT__", repr(str(ROOT))).replace(
            "__TOW02__", repr(str(TOW02_CONTOURS))
        ).replace("__SNAP__", repr(str(TOW02_SNAP))),
        encoding="utf-8",
    )
    proc = subprocess.run(
        [blender, "--background", "--factory-startup", "--python-exit-code", "1",
         "--python", str(script), "--", str(out)],
        check=False, capture_output=True, text=True, timeout=900,
    )
    report = json.loads(out.read_text(encoding="utf-8")) if out.is_file() else {"error": "no report"}
    assert proc.returncode == 0, (report, proc.stderr[-4000:], proc.stdout[-2000:])
    assert report["tops_ok"] is True
    assert all(row["n_top_z"] == 1 and row["ok"] for row in report["tops"])
    assert report["unbalanced"] == {"face_nosnap": 7, "face_snap": 3, "point_snap": 0}
