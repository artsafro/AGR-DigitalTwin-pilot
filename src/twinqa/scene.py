"""FBX scene checks from a Blender readback (tools/blender/fbx_readback.py).

Fills the scene stages the header-only validator leaves not_run: V002 (units and scale;
units come from a pure-Python GlobalSettings read), V003 (triangulation,
triangle limits, object types), V004 (applied transforms, co-directional overlap clearance, regulatory topology defect count, MAF smoothing/flipped normals/dimensions (GroundEl)), V006 (NPM embedded images),
V008 (one UV channel, mirrored islands, glass tile), V010 (UCX presence, no material slots, triangle budget, intersections, intersection coverage, advisory gap; shape and coverage stay not_run),
V013 (origin, geometric-centre pivot, shared pivot). Triangle limits follow the 2026-10-07 decisions on conflicts #1 and #3.
Ground FBX: Flora checks from twinqa.flora (V015 dimensions, V005 maps, V003 Flora share; #191).
"""
import itertools
import math
import tempfile
from pathlib import Path

from dt_ai.core.blender_runner import blender_executable, run_blender
from twinqa.fbx_header import fbx_units
from twinqa.maf_checks import SMOOTHING_ANGLE_DEG, maf_findings
from twinqa.flora import FLORA_SHARE, flora_findings
from twinqa.geometry.ucx_audit import (
    BAND_TOL_M, GAP_BAND_M, NEIGHBOUR_M, bbox_gap, bounds, is_closed, is_convex,
    sat_separation, surface_distance, weld,
)
from twinqa.clearance import BAND_EDGE_TOL_M, co_directional_distribution, co_directional_pairs
from twinqa.report import Finding
from twinqa.naming import mesh_name_findings

READBACK = Path(__file__).resolve().parents[2] / "tools" / "blender" / "fbx_readback.py"
ANGLE_TOL_DEG, SCALE_TOL = 1e-3, 1e-4
METRE_UNIT_SCALE_CM = 100.0
UNIT_REL_TOL = 1e-6
UNIT_PAGES = [4, 24]
# Project target (user decision on conflict #1, 2026-10-07): one model serves VPM and NPM, so
# VPM OKS aims at the NPM limit; above it, windows go to atlas textures on planes.
PROJECT_TRIANGLE_TARGET = 150_000
PIVOT_CENTRE_TOL_PCT, PIVOT_SHARED_TOL_M = 10, 0.001  # SINTEZ AGR Checker 2.9.4a / 2.9.5
UCX_SMALL_MODEL, UCX_SMALL_LIMIT, UCX_SHARE, UCX_CAP = 50_000, 15_000, 0.05, 100_000
# float32 FBX coordinates near 100 m carry ~1e-5 m noise, same value as ucx_audit.BAND_TOL_M;
# it is numerical precision, not a permitted overlap.
OVERLAP_EPS_M = 1e-5
_DEGENERATE_VOLUME_M3 = 1e-9


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
        rb = run_blender(READBACK, [str(fbx_path), str(out)], executable=blender,
                         output_json=out, timeout=timeout)
    try:
        data = Path(fbx_path).read_bytes()
    except OSError as exc:
        rb["fbx_units"] = {"unit_scale_factor": None, "original_unit_scale_factor": None, "error": str(exc)}
    else:
        rb["fbx_units"] = fbx_units(data)
    return rb


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


def _enclosed_volume(verts, tris) -> float:
    """Absolute enclosed volume (m^3) from the signed tetrahedron sum over triangles."""
    total = 0.0
    for ia, ib, ic in tris:
        a, b, c = verts[ia], verts[ib], verts[ic]
        total += a[0] * (b[1] * c[2] - b[2] * c[1])
        total -= a[1] * (b[0] * c[2] - b[2] * c[0])
        total += a[2] * (b[0] * c[1] - b[1] * c[0])
    return abs(total) / 6.0


def _ucx_piece(mesh: dict) -> dict:
    """One UCX mesh as a welded hull plus an unsupported reason, or reason None when SAT is valid.

    Supported iff the hull has verts and tris and, after weld, is closed, convex and
    non-degenerate (absolute enclosed volume > 1e-9 m^3). A flat hull that collapses to a
    convex zero-volume shell is degenerate; an opened box still has a non-zero tetrahedron sum.
    """
    hull = mesh.get("hull") or {}
    verts, tris = hull.get("verts") or (), hull.get("tris") or ()
    if not verts or not tris:
        return {"name": mesh["name"], "hull": None, "reason": "no hull"}
    welded = weld(verts, tris)
    wv, wt = welded
    if not wt or not is_closed(wt):
        collapsed = bool(wt) and is_convex(wv, wt) and _enclosed_volume(wv, wt) <= _DEGENERATE_VOLUME_M3
        reason = "degenerate" if collapsed else "open"
    elif not is_convex(wv, wt):
        reason = "non-convex"
    elif _enclosed_volume(wv, wt) <= _DEGENERATE_VOLUME_M3:
        reason = "degenerate"
    else:
        reason = None
    return {"name": mesh["name"], "hull": welded, "reason": reason}


