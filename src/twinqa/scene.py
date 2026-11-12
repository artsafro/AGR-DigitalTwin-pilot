"""FBX scene checks from a Blender readback (tools/blender/fbx_readback.py).

Fills the scene stages the header-only validator leaves not_run: V002 (units and scale;
units come from a pure-Python GlobalSettings read), V003 (triangulation,
triangle limits, object types), V004 (applied transforms, co-directional overlap clearance, regulatory topology defect count, MAF smoothing/flipped normals/dimensions (GroundEl)), V006 (NPM embedded images),
V008 (one UV channel, mirrored islands, glass tile), V009 (texel density from UV and the diffuse side per tile),
V005 (color attributes, reg 4.1.1, review only),
V012 (VPM OKS MainGlass object and glass material names), V010 (UCX presence, no material slots, triangle budget, intersections, intersection coverage, advisory gap, piece shape closed/convex; coverage and offsets stay not_run),
V013 (origin, geometric-centre pivot, shared pivot). Triangle limits follow the 2026-10-07 decisions on conflicts #1 and #3.
Ground FBX: Flora checks from twinqa.flora (V015 dimensions, V005 maps, V003 Flora share; #191).
"""
import itertools
import math
import os
import re
import tempfile
import uuid
from fractions import Fraction
from pathlib import Path

from dt_ai.core.blender_runner import blender_executable, run_blender
from twinqa.fbx_header import fbx_application, fbx_units
from twinqa.maf_checks import SMOOTHING_ANGLE_DEG, maf_findings
from twinqa.flora import FLORA_SHARE, flora_findings
from twinqa.geometry.ucx_audit import (
    BAND_TOL_M, GAP_BAND_M, NEIGHBOUR_M, bbox_gap, bounds, is_closed, is_convex,
    sat_separation, surface_distance, weld,
)
from twinqa.clearance import BAND_EDGE_TOL_M, co_directional_distribution, co_directional_pairs
from twinqa.report import Finding, signed_margin
from twinqa.naming import mesh_name_findings
from twinqa.uv import DENSITY_MAX_PX_PER_M, DENSITY_MIN_PX_PER_M, _density_finding, edge_densities, udim_of

READBACK = Path(__file__).resolve().parents[2] / "tools" / "blender" / "fbx_readback.py"
ANGLE_TOL_DEG, SCALE_TOL = 1e-3, 1e-4
METRE_UNIT_SCALE_CM = 100.0
UNIT_REL_TOL = 1e-6
UNIT_PAGES = [4, 24]
# Project target (user decision on conflict #1, 2026-10-07 [D010]): one model serves VPM and NPM, so
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


def readback_log_dir() -> Path:
    """Blender logs of the readback: TWINQA_LOG_DIR, else the system temp folder; never the caller's cwd
    (team audit T04: run_blender's default `<cwd>/logs/blender` littered the repository a check ran from)."""
    return Path(os.environ.get("TWINQA_LOG_DIR") or Path(tempfile.gettempdir()) / "twinqa" / "blender_logs")


def readback(fbx_path: Path, blender: str | None = None, timeout: int = 600) -> dict:
    log = readback_log_dir() / f"readback-{uuid.uuid4().hex}.log"
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "readback.json"
        rb = run_blender(READBACK, [str(fbx_path), str(out)], executable=blender,
                         output_json=out, timeout=timeout, log_path=log)
    try:
        data = Path(fbx_path).read_bytes()
    except OSError as exc:
        rb["fbx_units"] = {"unit_scale_factor": None, "original_unit_scale_factor": None, "error": str(exc)}
        rb["fbx_application"] = None
    else:
        rb["fbx_units"] = fbx_units(data)
        rb["fbx_application"] = fbx_application(data)
    return rb


def _f(status, name, observed, expected, pages, evidence, conflicts=(), data=None, *,
      measured=None, threshold=None, margin=None):
    return Finding(name, status, observed, expected, list(pages), evidence, list(conflicts),
                   measured, threshold, margin, dict(data or {}))


GROUND_TABLE_KEY = "ground_triangles_max_by_area_ha"
GROUND_AREA_TOL_M2 = 0.25
"""Absolute tolerance in m2 for the Ground footprint checks.

The top-down area check passes only when ``|measured - ground_area_m2|`` is strictly
below this value, so a difference of exactly 0.25 m2 fails closed. The footprint-hole
check uses the same constant: top-down coverage inside the hole polygon(s) passes
only when it is strictly below this value. A 0.5 m2 net excess fails on the 3431.50 m2
Vatutino fixture. A 0.5 m2 coverage of the hole fails even when the net area is unchanged.
"""


def _finite_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def check_ground_area(value) -> float:
    """Fail closed: the Ground area operand must be a finite number > 0 (m2), never bool/str/NaN/inf."""
    if not _finite_number(value) or value <= 0:
        raise ValueError(f"ground_area_m2 must be a finite number > 0 (m2), got {value!r}")
    return value


def _ground_bands(profile: dict) -> list[dict]:
    """The VPM Ground table (reg p.28-29 §3.10) from the standard, checked: ascending finite `area_max`
    bands (upper edge inclusive) ending in one `area_above` band equal to the last `area_max`."""
    bands = profile.get("geometry", {}).get(GROUND_TABLE_KEY)
    if not isinstance(bands, list) or len(bands) < 2:
        raise ValueError(f"{GROUND_TABLE_KEY}: expected a list of >= 2 bands, got {bands!r}")
    previous = 0.0
    for i, band in enumerate(bands):
        last = i == len(bands) - 1
        edge_key = "area_above" if last else "area_max"
        if not isinstance(band, dict) or set(band) != {edge_key, "triangles_max"}:
            raise ValueError(f"{GROUND_TABLE_KEY}[{i}]: expected keys {{{edge_key}, triangles_max}}, got {band!r}")
        edge, limit = band[edge_key], band["triangles_max"]
        if not _finite_number(edge) or not (isinstance(limit, int) and not isinstance(limit, bool) and limit > 0):
            raise ValueError(f"{GROUND_TABLE_KEY}[{i}]: non-finite edge or non-positive triangles_max: {band!r}")
        if last and edge != previous:
            raise ValueError(f"{GROUND_TABLE_KEY}[{i}]: area_above {edge} != last area_max {previous}")
        if not last and edge <= previous:
            raise ValueError(f"{GROUND_TABLE_KEY}[{i}]: area_max {edge} not above {previous}")
        previous = edge
    return bands


def ground_triangle_limit(profile: dict, ground_area_m2) -> tuple[int, dict]:
    """VPM Ground triangle limit for (site area - OKS footprint) in m2 (reg p.28-29 §3.10, [D010]).
    Bands come from VPM_STANDARD.yaml; the upper edge of each band is inclusive (500 m2 -> 300 000).
    Non-finite, non-positive or non-numeric area raises ValueError naming `ground_area_m2`."""
    check_ground_area(ground_area_m2)
    bands = _ground_bands(profile)
    # Exact rational comparison in m2: a float ha quotient rounds 500.00000000000006 m2 down to 0.05 ha
    # and would pick the lower band; the YAML edge is read as its decimal text (0.05 ha == 500 m2 exactly).
    area = Fraction(ground_area_m2)
    for band in bands[:-1]:
        if area <= Fraction(str(band["area_max"])) * 10_000:
            return band["triangles_max"], band
    return bands[-1]["triangles_max"], bands[-1]


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
    malformed = []
    for mesh in geometry:
        shape = mesh["face_geometry"]
        vertices = shape["vertices"]
        for index, polygon in enumerate(shape["polygons"]):
            label = f"{mesh['name']}#{index}"
            if isinstance(polygon, (str, bytes)) or not isinstance(polygon, (list, tuple)):
                malformed.append(f"{label}: polygon is not an index list")
                continue
            try:
                if any(isinstance(v, bool) or not isinstance(v, int) or v < 0 for v in polygon):
                    raise IndexError("negative or non-integer index")
                points = [vertices[vertex] for vertex in polygon]
            except (IndexError, TypeError, KeyError):
                malformed.append(f"{label}: vertex index out of range")
                continue
            if not all(isinstance(point, (list, tuple)) and len(point) >= 3 for point in points):
                malformed.append(f"{label}: vertex without X/Y/Z")
                continue
            if len(points) >= 3:
                faces.append({"object": mesh["name"], "index": index, "points": points})
    if malformed:
        return _f("fail", "co-directional clearance",
                  f"{src}: malformed face geometry, {len(malformed)} face(s) cannot be measured: "
                  f"{malformed[:5]}", expected, [8, 29], src, [30])
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
    return _f(status, "co-directional clearance", observed, expected, [8, 29], src, [30],
              measured=distribution["measured"], threshold=distribution["threshold"],
              margin=distribution["margin"])


def _enclosed_volume(verts, tris) -> float:
    """Absolute enclosed volume (m^3) from the signed tetrahedron sum over triangles.

    Vertices are shifted by the first vertex before the sum. Signed volume is
    translation-invariant; the local frame avoids cancellation when the hull sits far
    from the global origin (same sum as ucx_audit._enclosed_volume, kept as a copy).
    """
    if not verts:
        return 0.0
    origin = verts[0]
    total = 0.0
    for ia, ib, ic in tris:
        a = (verts[ia][0] - origin[0], verts[ia][1] - origin[1], verts[ia][2] - origin[2])
        b = (verts[ib][0] - origin[0], verts[ib][1] - origin[1], verts[ib][2] - origin[2])
        c = (verts[ic][0] - origin[0], verts[ic][1] - origin[1], verts[ic][2] - origin[2])
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


def _from_max(rb: dict) -> bool:
    """FBX written by 3ds Max (SceneInfo ApplicationName, twinqa.fbx_header.fbx_application)."""
    return "3ds max" in str(rb.get("fbx_application") or "").lower()


