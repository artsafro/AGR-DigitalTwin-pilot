"""Driver for hypothesis #281: UCX-style box gaps through Blender 5.1.2 FBX export + fresh import.

    PYTHONPATH=src python experiments/hyp-281/driver.py <work_dir> <out_results.json>

Builds the frozen matrix (predictions.json), measures the analytic baseline with the unchanged
`ucx_audit`, runs the unchanged `tools/export/export_mesh_blender.py` per scene, imports each FBX
in a fresh Blender process (readback.py) and measures the declared A/B pairs on the imported
world geometry. Two repetitions in fresh paths. Synthetic geometry; delivery_passed=false.
"""
import json
import math
import struct
import subprocess
import sys
import time
from pathlib import Path

from twinqa.geometry import ucx_audit as ua

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
BLENDER = "C:/Program Files/Blender Foundation/Blender 5.1/blender.exe"
EXPORTER = REPO / "tools/export/export_mesh_blender.py"
READBACK = HERE / "readback.py"
FLAGS = ["--background", "--factory-startup", "--disable-autoexec", "--python-exit-code", "1", "--python"]
P = json.loads((HERE / "predictions.json").read_text(encoding="utf-8"))
T = P["thresholds"]
# tests/qa/test_ucx_audit.py:BOX_TRIS (copied verbatim; vertex index bits = x,y,z)
BOX_TRIS = [(0, 1, 3), (0, 3, 2), (4, 6, 7), (4, 7, 5), (0, 4, 5), (0, 5, 1),
            (2, 3, 7), (2, 7, 6), (0, 2, 6), (0, 6, 4), (1, 5, 7), (1, 7, 3)]


def box(lo, hi):
    return [(hi[0] if i & 4 else lo[0], hi[1] if i & 2 else lo[1], hi[2] if i & 1 else lo[2]) for i in range(8)]


def xform(pts, deg, t):
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    return [(x * c - y * s + t[0], x * s + y * c + t[1], z + t[2]) for x, y, z in pts]


def f32(pts):
    return [tuple(struct.unpack("f", struct.pack("f", v))[0] for v in p) for p in pts]


def scene(deg, t):
    boxes = {}
    for k, g in enumerate(P["gaps_m"]):
        boxes[f"P{k}_A"] = xform(box((0, 4 * k, 0), (2, 4 * k + 1, 3)), deg, t)
        boxes[f"P{k}_B"] = xform(box((2 + g, 4 * k, 0), (4 + g, 4 * k + 1, 3)), deg, t)
    return boxes


def run(cmd):
    t0 = time.perf_counter()
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode, time.perf_counter() - t0, (r.stdout + r.stderr)[-600:]


def measure(boxes, g, k):
    a, b = (boxes[f"P{k}_{s}"] for s in "AB")
    cls, gap, pen = ua.pair_relation(a, b)
    return {"class": cls, "gap_m": gap, "penetration_m": pen, "abs_err_m": abs(gap - g)}


