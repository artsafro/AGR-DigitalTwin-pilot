"""new-case: read-only Vatutino boundary sampling experiment (#358).

Production functions are called with explicit tolerances, never monkeypatched.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
FIXTURE = ROOT / 'tests/fixtures/spozu/vatutino_hatch_excerpt.dxf'
SPEC = importlib.util.spec_from_file_location('hyp358_inspector', ROOT / 'tools/source/inspect_ground_dxf.py')
inspector = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = inspector
SPEC.loader.exec_module(inspector)
HANDLES = ('150B41', '181ECB', 'FAA81')
TOLS = (0.0001, 0.0005, 1e-6, 1e-7)
HATCH_TOL = 0.001


def checked_boundary(doc, handle, tol):
    if type(tol) not in (int, float) or not math.isfinite(tol) or tol <= 0:
        raise ValueError('boundary tolerance must be finite and positive')
    entity = doc.entitydb.get(handle)
    if entity is None:
        raise ValueError(f'boundary {handle}: no such entity')
    if entity.dxftype() != 'LWPOLYLINE':
        raise ValueError(f'boundary {handle}: unsupported experiment type {entity.dxftype()}')
    verts = list(entity.get_points('xyb'))
    if not verts or any(not math.isfinite(v) for point in verts for v in point):
        raise ValueError(f'boundary {handle}: empty or nonfinite vertices')
    poly = inspector.boundary_polygon(doc, handle, tol)
    check_geometry(poly, f'boundary {handle}')
    return poly


def check_geometry(poly, label):
    if (poly is None or poly.is_empty or not poly.is_valid
            or poly.geom_type not in ('Polygon', 'MultiPolygon')
            or not math.isfinite(poly.area) or poly.area <= 0
            or not math.isfinite(poly.length)):
        raise ValueError(f'{label}: invalid/empty/unsupported geometry')


def analytic(verts):
    """Independent Green integral: chord shoelace plus circular segments.

    Translation to first vertex avoids cancellation at survey coordinates.
    Straight chords contribute to perimeter, not just the four arcs.
    """
    x0, y0, _ = verts[0]
    pts = [(x-x0, y-y0, b) for x, y, b in verts]
    areas, lengths = [], []
    for (x, y, b), (xx, yy, _) in zip(pts, pts[1:] + pts[:1]):
        chord = math.hypot(xx-x, yy-y)
        areas.append((x*yy-xx*y)/2)
        if b:
            theta = 4*math.atan(b)
            radius = chord / (2*abs(math.sin(theta/2)))
            areas.append(radius**2 * (theta-math.sin(theta))/2)
            lengths.append(radius*abs(theta))
        else:
            lengths.append(chord)
    return abs(math.fsum(areas)), math.fsum(lengths)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def measure(path=FIXTURE):
    import ezdxf

    before = sha(path)
    doc = ezdxf.readfile(path)  # one fresh parse per call; called exactly three times
    boundaries = list(doc.modelspace().query('LWPOLYLINE'))
    if len(boundaries) != 1:
        raise ValueError(f'expected exactly one boundary, got {len(boundaries)}')
    boundary = boundaries[0]
    verts = list(boundary.get_points('xyb'))
    if sum(bool(v[2]) for v in verts) != 4:
        raise ValueError('expected four bulges')
    hatches = {}
    for h in doc.modelspace().query('HATCH'):
        if not h.has_xdata('AGR'):
            raise ValueError(f'hatch {h.dxf.handle}: missing AGR source key')
        key = h.get_xdata('AGR')[0][1]
        if key not in HANDLES or key in hatches:
            raise ValueError(f'unmapped or duplicate hatch key: {key}')
        if h.dxf.hatch_style not in (0, 1, 2):
            raise ValueError(f'hatch {key}: unsupported style {h.dxf.hatch_style}')
        hatches[key] = h
    if set(hatches) != set(HANDLES):
        raise ValueError(f'missing hatch keys: {sorted(set(HANDLES)-set(hatches))}')
    # Every modelspace element is accounted for, including intentionally unused types.
    drops = [{'handle': e.dxf.handle, 'type': e.dxftype(),
              'reason': 'not the boundary or a target hatch'} for e in doc.modelspace()
             if e is not boundary and e not in hatches.values()]
    polys = {tol: checked_boundary(doc, boundary.dxf.handle, tol) for tol in TOLS}
    exact_area, exact_length = analytic(verts)
    rows, clips = {}, {}
    for tol, poly in polys.items():
        hs = {}
        for key in HANDLES:
            h = inspector.hatch_area(hatches[key], boundary=poly, tol=HATCH_TOL)
            if h.issues or h.area is None or h.area_in_plot is None:
                raise ValueError(f'hatch {key}: {h.issues}')
            check_geometry(h.geometry, f'hatch {key}')
            clipped = h.geometry.intersection(poly)
            check_geometry(clipped, f'clipped hatch {key}')
            clips[tol, key] = clipped
            hs[key] = {k: v for k, v in vars(h).items() if k != 'geometry'}
        inv = inspector.inventory(doc, boundary=poly, tol=HATCH_TOL)
        rows[str(tol)] = {
            'vertices': len(poly.exterior.coords)-1,
            'area_m2': poly.area, 'perimeter_m': poly.length,
            'area_error_m2': abs(poly.area-exact_area),
            'perimeter_error_m': abs(poly.length-exact_length),
            'wkb_sha256': hashlib.sha256(poly.wkb).hexdigest(),
            'valid': poly.is_valid, 'empty': poly.is_empty,
            'holes': len(poly.interiors), 'type': poly.geom_type,
            'hatches': hs, 'inventory_checks': inv['checks'],
        }
    base, candidate, ref, fine = (polys[t] for t in TOLS)
    reference = {
        'area_delta_m2': abs(ref.area-fine.area),
        'perimeter_delta_m': abs(ref.length-fine.length),
        'symmetric_difference_m2': ref.symmetric_difference(fine).area,
        'hausdorff_m': ref.boundary.hausdorff_distance(fine.boundary),
        'hatches': {k: {
            'symmetric_difference_m2': clips[1e-6, k].symmetric_difference(clips[1e-7, k]).area,
            'area_delta_m2': abs(clips[1e-6, k].area-clips[1e-7, k].area),
        } for k in HANDLES},
    }
    comparisons = {}
    for tol in TOLS[:2]:
        poly = polys[tol]
        comparisons[str(tol)] = {
            'boundary_symmetric_difference_m2': poly.symmetric_difference(fine).area,
            'hausdorff_m': poly.boundary.hausdorff_distance(fine.boundary),
            'hatches': {k: {
                'symmetric_difference_m2': clips[tol, k].symmetric_difference(clips[1e-7, k]).area,
                'clip_area_difference_m2': abs(clips[tol, k].area-clips[1e-7, k].area),
            } for k in HANDLES},
        }
    if sha(path) != before:
        raise ValueError('input bytes changed')
    return {
        'input_sha256': before, 'bulges': 4, 'boundary_handle': boundary.dxf.handle,
        'exact_area_m2': exact_area, 'exact_perimeter_m': exact_length,
        'rows': rows, 'reference_convergence': reference, 'comparisons': comparisons,
        'reduction': 1-(len(candidate.exterior.coords)-1)/(len(base.exterior.coords)-1),
        'candidate_vs_baseline': {
            'boundary_symmetric_difference_m2': base.symmetric_difference(candidate).area,
            'hatches': {k: {
                'symmetric_difference_m2': clips[0.0001, k].symmetric_difference(clips[0.0005, k]).area,
                'clip_area_difference_m2': abs(clips[0.0001, k].area-clips[0.0005, k].area),
            } for k in HANDLES},
        },
        'element_accounting': {'input': len(doc.modelspace()), 'output': 1+len(hatches), 'drops': drops},
    }


# Thresholds transcribed from the user message, NOT a reconstructed frozen issue table.
LIMITS = {'reduction': 0.5, 'area_error_m2': 0.05, 'perimeter_error_m': 0.005,
          'boundary_symmetric_difference_m2': 0.05, 'symmetric_difference_m2': 0.05,
          'clip_area_difference_m2': 0.05, 'hausdorff_m': 0.00051}


def threshold_pass(key, value):
    if key not in LIMITS:
        raise ValueError(f'unmapped metric: {key}')
    if type(value) not in (float, int) or not math.isfinite(value) or value < 0:
        raise ValueError(f'{key}: invalid metric {value!r}')
    # Fail closed at equality, per the explicit task instruction.
    return value > LIMITS[key] if key == 'reduction' else value < LIMITS[key]


def main():
    import platform
    import ezdxf
    import shapely

    blockers = [
        'Full issue #358 and its frozen prediction table are absent from task context/worktree.',
        'External ACCEPTANCE_TABLE.md is outside the permitted worktree; not read.',
        'Issue-specific reference convergence and diagnostics gates cannot be reconstructed.',
    ]
    result = {'verdict': 'inconclusive', 'delivery_passed': False, 'blockers': blockers,
              'hatch_tol_m': HATCH_TOL, 'boundary_tols_m': TOLS,
              'thresholds_from_user_message': LIMITS, 'runs': [],
              'environment': {'python': platform.python_version(), 'ezdxf': ezdxf.__version__,
                              'shapely': shapely.__version__, 'geos': shapely.geos_version_string},
              'code_hashes': {str(p.relative_to(ROOT)): sha(p) for p in (
                  Path(__file__), ROOT/'tools/source/inspect_ground_dxf.py',
                  ROOT/'tests/test_inspect_ground_dxf.py')}}
    try:
        result['runs'] = [measure() for _ in range(3)]
        canonical = [json.dumps(r, sort_keys=True, allow_nan=False) for r in result['runs']]
        result['repeatable'] = len(set(canonical)) == 1
        r = result['runs'][0]
        candidate = r['rows']['0.0005']
        comparison = r['comparisons']['0.0005']
        checks = {'reduction': threshold_pass('reduction', r['reduction'])}
        for key in ('area_error_m2', 'perimeter_error_m'):
            checks[key] = threshold_pass(key, candidate[key])
        for key in ('boundary_symmetric_difference_m2', 'hausdorff_m'):
            checks[key] = threshold_pass(key, comparison[key])
        for h, row in comparison['hatches'].items():
            for key, value in row.items():
                checks[f'{h}/{key}'] = threshold_pass(key, value)
        result['measured_user_threshold_checks'] = checks
        result['all_measured_thresholds_satisfied'] = all(checks.values())
    except Exception as exc:
        result['error'] = f'{type(exc).__name__}: {exc}'
    text = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + '\n'
    # No user-controlled destination, no temp file, no overwrites or input deletion.
    out = HERE/'results.json'
    with out.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(text)
    print(result['verdict'])


if __name__ == '__main__':
    main()
