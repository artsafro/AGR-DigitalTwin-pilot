"""new-case: #748 rigid local frames keep real TOW02 seam topology within 1 micrometre.

Opt in with AGR_TOW02_FIXTURE_ROOT pointing to a LOCAL COPY of rootcause/louvre_top (same convention
as test_seams_tow02.py). Binary fixtures are workstation evidence, not git assets. The comparator and
frame self-tests run everywhere so the real-input matrix cannot pass vacuously.

Frozen from issue #748 / docs/experiments/hyp-748.md: R = Rz @ Ry @ Rx, v' = v @ R.T + t,
t = (2, -3, 5) m, inverse (v' - t) @ R; frames F1-F3; thresholds: no refusal, 0 xView pairs,
max_weld_m <= 0.005, identical source-labelled multisets (winding-aware), max vertex deviation <= 1e-6 m.
"""
import hashlib
import os
from collections import Counter
from functools import lru_cache
from pathlib import Path

import numpy as np
import pytest

from dt_ai.ops.inv_quads import PolyMesh
from dt_ai.ops.inv_xview import XviewTolerance, face_pairs
from dt_ai.ops.seams import join_parts, simplify_part

HASH = {'016': 'eca2de87fc3c597eee9d20a622f8c8bbe182955920e3b3041b8cec8fcc2575a1',
        '017': '848cf3b3208532d11398df4150df52974d58b05fb1d2e89f5eeb99788a0bb384'}
OP = {'016': 'simplify_glass', '017': 'join'}
FRAMES = {'F1': (17, 31, 43), 'F2': (-29, 11, 67), 'F3': (53, -37, 19)}
T = np.array([2.0, -3.0, 5.0])
VERTEX_TOL_M = 1e-6
WELD_MAX_M = 0.005
# identity-run counts from the report (faces, vertices, dropped)
EXPECTED_COUNTS = {'016': (2882, 3471, 4925), '017': (2882, 3471, 3561)}


def rot(deg):
    x, y, z = np.radians(deg)
    rx = np.array([[1, 0, 0], [0, np.cos(x), -np.sin(x)], [0, np.sin(x), np.cos(x)]])
    ry = np.array([[np.cos(y), 0, np.sin(y)], [0, 1, 0], [-np.sin(y), 0, np.cos(y)]])
    rz = np.array([[np.cos(z), -np.sin(z), 0], [np.sin(z), np.cos(z), 0], [0, 0, 1]])
    return rz @ ry @ rx


def canon_cycle(cycle):
    """Cyclic start only; reversed winding stays distinct."""
    k = min(range(len(cycle)), key=lambda i: cycle[i:] + cycle[:i])
    return cycle[k:] + cycle[:k]


def describe(result, r):
    v = np.asarray(result.mesh.vertices, float)
    if not np.isfinite(v).all():
        raise ValueError('non-finite output vertex')
    if r is not None:
        v = (v - T) @ r
    vkey = [tuple(sorted(s)) for s in result.vertex_sources]
    coords, dup_v = {}, 0
    for key, p in zip(vkey, v):
        dup_v += key in coords
        coords[key] = p
    faces = Counter((tuple(sorted(src)), len(f), canon_cycle(tuple(vkey[i] for i in f)))
                    for f, src in zip(result.mesh.faces, result.face_sources))
    return dict(coords=coords, dup_v=dup_v, faces=faces, vgroups=Counter(vkey),
                dropped=Counter(map(tuple, result.dropped_vertices)),
                fgroups=Counter((tuple(sorted(s)), len(f))
                                for f, s in zip(result.mesh.faces, result.face_sources)))


def compare(ref, got):
    """List of failed criteria (empty = same topology within VERTEX_TOL_M)."""
    fails = [name for name in ('fgroups', 'vgroups', 'dropped', 'faces') if ref[name] != got[name]]
    missing = ref['coords'].keys() - got['coords'].keys()
    extra = got['coords'].keys() - ref['coords'].keys()
    if missing:
        fails.append(f'missing vertex groups: {len(missing)}')
    if extra:
        fails.append(f'extra vertex groups: {len(extra)}')
    if got['dup_v']:
        fails.append(f"duplicate vertex groups: {got['dup_v']}")
    common = ref['coords'].keys() & got['coords'].keys()
    if not common:
        fails.append('no common vertex groups')
    else:
        # builtin max() skips a NaN that is not first; np.max propagates it, so NaN fails closed
        dev = float(np.max([np.linalg.norm(ref['coords'][k] - got['coords'][k]) for k in common]))
        if not (dev <= VERTEX_TOL_M):
            fails.append(f'max vertex deviation {dev!r} m > {VERTEX_TOL_M}')
    return fails


# ---- self-tests: run everywhere -------------------------------------------------------------

@pytest.mark.parametrize('name', sorted(FRAMES))
def test_frozen_frames_are_rigid_and_invertible(name):
    r = rot(FRAMES[name])
    assert abs(np.linalg.det(r) - 1) < 1e-12
    assert np.abs(r.T @ r - np.eye(3)).max() < 1e-12
    v = np.random.default_rng(748).uniform(-50, 50, (100, 3))
    assert np.abs(((v @ r.T + T) - T) @ r - v).max() < 1e-12


