"""#117 replay: G22 agent recipe (A) vs A + source-only D341 pocket fill (B), scored by `agr trainer score`.

uv run python docs/research/trainer_pockets_r117/run.py --out NEW_DIR [--reps 3] [--controls-only]

Pinned inputs are hash-checked first (contract: docs/research/autoresearch-trainer-pocket-fill.md); any mismatch
refuses. Arm A = the r115-D1 command verbatim (`floor_from_dump NPZ plan.json --seal windows --openings`);
arm B = the same, then `pockets_self.py plan0.json` -> `floor_from_dump ... --fill fill.json`. Both arms build with
`agr body --max-side 3.6` (Blender 5.1, as D1) and are scored with `agr trainer score g22-k2-stage1`.
OBSERVE only: writes under NEW_DIR, never into the bank, the stored runs or the repo.
"""
import argparse
import hashlib
import importlib.util
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
D1 = Path("C:/x/trainer/runs/g22-k2-stage1-codex-r115-D1")
FFD = D1 / "wt/tools/methods/body/floor_from_dump.py"
NPZ = D1 / "inputs/g22_k2_src.npz"
PSELF = ROOT / "jobs/POLY63-A/hooks/pockets_self.py"
ENVC = ROOT / "jobs/garibaldi22/body-training-1619/hooks/envelope_check.py"
D1_PLAN = D1 / "built/plan.json"
FILL_K2 = Path("C:/x/ev_1619/r4/fill_k2_a.json")
KEY = Path("G:/Мой диск/AGR-evidence/1855-trainer-v0/bank/g22-k2-stage1/k2_v002r1_body_quad.fbx")
F63 = Path("C:/x/ev_1619/r6/floor_63A_a.json")
E63 = Path("C:/x/ev_1619/r6/env_63A_a.json")
BLENDER = "C:/Program Files/Blender Foundation/Blender 5.1/blender.exe"
PINS = {NPZ: "5eee4ac6911acb6c79e4d9d9871136d2eeb482fb5f8848f11ca179b397fc4622",
        FFD: "c2eb4f8542c8401e36e4cf8509c836b1cc1045655a0ca74448bcf01022f2fbd1",
        PSELF: "282af95c7e68a9fa208194b00b44f03aeab80c541443ebba62d44fbb6e6c059b",
        ENVC: "b67452ffb212ef904ba5089c0e2f95778da2dc7822522c96fb3879ced2f5e5d6",
        D1_PLAN: "5cf2bdbb51178900ef22362126fccb15df43a4637f8c23632e6f6747d1f25895",
        FILL_K2: "b8c0a4efcdb646f933c19d9974a1e52ac0d09806c133888d9df5a5d3d9759401",
        KEY: "5b1e8d76c81de07dd62a94a1419a1f0bb6f5c82bd069592c2453f21b94f0f200",
        F63: "a6e92c8564427d1f1dcca998d425db31e07aa78efa689d98200aae6e3fdfb890",
        E63: "ae18326d66f9beb194a411b4986b8748100ab963856602594718a5f8c0d0bb6b",
        Path("C:/x/trainer/runs/g22-k2-stage1-codex-r115-D1/score/form_v2/G22_k2/key_used.json"):
            "4cb3cbfcfa3d4472d7f85b84d166f4a48fa4ea25592a631fd82c0022f00af5b9"}
WITNESS = (538.656, 1038.941)  # env_k2_a.json pocket 1 centre (accepted repair list)
sys.path.insert(0, str(Path(__file__).resolve().parent))
import substitute as sub  # noqa: E402
SUB = None


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def preflight():
    bad = {str(p): (sha(p) if p.exists() else "missing") for p, want in PINS.items()
           if not p.exists() or sha(p) != want}
    if bad:
        sys.exit("refused: pinned input mismatch %s" % json.dumps(bad, ensure_ascii=False))


