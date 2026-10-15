"""Measure blender_exec.py (the Blender session bridge) without editing it.

Usage: python experiments/blender-exec-session/harness.py [section ...]
Sections: latency cubes output errors lock tmpdir (default: all). Results -> results.json next to this file.
Every object this harness creates is named "agrexp_*" and removed at the end of its section.
"""
import json
import os
import statistics
import subprocess
import sys
import tempfile
import time

BRIDGE = "C:/Users/artsafro/hermes_kanban/scripts/blender_exec.py"
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "results.json")
sys.path.insert(0, os.path.dirname(BRIDGE))
import blender_exec as be  # noqa: E402  (read-only import: we only call send())


def cli(*args, env=None, timeout=600):
    t = time.perf_counter()
    p = subprocess.run([sys.executable, BRIDGE, *args], capture_output=True, text=True,
                       encoding="utf-8", env=env, timeout=timeout)
    return p.returncode, p.stdout.strip(), time.perf_counter() - t


def raw(code, timeout=300):
    t = time.perf_counter()
    r = be.send({"type": "execute_code", "params": {"code": code}}, "127.0.0.1", 9876, timeout)
    return r, time.perf_counter() - t


def scene_counts():
    rc, out, _ = cli("--code", "import bpy; print(len(bpy.data.objects), len(bpy.data.meshes))")
    return json.loads(out)["result"]["result"].strip()


def med(xs):
    return round(statistics.median(xs) * 1000, 1)


def latency():
    ping = [cli("--ping")[2] for _ in range(10)]
    triv = [cli("--code", "x = 1")[2] for _ in range(10)]
    rawp = []
    for _ in range(10):
        t = time.perf_counter()
        be.send({"type": "get_scene_info", "params": {}}, "127.0.0.1", 9876, 30)
        rawp.append(time.perf_counter() - t)
    rawc = [raw("x = 1")[1] for _ in range(10)]
    py = []
    for _ in range(10):
        t = time.perf_counter()
        subprocess.run([sys.executable, "-c", "import argparse,json,socket,tempfile"])
        py.append(time.perf_counter() - t)
    return {"cli_ping_ms": med(ping), "cli_trivial_code_ms": med(triv), "raw_socket_ping_ms": med(rawp),
            "raw_socket_trivial_code_ms": med(rawc), "python_startup_ms": med(py),
            "cli_ping_min_max_ms": [round(min(ping) * 1000), round(max(ping) * 1000)]}


CREATE_OPS = """import bpy
for i in range({n}):
    bpy.ops.mesh.primitive_cube_add(location=(i % 50, i // 50, {z}))
    bpy.context.active_object.name = "agrexp_{tag}_%d" % i
print(len([o for o in bpy.data.objects if o.name.startswith("agrexp_")]))
"""
CREATE_DATA = """import bpy, bmesh
col = bpy.context.scene.collection
for i in range({n}):
    me = bpy.data.meshes.new("agrexp_{tag}_%d" % i)
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=2.0); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new("agrexp_{tag}_%d" % i, me); ob.location = (i % 50, i // 50, {z}); col.objects.link(ob)
print(len([o for o in bpy.data.objects if o.name.startswith("agrexp_")]))
"""
DELETE = """import bpy
obs = [o for o in bpy.data.objects if o.name.startswith("agrexp_")]
mes = {o.data for o in obs if o.data is not None}
for o in obs: bpy.data.objects.remove(o, do_unlink=True)
for m in mes:
    if m.users == 0: bpy.data.meshes.remove(m)
print(len(obs))
"""


def timed_cli(code):
    rc, out, dt = cli("--code", code)
    assert rc == 0, out[:300]
    return dt


def cubes():
    res = {"before": scene_counts()}
    for name, tmpl in (("ops", CREATE_OPS), ("data", CREATE_DATA)):
        one = timed_cli(tmpl.format(n=1000, z=0, tag=name))
        d1 = timed_cli(DELETE)
        ten = sum(timed_cli(tmpl.format(n=100, z=k, tag=f"{name}{k}")) for k in range(10))
        d10 = timed_cli(DELETE)
        res[name] = {"create_1x1000_s": round(one, 2), "create_10x100_s": round(ten, 2),
                     "delete_1000_after_1x_s": round(d1, 2), "delete_1000_after_10x_s": round(d10, 2)}
    res["after"] = scene_counts()
    return res