def _identity_transform(rotation_deg, scale) -> bool:
    return (all(abs(a) <= ANGLE_TOL_DEG for a in rotation_deg)
            and all(abs(s - 1) <= SCALE_TOL for s in scale))


def _ucx_shape_finding(ucx: list[dict], src: str) -> Finding:
    """V010 'UCX shape': every UCX piece closed, convex, non-degenerate (reg p.34-36). Team audit T04 (P14): open and
    concave UCX stayed not_run. A readback without hull data stays not_run, never a pass."""
    pieces = [_ucx_piece(mesh) for mesh in ucx]
    bad = {p["name"]: p["reason"] for p in pieces if p["reason"] not in (None, "no hull")}
    unread = [p["name"] for p in pieces if p["reason"] == "no hull"]
    expected = "closed, convex, non-degenerate UCX pieces"
    if bad:
        return _f("fail", "UCX shape", f"{src}: {bad}", expected, [34, 36], src)
    if unread:
        return _f("not_run", "UCX shape", f"{src}: readback without UCX hull data: {unread[:5]}", expected, [34, 36], src)
    return _f("pass", "UCX shape", f"{src}: {len(pieces)} closed convex piece(s)", expected, [34, 36], src)


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
    worst_gap = None  # (margin, measured_m, threshold_m); smallest safe-side margin wins
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
        worst_gap = _note_band_margin(worst_gap, gap_m, kind)
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
    if worst_gap is None:
        gap_measured = gap_threshold = gap_margin = None
    else:
        gap_margin, gap_measured, gap_threshold = worst_gap
    return [inter, coverage, _f(gap_status, "UCX piece gap (advisory)", gap_obs, gap_expected, [36], src, [15],
                                measured=gap_measured, threshold=gap_threshold, margin=gap_margin)]


def _note_band_margin(worst, gap_m, kind):
    """Smallest D098-band margin for one neighbour gap. Too-close itself is recorded on the audit finding."""
    if kind in ("touch", "below_band"):
        options = ((GAP_BAND_M[0], "min"),)
    elif kind == "wide":
        options = ((GAP_BAND_M[1], "max"),)
    elif kind == "in_band":
        options = ((GAP_BAND_M[0], "min"), (GAP_BAND_M[1], "max"))
    else:
        return worst
    for threshold, bound in options:
        margin = signed_margin(gap_m, threshold, bound)
        if margin is None:
            continue
        if worst is None or margin < worst[0]:
            worst = (margin, gap_m, threshold)
    return worst


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


_DIFFUSE_SOCKETS = ("Base Color", "Diffuse", "Diffuse Color")


def _square_side(size):
    """Positive square pixel side, or None when the size cannot be used as a texture side."""
    if not isinstance(size, (list, tuple)) or len(size) != 2:
        return None
    width, height = size
    if isinstance(width, bool) or isinstance(height, bool):
        return None
    if not isinstance(width, (int, float)) or not isinstance(height, (int, float)):
        return None
    if not math.isfinite(width) or not math.isfinite(height) or width != height or width <= 0:
        return None
    if float(width) != int(width):
        return None
    return int(width)


def _texture_side_px(rb: dict) -> int | None:
    """Diffuse side in px for rho = texture_side_px / polygon_length_m.

    VPM_STANDARD allows more than one square (2048 and 4096; the regulation also lists
    256, 512 and 1024) and the diffuse map is an external PNG, so the readback has no
    single production side. Use a side only when every diffuse image — or, when the
    readback has no material maps, every image — reports that same positive square size.
    Anything else stays None and the density findings are not_run, not a guessed number.
    """
    by_name = {}
    for image in rb.get("images") or []:
        if not isinstance(image, dict) or "name" not in image:
            return None
        by_name[image["name"]] = image.get("size")
    materials = rb.get("materials")
    if materials:
        sides = []
        for material in materials:
            if not isinstance(material, dict):
                return None
            for item in material.get("maps") or []:
                if not isinstance(item, dict) or item.get("socket") not in _DIFFUSE_SOCKETS:
                    continue
                side = _square_side(by_name.get(item.get("image")))
                if side is None:
                    return None
                sides.append(side)
        if len(set(sides)) != 1:
            return None
        return sides[0]
    sides = [_square_side(size) for size in by_name.values()]
    if not sides or any(side is None for side in sides) or len(set(sides)) != 1:
        return None
    return sides[0]


def _density_bounds(src: str, status: str, reason: str) -> list[Finding]:
    return [
        _f(status, "texel density", f"{src}: {reason}", f">= {DENSITY_MIN_PX_PER_M:g} px/m", [31, 32], src),
        _f(status, "texel density upper", f"{src}: {reason}", f"<= {DENSITY_MAX_PX_PER_M:g} px/m", [31, 32], src),
    ]


GLASS_SUFFIXES = ("MainGlass", "GroundGlass", "GroundElGlass")
_SLOT = re.compile(r"_(\d+)$")


def _tile_side(diffuse_px: dict, tile, material) -> int | None:
    """Diffuse side of one UDIM tile from the archive PNGs ({(slot, udim): side}).

    One side for the tile across all slots is used as is; otherwise the slot is read from the
    trailing `_N` of the material name (`M_{Address}_Main_N`, reg p.34 §10.4.4). None = unknown."""
    sides = {side for (_slot, udim), side in diffuse_px.items() if udim == tile}
    if len(sides) == 1:
        return next(iter(sides))
    hit = _SLOT.search(material or "")
    return diffuse_px.get((int(hit.group(1)), tile)) if hit else None


def _texel_density_findings(rb: dict, meshes: list[dict], ucx: list[dict], src: str,
                            diffuse_px: dict | None = None, placeholder_px: int | None = None) -> list[Finding]:
    """V009: min 512 px/m and max 1706 px/m for non-UCX meshes. Missing UV or texture size is not_run.

    diffuse_px ({(slot, udim): side} from the archive Diffuse PNGs) gives each polygon the side of its
    own tile; without it one diffuse size must come from the readback. Exempt (reg p.31-32 §6.1-6.2,
    2.6.2): placeholder tiles (placeholder_px) and glass meshes (*Glass: no texture maps, reg 2.4.2)."""
    geometry = [mesh for mesh in meshes if mesh not in ucx and not mesh["name"].endswith(GLASS_SUFFIXES)]
    if not geometry:
        return _density_bounds(src, "not_run", "no textured render mesh")
    if diffuse_px:
        return _tile_density_findings(geometry, src, diffuse_px, placeholder_px)
    side = _texture_side_px(rb)
    missing = [mesh["name"] for mesh in geometry if "uv" not in mesh.get("face_geometry", {})]
    if side is None or missing:
        reasons = []
        if side is None:
            reasons.append("diffuse texture size is not in the readback")
        if missing:
            reasons.append("no per-vertex UV in readback")
        return _density_bounds(src, "not_run", "; ".join(reasons))
    try:
        values = []
        for mesh in geometry:
            shape = mesh["face_geometry"]
            vertices, uvs = shape["vertices"], shape["uv"]
            polygons = shape.get("polygons")
            if not isinstance(polygons, list):
                raise ValueError(f"partial UV geometry on {mesh['name']}: polygons")
            polygon_uvs = shape.get("polygon_uv")
            use_corner_uv = polygon_uvs is not None
            if use_corner_uv and (not isinstance(polygon_uvs, list) or len(polygon_uvs) != len(polygons)):
                count = len(polygon_uvs) if isinstance(polygon_uvs, list) else None
                raise ValueError(
                    f"partial UV geometry on {mesh['name']}: {count} polygon_uv for {len(polygons)} polygons")
            if not use_corner_uv and len(uvs) != len(vertices):
                raise ValueError(
                    f"partial UV geometry on {mesh['name']}: {len(uvs)} uv for {len(vertices)} vertices")
            for poly_index, polygon in enumerate(polygons):
                try:
                    poly_xyz = [vertices[index] for index in polygon]
                    poly_uv = polygon_uvs[poly_index] if use_corner_uv else [uvs[index] for index in polygon]
                except (IndexError, TypeError) as exc:
                    raise ValueError(f"partial UV geometry on {mesh['name']}: polygon index") from exc
                if len(poly_xyz) < 2:
                    continue
                values.extend(edge_densities(poly_xyz, poly_uv, side))
    except ValueError as exc:
        return _density_bounds(src, "fail", str(exc))
    if not values:
        return [
            _density_finding("texel density", None, DENSITY_MIN_PX_PER_M, "min", f"{src}: no edges", src),
            _density_finding("texel density upper", None, DENSITY_MAX_PX_PER_M, "max", f"{src}: no edges", src),
        ]
    low, high = min(values), max(values)
    return [
        _density_finding("texel density", low, DENSITY_MIN_PX_PER_M, "min", f"{src}: min {low:.6g} px/m", src),
        _density_finding("texel density upper", high, DENSITY_MAX_PX_PER_M, "max", f"{src}: max {high:.6g} px/m", src),
    ]