def _neighbour_gap_kind(gap_m: float) -> str:
    """touch / below_band / in_band / wide / apart for a supported pair that does not overlap.

    apart: surface gap > NEIGHBOUR_M although the bounding boxes are within it (e.g. rotated hulls);
    such a pair is not a neighbour and is not reported."""
    if gap_m <= OVERLAP_EPS_M:
        return "touch"
    if gap_m < GAP_BAND_M[0] - BAND_TOL_M:
        return "below_band"
    if gap_m <= GAP_BAND_M[1] + BAND_TOL_M:
        return "in_band"
    if gap_m <= NEIGHBOUR_M:
        return "wide"
    return "apart"


def _unsupported_labels(pairs: list[tuple[dict, dict]]) -> list[str]:
    labels, seen = [], set()
    for left, right in pairs:
        for piece in (left, right):
            if piece["reason"] and piece["name"] not in seen:
                seen.add(piece["name"])
                labels.append(f"{piece['name']} ({piece['reason']})")
    return labels


def _ucx_pair_findings(ucx: list[dict], src: str) -> list[Finding]:
    """Intersection (fail), coverage of that check, and the advisory neighbour gap (never fail). [D098]

    SAT runs only on closed convex non-degenerate hulls. A pair overlaps iff separation
    < -OVERLAP_EPS_M. A missing or unsupported hull does not erase a proven overlap.
    """
    pieces = [_ucx_piece(mesh) for mesh in ucx]
    inter_expected = "no two UCX pieces intersect (reg p.36 §13.4)"
    coverage_expected = ("every neighbour pair evaluated: closed convex non-degenerate hulls (SAT) "
                         "or bounding boxes apart")
    gap_expected = "neighbour gap 2 mm - 1 cm inclusive [D098] (advisory, never a failure)"
    if pieces and all(piece["reason"] == "no hull" for piece in pieces):
        observed = f"{src}: readback without UCX hull data: {[piece['name'] for piece in pieces]}"
        return [_f("not_run", "UCX intersections", observed, inter_expected, [36], src),
                _f("not_run", "UCX intersections coverage", observed, coverage_expected, [36], src),
                _f("not_run", "UCX piece gap (advisory)", observed, gap_expected, [36], src, [15])]
    overlaps, unresolved, offending, gap_unmeasured = [], [], [], 0
    counts = {"touch": 0, "below_band": 0, "in_band": 0, "wide": 0}
    for left, right in itertools.combinations(pieces, 2):
        both_hulls = left["hull"] is not None and right["hull"] is not None
        box_gap = bbox_gap(bounds(left["hull"][0]), bounds(right["hull"][0])) if both_hulls else None
        if both_hulls and box_gap > NEIGHBOUR_M:
            continue
        if left["reason"] or right["reason"]:
            if not both_hulls or box_gap <= OVERLAP_EPS_M:
                unresolved.append((left, right))
            else:
                gap_unmeasured += 1  # no intersection (boxes apart), but the surface gap is not measured
            continue
        separation = sat_separation(left["hull"], right["hull"])
        if separation < -OVERLAP_EPS_M:
            overlaps.append((left["name"], right["name"], round(-separation * 1000, 1)))
            continue
        gap_m = surface_distance(left["hull"], right["hull"]) if separation > OVERLAP_EPS_M else 0.0
        kind = _neighbour_gap_kind(gap_m)
        if kind == "apart":
            continue
        counts[kind] += 1
        if kind != "in_band":
            offending.append((left["name"], right["name"], round(gap_m * 1000, 2)))
    n_unresolved = len(unresolved)
    if overlaps:
        inter = _f("fail", "UCX intersections",
                   f"{src}: {len(overlaps)} overlapping pair(s): {overlaps[:5]}; unresolved pairs: {n_unresolved}",
                   inter_expected, [36], src)
    elif n_unresolved:
        inter = _f("not_run", "UCX intersections", f"{src}: {n_unresolved} unresolved pair(s)",
                   inter_expected, [36], src)
    else:
        inter = _f("pass", "UCX intersections", f"{src}: no overlapping pairs among {len(pieces)} pieces",
                   inter_expected, [36], src)
    if n_unresolved:
        coverage = _f("not_run", "UCX intersections coverage",
                      f"{src}: {n_unresolved} unresolved pair(s); unsupported: {_unsupported_labels(unresolved)[:10]}",
                      coverage_expected, [36], src)
    else:
        coverage = _f("pass", "UCX intersections coverage", f"{src}: every neighbour pair evaluated",
                      coverage_expected, [36], src)
    bad = counts["touch"] or counts["below_band"] or counts["wide"]
    gap_obs = (f"{src}: touch={counts['touch']} below_band={counts['below_band']} "
               f"in_band={counts['in_band']} wide={counts['wide']} unmeasured={n_unresolved + gap_unmeasured}; "
               f"{offending[:5]}")
    gap_status = "review" if bad else "not_run" if n_unresolved or gap_unmeasured else "pass"
    return [inter, coverage, _f(gap_status, "UCX piece gap (advisory)", gap_obs, gap_expected, [36], src, [15])]


