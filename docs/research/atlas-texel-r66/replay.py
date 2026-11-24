"""Replay the frozen #66 AC08 diagnostic; no writes to delivered packages."""
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
from collections import Counter
from pathlib import Path

from PIL import Image
from twinqa.scene import readback
from twinqa.sintez_uv import DEGENERATE_DENSITY, _polygons, polygon_density

ROOT = Path(__file__).resolve().parents[3]
BASE = "e2d480997b452f03af3f37d54f6b5cc2122bcd06"
DRIVE = Path("G:/Мой диск/AGR-evidence")
BLENDER = Path("C:/Program Files/Blender Foundation/Blender 5.1/blender.exe")
PINS = {BLENDER: "1e6624af112b3c936f4b038b025ebd2bf00ae72c4b62881a6787166d71c58fa5"}
VERSIONS = {
    "v007": ({1001}, "271ee11bf78200ef883814a4ac108ef289098d0f106da01e8d9fc57da888c295",
             "9feb8685a71dec4cd2bb746bd3695bccdce3e648199dc0f32cb3738f6c430ea2"),
    "v010": ({1001, 1002}, "2fe983791566477e297aeefa09f04a1b7d176312c3fce1a8c9f1cf26138013bb",
             "338edcd767c0c6c99f762d4b7a9dcfd9407da030086ccb5b96e551d3bffae0cc"),
}
STATES = {"clean": 1, "0.75": 0.75, "0.50": 0.5}
FIRST, TOTAL = 60, 240


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


def measure(rb, sides, targets):
    """Only target corners enter the contraction; original arrays stay untouched."""
    if not rb.get("meshes"):
        raise ValueError("no meshes in native readback")
    before = json.dumps(rb, sort_keys=True)
    densities = {state: {t: [] for t in targets} for state in STATES}
    face_counts = {state: Counter() for state in STATES}
    loop_counts = {state: Counter() for state in STATES}
    excluded = Counter()
    for mesh in rb["meshes"]:
        name = mesh["name"]
        if name.upper().startswith("UCX_") or name.endswith(("MainGlass", "GroundGlass", "GroundElGlass")):
            continue
        for index, xyz, uv, _material in _polygons(mesh):
            center = tuple(statistics.fmean(axis) for axis in zip(*uv, strict=True))
            u, v = map(math.floor, center)
            tile = 1001 + u + 10 * v
            if not (0 <= u < 10 and 0 <= v < 10 and tile in sides):
                raise ValueError(f"{name}[{index}]: no bound Diffuse for centroid {center}")
            if tile not in targets:
                excluded[tile] += 1
                continue
            for state, factor in STATES.items():
                corners = uv if factor == 1 else [
                    [c + factor * (x - c) for x, c in zip(point, center, strict=True)] for point in uv
                ]
                if not all(u <= x <= u + 1 and v <= y <= v + 1 for x, y in corners):
                    raise ValueError(f"{name}[{index}] crosses tile {tile} ({state})")
                changed = sum(tuple(a) != tuple(b) for a, b in zip(uv, corners, strict=True))
                face_counts[state][tile] += bool(changed)
                loop_counts[state][tile] += changed
                rho = polygon_density(xyz, corners, sides[tile])
                if not math.isfinite(rho) or rho <= DEGENERATE_DENSITY:
                    raise ValueError(f"{name}[{index}] degenerate density ({state})")
                densities[state][tile].append(rho)
    if json.dumps(rb, sort_keys=True) != before:
        raise ValueError("original readback changed")
    states = {}
    for state, factor in STATES.items():
        rows = {}
        for tile, samples in sorted(densities[state].items()):
            changed = face_counts[state][tile]
            if not samples or changed != (len(samples) if factor != 1 else 0):
                raise ValueError(f"not_exercised: tile {tile}, state {state}")
            med = statistics.median(samples)
            ratio = med / statistics.median(densities["clean"][tile])
            if abs(ratio - factor) > 1e-8:
                raise ValueError(f"unexpected density ratio: {tile}/{state}: {ratio}")
            rows[tile] = {"faces": len(samples), "median": med, "min": min(samples), "max": max(samples),
                          "changed_faces": changed, "changed_loops": loop_counts[state][tile], "ratio": ratio}
        states[state] = {"tiles": rows, "score": max(abs(r["median"] / 1000 - 1) for r in rows.values())}
    return {"states": states, "excluded_faces": dict(excluded), "non_target_changed_faces": 0}


def one(v, out, timeout):
    archive, plan_path = fixture(v)
    target = VERSIONS[v][0]
    plan = json.loads(plan_path.read_text(encoding="utf-8"))["finishes"]
    expected = {d["udim"]: 256 if d["px_per_m"] is None else 4096 for d in plan.values()}
    if target != {t for t, side in expected.items() if side == 4096} or len(expected) != len(plan):
        raise ValueError(f"{v}: planning finish bindings mismatch")
    fbx = out / f"{v}_SM_Nku_1.fbx"
    with zipfile.ZipFile(archive) as z:
        fbx.write_bytes(z.read("SM_Nku_1.fbx"))
        sides = {}
        for name in z.namelist():
            if "_Diffuse_" in name and name.endswith(".png"):
                t = int(name.rsplit(".", 2)[1])
                with Image.open(io.BytesIO(z.read(name))) as im:
                    im.load()
                    w, h = im.size
                    if w != h or im.format != "PNG" or t in sides:
                        raise ValueError(f"{v}: unexpected image: {name}")
                    sides[t] = w
    if sides != expected:
        raise ValueError(f"{v}: actual Diffuse tile sizes {sides} != {expected}")
    rb = readback(fbx, blender=str(BLENDER), timeout=timeout)
    return measure(rb, sides, target) | {"tile_px": sides, "fbx_sha256": hashlib.sha256(fbx.read_bytes()).hexdigest()}


def summarize(rounds):
    def stats(values):
        return {"median": statistics.median(values), "spread": max(values) - min(values)}

    scores = {v: {k: stats([r[v]["states"][k]["score"] for r in rounds]) for k in STATES} for v in VERSIONS}
    delta = stats([r["v007"]["states"]["clean"]["score"] - r["v010"]["states"]["clean"]["score"] for r in rounds])
    stable = all(r[v] == rounds[0][v] for r in rounds for v in VERSIONS)
    calibrated = scores["v010"]["clean"]["median"] <= 0.02 and delta["median"] >= 0.02
    hypothesis = ("confirmed" if calibrated else "refuted") if len(rounds) == 3 and stable else "inconclusive"
    return {"scores": scores, "paired_clean_delta": delta, "stable": stable, "hypothesis": hypothesis}


def main(out):
    start = time.monotonic()
    out.mkdir(parents=True)
    receipt = {"status": "running", "hypothesis": "inconclusive", "rounds": [], "reference_commit": BASE,
               "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    try:
        receipt["inputs"] = preflight()
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
        receipt.update(summarize(receipt["rounds"]))
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
