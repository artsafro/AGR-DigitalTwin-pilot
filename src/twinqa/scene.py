"""FBX scene checks from a Blender readback (tools/blender/fbx_readback.py).

Fills the scene stages the header-only validator leaves not_run: V003 (triangulation,
triangle limits, object types), V004 (applied transforms, co-directional overlap clearance), V006 (NPM embedded images),
V008 (one UV channel, mirrored islands, glass tile), V010 (UCX triangle budget only),
V013 (origin, geometric-centre pivot, shared pivot). Triangle limits follow the 2026-10-07 decisions on conflicts #1 and #3.
"""
import math
import tempfile
from pathlib import Path

from dt_ai.core.blender_runner import blender_executable, run_blender
from twinqa.clearance import BAND_EDGE_TOL_M, co_directional_distribution, co_directional_pairs
from twinqa.report import Finding

READBACK = Path(__file__).resolve().parents[2] / "tools" / "blender" / "fbx_readback.py"
ANGLE_TOL_DEG, SCALE_TOL = 1e-3, 1e-4
# Project target (user decision on conflict #1, 2026-10-07): one model serves VPM and NPM, so
# VPM OKS aims at the NPM limit; above it, windows go to atlas textures on planes.
PROJECT_TRIANGLE_TARGET = 150_000
PIVOT_CENTRE_TOL_PCT, PIVOT_SHARED_TOL_M = 10, 0.001  # SINTEZ AGR Checker 2.9.4a / 2.9.5
UCX_SMALL_MODEL, UCX_SMALL_LIMIT, UCX_SHARE, UCX_CAP = 50_000, 15_000, 0.05, 100_000


def ucx_triangle_limit(model_triangles: int) -> int:
    """UCX budget (reg p.36-37 §13.7-13.8) as SINTEZ AGR Checker v1.6.1 (conflict #3, decided):
    < 50 000 -> 15 000; else ceil(5 %) capped at 100 000."""
    if model_triangles < UCX_SMALL_MODEL:
        return UCX_SMALL_LIMIT
    return min(math.ceil(model_triangles * UCX_SHARE), UCX_CAP)


def find_blender() -> str | None:
    """Compatibility discovery: configured executable or the pinned installation only."""
    executable = blender_executable()
    return executable if Path(executable).is_file() else None


def readback(fbx_path: Path, blender: str | None = None, timeout: int = 600) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "readback.json"
        return run_blender(READBACK, [str(fbx_path), str(out)], executable=blender,
                           output_json=out, timeout=timeout)


def _f(status, name, observed, expected, pages, evidence, conflicts=()):
    return Finding(name, status, observed, expected, list(pages), evidence, list(conflicts))


def _pivot_findings(meshes: list[dict], ucx: list[dict], src: str) -> list[Finding]:
    """Main mesh origin at FBX zero; its bbox centre within 10 % of the X/Y size from the origin;
    every non-UCX mesh shares that origin within 1 mm (UCX origins are not regulated)."""
    geometry = [m for m in meshes if m not in ucx]
    main = next((m for m in geometry if m["name"].endswith("_Main")), geometry[0] if geometry else None)
    if main is None:
        return []
    out = []
    loc = main["location"]
    at_zero = max(abs(c) for c in loc) <= PIVOT_SHARED_TOL_M
    out.append(_f("pass" if at_zero else "fail", "origin at FBX zero", f"{src}: {main['name']} at {[round(c, 3) for c in loc]}",
                  "local origin (0, 0, 0)", [32, 33], src))
    if main.get("bounds_m"):
        lo, hi = main["bounds_m"]
        offsets = []
        for i in (0, 1):
            size = hi[i] - lo[i]
            offsets.append(None if size == 0 else round(abs((lo[i] + hi[i]) / 2 - loc[i]) / size * 100, 2))
        bad = any(o is not None and o > PIVOT_CENTRE_TOL_PCT for o in offsets)
        out.append(_f("fail" if bad else "pass", "pivot at geometric centre", f"{src}: X/Y offset {offsets} %",
                      f"<= {PIVOT_CENTRE_TOL_PCT} % of the size", [32, 33], src))
    shifted = [m["name"] for m in geometry
               if sum((a - b) ** 2 for a, b in zip(m["location"], loc)) ** 0.5 > PIVOT_SHARED_TOL_M]
    out.append(_f("fail" if shifted else "pass", "shared pivot", f"{src}: {shifted[:5] or 'all meshes'}",
                  "every mesh shares the Main origin within 1 mm (UCX exempt)", [32, 33], src))
    return out