def run(cmd, log, cwd=None):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=os.pathsep.join([str(ROOT), str(ROOT / "src")]))
    t = time.time()
    p = subprocess.run([str(c) for c in cmd], capture_output=True, text=True, encoding="utf-8", errors="replace",
                       cwd=cwd or ROOT, env=env)
    Path(log).write_text(p.stdout[-20000:] + "\n--- stderr\n" + p.stderr[-8000:], encoding="utf-8")
    return p.returncode, round(time.time() - t, 1)


def load_pself():
    spec = importlib.util.spec_from_file_location("pockets_self_r117", PSELF)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def centroid(poly):
    xs, ys = zip(*poly)
    return sum(xs) / len(xs), sum(ys) / len(ys)


def ring(plan):
    return json.loads(Path(plan).read_text(encoding="utf-8"))["rings"][0]["xy"]


def moved_outside(a_xy, b_xy, fills, near=0.05):
    """A ring vertices > near from every fill polygon that have no B vertex within 1 mm."""
    from shapely.geometry import Point, Polygon
    polys = [Polygon(f).buffer(near) for f in fills]
    n = 0
    for p in a_xy:
        if any(q.contains(Point(p)) for q in polys):
            continue
        if min(math.dist(p, b) for b in b_xy) > 1e-3:
            n += 1
    return n


def score(plan, work, log):
    rc_b, t_b = run([sys.executable, "-m", "dt_ai.cli.agr", "body", "--blender", BLENDER, plan, work / "body",
                     "--max-side", "3.6"], log + ".body.log")
    if rc_b != 0:
        return {"body_rc": rc_b, "body_s": t_b}
    rc_s, t_s = run([sys.executable, "-m", "dt_ai.cli.agr", "trainer", "score", "g22-k2-stage1", "--built",
                     work / "body/body.fbx", "--out", work / "score.json"], log + ".score.log")
    out = {"body_rc": rc_b, "body_s": t_b, "score_rc": rc_s, "score_s": t_s, "fbx_sha256": sha(work / "body/body.fbx")}
    if rc_s == 0:
        rep = json.loads((work / "score.json").read_text(encoding="utf-8"))
        steps = {k: v["status"] for k, v in rep["steps"].items()}
        out.update(trainer_first_failing_step=rep["first_failing_step"], trainer_score=rep["score"],
                   form_p95_m=rep["form_p95_m"], trainer_form_v2=steps["form_v2"],
                   trainer_form_v2_reason=rep["steps"]["form_v2"].get("reason"), steps=steps)
        # substitute form_v2 (pinned key sections missing on this PC; parity 15/15 in substitute.py)
        key, ksec = SUB
        it = sub.items(key, ksec, sub.extract(work / "body/body.fbx", work / "sub.extract.json", work / "sub.extract.log"))
        v, nfail = sub.verdict(it)
        st = dict(steps, form_v2="pass" if v == "ok" else "fail")
        out.update(form_v2=st["form_v2"], form_v2_fail_count=nfail,
                   form_v2_fails={k: d for k, (s, d) in it.items() if s == "fail"},
                   first_failing_step=next((s for s in ("artifact", "readback", "bounds", "topology", "form", "form_v2",
                                                        "vlm", "package") if st.get(s) not in ("pass", "not_applicable")), None))
    return out


