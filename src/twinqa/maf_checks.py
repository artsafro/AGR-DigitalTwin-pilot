"""new-case: V004 MAF/GroundEl findings on the FBX readback - smoothing, flipped normals, dimensions vs specification (#185)."""
from __future__ import annotations

import math

from twinqa.report import Finding

SMOOTHING_ANGLE_DEG = 40.0  # user practice: hard edges by angle 30-45 (MAF grilling 2026-10-15), configurable
DIMENSION_TOL_M = 0.10  # [D094]


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


def _finite_nonneg(value):
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value) and value >= 0


def _count(value):
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _angles(facts):
    if not isinstance(facts, dict) or "error" in facts or not isinstance(facts.get("soft_edge_dihedrals_deg"), list):
        return None
    angles = facts["soft_edge_dihedrals_deg"]
    if any(not _finite_nonneg(angle) for angle in angles):
        return None
    return angles


def _flip_counts(facts):
    if not isinstance(facts, dict) or "error" in facts:
        return None
    keys = ("components", "undetermined_components", "flipped_faces", "inconsistent_edges")
    values = [facts.get(key) for key in keys]
    if any(not _count(value) for value in values) or values[1] > values[0]:
        return None
    return values


def _note_unmeasured(text, names):
    return text if not names else f"{text}; unmeasured: {', '.join(names)}"


def _bbox_size(mesh):
    bounds = mesh.get("bounds_m")
    if not isinstance(bounds, (list, tuple)) or len(bounds) != 2:
        return None
    lo, hi = bounds
    if not isinstance(lo, (list, tuple)) or not isinstance(hi, (list, tuple)) or len(lo) != 3 or len(hi) != 3:
        return None
    return [float(hi[i]) - float(lo[i]) for i in range(3)]


def maf_findings(meshes: list[dict], role: str, src: str, *, smoothing_angle_deg: float = SMOOTHING_ANGLE_DEG,
                 maf_sizes: dict[str, list[float]] | None = None, tol_m: float = DIMENSION_TOL_M) -> list[Finding]:
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
        smooth_bad, smooth_gap = [], []
        flip_bad, flip_open, flip_gap = [], [], []
        for item in groundel:
            name = item["name"]
            facts = item.get("maf_surface")
            angles = _angles(facts)
            if angles is None:
                smooth_gap.append(name)
            else:
                over = [angle for angle in angles if angle > smoothing_angle_deg + 1e-6]
                if over:
                    smooth_bad.append((name, len(over), max(over)))
            counts = _flip_counts(facts)
            if counts is None:
                flip_gap.append(name)
            else:
                _components, undetermined, flipped, inconsistent = counts
                if flipped or inconsistent:
                    flip_bad.append((name, flipped, inconsistent, undetermined))
                elif undetermined:
                    flip_open.append((name, undetermined))
        if smooth_bad:
            shown = [f"{name}: {count} soft edges > {smoothing_angle_deg:g} deg (max {peak:.2f} deg)"
                     for name, count, peak in smooth_bad[:5]]
            smooth_status, smooth_observed = "fail", _note_unmeasured(f"{src}: {'; '.join(shown)}", smooth_gap)
        elif smooth_gap:
            smooth_status, smooth_observed = "not_run", _note_unmeasured(src, smooth_gap)
        else:
            smooth_status = "pass"
            smooth_observed = f"{src}: no soft edges above {smoothing_angle_deg:g} deg"
        out.append(_finding("MAF smoothing", smooth_status, smooth_observed, smooth_expected, [8, 29], src))
        if flip_bad:
            shown = [f"{name}: flipped {flipped}, inconsistent {inconsistent}, undetermined {undetermined}"
                     for name, flipped, inconsistent, undetermined in flip_bad[:5]]
            shown.extend(f"{name}: {count} orientation undetermined" for name, count in flip_open)
            flip_status, flip_observed = "fail", _note_unmeasured(f"{src}: {'; '.join(shown)}", flip_gap)
        elif flip_open or flip_gap:
            shown = [f"{name}: {count} orientation undetermined" for name, count in flip_open]
            flip_status = "not_run"
            flip_observed = _note_unmeasured(f"{src}: {'; '.join(shown)}" if shown else src, flip_gap)
        else:
            flip_status, flip_observed = "pass", f"{src}: outward"
        out.append(_finding("MAF flipped normals", flip_status, flip_observed, flip_expected, [8, 29], src))

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
            deltas = (plan_b[0] - plan_s[0], plan_b[1] - plan_s[1], size[2] - sz)
            if any(abs(d) > tol_m + 1e-9 for d in deltas):
                failed.append(f"{name}: plan {deltas[0]:.3f} {deltas[1]:.3f} Z {deltas[2]:.3f}")
        expected = "|bbox - spec| <= 0.1 m per axis on overall dimensions; the 10 cm sink is a translation [D094, D095]"
        if failed:
            out.append(_finding("MAF dimensions vs specification", "fail", f"{src}: {'; '.join(failed[:5])}",
                                expected, [4, 24], src))
        else:
            out.append(_finding("MAF dimensions vs specification", "pass",
                                f"{src}: all {len(maf_sizes)} within 0.1 m", expected, [4, 24], src))
    return out
