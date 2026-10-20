"""Driver for hypothesis #386: baked-world (A) vs shared local-object transform (B) UCX boxes through
Blender 5.1.2 FBX export + fresh import, at 0/37/89 deg and up to 14.2 km.

    PYTHONPATH=src python experiments/hyp-386/driver.py <work_dir> <out_results.json>

Arm A runs the unchanged tools/export/export_mesh_blender.py with R*p+T baked into the vertices.
Arm B runs experiments/hyp-386/export_local.py (exporter copy): local p + the same 4x4 matrix_world
on all six objects. Every FBX is read back in a fresh factory-startup Blender (readback.py, binary64
reconstruction from Python floats). Pairs are measured with the unchanged twinqa ucx_audit and
compared with a Python sin/cos analytic oracle. Synthetic geometry; delivery_passed=false.
"""
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

from twinqa.geometry import ucx_audit as ua
from compatibility import inventory, validate_results

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
BLENDER = os.environ.get('DT_BLENDER', 'C:/Program Files/Blender Foundation/Blender 5.1/blender.exe')
EXPORTERS = {"A_baked": REPO / "tools/export/export_mesh_blender.py", "B_local": HERE / "export_local.py"}
READBACK = HERE / "readback.py"
FLAGS = ["--background", "--factory-startup", "--disable-autoexec", "--python-exit-code", "1", "--python"]
P = json.loads((HERE / "predictions.json").read_text(encoding="utf-8"))
T = P["thresholds"]
# tests/qa/test_ucx_audit.py:BOX_TRIS via experiments/hyp-281/driver.py (vertex index bits = x,y,z)
BOX_TRIS = [(0, 1, 3), (0, 3, 2), (4, 6, 7), (4, 7, 5), (0, 4, 5), (0, 5, 1),
            (2, 3, 7), (2, 7, 6), (0, 2, 6), (0, 6, 4), (1, 5, 7), (1, 7, 3)]


def box(lo, hi):
    return [(hi[0] if i & 4 else lo[0], hi[1] if i & 2 else lo[1], hi[2] if i & 1 else lo[2]) for i in range(8)]


def xform(pts, deg, t):
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    return [(x * c - y * s + t[0], x * s + y * c + t[1], z + t[2]) for x, y, z in pts]


def matrix(deg, t):
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    return [[c, -s, 0.0, float(t[0])], [s, c, 0.0, float(t[1])], [0.0, 0.0, 1.0, float(t[2])], [0.0, 0.0, 0.0, 1.0]]


def local_scene():
    boxes = {}
    for k, g in enumerate(P["gaps_m"]):
        boxes[f"P{k}_A"] = box((0, 4 * k, 0), (2, 4 * k + 1, 3))
        boxes[f"P{k}_B"] = box((2 + g, 4 * k, 0), (4 + g, 4 * k + 1, 3))
    return boxes


def run(cmd):
    t0 = time.perf_counter()
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode, time.perf_counter() - t0, (r.stdout + r.stderr)[-600:]


def measure(boxes, g, k):
    cls, gap, pen = ua.pair_relation(boxes[f"P{k}_A"], boxes[f"P{k}_B"])
    return {"class": cls, "gap_m": gap, "penetration_m": pen, "abs_err_m": abs(gap - g)}


def corner_dist(a, b):
    d = lambda p, q: math.dist(p, q)
    return max(max(min(d(p, q) for q in b) for p in a), max(min(d(p, q) for p in a) for q in b))


def structure(objs, oracle, fails, tag):
    """Weld, structural checks, corner distance vs oracle. Returns ({name: (verts, tris)}, meta)."""
    out, meta = {}, {}
    try:
        inventory(objs, oracle)
    except ValueError as exc:
        fails.append(f'{tag}: {exc}')
        return out, meta
    for o in objs:
        wv, wt = ua.weld(o["world"], o["tris"])
        closed, convex = ua.is_closed(wt), ua.is_convex(wv, wt)
        degenerate = sum(1 for p in ua.face_planes(wv, wt) if p is None)
        cd = corner_dist(wv, oracle[o["name"]]) if o["name"] in oracle else None
        meta[o["name"]] = {"raw_verts": len(o["raw"]), "corners": len(wv), "tris": len(wt), "closed": closed,
                           "convex": convex, "degenerate": degenerate, "corner_dist_m": cd}
        if (len(wv), len(wt)) != (T["unique_corners_per_box"], T["triangles_per_box"]) or not closed \
                or not convex or degenerate:
            fails.append(f"{tag} {o['name']} structure {meta[o['name']]}")
        out[o["name"]] = (wv, wt)
    return out, meta


