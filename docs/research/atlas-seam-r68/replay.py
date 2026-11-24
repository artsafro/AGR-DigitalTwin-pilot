"""Standing #67 replay: cross-UV-seam Diffuse continuity on AC08 v007 (rejected) vs v010 (accepted), OBSERVE.

Contract: docs/research/autoresearch-ac08-seam-continuity.md. Runner layout reuses #66 (atlas-texel-r66/replay.py).
"""
from __future__ import annotations

import hashlib
import io
import json
import math
import statistics
import subprocess
import sys
import time
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from PIL import Image

from twinqa.sintez_uv import _polygons

ROOT = Path(__file__).resolve().parents[3]
BASE = "4288c54de328db7a5037b57707862319f7aa6ff0"
REFERENCE = "efca352cb5fb60cc7bcd9f4f15204de6246480c0:docs/research/atlas-seam-r67/receipt.json"
DRIVE = Path("G:/Мой диск/AGR-evidence")
BLENDER = Path("C:/Program Files/Blender Foundation/Blender 5.1/blender.exe")
PINS = {BLENDER: "1e6624af112b3c936f4b038b025ebd2bf00ae72c4b62881a6787166d71c58fa5"}
VERSIONS = {
    "v007": ({1001}, "271ee11bf78200ef883814a4ac108ef289098d0f106da01e8d9fc57da888c295",
             "9feb8685a71dec4cd2bb746bd3695bccdce3e648199dc0f32cb3738f6c430ea2"),
    "v010": ({1001, 1002}, "2fe983791566477e297aeefa09f04a1b7d176312c3fce1a8c9f1cf26138013bb",
             "338edcd767c0c6c99f762d4b7a9dcfd9407da030086ccb5b96e551d3bffae0cc"),
}
STATES = {"clean": 0, "+2px": 2, "+5px": 5}  # V shift in px of the tile, +X-facing target faces only
INWARD_PX, UV_EPS, VISIBLE = 2.0, 1e-6, 0.10
FIRST, TOTAL = 60, 240


def _tile(uv):
    cu, cv = (statistics.fmean(a) for a in zip(*uv, strict=True))
    u, v = math.floor(cu), math.floor(cv)
    return 1001 + u + 10 * v, (u, v), (cu, cv)


def _normal_x(xyz):
    p = np.asarray(xyz, dtype=float)
    n = np.zeros(3)
    for a, b in zip(p, np.roll(p, -1, axis=0), strict=True):  # Newell
        n += [(a[1] - b[1]) * (a[2] + b[2]), (a[2] - b[2]) * (a[0] + b[0]), (a[0] - b[0]) * (a[1] + b[1])]
    length = np.linalg.norm(n)
    return n[0] / length if length > 0 else 0.0


def _positions(side, origin, uv_a, uv_b, centroid, t, inward):
    """Tile-local coordinates in pixels, before the #67 wrap."""
    a, b, c = (np.asarray(x, dtype=float) * side for x in (uv_a, uv_b, centroid))
    p = a[None, :] + t[:, None] * (b - a)[None, :]
    d = b - a
    n = np.array([-d[1], d[0]]) / np.linalg.norm(d)
    if np.dot(n, c - (a + b) / 2) < 0:
        n = -n
    return p + inward * n - np.asarray(origin, dtype=float) * side


def _rgb(img, p):
    side = img.shape[0]
    p = np.mod(p, side)  # #67 legacy raw score only; contrast support is checked before sampling.
    col = np.minimum(p[:, 0].astype(int), side - 1)
    row = np.minimum((side - p[:, 1]).astype(int), side - 1)
    return img[row, col].astype(float)


def _on_tile(p, side):
    return ((0 <= p) & (p < side)).all(axis=1)


def _inside(p, uv, origin, side):
    """Even-odd UV ring containment, also valid for concave faces."""
    ring = (np.asarray(uv) - origin) * side
    x, y = p.T
    inside = np.zeros(len(x), dtype=bool)
    for (ax, ay), (bx, by) in zip(ring, np.roll(ring, -1, axis=0), strict=True):
        if ay != by:
            inside ^= ((ay > y) != (by > y)) & (x < ax + (y - ay) * (bx - ax) / (by - ay))
    return inside & _on_tile(p, side)


def _error(a, b):
    return np.abs(a - b).mean(axis=1) / 255


