"""new-case: dependency-free vertical-datum arithmetic for CPython and embedded Blender (#1330).

Horizontal CRS is deliberately not an operand; ground marks never alter project zero.
"""
import math
import operator


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


def _finite(key, value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f'{key} must be a finite number, got {value!r}')
    return float(value)


def _level(p):
    lv = p[3]
    try:
        lv_i = None if isinstance(lv, bool) else operator.index(lv)
    except TypeError:
        lv_i = None
    if lv_i is None or lv_i < 0:
        raise ValueError(f'ground point {p!r}: level must be an integer >= 0')
    return lv_i


def export_z_check(project_zero_m, project_zero_fbx_z_m, ground_points, relief_z_at, *, step_m=0.0, tol_m=0.01):
    """Project zero command core (#1406, D279): every exported ground-top vertex against the relief at its XY.

    ``ground_points``: ``(x, y, z_export, level)`` with x, y in the relief's (source) coordinates and ``level`` the
    inset layer (0 base, k = +k * ``step_m``). ``relief_z_at(list of (x, y)) -> list of absolute Z or None`` (None =
    outside the relief TIN). Per vertex ``residual = project_zero_m + (z - project_zero_fbx_z_m) - level * step_m
    - relief(x, y)``; pass iff every ``|residual| <= tol_m``. A shifted project zero moves every residual by the
    shift, so it fails even when the ground stays inside the relief envelope (review r1 P1-1). h_relief stays the
    project zero. Invalid input or a vertex outside the relief raises ValueError (never pass).
    """
    zero = _finite('project_zero_m', project_zero_m)
    fbx = _finite('project_zero_fbx_z_m', project_zero_fbx_z_m)
    tol = _finite('tol_m', tol_m)
    step = _finite('step_m', step_m)
    if tol < 0:
        raise ValueError('tol_m must be >= 0')
    if step < 0:
        raise ValueError('step_m must be >= 0')
    if not callable(relief_z_at):
        raise ValueError('relief_z_at must be a callable (x, y) list -> absolute relief Z: no relief, no check')
    pts = []
    for p in ground_points:
        if len(p) != 4:
            raise ValueError(f'ground point {p!r}: expected (x, y, z, level)')
        x, y, z = (_finite('ground point', v) for v in p[:3])
        pts.append((x, y, z, _level(p)))
    if not pts:
        raise ValueError('no ground points: nothing to check')
    if step == 0 and any(lv > 0 for *_, lv in pts):
        raise ValueError('inset levels present but step_m is 0: give the cover step')
    rel = list(relief_z_at([(x, y) for x, y, _, _ in pts]))
    if len(rel) != len(pts):
        raise ValueError(f'relief_z_at returned {len(rel)} values for {len(pts)} points')
    outside = [pts[i][:2] for i, r in enumerate(rel) if r is None]
    if outside:
        raise ValueError(f'{len(outside)} ground vertices outside the relief TIN, first {outside[:3]} '
                         '(no extrapolation: wrong origin, wrong relief source or a missing crop)')
    res = [(zero + (z - fbx) - lv * step - _finite('relief Z', r), x, y, lv) for (x, y, z, lv), r in zip(pts, rel)]
    over = [t for t in res if abs(t[0]) > tol + 1e-9]
    vals = sorted(t[0] for t in res)
    out: dict = dict(project_zero_m=zero, project_zero_fbx_z_m=fbx, step_m=step, tol_m=tol, checked_vertices=len(pts),
               levels=sorted({t[3] for t in res}), residual_m=[round(vals[0], 6), round(vals[-1], 6)],
               shift_estimate_m=round(vals[len(vals) // 2], 6), h_relief=round(zero, 2), notes=[], findings=[])
    try:
        out.update(height_values(zero, fbx, max(z - lv * step for _, _, z, lv in pts)))
    except ValueError as exc:
        out['notes'].append(f'h_otn not computed: {exc} (ground top below the project zero FBX Z)')
    if over:
        worst = max(over, key=lambda t: abs(t[0]))
        out['findings'].append(f'{len(over)} ground vertices off the relief by > {tol} m, worst {worst[0]:+.4f} m '
                               f'at ({worst[1]:.3f}, {worst[2]:.3f}) level {worst[3]}; median shift '
                               f'{out["shift_estimate_m"]:+.4f} m')
    out['status'] = 'fail' if out['findings'] else 'pass'
    return out