def _tile_density_findings(geometry: list[dict], src: str, diffuse_px: dict,
                           placeholder_px: int | None) -> list[Finding]:
    """Per-polygon edge densities with the diffuse side of the polygon's own UDIM tile."""
    low = high = None
    low_at = high_at = ""
    exempt, unknown = 0, {}
    try:
        for mesh in geometry:
            shape = mesh.get("face_geometry") or {}
            vertices, polygons = shape.get("vertices"), shape.get("polygons")
            polygon_uvs = shape.get("polygon_uv")
            materials = shape.get("polygon_material") or []
            if not isinstance(polygons, list) or not isinstance(polygon_uvs, list) \
                    or len(polygon_uvs) != len(polygons):
                raise ValueError(f"partial UV geometry on {mesh['name']}: no polygon_uv per polygon")
            for index, (polygon, poly_uv) in enumerate(zip(polygons, polygon_uvs)):
                try:
                    poly_xyz = [vertices[i] for i in polygon]
                except (IndexError, TypeError) as exc:
                    raise ValueError(f"partial UV geometry on {mesh['name']}: polygon index") from exc
                if len(poly_xyz) < 2:
                    continue
                tile = udim_of(poly_uv)
                material = materials[index] if index < len(materials) else None
                side = _tile_side(diffuse_px, tile, material)
                if side is None:
                    unknown.setdefault(mesh["name"], set()).add(tile)
                    continue
                if placeholder_px is not None and side == placeholder_px:
                    exempt += 1
                    continue
                values = edge_densities(poly_xyz, poly_uv, side)
                if values and (low is None or min(values) < low):
                    low, low_at = min(values), f"{mesh['name']} polygon {index}, tile {tile}"
                if values and (high is None or max(values) > high):
                    high, high_at = max(values), f"{mesh['name']} polygon {index}, tile {tile}"
    except ValueError as exc:
        return _density_bounds(src, "fail", str(exc))
    note = f"; {exempt} placeholder polygon(s) exempt" if exempt else ""
    if low is None and exempt and not unknown:
        return _density_bounds(src, "pass", f"all {exempt} polygon(s) on placeholder tiles (exempt)")
    out = [
        _density_finding("texel density", low, DENSITY_MIN_PX_PER_M, "min",
                         f"{src}: min {low:.6g} px/m at {low_at}{note}" if low is not None else f"{src}: no edges", src),
        _density_finding("texel density upper", high, DENSITY_MAX_PX_PER_M, "max",
                         f"{src}: max {high:.6g} px/m at {high_at}" if high is not None else f"{src}: no edges", src),
    ]
    if unknown:
        shown = {name: sorted(t for t in tiles if t is not None) or ["outside grid"] for name, tiles in unknown.items()}
        out.append(_f("not_run", "texel density coverage", f"{src}: no Diffuse PNG for tiles {shown}",
                      "a Diffuse map for every textured tile", [31, 32], src))
    return out


def _m2_text(value: float) -> str:
    return f"{value:.6f}".rstrip("0").rstrip(".")


def _ground_xy_rings(geometry: list[dict]) -> list[list[tuple[float, float]]]:
    """XY rings of render-mesh faces. Empty geometry raises ValueError('empty face geometry').

    A polygon with fewer than 3 indices, a negative index, an out-of-range index,
    a vertex with fewer than 3 components, and a non-finite coordinate each raise
    ValueError naming that problem. Unsupported structure does too.
    """
    rings = []
    for mesh in geometry:
        shape = mesh["face_geometry"]
        vertices, polygons = shape.get("vertices"), shape.get("polygons")
        if not isinstance(vertices, (list, tuple)) or not isinstance(polygons, (list, tuple)):
            raise ValueError(f"unsupported face geometry on {mesh['name']}")
        for polygon in polygons:
            if isinstance(polygon, (str, bytes)) or not isinstance(polygon, (list, tuple)):
                raise ValueError(f"unsupported polygon on {mesh['name']}")
            if len(polygon) < 3:
                raise ValueError(f"polygon with fewer than 3 indices on {mesh['name']}")
            ring = []
            for index in polygon:
                if isinstance(index, bool) or not isinstance(index, int):
                    raise ValueError(f"unsupported polygon index on {mesh['name']}")
                if index < 0:
                    raise ValueError(f"negative face index on {mesh['name']}")
                if index >= len(vertices):
                    raise ValueError(f"out-of-range face index on {mesh['name']}")
                try:
                    point = vertices[index]
                except (IndexError, TypeError) as exc:
                    raise ValueError(f"out-of-range face index on {mesh['name']}") from exc
                if isinstance(point, (str, bytes)) or not isinstance(point, (list, tuple)) or len(point) < 2:
                    raise ValueError(f"unsupported vertex on {mesh['name']}")
                if len(point) < 3:
                    raise ValueError(f"vertex missing Z on {mesh['name']}")
                coords = (point[0], point[1], point[2])
                if any(isinstance(coord, bool) or not isinstance(coord, (int, float)) or not math.isfinite(coord)
                       for coord in coords):
                    raise ValueError(f"non-finite coordinate on {mesh['name']}")
                ring.append((float(point[0]), float(point[1])))
            if len(ring) >= 3:
                rings.append(ring)
    if not rings:
        raise ValueError("empty face geometry")
    return rings


def _projected_union(rings: list[list[tuple[float, float]]]):
    """XY union of face rings. Stacked coverings count once. An empty union has area 0."""
    import shapely

    parts = []
    for ring in rings:
        polygon = shapely.Polygon(ring)
        if not polygon.is_valid:
            polygon = shapely.make_valid(polygon)
        if polygon.is_empty or polygon.area <= 0.0:
            continue
        parts.append(polygon)
    if not parts:
        return shapely.Polygon()
    try:
        return shapely.union_all(parts)
    except shapely.errors.GEOSException as exc:
        raise ValueError(f"unsupported face geometry: {exc}") from exc


def _topdown_area_m2(rings: list[list[tuple[float, float]]]) -> float:
    """Union area of the XY projections. Stacked coverings count once."""
    area = float(_projected_union(rings).area)
    if not math.isfinite(area):
        raise ValueError("non-finite projected area")
    return area


def _parse_footprint_holes(footprint_holes):
    """Shapely geometries for the absence rings. Raises ValueError naming a bad reference."""
    import shapely

    if isinstance(footprint_holes, (str, bytes)) or not isinstance(footprint_holes, (list, tuple)):
        raise ValueError("footprint hole reference is not a list of rings")
    if len(footprint_holes) == 0:
        raise ValueError("footprint hole reference is empty")
    polygons = []
    for ring in footprint_holes:
        if isinstance(ring, (str, bytes)) or not isinstance(ring, (list, tuple)) or len(ring) < 3:
            raise ValueError("footprint hole ring has fewer than 3 points")
        coords = []
        for point in ring:
            if isinstance(point, (str, bytes)) or not isinstance(point, (list, tuple)) or len(point) < 2:
                raise ValueError("footprint hole point is not an XY coordinate")
            x, y = point[0], point[1]
            if any(isinstance(coord, bool) or not isinstance(coord, (int, float)) or not math.isfinite(coord)
                   for coord in (x, y)):
                raise ValueError("non-finite footprint hole coordinate")
            coords.append((float(x), float(y)))
        polygon = shapely.Polygon(coords)
        if not polygon.is_valid:
            polygon = shapely.make_valid(polygon)
        if polygon.is_empty or not math.isfinite(polygon.area) or polygon.area <= 0.0:
            raise ValueError("footprint hole ring has no area")
        polygons.append(polygon)
    return polygons


def _hole_coverage_m2(rings: list[list[tuple[float, float]]], holes) -> float:
    """Top-down area of the Ground union that lies inside the footprint-hole union."""
    import shapely

    ground = _projected_union(rings)
    try:
        covered = ground.intersection(shapely.union_all(holes))
    except shapely.errors.GEOSException as exc:
        raise ValueError(f"unsupported face geometry: {exc}") from exc
    area = float(covered.area)
    if not math.isfinite(area):
        raise ValueError("non-finite hole coverage")
    return area


def _ground_face_presence(geometry: list[dict]) -> tuple[str, str] | None:
    """``None`` when every mesh has a face_geometry dict. Otherwise ``(status, reason)``."""
    missing = [mesh for mesh in geometry if not isinstance(mesh.get("face_geometry"), dict)]
    if not geometry or len(missing) == len(geometry):
        return "not_run", "no face geometry in readback"
    if missing:
        return "fail", "partial face geometry"
    return None


def _ground_area_finding(geometry: list[dict], src: str, ground_area_m2) -> Finding:
    """Scalar top-down area against ``ground_area_m2``.

    Pass only when the absolute difference is strictly below ``GROUND_AREA_TOL_M2``.
    This comparison does not locate the OKS footprint. Missing ``ground_area_m2``,
    or a readback with no face geometry, is ``not_run`` and never a pass. Empty,
    partial, negative, short, out-of-range and non-finite face data fail.
    """
    name = "ground footprint coverage"
    expected = f"|top-down area - ground_area_m2| < {GROUND_AREA_TOL_M2} m2"
    pages = [28, 29]
    presence = _ground_face_presence(geometry)
    if presence is not None and presence[0] == "not_run":
        return _f("not_run", name, f"{src}: {presence[1]}", expected, pages, src,
                  data={"measured_m2": None, "expected_m2": ground_area_m2, "difference_m2": None})
    if presence is not None:
        return _f("fail", name, f"{src}: {presence[1]}", expected, pages, src,
                  data={"measured_m2": None, "expected_m2": ground_area_m2, "difference_m2": None})
    try:
        measured = _topdown_area_m2(_ground_xy_rings(geometry))
    except ValueError as exc:
        reason = str(exc)
        data = {"measured_m2": None, "expected_m2": ground_area_m2, "difference_m2": None}
        if reason == "empty face geometry" and ground_area_m2 is not None:
            measured = 0.0
            difference = measured - ground_area_m2
            data = {"measured_m2": measured, "expected_m2": ground_area_m2, "difference_m2": difference}
            reason = (f"empty face geometry; measured {_m2_text(measured)} m2, "
                      f"expected {_m2_text(ground_area_m2)} m2, difference {_m2_text(difference)} m2")
        return _f("fail", name, f"{src}: {reason}", expected, pages, src, data=data)
    if ground_area_m2 is None:
        return _f("not_run", name, f"{src}: ground_area_m2 missing", expected, pages, src,
                  data={"measured_m2": measured, "expected_m2": None, "difference_m2": None})
    difference = measured - ground_area_m2
    if not math.isfinite(difference):
        return _f("fail", name, f"{src}: non-finite difference", expected, pages, src,
                  data={"measured_m2": measured, "expected_m2": ground_area_m2, "difference_m2": None})
    data = {"measured_m2": measured, "expected_m2": ground_area_m2, "difference_m2": difference}
    status = "pass" if abs(difference) < GROUND_AREA_TOL_M2 else "fail"
    margin = (GROUND_AREA_TOL_M2 - abs(difference)) / GROUND_AREA_TOL_M2
    observed = (f"{src}: measured {_m2_text(measured)} m2, expected {_m2_text(ground_area_m2)} m2, "
                f"difference {_m2_text(difference)} m2")
    return _f(status, name, observed, expected, pages, src, data=data,
              measured=measured, threshold=ground_area_m2, margin=margin)


