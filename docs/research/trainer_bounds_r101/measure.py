"""Research #101 (OBSERVE): KPP1 `bounds` from the DWG sources only (rule E1) vs the native trainer bounds step.

Replay: uv run --frozen python docs/research/trainer_bounds_r101/measure.py --out C:/x/<new-dir>
Contract: docs/research/autoresearch-trainer-bounds-source.md. No product code is changed.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import re
import statistics
import sys
import time
from pathlib import Path

import ezdxf
from ezdxf import bbox, recover

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.trainer import trainer as T  # noqa: E402  (native scorer, unchanged)

HERE = Path(__file__).resolve().parent
PHYS = ("A-WALL-", "A-GLAZ-", "S-STRS-")
MARK = re.compile(r"^[+-]?\d+,\d{3}$")


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def pinned(man):
    out = [(k, v) for k, v in man["code"].items()]
    for sec in ("kpp1", "ac08_heldout"):
        for k, v in man[sec].items():
            if isinstance(v, list):
                out.append(v)
            elif k == "built":
                out.extend(v.values())
    return [(str(ROOT / p) if not Path(p).is_absolute() else p, h) for p, h in out]


def preflight(man):
    bad = [(p, h, sha(p)) for p, h in pinned(man) if sha(p) != h]
    return bad


def read(path, tolerant=False):
    if tolerant:
        doc, aud = recover.readfile(path)
        return doc.modelspace(), {"recover_fixes": len(aud.fixes), "recover_errors": len(aud.errors)}
    return ezdxf.readfile(path).modelspace(), {}


def boxes(msp):
    for e in msp:
        try:
            b = bbox.extents([e], fast=True)
        except Exception:  # noqa: BLE001 - unreadable entity: skipped and counted by caller via layer census
            continue
        if b.has_data:
            yield e, (b.extmin.x, b.extmin.y, b.extmax.x, b.extmax.y)


def union(bs):
    bs = list(bs)
    if not bs:
        return None
    return (min(b[0] for b in bs), min(b[1] for b in bs), max(b[2] for b in bs), max(b[3] for b in bs))


def plan_footprint(msp, layers=PHYS):
    allb = list(boxes(msp))
    walls = union(b for e, b in allb if e.dxf.layer.startswith("A-WALL-"))
    counts = collections.Counter()
    if walls is None:
        return None, counts
    d = 5000.0
    box = (walls[0] - d, walls[1] - d, walls[2] + d, walls[3] + d)
    keep = {}
    for e, b in allb:
        pre = next((p for p in layers if e.dxf.layer.startswith(p)), None)
        if pre and b[0] >= box[0] and b[1] >= box[1] and b[2] <= box[2] and b[3] <= box[3]:
            counts[pre] += 1
            keep.setdefault(pre, []).append(b)
    return {p: union(v) for p, v in keep.items()}, counts


def facade_top(msp, layers=PHYS):
    ys = [b[3] for e, b in boxes(msp) if e.dxf.layer.startswith(layers)]
    return (max(ys) / 1000.0) if ys else None


def level_marks(msp):
    vals, offs = [], []
    for e in msp.query("TEXT MTEXT"):
        t = (e.plain_text() if e.dxftype() == "MTEXT" else e.dxf.text).strip()
        if MARK.match(t):
            v = float(t.replace(",", "."))
            vals.append(v)
            offs.append(round(e.dxf.insert.y - 1000 * v, -1))
    return vals, collections.Counter(offs).most_common(3)


def to_world(xy_mm, frame):
    ox, oy = frame["origin_mm"]
    sx, sy = frame["frame_shift_m"]
    return ((xy_mm[0] - ox) / 1000.0 + sx, (xy_mm[1] - oy) / 1000.0 + sy)


def rb_box(lo, hi):
    return {"meshes": [{"bounds_m": [list(lo), list(hi)]}]}


def box_of(rb):
    lo = [min(m["bounds_m"][0][i] for m in rb["meshes"]) for i in range(3)]
    hi = [max(m["bounds_m"][1][i] for m in rb["meshes"]) for i in range(3)]
    return lo, hi


def faces(rb, key):
    (a, b), (c, d) = box_of(rb), box_of(key)
    names = ["x_min", "y_min", "z_min", "x_max", "y_max", "z_max"]
    return {n: round(v1 - v2, 4) for n, v1, v2 in zip(names, a + b, c + d)}


def envelope(fp, z0, z1, frame, layers):
    bs = [fp[p] for p in layers if fp.get(p)]
    u = union(bs)
    lo, hi = to_world(u[:2], frame), to_world(u[2:], frame)
    return rb_box((lo[0], lo[1], z0), (hi[0], hi[1], z1))


def one_repeat(man, out, i):
    work = out / f"rep{i}"
    work.mkdir(parents=True)
    k = man["kpp1"]
    frame = json.loads(Path(k["frame"][0]).read_text(encoding="utf-8"))
    l03, _ = read(k["l03_dxf"][0])
    l01, _ = read(k["l01_dxf"][0])
    fp, counts = plan_footprint(l03)
    z1 = facade_top(l01)
    marks, offs = level_marks(l01)
    key = T.readback(k["key"][0], work / "key.json", work)
    rej = T.readback(k["rejected"][0], work / "rejected.json", work)
    if key is None or rej is None:
        return {"status": "native readback failed (key or rejected)"}
    rep = {"plan_counts": dict(counts), "facade_top_m": z1, "mark_max_m": max(marks), "mark_offset_mode": offs,
           "calibration": {"accepted_vs_key": T.bounds_step(key, key), "rejected_vs_key": T.bounds_step(rej, key)}}
    variants = {
        "E1": envelope(fp, 0.0, z1, frame, PHYS),
        "P1_no_stairs": envelope(fp, 0.0, z1, frame, ("A-WALL-", "A-GLAZ-")),
        "P2_top_from_marks": envelope(fp, 0.0, max(marks), frame, PHYS),
        "P3_no_glazing": envelope(fp, 0.0, z1, frame, ("A-WALL-", "S-STRS-")),
    }
    rep["variants"] = {n: {"step": T.bounds_step(rb, key), "faces": faces(rb, key), "box": box_of(rb)}
                       for n, rb in variants.items()}
    stairs = variants["E1"]["meshes"][0]["bounds_m"] if fp.get("S-STRS-") else None
    s_lo = to_world(fp["S-STRS-"][:2], frame) if fp.get("S-STRS-") else None
    s_hi = to_world(fp["S-STRS-"][2:], frame) if fp.get("S-STRS-") else None
    runs = {}
    for rid, (p, _h) in k["built"].items():
        rb = T.readback(p, work / f"{rid}.json", work)
        if rb is None:
            runs[rid] = {"status": "native readback failed"}
            continue
        row = {"baseline": T.bounds_step(rb, key), "faces": faces(rb, key)}
        if s_lo:
            lo, hi = box_of(rb)
            u = rb_box((min(lo[0], s_lo[0]), min(lo[1], s_lo[1]), lo[2]), (max(hi[0], s_hi[0]), max(hi[1], s_hi[1]), hi[2]))
            row["with_stair_box"] = {"step": T.bounds_step(u, key), "faces": faces(u, key)}
        runs[rid] = row
    rep["runs"] = runs
    rep["stairs_box_used"] = bool(stairs)
    return rep


def heldout(man, out):
    h = man["ac08_heldout"]
    msp, info = read(h["dxf"][0], tolerant=True)
    fp, counts = plan_footprint(msp)
    work = out / "ac08"
    work.mkdir(parents=True)
    key = T.readback(h["key"][0], work / "key.json", work)
    res = {"recover": info, "e1_counts": dict(counts), "key_box": box_of(key) if key else None,
           "layers_seen": sorted({e.dxf.layer for e in msp})[:60]}
    if fp is None:
        res["status"] = "not_exercised"
        res["reason"] = "no A-WALL-* entities: rule E1 has no input on this drawing (SPDS / PDF-import layers)"
    else:
        res["status"] = "exercised"
        res["footprint"] = fp
    return res


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    out = Path(a.out)
    if out.exists():
        sys.exit(f"--out must be a new folder: {out}")
    man = json.loads((HERE / "manifest.json").read_text(encoding="utf-8"))
    t0 = time.monotonic()
    bad = preflight(man)
    if bad:
        sys.exit(f"manifest mismatch: {bad}")
    out.mkdir(parents=True)
    reps, walls = [], []
    for i in range(1, man["repeats"] + 1):
        left = man["budget_s"] - (time.monotonic() - t0)
        if left < 60:
            reps.append({"status": "budget stop", "left_s": round(left, 1)})
            break
        s = time.monotonic()
        r = one_repeat(man, out, i)
        r["wall_s"] = round(time.monotonic() - s, 1)
        reps.append(r)
        walls.append(r["wall_s"])
    ho = heldout(man, out)
    post = preflight(man)
    e1 = [r["variants"]["E1"]["step"]["max_corner_dev_m"] for r in reps if "variants" in r]
    base = {rid: [r["runs"][rid]["baseline"].get("max_corner_dev_m") for r in reps if "runs" in r]
            for rid in man["kpp1"]["built"]}
    summary = {
        "complete_repeats": len(e1),
        "e1_dev_m": {"median": statistics.median(e1) if e1 else None, "min": min(e1, default=None), "max": max(e1, default=None)},
        "baseline_dev_m_median": {rid: statistics.median(v) for rid, v in base.items() if v},
        "e1_pass": sum(r["variants"]["E1"]["step"]["status"] == "pass" for r in reps if "variants" in r),
        "heldout": ho["status"],
        "input_parity_after": not post,
        "wall_s": round(time.monotonic() - t0, 1),
        "repeat_wall_s": walls,
    }
    rec = {"schema": "r101-receipt/1", "summary": summary, "repeats": reps, "heldout": ho,
           "manifest_sha256": sha(HERE / "manifest.json"), "measure_sha256": sha(Path(__file__))}
    (out / "receipt.json").write_text(json.dumps(rec, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
