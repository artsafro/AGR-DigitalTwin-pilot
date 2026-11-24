"""#65 driver: 3 fresh Blender readbacks of AC08 v007/v010 NPM FBX, unchanged twinqa.npm_uv + UDIM fold + U shifts.

uv run --frozen python docs/research/atlas-padding-v006-r65/run65.py tmp/r65-run-NEW
"""
from __future__ import annotations

import hashlib
import json
import math
import statistics
import sys
import time
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path[:0] = [str(HERE), str(ROOT / "src")]

from r65 import TARGET, fold, margin_px, png_size, shift, target_faces, verdict  # noqa: E402
from twinqa.npm_uv import npm_uv_findings  # noqa: E402
from twinqa.scene import readback  # noqa: E402

DRIVE = Path("G:/Мой диск/AGR-evidence")
ZIPS = {"v007": "271ee11bf78200ef883814a4ac108ef289098d0f106da01e8d9fc57da888c295",
        "v010": "2fe983791566477e297aeefa09f04a1b7d176312c3fce1a8c9f1cf26138013bb"}
BLENDER = Path("C:/Program Files/Blender Foundation/Blender 5.1/blender.exe")
BLENDER_SHA = "1e6624af112b3c936f4b038b025ebd2bf00ae72c4b62881a6787166d71c58fa5"
TOTAL, FIRST, ROUNDS = 480, 120, 3
CODE = ["src/twinqa/npm_uv.py", "tools/blender/fbx_readback.py", "src/twinqa/scene.py"]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inputs():
    out = {}
    for v in ZIPS:
        d = DRIVE / f"559-tec26-oks-ac08-pilot-{v}"
        out[str(d / "SM_Nku_1.zip")] = sha(d / "SM_Nku_1.zip")
        out[str(d / "npm_atlas.json")] = sha(d / "npm_atlas.json")
    out[str(BLENDER)] = sha(BLENDER)
    return out


def one(v, work):
    d = DRIVE / f"559-tec26-oks-ac08-pilot-{v}"
    atlas = json.loads((d / "npm_atlas.json").read_text(encoding="utf-8"))
    with zipfile.ZipFile(d / "SM_Nku_1.zip") as z:
        fbx = work / f"{v}_SM_Nku_1.fbx"
        fbx.write_bytes(z.read("SM_Nku_1.fbx"))
        tile_px = {int(n.rsplit(".", 2)[1]): png_size(z.read(n)) for n in z.namelist()
                   if "_Diffuse_" in n and n.endswith(".png")}
    rb = readback(fbx, blender=str(BLENDER))
    u = npm_uv_findings(rb, atlas, fbx.name)
    meshes = [m for m in rb.get("meshes") or [] if not str(m.get("name", "")).upper().startswith("UCX_")
              and not str(m.get("name", "")).endswith(("MainGlass", "GroundGlass", "GroundElGlass"))]
    rec = {"U": [{"status": x.status, "observed": x.observed[:300], "bad_faces": (x.data or {}).get("bad_faces")}
                 for x in u],
           "images": rb.get("images"), "meshes": [m.get("name") for m in meshes], "tile_px": tile_px}
    try:
        f = fold(meshes, atlas, tile_px)
    except ValueError as exc:  # R0: frozen precondition failed -> F not measured (run inconclusive)
        rec["F"] = {"not_measured": str(exc)}
        return rec
    rec["F"] = {"faces": f["faces"], "B65": len(f["bad"]), "errors": f["errors"][:5], "tiles": f["tiles"],
                "bad": f["bad"][:10]}
    if v == "v010":
        hits = target_faces(meshes, atlas)
        if not hits:
            raise ValueError("not_exercised: no TARGET faces")
        raw = margin_px(meshes, atlas, hits)
        m = math.ceil(raw)
        pad = atlas["pad"]
        sens = {}
        for s in (1, 5, m + 1, m + pad + 1):
            g = fold(shift(meshes, hits, s, atlas["atlas"]), atlas, tile_px)
            reasons = sorted({b["reason"] for b in g["bad"]})
            sens[s] = {"B65": len(g["bad"]), "reasons": reasons, "changed_faces": len(hits),
                       "expected_bad": s > raw + 0.02}   # UV_TOL 1e-5 * 2048 ~ 0.02 px
        rec |= {"margin_m_px": m, "margin_raw_px": raw, "target_faces": len(hits),
                "sens": sens}
    return rec