def _topology_finding(meshes: list[dict], profile: dict, src: str) -> Finding:
    """Regulatory defect ceiling for every mesh, UCX included (reg p.8 §3.7, p.29 §3.11)."""
    limit = profile["geometry"].get("duplicate_or_self_intersection_count_max", 100)
    tol = float(profile["geometry"].get("geometric_error_tolerance_m", 0.002))
    expected = (f"<= {limit} duplicates/self-intersections at {tol} m per mesh; "
                "0 isolated vertices/edges/polygons; 0 zero-length edges")
    blocked = []
    for mesh in meshes:
        topo = mesh.get("topology")
        if not isinstance(topo, dict):
            blocked.append(f"{mesh['name']} (no topology)")
        elif "error" in topo:
            blocked.append(f"{mesh['name']} ({topo['error']})")
        else:
            got = topo.get("tol_m")
            try:
                differs = abs(float(got) - tol) > 1e-12
            except (TypeError, ValueError):
                differs = True
            if differs:
                blocked.append(f"{mesh['name']} (tol_m {got})")
    if blocked:
        return _f("not_run", "topology defects", f"{src}: {blocked[:5]}", expected, [8, 29], src)
    offenders = []
    max_dup = 0
    element_keys = ("isolated_vertices", "isolated_edges", "isolated_polygons", "zero_length_edges")
    for mesh in meshes:
        topo = mesh["topology"]
        dup = int(topo["duplicates_and_self_intersections"])
        max_dup = max(max_dup, dup)
        nonzero = []
        if dup > 0:
            nonzero.append(f"duplicates_and_self_intersections={dup}")
        for key in element_keys:
            count = int(topo[key])
            if count > 0:
                nonzero.append(f"{key}={count}")
        if dup > limit or any(int(topo[key]) > 0 for key in element_keys):
            offenders.append(f"{mesh['name']} ({', '.join(nonzero)})")
    if offenders:
        return _f("fail", "topology defects", f"{src}: {offenders[:5]}", expected, [8, 29], src)
    return _f("pass", "topology defects",
              f"{src}: max {max_dup} duplicates/self-intersections, no isolated or zero-length elements",
              expected, [8, 29], src)


def _scale_not_one(values) -> bool:
    return any(abs(s - 1) > SCALE_TOL for s in values)


def _fmt_scale(values) -> str:
    parts = []
    for value in values:
        parts.append(f"{value:g}" if isinstance(value, float) else str(value))
    return "[" + ",".join(parts) + "]"


def _v002_scale_bad(mesh: dict) -> bool:
    """Local scale, or effective world scale when the readback recorded it (else local)."""
    local = mesh["scale"]
    world = mesh["world_scale"] if "world_scale" in mesh else local
    return _scale_not_one(local) or _scale_not_one(world)


def _v002_scale_text(mesh: dict) -> str:
    text = f"{mesh['name']} local {_fmt_scale(mesh['scale'])}"
    if "world_scale" in mesh:
        text += f" world {_fmt_scale(mesh['world_scale'])}"
    return f"{text} parent {mesh.get('parent')}"