def _desc(coords, faces, dropped=()):
    vkey = list(coords)
    return dict(coords={k: np.asarray(p, float) for k, p in coords.items()}, dup_v=0,
                faces=Counter((('f', i),) + (len(f), canon_cycle(tuple(vkey[j] for j in f)))
                              for i, f in enumerate(faces)),
                vgroups=Counter(vkey), dropped=Counter(dropped),
                fgroups=Counter(((('f', i),), len(f)) for i, f in enumerate(faces)))


_BASE = {(('a', 0),): (0, 0, 0), (('a', 1),): (1, 0, 0), (('a', 2),): (1, 1, 0), (('a', 3),): (0, 1, 0)}


def test_comparator_accepts_rotated_start_and_tiny_noise():
    ref = _desc(_BASE, [(0, 1, 2, 3)])
    shifted = {k: tuple(np.add(p, (5e-7, 0, 0))) for k, p in _BASE.items()}
    got = _desc(shifted, [(2, 3, 0, 1)])
    assert compare(ref, got) == []


@pytest.mark.parametrize('case', ['over_tolerance', 'at_threshold_plus', 'nan', 'reversed_winding',
                                  'missing_group', 'dropped_changed', 'duplicate_group', 'empty'])
def test_comparator_fails_closed(case):
    ref = _desc(_BASE, [(0, 1, 2, 3)], dropped=[('a', 9)])
    coords, faces, dropped = dict(_BASE), [(0, 1, 2, 3)], [('a', 9)]
    if case == 'over_tolerance':
        coords[(('a', 0),)] = (2e-6, 0, 0)
    elif case == 'at_threshold_plus':
        coords[(('a', 0),)] = (np.nextafter(VERTEX_TOL_M, 1), 0, 0)
    elif case == 'nan':
        coords[(('a', 0),)] = (np.nan, 0, 0)
    elif case == 'reversed_winding':
        faces = [(3, 2, 1, 0)]
    elif case == 'missing_group':
        del coords[(('a', 3),)]
        faces = [(0, 1, 2)]
    elif case == 'dropped_changed':
        dropped = []
    got = _desc(coords, faces, dropped)
    if case == 'duplicate_group':
        got['dup_v'] = 1
    if case == 'empty':
        got = _desc({}, [], dropped)
    assert compare(ref, got), case


def test_comparator_exact_threshold_passes():
    ref = _desc(_BASE, [(0, 1, 2, 3)])
    coords = dict(_BASE)
    coords[(('a', 0),)] = (VERTEX_TOL_M, 0, 0)
    assert compare(ref, _desc(coords, [(0, 1, 2, 3)])) == []


# ---- real-input matrix: opt-in --------------------------------------------------------------

def _root():
    root = os.environ.get('AGR_TOW02_FIXTURE_ROOT')
    if not root:
        pytest.skip('set AGR_TOW02_FIXTURE_ROOT to local copied review fixtures')
    return Path(root)


@lru_cache(maxsize=None)
def _load(path_str):
    source = Path(path_str)
    original = source.read_bytes()  # explicitly configured missing input is an error
    assert hashlib.sha256(original).hexdigest() == HASH[source.stem[-3:]]
    with np.load(source, allow_pickle=False) as z:
        vertices = z['vertices'] - z['vertices'].min(0)  # once, before any frame change
        faces = tuple(tuple(map(int, z['loop_vert'][s:s + n]))
                      for s, n in zip(z['loop_start'], z['loop_total']))
        owner = z['owner'].copy()
    return original, vertices, faces, owner


def _run(version, r):
    source = _root() / f'top_build-v{version}.npz'
    original, vertices, faces, owner = _load(str(source))
    v = vertices if r is None else vertices @ r.T + T
    parts = {name: PolyMesh(v.copy(), tuple(f for f, o in zip(faces, owner) if o == k))
             for k, name in enumerate(('top', 'glass'))}
    snap = {k: (m.vertices.copy(), m.faces) for k, m in parts.items()}
    result = simplify_part(parts, 'glass') if OP[version] == 'simplify_glass' else join_parts(parts)
    for k, (sv, sf) in snap.items():
        assert np.array_equal(parts[k].vertices, sv) and parts[k].faces == sf, f'input {k} mutated'
    assert face_pairs(result.mesh, XviewTolerance()) == []
    assert float(result.max_weld_m) <= WELD_MAX_M
    counts = (len(result.mesh.faces), len(result.mesh.vertices), len(result.dropped_vertices))
    assert counts == EXPECTED_COUNTS[version]
    assert source.read_bytes() == original
    return describe(result, r)


_REF = {}


def _reference(version):
    if version not in _REF:
        ref = _run(version, None)
        assert ref['dup_v'] == 0
        _REF[version] = ref
    return _REF[version]


@pytest.mark.parametrize('frame', sorted(FRAMES))
@pytest.mark.parametrize('version', sorted(HASH))
def test_tow02_rigid_frame_preserves_seam_topology(version, frame):
    ref = _reference(version)
    got = _run(version, rot(FRAMES[frame]))
    assert compare(ref, got) == []


def test_tow02_non_rigid_frame_is_detected():
    """Negative control on real input: a 1 ppm scale is not rigid and must fail the matrix."""
    ref = _reference('017')
    try:
        got = _run('017', rot(FRAMES['F1']) * (1 + 1e-6))
    except AssertionError:
        return  # a postcondition already rejected it
    assert compare(ref, got)