def _ground_hole_finding(geometry: list[dict], src: str, footprint_holes) -> Finding:
    """Top-down coverage of Ground inside the footprint-hole polygons.

    Independent of the scalar area difference: coverage strictly below
    ``GROUND_AREA_TOL_M2`` passes, and coverage at or above it fails even when
    the same area was removed outside the hole. No hole reference, or a readback
    with no face geometry, is ``not_run`` and never a pass of the hole claim.
    """
    name = "ground footprint hole coverage"
    expected = f"top-down coverage inside the footprint hole < {GROUND_AREA_TOL_M2} m2"
    pages = [28, 29]
    data = {"hole_coverage_m2": None, "tolerance_m2": GROUND_AREA_TOL_M2}
    if footprint_holes is None:
        return _f("not_run", name, f"{src}: footprint hole reference missing", expected, pages, src, data=data)
    presence = _ground_face_presence(geometry)
    if presence is not None:
        return _f(presence[0], name, f"{src}: {presence[1]}", expected, pages, src, data=data)
    try:
        holes = _parse_footprint_holes(footprint_holes)
        coverage = _hole_coverage_m2(_ground_xy_rings(geometry), holes)
    except ValueError as exc:
        return _f("fail", name, f"{src}: {exc}", expected, pages, src, data=data)
    status = "pass" if coverage < GROUND_AREA_TOL_M2 else "fail"
    margin = (GROUND_AREA_TOL_M2 - coverage) / GROUND_AREA_TOL_M2
    observed = (f"{src}: hole coverage {_m2_text(coverage)} m2, "
                f"tolerance {_m2_text(GROUND_AREA_TOL_M2)} m2")
    return _f(status, name, observed, expected, pages, src,
              data={"hole_coverage_m2": coverage, "tolerance_m2": GROUND_AREA_TOL_M2},
              measured=coverage, threshold=GROUND_AREA_TOL_M2, margin=margin)


def check_ground_materials(value) -> list[str]:
    """Allow-list of Ground material names or fnmatch globs. Raises ValueError naming `ground_materials`
    for anything but a non-empty list of non-empty strings."""
    if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple)) or not value:
        raise ValueError(f"ground_materials must be a non-empty list of material names or globs, got {value!r}")
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"ground_materials entry must be a non-empty string, got {item!r}")
    return list(value)


def _select_ground_faces(geometry: list[dict], ground_materials: list[str]) -> tuple[list[dict], dict]:
    """Keep only polygons whose material matches the allow-list (exact name or fnmatch glob, case-sensitive).

    Meshes without a face_geometry dict pass through unchanged so the presence check still reports them.
    A mesh whose ``polygon_material`` is missing or not one entry per polygon raises ValueError: a filter
    that cannot read materials must never pass. Returns the filtered meshes and a report of the drop.
    """
    from fnmatch import fnmatchcase

    selected, excluded, kept, excluded_materials, readable = [], 0, 0, {}, False
    for mesh in geometry:
        shape = mesh.get("face_geometry")
        if not isinstance(shape, dict):
            selected.append(mesh)
            continue
        readable = True
        polygons, materials = shape.get("polygons"), shape.get("polygon_material")
        if not isinstance(polygons, (list, tuple)) or not isinstance(materials, (list, tuple)) \
                or len(materials) != len(polygons):
            raise ValueError(f"--ground-materials needs one polygon_material per polygon on {mesh['name']}")
        keep = []
        for polygon, material in zip(polygons, materials):
            if isinstance(material, str) and any(fnmatchcase(material, pattern) for pattern in ground_materials):
                keep.append(polygon)
            else:
                excluded += 1
                excluded_materials[str(material)] = excluded_materials.get(str(material), 0) + 1
        kept += len(keep)
        if keep:
            selected.append({**mesh, "face_geometry": {**shape, "polygons": keep}})
    if readable and kept == 0:
        raise ValueError(f"no faces match --ground-materials {ground_materials}")
    return selected, {"ground_materials": list(ground_materials), "excluded_faces": excluded,
                      "excluded_materials": dict(sorted(excluded_materials.items()))}


def _filter_note(report: dict) -> str:
    names = ", ".join(report["excluded_materials"]) or "none"
    return (f"; filter --ground-materials {report['ground_materials']}: "
            f"{report['excluded_faces']} face(s) excluded ({names})")


def _with_filter(finding: Finding, report: dict) -> Finding:
    finding.observed += _filter_note(report)
    finding.data = {**(finding.data or {}), **report}
    return finding


def _ground_footprint_findings(meshes: list[dict], ucx: list[dict], src: str, ground_area_m2,
                               footprint_holes, ground_materials=None) -> list[Finding]:
    """Scalar area check, then the spatial hole check. UCX meshes are excluded from both.

    ground_materials (opt-in): only faces whose material matches feed both checks; None keeps every
    non-UCX render face (unchanged behaviour). An allow-list that matches no face fails both."""
    geometry = [mesh for mesh in meshes if mesh not in ucx]
    if ground_materials is None:
        return [
            _ground_area_finding(geometry, src, ground_area_m2),
            _ground_hole_finding(geometry, src, footprint_holes),
        ]
    try:
        geometry, report = _select_ground_faces(geometry, ground_materials)
    except ValueError as exc:
        data = {"ground_materials": list(ground_materials), "excluded_faces": None}
        area = _f("fail", "ground footprint coverage", f"{src}: {exc}",
                  f"|top-down area - ground_area_m2| < {GROUND_AREA_TOL_M2} m2", [28, 29], src,
                  data={"measured_m2": None, "expected_m2": ground_area_m2, "difference_m2": None, **data})
        hole = _ground_hole_finding([], src, footprint_holes)
        if footprint_holes is not None:
            hole.status, hole.observed = "fail", f"{src}: {exc}"
        hole.data = {**(hole.data or {}), **data}
        return [area, hole]
    return [
        _with_filter(_ground_area_finding(geometry, src, ground_area_m2), report),
        _with_filter(_ground_hole_finding(geometry, src, footprint_holes), report),
    ]


SKIRT_MIN_M = 1.0  # GND-03: Ground perimeter polygons extruded down by at least 1 m (reg p.7 §3.4, p.28 §3.7)
_SKIRT_XY_ROUND = 4  # XY rounding (0.1 mm): a perimeter edge shorter than this in XY is degenerate (GND-03)
_SKIRT_XY_TOL = 10.0 ** -_SKIRT_XY_ROUND  # XY distance (0.1 mm) within which a mesh edge lies on a perimeter edge
# GND-03: minimum upward normal ratio (nz/|n|) for a Ground face to count as "surface". A skirt wall
# is vertical (nz ~ 0), but the v015 readback has 13 _Skirt faces that are not quite vertical: their
# nz/|n| runs up to 0.0054 (a ~0.3 deg build slant, not pure float noise). eps sits above that so the
# geometry alone keeps the skirt walls out, and far below the steepest real surface band (nz/|n| ~ 0.148
# at 81.5 deg) so interior step bands stay in. The material guard (below) is a second, naming-independent
# backstop for any skirt face tilted past eps.
_SKIRT_UP_EPS = 0.01


def _polygon_normal(verts: list, poly) -> tuple[float, float, float]:
    """Newell normal (unnormalised) of a polygon; ``(0, 0, 0)`` for a degenerate polygon."""
    nx = ny = nz = 0.0
    n = len(poly)
    for k in range(n):
        a = verts[poly[k]]
        b = verts[poly[(k + 1) % n]]
        nx += (a[1] - b[1]) * (a[2] + b[2])
        ny += (a[2] - b[2]) * (a[0] + b[0])
        nz += (a[0] - b[0]) * (a[1] + b[1])
    return nx, ny, nz


def _xy_key(x, y) -> tuple[float, float]:
    return round(float(x), _SKIRT_XY_ROUND), round(float(y), _SKIRT_XY_ROUND)


def _skirt_cells(x0: float, y0: float, x1: float, y1: float, cell: float) -> set[tuple[int, int]]:
    """Grid cells of samples spaced <= ``cell / 2`` along an XY segment (every point of the
    segment lies within ``cell / 4`` of a sample, so two segments sharing a point have samples
    at most two cells apart per axis)."""
    steps = int(math.ceil(math.hypot(x1 - x0, y1 - y0) / (cell / 2.0))) or 1
    return {(math.floor((x0 + (x1 - x0) * m / steps) / cell), math.floor((y0 + (y1 - y0) * m / steps) / cell))
            for m in range(steps + 1)}


