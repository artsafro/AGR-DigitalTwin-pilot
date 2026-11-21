"""Standing #31 harness: Ground quality Q = 1e4 * (V + F + C) / T per dump (contract: ../autoresearch-ground-quality.md).

V/F = xview_gate.gate_report (NPM, coords local) overlapping vertices / faces; C = crack edges (open edge whose
midpoint is within FACE_M of another open edge of the same part sharing no vertex); T = fan triangles.
Modes: clean (3 repeats), rigid (translate + rotate 30 deg Z), inject (unweld 50 interior vertices by 1 mm, accepted only).
Usage: uv run python score.py --out <new.json> [--dumps C:/x/ev_t_193a0887/dumps-v002] [--only A1,F5] [--modes clean,rigid,inject]
"""
import argparse
import hashlib
import json
import math
import sys
import time
from pathlib import Path

import numpy as np

from dt_ai.ops import inv_xview, xview_gate
from dt_ai.ops.xview_gate import Part

FACE_M = inv_xview.tolerance_for("NPM").face_m
SHIFT = np.array([123.456, -78.9, 3.21])
ANG = math.radians(30.0)


def open_edges(faces):
    cnt = {}
    for f in faces:
        n = len(f)
        for i in range(n):
            a, b = f[i], f[(i + 1) % n]
            k = (a, b) if a < b else (b, a)
            cnt[k] = cnt.get(k, 0) + 1
    return np.array([k for k, c in cnt.items() if c == 1], dtype=np.int64).reshape(-1, 2)


def crack_edges(v, faces, r=FACE_M) -> int:
    e = open_edges(faces)
    if not len(e):
        return 0
    p, q = v[e[:, 0]], v[e[:, 1]]
    mid = (p + q) / 2
    lo = np.minimum(p, q) - r
    hi = np.maximum(p, q) + r
    cell = max(float(np.median(np.linalg.norm(q - p, axis=1))), 0.05)
    grid = {}
    for j in range(len(e)):                       # bucket each edge's padded box
        a = np.floor(lo[j] / cell).astype(int)
        b = np.floor(hi[j] / cell).astype(int)
        if np.prod(b - a + 1) > 64:               # very long edge: bucket by sampling along it
            n = int(np.ceil(np.linalg.norm(q[j] - p[j]) / cell)) + 1
            keys = {tuple(np.floor((p[j] + (q[j] - p[j]) * t) / cell).astype(int)) for t in np.linspace(0, 1, n + 1)}
            keys = {(x + dx, y + dy, z + dz) for x, y, z in keys for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                    for dz in (-1, 0, 1)}
        else:
            keys = {(x, y, z) for x in range(a[0], b[0] + 1) for y in range(a[1], b[1] + 1)
                    for z in range(a[2], b[2] + 1)}
        for k in keys:
            grid.setdefault(k, []).append(j)
    hit = np.zeros(len(e), dtype=bool)
    for i in range(len(e)):
        k = tuple(np.floor(mid[i] / cell).astype(int))
        cand = [j for j in grid.get(k, ()) if j != i]
        if not cand:
            continue
        cand = np.array(cand)
        cand = cand[(e[cand, 0] != e[i, 0]) & (e[cand, 0] != e[i, 1]) & (e[cand, 1] != e[i, 0])
                    & (e[cand, 1] != e[i, 1])]
        if not len(cand):
            continue
        d = q[cand] - p[cand]
        t = np.clip(np.einsum("ij,ij->i", mid[i] - p[cand], d) / np.maximum(np.einsum("ij,ij->i", d, d), 1e-30), 0, 1)
        dist = np.linalg.norm(p[cand] + d * t[:, None] - mid[i], axis=1)
        hit[i] = bool((dist <= r).any())
    return int(hit.sum())


def rigid(parts):
    c, s = math.cos(ANG), math.sin(ANG)
    R = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1.0]])
    return [Part(p.name, p.vertices @ R.T + SHIFT, p.faces,
                 None if p.location is None else p.location @ R.T + SHIFT) for p in parts]


