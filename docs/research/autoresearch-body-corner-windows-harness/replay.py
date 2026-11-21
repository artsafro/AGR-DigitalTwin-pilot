"""Standing #23 replay: stage-1 windows that run over a contour corner (OBSERVE, read-only).

    ../../.venv/Scripts/python.exe docs/research/autoresearch-body-corner-windows-harness/replay.py OUT.json

Loads ``straight`` and ``run_points`` verbatim from the pinned blob of the shared floor builder
(``jobs/garibaldi22/body-training-1619/hooks/floor_from_dump.py``), applies them to every stage-1 window of
the frozen floor.json inputs, and attributes the rejected 63C v001 irregular faces (core ``_angles``
definition, 15 deg) to the flagged corners. Every input is SHA-256 checked before and after; three
repeats must give byte-identical payloads. Nothing is written except OUT.json.
"""
import ast
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path

from shapely.geometry import Polygon
from shapely.ops import substring

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.qa import mesh_quality_core as core  # noqa: E402

BUILDER = "jobs/garibaldi22/body-training-1619/hooks/floor_from_dump.py"
BUILDER_BLOB = "3b865d46a787756053b6d7f7242d1356e2ed08cd"
EV = "G:/Мой диск/AGR-evidence/1619-body-training/"
# label: (path, set, verdict); SHA-256 of every input is pinned in inputs.json
NONE = "no corner rejection on record"
FLOORS = {
    "63C_v001": (EV + "tower-C/v001/floor.json", "train", "rejected"),
    "63C_v002": (EV + "tower-C/v002/floor.json", "train", "accepted"),
    "63A_v005": (EV + "tower-A/v005/floor_v005.json", "train", "accepted"),
    "63B_v007_A": (EV + "tower-B/v007/floor_A.json", "train", "accepted"),
    "63B_v007_B": (EV + "tower-B/v007/floor_B.json", "train", "accepted"),
    "G22_k3_j6": (EV + "round1-k3/floor_k3_j6.json", "holdout", NONE),
    "G22_k1_z": (EV + "round2-k1/floor_k1_z.json", "holdout", NONE),
    "G22_k1_z2": (EV + "round2-k1/floor_k1_z2.json", "holdout", NONE),
    "G22_k1_v003": (EV + "round2b-k1/floor_k1_v003.json", "holdout", NONE),
    "G22_k2_v002": (EV + "round4-k2-stage1/floor_k2_v002.json", "holdout", NONE),
}
SHA = json.loads((Path(__file__).with_name("inputs.json")).read_text(encoding="utf-8"))
DUMPS = {"63C_v001": "C:/x/ar15/r1/tmp/63C-v001.1/dump.json", "63C_v002": "C:/x/ar15/r1/tmp/63C-v002.1/dump.json"}
TOL_PRIMARY = 1.0  # the builder's own stage-2 default, straight(tol_deg=1.0)
TOL_SECONDARY = 15.0  # frozen after the training look, see contract
RADIUS_M = 2.0
IRREGULAR_DEG = 15.0


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def builder_funcs():
    src = subprocess.check_output(["git", "cat-file", "-p", BUILDER_BLOB], cwd=ROOT)
    tree = ast.parse(src)
    keep = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in ("straight", "run_points")]
    ns = {"math": math, "substring": substring}
    exec(compile(ast.Module(body=keep, type_ignores=[]), BUILDER_BLOB, "exec"), ns)
    return ns["straight"], ns["run_points"]


def turns(pts):
    out = []
    for a, b, c in zip(pts, pts[1:], pts[2:]):
        t1 = math.atan2(b[1] - a[1], b[0] - a[0])
        t2 = math.atan2(c[1] - b[1], c[0] - b[0])
        out.append((round(b[0], 3), round(b[1], 3), round(abs(math.degrees((t2 - t1 + math.pi) % (2 * math.pi) - math.pi)), 3)))
    return out


