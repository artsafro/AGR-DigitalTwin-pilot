"""#748 driver: rigid local frames vs identity on real TOW02 v016/v017 seam operations.

Predictions/frames/thresholds are frozen from the issue before execution. Usage:
    uv run python experiments/hyp-748/run_frames.py [scratch_dir]
Writes results.json into the scratch dir (default %TEMP%/agr-hyp-t_bd80a975).
"""
import hashlib
import json
import shutil
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

import numpy as np

from dt_ai.ops.inv_quads import PolyMesh
from dt_ai.ops.inv_xview import XviewTolerance, face_pairs
from dt_ai.ops.seams import join_parts, simplify_part

SRC = Path('C:/Users/artsafro/.AGR-DigitalTwin_pilot/jobs/vyatskaya-tow02/outputs/'
           'review-v002/rootcause/louvre_top')
HASH = {'016': 'eca2de87fc3c597eee9d20a622f8c8bbe182955920e3b3041b8cec8fcc2575a1',
        '017': '848cf3b3208532d11398df4150df52974d58b05fb1d2e89f5eeb99788a0bb384'}
FRAMES = {'identity': None, 'F1': (17, 31, 43), 'F2': (-29, 11, 67), 'F3': (53, -37, 19)}
T = np.array([2.0, -3.0, 5.0])
VERTEX_TOL_M = 1e-6
WELD_MAX_M = 0.005


def rot(deg):
    x, y, z = np.radians(deg)
    rx = np.array([[1, 0, 0], [0, np.cos(x), -np.sin(x)], [0, np.sin(x), np.cos(x)]])
    ry = np.array([[np.cos(y), 0, np.sin(y)], [0, 1, 0], [-np.sin(y), 0, np.cos(y)]])
    rz = np.array([[np.cos(z), -np.sin(z), 0], [np.sin(z), np.cos(z), 0], [0, 0, 1]])
    return rz @ ry @ rx


def load(path):
    with np.load(path, allow_pickle=False) as z:
        vertices = z['vertices'] - z['vertices'].min(0)  # once, before any frame change
        faces = tuple(tuple(map(int, z['loop_vert'][s:s + n]))
                      for s, n in zip(z['loop_start'], z['loop_total']))
        owner = z['owner'].copy()
    return vertices, faces, owner


def parts_in(vertices, faces, owner, r):
    v = vertices if r is None else vertices @ r.T + T
    return {name: PolyMesh(v.copy(), tuple(f for f, o in zip(faces, owner) if o == k))
            for k, name in enumerate(('top', 'glass'))}


def canon_cycle(cycle):
    # cyclic start only; reversed winding stays distinct
    k = min(range(len(cycle)), key=lambda i: cycle[i:] + cycle[:i])
    return cycle[k:] + cycle[:k]


def describe(result, r):
    v = np.asarray(result.mesh.vertices, float)
    if r is not None:
        v = (v - T) @ r
    vkey = [tuple(sorted(s)) for s in result.vertex_sources]
    coords, dup_v = {}, 0
    for key, p in zip(vkey, v):
        dup_v += key in coords
        coords[key] = p
    faces = Counter()
    for f, src in zip(result.mesh.faces, result.face_sources):
        faces[(tuple(sorted(src)), len(f), canon_cycle(tuple(vkey[i] for i in f)))] += 1
    return dict(coords=coords, dup_v=dup_v, faces=faces,
                vgroups=Counter(vkey), dropped=Counter(map(tuple, result.dropped_vertices)),
                fgroups=Counter((tuple(sorted(s)), len(f))
                                for f, s in zip(result.mesh.faces, result.face_sources)))


def compare(ref, got):
    common = ref['coords'].keys() & got['coords'].keys()
    dev = max((float(np.linalg.norm(ref['coords'][k] - got['coords'][k])) for k in common),
              default=float('nan'))
    return dict(
        face_group_arity_equal=ref['fgroups'] == got['fgroups'],
        vertex_groups_equal=ref['vgroups'] == got['vgroups'],
        dropped_equal=ref['dropped'] == got['dropped'],
        face_cycles_equal=ref['faces'] == got['faces'],
        face_cycle_mismatch=sum((ref['faces'] - got['faces']).values())
        + sum((got['faces'] - ref['faces']).values()),
        vertex_groups_missing=len(ref['coords'].keys() - got['coords'].keys()),
        vertex_groups_extra=len(got['coords'].keys() - ref['coords'].keys()),
        duplicate_vertex_groups=got['dup_v'],
        max_vertex_dev_m=dev)


def main():
    scratch = Path(sys.argv[1] if len(sys.argv) > 1 else
                   Path(tempfile.gettempdir()) / 'agr-hyp-t_bd80a975')
    scratch.mkdir(parents=True, exist_ok=True)
    out = dict(numpy=np.__version__, python=sys.version.split()[0], frames={}, cases=[])
    for name, deg in FRAMES.items():
        if deg:
            r = rot(deg)
            out['frames'][name] = dict(euler_deg=deg, det=float(np.linalg.det(r)),
                                       orth_err=float(np.abs(r.T @ r - np.eye(3)).max()))
    for version in ('016', '017'):
        orig = SRC / f'top_build-v{version}.npz'
        copy = scratch / orig.name
        shutil.copyfile(orig, copy)
        ob, cb = orig.read_bytes(), copy.read_bytes()
        assert hashlib.sha256(ob).hexdigest() == HASH[version] == hashlib.sha256(cb).hexdigest()
        vertices, faces, owner = load(copy)
        op = 'simplify_glass' if version == '016' else 'join'
        ref = None
        for name, deg in FRAMES.items():
            r = None if deg is None else rot(deg)
            parts = parts_in(vertices, faces, owner, r)
            snap = {k: (m.vertices.copy(), m.faces) for k, m in parts.items()}
            case = dict(version=version, op=op, frame=name)
            t0 = time.perf_counter()
            try:
                res = simplify_part(parts, 'glass') if op == 'simplify_glass' else join_parts(parts)
            except Exception as exc:  # any refusal is a rejection, recorded
                case.update(refused=f'{type(exc).__name__}: {exc}'[:300])
                out['cases'].append(case)
                continue
            case['elapsed_s'] = round(time.perf_counter() - t0, 3)
            case['mutated'] = any(not np.array_equal(parts[k].vertices, sv) or parts[k].faces != sf
                                  for k, (sv, sf) in snap.items())
            case['pairs'] = len(face_pairs(res.mesh, XviewTolerance()))
            case['max_weld_m'] = float(res.max_weld_m)
            case['faces'] = len(res.mesh.faces)
            case['vertices'] = len(res.mesh.vertices)
            case['dropped'] = len(res.dropped_vertices)
            d = describe(res, r)
            if ref is None:
                ref = d
                case['duplicate_vertex_groups'] = d['dup_v']
            else:
                case.update(compare(ref, d))
            out['cases'].append(case)
        case_bytes = orig.read_bytes() == ob and copy.read_bytes() == cb
        out[f'bytes_unchanged_v{version}'] = case_bytes
    (scratch / 'results.json').write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps(out, indent=1, default=str))


if __name__ == '__main__':
    main()