def output():
    res = []
    for size in (1_000, 10_000, 19_000, 20_000, 100_000, 1_000_000, 5_000_000):
        code = f"s = ''.join(chr(65 + i % 26) for i in range({size})); print(s, end='')"
        rc, out, dt = cli("--code", code)
        try:
            got = json.loads(out)["result"]["result"]
            cli_ok = got == "".join(chr(65 + i % 26) for i in range(size))
        except Exception:
            got, cli_ok = None, False
        r, rdt = raw(code)
        raw_ok = r.get("result", {}).get("result", "") == "".join(chr(65 + i % 26) for i in range(size))
        res.append({"bytes": size, "cli_rc": rc, "cli_intact": cli_ok, "cli_stdout_len": len(out),
                     "cli_truncated_marker": out.endswith("...[truncated]"), "cli_s": round(dt, 2),
                     "raw_intact": raw_ok, "raw_s": round(rdt, 2)})
    return res


def errors():
    res = {}
    for name, args in (("exception", ["--code", "raise ValueError('boom')"]),
                       ("syntax_error", ["--code", "def ("]),
                       ("print_then_exception", ["--code", "print('partial'); 1/0"]),
                       ("sleep40_default_timeout", ["--code", "import time; time.sleep(40); print('woke')"]),
                       ("sleep40_timeout10", ["--timeout", "10", "--code", "import time; time.sleep(40); print('woke')"])):
        rc, out, dt = cli(*args)
        entry = {"rc": rc, "out": out[:300], "s": round(dt, 1)}
        if name == "sleep40_timeout10":
            rc2, out2, dt2 = cli("--ping")  # Blender still sleeping? how long does the next caller wait?
            entry["ping_after"] = {"rc": rc2, "s": round(dt2, 1), "out": out2[:120]}
        res[name] = entry
    rc, out, dt = cli("--port", "9899", "--ping")
    res["wrong_port"] = {"rc": rc, "out": out[:200], "s": round(dt, 1)}
    return res


def lock():
    res = {}
    a = subprocess.Popen([sys.executable, BRIDGE, "--code", "import time; time.sleep(15); print('A done')"],
                         stdout=subprocess.PIPE, text=True)
    time.sleep(1.5)
    res["lock_file_present"] = os.path.exists(be.LOCK)
    with open(be.LOCK, encoding="utf-8") as f:
        res["lock_content"] = json.loads(f.read())
    rc, out, dt = cli("--ping", "--wait", "3")
    res["short_wait"] = {"rc": rc, "out": out[:200], "s": round(dt, 1)}
    rc, out, dt = cli("--ping", "--wait", "60")
    res["long_wait"] = {"rc": rc, "s": round(dt, 1), "status": json.loads(out).get("status")}
    a.wait()
    res["A_rc"] = a.returncode
    res["lock_left_after"] = os.path.exists(be.LOCK)
    return res


def tmpdir():
    """Is the lock shared by callers with different TEMP/TMP/TMPDIR (different profiles/shells)?"""
    alt = os.path.join(os.environ.get("LOCALAPPDATA", tempfile.gettempdir()), "Temp", "agr-exp-t_b4af19e2")
    os.makedirs(alt, exist_ok=True)
    env = dict(os.environ, TMPDIR=alt, TEMP=alt, TMP=alt)
    a = subprocess.Popen([sys.executable, BRIDGE, "--code", "import time; time.sleep(8)"], stdout=subprocess.PIPE, text=True)
    time.sleep(1.5)
    rc, out, dt = cli("--ping", "--wait", "1", env=env)
    a.wait()
    return {"alt_tmp": alt, "second_caller_rc": rc, "second_caller_s": round(dt, 1),
            "second_caller_status": json.loads(out).get("status") if out else None,
            "note": "rc 0 here means the lock did NOT exclude the second caller"}


SECTIONS = {f.__name__: f for f in (latency, cubes, output, errors, lock, tmpdir)}

if __name__ == "__main__":
    want = sys.argv[1:] or list(SECTIONS)
    data = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}
    for name in want:
        t = time.perf_counter()
        data[name] = SECTIONS[name]()
        print(name, round(time.perf_counter() - t, 1), "s", json.dumps(data[name])[:1500], flush=True)
        json.dump(data, open(OUT, "w", encoding="utf-8"), indent=1)
    print("scene after:", scene_counts())