def arm(kind, d, ps):
    d.mkdir(parents=True)
    res = {"arm": kind}
    rc, t = run([sys.executable, FFD, NPZ, d / "plan0.json", "--seal", "windows", "--openings"], d / "ffd0.log", cwd=FFD.parent)
    res.update(ffd0_rc=rc, ffd0_s=t)
    plan = d / "plan0.json"
    if kind == "B":
        rc, t = run([sys.executable, PSELF, d / "plan0.json", d / "pk.json", "--fill", d / "fill.json"], d / "pk.log")
        res.update(pself_rc=rc, pself_s=t)
        pk = json.loads((d / "pk.json").read_text(encoding="utf-8"))
        res.update(pockets=[(r["at"], r["depth_m"], r["decision"]) for r in pk["pockets"]], fill=pk["fill"], keep=pk["keep"])
        fills = json.loads((d / "fill.json").read_text(encoding="utf-8"))["polygons"] if (d / "fill.json").exists() else []
        acc = [centroid(p) for p in json.loads(FILL_K2.read_text(encoding="utf-8"))["polygons"]]
        mine = [centroid(p) for p in fills]
        res["fill_match_accepted"] = {"accepted": len(acc), "candidate": len(mine),
                                      "matched": sum(1 for c in acc if mine and min(math.dist(c, m) for m in mine) <= 0.15),
                                      "witness_filled": bool(mine) and min(math.dist(WITNESS, m) for m in mine) <= 0.5}
        rc, t = run([sys.executable, FFD, NPZ, d / "plan.json", "--seal", "windows", "--openings", "--fill",
                     d / "fill.json"], d / "ffd1.log", cwd=FFD.parent)
        res.update(ffd1_rc=rc, ffd1_s=t)
        plan = d / "plan.json"
        res["invariance_moved_outside_fills"] = moved_outside(ring(d / "plan0.json"), ring(plan), fills)
        res["ring_vertices"] = [len(ring(d / "plan0.json")), len(ring(plan))]
    res["parity_rings_equal_d1"] = ring(d / "plan0.json") == ring(D1_PLAN)
    res.update(score(plan, d, str(d / "s")))
    return res


def controls(out, ps):
    """63A accepted-lineage control + synthetic perturbations (pure census, no DCC)."""
    rows63, fills63 = ps.census(ring(F63))
    env = json.loads(E63.read_text(encoding="utf-8"))["pockets"]
    exp_fill = sum(p["depth_m"] <= 0.4 for p in env)
    res = {"63A": {"fill": len(fills63), "keep": len(rows63) - len(fills63), "expected_fill": exp_fill,
                   "expected_keep": len(env) - exp_fill,
                   "depths_match": sorted(round(r["depth_m"], 2) for r in rows63) == sorted(round(p["depth_m"], 2) for p in env)}}

    def notch(depth, shift=0.0):
        s = shift
        xy = [(0, 0), (9.25, 0), (9.25, depth), (10.75, depth), (10.75, 0), (20, 0), (20, 10), (0, 10)] if depth else \
             [(0, 0), (20, 0), (20, 10), (0, 10)]
        return [(x + s, y + s) for x, y in xy]
    cases = {"P0_none": (notch(0), 0, 0), "P1_d0.10": (notch(0.10), 1, 0), "P2_d0.39": (notch(0.39), 1, 0),
             "P3_d0.41": (notch(0.41), 0, 1), "P4_d0.10_shift": (notch(0.10, 1000.0), 1, 0)}
    res["perturbations"] = {}
    for name, (xy, ef, ek) in cases.items():
        r, f = ps.census(xy)
        res["perturbations"][name] = {"fill": len(f), "keep": len(r) - len(f), "expected": [ef, ek],
                                      "as_expected": (len(f), len(r) - len(f)) == (ef, ek)}
    return res


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--controls-only", action="store_true")
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=False)
    preflight()
    ps = load_pself()
    global SUB
    SUB = sub.key_and_sections(out / "ksec")
    t0 = time.time()
    rec = {"schema": "r117-series/1", "pins": {str(k): v for k, v in PINS.items()}, "python": sys.version,
           "controls": controls(out, ps), "reps": []}
    (out / "receipt.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    if not a.controls_only:
        for k in range(1, a.reps + 1):
            pair = {}
            for kind in ("A", "B"):
                pair[kind] = arm(kind, out / ("rep%d" % k) / kind, ps)
                print(k, kind, json.dumps({x: pair[kind].get(x) for x in ("form_v2", "form_v2_fail_count", "first_failing_step",
                                           "trainer_form_v2", "parity_rings_equal_d1", "fill")}), flush=True)
            rec["reps"].append(pair)
            (out / "receipt.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    rec["wall_s"] = round(time.time() - t0, 1)
    rec["M117"] = {kind: sum(p[kind].get("form_v2") == "pass" for p in rec["reps"]) for kind in ("A", "B")}
    (out / "receipt.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"M117": rec["M117"], "wall_s": rec["wall_s"], "controls": rec["controls"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