def _v002_findings(rb: dict, meshes: list[dict], src: str) -> list[Finding]:
    """1 unit = 1 m (UnitScaleFactor 100 cm) and local and effective (inherited) scale 1 on every mesh, UCX included."""
    expected_units = "1 unit = 1 m (UnitScaleFactor 100)"
    if "fbx_units" not in rb:
        units = _f("not_run", "system units", "units not read", expected_units, UNIT_PAGES, src)
    else:
        info = rb.get("fbx_units") or {}
        usf = info.get("unit_scale_factor")
        ousf = info.get("original_unit_scale_factor")
        if usf is None:
            units = _f("fail", "system units", f"{src}: {info.get('error') or 'UnitScaleFactor not declared'}",
                       expected_units, UNIT_PAGES, src)
        else:
            ok = abs(usf - METRE_UNIT_SCALE_CM) <= METRE_UNIT_SCALE_CM * UNIT_REL_TOL
            observed = (f"{src}: 1 unit = {usf:g} cm "
                        f"(UnitScaleFactor {usf:g}, OriginalUnitScaleFactor {ousf})")
            units = _f("pass" if ok else "fail", "system units", observed, expected_units, UNIT_PAGES, src)
    bad = [m for m in meshes if _v002_scale_bad(m)]
    expected_scale = "local and effective (inherited) scale 1 on every mesh (1:1)"
    if bad:
        shown = ", ".join(_v002_scale_text(m) for m in bad[:5])
        scale = _f("fail", "scale 1:1", f"{src}: {shown}", expected_scale, UNIT_PAGES, src)
    else:
        scale = _f("pass", "scale 1:1", f"{src}: scale 1 on every mesh", expected_scale, UNIT_PAGES, src)
    return [units, scale]


def scene_findings(rb: dict, kind: str, role: str, profile: dict, flora_schedule: dict | None = None,
                   flora_share: int = FLORA_SHARE, *, maf_sizes=None, smoothing_angle_deg=None) -> dict[str, list[Finding]]:
    """role: 'oks' | 'ground' | 'light'. Returns {stage_id: findings}. Ground FBX: Flora checks
    (twinqa.flora; flora_schedule = {mesh name: {"height_m", "crown_m"}}, flora_share default 70 000)."""
    src = Path(rb["source"]).name
    out = {"V003": [], "V004": [], "V008": [], "V010": [], "V013": [], "V006": [], "V002": []}
    if not rb.get("readback_ok"):
        out["V003"].append(_f("fail", "FBX readback", rb.get("error", "no meshes"), "importable FBX with meshes", [4, 24], src))
        return out
    meshes = rb["meshes"]
    ucx = [m for m in meshes if m["name"].upper().startswith("UCX_")]
    out["V002"].extend(_v002_findings(rb, meshes, src))
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
    out["V004"].append(_topology_finding(meshes, profile, src))
    angle = SMOOTHING_ANGLE_DEG if smoothing_angle_deg is None else smoothing_angle_deg
    out["V004"].extend(maf_findings(meshes, role, src, smoothing_angle_deg=angle, maf_sizes=maf_sizes))
    if role != "light":
        out["V004"].append(_clearance_finding(meshes, ucx, src, profile))

    if kind == "vpm" and role != "light":
        # V010: own UCX in each non-lighting geometry FBX (reg p.36 §13.3), no material slots on UCX
        # (reg p.36 §13.1; an empty slot is still a slot), triangle budget; shape, coverage and offsets
        # need other checks (reg p.34-37)
        out["V010"].append(_f("pass" if ucx else "fail", "UCX present", f"{src}: {len(ucx)} UCX mesh(es)",
                              "own UCX_ collision in each non-lighting geometry FBX", [36], src))
        if ucx:
            slotted = {m["name"]: m["materials"] for m in ucx if m.get("materials")}
            unknown = [m["name"] for m in ucx if "materials" not in m]
            status = "fail" if slotted else "not_run" if unknown else "pass"
            observed = slotted or (f"slots not in readback: {unknown[:5]}" if unknown else "no slots")
            out["V010"].append(_f(status, "UCX material slots", f"{src}: {observed}",
                                  "no material slots on UCX meshes", [36], src))
            ucx_tris, budget = sum(m["triangles"] for m in ucx), ucx_triangle_limit(tris)
            out["V010"].append(_f("fail" if ucx_tris > budget else "pass", "UCX triangle budget",
                                  f"{src}: {ucx_tris} UCX for {tris} model triangles", f"<= {budget}", [36, 37], src))
            out["V010"].extend(_ucx_pair_findings(ucx, src))
            out["V010"].append(_f("not_run", "UCX shape and coverage", "convex, closed, coverage, offsets",
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
    if role == "ground":  # Flora checks (#191): dimensions V015, maps V005, Flora share V003
        geometry = [m for m in meshes if m not in ucx]
        for stage_id, findings in flora_findings(rb, kind, geometry, tris, profile, flora_schedule, flora_share).items():
            out.setdefault(stage_id, []).extend(findings)

    # V012: internal mesh names and UCX index grammar (reg p.11-12 §3.3, p.33-34 §4.2) -> twinqa.naming
    out["V012"] = mesh_name_findings([m["name"] for m in meshes], kind, role, Path(rb["source"]).stem,
                                     profile["naming"]["max_characters"], src)
    return out