def _skirt_edge_drop(vi, vj, segs) -> float:
    """Smallest skirt drop along the perimeter edge ``vi``-``vj`` (GND-03, #1133 case 1).

    At every point of the edge's XY segment the drop is the top Z minus the lowest Z of the mesh
    edges that cover that point collinearly in XY (within ``_SKIRT_XY_TOL``); the edge itself
    covers it at drop 0, so an uncovered stretch gives 0. Between breakpoints (ends of covering
    edges) the drop is the upper envelope of linear functions, so its minimum is at a piece end
    or at a crossing of two of those lines: those are the points evaluated, nothing is sampled.
    """
    x0, y0, z0 = float(vi[0]), float(vi[1]), float(vi[2])
    dx, dy, dz = float(vj[0]) - x0, float(vj[1]) - y0, float(vj[2]) - z0
    l2 = dx * dx + dy * dy
    length = math.sqrt(l2)
    eps = _SKIRT_XY_TOL / length
    lines = [(0.0, 1.0, 0.0, 0.0)]  # (t_lo, t_hi, drop at t=0, drop slope): the edge itself
    for ax, ay, az, bx, by, bz in segs:
        if abs((ax - x0) * dy - (ay - y0) * dx) / length > _SKIRT_XY_TOL:
            continue
        if abs((bx - x0) * dy - (by - y0) * dx) / length > _SKIRT_XY_TOL:
            continue
        ta = ((ax - x0) * dx + (ay - y0) * dy) / l2
        tb = ((bx - x0) * dx + (by - y0) * dy) / l2
        lo, hi = max(min(ta, tb), 0.0), min(max(ta, tb), 1.0)
        if hi - lo <= eps or tb == ta:
            continue
        slope = (bz - az) / (tb - ta)  # segment Z(t) = az + slope * (t - ta)
        lines.append((lo, hi, z0 - (az - slope * ta), dz - slope))
    cuts = sorted({0.0, 1.0, *(t for ln in lines for t in ln[:2])})
    best = math.inf
    for t0, t1 in zip(cuts, cuts[1:]):
        if t1 - t0 <= eps:
            continue
        cover = [(c, m) for lo, hi, c, m in lines if lo <= t0 + eps and hi >= t1 - eps]
        points = [t0, t1]
        for k, (c1, m1) in enumerate(cover):
            for c2, m2 in cover[k + 1:]:
                if m1 != m2:
                    t = (c2 - c1) / (m1 - m2)
                    if t0 < t < t1:
                        points.append(t)
        for t in points:
            drop = max(c + m * t for c, m in cover)
            if drop < best:
                best = drop
    return best if math.isfinite(best) else 0.0


_RING_TURN_EPS = 1e-9  # rad: outgoing directions closer than this at a shared vertex are ambiguous


def _boundary_rings(verts: list, boundary: list[tuple[int, int]]) -> list[list[tuple[int, int]]] | None:
    """Split directed boundary edges into simple closed rings, or ``None`` when ambiguous (#1224).

    Every vertex must have as many outgoing as incoming boundary edges (else non-manifold ->
    ``None``). At a vertex shared by several rings (a pinch, or a hole touching the outer ring)
    the edge after an incoming one is the first outgoing edge clockwise from the reversed incoming
    direction in XY: the planar-face walk, which keeps the surface on the left and never crosses
    rings. A face walk can still pass a shared vertex twice (a hole touching the outer ring is
    one walk), so each walk is cut at every repeated vertex into simple rings, which the caller
    classifies by signed area. Zero-length or coinciding outgoing directions -> ``None``.
    """
    out: dict[int, list[int]] = {}
    in_deg: dict[int, int] = {}
    for a, b in boundary:
        out.setdefault(a, []).append(b)
        in_deg[b] = in_deg.get(b, 0) + 1
    if set(out) != set(in_deg) or any(len(out[v]) != in_deg[v] for v in out):
        return None

    def direction(v: int, w: int) -> float | None:
        dx, dy = verts[w][0] - verts[v][0], verts[w][1] - verts[v][1]
        return math.atan2(dy, dx) if (dx or dy) else None

    nxt: dict[tuple[int, int], tuple[int, int]] = {}
    for p, v in boundary:
        choices = out[v]
        if len(choices) == 1:
            nxt[(p, v)] = (v, choices[0])
            continue
        back = direction(v, p)
        if back is None:
            return None
        turns = []
        for w in choices:
            ang = direction(v, w)
            if ang is None:
                return None
            cw = (back - ang) % (2 * math.pi)
            if cw <= _RING_TURN_EPS or cw >= 2 * math.pi - _RING_TURN_EPS:
                return None  # leaves along the incoming edge: overlapping boundary
            turns.append((cw, w))
        turns.sort()
        if turns[1][0] - turns[0][0] <= _RING_TURN_EPS:
            return None
        nxt[(p, v)] = (v, turns[0][1])
    if len(set(nxt.values())) != len(nxt):
        return None  # two incoming edges claim the same outgoing edge: not a planar boundary

    rings: list[list[tuple[int, int]]] = []
    seen: set[tuple[int, int]] = set()
    for first in boundary:
        if first in seen:
            continue
        walk = []
        e = first
        while e not in seen:
            seen.add(e)
            walk.append(e)
            e = nxt[e]
        if e != first:
            return None
        # Cut the closed walk at every repeated vertex into simple rings.
        stack: list[tuple[int, int]] = []
        pos = {first[0]: 0}
        for a, b in walk:
            stack.append((a, b))
            if b in pos:
                i = pos[b]
                rings.append(stack[i:])
                for x, _ in stack[i + 1:]:
                    pos.pop(x, None)
                del stack[i:]
            else:
                pos[b] = len(stack)
        if stack:
            return None
    return rings


def _skirt_perimeter_drop(mesh: dict) -> tuple[str, float | None] | None:
    """``(status, depth)`` of the Ground perimeter skirt (GND-03), or ``None`` when unmeasurable.

    ``status`` is ``"fail"`` for broken (empty/partial/non-finite) face data, ``"unmeasurable"``
    when the mesh has no upward-facing surface or no surface perimeter to measure, and ``"ok"``
    when the perimeter drop was measured. The skirt extrudes the Ground surface's perimeter
    straight down. Only outer boundary rings of every component count as perimeter; inner holes
    (including building cut-outs) are excluded [D251]; rings sharing a welded vertex are split there
    by ``_boundary_rings`` (#1224). Under every outer edge the mesh must carry
    edges at least ``SKIRT_MIN_M`` lower that lie on the same XY segment, either one copy per
    perimeter edge or one bottom edge spanning several collinear perimeter edges (#1133 case 1).
    The drop is measured per perimeter edge
    (top Z vs the lowest Z under the same XY segment), never at the convex-hull corners alone: a skirt on
    two sides of a quad leaves the two other perimeter edges uncovered, which a corner-only
    measure cannot see. The measured depth is the smallest drop over all perimeter edges; a
    sloped surface with relief but no skirt fails (each perimeter edge has no lower copy -> drop
    0), and the total Z-extent is deliberately NOT the measure (it passes relief with no skirt).
    """
    shape = mesh.get("face_geometry")
    if not isinstance(shape, dict):
        return None
    verts = shape.get("vertices")
    polys = shape.get("polygons")
    if not isinstance(verts, list) or not verts:
        return "fail", 0.0
    if not isinstance(polys, list) or not polys:
        return "fail", 0.0
    for v in verts:
        if isinstance(v, bool) or not isinstance(v, (list, tuple)) or len(v) < 3:
            return "fail", 0.0
        if any(isinstance(c, bool) or not isinstance(c, (int, float)) or not math.isfinite(c) for c in v[:3]):
            return "fail", 0.0
    for poly in polys:
        if not isinstance(poly, (list, tuple)) or len(poly) < 3:
            return "fail", 0.0
        for idx in poly:
            if isinstance(idx, bool) or not isinstance(idx, int) or idx < 0 or idx >= len(verts):
                return "fail", 0.0

    # upward-facing surface polygons: the Ground top whose perimeter the skirt must extrude. A face is
    # surface when its normal has an upward component above the skirt-tilt tolerance (nz > eps*|n|) and
    # its material is not a skirt wall (*_Skirt). Interior step bands are steep (75-81.5 deg, nz/|n| ~
    # 0.15-0.26) but still surface: dropping them turns their rim into a false "perimeter" with no lower
    # copy (drop 0). Skirt walls are near-vertical (nz ~ 0) or *_Skirt, so both tests keep them out.
    materials = shape.get("polygon_material")
    if materials is not None and (not isinstance(materials, list) or len(materials) != len(polys)):
        return "fail", 0.0
    top = []
    for idx, p in enumerate(polys):
        nx, ny, nz = _polygon_normal(verts, p)
        if nz <= _SKIRT_UP_EPS * math.hypot(nx, ny, nz):
            continue
        if materials is not None and str(materials[idx]).endswith("_Skirt"):
            continue
        top.append(p)
    if not top:
        return "unmeasurable", None

    # Upward-facing surface polygons orient outer boundaries CCW in XY and holes CW.
    # [D251]: only outer rings need skirts, including every disconnected component.
    # Classify each directed ring, not by global containment/size (an island inside a
    # different component's hole is still an outer boundary of its own component).
    edge_count: dict[tuple[int, int], int] = {}
    directed: dict[tuple[int, int], tuple[int, int]] = {}
    for p in top:
        n = len(p)
        for k in range(n):
            a, b = p[k], p[(k + 1) % n]
            key = (a, b) if a < b else (b, a)
            edge_count[key] = edge_count.get(key, 0) + 1
            directed[key] = (a, b)
    boundary = [directed[e] for e, c in edge_count.items() if c == 1]
    if not boundary:
        return "unmeasurable", None
    rings = _boundary_rings(verts, boundary)
    if rings is None:
        return "fail", 0.0
    perimeter = []
    for ring in rings:
        start = ring[0][0]
        # Translate before shoelace accumulation to avoid cancellation at map coordinates.
        x0, y0 = verts[start][:2]
        area2 = math.fsum((verts[i][0] - x0) * (verts[j][1] - y0)
                          - (verts[j][0] - x0) * (verts[i][1] - y0) for i, j in ring)
        if not math.isfinite(area2) or area2 == 0:
            return "fail", 0.0
        if area2 > 0:
            perimeter.extend(ring)
    if not perimeter:
        return "fail", 0.0

    # every mesh edge with an XY extent (vertical edges have none), on a uniform XY grid; the skirt
    # bottom lies under the perimeter XY but may span several collinear perimeter edges (#1133)
    segs: list[tuple[float, float, float, float, float, float]] = []
    seen: set[tuple[int, int]] = set()
    total = 0.0
    for p in polys:
        n = len(p)
        for k in range(n):
            a, b = p[k], p[(k + 1) % n]
            key = (a, b) if a < b else (b, a)
            if key in seen:
                continue
            seen.add(key)
            va, vb = verts[a], verts[b]
            length = math.hypot(float(vb[0]) - float(va[0]), float(vb[1]) - float(va[1]))
            if length <= _SKIRT_XY_TOL:
                continue  # vertical edge: zero XY length, not a perimeter copy
            segs.append((float(va[0]), float(va[1]), float(va[2]), float(vb[0]), float(vb[1]), float(vb[2])))
            total += length
    cell = max(total / len(segs), 100 * _SKIRT_XY_TOL) if segs else 1.0
    grid: dict[tuple[int, int], list[int]] = {}
    for s, seg in enumerate(segs):
        for c in _skirt_cells(seg[0], seg[1], seg[3], seg[4], cell):
            grid.setdefault(c, []).append(s)

    best = math.inf
    for i, j in perimeter:
        vi, vj = verts[i], verts[j]
        if _xy_key(vi[0], vi[1]) == _xy_key(vj[0], vj[1]):
            drop = 0.0  # degenerate perimeter edge: no downward skirt
        else:
            near: set[int] = set()
            for cx, cy in _skirt_cells(float(vi[0]), float(vi[1]), float(vj[0]), float(vj[1]), cell):
                for ox in range(-2, 3):
                    for oy in range(-2, 3):
                        near.update(grid.get((cx + ox, cy + oy), ()))
            drop = _skirt_edge_drop(vi, vj, [segs[s] for s in near])
        if drop < 0.0:
            drop = 0.0
        if drop < best:
            best = drop
    if not math.isfinite(best):
        return "fail", 0.0
    return "ok", best


