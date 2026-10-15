"""PROTOTYPE harness (experiment t_d6c8f213).

    uv run python experiments/mcp-dcc-bridges/harness.py fixtures   # engine body meshes -> %TEMP%/agr-exp-t_d6c8f213
    uv run python experiments/mcp-dcc-bridges/harness.py concurrency [reps]   # 2 agents x 4 configs x reps
    uv run python experiments/mcp-dcc-bridges/harness.py recovery   # crashed holder: per-call lock vs lease

Writes experiments/mcp-dcc-bridges/results_<section>.json.
"""
import hashlib
import json
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
TMP = Path(os.environ["LOCALAPPDATA"]) / "Temp" / "agr-exp-t_d6c8f213"
FX = TMP / "fixtures"
os.environ["AGR_DCC_LEASE_DIR"] = str(TMP / "leases")
sys.path.insert(0, str(HERE))
from dcc_lease import Lease, Quarantined, process_start  # noqa: E402

EXEC = "C:/Users/artsafro/hermes_kanban/scripts/blender_exec.py"
BENCHES = ["bench-b01-box", "bench-b02-corner-niche", "bench-b02t-terrace"]
INV = """import bpy, json
print(json.dumps({k: len(getattr(bpy.data, k)) for k in ['objects','meshes','materials','images','collections']}))
"""


def sha_tree():
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for b in BENCHES for p in sorted((ROOT / "benchmark" / b).glob("*"))}


def bx(*args):
    r = subprocess.run([sys.executable, EXEC, *args], capture_output=True, text=True)
    return r.returncode, r.stdout.strip()


def inventory():
    rc, out = bx("--code", INV, "--card", "exp-t_d6c8f213")
    return json.loads(json.loads(out)["result"]["result"])


def fixtures():
    sys.path.insert(0, str(ROOT / "src"))
    from dt_ai.geometry.from_spec import BuildInputs, build
    from dt_ai.spec.model import Spec
    FX.mkdir(parents=True, exist_ok=True)
    for b in BENCHES:
        d = ROOT / "benchmark" / b
        spec = Spec.model_validate(json.loads((d / "spec.json").read_text(encoding="utf-8")))
        body = build(spec, BuildInputs.from_object(json.loads((d / "object.json").read_text(encoding="utf-8"))))
        m = body["meshes"][0]
        (FX / f"{b}.json").write_text(json.dumps({"vertices": m["vertices"], "polygons": m["polygons"]}),
                                      encoding="utf-8")
        print(b, len(m["vertices"]), len(m["polygons"]))


def concurrency(reps=3):
    out = {"etalon_sha_before": sha_tree(), "configs": {}}
    for lock in ("percall", "lease"):
        for cleanup in ("objects", "diff"):
            key = f"{lock}+{cleanup}"
            runs = []
            for rep in range(reps):
                inv0 = inventory()
                t0 = time.perf_counter()
                procs = [subprocess.Popen([sys.executable, str(HERE / "agent.py"), "--name", n, "--lock", lock,
                                           "--cleanup", cleanup, "--fixtures", str(FX), "--rounds", "2",
                                           "--out", str(TMP / f"{key}_{rep}_{n}.json")]) for n in "AB"]
                for p in procs:
                    p.wait()
                wall = time.perf_counter() - t0
                inv1 = inventory()
                recs = [w for n in "AB" for w in json.load(open(TMP / f"{key}_{rep}_{n}.json"))["workflows"]]
                runs.append({"wall_s": round(wall, 2), "workflows": len(recs),
                             "torn": sum(w["torn"] for w in recs),
                             "errors": [w["error"] for w in recs if w["error"]],
                             "residual": {k: inv1[k] - inv0[k] for k in inv0 if inv1[k] != inv0[k]},
                             "calls": sum(w["calls"] for w in recs)})
                print(key, rep, runs[-1]["wall_s"], "torn", runs[-1]["torn"], "err", len(runs[-1]["errors"]),
                      "residual", runs[-1]["residual"], flush=True)
            out["configs"][key] = {"runs": runs, "median_wall_s": statistics.median(r["wall_s"] for r in runs)}
    out["etalon_sha_after"] = sha_tree()
    out["etalon_unchanged"] = out["etalon_sha_before"] == out["etalon_sha_after"]
    (HERE / "results_concurrency.json").write_text(json.dumps(out, indent=1), encoding="utf-8")


