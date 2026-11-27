"""#137 OBSERVE harness: Sokolniki NPM window/CW atlas vs Revit same-camera render-diff (M_edge, M_de).

Usage: uv run --frozen python docs/research/autoresearch-npm-revit-window-diff-harness/run.py OUT_DIR [--pin]
--pin only writes pins.json (input SHA-256) and exits; a normal run refuses on any hash mismatch.
Contract: docs/research/autoresearch-npm-revit-window-diff.md. Evidence only; never writes to Drive inputs.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
EV = Path("G:/Мой диск/AGR-evidence/1784-sokolniki-lattice/step4-uv-atlas-v001")
BLENDER = Path("C:/Program Files/Blender Foundation/Blender 5.1/blender.exe")
SHIFT = "26.148,61.907"
WIN = ["W1", "W2", "W3", "W4", "D1"]
CW = ["CF", "CW4", "CWL", "CWS"]
VIEWS = ["f", "q"]
CAP = 10
EDGE_T = 0.05
MARGIN = 0.25

INPUTS = {
    "qwin_npm.py": EV / "question-windows/scripts/qwin_npm.py",
    "measure.json": EV / "question-windows/measure.json",
    "cams.json": EV / "curtain-walls-v001/scripts/cams.json",
    "fbx_R1_step4": EV / "npm/NPM_Sokolniki_UVK1000_01.fbx",
    "fbx_A_windows": EV / "windows-texture-v001/npm/NPM_Sokolniki_UVK1000_01.fbx",
    "fbx_CWafter": EV / "curtain-walls-v001/npm/NPM_Sokolniki_UVK1000_01.fbx",
}
for e in WIN:
    for v in VIEWS:
        c = f"{e}_{v}"
        INPUTS[f"revit_{c}"] = EV / f"question-windows/renders/revit_{c}.png"
        INPUTS[f"v009_{c}"] = EV / f"question-windows/renders/v009_{c}.png"
        INPUTS[f"arch_R1_{c}"] = EV / f"question-windows/renders/npm_{c}.png"
        INPUTS[f"arch_A_{c}"] = EV / f"windows-texture-v001/renders/npm_{c}.png"
for e in CW:
    for v in VIEWS:
        c = f"{e}_{v}"
        for k in ("revit", "before", "after"):
            INPUTS[f"cw_{k}_{c}"] = EV / f"curtain-walls-v001/close/{k}/npm_{c}.png"


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def load(p: Path) -> np.ndarray:
    return np.asarray(Image.open(p).convert("RGBA")).astype(np.float64)


def luma(a: np.ndarray) -> np.ndarray:
    rgb = a[..., :3] / 255.0
    return rgb @ np.array([0.2126, 0.7152, 0.0722])


def sobel_edges(y: np.ndarray) -> np.ndarray:
    p = np.pad(y, 1, mode="edge")
    gx = (p[:-2, 2:] + 2 * p[1:-1, 2:] + p[2:, 2:]) - (p[:-2, :-2] + 2 * p[1:-1, :-2] + p[2:, :-2])
    gy = (p[2:, :-2] + 2 * p[2:, 1:-1] + p[2:, 2:]) - (p[:-2, :-2] + 2 * p[:-2, 1:-1] + p[:-2, 2:])
    return np.hypot(gx, gy) / 4.0 > EDGE_T


_OFFS = sorted(((dx, dy) for dx in range(-CAP, CAP + 1) for dy in range(-CAP, CAP + 1)
                if 0 < dx * dx + dy * dy <= CAP * CAP), key=lambda o: o[0] ** 2 + o[1] ** 2)


def dist_capped(edge: np.ndarray) -> np.ndarray:
    """Euclidean distance to the nearest True pixel, capped at CAP (no wrap)."""
    h, w = edge.shape
    d = np.where(edge, 0.0, float(CAP))
    pad = np.pad(edge, CAP)
    for dx, dy in _OFFS:
        r = (dx * dx + dy * dy) ** 0.5
        sh = pad[CAP + dy:CAP + dy + h, CAP + dx:CAP + dx + w]
        d = np.where(sh & (d > r), r, d)
    return d


def erode1(m: np.ndarray) -> np.ndarray:
    p = np.pad(m, 1, constant_values=False)
    out = m.copy()
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            out &= p[1 + dy:1 + dy + m.shape[0], 1 + dx:1 + dx + m.shape[1]]
    return out


def lab(a: np.ndarray) -> np.ndarray:
    c = a[..., :3] / 255.0
    c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    m = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
    xyz = c @ m.T / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 216 / 24389, np.cbrt(xyz), (24389 / 27 * xyz + 16) / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1)


def cell_mask(shape, cam: dict | None, typ: dict | None) -> np.ndarray:
    h, w = shape
    m = np.zeros((h, w), bool)
    if cam is None or typ is None:
        m[:] = True
        return m
    d = np.array(cam["dir"], float)
    d /= np.linalg.norm(d)
    right = np.cross(d, [0.0, 0.0, 1.0])
    right /= np.linalg.norm(right)
    up = np.cross(right, d)
    ppm = w / cam["scale"]
    c = np.array(typ["center"], float)
    t, n, hf = np.array(typ["t"], float), np.array(typ["nout"], float), typ["half"]
    xs, ys = [], []
    for sx in (-1, 1):
        for sy in (-1, 1):
            for sz in (-1, 1):
                p = c + sx * hf[0] * t + sy * hf[1] * n + sz * hf[2] * np.array([0.0, 0.0, 1.0])
                q = p - np.array(cam["target"], float)
                xs.append(w / 2 + q @ right * ppm)
                ys.append(h / 2 - q @ up * ppm)
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    mx, my = 0.1 * (x1 - x0), 0.1 * (y1 - y0)
    x0, x1 = int(max(0, np.floor(x0 - mx))), int(min(w, np.ceil(x1 + mx)))
    y0, y1 = int(max(0, np.floor(y0 - my))), int(min(h, np.ceil(y1 + my)))
    m[y0:y1, x0:x1] = True
    return m


def score(ref: np.ndarray, cand: np.ndarray, cell: np.ndarray) -> dict:
    mask = cell & erode1(cand[..., 3] >= 255) & erode1(ref[..., 3] >= 255)
    er, ec = sobel_edges(luma(ref)) & mask, sobel_edges(luma(cand)) & mask
    dr, dc = dist_capped(ec), dist_capped(er)
    a = float(dr[er].mean()) if er.any() else float(CAP)
    b = float(dc[ec].mean()) if ec.any() else float(CAP)
    de = float(np.linalg.norm(lab(ref) - lab(cand), axis=-1)[mask].mean()) if mask.any() else None
    return {"m_edge": round((a + b) / 2, 4), "ref_to_cand": round(a, 4), "cand_to_ref": round(b, 4),
            "m_de": None if de is None else round(de, 4), "mask_px": int(mask.sum()),
            "ref_edges": int(er.sum()), "cand_edges": int(ec.sum())}


def parity(fresh: Path, arch: Path) -> dict:
    a, b = load(fresh), load(arch)
    both = (a[..., 3] >= 255) & (b[..., 3] >= 255)
    d = np.abs(a[..., :3] - b[..., :3]).max(-1)
    return {"opaque_both": int(both.sum()), "rgb_gt8": int((d[both] > 8).sum()),
            "alpha_mismatch": int((a[..., 3] != b[..., 3]).sum())}


def render(fbx: Path, cams: Path, out: Path) -> float:
    out.mkdir(parents=True, exist_ok=True)
    t = time.perf_counter()
    r = subprocess.run([str(BLENDER), "-b", "--factory-startup", "--python", str(INPUTS["qwin_npm.py"]), "--",
                        str(fbx), str(cams), str(out), SHIFT], capture_output=True, text=True, errors="replace")
    if r.returncode != 0 or "DONE npm" not in r.stdout:
        raise SystemExit(f"render failed {fbx}: {r.stdout[-800:]} {r.stderr[-800:]}")
    return round(time.perf_counter() - t, 2)


def main() -> None:
    out = Path(sys.argv[1]).resolve()
    pins_path = HERE / "pins.json"
    hashes = {k: sha(p) for k, p in INPUTS.items()}
    if "--pin" in sys.argv:
        pins_path.write_text(json.dumps(hashes, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        print("pinned", len(hashes))
        return
    pins = json.loads(pins_path.read_text(encoding="utf-8"))
    bad = sorted(k for k in pins if pins[k] != hashes.get(k))
    if bad or set(pins) != set(hashes):
        raise SystemExit(f"preflight: hash mismatch {bad}")
    meas = json.loads(INPUTS["measure.json"].read_text(encoding="utf-8"))
    cams = {c["id"]: c for c in meas["cams"]}
    types = {t["id"]: t for t in meas["types"]}
    t0 = time.perf_counter()
    rounds, wall = [], {}
    for r in (1, 2, 3):
        rd = out / f"r{r}"
        wall[f"r{r}"] = {
            "A": render(INPUTS["fbx_A_windows"], INPUTS["measure.json"], rd / "A"),
            "R1": render(INPUTS["fbx_R1_step4"], INPUTS["measure.json"], rd / "R1"),
            "CWbefore": render(INPUTS["fbx_A_windows"], INPUTS["cams.json"], rd / "CWbefore"),
            "CWafter": render(INPUTS["fbx_CWafter"], INPUTS["cams.json"], rd / "CWafter"),
        }
        win, cw = {}, {}
        for e in WIN:
            for v in VIEWS:
                c = f"{e}_{v}"
                ref = load(INPUTS[f"revit_{c}"])
                cell = cell_mask(ref.shape[:2], cams[c], types[e])
                win[c] = {
                    "A": score(ref, load(rd / "A" / f"npm_{c}.png"), cell),
                    "R1": score(ref, load(rd / "R1" / f"npm_{c}.png"), cell),
                    "R2_frozen": score(ref, load(INPUTS[f"v009_{c}"]), cell),
                    "cell_px": int(cell.sum()),
                    "parity_A": parity(rd / "A" / f"npm_{c}.png", INPUTS[f"arch_A_{c}"]),
                    "parity_R1": parity(rd / "R1" / f"npm_{c}.png", INPUTS[f"arch_R1_{c}"]),
                }
        for e in CW:
            for v in VIEWS:
                c = f"{e}_{v}"
                ref = load(INPUTS[f"cw_revit_{c}"])
                cell = cell_mask(ref.shape[:2], None, None)
                cw[c] = {
                    "after": score(ref, load(rd / "CWafter" / f"npm_{c}.png"), cell),
                    "before": score(ref, load(rd / "CWbefore" / f"npm_{c}.png"), cell),
                    "parity_after": parity(rd / "CWafter" / f"npm_{c}.png", INPUTS[f"cw_after_{c}"]),
                    "parity_before": parity(rd / "CWbefore" / f"npm_{c}.png", INPUTS[f"cw_before_{c}"]),
                }
        rounds.append({"windows": win, "cw": cw})

    def verdicts(rnd: dict) -> dict:
        w = rnd["windows"]
        ok1 = [c for c in w if w[c]["R1"]["m_edge"] - w[c]["A"]["m_edge"] >= MARGIN]
        ok2 = [c for c in w if w[c]["R2_frozen"]["m_edge"] - w[c]["A"]["m_edge"] >= MARGIN]
        cw = rnd["cw"]
        okc = [c for c in cw if cw[c]["before"]["m_edge"] - cw[c]["after"]["m_edge"] >= MARGIN]
        de1 = [c for c in w if w[c]["R1"]["m_de"] > w[c]["A"]["m_de"]]
        de2 = [c for c in w if w[c]["R2_frozen"]["m_de"] > w[c]["A"]["m_de"]]
        dec = [c for c in cw if cw[c]["before"]["m_de"] > cw[c]["after"]["m_de"]]
        return {"A_lt_R1": len(ok1), "A_lt_R2": len(ok2), "cw_after_lt_before": len(okc), "n_win": len(w),
                "n_cw": len(cw), "fail_R1": sorted(set(w) - set(ok1)), "fail_R2": sorted(set(w) - set(ok2)),
                "fail_cw": sorted(set(cw) - set(okc)),
                "m_de_ordered": {"A_lt_R1": len(de1), "A_lt_R2": len(de2), "cw": len(dec)}}

    vs = [verdicts(r) for r in rounds]
    spread = {}
    for c in rounds[0]["windows"]:
        for k in ("A", "R1"):
            vals = [r["windows"][c][k]["m_edge"] for r in rounds]
            spread[f"{c}/{k}"] = round(max(vals) - min(vals), 4)
    for c in rounds[0]["cw"]:
        for k in ("after", "before"):
            vals = [r["cw"][c][k]["m_edge"] for r in rounds]
            spread[f"{c}/{k}"] = round(max(vals) - min(vals), 4)
    h137 = "confirmed" if all(v["A_lt_R1"] == v["n_win"] and v["A_lt_R2"] == v["n_win"] for v in vs) else "refuted"
    cwmin = min(v["cw_after_lt_before"] for v in vs)
    h137b = "confirmed" if cwmin == 8 else ("inconclusive" if cwmin >= 6 else "refuted")

    # witnesses on round-1 fresh A, W1_f
    ref = load(INPUTS["revit_W1_f"])
    cell = cell_mask(ref.shape[:2], cams["W1_f"], types["W1"])
    a = load(out / "r1/A/npm_W1_f.png")
    wit = {"N0_revit_self": score(ref, ref, cell)["m_edge"], "A": score(ref, a, cell)}
    blur = a.copy()
    ys, xs = np.where(cell)
    sl = (slice(ys.min(), ys.max() + 1), slice(xs.min(), xs.max() + 1))
    for _ in range(6):
        p = np.pad(blur[sl][..., :3], ((2, 2), (2, 2), (0, 0)), mode="edge")
        acc = sum(p[dy:dy + blur[sl].shape[0], dx:dx + blur[sl].shape[1]] for dy in range(5) for dx in range(5))
        blur[sl + (slice(0, 3),)] = acc / 25.0
    wit["P1_pattern_erased"] = score(ref, blur, cell)
    for s in (2, 5, 10):
        wit[f"P2_shift_{s}px"] = score(ref, np.roll(a, s, axis=1), cell)
    dim = a.copy()
    dim[..., :3] *= 0.8
    wit["P3_brightness_0.8"] = score(ref, dim, cell)

    receipt = {
        "card": "t_bab8c465", "contract": "docs/research/autoresearch-npm-revit-window-diff.md",
        "blender": str(BLENDER), "shift": SHIFT, "inputs_sha256": hashes, "preflight": "pins.json equal",
        "wall_s_total": round(time.perf_counter() - t0, 2), "render_wall_s": wall,
        "verdict_per_round": vs, "H137": h137, "H137b_cw_heldout": h137b, "m_edge_spread": spread,
        "max_spread": max(spread.values()), "witnesses_W1_f_r1": wit, "rounds": rounds,
    }
    (out / "receipt.json").write_text(json.dumps(receipt, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"H137": h137, "H137b": h137b, "per_round": vs, "max_spread": receipt["max_spread"],
                      "wall_s": receipt["wall_s_total"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