def _ground_skirt_finding(meshes: list[dict], ucx: list[dict], src: str) -> Finding:
    """GND-03: every Ground surface's perimeter is extruded down >= 1 m (reg p.7 §3.4, p.28 §3.7)."""
    name = "ground skirt depth"
    expected = f"perimeter polygons extruded down >= {SKIRT_MIN_M:g} m [GND-03] (reg p.7 §3.4, p.28 §3.7)"
    pages = [7, 28]
    geometry = [mesh for mesh in meshes if mesh not in ucx]
    ground = [m for m in geometry if m["name"].endswith("_Ground")]
    if not ground:
        return _f("not_run", name, f"{src}: no Ground surface mesh", expected, pages, src)
    broken: list[str] = []
    unmeasurable: list[str] = []
    ok: list[tuple[str, float]] = []
    for mesh in ground:
        probe = _skirt_perimeter_drop(mesh)
        if probe is None:
            unmeasurable.append(mesh["name"])
        elif probe[0] == "fail":
            broken.append(mesh["name"])
        elif probe[0] == "unmeasurable":
            unmeasurable.append(mesh["name"])
        else:
            depth = probe[1]
            assert depth is not None, "ok status must carry a numeric depth"
            ok.append((mesh["name"], depth))
    if broken:
        shown = ", ".join(broken[:5])
        return _f("fail", name, f"{src}: broken face geometry: {shown}", expected, pages, src)
    failing = sorted((n, d) for n, d in ok if d < SKIRT_MIN_M)
    if failing:
        worst_n, worst_d = failing[0]
        tail = f" (and {len(failing) - 1} more)" if len(failing) > 1 else ""
        return _f("fail", name, f"{src}: {worst_n} perimeter drop {worst_d:.3f} m{tail}",
                  expected, pages, src, measured=worst_d, threshold=SKIRT_MIN_M,
                  margin=signed_margin(worst_d, SKIRT_MIN_M, "min"))
    if unmeasurable:
        shown = ", ".join(unmeasurable[:5])
        tail = f" (and {len(unmeasurable) - 1} more)" if len(unmeasurable) > 1 else ""
        return _f("not_run", name,
                  f"{src}: Ground mesh(es) without measurable face geometry: {shown}{tail}",
                  expected, pages, src)
    best = min(d for _, d in ok)
    return _f("pass", name, f"{src}: perimeter drop >= {SKIRT_MIN_M:g} m (min {best:.3f} m)",
              expected, pages, src, measured=best, threshold=SKIRT_MIN_M,
              margin=signed_margin(best, SKIRT_MIN_M, "min"))


_MAF_FLORA_SUFFIXES = ("_GroundEl", "_GroundElGlass", "_Flora")
MAF_FLORA_SINK_M = 0.1  # [D095]/[D100]: MAF and Flora sink 10 cm into the Ground; that band is exempt


def _maf_flora_triangles(mesh: dict) -> tuple[list, list] | tuple[None, str]:
    """``(verts, tris)`` of a MAF/Flora mesh fan-triangulated from ``face_geometry``.

    Returns ``(None, reason)`` when the mesh has no measurable face geometry, so the caller can
    report ``not_run`` naming the mesh instead of silently skipping it.
    """
    shape = mesh.get("face_geometry")
    if not isinstance(shape, dict):
        return None, "no face_geometry"
    verts = shape.get("vertices")
    polys = shape.get("polygons")
    if not isinstance(verts, list) or not verts:
        return None, "no vertices"
    if not isinstance(polys, list) or not polys:
        return None, "no polygons"
    for v in verts:
        if isinstance(v, bool) or not isinstance(v, (list, tuple)) or len(v) < 3:
            return None, "malformed vertices"
        if any(isinstance(c, bool) or not isinstance(c, (int, float)) or not math.isfinite(c) for c in v[:3]):
            return None, "non-finite vertices"
    tris = []
    for poly in polys:
        if not isinstance(poly, (list, tuple)) or len(poly) < 3:
            return None, "malformed polygons"
        for idx in poly:
            if isinstance(idx, bool) or not isinstance(idx, int) or idx < 0 or idx >= len(verts):
                return None, "invalid polygon indices"
        for k in range(1, len(poly) - 1):
            tris.append((poly[0], poly[k], poly[k + 1]))
    if not tris:
        return None, "no triangles"
    return [tuple(float(c) for c in v[:3]) for v in verts], tris


def _clip_tri_above(tri: list, band_z: float) -> list[list]:
    """Part of triangle ``tri`` (three xyz) at or above ``band_z``, as 0..2 triangles."""
    above = [i for i in range(3) if tri[i][2] >= band_z]
    if len(above) == 3:
        return [list(tri)]
    if not above:
        return []

    def cross(i, j):
        a, b = tri[i], tri[j]
        t = (band_z - a[2]) / (b[2] - a[2])
        return (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]), band_z)

    if len(above) == 1:
        i = above[0]
        others = [j for j in range(3) if j != i]
        return [[tri[i], cross(i, others[0]), cross(i, others[1])]]
    below = [j for j in range(3) if j not in above][0]
    a, b = [j for j in range(3) if j != below]
    return [[tri[a], cross(a, below), cross(b, below)], [tri[a], cross(b, below), tri[b]]]


def _point_in_closed_mesh(point, verts, tris) -> bool | None:
    """Exact ray parity, independent of face winding; None for ambiguous rays.

    Retry edge/vertex hits with different directions, never count a shared edge twice.
    Fractions preserve the supplied float coordinates without a scale-dependent epsilon.
    A point on the surface is not strict containment (touch remains exempt).
    """
    def sub(a, b):
        return tuple(x - y for x, y in zip(a, b))

    def dot(a, b):
        return sum(x * y for x, y in zip(a, b))

    def cross(a, b):
        return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2],
                a[0] * b[1] - a[1] * b[0])

    p = tuple(Fraction(c) for c in point)
    vv = [tuple(Fraction(c) for c in v) for v in verts]
    for direction in ((1, 0, 0), (0, 1, 0), (0, 0, 1), (1, 2, 3), (3, 1, 2)):
        hits, ambiguous = 0, False
        for i, j, k in tris:
            a, b, c = vv[i], vv[j], vv[k]
            e1, e2, s = sub(b, a), sub(c, a), sub(p, a)
            h = cross(direction, e2)
            det = dot(e1, h)
            if det == 0:
                # Coplanar rays cannot certify parity; another direction may.
                if dot(cross(e1, e2), s) == 0:
                    ambiguous = True
                    break
                continue
            u = dot(s, h) / det
            q = cross(s, e1)
            v = dot(direction, q) / det
            t = dot(e2, q) / det
            if u < 0 or v < 0 or u + v > 1 or t < 0:
                continue
            if t == 0:
                return False
            if u == 0 or v == 0 or u + v == 1:
                ambiguous = True
                break
            hits += 1
        if not ambiguous:
            return hits % 2 == 1
    return None


