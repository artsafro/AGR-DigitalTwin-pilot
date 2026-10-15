"""new-case: V004 MAF/GroundEl findings on the FBX readback - smoothing, flipped normals, dimensions vs specification (#185)."""
from __future__ import annotations

import math

from twinqa.report import Finding

SMOOTHING_ANGLE_DEG = 40.0  # user practice: hard edges by angle 30-45 (MAF grilling 2026-10-15), configurable
DIMENSION_TOL_M = 0.10  # [D094]
SINK_M = 0.10  # [D095]


def is_groundel(name: str) -> bool:
    """NPM GroundEl mesh suffix, not glass and not a UCX collision mesh."""
    return name.endswith("_GroundEl") and not name.upper().startswith("UCX_")


def _size(value, label):
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError(f"{label} must be three finite positive numbers")
    out = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(item) or item <= 0:
            raise ValueError(f"{label} must be three finite positive numbers")
        out.append(float(item))
    return out


def _finding(name, status, observed, expected, pages, evidence):
    return Finding(name, status, observed, expected, list(pages), evidence)


def _soft_over(hist, angle):
    count, peak = 0, None
    for key, n in hist.items():
        deg = float(key)
        if deg > angle:
            count += n
            peak = deg if peak is None else max(peak, deg)
    return count, peak


def _bbox_size(mesh):
    bounds = mesh.get("bounds_m")
    if not isinstance(bounds, (list, tuple)) or len(bounds) != 2:
        return None
    lo, hi = bounds
    if not isinstance(lo, (list, tuple)) or not isinstance(hi, (list, tuple)) or len(lo) != 3 or len(hi) != 3:
        return None
    return [float(hi[i]) - float(lo[i]) for i in range(3)]


def maf_findings(meshes: list[dict], role: str, src: str, *, smoothing_angle_deg: float = SMOOTHING_ANGLE_DEG,
                 maf_sizes: dict[str, list[float]] | None = None, tol_m: float = DIMENSION_TOL_M,
                 sink_m: float = SINK_M) -> list[Finding]:
    """GroundEl smoothing and flipped normals, plus optional per-MAF bbox vs specification."""
    if not (0 < smoothing_angle_deg < 180):
        raise ValueError("smoothing_angle_deg must be between 0 and 180")
    if maf_sizes is not None:
        if not isinstance(maf_sizes, dict):
            raise ValueError("maf_sizes must map a mesh name to three finite positive numbers")
        for name, size in maf_sizes.items():
            if not isinstance(name, str):
                raise ValueError("maf_sizes keys must be mesh names")
            _size(size, name)

    out = []
    groundel = [m for m in meshes if is_groundel(m.get("name", ""))]
    if role == "ground" and groundel:
        smooth_expected = f"hard edge / split normals where faces meet above {smoothing_angle_deg:g} deg"
        flip_expected = "outward faces, consistent winding (single-sided only for NPM Flora)"
        missing = [m["name"] for m in groundel
                   if not isinstance(m.get("maf_surface"), dict) or "error" in m["maf_surface"]]
        if missing:
            observed = f"{src}: {', '.join(missing)}"
            out.append(_finding("MAF smoothing", "not_run", observed, smooth_expected, [8, 29], src))
            out.append(_finding("MAF flipped normals", "not_run", observed, flip_expected, [8, 29], src))
        else:
            rows = []
            for mesh in groundel:
                count, peak = _soft_over(mesh["maf_surface"].get("soft_edge_angles_deg", {}), smoothing_angle_deg)
                if count:
                    rows.append((mesh["name"], count, peak))
            if rows:
                shown = [f"{name}: {count} soft edges > {smoothing_angle_deg:g} deg (max {peak:.1f} deg)"
                         for name, count, peak in rows[:5]]
                out.append(_finding("MAF smoothing", "fail", f"{src}: {'; '.join(shown)}", smooth_expected, [8, 29], src))
            else:
                out.append(_finding("MAF smoothing", "pass", f"{src}: no soft edges above {smoothing_angle_deg:g} deg",
                                    smooth_expected, [8, 29], src))
            bad = []
            undetermined = 0
            for mesh in groundel:
                facts = mesh["maf_surface"]
                undetermined += int(facts.get("undetermined_components", 0))
                if facts.get("flipped_faces", 0) or facts.get("inconsistent_edges", 0):
                    bad.append(mesh)
            if bad:
                shown = [f"{m['name']}: flipped {m['maf_surface'].get('flipped_faces', 0)}, "
                         f"inconsistent {m['maf_surface'].get('inconsistent_edges', 0)}, "
                         f"undetermined {m['maf_surface'].get('undetermined_components', 0)}"
                         for m in bad[:5]]
                observed = f"{src}: {'; '.join(shown)}; undetermined components {undetermined}"
                out.append(_finding("MAF flipped normals", "fail", observed, flip_expected, [8, 29], src))
            else:
                observed = f"{src}: outward, undetermined components {undetermined}"
                out.append(_finding("MAF flipped normals", "pass", observed, flip_expected, [8, 29], src))

    if maf_sizes is not None:
        by_name = {m.get("name"): m for m in meshes}
        failed = []
        for name, spec in maf_sizes.items():
            sx, sy, sz = _size(spec, name)
            mesh = by_name.get(name)
            if mesh is None:
                failed.append(f"{name}: missing mesh")
                continue
            size = _bbox_size(mesh)
            if size is None:
                failed.append(f"{name}: missing bounds")
                continue
            plan_b, plan_s = sorted(size[:2]), sorted((sx, sy))
            deltas = (plan_b[0] - plan_s[0], plan_b[1] - plan_s[1], size[2] - (sz + sink_m))
            if any(abs(d) > tol_m + 1e-9 for d in deltas):
                failed.append(f"{name}: plan {deltas[0]:.3f} {deltas[1]:.3f} Z {deltas[2]:.3f}")
        expected = "|bbox - spec| <= 0.1 m per axis; Z = spec + 0.1 m sink [D094, D095]"
        if failed:
            out.append(_finding("MAF dimensions vs specification", "fail", f"{src}: {'; '.join(failed[:5])}",
                                expected, [4, 24], src))
        else:
            out.append(_finding("MAF dimensions vs specification", "pass",
                                f"{src}: all {len(maf_sizes)} within 0.1 m", expected, [4, 24], src))
    return out