def _mm_text(value) -> str:
    if value is None:
        return "None"
    return f"{value:.4f}".rstrip("0").rstrip(".")


def _clearance_finding(meshes: list[dict], ucx: list[dict], src: str, profile: dict) -> Finding:
    """One V004 co-directional clearance finding for every non-light readback."""
    band = profile["geometry"]["near_coplanar_spacing_m"]
    band_min, band_max = float(band["min"]), float(band["max"])
    min_mm, max_mm = band_min * 1000, band_max * 1000
    expected = (f"co-directional overlapping faces {min_mm:g}-{max_mm:g} mm apart "
                f"(pairs beyond {max_mm:g} mm: review)")
    geometry = [mesh for mesh in meshes if mesh not in ucx]
    if any("face_geometry" not in mesh for mesh in geometry):
        return _f("not_run", "co-directional clearance", f"{src}: no face geometry in readback",
                  expected, [8, 29], src, [30])
    faces = []
    for mesh in geometry:
        shape = mesh["face_geometry"]
        vertices = shape["vertices"]
        for index, polygon in enumerate(shape["polygons"]):
            points = [vertices[vertex] for vertex in polygon]
            if len(points) >= 3:
                faces.append({"object": mesh["name"], "index": index, "points": points})
    pairs = co_directional_pairs(faces)
    distribution = co_directional_distribution(pairs, band_min, band_max)
    if distribution["below_band"]:
        status = "fail"
    elif distribution["above_band"]:
        status = "review"
    else:
        status = "pass"
    out_of_band = []  # (below band, deviation, label): below-band (fail) first, then largest deviation
    for pair in pairs:
        distance = pair["distance_m"]
        deviation = max(band_min - distance, distance - band_max)
        if deviation > BAND_EDGE_TOL_M:
            out_of_band.append((distance < band_min, deviation, f"{pair['a'][0]}#{pair['a'][1]}/{pair['b'][0]}#{pair['b'][1]} "
                                           f"d={distance * 1000:.1f} mm"))
    out_of_band.sort(key=lambda item: (not item[0], -item[1]))
    worst = [label for _, _, label in out_of_band]
    observed = (f"{src}: {distribution['pairs']} co-directional overlapping pairs: "
                f"{distribution['below_band']} < {min_mm:g} mm, {distribution['in_band']} in band, "
                f"{distribution['above_band']} > {max_mm:g} mm; "
                f"distance mm min/median/max {_mm_text(distribution['min_mm'])}/"
                f"{_mm_text(distribution['median_mm'])}/{_mm_text(distribution['max_mm'])}; "
                f"histogram {distribution['histogram_mm']}; worst: {worst[:5]}")
    return _f(status, "co-directional clearance", observed, expected, [8, 29], src, [30])


