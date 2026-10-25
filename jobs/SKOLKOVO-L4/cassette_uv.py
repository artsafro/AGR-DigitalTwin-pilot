"""new-case: source-bound cassette UV evidence for delegated Skolkovo aspect diagnostics.

Orchestrator 2026-10-25 22:43 (pending Artem review): aspect <= 8 is diagnostic
ONLY for long thin rectangular cassette profiles with measured tile fit, density
and padding. This job-only audit leaves the shared checker and all budgets intact.
Charts are actual loop UVs in one local 4K tile, with a separate UDIM identifier.
Qualification is not a whole-scene, texture-count, export or human-approval receipt.
"""
import hashlib

import numpy as np

from dt_ai.ops.inv_texel import PolyMesh, face_metrics, texel_report

PART = "facade_cassette_perimeter_profiles_frame_contour_rebuild"
DENSITY = 1024
TILE = 4096
PADDING = 32


def qualify(part, mesh, charts):
    """Recompute proof from the current geometry and every actual chart; no trusted pass flags."""
    if part != PART:
        raise ValueError(f"aspect diagnostic is not authorized for {part!r}")
    if not isinstance(mesh, PolyMesh) or not mesh.faces:
        raise ValueError("nonempty polygon mesh required")
    if not isinstance(charts, list) or len(charts) != len(mesh.faces):
        raise ValueError("exactly one chart per face required")
    strict = texel_report({part: mesh}, "VPM-OKS")[part]
    errors = []
    seen, occupied = set(), {}
    density_errors, margins = [], []
    for chart in charts:
        if not isinstance(chart, dict) or set(chart) != {"face", "tile", "uv"}:
            raise ValueError("chart must contain exactly face, tile and uv")
        index, tile = chart["face"], chart["tile"]
        if type(index) is not int or not 0 <= index < len(mesh.faces) or index in seen:
            raise ValueError(f"unknown or duplicate face {index!r}")
        seen.add(index)
        if type(tile) is not int or tile < 1001:
            raise ValueError(f"invalid UDIM tile {tile!r}")
        points = mesh.vertices[list(mesh.faces[index])]
        uv = np.asarray(chart["uv"], dtype=float)
        if points.shape != (4, 3) or uv.shape != (4, 2) or not np.isfinite(uv).all():
            raise ValueError(f"face {index}: finite quad loop UVs required")
        a, b = points[1] - points[0], points[3] - points[0]
        la, lb = np.linalg.norm(a), np.linalg.norm(b)
        metric = face_metrics(points)
        if (metric.degenerate or metric.nonfinite or not np.isfinite([la, lb]).all()
                or abs(np.dot(a, b)) > 1e-10 * la * lb
                or not np.allclose(points[2] - points[0], a + b, rtol=0, atol=1e-9)):
            errors.append(f"face {index}: not a nondegenerate rectangle")
            continue
        px = uv * TILE
        with np.errstate(over="ignore", invalid="ignore"):
            geometric = np.linalg.norm(points[:, None] - points[None, :], axis=2) * DENSITY
            mapped = np.linalg.norm(px[:, None] - px[None, :], axis=2)
        if not np.isfinite(mapped).all() or not np.isfinite(geometric).all():
            errors.append(f"face {index}: nonfinite derived metric")
            continue
        error = float(np.abs(geometric - mapped).max())
        density_errors.append(error)
        if error > 1e-6:
            errors.append(f"face {index}: density/isometry mismatch {error:g} px")
        lo, hi = px.min(0), px.max(0)
        margin = float(min(lo.min(), (TILE - hi).min()))
        margins.append(margin)
        if margin < PADDING - 1e-8:
            errors.append(f"face {index}: tile/padding margin {margin:g} px < {PADDING}")
        for edge in np.roll(px, -1, axis=0) - px:
            if min(abs(edge)) > 1e-7:
                errors.append(f"face {index}: unsupported rotated chart")
                break
        for other, other_lo, other_hi in occupied.get(tile, ()):
            separation = np.maximum(other_lo - hi, lo - other_hi)
            if separation.max() < 2 * PADDING - 1e-8:
                errors.append(f"faces {other}/{index}: insufficient chart separation in tile {tile}")
        occupied.setdefault(tile, []).append((index, lo, hi))
    for index, face in enumerate(mesh.faces):
        metric = face_metrics(mesh.vertices[list(face)])
        if metric.degenerate or metric.nonfinite or metric.max_edge_m > 4 or metric.area_m2 > 16:
            errors.append(f"face {index}: strict non-aspect texel failure")
    signature = hashlib.sha256(mesh.vertices.astype('<f8').tobytes())
    signature.update(repr(mesh.faces).encode('ascii'))
    return {"qualified": not errors, "errors": errors, "geometry_sha256": signature.hexdigest(),
            "strict_passed": strict.passed, "strict_offenders": list(strict.offenders),
            "aspect_diagnostic_faces": [i for i, f in enumerate(mesh.faces)
                                        if face_metrics(mesh.vertices[list(f)]).aspect > 8],
            "faces": len(mesh.faces), "chart_tiles": len(occupied),
            "max_pair_distance_error_px": max(density_errors, default=None),
            "min_padding_px": min(margins, default=None),
            "decision": "orchestrator 2026-10-25 22:43; pending Artem review"}
