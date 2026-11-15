"""KPP1 #1416 [D308]: pure plan for the derived Ground copy v003 (bridge, names, path guards).

Pattern: n/a | new-case: job helper, maps the customer Ground mesh names to the NPM V012 grammar
(`SM_Kpp_1_<suffix>`) and applies the #1371 indexed frame bridge (row vectors: p_abs = p @ R + t).
No bpy import: derive_ground_v003.py (Blender) and the tests share it.
"""
import json
import math
import os
from pathlib import Path

SOURCE_PREFIX = "SM_77_05_0009005_117_"
TARGET_PREFIX = "SM_Kpp_1_"
SUFFIXES = ("Ground", "GroundGlass", "GroundEl", "GroundElGlass", "Flora")  # reg p.11-12 §3.2-3.3


class PlanError(ValueError):
    pass


def target_name(name: str) -> str:
    """Customer mesh name -> NPM Ground name; anything unmapped is an error naming it."""
    if not name.startswith(SOURCE_PREFIX) or name[len(SOURCE_PREFIX):] not in SUFFIXES:
        raise PlanError(f"unmapped Ground mesh name: {name!r}")
    return TARGET_PREFIX + name[len(SOURCE_PREFIX):]


def rename_map(names) -> dict:
    names = list(names)
    if not names:
        raise PlanError("no Ground meshes")
    if len(set(names)) != len(names):
        raise PlanError(f"duplicated mesh names: {sorted(names)}")
    return {n: target_name(n) for n in names}


def load_bridge(mapping_json: Path) -> tuple[list, list]:
    """Rotation rows and translation of the #1371 frame bridge; finite, orthonormal, det +1."""
    fb = json.loads(Path(mapping_json).read_text(encoding="utf-8"))["frame_bridge"]
    rot, t = fb["rotation_row"], fb["translation"]
    if len(rot) != 3 or any(len(r) != 3 for r in rot) or len(t) != 3:
        raise PlanError("bridge rotation must be 3x3 and translation 3")
    if not all(math.isfinite(float(x)) for x in [*t, *(c for r in rot for c in r)]):
        raise PlanError("non-finite bridge value")
    for i in range(3):
        for j in range(3):
            dot = sum(rot[i][k] * rot[j][k] for k in range(3))
            if abs(dot - (1.0 if i == j else 0.0)) > 1e-6:
                raise PlanError("bridge rotation is not orthonormal")
    det = (rot[0][0] * (rot[1][1] * rot[2][2] - rot[1][2] * rot[2][1])
           - rot[0][1] * (rot[1][0] * rot[2][2] - rot[1][2] * rot[2][0])
           + rot[0][2] * (rot[1][0] * rot[2][1] - rot[1][1] * rot[2][0]))
    if abs(det - 1.0) > 1e-6:
        raise PlanError(f"bridge rotation det {det} != 1 (mirror)")
    return [list(map(float, r)) for r in rot], [float(x) for x in t]


def apply_bridge(p, rot, t) -> tuple:
    """Row-vector convention of mapping.json: p_abs = p @ R + t."""
    return tuple(sum(p[k] * rot[k][j] for k in range(3)) + t[j] for j in range(3))


def column_matrix(rot, t) -> list:
    """4x4 column-vector matrix (Blender convention) equal to apply_bridge."""
    return [[rot[0][0], rot[1][0], rot[2][0], t[0]],
            [rot[0][1], rot[1][1], rot[2][1], t[1]],
            [rot[0][2], rot[1][2], rot[2][2], t[2]],
            [0.0, 0.0, 0.0, 1.0]]


def check_out_dir(out: str, inputs) -> str:
    """New output dir: not existing (nor its .partial), not equal to or inside any input's dir."""
    out = os.path.realpath(out)
    if os.path.lexists(out) or os.path.lexists(out + ".partial"):
        raise PlanError(f"output exists: {out}")
    for i in inputs:
        i = os.path.realpath(i)
        d = os.path.dirname(i)
        if out in (i, d) or out.startswith(d + os.sep):
            raise PlanError(f"output {out} aliases / sits inside input dir {d}")
    return out