def scene_findings(rb: dict, kind: str, role: str, profile: dict) -> dict[str, list[Finding]]:
    """role: 'oks' | 'ground' | 'light'. Returns {stage_id: findings}."""
    src = Path(rb["source"]).name
    out = {"V003": [], "V004": [], "V008": [], "V010": [], "V013": [], "V006": []}
    if not rb.get("readback_ok"):
        out["V003"].append(_f("fail", "FBX readback", rb.get("error", "no meshes"), "importable FBX with meshes", [4, 24], src))
        return out
    meshes = rb["meshes"]
    ucx = [m for m in meshes if m["name"].upper().startswith("UCX_")]
    tris = sum(m["triangles"] for m in meshes if m not in ucx)  # collision is excluded (reg p.28 §3.9)

    # V003: triangulated on export, triangle limits, no foreign objects (reg p.6-8, 28-29)
    not_tri = [m["name"] for m in meshes if set(m["polygon_degrees"]) != {"3"}]
    out["V003"].append(_f("fail" if not_tri else "pass", "triangulated", f"{src}: {not_tri or 'all triangles'}",
                          "triangulated on export", [7, 28], src))
    if role != "light":
        if kind == "npm":
            limit = profile["geometry"]["ground_triangles_total_max" if role == "ground" else "oks_triangles_per_fbx_max"]
            status, conflicts = ("fail" if tris > limit else "pass"), []
        else:
            if role == "ground":
                status, limit, conflicts = "review", "by site area (reg p.29 table)", []
            else:
                hard = profile["geometry"]["oks_triangles_per_fbx_max_excluding_collision"]
                status = "fail" if tris > hard else "review" if tris > PROJECT_TRIANGLE_TARGET else "pass"
                limit = (f"{PROJECT_TRIANGLE_TARGET} project target (reuse as NPM; else windows as atlas planes), "
                         f"{hard} regulation limit")
                conflicts = []
        out["V003"].append(_f(status, "triangle count", f"{src}: {tris}", f"<= {limit}", [7, 28, 29], src, conflicts))
    foreign = [o for o in rb["other_objects"] if not (role == "light" and o["type"] in ("LIGHT", "EMPTY"))]
    if foreign:
        # Any non-mesh object, lights included, fails (conflict #14 decided 2026-10-07 as the checker)
        out["V003"].append(_f("fail", "object types", f"{src}: {[(o['name'], o['type']) for o in foreign][:5]}",
                              "meshes only (lights only in the _Light FBX)", [4, 24, 33], src))

    # V004: transforms applied, rotation 0 (reg p.8, 29, 32-33)
    bad = [m["name"] for m in meshes
           if any(abs(a) > ANGLE_TOL_DEG for a in m["rotation_euler_deg"]) or any(abs(s - 1) > SCALE_TOL for s in m["scale"])]
    out["V004"].append(_f("fail" if bad else "pass", "applied transforms", f"{src}: {bad or 'rotation 0, scale 1'}",
                          "rotation 0, scale 1 after reset", [8, 29, 33], src))
    if role != "light":
        out["V004"].append(_clearance_finding(meshes, ucx, src, profile))

    if kind == "vpm" and role != "light":
        # V010: UCX triangle budget only; shape, coverage and offsets need other checks (reg p.34-37)
        if ucx:
            ucx_tris, budget = sum(m["triangles"] for m in ucx), ucx_triangle_limit(tris)
            out["V010"].append(_f("fail" if ucx_tris > budget else "pass", "UCX triangle budget",
                                  f"{src}: {ucx_tris} UCX for {tris} model triangles", f"<= {budget}", [36, 37], src))
            out["V010"].append(_f("not_run", "UCX shape and coverage", "convex, closed, no intersections, coverage, offsets",
                                  "reg p.34-37", [34, 36, 37], src))
        # V008: one UV channel, no mirrored islands, glass only in 1001 (reg p.31-32, 39)
        multi = [m["name"] for m in meshes if m["uv_channels"] != 1]
        mirrored = {m["name"]: m["mirrored_uv_triangles"] for m in meshes if m["mirrored_uv_triangles"]}
        glass = {m["name"]: m["udim_tiles"] for m in meshes if m["name"].endswith("MainGlass") and m["udim_tiles"] != [1001]}
        out["V008"].append(_f("fail" if multi else "pass", "one UV channel", f"{src}: {multi or 'all meshes'}", "1 UV channel", [31], src))
        out["V008"].append(_f("fail" if mirrored else "pass", "mirrored islands", f"{src}: {mirrored or 'none'}", "no mirrored UV", [31], src))
        if glass:
            out["V008"].append(_f("fail", "glass tile", f"{src}: {glass}", "glass only in UDIM 1001", [31, 32], src))
        # V013 (reg p.32-33 §9.3-9.5; conflict #19 decided 2026-10-07 as the checker)
        out["V013"].extend(_pivot_findings(meshes, ucx, src))
        out["V013"].append(_f("not_run", "MSK-77 point", "GeoJSON point vs survey coordinates and project zero",
                              "reg p.32-33, p.55", [32, 33, 55], src))

    if kind == "npm":
        # V006: textures embedded in the FBX (reg p.9 §5.1); pixel rules need the PNG bytes
        loose = [i["name"] for i in rb.get("images", []) if not i["packed"]]
        out["V006"].append(_f("fail" if loose else "pass", "embedded textures", f"{src}: {loose or 'all embedded'}",
                              "PNG embedded in FBX", [9], src))
    return out
