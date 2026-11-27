"""#131 OBSERVE harness: D171 joint-gate field binding on AC08 v007 (rejected) / v010 (accepted).

Reuses jobs/TEC26-OKS/scripts/joint_count.py and compare_facades.py unchanged (imported, never edited). C1 rebinding
exists only here. Contract: docs/research/autoresearch-ac08-joint-gate-binding.md.
"""
import copy
import hashlib
import io
import json
import subprocess
import sys
import time
from pathlib import Path
from zipfile import ZipFile

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "jobs/TEC26-OKS/scripts"))
import compare_facades  # noqa: E402
import joint_count  # noqa: E402

EV = Path("G:/Мой диск/AGR-evidence")
GATE = EV / "127-ac08-joint-gate"
GATE_SUMS = "28ff6d843ff5ef759cb6267c19c653a22c8b8ddce7412a767f5897efde4ccd15"
SPEC = ROOT / "jobs/TEC26-OKS/AC08/vpm_textures.json"
SHEET = ROOT / "jobs/TEC26-OKS/AC08/sheet-facades.json"
LABELS = {"pilot-v007": "rejected", "pilot-v010": "accepted"}
TOL_W = 0.010  # frozen binding tolerance (m)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def sums(folder):
    out = {}
    for line in (folder / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
        h, name = line.split(maxsplit=1)
        out[name.lstrip("*").removeprefix("./")] = h
    return out


def preflight():
    if sha(GATE / "SHA256SUMS.txt") != GATE_SUMS:
        raise SystemExit("127 SHA256SUMS.txt digest mismatch")
    gs, checked = sums(GATE), {}
    for ver in LABELS:
        for rel in [f"{ver}/vpm.readback.json"] + [f"{ver}/renders_r127/{p}" for p in
                                                    ("renders.json", *(f"{k}_{v}.png" for k in ("vpm", "npm")
                                                                       for v in ("north", "south", "east", "west")))]:
            if sha(GATE / rel) != gs[rel]:
                raise SystemExit(f"digest mismatch {rel}")
            checked[f"127/{rel}"] = gs[rel]
        folder = EV / f"559-tec26-oks-ac08-{ver}"
        want = sums(folder)["SM_Nku_1.zip"]
        if sha(folder / "SM_Nku_1.zip") != want:
            raise SystemExit(f"digest mismatch {ver} SM_Nku_1.zip")
        checked[f"559/{ver}/SM_Nku_1.zip"] = want
    return checked


def git_blob(path):
    return subprocess.check_output(["git", "hash-object", str(path)], text=True, cwd=ROOT).strip()


def load(ver):
    rb = json.loads((GATE / ver / "vpm.readback.json").read_text(encoding="utf-8"))
    vmain = next(o for o in rb["objects"] if not o["name"].startswith("UCX_"))
    with ZipFile(EV / f"559-tec26-oks-ac08-{ver}" / "SM_Nku_1.zip") as z:
        tiles = {int(n.rsplit(".", 2)[-2]): np.asarray(Image.open(io.BytesIO(z.read(n))).convert("RGB"))
                 for n in z.namelist() if n.startswith("T_Nku_1_Diffuse_1.")}
    rdir = GATE / ver / "renders_r127"
    meta = json.loads((rdir / "renders.json").read_text(encoding="utf-8"))
    imgs = {(t, v): np.asarray(Image.open(rdir / f"{t}_{v}.png").convert("RGB"))
            for t in ("vpm", "npm") for v in ("north", "south", "east", "west")}
    return vmain, tiles, meta, imgs


def tile_of_factory(tiles):
    def tile_of(u, v):  # as qa_packages.facade_joint_checks.vpm_tile_of
        groups = []
        tu, tv = np.floor(u).astype(int), np.floor(v).astype(int)
        for a, b in sorted(set(zip(tu.tolist(), tv.tolist()))):
            idx = np.where((tu == a) & (tv == b))[0]
            img = tiles.get(1001 + a + 10 * b)
            if img is not None:
                groups.append((idx, img, u[idx] - a, v[idx] - b))
        return groups
    return tile_of


def facade(vmain, tiles, meta, imgs, spec, sheet, name, rebind):
    V, F = np.asarray(vmain["vertices"], float), vmain["faces"]
    uvs = [np.asarray(u, float) for u in vmain["face_uvs"]]
    fc, f = spec["facades"][name], sheet["facades"][name]
    key = fc["normal"]
    udim = lambda t: int(1001 + np.floor(uvs[t].mean(0)[0]) + 10 * np.floor(uvs[t].mean(0)[1]))  # noqa: E731
    ground = min(p["bbox_mm"][1] for p in f["plinth"]) / 1000
    width = f["field_width_mm"] / 1000

    def bind(ud):
        tris = joint_count.facade_triangles(V, F, lambda t: udim(t) == ud, key)
        if not tris:
            return None, False
        fld = joint_count.field_extent(V, F, tris, key)
        return [float(x) for x in fld], bool(abs((fld[1] - fld[0]) - width) <= TOL_W and fld[2] >= ground)

    spec_ud = spec["finishes"][fc["finish"]]["udim"]
    fld, ok = bind(spec_ud)
    row = {"spec_udim": spec_ud, "spec_field": fld, "binding_ok": ok, "used_udim": spec_ud, "rebound": False}
    if not ok and rebind:
        cands = sorted({udim(t) for t in joint_count.facade_triangles(V, F, lambda t: True, key)})
        good = [u for u in cands if bind(u)[1]]
        row["rebind_candidates"] = good
        if len(good) != 1:
            row["refused"] = f"{len(good)} passing UDIMs"
            return row
        row.update(used_udim=good[0], rebound=True)
        fld = bind(good[0])[0]
    if fld is None:
        row["refused"] = "no triangles"
        return row
    lo, hi, zlo, zhi = fld
    for tag in ("vpm", "npm"):
        view = meta[tag]["views"][compare_facades.VIEW[key]]
        axis = 1 if key in ("+x", "-x") else 0
        rows = {}
        for frac in (0.2, 0.95):
            z = zlo + frac * (zhi - zlo)
            s, lum = joint_count.render_row(imgs[tag, compare_facades.VIEW[key]], view, axis, z, lo, hi)
            r = joint_count.count_joints(s, lum, lo, hi, fc["ribs"], tol=0.01, dark=0.85)
            rows[f"{frac}"] = {"z": round(z, 3), "found": r.get("joints_found"), "nan_frac":
                               round(float(np.mean(~np.isfinite(lum))), 4) if len(lum) else None}
        row[f"{tag}_render"] = rows["0.95"]["found"]
        row[f"{tag}_rows"] = rows
    used = row["used_udim"]
    rep = joint_count.mesh_facade_report(V, F, uvs, lambda t: udim(t) == used, key, fc["ribs"],
                                         tile_of_factory(tiles), tol=0.003)
    top = rep["rows"][f"z={zlo + 0.95 * (zhi - zlo):.3f}"] if "rows" in rep else {}
    row["truth_T"] = top.get("joints_found")
    row["want"] = fc["ribs"] - 1
    return row


def package(ver, spec, sheet, rebind, data):
    rows = {n: facade(*data[ver], spec, sheet, n, rebind) for n in spec["facades"]}
    scored = [r for r in rows.values() if "refused" not in r]
    out = {"facades": rows, "B131": sum(not r["binding_ok"] for r in rows.values()),
           "refused": [n for n, r in rows.items() if "refused" in r]}
    if len(scored) == len(rows):
        out["E127"] = sum(abs(r[f"{t}_render"] - r["want"]) for r in scored for t in ("vpm", "npm"))
        out["A131"] = sum(abs(r[f"{t}_render"] - r["truth_T"]) for r in scored for t in ("vpm", "npm"))
    return out


def one_round(data):
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    sheet = json.loads(SHEET.read_text(encoding="utf-8"))
    res = {}
    for ver in LABELS:
        res[ver] = {"baseline": package(ver, spec, sheet, False, data), "C1": package(ver, spec, sheet, True, data)}
    k1 = copy.deepcopy(spec); k1["finishes"]["PanelVJ12_RAL5015"]["udim"] = 1003
    k2 = copy.deepcopy(spec); k2["finishes"]["PanelVJ30_RAL5015"]["udim"] = 1004
    res["controls_v010"] = {k: {"baseline": package("pilot-v010", s, sheet, False, data),
                                "C1": package("pilot-v010", s, sheet, True, data)} for k, s in (("K1", k1), ("K2", k2))}
    return res


def main(out):
    t0 = time.monotonic()
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    receipt = {"status": "preflight", "head": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True,
                                                                     cwd=ROOT).strip()}
    try:
        receipt["inputs_sha256"] = preflight()
        receipt["git_blobs"] = {p: git_blob(ROOT / p) for p in (
            "jobs/TEC26-OKS/scripts/joint_count.py", "jobs/TEC26-OKS/scripts/compare_facades.py",
            "jobs/TEC26-OKS/AC08/vpm_textures.json", "jobs/TEC26-OKS/AC08/sheet-facades.json",
            "docs/research/autoresearch-ac08-joint-gate-binding-harness/run.py")}
        receipt["versions"] = {"python": sys.version.split()[0], "numpy": np.__version__}
        data = {ver: load(ver) for ver in LABELS}
        receipt["rounds"] = []
        for i in range(3):
            r0 = time.monotonic()
            res = one_round(data)
            blob = json.dumps(res, sort_keys=True, ensure_ascii=False).encode()
            (out / f"round{i + 1}.json").write_bytes(blob)
            receipt["rounds"].append({"seconds": round(time.monotonic() - r0, 3),
                                      "sha256": hashlib.sha256(blob).hexdigest()})
            if time.monotonic() - t0 > 600:
                receipt["status"] = "budget_stop"
                break
        else:
            receipt["status"] = "series_complete"
        receipt["identical"] = len({r["sha256"] for r in receipt["rounds"]}) == 1
        receipt["result"] = res
    except Exception as e:  # noqa: BLE001
        receipt.update(status="refused", error=repr(e))
        raise
    finally:
        receipt["seconds"] = round(time.monotonic() - t0, 3)
        (out / "receipt.json").write_text(json.dumps(receipt, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1])