def floor_report(path, straight, run_points):
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    rings = [Polygon(r["xy"]) for r in d["rings"]]
    flagged = []
    for k, w in enumerate(d["windows"]):
        ring = rings[int(w[0])]
        pts = run_points(ring, float(w[1]), float(w[2]))
        if not straight(pts, TOL_PRIMARY):
            flagged.append({"window": k, "ring": int(w[0]), "s": [round(w[1], 3), round(w[2], 3)],
                            "secondary": not straight(pts, TOL_SECONDARY), "corners": turns(pts)})
    return {"windows": len(d["windows"]), "n_primary": len(flagged),
            "n_secondary": sum(f["secondary"] for f in flagged), "flagged": flagged}


def attribution(dump, corners):
    d = json.loads(Path(dump).read_text(encoding="utf-8"))
    tot = near = 0.0
    nf = nn = 0
    for o in d["objects"]:
        V = o["verts"]
        for f in o["faces"]:
            pts = [V[i] for i in f]
            if max(abs(x - 90.0) for x in core._angles(pts)) <= IRREGULAR_DEG + core.ANGLE_EPS_DEG:
                continue
            area = core._norm(core._newell(pts)) / 2.0
            cx = sum(p[0] for p in pts) / len(pts)
            cy = sum(p[1] for p in pts) / len(pts)
            nf += 1
            tot += area
            if any(math.hypot(cx - x, cy - y) <= RADIUS_M for x, y in corners):
                nn += 1
                near += area
    return {"irregular_faces": nf, "irregular_area": round(tot, 6), "near_faces": nn, "near_area": round(near, 6),
            "near_area_pct": round(100.0 * near / tot, 3) if tot else None}


def once():
    straight, run_points = builder_funcs()
    floors = {k: floor_report(v[0], straight, run_points) | {"set": v[1], "verdict": v[2]} for k, v in FLOORS.items()}
    corners = [(c[0], c[1]) for f in floors["63C_v001"]["flagged"] for c in f["corners"] if c[2] > TOL_PRIMARY]
    attr = {k: attribution(p, corners) for k, p in DUMPS.items()}
    train_acc = [v["n_primary"] for v in floors.values() if v["set"] == "train" and v["verdict"] == "accepted"]
    train_acc2 = [v["n_secondary"] for v in floors.values() if v["set"] == "train" and v["verdict"] == "accepted"]
    return {
        "floors": floors, "attribution_63C": attr, "corners_63C_v001": corners,
        "margin_primary": floors["63C_v001"]["n_primary"] - max(train_acc),
        "margin_secondary": floors["63C_v001"]["n_secondary"] - max(train_acc2),
        "holdout_primary": {k: v["n_primary"] for k, v in floors.items() if v["set"] == "holdout"},
        "holdout_secondary": {k: v["n_secondary"] for k, v in floors.items() if v["set"] == "holdout"},
    }


def main():
    out = Path(sys.argv[1]).resolve()
    paths = [v[0] for v in FLOORS.values()] + list(DUMPS.values())
    if out in {Path(p).resolve() for p in paths}:
        sys.exit("refused: OUT aliases an input")
    for p in paths:
        if sha(p) != SHA[p]:
            sys.exit("refused: hash mismatch %s" % p)
    blob = subprocess.check_output(["git", "rev-parse", "HEAD:" + BUILDER], cwd=ROOT, text=True).strip()
    runs = [json.dumps(once(), sort_keys=True) for _ in range(3)]
    for p in paths:
        if sha(p) != SHA[p]:
            sys.exit("refused: input changed during replay %s" % p)
    if len(set(runs)) != 1:
        sys.exit("noisy: repeats differ")
    payload = json.loads(runs[0])
    payload["provenance"] = {"builder_blob": BUILDER_BLOB, "head_builder_blob": blob, "inputs_sha256": SHA,
                             "repeats": 3, "identical": True, "payload_sha256": hashlib.sha256(runs[0].encode()).hexdigest()}
    out.write_text(json.dumps(payload, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    print("margin_primary", payload["margin_primary"], "margin_secondary", payload["margin_secondary"])
    print("holdout_primary", payload["holdout_primary"], "holdout_secondary", payload["holdout_secondary"])
    print("attribution", {k: (v["irregular_faces"], v["near_faces"], v["near_area_pct"]) for k, v in payload["attribution_63C"].items()})


if __name__ == "__main__":
    main()