def main(out):
    out = Path(out)
    out.mkdir(parents=True)
    start = time.monotonic()
    rep = {"status": "running", "hypothesis": "inconclusive", "rounds": [],
           "code": {c: sha(ROOT / c) for c in CODE} | {p.name: sha(p) for p in (HERE / "r65.py", HERE / "run65.py")}}
    try:
        before = inputs()
        rep["inputs"] = before
        if before[str(BLENDER)] != BLENDER_SHA or any(
                before[str(DRIVE / f"559-tec26-oks-ac08-pilot-{v}" / "SM_Nku_1.zip")] != h for v, h in ZIPS.items()):
            raise ValueError("input hash preflight failed")
        for r in range(ROUNDS):
            t0 = time.monotonic()
            work = out / f"round{r + 1}"
            work.mkdir()
            rnd = {v: one(v, work) for v in ZIPS}
            rnd["seconds"] = round(time.monotonic() - t0, 3)
            rep["rounds"].append(rnd)
            (out / "receipt.json").write_text(json.dumps(rep, indent=1, default=str), encoding="utf-8")
            used = time.monotonic() - start
            if r == 0 and (rnd["seconds"] > FIRST or TOTAL - used < 2 * rnd["seconds"] + 15):
                rep["status"] = "budget_stop"
                break
        rep["inputs_match_after"] = inputs() == before
        if rep["status"] != "budget_stop":
            rep["status"] = "completed"
            key = lambda rnd: json.dumps({v: {k: rnd[v][k] for k in rnd[v] if k != "images"} for v in ZIPS},
                                         sort_keys=True, default=str)
            rep["stable"] = len({key(x) for x in rep["rounds"]}) == 1
            last = rep["rounds"][-1]
            rep["U_fail_all"] = all(u["status"] == "fail" and u["bad_faces"] is None for x in rep["rounds"]
                                    for v in ZIPS for u in x[v]["U"])
            if any("not_measured" in last[v]["F"] for v in ZIPS):
                rep["hypothesis"] = "inconclusive"
                rep["F_not_measured"] = {v: last[v]["F"].get("not_measured") for v in ZIPS}
                raise StopIteration
            b = {v: statistics.median(x[v]["F"]["B65"] for x in rep["rounds"]) for v in ZIPS}
            applicable = all(all(u["bad_faces"] is not None for u in last[v]["U"]) for v in ZIPS)
            sens = {s: (x["B65"], x["expected_bad"]) for s, x in last["v010"]["sens"].items()}
            witness = last["v010"]["sens"][last["v010"]["margin_m_px"] + 1]["B65"] > 0
            rep["B65_median"] = b
            rep["applicable_U"] = applicable
            rep["witness_fired"] = witness
            ok = rep["stable"] and rep["inputs_match_after"] and witness
            rep["hypothesis"] = verdict(applicable, b["v007"], b["v010"], sens) if ok else "inconclusive"
    except StopIteration:
        pass
    except Exception as exc:  # noqa: BLE001 - recorded, run is inconclusive
        rep["status"] = f"error: {type(exc).__name__}: {exc}"
    rep["seconds"] = round(time.monotonic() - start, 3)
    (out / "receipt.json").write_text(json.dumps(rep, indent=1, default=str), encoding="utf-8")
    print(json.dumps({k: rep.get(k) for k in ("status", "hypothesis", "B65_median", "applicable_U",
                                              "witness_fired", "stable", "seconds")}, default=str))


if __name__ == "__main__":
    main(sys.argv[1])
