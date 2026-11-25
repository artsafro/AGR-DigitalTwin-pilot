"""Ground for any site (`dt ground site` / `agr ground site`, #1406): D293 order from a site spec JSON.

Pattern: n/a | new-case: site-spec CLI over dt_ai.geometry.ground_site (no job-specific code).

usage: dt ground site SPEC.json NEW_OUT_DIR

The spec names the DXF (with sha256), boundary handle, project zero (+ source), covers (ID, name, hatch handles;
ID colour = hatch background colour or a stated colour with reason), base ID, relief marks (block / INSERT names /
contour layers) and optional crop box and parameters. Output (new directory, written via NEW_OUT_DIR.partial):
ground-flat.obj (flat-first stage), SM_<site>_Ground.obj (projected + skirt, UDIM = ID), ground-report.json
(every stage, OBJ readback and the project zero check on the OBJ readback). Exit 0 built (advisories such as
UCX not_run: #1404 never change it), 1 geometry failures (diagnostic OBJ + failed report are still published,
passed=false: not package readiness evidence), 2 refused. No FBX is written or read: its zero is not_measured.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from dt_ai.core.heights import export_z_check
from dt_ai.geometry import ground_site as gs

TOP_KEYS = {"site", "dxf", "adapter", "adapter_empty", "boundary", "crop_box", "zero", "covers", "base_id", "relief", "params", "note",
            "unhatched"}
PARAMS = {"cell", "chord", "step", "snap", "relief_tol", "skirt_m", "tex_px", "footprint_min_area", "origin_xy",
          "relief_extension", "surfaces"}


def adapter_sources(path: Path, spec: dict):
    """Typed SPOZU adapter JSON (``adapters.cad.spozu`` output, e.g. Vatutino #295) -> boundary, covers, relief.

    Cover rows: ``{"id", "name", "adapter_keys": [...], "colour": [r, g, b], "colour_reason"}``; the adapter has no
    hatch colours, so the colour is always stated. An adapter covering not named by any row, or a key named twice
    or missing, is an error naming it (no default cover)."""
    from shapely.geometry import shape
    d = json.loads(path.read_text(encoding="utf-8"))
    cov = d.get("coverings") or {}
    named: dict = {}
    covers = []
    for row in spec["covers"]:
        keys = row.get("adapter_keys") or []
        if not keys:
            raise ValueError(f"cover {row.get('id')} {row.get('name')}: adapter_keys missing")
        polys = []
        for k in keys:
            if k in named:
                raise ValueError(f"adapter covering {k!r} named by covers {named[k]} and {row['id']}")
            if k not in cov:
                raise ValueError(f"adapter covering {k!r} not in {path.name}")
            named[k] = row["id"]
            g = shape(cov[k]["geometry"])
            polys += list(getattr(g, "geoms", [g]))
        if "colour" not in row or not str(row.get("colour_reason", "")).strip():
            raise ValueError(f"cover {row['id']} {row['name']}: adapter covers need a stated colour + colour_reason")
        covers.append(gs.Cover(int(row["id"]), row["name"], polys, tuple(row["colour"]), "spec",
                               [{"adapter_key": k} for k in keys]))
    left = sorted(set(cov) - set(named) - set(spec.get("adapter_empty") or []))
    if left:
        raise ValueError(f"adapter coverings {left} are not mapped to a cover ID")
    for k in spec.get("adapter_empty") or []:
        if k in named or k not in cov or not shape(cov[k]["geometry"]).is_empty:
            raise ValueError(f"adapter_empty {k!r} must be an unmapped adapter covering with empty geometry")
    relief = [(e["x"], e["y"], e["z"]) for e in d["elevations"]]
    return shape(d["boundary"]), covers, relief


def run(spec_path: Path, out: Path) -> int:
    spec_digest = gs.sha256(spec_path)
    spec = gs.load_spec(spec_path)
    unknown = set(spec) - TOP_KEYS
    if unknown:
        raise ValueError(f"unknown spec keys {sorted(unknown)}")
    for key in ("site", "zero", "covers", "base_id"):
        if key not in spec:
            raise ValueError(f"spec misses {key!r}" + (" (take it from the project or ask, D293)"
                                                        if key == "zero" else ""))
    if ("dxf" in spec) == ("adapter" in spec):
        raise ValueError("spec needs exactly one source: 'dxf' (hatches) or 'adapter' (typed SPOZU JSON)")
    if "dxf" in spec:
        for key in ("boundary", "relief"):
            if key not in spec:
                raise ValueError(f"spec misses {key!r}")
    params = spec.get("params") or {}
    if set(params) - PARAMS:
        raise ValueError(f"unknown params {sorted(set(params) - PARAMS)}")
    site = spec["site"]
    if not isinstance(site, str) or not site or not all(c.isalnum() or c == "_" for c in site):
        raise ValueError(f"site {site!r}: Latin letters, digits and _ only")
    zero = spec["zero"]
    if not isinstance(zero, dict) or not str(zero.get("source", "")).strip():
        raise ValueError("zero needs project_zero_m and source (from the project or the agent asks, D293)")
    dxf = Path((spec.get("dxf") or spec.get("adapter"))["path"])
    if not spec_path.is_absolute():
        spec_path = spec_path.resolve()
    inputs = {spec_path.resolve(), dxf.resolve()}
    out_r, partial = out.resolve(), Path(str(out.resolve()) + ".partial")
    if out_r in inputs or partial in inputs:
        raise ValueError(f"output {out} resolves to an input")
    if out_r.exists() or partial.exists():
        raise ValueError(f"output {out} (or its .partial) exists: give a new versioned path")
    digest = gs.sha256(dxf)
    want = (spec.get("dxf") or spec.get("adapter")).get("sha256")
    if digest != want:
        raise ValueError(f"source sha256 {digest} != spec {want}")

    chord = float(params.get("chord", 0.02))
    if "adapter" in spec:
        boundary, covers, relief = adapter_sources(dxf, spec)
    else:
        import ezdxf
        doc = ezdxf.readfile(str(dxf))
        boundary = gs.boundary_from_dxf(doc, spec["boundary"]["handle"])
        covers = gs.covers_from_dxf(doc, spec["covers"], max(chord, 0.002))
        relief = gs.relief_from_dxf(doc, spec["relief"])
    kw = {k: params[k] for k in params if k in PARAMS and k != "origin_xy"}
    result = gs.build_site(boundary, covers, spec["base_id"], relief, zero["project_zero_m"],
                           origin_xy=params.get("origin_xy"), crop_box=spec.get("crop_box"),
                           unhatched=spec.get("unhatched"), **kw)
    rep = result.report
    rep["site"] = site
    rep["stages"]["sources"].update({"dxf": str(dxf), "dxf_sha256": digest, "spec": str(spec_path),
                                     "spec_sha256": gs.sha256(spec_path), "zero_source": zero["source"]})
    prefix = f"SM_{site}_Ground"
    if gs.sha256(spec_path) != spec_digest or gs.sha256(dxf) != digest:
        raise ValueError("spec or DXF changed during the site build; nothing published")
    rep["stages"]["sources"]["spec_sha256"] = spec_digest
    partial.mkdir(parents=True)
    gs.write_obj(partial / "ground-flat.obj", result.flat, result.slots, prefix, "flat-first stage, Z = level*step")
    gs.write_obj(partial / f"{prefix}.obj", result.mesh, result.slots, prefix,
                 f"local XY = source - {rep['stages']['sources']['origin_xy_m']}; Z = mark - {zero['project_zero_m']}")
    back = gs.read_obj(partial / f"{prefix}.obj")
    rep["readback"] = {k: v for k, v in back.items() if k not in ("z_values", "points")}
    skirt_m = float(params.get("skirt_m", 1.0))
    rep["skirt_export_check"] = gs.skirt_check_export(partial / f"{prefix}.obj", skirt_m)
    fails = rep["geometry_failures"]
    if rep["skirt_export_check"]["status"] != "pass":
        fails.append(f"export skirt: {rep['skirt_export_check']['gap_count']} outer edges without a "
                     f">= {skirt_m} m skirt (GND-03)")
    from dt_ai.ops.inv_xview import mesh_report
    xv = mesh_report(result.mesh.verts, result.mesh.faces, profile="NPM-GROUND", part=prefix)
    rep["xview"] = {k: xv[k] for k in ("passed", "vertex_pairs", "face_pairs", "thresholds")}
    if not xv["passed"]:
        fails.append(f"xView: {xv['vertex_pairs']} near vertex pairs / {xv['face_pairs']} face pairs")
    origin_xy = rep["stages"]["sources"]["origin_xy_m"]
    obj_zero_z = 0.0  # assumed: the OBJ is written with Z local = mark - project zero (see its header comment)
    check = export_z_check(zero["project_zero_m"], obj_zero_z, gs.ground_points(back, origin_xy),
                           gs.relief_z_at(relief, gs.relief_margin(
                               params.get("snap", 0.001), params.get("relief_extension")), origin_xy),
                           step_m=float(params.get("step", 0.006)),
                           tol_m=float(params.get("relief_tol", 0.01)))
    check.pop("project_zero_fbx_z_m")  # #1821: the core's name says FBX; this check reads back the OBJ only
    rep["project_zero_check"] = {
        "checked_file": f"{prefix}.obj", "checked_format": "OBJ",
        "project_zero_m": check.pop("project_zero_m"), "zero_source": zero["source"],
        "project_zero_role": "supplied by the project (spec zero)",
        "obj_z_of_zero_m_assumed": obj_zero_z,
        "obj_z_of_zero_basis": "assumed by construction (Z local = mark - project zero), not measured in the OBJ",
        "fbx_z_of_zero": dict(gs.FBX_ZERO_NOT_MEASURED),
        "h_values_basis": "h_otn / h_abs derive from the OBJ readback with the assumed OBJ zero, not from an FBX",
        **check}
    expected = {f"M_{site}_Ground_{s}": [1000 + int(s[2:4])] for s in result.slots
                if f"M_{site}_Ground_{s}" in back["tiles"]}
    if back["tiles"] != expected:
        fails.append(f"readback UDIM tiles {back['tiles']} != ID tiles {expected}")
    if rep["project_zero_check"]["status"] != "pass":
        fails.append("project zero check: " + "; ".join(rep["project_zero_check"]["findings"]))
    status = 1 if gs.finalize_geometry(rep) else 0
    rep["passed"] = False
    (partial / "ground-report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1) + "\n",
                                                encoding="utf-8", newline="\n")
    if gs.sha256(spec_path) != spec_digest or gs.sha256(dxf) != digest:
        raise ValueError("spec or DXF changed during output readback; partial retained, nothing published")
    os.replace(partial, out_r)
    print(json.dumps({"out": str(out_r), "geometry_status": rep["geometry_status"],
                      "geometry_failures": rep["geometry_failures"], "advisories": rep["advisories"],
                      "findings": rep["findings"], "triangles": back["triangles"]}, ensure_ascii=False))
    return status


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args in (["--help"], ["-h"]) or len(args) != 2:
        print(__doc__)
        return 0 if args in (["--help"], ["-h"]) else 2
    try:
        return run(Path(args[0]), Path(args[1]))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
