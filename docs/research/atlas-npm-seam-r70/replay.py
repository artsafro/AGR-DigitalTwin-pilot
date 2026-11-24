"""Standing #70: run the pinned #68 seam metric in exported NPM atlas cells."""
from __future__ import annotations

import copy
import hashlib
import io
import json
import math
import statistics
import subprocess
import sys
import time
import zipfile
from functools import cache
from pathlib import Path

import numpy as np
from PIL import Image

from twinqa.fbx_header import _iter_nodes, _parse_props, fbx_header
from twinqa.scene import readback
from twinqa.sintez_uv import _polygons

ROOT = Path(__file__).resolve().parents[3]
BASE = "4288c54de328db7a5037b57707862319f7aa6ff0"
UPSTREAM = "a86319003a684b4eccabc7eb524d4e70b829b853:docs/research/atlas-seam-r68/replay.py"
MEMBER = "0000_Nku_1_01.fbx"
ATLAS = "T_Nku_1_001_Main_d_1.png"
DRIVE = Path("G:/Мой диск/AGR-evidence")
BLENDER = Path("C:/Program Files/Blender Foundation/Blender 5.1/blender.exe")
PINS = {
    "v007": (["0d1fa6c036bb553459dd0e9baec8be4ace8bc61d5acea6aab585d713f2292d0f",
              "772a2768ca396a4c6b404357ad30a676de4bf6928be053db1d956fb3b675a516",
              "9feb8685a71dec4cd2bb746bd3695bccdce3e648199dc0f32cb3738f6c430ea2"],
             "456132ee2167f507415cc971b3ddc2093c9cd74441432252027e5b26bb0af932", {1001}),
    "v010": (["8f0cb8b7e922850eab15198d0bd40cf2ca1e2bfed12e9c4912173b4aef565ab3",
              "88e0392ea057013e4eb33e9240a3856a1728fb8380433cab9662f73052473278",
              "338edcd767c0c6c99f762d4b7a9dcfd9407da030086ccb5b96e551d3bffae0cc"],
             "7eb0544231e5148a60a9a8760f2ccc16828130b002691d205a30e5e233597a52", {1001, 1002}),
}


@cache
def upstream():
    raw = subprocess.check_output(["git", "show", UPSTREAM], cwd=ROOT)
    ns = {"__name__": "r68_frozen", "__file__": __file__}
    exec(compile(raw, UPSTREAM, "exec"), ns)
    return ns