def measure(rb, images, targets, witness="seam_first"):
    """images: tile -> uint8 HxWx3 (non-target tiles may be any array); original readback stays untouched.

    witness: "plus_x" = R1 (+X-facing target faces), "seam_first" = R2 (smaller polygon index of each seam pair).
    """
    if witness not in ("plus_x", "seam_first"):
        raise ValueError(f"unknown witness: {witness}")
    if not rb.get("meshes"):
        raise ValueError("no meshes in native readback")
    before = json.dumps(rb, sort_keys=True)
    edges = Counter()
    diffs = {s: defaultdict(list) for s in STATES}
    cross, within, changed = ({s: [] for s in STATES}, {s: [] for s in STATES}, Counter())
    seam_edges = Counter()
    n_shifted = n_non_target = 0
    for mesh in rb["meshes"]:
        name = mesh["name"]
        if name.upper().startswith("UCX_") or name.endswith(("MainGlass", "GroundGlass", "GroundElGlass")):
            continue
        faces, owners = {}, defaultdict(list)
        polys = mesh["face_geometry"]["polygons"]
        for index, xyz, uv, _material in _polygons(mesh):
            tile, origin, centroid = _tile(uv)
            if tile not in images:
                raise ValueError(f"{name}[{index}]: no bound Diffuse for tile {tile}")
            plus_x = tile in targets and _normal_x(xyz) > 0.9
            faces[index] = (tile, origin, centroid, uv, plus_x, {vi: k for k, vi in enumerate(polys[index])})
            for vi, vj in zip(polys[index], polys[index][1:] + polys[index][:1], strict=True):
                owners[(min(vi, vj), max(vi, vj))].append(index)
        verts = mesh["face_geometry"]["vertices"]
        seams = []  # (tile, length, [(face index, uv ends)] x 2), first side = smaller polygon index
        for (vi, vj), fs in owners.items():
            if len(fs) != 2:
                edges["boundary" if len(fs) == 1 else "non_manifold"] += 1
                continue
            fs = sorted(fs)
            f1, f2 = (faces[f] for f in fs)
            if f1[0] != f2[0] or f1[0] not in targets:
                edges["border" if f1[0] != f2[0] else "non_target"] += 1
                continue
            ends = [[f[3][f[5][vi]], f[3][f[5][vj]]] for f in (f1, f2)]
            if all(abs(x - y) <= UV_EPS for p, q in zip(*ends, strict=True) for x, y in zip(p, q, strict=True)):
                edges["continuous"] += 1
                continue
            edges["seam"] += 1
            seam_edges[f1[0]] += 1
            seams.append((f1[0], math.dist(verts[vi], verts[vj]), list(zip(fs, ends, strict=True))))
        if witness == "plus_x":
            shifted = {i for i, f in faces.items() if f[4]}
        else:
            shifted = {s[2][0][0] for s in seams}
        n_shifted += len(shifted)
        n_non_target += sum(faces[i][0] not in targets for i in shifted)
        for tile, length, sides in seams:
            k = max(2, math.ceil(length * 1000))
            t = (np.arange(k) + 0.5) / k
            img = images[tile]
            side = img.shape[0]
            positions = []
            valid = np.ones(k, dtype=bool)
            for i, (ua, ub) in sides:
                f = faces[i]
                points = [_positions(side, f[1], ua, ub, f[2], t, offset) for offset in (INWARD_PX, 6.0)]
                for p in points:
                    valid &= _inside(p, f[3], f[1], side)
                positions.append(points)
            clean_vectors = None
            for state, px in STATES.items():
                rgb, interior = [], []
                for (i, (ua, ub)), points in zip(sides, positions, strict=True):
                    f = faces[i]
                    dv = px / side if (px and i in shifted) else 0.0
                    sh = [[ua[0], ua[1] + dv], [ub[0], ub[1] + dv]]
                    p2 = _positions(side, f[1], sh[0], sh[1], (f[2][0], f[2][1] + dv), t, INWARD_PX)
                    p6 = points[1][valid] + (0, dv * side)
                    if not (_on_tile(p2[valid], side).all() and _on_tile(p6, side).all()):
                        raise ValueError("contrast witness crosses tile on eligible support")
                    rgb.append(_rgb(img, p2))
                    interior.append(_rgb(img, p6))
                raw = _error(*rgb)
                diffs[state][tile].extend(raw.tolist())
                cross[state].extend(raw[valid].tolist())
                first, second = (a[valid] for a in rgb)
                within[state].extend(((_error(first, interior[0]) + _error(second, interior[1])) / 2).tolist())
                vectors = np.concatenate((first, second, *interior))
                if clean_vectors is None:
                    clean_vectors = vectors
                changed[state] += int(np.count_nonzero(np.any(vectors != clean_vectors, axis=1)))
    if json.dumps(rb, sort_keys=True) != before:
        raise ValueError("original readback changed")
    if not any(diffs["clean"].values()):
        raise ValueError("not_exercised: no seam samples on target tiles")
    states = {}
    for state, px in STATES.items():
        rows = {}
        for tile in sorted(targets):
            s = diffs[state].get(tile, [])
            rows[tile] = {"seam_edges": seam_edges[tile], "samples": len(s),
                          "mean": statistics.fmean(s) if s else None,
                          "p95": float(np.percentile(s, 95)) if s else None,
                          "visible_fraction": sum(x > VISIBLE for x in s) / len(s) if s else None}
        pooled = [x for tile in targets for x in diffs[state].get(tile, [])]
        contrast = {"samples": 0, "status": "not_exercised", "rgb_vectors_changed": 0}
        if cross[state]:
            a, b = statistics.fmean(cross[state]), statistics.fmean(within[state])
            floor = 1 / 255
            contrast = {"samples": len(cross[state]), "status": "measured", "cross": a, "within": b,
                        "ratio": a / max(b, floor), "floor_used": b < floor,
                        "rgb_vectors_changed": changed[state]}
        states[state] = {"tiles": rows, "score": statistics.fmean(pooled),
                         "contrast": contrast,
                         "changed_faces": n_shifted if px else 0,
                         "non_target_changed_faces": n_non_target if px else 0}
    return {"states": states, "edges": dict(edges), "witness": witness}


