"""MAF NPM-light version + atlas UV for a MAF set in one command (#1410, plan #425 steps 5-6).

Pattern: n/a | new-case: MAF NPM-light tool - the D293 "conversion" branch of the MAF NPM stage when the set does not
fit the budget [D164, D236, D167]: per row Decimate (never under the floor), material remap + UV transfer into
the shared 512 GroundEl atlas (tools/materials/maf_uv_remap.py), NPM FBX export and readback, then gates on the
readback: dimensions within [D094] of the full-resolution reference, silhouette IoU >= ``iou_min`` on three axis
views, 0 faces outside their atlas slot.

    dt derive maf-npm-light SPEC.json --out NEW_DIR        (alias: agr npm-light SPEC.json --out NEW_DIR)

Spec (``dt-maf-npm-light/1``; relative paths resolve against the spec file)::

    {"schema": "dt-maf-npm-light/1", "set": "SIL13-MAF", "atlas_json": "...", "atlas_png": "...",
     "smoothing_deg": 40.0, "floor_tris": 400, "iou_min": 0.95,
     "positions": [{"set_id": "...", "catalogue_id": "...", "source_fbx": "...", "decimate_ratio": 0.5,
                    "material_map": {"<source material>": "<atlas material>"}, "height_rule": "overall"}]}

One DCC run builds, per row, ``OUT/full/<set_id>.fbx`` (ratio 1.0 on the same atlas: the reference, not a VPM
delivery) and ``OUT/npm/<set_id>.fbx`` (the light version). Sources are copied to ``OUT/src`` first and their
SHA-256 is checked again after the run; nothing writes a source. Report: ``OUT/npm-light-report.json``.

Fail closed (``SpecError`` naming the key, exit 2, nothing written): unknown schema / key, empty positions, unsafe or
duplicate ``set_id``, two rows whose sources share a file name with different content, missing files, a ratio
outside (0, 1], a non-finite / out-of-range smoothing, floor or IoU threshold, a material map that is empty, not a
mapping or names an atlas material that does not exist (the builder also refuses an unmapped source material,
exit 3 before any export), an existing output folder, an output folder that is or contains an input.

Program choice: Blender headless (``tools/blender/maf_site_set_build.py`` via ``dt_ai.core.blender_runner``).
``run`` takes any ``dcc(config, atlas_json, atlas_png, out_dir)`` callable, so a 3ds Max (AGR Tools) adapter
calls the same core (roadmap #1374).

Exit codes: 0 every row passes; 3 a gate failed (rows listed with reasons); 1 the DCC run failed or a source
changed; 2 input error (nothing written).
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import re
import shutil
import sys
from pathlib import Path
from typing import Callable

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
BUILDER = ROOT / "tools" / "blender" / "maf_site_set_build.py"
SCHEMA = "dt-maf-npm-light/1"
SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
HEIGHT_RULES = ("overall", "max", "table_top")
DEFAULT_FLOOR = 400      # plan #425 step 5: rows already <= 400 tris are not lightened
DEFAULT_IOU = 0.95       # plan #425 step 5 (proposed threshold)
SILHOUETTE_PX = 256
TOP_KEYS = {"schema", "set", "atlas_json", "atlas_png", "smoothing_deg", "floor_tris", "iou_min", "positions"}
ROW_KEYS = {"set_id", "catalogue_id", "source_fbx", "decimate_ratio", "material_map", "height_rule", "note"}


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mss = _load("maf_site_set", "tools/library/maf_site_set.py")


class SpecError(ValueError):
    """The spec is not a complete, unambiguous NPM-light order; nothing was written."""


def _finite(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _path(base: Path, value, key: str) -> Path:
    if not isinstance(value, str) or not value:
        raise SpecError(f"{key}: a file path is required")
    p = Path(value)
    p = (p if p.is_absolute() else base / p).resolve()
    if not p.is_file():
        raise SpecError(f"{key}: file not found: {p}")
    return p


def load_spec(spec_path) -> dict:
    """Validate the spec; return it with resolved absolute paths. Raises SpecError naming the bad key."""
    spec_path = Path(spec_path).resolve()
    try:
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SpecError(f"spec unreadable: {exc}") from exc
    if not isinstance(spec, dict):
        raise SpecError("spec must be a JSON object")
    if spec.get("schema") != SCHEMA:
        raise SpecError(f"schema: expected {SCHEMA!r}, got {spec.get('schema')!r}")
    unknown = sorted(set(spec) - TOP_KEYS)
    if unknown:
        raise SpecError(f"unknown key(s): {unknown}")
    if not isinstance(spec.get("set"), str) or not SAFE_NAME.match(spec["set"]):
        raise SpecError(f"set: unsafe or missing name {spec.get('set')!r}")
    base = spec_path.parent
    atlas_json = _path(base, spec.get("atlas_json"), "atlas_json")
    atlas_png = _path(base, spec.get("atlas_png"), "atlas_png")
    try:
        atlas = json.loads(atlas_json.read_text(encoding="utf-8"))
        rects = {name: m["uv"] for name, m in atlas["materials"].items()}
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        raise SpecError(f"atlas_json: no materials with uv rects ({exc})") from exc
    if not rects:
        raise SpecError("atlas_json: no materials")
    for name, rect in rects.items():
        try:
            mss.uv_remap.check_rect(rect)
        except ValueError as exc:
            raise SpecError(f"atlas_json: material {name!r}: {exc}") from exc
    smoothing = spec.get("smoothing_deg")
    if not _finite(smoothing) or not (0.0 < smoothing < 180.0):
        raise SpecError(f"smoothing_deg: must be in (0, 180), got {smoothing!r}")
    floor = spec.get("floor_tris", DEFAULT_FLOOR)
    if isinstance(floor, bool) or not isinstance(floor, int) or floor < 0:
        raise SpecError(f"floor_tris: must be a non-negative integer, got {floor!r}")
    iou_min = spec.get("iou_min", DEFAULT_IOU)
    if not _finite(iou_min) or not (0.0 < iou_min <= 1.0):
        raise SpecError(f"iou_min: must be in (0, 1], got {iou_min!r}")
    rows = spec.get("positions")
    if not isinstance(rows, list) or not rows:
        raise SpecError("positions: at least one row is required")
    seen_ids, seen_names, out_rows = set(), {}, []
    for i, row in enumerate(rows):
        where = f"positions[{i}]"
        if not isinstance(row, dict):
            raise SpecError(f"{where}: must be an object")
        unknown = sorted(set(row) - ROW_KEYS)
        if unknown:
            raise SpecError(f"{where}: unknown key(s): {unknown}")
        sid = row.get("set_id")
        if not isinstance(sid, str) or not SAFE_NAME.match(sid):
            raise SpecError(f"{where}.set_id: unsafe or missing {sid!r}")
        if sid.lower() in seen_ids:
            raise SpecError(f"{where}.set_id: duplicate {sid!r}")
        seen_ids.add(sid.lower())
        src = _path(base, row.get("source_fbx"), f"{where}.source_fbx")
        prev = seen_names.get(src.name.lower())
        if prev is not None and sha256(prev) != sha256(src):
            raise SpecError(f"{where}.source_fbx: file name {src.name!r} also used by {prev} with other content")
        seen_names[src.name.lower()] = src
        ratio = row.get("decimate_ratio")
        if not _finite(ratio) or not (0.0 < ratio <= 1.0):
            raise SpecError(f"{where}.decimate_ratio: must be in (0, 1], got {ratio!r}")
        mmap = row.get("material_map")
        if not isinstance(mmap, dict) or not mmap:
            raise SpecError(f"{where}.material_map: a non-empty mapping source material -> atlas material is required")
        for key, target in mmap.items():
            if target not in rects:
                raise SpecError(f"{where}.material_map[{key!r}]: atlas material {target!r} does not exist "
                                f"(atlas has {sorted(rects)})")
        height_rule = row.get("height_rule", "overall")
        if height_rule not in HEIGHT_RULES:
            raise SpecError(f"{where}.height_rule: {height_rule!r} not in {HEIGHT_RULES}")
        cat = row.get("catalogue_id", sid)
        if not isinstance(cat, str) or not cat:
            raise SpecError(f"{where}.catalogue_id: must be a non-empty string")
        out_rows.append({"set_id": sid, "catalogue_id": cat, "source_fbx": str(src), "decimate_ratio": float(ratio),
                         "material_map": dict(mmap), "smoothing_deg": float(smoothing), "height_rule": height_rule})
    return {"spec": str(spec_path), "set": spec["set"], "atlas_json": str(atlas_json), "atlas_png": str(atlas_png),
            "rects": rects, "smoothing_deg": float(smoothing), "floor_tris": floor, "iou_min": float(iou_min),
            "positions": out_rows}


def check_out(out, spec: dict) -> Path:
    """The output folder must be new and must not be, contain or sit inside any input path."""
    out = Path(out).resolve()
    if out.exists():
        raise SpecError(f"--out exists: {out} (a new versioned folder is required)")
    inputs = [Path(spec["spec"]), Path(spec["atlas_json"]), Path(spec["atlas_png"])]
    inputs += [Path(r["source_fbx"]) for r in spec["positions"]]
    for p in inputs:
        if out == p or out in p.parents:
            raise SpecError(f"--out {out} is or contains the input {p}")
    return out


# ------------------------------------------------------------------ gates (pure, no DCC)
def silhouette_iou(tri_a, tri_b, px: int = SILHOUETTE_PX) -> dict:
    """IoU of the filled silhouettes of two triangle soups (N, 3, 3) on the three axis views, one common frame.

    Returns {"x": iou, "y": iou, "z": iou, "min": iou}. Empty or non-finite input raises.
    """
    a = np.asarray(tri_a, dtype=np.float64).reshape(-1, 3, 3)
    b = np.asarray(tri_b, dtype=np.float64).reshape(-1, 3, 3)
    if len(a) == 0 or len(b) == 0:
        raise ValueError("silhouette: no triangles")
    if not (np.isfinite(a).all() and np.isfinite(b).all()):
        raise ValueError("silhouette: non-finite vertex")
    pts = np.concatenate([a.reshape(-1, 3), b.reshape(-1, 3)])
    lo, hi = pts.min(axis=0), pts.max(axis=0)
    out = {}
    for axis, name in ((0, "x"), (1, "y"), (2, "z")):
        u, v = [i for i in range(3) if i != axis]
        span = max(hi[u] - lo[u], hi[v] - lo[v], 1e-9)
        step = span / px
        nu = max(1, int(math.ceil((hi[u] - lo[u]) / step)) + 1)
        nv = max(1, int(math.ceil((hi[v] - lo[v]) / step)) + 1)
        ma = _raster(a[:, :, [u, v]], lo[[u, v]], step, nu, nv)
        mb = _raster(b[:, :, [u, v]], lo[[u, v]], step, nu, nv)
        union = np.logical_or(ma, mb).sum()
        out[name] = float(np.logical_and(ma, mb).sum() / union) if union else 1.0
    out["min"] = min(out["x"], out["y"], out["z"])
    return out


def _raster(tris2, origin, step, nu, nv) -> np.ndarray:
    """Pixel-centre coverage of 2D triangles (conservative: a pixel whose centre is inside or on an edge)."""
    mask = np.zeros((nu, nv), dtype=bool)
    t = (tris2 - origin) / step - 0.5          # pixel-centre coordinates
    for tri in t:
        (x0, y0), (x1, y1), (x2, y2) = tri
        i0, i1 = max(0, int(math.floor(min(x0, x1, x2)))), min(nu - 1, int(math.ceil(max(x0, x1, x2))))
        j0, j1 = max(0, int(math.floor(min(y0, y1, y2)))), min(nv - 1, int(math.ceil(max(y0, y1, y2))))
        if i1 < i0 or j1 < j0:
            continue
        gx, gy = np.meshgrid(np.arange(i0, i1 + 1), np.arange(j0, j1 + 1), indexing="ij")
        d = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
        if abs(d) < 1e-12:                      # edge-on triangle: mark the pixels its segments cross
            for (ax, ay), (bx, by) in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
                n = int(max(abs(bx - ax), abs(by - ay))) + 2
                xs = np.clip(np.rint(np.linspace(ax, bx, n)).astype(int), 0, nu - 1)
                ys = np.clip(np.rint(np.linspace(ay, by, n)).astype(int), 0, nv - 1)
                mask[xs, ys] = True
            continue
        l0 = ((y1 - y2) * (gx - x2) + (x2 - x1) * (gy - y2)) / d
        l1 = ((y2 - y0) * (gx - x2) + (x0 - x2) * (gy - y2)) / d
        inside = (l0 >= -1e-9) & (l1 >= -1e-9) & (1 - l0 - l1 >= -1e-9)
        mask[i0:i1 + 1, j0:j1 + 1] |= inside
        for x, y in tri:                        # sub-pixel triangles still mark their corners
            mask[min(nu - 1, max(0, int(round(x)))), min(nv - 1, max(0, int(round(y))))] = True
    return mask


def gate_row(entry: dict, full_tris, npm_tris, iou_min: float, tol_m: float = mss.DIMENSION_TOL_M) -> dict:
    """Verdict of one row from the builder report entry and the readback triangle dumps."""
    full, npm = entry["full"], entry["npm"]
    rf, rn = full["readback"], npm["readback"]
    reasons = []
    dims = [abs(a - b) for a, b in zip(rn["size_m"], rf["size_m"])]
    if len(dims) != 3 or not all(math.isfinite(d) for d in dims):
        reasons.append("dims: readback size missing or non-finite")
    elif max(dims) > tol_m + 1e-9:
        reasons.append(f"dims: max deviation {max(dims):.4f} m > {tol_m} m [D094]")
    for role, rb in (("full", rf), ("npm", rn)):
        if rb["uv_slots"]["faces_outside"] != 0:
            reasons.append(f"uv: {role} has {rb['uv_slots']['faces_outside']} faces outside their atlas slot")
    iou = silhouette_iou(full_tris, npm_tris)
    if not iou["min"] >= iou_min:
        reasons.append(f"silhouette: IoU {iou['min']:.4f} < {iou_min}")
    tri_full, tri_npm = rf["triangles"], rn["triangles"]
    if npm["light"] == "refused_floor" and tri_npm != tri_full:
        reasons.append(f"floor: row under the floor changed {tri_full} -> {tri_npm} tris")
    return {"set_id": entry["set_id"], "light": npm["light"], "decimate_ratio": npm["decimate_ratio"],
            "tris_full": tri_full, "tris_npm": tri_npm, "tris_saved": tri_full - tri_npm,
            "dims_dev_m": dims, "silhouette_iou": iou, "uv_faces_outside": rn["uv_slots"]["faces_outside"],
            "fbx": npm["fbx"], "passed": not reasons, "reasons": reasons}


# ------------------------------------------------------------------ run
def blender_dcc(config: Path, atlas_json: Path, atlas_png: Path, out: Path) -> None:
    """Default DCC: headless Blender with the shared builder (raises BlenderRunError on a failed run)."""
    sys.path.insert(0, str(ROOT / "src"))
    from dt_ai.core.blender_runner import run_blender

    run_blender(BUILDER, [str(config), str(atlas_json), str(atlas_png), str(out)],
                output_json=out / "build-report.json", timeout=3600, log_path=out / "blender.log")


def run(spec_path, out, dcc: Callable | None = None) -> tuple[int, dict]:
    spec = load_spec(spec_path)
    out = check_out(out, spec)
    hashes = {r["source_fbx"]: sha256(Path(r["source_fbx"])) for r in spec["positions"]}
    (out / "src").mkdir(parents=True)
    for r in spec["positions"]:
        dst = out / "src" / Path(r["source_fbx"]).name
        if not dst.exists():
            shutil.copy2(r["source_fbx"], dst)
        if sha256(dst) != hashes[r["source_fbx"]]:
            raise RuntimeError(f"copy of {r['source_fbx']} differs from the source")
    config = out / "build-config.json"
    config.write_text(json.dumps({"smoothing_deg": spec["smoothing_deg"], "roles": ["full", "npm"],
                                  "npm_floor_tris": spec["floor_tris"], "dump_triangles": True,
                                  "positions": spec["positions"]}, indent=1, ensure_ascii=False), encoding="utf-8")
    report = {"schema": SCHEMA + "-report", "set": spec["set"], "spec": spec["spec"], "out": str(out),
              "atlas_json": spec["atlas_json"], "atlas_png": spec["atlas_png"], "floor_tris": spec["floor_tris"],
              "iou_min": spec["iou_min"], "rows": [], "dropped": [], "sources_unchanged": None}
    code = 0
    try:
        (dcc or blender_dcc)(config, Path(spec["atlas_json"]), Path(spec["atlas_png"]), out)
        build = json.loads((out / "build-report.json").read_text(encoding="utf-8"))
        by_id = {e["set_id"]: e for e in build["positions"]}
        for r in spec["positions"]:
            entry = by_id.get(r["set_id"])
            if entry is None or "full" not in entry or "npm" not in entry:
                report["dropped"].append({"set_id": r["set_id"], "reason": "missing from the build report"})
                continue
            full_t = np.load(out / "readback" / "full" / (r["set_id"] + ".npy"))
            npm_t = np.load(out / "readback" / "npm" / (r["set_id"] + ".npy"))
            report["rows"].append(gate_row(entry, full_t, npm_t, spec["iou_min"]))
    except Exception as exc:   # noqa: BLE001 - any DCC / report failure is a failed run, recorded
        report["error"] = f"{type(exc).__name__}: {exc}"
        code = 1
    changed = [s for s, h in hashes.items() if sha256(Path(s)) != h]
    report["sources_unchanged"] = not changed
    if changed:
        report["error"] = report.get("error", "") + f" sources changed: {changed}"
        code = 1
    if code == 0 and (report["dropped"] or not all(r["passed"] for r in report["rows"])):
        code = 3
    report["tris_full_total"] = sum(r["tris_full"] for r in report["rows"])
    report["tris_npm_total"] = sum(r["tris_npm"] for r in report["rows"])
    report["status"] = {0: "pass", 1: "error", 3: "fail"}[code]
    report["passed"] = code == 0
    (out / "npm-light-report.json").write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    return code, report


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="dt derive maf-npm-light", description=__doc__.split("\n\n")[0])
    ap.add_argument("spec", help="dt-maf-npm-light/1 spec JSON")
    ap.add_argument("--out", required=True, help="NEW output folder (must not exist)")
    ns = ap.parse_args(argv)
    try:
        code, report = run(ns.spec, ns.out)
    except SpecError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    for r in report["rows"]:
        print(f"{r['set_id']}: {r['light']} {r['tris_full']} -> {r['tris_npm']} tris, "
              f"IoU {r['silhouette_iou']['min']:.3f}, uv out {r['uv_faces_outside']}, "
              f"{'pass' if r['passed'] else 'FAIL ' + '; '.join(r['reasons'])}")
    for d in report["dropped"]:
        print(f"{d['set_id']}: DROPPED {d['reason']}")
    if report.get("error"):
        print(f"ERROR: {report['error']}", file=sys.stderr)
    print(f"{report['status']}: {report['tris_full_total']} -> {report['tris_npm_total']} tris; "
          f"report {Path(ns.out).resolve() / 'npm-light-report.json'}")
    return code


if __name__ == "__main__":
    sys.exit(main())