def adapt_atlas(rb, atlas, plan):
    """Represent each physical padded cell as an integer UDIM-offset square, without resampling."""
    side, cell, pad, region = (plan[k] for k in ("atlas", "cell", "pad", "region"))
    if atlas.shape != (side, side, 3) or cell != region + 2 * pad or not 0 < region <= cell <= side:
        raise ValueError("invalid atlas extent")
    tiles, inner, census = {}, {}, {}
    for entry in plan["finishes"].values():
        t = entry["udim"]
        x, y = entry["u0"] * side, entry["v0"] * side
        if not (1001 <= t <= 1100 and t not in tiles and entry["size"] * side == region
                and x.is_integer() and y.is_integer()):
            raise ValueError(f"invalid cell {entry}")
        x, y = int(x), int(y)
        lo, bottom = x - pad, y - pad
        if min(lo, bottom) < 0 or max(lo, bottom) + cell > side:
            raise ValueError(f"cell {t} outside atlas")
        inner[t] = (x, y)
        tiles[t] = atlas[side - bottom - cell:side - bottom, lo:lo + cell]
        census[t] = 0
    result = copy.deepcopy(rb)
    for mesh in result["meshes"]:
        if mesh["name"].endswith("MainGlass"):
            continue
        if not mesh["name"].endswith("Main"):
            raise ValueError(f"unexpected NPM mesh {mesh['name']}")
        for i, _, uv, _ in _polygons(mesh):
            pixel = np.asarray(uv) * side
            matches = [t for t, xy in inner.items()
                       if ((pixel >= np.asarray(xy) - 0.01) & (pixel <= np.asarray(xy) + region + 0.01)).all()]
            if len(matches) != 1:
                raise ValueError(f"{mesh['name']}[{i}]: not in a unique finish")
            t, = matches
            origin = np.asarray(inner[t]) - pad
            offset = np.array([(t - 1001) % 10, (t - 1001) // 10])
            mesh["face_geometry"]["polygon_uv"][i] = ((pixel - origin) / cell + offset).tolist()
            census[t] += 1
    return result, tiles, census


def same_embedded_atlas(fbx, atlas):
    fmt, version = fbx_header(fbx)
    if fmt != "binary" or version is None:
        raise ValueError(f"unsupported FBX format: {fmt}")

    def children(node):
        return _iter_nodes(fbx, node["props_end"], node["end_offset"], version)

    def props(node):
        return _parse_props(fbx, node["props_at"], node["props_end"], node["num_props"])

    matches = []
    for container in _iter_nodes(fbx, 27, len(fbx), version):
        if container["name"] != "Objects":
            continue
        for video in children(container):
            if video["name"] != "Video":
                continue
            fields = {n["name"]: props(n) for n in children(video)
                      if n["name"] in {"RelativeFilename", "FileName", "Content"}}
            names = [v.replace("\\", "/").split("/")[-1] for field in ("RelativeFilename", "FileName")
                     for code, v in fields.get(field, []) if code == "S"]
            if ATLAS in names:
                matches.append([v.encode("latin-1") for code, v in fields.get("Content", []) if code == "R"])
    if matches != [[atlas]]:
        raise ValueError("Diffusion atlas lacks a unique byte-identical embedded Video")


def paths(v):
    folder = DRIVE / f"559-tec26-oks-ac08-pilot-{v}"
    return [folder / f for f in ("0000_Nku_1.zip", ATLAS, "npm_atlas.json")]


def digest_file(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def preflight():
    subprocess.run(["git", "diff", "--quiet", BASE, "--", "src", "tools", "standards", "adapters",
                    "uv.lock", "pyproject.toml", "jobs"], cwd=ROOT, check=True)
    pins = upstream()["PINS"] | {p: digest for v, (digests, _, _) in PINS.items()
                                 for p, digest in zip(paths(v), digests, strict=True)}
    for path, digest in pins.items():
        if digest_file(path) != digest:
            raise ValueError(f"hash mismatch: {path}")
    return {str(p): h for p, h in pins.items()}


def one(v, out, timeout):
    archive, diffuse, manifest = paths(v)
    _, expected, targets = PINS[v]
    plan = json.loads(manifest.read_bytes())
    if {e["udim"] for e in plan["finishes"].values() if e["px_per_m"] is not None} != targets:
        raise ValueError(f"{v}: finish plan differs from declared scope")
    with zipfile.ZipFile(archive) as z:
        fbx = z.read(MEMBER)
    if hashlib.sha256(fbx).hexdigest() != expected:
        raise ValueError(f"{v}: readback FBX identity differs from #69")
    atlas_bytes = diffuse.read_bytes()
    same_embedded_atlas(fbx, atlas_bytes)
    with Image.open(io.BytesIO(atlas_bytes)) as image:
        if image.size != (2048, 2048) or image.format != "PNG" or image.mode != "RGB":
            raise ValueError(f"{v}: unexpected atlas raster")
        atlas = np.asarray(image)
    out.mkdir()
    local = out / MEMBER
    local.write_bytes(fbx)
    rb = readback(local, blender=str(BLENDER), timeout=timeout)
    adapted, rasters, counts = adapt_atlas(rb, atlas, plan)
    score = upstream()["measure"]

    def grade(scope):
        try:
            result = score(adapted, rasters, scope)
        except ValueError as exc:
            if str(exc) != "not_exercised: no seam samples on target tiles":
                raise
            return {"status": "not_exercised", "reason": str(exc)}
        return result | {"status": result["states"]["clean"]["contrast"]["status"]}

    return {"fbx_sha256": expected, "atlas_embedded_byte_parity": True, "fbx_units": rb.get("fbx_units"),
            "cell_faces": counts, "score": grade(targets),
            "per_finish": {t: grade({t}) for t in sorted(targets)}}


def summarize(rounds):
    clean, controls = {}, {}
    for v in PINS:
        clean[v] = []
        controls[v] = []
        for pair in rounds:
            item = pair.get(v, {}).get("score", {})
            if item.get("status") != "measured":
                continue
            states = item["states"]
            baseline = states["clean"]["contrast"]
            clean[v].append(baseline["ratio"])
            controls[v].append(
                all(s["contrast"]["status"] == "measured" and s["contrast"]["samples"] == baseline["samples"]
                    and s["contrast"]["rgb_vectors_changed"] > 0 and s["changed_faces"] > 0
                    and s["non_target_changed_faces"] == 0 and math.isfinite(s["contrast"]["ratio"])
                    and s["contrast"]["ratio"] >= 0 for s in (states["+2px"], states["+5px"]))
                and states["+5px"]["contrast"]["ratio"] > baseline["ratio"]
            )
    deltas = [p["v007"]["score"]["states"]["clean"]["contrast"]["ratio"]
              - p["v010"]["score"]["states"]["clean"]["contrast"]["ratio"] for p in rounds
              if all(p.get(v, {}).get("score", {}).get("status") == "measured" for v in PINS)]
    med = statistics.median(deltas) if deltas else None
    bound = max(0.05, 0.25 * statistics.median(clean["v010"])) if clean["v010"] else None
    spread = max(deltas) - min(deltas) if deltas else None
    ready = len(deltas) == 3 and spread == 0 and all(all(rows) for rows in controls.values())
    verdict = ("confirmed" if med >= bound else "refuted") if ready else "inconclusive"
    return {"hypothesis": verdict, "clean": clean, "controls_pass": controls, "paired_median": med,
            "paired_spread": spread, "bound": bound}


def main(out):
    out = out.resolve()
    out.mkdir(parents=True)
    pins = preflight()
    start = time.perf_counter()
    rounds, walls, status, error = [], [], "completed", None
    try:
        for n in range(1, 4):
            pair = {}
            rounds.append(pair)
            pair_start = time.perf_counter()
            for v in PINS:
                remaining = (60 if n == 1 else 240) - (time.perf_counter() - start)
                if remaining < 1:
                    raise TimeoutError("measurement deadline reached")
                pair[v] = one(v, out / f"r{n}-{v}", int(remaining))
            walls.append(time.perf_counter() - pair_start)
            elapsed = time.perf_counter() - start
            if elapsed > 240 or (n == 1 and (elapsed > 60 or elapsed + 2 * walls[0] + 15 > 240)):
                status = "budget_stop"
                break
            if any(row["score"]["status"] != "measured" for row in pair.values()):
                status = "not_exercised"
                break
    except TimeoutError as exc:
        status, error = "budget_stop", str(exc)
    except Exception as exc:
        status, error = "readback_error", f"{type(exc).__name__}: {exc}"
    wall = time.perf_counter() - start
    assert preflight() == pins
    row = summarize(rounds)
    if status != "completed":
        row["hypothesis"] = "inconclusive"
    receipt = row | {"status": status, "error": error, "seconds": wall, "pair_seconds": walls, "rounds": rounds,
                     "pins": pins, "base": BASE, "evaluator": UPSTREAM, "candidate_sha256": digest_file(Path(__file__))}
    (out / "receipt.json").write_bytes((json.dumps(receipt, indent=2, ensure_ascii=False) + "\n").encode())
    print(json.dumps(row | {"status": status, "seconds": wall, "pair_seconds": walls, "error": error}))
    return int(status not in {"completed", "not_exercised"})


if __name__ == "__main__":
    raise SystemExit(main(Path(sys.argv[1])))