def _hull_intersects_mesh_above(hull, verts: list, tris: list, band_z: float) -> bool | None:
    """True if the convex ``hull`` (verts, tris) overlaps any mesh triangle at or above ``band_z``.

    Each triangle is clipped to the half-space ``z >= band_z`` (the sunk band [D095]/[D100] is not
    coverage) and tested against the hull with the SAT separation already used by the UCX pair
    checks; a real penetration (< -OVERLAP_EPS_M) is an intersection, mere touching is not.
    If no surface crosses, test hull vertices strictly above the band for volume containment.
    Return None when closure or ray parity cannot certify the remaining volume check.
    """
    hv, ht = hull
    for tri in tris:
        for ctri in _clip_tri_above([verts[i] for i in tri], band_z):
            if sat_separation((hv, ht), (ctri, [(0, 1, 2)])) < -OVERLAP_EPS_M:
                return True
    # Surface crossings do not detect a hull wholly enclosed by the element.
    # A point strictly inside the volume is strictly inside the mesh AABB, so the AABB prefilter
    # skips far meshes (open Flora alpha cards included) without a parity test (#1192).
    lo = [min(v[i] for v in verts) for i in range(3)]
    hi = [max(v[i] for v in verts) for i in range(3)]
    candidates = [v for v in hv if v[2] > band_z and all(lo[i] < v[i] < hi[i] for i in range(3))]
    if not candidates:
        return False
    # Closure is needed only for volume parity; proven surface crossings above still fail.
    unique = {v: i for i, v in enumerate(dict.fromkeys(verts))}
    mv = list(unique)
    mt = [tuple(unique[verts[i]] for i in tri) for tri in tris]
    if not is_closed(mt):
        return None
    uncertain = False
    for point in candidates:
        inside = _point_in_closed_mesh(point, mv, mt)
        if inside is True:
            return True
        uncertain |= inside is None
    return None if uncertain else False


def _ucx_maf_flora_finding(ucx: list[dict], meshes: list[dict], src: str) -> list[Finding]:
    """FLO-15 / MAF-22: the Ground UCX must not intersect a MAF or Flora element.

    MAF (``_GroundEl``) and Flora (``_Flora``) are excluded from Ground collision (reg p.36 §13.2),
    and both sink 10 cm into the Ground [D095]/[D100], so only the part of a MAF/Flora element
    *above* its 10 cm sunk band is judged. Each supported (closed, convex, non-degenerate) UCX
    piece is tested against that part of every MAF/Flora mesh with a real hull-triangle SAT
    intersection test and closed-mesh volume containment; a proven overlap is a blocking fail.
    Open meshes or ambiguous containment are ``not_run`` (each mesh named once) unless a surface
    crossing is proven; containment is tested only for UCX vertices strictly inside the mesh
    bounding box, so an open mesh away from every UCX passes (#1192).
    A MAF/Flora mesh without measurable
    face geometry is ``not_run`` naming the mesh, never a silent pass; an unsupported UCX piece is
    ``not_run`` too and never hides a proven intersection.
    """
    name = "UCX vs MAF/Flora intersection"
    expected = ("Ground UCX does not intersect MAF or Flora above the 10 cm sunk band "
                "[D095]/[D100] (reg p.36 §13.2) [FLO-15, MAF-22]")
    pages = [36]
    maf_flora = [m for m in meshes if m["name"].endswith(_MAF_FLORA_SUFFIXES)]
    if not maf_flora:
        return []
    unmeasurable, measurable = [], []
    for m in maf_flora:
        geom = _maf_flora_triangles(m)
        if geom[0] is None:
            unmeasurable.append((m["name"], geom[1]))
        else:
            measurable.append((m, geom[0], geom[1]))
    pieces = [_ucx_piece(mesh) for mesh in ucx]
    supported = [p for p in pieces if p["reason"] is None and p["hull"] is not None]
    unresolved = [p["name"] for p in pieces if p["reason"] is not None]
    offenders, ambiguous = [], {}
    for p in supported:
        for m, mverts, mtris in measurable:
            band_z = min(v[2] for v in mverts) + MAF_FLORA_SINK_M
            intersection = _hull_intersects_mesh_above(p["hull"], mverts, mtris, band_z)
            if intersection is True:
                offenders.append((p["name"], m["name"]))
                break
            if intersection is None:
                ambiguous.setdefault(id(m), m["name"])
    if offenders:
        shown = ", ".join(f"{a} intersects {b}" for a, b in offenders[:5])
        return [_f("fail", name, f"{src}: {len(offenders)} UCX piece(s) intersect a MAF/Flora element: {shown}",
                   expected, pages, src)]
    if unmeasurable or ambiguous or unresolved:
        notes = []
        if unmeasurable:
            notes.append(f"{len(unmeasurable)} MAF/Flora without measurable geometry: "
                         f"{', '.join(f'{n} ({r})' for n, r in unmeasurable[:5])}")
        if ambiguous:
            names = list(ambiguous.values())
            notes.append(f"{len(names)} MAF/Flora open or ambiguous (a UCX vertex lies inside the mesh "
                         f"bounding box; containment needs a closed mesh and an unambiguous ray): "
                         f"{', '.join(names[:5])}")
        if unresolved:
            notes.append(f"{len(unresolved)} unsupported UCX piece(s): {unresolved[:5]}")
        return [_f("not_run", name, f"{src}: {'; '.join(notes)}", expected, pages, src)]
    return [_f("pass", name, f"{src}: no UCX piece intersects a MAF/Flora element", expected, pages, src)]


def main_glass_findings(meshes: list[dict], stem: str, src: str) -> list[Finding]:
    """VPM OKS main FBX: the glass object and its materials (#1029; DER-18/19; reg p.33 §10.4.2, p.34 §10.4.4).

    Glass is mandatory where the building has glazing (reg 2.8, 2.8.1: one glass object), so a Main without
    `SM_{Address}_MainGlass` is `review` (a building without glazing is valid), never a silent pass. Glass
    materials are `M_{Address}_MainGlass_N`, N 1..7 (reg 2.8.2: at most 7); names absent from the readback: review."""
    if not stem.startswith("SM_") or stem.endswith(("_Light", "_Ground")):
        return []
    address = stem[3:]
    main, glass = f"SM_{address}_Main", f"SM_{address}_MainGlass"
    names = {m["name"]: m for m in meshes}
    out = []
    if glass not in names:
        status = "review" if main in names else "not_run"
        out.append(_f(status, "MainGlass object", f"{src}: no {glass}" + ("" if main in names else f" and no {main}"),
                      f"{glass} when the building has glazing (one glass object)", [33], src))
        return out
    out.append(_f("pass", "MainGlass object", f"{src}: {glass}", f"{glass}", [33], src))
    mats = names[glass].get("materials")
    if mats is None:
        out.append(_f("review", "MainGlass materials", f"{src}: material names not in the readback",
                      f"M_{address}_MainGlass_1..7", [34], src))
        return out
    pattern = re.compile(rf"^M_{re.escape(address)}_MainGlass_([1-7])$")
    bad = [m for m in mats if not (m and pattern.match(m))]
    out.append(_f("fail" if bad or not mats else "pass", "MainGlass materials",
                  f"{src}: {bad or mats or 'no material'}", f"M_{address}_MainGlass_1..7", [34], src))
    return out


def _color_layer_names(attrs) -> list[str] | None:
    """Names of readback color attributes; None when the value is not a list of {name: str} dicts."""
    if not isinstance(attrs, list):
        return None
    names = []
    for attr in attrs:
        if not isinstance(attr, dict) or not isinstance(attr.get("name"), str):
            return None
        names.append(attr["name"])
    return names


def color_attribute_finding(meshes: list[dict], src: str) -> Finding:
    """V005 'color attributes' (reg 2026 req 4.1.1, SINTEZ lp_color_attributes / check_color_attributes).

    The regulation only recommends removing color attributes (they break the UV display in 3ds Max),
    so any layer is 'review', not 'fail'. Every mesh, UCX included, is checked: SINTEZ counts the file.
    A mesh without the readback key (old readback JSON), a malformed value or no meshes at all is
    not_run, never pass.
    """
    expected = "no color attributes (reg 4.1.1: recommended to remove)"
    if not meshes:
        return _f("not_run", "color attributes", f"{src}: no meshes in readback", expected, [], src)
    unknown, found = [], {}
    for m in meshes:
        names = _color_layer_names(m.get("color_attributes"))
        legacy = m.get("legacy_vertex_colors", 0)
        legacy_ok = isinstance(legacy, int) and not isinstance(legacy, bool) and legacy >= 0
        if names is None or not legacy_ok:
            unknown.append(m["name"])
            continue
        if names or legacy:
            found.setdefault(m["name"], []).extend(names or [f"<{legacy} legacy vertex_colors>"])
    if unknown:
        return _f("not_run", "color attributes",
                  f"{src}: readback has no color_attributes for {len(unknown)} mesh(es): {unknown[:5]}",
                  expected, [], src, data={"unknown": unknown})
    count = sum(len(v) for v in found.values())
    if not found:
        return _f("pass", "color attributes", f"{src}: 0 color attributes on {len(meshes)} mesh(es)", expected,
                  [], src, measured=0, threshold=0, data={"objects": {}})
    labels = [f"{obj}:{name}" for obj, names in found.items() for name in names]
    return _f("review", "color attributes", f"{src}: {count} on {len(found)} object(s): {labels[:10]}", expected,
              [], src, measured=count, threshold=0, data={"objects": found})