def fixture(v):
    d = DRIVE / f"559-tec26-oks-ac08-pilot-{v}"
    return d / "SM_Nku_1.zip", d / "npm_atlas.json"


def preflight():
    pins = PINS | {p: h for v, (_, a, b) in VERSIONS.items() for p, h in zip(fixture(v), (a, b), strict=True)}
    for p, expected in pins.items():
        with p.open("rb") as f:
            if hashlib.file_digest(f, "sha256").hexdigest() != expected:
                raise ValueError(f"fixture hash mismatch: {p}")
    subprocess.run(["git", "diff", "--quiet", BASE, "--", "src", "tools", "standards", "adapters",
                    "uv.lock", "pyproject.toml"], cwd=ROOT, check=True)
    return {str(p): h for p, h in pins.items()}


def one(v, out, timeout):
    from twinqa.scene import readback

    archive, plan_path = fixture(v)
    target = VERSIONS[v][0]
    plan = json.loads(plan_path.read_text(encoding="utf-8"))["finishes"]
    expected = {d["udim"]: 256 if d["px_per_m"] is None else 4096 for d in plan.values()}
    if target != {t for t, side in expected.items() if side == 4096} or len(expected) != len(plan):
        raise ValueError(f"{v}: planning finish bindings mismatch")
    fbx = out / f"{v}_SM_Nku_1.fbx"
    images = {}
    with zipfile.ZipFile(archive) as z:
        fbx.write_bytes(z.read("SM_Nku_1.fbx"))
        for name in z.namelist():
            if "_Diffuse_" in name and name.endswith(".png"):
                t = int(name.rsplit(".", 2)[1])
                with Image.open(io.BytesIO(z.read(name))) as im:
                    im.load()
                    if im.size[0] != im.size[1] or im.format != "PNG" or t in images:
                        raise ValueError(f"{v}: unexpected image: {name}")
                    images[t] = np.asarray(im.convert("RGB"))
    sides = {t: a.shape[0] for t, a in images.items()}
    if sides != expected:
        raise ValueError(f"{v}: actual Diffuse tile sizes {sides} != {expected}")
    rb = readback(fbx, blender=str(BLENDER), timeout=timeout)
    return measure(rb, images, target) | {"tile_px": sides, "fbx_sha256": hashlib.sha256(fbx.read_bytes()).hexdigest()}


