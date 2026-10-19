"""PROTOTYPE (experiment t_d6c8f213): one agent running multi-step Blender workflows through blender_exec.py.

    python agent.py --name A --lock percall|lease --cleanup objects|diff --fixtures <dir> --rounds 2 --out a.json

A workflow on one benchmark body mesh = 5 blender_exec calls:
  0 snapshot  (names of every ID in objects/meshes/materials/images/collections + scene mesh objects)
  1 create    (bpy.data mesh + material + object, linked to the scene)
  2 move      (location.x += 10)
  3 readback  (SCENE-WIDE check: mesh object count, vertex sum, world min x) -> torn if != expected
  4 cleanup   objects: remove the object it created (current card rule)
              diff:    remove every ID not in the step-0 snapshot (inventory-diff reset)
--lock percall: only blender_exec's own per-call lock (current state).
--lock lease:   the whole workflow runs under dcc_lease.Lease("blender") (prototype).
"""
import argparse
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
from dcc_lease import Lease  # noqa: E402

EXEC = "C:/Users/artsafro/hermes_kanban/scripts/blender_exec.py"
IDS = ["objects", "meshes", "materials", "images", "collections"]

SNAP = """import bpy, json
inv = {k: sorted(x.name for x in getattr(bpy.data, k)) for k in %r}
inv['scene_meshes'] = sum(1 for o in bpy.context.scene.objects if o.type == 'MESH')
print(json.dumps(inv))
""" % IDS

CREATE = """import bpy, json
d = json.load(open(%r, encoding='utf-8'))
me = bpy.data.meshes.new(%r)
me.from_pydata([tuple(v) for v in d['vertices']], [], [tuple(p) for p in d['polygons']])
me.materials.append(bpy.data.materials.new(%r))
ob = bpy.data.objects.new(%r, me)
bpy.context.scene.collection.objects.link(ob)
print(json.dumps({'v': len(me.vertices)}))
"""

MOVE = """import bpy
bpy.data.objects[%r].location.x += 10.0
print('ok')
"""

READ = """import bpy, json
from mathutils import Vector
dg = bpy.context.evaluated_depsgraph_get()
obs = [o for o in bpy.context.scene.objects if o.type == 'MESH']
minx = min((min((o.matrix_world @ Vector(c)).x for c in o.bound_box) for o in obs), default=None)
print(json.dumps({'n': len(obs), 'v': sum(len(o.data.vertices) for o in obs), 'minx': minx}))
"""

CLEAN_OBJ = """import bpy
ob = bpy.data.objects.get(%r)
if ob: bpy.data.objects.remove(ob)
print('ok')
"""

CLEAN_DIFF = """import bpy, json
snap = json.loads(%r)
n = 0
for k in %r:
    coll = getattr(bpy.data, k)
    keep = set(snap[k])
    for x in [x for x in coll if x.name not in keep]:
        coll.remove(x); n += 1
print(n)
"""


def call(code, card, tmp):
    path = os.path.join(tmp, f"{card}_{os.getpid()}.py")
    with open(path, "w", encoding="utf-8") as f:
        f.write(code)
    r = subprocess.run([sys.executable, EXEC, "--file", path, "--card", card, "--wait", "300"],
                       capture_output=True, text=True)
    try:
        resp = json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return None, f"exit {r.returncode}: {r.stdout[-200:]}"
    if r.returncode != 0:
        return None, (resp.get("traceback") or resp.get("message") or str(resp))[-200:]
    res = resp.get("result")
    return (res.get("result") if isinstance(res, dict) else res).strip(), None


def workflow(name, bench, fx_path, fx, cleanup, card, tmp, lease=None):
    obj = f"agrexp_{name}_{bench}"
    rec = {"agent": name, "bench": bench, "torn": False, "error": None, "calls": 0}
    t0 = time.perf_counter()
    snap_txt, err = call(SNAP, card, tmp)
    rec["calls"] += 1
    if err:
        rec["error"] = "snapshot: " + err
        return rec
    snap = json.loads(snap_txt)
    steps = [("create", CREATE % (fx_path, obj, obj, obj)), ("move", MOVE % obj), ("read", READ)]
    for step, code in steps:
        if lease:
            lease.check()
        out, err = call(code, card, tmp)
        rec["calls"] += 1
        if err:
            rec["error"] = f"{step}: {err.splitlines()[-1] if err else err}"
            break
        if step == "read":
            got = json.loads(out)
            exp = {"n": snap["scene_meshes"] + 1, "v": len(fx["vertices"]),
                   "minx": min(v[0] for v in fx["vertices"]) + 10.0}
            rec["read"] = got
            rec["torn"] = (got["n"] != exp["n"] or got["v"] != exp["v"]
                           or got["minx"] is None or abs(got["minx"] - exp["minx"]) > 1e-3)
    code = CLEAN_OBJ % obj if cleanup == "objects" else CLEAN_DIFF % (json.dumps(snap), IDS)
    out, err = call(code, card, tmp)
    rec["calls"] += 1
    if err and not rec["error"]:
        rec["error"] = "cleanup: " + err
    rec["s"] = round(time.perf_counter() - t0, 3)
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--lock", choices=["percall", "lease"], required=True)
    ap.add_argument("--cleanup", choices=["objects", "diff"], required=True)
    ap.add_argument("--fixtures", required=True)
    ap.add_argument("--rounds", type=int, default=2)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    card = f"exp-t_d6c8f213-{a.name}"
    tmp = os.path.join(a.fixtures, "code")
    os.makedirs(tmp, exist_ok=True)
    benches = sorted(p[:-5] for p in os.listdir(a.fixtures) if p.endswith(".json"))
    recs, lease_wait = [], []
    t0 = time.perf_counter()
    for r in range(a.rounds):
        for b in benches:
            fx_path = os.path.join(a.fixtures, b + ".json").replace("\\", "/")
            fx = json.load(open(fx_path, encoding="utf-8"))
            if a.lock == "lease":
                tw = time.perf_counter()
                with Lease("blender", card=card, wait=600) as lease:
                    lease_wait.append(time.perf_counter() - tw)
                    recs.append(workflow(a.name, f"{b}_r{r}", fx_path, fx, a.cleanup, card, tmp, lease))
                    recs[-1]["token"] = lease.token
            else:
                recs.append(workflow(a.name, f"{b}_r{r}", fx_path, fx, a.cleanup, card, tmp))
    json.dump({"agent": a.name, "wall_s": time.perf_counter() - t0, "workflows": recs,
               "lease_wait_s": lease_wait}, open(a.out, "w", encoding="utf-8"), indent=1)


if __name__ == "__main__":
    main()