def main(work, out):
    work.mkdir(parents=True, exist_ok=True)
    rows, fails, timings = [], [], {"export_s": [], "import_s": []}
    for rep in range(1, P["repetitions"] + 1):
        for deg in P["angles_deg"]:
            for t in P["translations_m"]:
                tag = f"r{rep}_a{deg}_t{t[0]}_{t[1]}"
                src = scene(deg, t)
                dump = {"meshes": [{"name": n, "vertices": v, "triangles": BOX_TRIS, "material_ids": [1] * 12}
                                   for n, v in src.items()]}
                dpath = work / f"{tag}.json"
                dpath.write_text(json.dumps(dump), encoding="utf-8")
                blend, fbx, rb = work / f"{tag}.blend", work / f"{tag}.fbx", work / f"{tag}_readback.json"
                rc_e, te, log_e = run([BLENDER, *FLAGS, str(EXPORTER), "--", str(dpath), str(blend), str(fbx)])
                timings["export_s"].append(te)
                rc_i, ti, log_i = (None, 0.0, "")
                if rc_e == 0:
                    rc_i, ti, log_i = run([BLENDER, *FLAGS, str(READBACK), "--", str(fbx), str(rb)])
                    timings["import_s"].append(ti)
                scene_fail = []
                if rc_e != 0 or rc_i != 0:
                    scene_fail.append(f"native failure export={rc_e} import={rc_i}: {log_e if rc_e else log_i}")
                    imp = {}
                    meta = {}
                else:
                    data = json.loads(rb.read_text(encoding="utf-8"))
                    meshes = [o for o in data["objects"] if o["type"] == "MESH"]
                    names = sorted(o["name"] for o in meshes)
                    if names != sorted(src) or len(data["objects"]) != 6:
                        scene_fail.append(f"objects {names} / {len(data['objects'])}")
                    imp, meta = {}, {}
                    for o in meshes:
                        wv, wt = ua.weld(o["world"], o["tris"])
                        mw = o["matrix_world"]
                        ident_dev = max(abs(mw[r][c] - (1.0 if r == c else 0.0)) for r in range(4) for c in range(4))
                        closed, convex = ua.is_closed(wt), ua.is_convex(wv, wt)
                        degenerate = sum(1 for p in ua.face_planes(wv, wt) if p is None)
                        meta[o["name"]] = {"raw_verts": len(o["raw"]), "corners": len(wv), "tris": len(wt),
                                           "closed": closed, "convex": convex, "degenerate": degenerate,
                                           "matrix_identity_dev": ident_dev}
                        if (len(wv), len(wt)) != (T["unique_corners_per_box"], T["triangles_per_box"]) \
                                or not closed or not convex or degenerate:
                            scene_fail.append(f"{o['name']} structure {meta[o['name']]}")
                        imp[o["name"]] = (wv, wt)
                for k, g in enumerate(P["gaps_m"]):
                    hull = {n: (v, BOX_TRIS) for n, v in src.items()}
                    base = measure(hull, g, k)
                    q32 = measure({n: (f32(v), BOX_TRIS) for n, v in src.items()}, g, k)
                    row = {"rep": rep, "angle": deg, "t": t, "gap_nominal_m": g, "baseline": base,
                           "f32_diag": q32, "export_rc": rc_e, "import_rc": rc_i}
                    if base["class"] != T["baseline_class"] or base["abs_err_m"] > T["baseline_abs_error_m_max"] \
                            or base["penetration_m"] != 0:
                        fails.append(f"{tag} P{k} baseline {base}")
                    if f"P{k}_A" in imp and f"P{k}_B" in imp:
                        r = measure(imp, g, k)
                        row["imported"] = r
                        if r["class"] != T["imported_class"] or r["abs_err_m"] > T["imported_abs_error_m_max"] \
                                or r["penetration_m"] != 0:
                            fails.append(f"{tag} P{k} imported {r['class']} gap={r['gap_m']:.7f} err={r['abs_err_m']:.2e}")
                    else:
                        row["imported"] = None
                        fails.append(f"{tag} P{k} pair missing")
                    rows.append(row)
                fails += [f"{tag} {m}" for m in scene_fail]
                if meta:
                    rows[-1]["scene_meta"] = meta
                print(f"{tag}: export {rc_e} {te:.1f}s import {rc_i} {ti:.1f}s "
                      + " ".join(f"{r['imported']['gap_m'] * 1000:.4f}" if r.get("imported") else "NA"
                                 for r in rows[-3:]), flush=True)
    # repeatability
    n = len(rows) // 2
    for a, b in zip(rows[:n], rows[n:]):
        ia, ib = a.get("imported"), b.get("imported")
        if not ia or not ib or ia["class"] != ib["class"] or abs(ia["gap_m"] - ib["gap_m"]) > T["repeat_gap_diff_m_max"]:
            fails.append(f"repeat a{a['angle']} t{a['t']} g{a['gap_nominal_m']} differs")
    out.write_text(json.dumps({"rows": rows, "fails": fails, "timings": timings}, indent=1), encoding="utf-8")
    print(f"FAILS {len(fails)}")
    for f in fails[:40]:
        print(" ", f)


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
