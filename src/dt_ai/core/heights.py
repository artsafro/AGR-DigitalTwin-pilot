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
