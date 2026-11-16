"""new-case: dependency-free vertical-datum arithmetic for CPython and embedded Blender (#1330).

Horizontal CRS is deliberately not an operand; ground marks never alter project zero.
"""
import math


def height_values(project_zero_m, project_zero_fbx_z_m, model_max_z_m):
    """Return App.3 heights with final-only rounding; ±0.000 need not coincide with FBX Z=0."""
    for key, value in zip(('project_zero_m', 'project_zero_fbx_z_m', 'model_max_z_m'),
                          (project_zero_m, project_zero_fbx_z_m, model_max_z_m)):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f'{key} must be a finite number')
    relative = model_max_z_m - project_zero_fbx_z_m
    absolute = project_zero_m + relative
    if not math.isfinite(relative) or not math.isfinite(absolute) or relative < 0:
        raise ValueError('height formula has invalid derived heights')
    return dict(h_relief=round(project_zero_m, 2), h_otn=round(relative, 2), h_abs=round(absolute, 2))


def export_z_check(project_zero_m, project_zero_fbx_z_m, ground_z_values, relief_abs_range=None, tol_m=0.01):
    """Project zero command core (#1406, D279): export Z of the ground top -> absolute marks, checked against the
    absolute range of the relief source. h_relief stays the project zero; a shift (e.g. 1.40 m) fails.

    Returns a dict with status pass | fail; invalid input raises ValueError (never pass)."""
    for key, value in (('project_zero_m', project_zero_m), ('project_zero_fbx_z_m', project_zero_fbx_z_m),
                       ('tol_m', tol_m)):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f'{key} must be a finite number')
    if tol_m < 0:
        raise ValueError('tol_m must be >= 0')
    zs = list(ground_z_values)
    if not zs:
        raise ValueError('no ground Z values: nothing to check')
    for z in zs:
        if isinstance(z, bool) or not isinstance(z, (int, float)) or not math.isfinite(z):
            raise ValueError(f'ground Z {z!r} is not a finite number')
    lo, hi = min(zs), max(zs)
    abs_lo, abs_hi = project_zero_m + (lo - project_zero_fbx_z_m), project_zero_m + (hi - project_zero_fbx_z_m)
    out = dict(project_zero_m=project_zero_m, project_zero_fbx_z_m=project_zero_fbx_z_m,
               export_z_range_m=[lo, hi], abs_range_m=[round(abs_lo, 6), round(abs_hi, 6)], findings=[])
    try:
        out.update(height_values(project_zero_m, project_zero_fbx_z_m, hi))
    except ValueError as exc:
        out['findings'].append(f'heights: {exc} (ground top below the project zero FBX Z)')
        out['h_relief'] = round(project_zero_m, 2)
    if relief_abs_range is not None:
        r_lo, r_hi = relief_abs_range
        for key, value in (('relief min', r_lo), ('relief max', r_hi)):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f'{key} must be a finite number')
        if r_lo > r_hi:
            raise ValueError('relief range min > max')
        if abs_lo < r_lo - tol_m:
            out['findings'].append(f'ground min {abs_lo:.4f} m < relief min {r_lo:.4f} m - {tol_m} m')
        if abs_hi > r_hi + tol_m:
            out['findings'].append(f'ground max {abs_hi:.4f} m > relief max {r_hi:.4f} m + {tol_m} m')
    else:
        out['findings'].append('relief range not given: export Z only converted, not checked')
    out['status'] = 'fail' if out['findings'] else 'pass'
    return out