def main(work, out):
    work, out = work.resolve(), out.resolve()
    if not work.is_relative_to(REPO) or work.is_relative_to(REPO / 'data') or work.exists():
        raise ValueError('work must be a new directory inside this worktree, outside data/')
    if out != work / 'results.json':
        raise ValueError('report must be <new-work-directory>/results.json')
    work.mkdir(parents=True)
    raw_dir = work / 'raw'
    raw_dir.mkdir()
    v = subprocess.run([BLENDER, "--version"], capture_output=True, text=True)
    rc_v = v.returncode
    env = {"blender_version": v.stdout.strip().splitlines()[0] if rc_v == 0 else None, "rc": rc_v}
    if rc_v != 0 or not re.match(r'^Blender 5\.1\.\d+\b', env['blender_version'] or ''):
        raise SystemExit(f"preflight failed: {env}")
    local = local_scene()
    rows = []
    fails = {"analytic": [], "A_baked": [], "B_local": [], "control": [], "native": []}
    timings = {a: {"export_s": [], "import_s": []} for a in EXPORTERS}
    for rep in range(1, P["repetitions"] + 1):
        for deg in P["angles_deg"]:
            for t in P["translations_m"]:
                oracle = {n: xform(v, deg, t) for n, v in local.items()}
                m = matrix(deg, t)
                hull = {n: (v, BOX_TRIS) for n, v in oracle.items()}
                analytic = [measure(hull, g, k) for k, g in enumerate(P["gaps_m"])]
                for k, a in enumerate(analytic):
                    if a["class"] != T["analytic_class"] or a["abs_err_m"] > T["analytic_abs_error_m_max"] \
                            or a["penetration_m"] != 0:
                        fails["analytic"].append(f"r{rep} a{deg} t{t} P{k} {a}")
                for arm, exporter in EXPORTERS.items():
                    tag = f"{arm}_r{rep}_a{deg}_t{t[0]}_{t[1]}"
                    d = work / f"rep{rep}" / arm
                    d.mkdir(parents=True, exist_ok=True)
                    if arm == "A_baked":
                        meshes = [{"name": n, "vertices": v, "triangles": BOX_TRIS, "material_ids": [1] * 12}
                                  for n, v in oracle.items()]
                    else:
                        meshes = [{"name": n, "vertices": v, "triangles": BOX_TRIS, "material_ids": [1] * 12,
                                   "matrix_world": m} for n, v in local.items()]
                    dpath = d / f"{tag}.json"
                    dpath.write_text(json.dumps({"meshes": meshes}), encoding="utf-8")
                    blend, fbx, rb, pre = (d / f"{tag}{s}" for s in (".blend", ".fbx", "_readback.json", "_prefbx.json"))
                    cmd = [BLENDER, *FLAGS, str(exporter), "--", str(dpath), str(blend), str(fbx)]
                    if arm == "B_local":
                        cmd.append(str(pre))
                    rc_e, te, log_e = run(cmd)
                    timings[arm]["export_s"].append(te)
                    rc_i, ti, log_i = None, 0.0, ""
                    if rc_e == 0:
                        rc_i, ti, log_i = run([BLENDER, *FLAGS, str(READBACK), "--", str(fbx), str(rb)])
                        timings[arm]["import_s"].append(ti)
                    row = {"arm": arm, "rep": rep, "angle": deg, "t": t, "export_rc": rc_e, "import_rc": rc_i,
                           "analytic": analytic, "matrix_set": m if arm == "B_local" else None}
                    if rc_e != 0 or rc_i != 0:
                        fails["native"].append(f"{tag} export={rc_e} import={rc_i}: {log_e if rc_e else log_i}")
                        rows.append(row)
                        continue
                    sf = fails[arm]
                    if arm == "B_local":
                        shutil.copy(pre, raw_dir / pre.name)
                        pd = json.loads(pre.read_text(encoding="utf-8"))
                        mats = [o["matrix_world"] for o in pd["objects"]]
                        identical = all(x == mats[0] for x in mats)
                        mdev = max(abs(mats[0][r][c] - m[r][c]) for r in range(4) for c in range(4))
                        if not identical:
                            sf.append(f"{tag} prefbx matrices differ")
                        pobj = [dict(o, tris=BOX_TRIS) for o in pd["objects"]]
                        pboxes, pmeta = structure(pobj, oracle, sf, tag + " prefbx")
                        pre_gaps = [measure(pboxes, g, k) for k, g in enumerate(P["gaps_m"])]
                        for k, r in enumerate(pre_gaps):
                            if r["abs_err_m"] > T["local_prefbx_gap_error_m_max"]:
                                sf.append(f"{tag} P{k} prefbx gap err {r['abs_err_m']:.3e}")
                        row["prefbx"] = {"matrices_identical": identical, "matrix_vs_set_max_dev": mdev,
                                         "gaps": pre_gaps, "meta": pmeta,
                                         "location": pd["objects"][0]["location"],
                                         "rotation_euler": pd["objects"][0]["rotation_euler"],
                                         "scale": pd["objects"][0]["scale"]}
                    shutil.copy(rb, raw_dir / rb.name)
                    data = json.loads(rb.read_text(encoding="utf-8"))
                    row["blender_import"] = data["blender"]
                    meshes_i = [o for o in data["objects"] if o["type"] == "MESH"]
                    names = sorted(o["name"] for o in meshes_i)
                    if names != sorted(local) or len(data["objects"]) != 6:
                        sf.append(f"{tag} objects {names} / {len(data['objects'])}")
                    imp, meta = structure(meshes_i, oracle, sf if arm == "B_local" else [], tag)
                    row["meta"] = meta
                    row["imported_matrices"] = {o["name"]: o["matrix_world"] for o in meshes_i}
                    gaps = []
                    for k, g in enumerate(P["gaps_m"]):
                        if f"P{k}_A" in imp and f"P{k}_B" in imp:
                            r = measure(imp, g, k)
                            gaps.append(r)
                            if arm == "B_local" and (r["class"] != T["local_imported_class"] or r["penetration_m"] != 0
                                                     or r["abs_err_m"] > T["local_imported_gap_error_m_max"]):
                                sf.append(f"{tag} P{k} imported {r['class']} gap={r['gap_m']:.9f} err={r['abs_err_m']:.3e}")
                        else:
                            gaps.append(None)
                            sf.append(f"{tag} P{k} pair missing")
                    if arm == "B_local":
                        for n, md in meta.items():
                            if md["corner_dist_m"] is None or md["corner_dist_m"] > T["local_corner_distance_m_max"]:
                                sf.append(f"{tag} {n} corner dist {md['corner_dist_m']}")
                    row["imported"] = gaps
                    rows.append(row)
                    print(f"{tag}: exp {rc_e} {te:.1f}s imp {rc_i} {ti:.1f}s gaps_mm "
                          + " ".join(f"{x['gap_m'] * 1000:.6f}" if x else "NA" for x in gaps), flush=True)
    # repeatability (local arm mandatory; baked arm recorded)
    rep_diff = {}
    for arm in EXPORTERS:
        r1 = [r for r in rows if r["arm"] == arm and r["rep"] == 1]
        r2 = [r for r in rows if r["arm"] == arm and r["rep"] == 2]
        worst = 0.0
        for a, b in zip(r1, r2):
            for k in range(len(P["gaps_m"])):
                ia = (a.get("imported") or [None] * 3)[k]
                ib = (b.get("imported") or [None] * 3)[k]
                if not ia or not ib:
                    fails[arm].append(f"repeat a{a['angle']} t{a['t']} P{k} missing")
                    continue
                dd = abs(ia["gap_m"] - ib["gap_m"])
                worst = max(worst, dd)
                if arm == "B_local" and (dd > T["repeat_gap_diff_m_max"] or ia["class"] != ib["class"]):
                    fails[arm].append(f"repeat a{a['angle']} t{a['t']} P{k} diff {dd:.3e}")
        rep_diff[arm] = worst
    # baked control
    c = T["baked_control"]
    ctrl = []
    for r in rows:
        if r["arm"] == "A_baked" and r["angle"] == c["angle"] and r["t"] == c["t"] and r.get("imported"):
            mm = r["imported"][P["gaps_m"].index(c["gap_m"])]["gap_m"] * 1000
            ctrl.append(mm)
            if abs(mm - c["expected_imported_gap_mm"]) > c["tolerance_mm"]:
                fails["control"].append(f"rep{r['rep']} control {mm:.9f} mm")
    if len(ctrl) != P["repetitions"]:
        fails["control"].append(f"control rows {len(ctrl)}")
    expected_rows = 2 * len(P["angles_deg"]) * len(P["translations_m"]) * P["repetitions"]
    complete = len([r for r in rows if r.get("imported")]) == expected_rows
    if fails["B_local"] or fails["native"]:
        verdict = "REJECTED"
    elif not complete or fails["control"] or fails["analytic"]:
        verdict = "INCONCLUSIVE"
    else:
        verdict = "CONFIRMED"
    res = {"env": env, "verdict": verdict, "complete": complete, "control_mm": ctrl, "repeat_max_diff_m": rep_diff,
           "fails": fails, "timings": timings, "rows": rows, "delivery_passed": False}
    try:
        validate_results(res, P)
    except (ValueError, KeyError, TypeError, IndexError) as exc:
        res['verdict'] = 'REJECTED'
        res['fails']['native'].append(f'strict compatibility validation: {exc}')
    out.write_text(json.dumps(res, indent=1, allow_nan=False), encoding="utf-8")
    print(f"VERDICT {res['verdict']} complete={complete} control={ctrl} repeat={rep_diff}")
    for k, v in fails.items():
        print(f" {k}: {len(v)}", *v[:12], sep="\n   ")
    if res['verdict'] != 'CONFIRMED':
        raise SystemExit(1)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit('usage: driver.py <new-work-dir> <new-work-dir/results.json>')
    main(Path(sys.argv[1]), Path(sys.argv[2]))