def inject(parts, n=50):
    p0 = parts[0]
    v = np.asarray(p0.vertices, dtype=np.float64)
    border = set(open_edges(p0.faces).ravel().tolist())
    first = {}
    for fi, f in enumerate(p0.faces):
        for x in f:
            first.setdefault(x, fi)
    interior = [x for x in sorted(first) if x not in border]
    k = max(len(interior) // n, 1)
    pick = interior[::k][:n]
    faces = [list(f) for f in p0.faces]
    extra = []
    for x in pick:
        fi = first[x]
        extra.append(v[x] + np.array([0.001, 0.0, 0.0]))
        faces[fi][faces[fi].index(x)] = len(v) + len(extra) - 1
    nv = np.vstack([v, np.array(extra)]) if extra else v
    return [Part(p0.name, nv, tuple(tuple(f) for f in faces), p0.location)] + list(parts[1:]), len(pick)


def score(parts, ground_only=True) -> dict:
    parts = [p for p in parts if not p.name.upper().startswith("UCX_")]
    if ground_only:                               # amendment 1: the Ground surface object only
        parts = [p for p in parts if p.name.endswith("_Ground")]
        if len(parts) != 1:
            raise ValueError(f"expected one *_Ground part, got {[p.name for p in parts]}")
    rep = xview_gate.gate_report(parts, "NPM", "local")
    tot = rep["totals"]
    rows, C, T, O = [], 0, 0, 0
    for p, r in zip(parts, rep["parts"]):
        loc = np.zeros(3) if p.location is None else p.location
        c = crack_edges(np.asarray(p.vertices) - loc, p.faces)
        t = sum(len(f) - 2 for f in p.faces)
        o = len(open_edges(p.faces))
        C, T, O = C + c, T + t, O + o
        rows.append({"part": p.name, "V": r["overlapping_vertices"], "F": r["overlapping_faces"], "C": c, "T": t,
                     "open_edges": o})
    V, F = tot["overlapping_vertices"], tot["overlapping_faces"]
    return {"Q": 1e4 * (V + F + C) / T, "V": V, "F": F, "C": C, "T": T, "open_edges": O,
            "vertex_pairs": tot["vertex_pairs"], "face_pairs": tot["face_pairs"], "parts": len(parts),
            "per_part": rows if len(rows) <= 40 else sorted(rows, key=lambda x: -(x["V"] + x["F"] + x["C"]))[:40]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dumps", default="C:/x/ev_t_193a0887/dumps-v002")
    ap.add_argument("--out", required=True)
    ap.add_argument("--only", default="")
    ap.add_argument("--modes", default="clean,rigid,inject")
    ap.add_argument("--repeats", type=int, default=3)
    a = ap.parse_args()
    out = Path(a.out)
    if out.exists():
        raise SystemExit(f"{out} exists; write a new versioned result")
    d = Path(a.dumps)
    frozen = {ln.split()[1].lstrip("*"): ln.split()[0] for ln in (d / "dumps.sha256").read_text().splitlines() if ln}
    only = set(filter(None, a.only.split(",")))
    modes = a.modes.split(",")
    res = {"contract": "docs/research/autoresearch-ground-quality.md", "modes": modes, "inputs": {}}
    for name, h in sorted(frozen.items()):
        iid = name.split("_")[0]
        if only and iid not in only:
            continue
        path = d / name
        if hashlib.sha256(path.read_bytes()).hexdigest() != h:
            raise SystemExit(f"dump hash mismatch: {path}")
        parts = xview_gate.load_npz(path)
        row: dict = {"dump": name, "dump_sha256": h}
        t0 = time.time()
        if "clean" in modes:
            reps = [score(parts) for _ in range(a.repeats)]
            qs = [r["Q"] for r in reps]
            row["clean"] = reps[0]
            row["clean_Q_runs"] = qs
            row["clean_Q_median"] = float(np.median(qs))
            row["clean_spread"] = max(qs) - min(qs)
            row["Q_all"] = {k: v for k, v in score(parts, ground_only=False).items() if k != "per_part"}
        if "rigid" in modes:
            row["rigid"] = {k: v for k, v in score(rigid(parts)).items() if k != "per_part"}
        if "inject" in modes and iid.startswith("A"):
            inj, n = inject(parts)
            row["inject"] = {"unwelded": n, **{k: v for k, v in score(inj).items() if k != "per_part"}}
        row["seconds"] = round(time.time() - t0, 1)
        res["inputs"][iid] = row
        c = row.get("clean", {})
        print(iid, "Q=%.3f" % c.get("Q", float("nan")), "V/F/C/T", c.get("V"), c.get("F"), c.get("C"), c.get("T"),
              "rigidQ=%.3f" % row.get("rigid", {}).get("Q", float("nan")),
              "injQ=%.3f" % row.get("inject", {}).get("Q", float("nan")), row["seconds"], "s", flush=True)
        out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
