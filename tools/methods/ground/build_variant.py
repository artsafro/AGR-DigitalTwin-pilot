"""Build one ground-terrain variant from the typed adapter JSON into a new folder (methods catalog, #733).

Pattern: new-case: methods-catalog driver for the ground-terrain class (builder / CDT / Blender grid).

    uv run python tools/methods/ground/build_variant.py <builder|cdt|bgrid> <adapter.json> --cell <m> --out <new dir> \\
        [--expect-sha256 <hex>] [--address Vatutino]

Variants (docs/methods/ground-terrain/VARIANTS.md):
- builder: jobs/VATUTINO-SITE/build_ground.py run unchanged in a fresh process with the v014 arguments
  (--snap 0.003 --gap-exceptions jobs/VATUTINO-SITE/ground-gap-exceptions.json) and the given --cell; its VPM master.
- cdt: plan polygon from the same method-C planner, constrained Delaunay per grid cell (shapely / GEOS), Z from the
  adapter TIN (all elevations), world-planar UV, one `Surface` slot.
- bgrid: same plan polygon and elevations handed to factory Blender (build_grid_blender.py): grid, cut, raycast.
Every variant is exported by the shared tools/blender/ground_json_to_fbx.py build (same names, pivot and
`.placement.json` sidecar), so the comparison differs only in the mesher. Writes <out>/SM_<Address>_Ground.fbx,
its sidecar and <out>/SM_<Address>_Ground.fbx.variant.json ({ok, wall_time_s, input, ...}); work files in
<out>/work/. Exit 0 built; 1 the variant failed (report ok=false with the error, no FBX); 4 refused before any
write (unknown variant, bad cell, --out not new/empty or aliasing the input, input sha256 differs, --address
not a plain name or any derived FBX/sidecar/report/work path escaping --out or resolving to the input).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(HERE))

import ground_variants as gv  # noqa: E402

VARIANTS = ("builder", "cdt", "bgrid")
BUILDER_ARGS = ["--snap", "0.003", "--gap-exceptions", str(ROOT / "jobs" / "VATUTINO-SITE" / "ground-gap-exceptions.json")]
FBX_WRITER = ROOT / "tools" / "blender" / "ground_json_to_fbx.py"
GRID_SCRIPT = HERE / "build_grid_blender.py"


class Refused(ValueError):
    pass


ADDRESS_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")


def derived_paths(out: Path, address: str, adapter: Path) -> dict[str, Path]:
    """Every path the driver writes, renames or creates, checked before any write: --address is a plain name
    (letters, digits, `_`, `-`; no separator, dot, drive or traversal), each path sits directly in --out (work/ is
    the one subfolder) and none resolves to the adapter."""
    if not isinstance(address, str) or not ADDRESS_RE.fullmatch(address):
        raise Refused(f"--address {address!r} must match {ADDRESS_RE.pattern} (a plain name, no path)")
    fbx = out / f"SM_{address}_Ground.fbx"
    paths = {"fbx": fbx, "placement": Path(str(fbx) + ".placement.json"),
             "report": Path(str(fbx) + ".variant.json"), "failed": fbx.with_name(fbx.name + ".failed"),
             "work": out / "work"}
    ro, ra = out.resolve(), adapter.resolve()
    for key, p in paths.items():
        rp = p.resolve()
        if rp.parent != ro:
            raise Refused(f"derived {key} path {p} escapes --out {out}")
        if rp == ra or ra.is_relative_to(rp):
            raise Refused(f"derived {key} path {p} is or holds the input {ra}")
        if p.exists():
            raise Refused(f"derived {key} path {p} already exists")
    return paths


def _blender(script: Path, *rest: str, timeout: int = 1800) -> subprocess.CompletedProcess:
    from dt_ai.core.blender_runner import blender_executable

    cmd = [blender_executable(), "--background", "--factory-startup", "--python-exit-code", "1",
           "--python", str(script), "--", *rest]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def check_args(variant: str, adapter: Path, cell: float, out: Path, expect: str | None) -> bytes:
    if variant not in VARIANTS:
        raise Refused(f"unknown variant {variant!r}; known: {list(VARIANTS)}")
    if not math.isfinite(cell) or cell <= 0:
        raise Refused(f"--cell must be a finite number > 0, got {cell!r}")
    if not adapter.is_file():
        raise Refused(f"no adapter JSON {adapter}")
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        raise Refused(f"--out {out} must be a new or empty folder")
    rs = adapter.resolve()
    if out.resolve() == rs or rs.is_relative_to(out.resolve()):
        raise Refused(f"--out {out} holds or is the input {rs}")
    data = adapter.read_bytes()
    if expect and hashlib.sha256(data).hexdigest() != expect.lower():
        raise Refused(f"{adapter.name} sha256 {hashlib.sha256(data).hexdigest()} != expected {expect}")
    return data


def build_mesh(variant: str, adapter: Path, data: bytes, cell: float, work: Path) -> tuple[Path, dict]:
    """Mesh JSON for ground_json_to_fbx.py plus the variant's own facts; raises RuntimeError on a failed build."""
    if variant == "builder":
        proc = subprocess.run([sys.executable, str(ROOT / "jobs" / "VATUTINO-SITE" / "build_ground.py"), str(adapter),
                               "--cell", repr(cell), *BUILDER_ARGS, "--out", str(work / "builder")],
                              capture_output=True, text=True, timeout=7000)
        (work / "builder.log").write_text(proc.stdout[-20000:] + "\n--- stderr\n" + proc.stderr[-20000:],
                                          encoding="utf-8")
        master = work / "builder" / "ground_master_vpm.json"
        if proc.returncode != 0 or not master.is_file():
            raise RuntimeError(f"build_ground.py exit {proc.returncode}: {proc.stderr.strip()[-300:]}")
        rep = json.loads((work / "builder" / "ground_report.json").read_text(encoding="utf-8"))
        return master, {"builder_seconds": rep.get("seconds"), "surface_sha256": rep.get("surface_sha256"),
                        "budget": rep.get("budget"), "failed_gates": [k for k, v in rep["gates"].items() if not v["pass"]]}
    adapter_data = json.loads(data)
    poly = gv.plan_polygon(adapter_data)
    relief = gv.relief_points(adapter_data)
    facts = {"plan_area_m2": round(poly.area, 3), "plan_parts": len(poly.geoms),
             "plan_holes": sum(len(p.interiors) for p in poly.geoms), "relief_points": len(relief)}
    if variant == "cdt":
        v2, faces = gv.cdt_mesh(poly, cell)
        z, misses = gv.project_relief(v2, relief)
        verts = [[x, y, zz] for (x, y), zz in zip(v2.tolist(), z.tolist())]
        facts.update(relief_misses=len(misses), triangles=len(faces))
    else:
        minx, miny, maxx, maxy = poly.bounds
        origin = (round((minx + maxx) / 2), round((miny + maxy) / 2))
        prep = {"cell": cell, "origin": origin,
                "rings": [[[x - origin[0], y - origin[1]] for x, y in r] for r in gv.plan_rings(poly)],
                "relief": [[x - origin[0], y - origin[1], z] for x, y, z in relief]}
        (work / "prep.json").write_text(json.dumps(prep), encoding="utf-8")
        local = work / "mesh_local.json"
        proc = _blender(GRID_SCRIPT, str(work / "prep.json"), str(local))
        (work / "bgrid.log").write_text(proc.stdout[-20000:] + "\n--- stderr\n" + proc.stderr[-20000:],
                                        encoding="utf-8")
        if proc.returncode != 0 or not local.is_file():
            raise RuntimeError(f"build_grid_blender.py exit {proc.returncode}: {proc.stderr.strip()[-300:]}")
        res = json.loads(local.read_text(encoding="utf-8"))
        verts = [[x + origin[0], y + origin[1], z] for x, y, z in res["verts"]]
        faces = res["faces"]
        facts.update(res["report"])
    mesh = work / "mesh.json"
    mesh.write_text(json.dumps(gv.mesh_dict(verts, faces, {"variant": variant, "cell": cell, **facts})),
                    encoding="utf-8")
    return mesh, facts


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("variant")
    ap.add_argument("adapter", type=Path)
    ap.add_argument("--cell", type=float, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--expect-sha256")
    ap.add_argument("--address", default="Vatutino")
    a = ap.parse_args(argv)
    try:
        data = check_args(a.variant, a.adapter, a.cell, a.out, a.expect_sha256)
        paths = derived_paths(a.out, a.address, a.adapter)
    except (Refused, OSError) as exc:
        print(f"GROUND_VARIANT refused: {exc}", file=sys.stderr)
        return 4
    work, fbx, report_path = paths["work"], paths["fbx"], paths["report"]
    work.mkdir(parents=True)
    report = {"ok": False, "variant": a.variant, "cell_m": a.cell,
              "input": {"kind": "adapter-v4", "path": str(a.adapter), "sha256": hashlib.sha256(data).hexdigest()}}
    t0 = time.perf_counter()
    try:
        mesh, facts = build_mesh(a.variant, a.adapter, data, a.cell, work)
        proc = _blender(FBX_WRITER, "build", str(mesh), str(fbx), a.address)
        if proc.returncode != 0 or not fbx.is_file():
            raise RuntimeError(f"ground_json_to_fbx build exit {proc.returncode}: {proc.stderr.strip()[-300:]}")
        if a.adapter.read_bytes() != data:
            raise RuntimeError("adapter changed during the build")
        report.update(ok=True, wall_time_s=round(time.perf_counter() - t0, 3), facts=facts)
    except (RuntimeError, ValueError, OSError, KeyError, subprocess.TimeoutExpired) as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
        report["wall_time_s"] = round(time.perf_counter() - t0, 3)
        if fbx.exists():
            fbx.rename(paths["failed"])
    report_path.write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(f"GROUND_VARIANT {a.variant} cell {a.cell}: ok={report['ok']} {report.get('error', '')}".rstrip())
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
