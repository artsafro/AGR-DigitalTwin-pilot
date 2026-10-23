"""FBX scene checks from a Blender readback (tools/blender/fbx_readback.py).

Fills the scene stages the header-only validator leaves not_run: V002 (units and scale;
units come from a pure-Python GlobalSettings read), V003 (triangulation,
triangle limits, object types), V004 (applied transforms, co-directional overlap clearance, regulatory topology defect count, MAF smoothing/flipped normals/dimensions (GroundEl)), V006 (NPM embedded images),
V008 (one UV channel, mirrored islands, glass tile, texel density when the readback has UV and one diffuse size), V010 (UCX presence, no material slots, triangle budget, intersections, intersection coverage, advisory gap; shape and coverage stay not_run),
V013 (origin, geometric-centre pivot, shared pivot). Triangle limits follow the 2026-10-07 decisions on conflicts #1 and #3.
Ground FBX: Flora checks from twinqa.flora (V015 dimensions, V005 maps, V003 Flora share; #191).
"""
import itertools
import math
import tempfile
from fractions import Fraction
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
from twinqa.report import Finding, signed_margin
from twinqa.naming import mesh_name_findings
from twinqa.uv import DENSITY_MAX_PX_PER_M, DENSITY_MIN_PX_PER_M, _density_finding, edge_densities

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


def _f(status, name, observed, expected, pages, evidence, conflicts=(), data=None, *,
      measured=None, threshold=None, margin=None):
    return Finding(name, status, observed, expected, list(pages), evidence, list(conflicts),
                   measured, threshold, margin, dict(data or {}))


GROUND_TABLE_KEY = "ground_triangles_max_by_area_ha"
GROUND_AREA_TOL_M2 = 0.25
"""Absolute tolerance in m2 between the readback top-down Ground area and ground_area_m2.

Pass only when the absolute difference is strictly below this value, so a difference
of exactly 0.25 m2 fails closed. A 0.5 m2 fill of the OKS footprint fails on the
3431.50 m2 Vatutino fixture.
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


def _texel_density_findings(rb: dict, meshes: list[dict], ucx: list[dict], src: str) -> list[Finding]:
    """Min 512 px/m and max 1706 px/m for non-UCX meshes. Missing UV or texture size is not_run."""
    geometry = [mesh for mesh in meshes if mesh not in ucx]
    if not geometry:
        return _density_bounds(src, "not_run", "no render mesh")
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


def _m2_text(value: float) -> str:
    return f"{value:.6f}".rstrip("0").rstrip(".")


def _ground_xy_rings(geometry: list[dict]) -> list[list[tuple[float, float]]]:
    """XY rings of render-mesh faces. Empty geometry raises ValueError('empty face geometry').

    Unsupported structure, a partial index and a non-finite coordinate also raise ValueError.
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
                continue
            ring = []
            for index in polygon:
                if isinstance(index, bool) or not isinstance(index, int):
                    raise ValueError(f"unsupported polygon index on {mesh['name']}")
                try:
                    point = vertices[index]
                except (IndexError, TypeError) as exc:
                    raise ValueError(f"partial face geometry on {mesh['name']}") from exc
                if isinstance(point, (str, bytes)) or not isinstance(point, (list, tuple)) or len(point) < 2:
                    raise ValueError(f"unsupported vertex on {mesh['name']}")
                coords = (point[0], point[1], point[2] if len(point) > 2 else 0.0)
                if any(isinstance(coord, bool) or not isinstance(coord, (int, float)) or not math.isfinite(coord)
                       for coord in coords):
                    raise ValueError(f"non-finite coordinate on {mesh['name']}")
                ring.append((float(point[0]), float(point[1])))
            if len(ring) >= 3:
                rings.append(ring)
    if not rings:
        raise ValueError("empty face geometry")
    return rings


def _topdown_area_m2(rings: list[list[tuple[float, float]]]) -> float:
    """Union area of the XY projections. Stacked coverings count once; a filled hole adds its area."""
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
        return 0.0
    try:
        area = float(shapely.union_all(parts).area)
    except shapely.errors.GEOSException as exc:
        raise ValueError(f"unsupported face geometry: {exc}") from exc
    if not math.isfinite(area):
        raise ValueError("non-finite projected area")
    return area