def scene_findings(rb: dict, kind: str, role: str, profile: dict, flora_schedule: dict | None = None,
                   flora_share: int = FLORA_SHARE, *, maf_sizes=None, smoothing_angle_deg=None,
                   ground_area_m2=None, footprint_holes=None, diffuse_px=None,
                   ground_materials=None) -> dict[str, list[Finding]]:
    """role: 'oks' | 'ground' | 'light'. Returns {stage_id: findings}. Ground FBX: Flora checks
    (twinqa.flora; flora_schedule = {mesh name: {"height_m", "crown_m"}}, flora_share default 70 000).
    ground_area_m2: VPM Ground area basis = site minus OKS footprint, m2; selects the reg p.29 band for the
    Ground triangle count (None keeps it at 'review'; a non-finite or non-positive value raises ValueError)
    and is the expected top-down area of the footprint-coverage finding (missing -> not_run, never pass).
    footprint_holes: optional list of XY rings, one polygon per OKS footprint hole. Ground coverage
    inside that region is a separate finding; None leaves it not_run and never a pass of the hole claim.
    diffuse_px: VPM {(slot, udim): side px} of the archive Diffuse PNGs for V009 texel density.
    ground_materials: optional allow-list (exact names or fnmatch globs) of Ground materials; only matching
    faces feed the footprint area and hole checks. None keeps every non-UCX render face."""
    if ground_area_m2 is not None:
        check_ground_area(ground_area_m2)
    if ground_materials is not None:
        ground_materials = check_ground_materials(ground_materials)
    src = Path(rb["source"]).name
    out = {"V003": [], "V004": [], "V008": [], "V009": [], "V010": [], "V013": [], "V006": [], "V002": []}
    if not rb.get("readback_ok"):
        out["V003"].append(_f("fail", "FBX readback", rb.get("error", "no meshes"), "importable FBX with meshes", [4, 24], src))
        return out
    meshes = rb["meshes"]
    ucx = [m for m in meshes if m["name"].upper().startswith("UCX_")]
    out["V002"].extend(_v002_findings(rb, meshes, src))
    # V005: color attributes (reg 4.1.1, SINTEZ lp_color_attributes); review only, the regulation recommends removal
    out.setdefault("V005", []).append(color_attribute_finding(meshes, src))
    tris = sum(m["triangles"] for m in meshes if m not in ucx)  # collision is excluded (reg p.28 §3.9)

    # V003: triangulated on export, triangle limits, no foreign objects (reg p.6-8, 28-29)
    not_tri = [m["name"] for m in meshes if set(m["polygon_degrees"]) != {"3"}]
    out["V003"].append(_f("fail" if not_tri else "pass", "triangulated", f"{src}: {not_tri or 'all triangles'}",
                          "triangulated on export", [7, 28], src))
    if role != "light":
        observed, data = f"{src}: {tris}", None
        measured = threshold_n = margin = None
        if kind == "npm":
            limit = profile["geometry"]["ground_triangles_total_max" if role == "ground" else "oks_triangles_per_fbx_max"]
            status, conflicts = ("fail" if tris > limit else "pass"), []
            measured, threshold_n, margin = tris, limit, signed_margin(tris, limit, "max")
        else:
            if role == "ground":
                basis = profile["geometry"].get("ground_area_basis")
                conflicts = []
                if ground_area_m2 is None:
                    status, limit = "review", "by site area (reg p.29 table)"
                    observed += "; ground_area_m2 (site minus OKS footprint, m2) missing, band not selected"
                    data = {"area_m2": None, "area_ha": None, "band": None, "basis": basis}
                else:
                    limit, band = ground_triangle_limit(profile, ground_area_m2)
                    status = "fail" if tris > limit else "pass"
                    measured, threshold_n, margin = tris, limit, signed_margin(tris, limit, "max")
                    area_ha = ground_area_m2 / 10_000
                    observed += f"; ground_area_m2 {ground_area_m2} ({area_ha:g} ha)"
                    data = {"area_m2": ground_area_m2, "area_ha": area_ha, "band": dict(band), "basis": basis}
            else:
                hard = profile["geometry"]["oks_triangles_per_fbx_max_excluding_collision"]
                status = "fail" if tris > hard else "review" if tris > PROJECT_TRIANGLE_TARGET else "pass"
                limit = (f"{PROJECT_TRIANGLE_TARGET} project target (reuse as NPM; else windows as atlas planes), "
                         f"{hard} regulation limit")
                conflicts = []
                active = hard if tris > hard else PROJECT_TRIANGLE_TARGET
                measured, threshold_n, margin = tris, active, signed_margin(tris, active, "max")
        out["V003"].append(_f(status, "triangle count", observed, f"<= {limit}", [7, 28, 29], src, conflicts, data,
                              measured=measured, threshold=threshold_n, margin=margin))
        if role == "ground":
            out["V003"].extend(_ground_footprint_findings(meshes, ucx, src, ground_area_m2, footprint_holes,
                                                         ground_materials))
            out["V003"].append(_ground_skirt_finding(meshes, ucx, src))
    foreign = [o for o in rb["other_objects"] if not (role == "light" and o["type"] in ("LIGHT", "EMPTY"))]
    if foreign:
        # Any non-mesh object, lights included, fails (conflict #14 decided 2026-10-07 [D017] as the checker)
        out["V003"].append(_f("fail", "object types", f"{src}: {[(o['name'], o['type']) for o in foreign][:5]}",
                              "meshes only (lights only in the _Light FBX)", [4, 24, 33], src))

    # V004: transforms applied, rotation 0 (reg p.8, 29, 32-33)
    # Max writes the axis correction on the node: its default import is the object's own transform, and the baked
    # import adds -90 deg X (lab job 20261105-015151-c6e23463), so a Max object really rotated +90 deg X would pass
    # there. A Max FBX is judged on the default import only (real Max exports, owner decision 05.11.2026, #908);
    # other exporters: identity in either import mode (a baked Blender export carries the axes in the geometry).
    max_fbx = _from_max(rb)
    bad = [m["name"] for m in meshes
           if not _identity_transform(m["rotation_euler_deg"], m["scale"])
           and (max_fbx or not ("baked_rotation_euler_deg" in m
                                and _identity_transform(m["baked_rotation_euler_deg"], m.get("baked_scale", [1, 1, 1]))))]
    detail = ", ".join(f"{m['name']} rotation {[round(a, 3) for a in m['rotation_euler_deg']]} scale "
                       f"{[round(s, 4) for s in m['scale']]}" for m in meshes if m["name"] in bad[:5])
    origin = f" ({rb.get('fbx_application')} FBX, default import)" if max_fbx else ""
    out["V004"].append(_f("fail" if bad else "pass", "applied transforms",
                          f"{src}: {detail or 'rotation 0, scale 1'}{origin}",
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
            out["V010"].append(_ucx_shape_finding(ucx, src))
            if role == "ground":
                out["V010"].extend(_ucx_maf_flora_finding(ucx, meshes, src))
            out["V010"].append(_f("not_run", "UCX coverage and offsets", "coverage of the model, offsets",
                                  "reg p.34-37", [34, 37], src))
        # V008: one UV channel, no mirrored islands, glass only in 1001 (reg p.31-32, 39)
        multi = [m["name"] for m in meshes if m not in ucx and m["uv_channels"] != 1]
        mirrored = {m["name"]: m["mirrored_uv_triangles"] for m in meshes if m["mirrored_uv_triangles"]}
        glass = {m["name"]: m["udim_tiles"] for m in meshes if m["name"].endswith("MainGlass") and m["udim_tiles"] != [1001]}
        out["V008"].append(_f("fail" if multi else "pass", "one UV channel", f"{src}: {multi or 'all meshes'}", "1 UV channel", [31], src))
        out["V008"].append(_f("fail" if mirrored else "pass", "mirrored islands", f"{src}: {mirrored or 'none'}", "no mirrored UV", [31], src))
        if glass:
            out["V008"].append(_f("fail", "glass tile", f"{src}: {glass}", "glass only in UDIM 1001", [31, 32], src))
        # V009: texel density 512..1706 px/m (reg p.31-32 §6, [D160]); diffuse side per tile from the archive
        placeholder = profile.get("textures", {}).get("flat_placeholder", {}).get("size_px")
        out["V009"].extend(_texel_density_findings(rb, meshes, ucx, src, diffuse_px, placeholder))
        if role == "oks":
            out.setdefault("V012", []).extend(main_glass_findings(meshes, Path(rb["source"]).stem, src))
        # V013 (reg p.32-33 §9.3-9.5; conflict #19 decided 2026-10-07 [D018] as the checker)
        out["V013"].extend(_pivot_findings(meshes, ucx, src))
        out["V013"].append(_f("not_run", "MSK-77 point", "GeoJSON point vs survey coordinates and project zero",
                              "reg p.32-33, p.55", [32, 33, 55], src))

    if kind == "npm":
        # V006: textures embedded in the FBX (reg p.9 §5.1); pixel rules need the PNG bytes
        loose = [i["name"] for i in rb.get("images", []) if not i["packed"]]
        out["V006"].append(_f("fail" if loose else "pass", "embedded textures", f"{src}: {loose or 'all embedded'}",
                              "PNG embedded in FBX", [9], src))
        # Reg p.9 §5.2: no NPM atlas side exceeds 2048 px. Readback dimensions
        # complement (never replace) PNG-byte checks and area-specific smaller limits.
        images = rb.get('images', [])
        if images:
            bad_sizes = []
            for image in images:
                size = image.get('size')
                if (not isinstance(size, (list, tuple)) or len(size) != 2
                        or any(type(s) is not int or not 0 < s <= 2048 for s in size)):
                    bad_sizes.append((image.get('name', '<unnamed image>'), size))
            out["V006"].append(_f('fail' if bad_sizes else 'pass', 'texture dimensions',
                                  f"{src}: {bad_sizes or 'all measured sides <= 2048 px'}",
                                  'positive measured NPM image dimensions, each side <= 2048 px; PNG-byte checks separate',
                                  [9], src))
    if role == "ground":  # Flora checks (#191): dimensions V015, maps V005, Flora share V003
        geometry = [m for m in meshes if m not in ucx]
        for stage_id, findings in flora_findings(rb, kind, geometry, tris, profile, flora_schedule, flora_share).items():
            out.setdefault(stage_id, []).extend(findings)

    # V012: internal mesh names and UCX index grammar (reg p.11-12 §3.3, p.33-34 §4.2) -> twinqa.naming
    out["V012"] = out.get("V012", []) + mesh_name_findings([m["name"] for m in meshes], kind, role, Path(rb["source"]).stem,
                                     profile["naming"]["max_characters"], src)
    return out