def ping():
    return bx("--ping", "--wait", "5", "--card", "exp-t_d6c8f213")[0] == 0


def recovery():
    res = {}
    lock = Path(os.environ["LOCALAPPDATA"]) / "Temp" / "agr-blender-session.lock"
    # Baseline: a blender_exec client killed mid-call leaves its per-call lock behind.
    p = subprocess.Popen([sys.executable, EXEC, "--code", "import time; time.sleep(3)", "--card", "exp-crash"])
    time.sleep(1.0)
    subprocess.run(["taskkill", "/F", "/PID", str(p.pid)], capture_output=True)
    p.wait()
    time.sleep(3)  # Blender finishes the sleep; it is idle now
    left = lock.exists()
    t0 = time.perf_counter()
    rc, outp = bx("--ping", "--wait", "10", "--card", "exp-after-crash")
    res["percall_after_crash"] = {"lock_left": left, "exit": rc, "status": json.loads(outp).get("status"),
                                  "s": round(time.perf_counter() - t0, 1),
                                  "stale_after_s_by_code": "max(1800, timeout+120) = 1800 s for --timeout 300"}
    if left and lock.exists() and json.load(open(lock)).get("card") == "exp-crash":
        lock.unlink()  # our own orphan lock
    # Prototype: holder of the lease is killed; next caller checks pid+start time, pings Blender, reclaims.
    holder = subprocess.Popen([sys.executable, "-c",
                               "import sys,time; sys.path.insert(0, r'%s'); from dcc_lease import Lease; "
                               "Lease('blender', card='exp-crash').acquire(); time.sleep(60)" % HERE])
    time.sleep(1.5)
    subprocess.run(["taskkill", "/F", "/PID", str(holder.pid)], capture_output=True)
    holder.wait()
    t0 = time.perf_counter()
    lz = Lease("blender", card="exp-after-crash", wait=10, ping=ping)
    lz.acquire()
    res["lease_after_crash"] = {"acquired": True, "s": round(time.perf_counter() - t0, 2), "reclaims": lz.reclaims,
                                "token": lz.token}
    lz.release()
    # PID reuse: lease names a LIVE pid (this process's parent) with a wrong start time.
    fake = {"program": "blender", "card": "exp-ghost", "pid": os.getppid(),
            "pid_start": (process_start(os.getppid()) or 0) + 12345, "token": 0, "t": time.time()}
    Path(lz.path).write_text(json.dumps(fake))
    t0 = time.perf_counter()
    lz = Lease("blender", card="exp-after-reuse", wait=10, ping=ping)
    lz.acquire()
    res["lease_pid_reuse"] = {"s": round(time.perf_counter() - t0, 2), "reclaims": lz.reclaims}
    lz.release()
    # Live owner: must NOT be reclaimed (Busy after wait).
    owner = Lease("blender", card="exp-live").acquire()
    t0 = time.perf_counter()
    try:
        Lease("blender", card="exp-other", wait=2, ping=ping).acquire()
        res["lease_live_owner"] = "WRONGLY ACQUIRED"
    except Exception as e:  # noqa: BLE001
        res["lease_live_owner"] = {"raised": type(e).__name__, "s": round(time.perf_counter() - t0, 2)}
    owner.release()
    # Dead owner + DCC not answering -> quarantine, no takeover.
    Path(lz.path).write_text(json.dumps(dict(fake, pid=999999, card="exp-dead")))
    try:
        Lease("blender", card="exp-q", wait=2, ping=lambda: False).acquire()
        res["lease_dead_owner_dcc_silent"] = "WRONGLY ACQUIRED"
    except Quarantined as e:
        res["lease_dead_owner_dcc_silent"] = {"raised": "Quarantined", "lease_kept": Path(lz.path).exists()}
    Path(lz.path).unlink()
    # Overhead of an uncontended acquire/release.
    ts = []
    for _ in range(50):
        t0 = time.perf_counter()
        Lease("blender", card="exp-ovh").acquire().release()
        ts.append((time.perf_counter() - t0) * 1000)
    res["lease_acquire_release_ms_median"] = round(statistics.median(ts), 3)
    print(json.dumps(res, indent=1))
    (HERE / "results_recovery.json").write_text(json.dumps(res, indent=1), encoding="utf-8")


if __name__ == "__main__":
    {"fixtures": fixtures, "concurrency": lambda: concurrency(int(sys.argv[2]) if len(sys.argv) > 2 else 3),
     "recovery": recovery}[sys.argv[1]]()