def _ground_footprint_finding(meshes: list[dict], ucx: list[dict], src: str, ground_area_m2) -> Finding:
    """Ground footprint coverage (V003), next to the triangle count.

    ``GROUND_AREA_TOL_M2`` is the absolute tolerance in square metres between the
    top-down (XY union) area of the Ground render meshes and ``ground_area_m2``
    (site area minus the OKS footprint). Pass only when the absolute difference is
    strictly below this value, so a difference of exactly ``GROUND_AREA_TOL_M2``
    fails closed. A 0.5 m2 fill is above the band and fails on the 3431.50 m2
    Vatutino fixture. UCX meshes are excluded. A positive difference is the area
    of the filled absence. Missing ``ground_area_m2``, or a readback with no face
    geometry, is ``not_run`` and never a pass. Empty, partial, unsupported and
    non-finite face data fail.
    """
    name = "ground footprint coverage"
    expected = (f"|top-down area - ground_area_m2| < {GROUND_AREA_TOL_M2} m2 "
                f"(filled footprint above the tolerance fails)")
    pages = [28, 29]
    geometry = [mesh for mesh in meshes if mesh not in ucx]
    if ground_area_m2 is None:
        return _f("not_run", name, f"{src}: ground_area_m2 missing", expected, pages, src,
                  data={"measured_m2": None, "expected_m2": None, "difference_m2": None})
    missing = [mesh for mesh in geometry if not isinstance(mesh.get("face_geometry"), dict)]
    if not geometry or len(missing) == len(geometry):
        return _f("not_run", name, f"{src}: no face geometry in readback", expected, pages, src,
                  data={"measured_m2": None, "expected_m2": ground_area_m2, "difference_m2": None})
    if missing:
        return _f("fail", name, f"{src}: partial face geometry", expected, pages, src,
                  data={"measured_m2": None, "expected_m2": ground_area_m2, "difference_m2": None})
    try:
        measured = _topdown_area_m2(_ground_xy_rings(geometry))
    except ValueError as exc:
        reason = str(exc)
        data = {"measured_m2": None, "expected_m2": ground_area_m2, "difference_m2": None}
        if reason == "empty face geometry":
            measured = 0.0
            difference = measured - ground_area_m2
            data = {"measured_m2": measured, "expected_m2": ground_area_m2, "difference_m2": difference}
            reason = (f"empty face geometry; measured {_m2_text(measured)} m2, "
                      f"expected {_m2_text(ground_area_m2)} m2, difference {_m2_text(difference)} m2")
        return _f("fail", name, f"{src}: {reason}", expected, pages, src, data=data)
    difference = measured - ground_area_m2
    if not math.isfinite(difference):
        return _f("fail", name, f"{src}: non-finite difference", expected, pages, src,
                  data={"measured_m2": measured, "expected_m2": ground_area_m2, "difference_m2": None})
    data = {"measured_m2": measured, "expected_m2": ground_area_m2, "difference_m2": difference}
    if difference > 0:
        data["filled_absence_m2"] = difference
    status = "pass" if abs(difference) < GROUND_AREA_TOL_M2 else "fail"
    margin = (GROUND_AREA_TOL_M2 - abs(difference)) / GROUND_AREA_TOL_M2
    observed = (f"{src}: measured {_m2_text(measured)} m2, expected {_m2_text(ground_area_m2)} m2, "
                f"difference {_m2_text(difference)} m2")
    if difference > 0:
        observed += f", filled absence {_m2_text(difference)} m2"
    return _f(status, name, observed, expected, pages, src, data=data,
              measured=measured, threshold=ground_area_m2, margin=margin)


def scene_findings(rb: dict, kind: str, role: str, profile: dict, flora_schedule: dict | None = None,
                   flora_share: int = FLORA_SHARE, *, maf_sizes=None, smoothing_angle_deg=None,
                   ground_area_m2=None) -> dict[str, list[Finding]]:
    """role: 'oks' | 'ground' | 'light'. Returns {stage_id: findings}. Ground FBX: Flora checks
    (twinqa.flora; flora_schedule = {mesh name: {"height_m", "crown_m"}}, flora_share default 70 000).
    ground_area_m2: VPM Ground area basis = site minus OKS footprint, m2; selects the reg p.29 band for the
    Ground triangle count (None keeps it at 'review'; a non-finite or non-positive value raises ValueError)
    and is the expected top-down area of the footprint-coverage finding (missing -> not_run, never pass)."""
    if ground_area_m2 is not None:
        check_ground_area(ground_area_m2)
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
            out["V003"].append(_ground_footprint_finding(meshes, ucx, src, ground_area_m2))
    foreign = [o for o in rb["other_objects"] if not (role == "light" and o["type"] in ("LIGHT", "EMPTY"))]
    if foreign:
        # Any non-mesh object, lights included, fails (conflict #14 decided 2026-10-07 [D017] as the checker)
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
        multi = [m["name"] for m in meshes if m not in ucx and m["uv_channels"] != 1]
        mirrored = {m["name"]: m["mirrored_uv_triangles"] for m in meshes if m["mirrored_uv_triangles"]}
        glass = {m["name"]: m["udim_tiles"] for m in meshes if m["name"].endswith("MainGlass") and m["udim_tiles"] != [1001]}
        out["V008"].append(_f("fail" if multi else "pass", "one UV channel", f"{src}: {multi or 'all meshes'}", "1 UV channel", [31], src))
        out["V008"].append(_f("fail" if mirrored else "pass", "mirrored islands", f"{src}: {mirrored or 'none'}", "no mirrored UV", [31], src))
        if glass:
            out["V008"].append(_f("fail", "glass tile", f"{src}: {glass}", "glass only in UDIM 1001", [31, 32], src))
        # Texel density is the same 512..1706 px/m band as twinqa.uv (reg p.32). It does not
        # change the channel / mirror / glass verdicts above.
        out["V008"].extend(_texel_density_findings(rb, meshes, ucx, src))
        # V013 (reg p.32-33 §9.3-9.5; conflict #19 decided 2026-10-07 [D018] as the checker)
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