def summarize(rounds, reference):
    def stats(values):
        return {"median": statistics.median(values), "spread": max(values) - min(values)}

    def c(row, state):
        return row["states"][state]["contrast"]

    scores = {v: {k: stats([c(r[v], k)["ratio"] for r in rounds]) for k in STATES} for v in VERSIONS}
    delta = stats([c(r["v007"], "clean")["ratio"] - c(r["v010"], "clean")["ratio"] for r in rounds])
    stable = all(r[v] == rounds[0][v] for r in rounds for v in VERSIONS)
    parity = all(
        r[v] | {"states": {k: {a: b for a, b in row.items() if a != "contrast"}
                            for k, row in r[v]["states"].items()}} == reference[v]
        for r in rounds for v in VERSIONS
    )
    support = all(
        len({c(r[v], k)["samples"] for k in STATES}) == 1
        and 10 * c(r[v], "clean")["samples"] >= 9 * sum(t["samples"] for t in r[v]["states"]["clean"]["tiles"].values())
        for r in rounds for v in VERSIONS
    )
    witness = all(
        all(r[v]["states"][k]["changed_faces"] == 10 and r[v]["states"][k]["non_target_changed_faces"] == 0
            and c(r[v], k)["rgb_vectors_changed"] > 0 for k in ("+2px", "+5px"))
        and c(r[v], "+5px")["ratio"] > c(r[v], "clean")["ratio"]
        for r in rounds for v in VERSIONS
    )
    threshold = max(0.05, 0.25 * scores["v010"]["clean"]["median"])
    separated = delta["median"] >= threshold
    hypothesis = ("confirmed" if separated else "refuted") if len(rounds) == 3 and stable and parity and support and witness else "inconclusive"
    return {"scores": scores, "paired_clean_delta": delta, "stable": stable, "witness": witness,
            "raw_r67_parity": parity, "support": support, "threshold": threshold,
            "separated": separated, "hypothesis": hypothesis}


def main(out):
    start = time.monotonic()
    out.mkdir(parents=True)
    receipt = {"status": "running", "hypothesis": "inconclusive", "rounds": [], "reference_commit": BASE,
               "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    try:
        receipt["inputs"] = preflight()
        ref = subprocess.check_output(["git", "show", REFERENCE], cwd=ROOT)
        receipt["r67_reference"] = {"blob": REFERENCE, "sha256": hashlib.sha256(ref).hexdigest()}
        reference_round = json.loads(ref)["rounds"][0]
        for i in range(3):
            begin = time.monotonic()
            d = out / f"round{i + 1}"
            d.mkdir()
            cap = min(start + TOTAL, begin + FIRST) if i == 0 else start + TOTAL
            pair = {}
            for v in VERSIONS:
                left = int(cap - time.monotonic())
                if left <= 0:
                    raise TimeoutError("pair budget exhausted")
                pair[v] = one(v, d, timeout=left)
            elapsed = time.monotonic() - begin
            receipt["rounds"].append(pair | {"seconds": round(elapsed, 3)})
            remaining = start + TOTAL - time.monotonic()
            if time.monotonic() > cap or (i == 0 and remaining < 2 * elapsed + 15):
                raise TimeoutError("measured pair does not fit frozen confirmation budget")
        receipt["inputs_match_after"] = preflight() == receipt["inputs"]
        if not receipt["inputs_match_after"]:
            raise ValueError("fixture parity failed")
        receipt.update(summarize([{v: r[v] for v in VERSIONS} for r in receipt["rounds"]], reference_round))
        receipt["status"] = "completed"
    except (ValueError, LookupError, OSError, RuntimeError, subprocess.SubprocessError) as exc:
        expired = time.monotonic() >= start + TOTAL
        receipt["status"] = "budget_stop" if expired or isinstance(exc, (TimeoutError, subprocess.TimeoutExpired)) else "error"
        receipt["error"] = f"{type(exc).__name__}: {exc}"
    receipt["seconds"] = round(time.monotonic() - start, 3)
    (out / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({k: receipt[k] for k in ("status", "hypothesis", "seconds")} | {
        "rounds": len(receipt["rounds"]), "error": receipt.get("error"), "receipt": str(out / "receipt.json")}, ensure_ascii=False))
    return 0 if receipt["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main(Path(sys.argv[1])))
