"""new-case: retained, immutable TOW02 #514 review fixture replay for #530.

Opt in with AGR_TOW02_FIXTURE_ROOT pointing to a LOCAL COPY of rootcause/louvre_top.
Binary fixtures are workstation evidence, not git assets. Synthetic tests run everywhere.
"""
import hashlib
import os
from pathlib import Path

import numpy as np
import pytest

from dt_ai.ops.inv_quads import PolyMesh
from dt_ai.ops.inv_xview import XviewTolerance, face_pairs
from dt_ai.ops.seams import join_parts, simplify_part


@pytest.mark.parametrize('version, expected', [('016', 0), ('017', 141)])
def test_tow02_fixture_seam_postcondition(version, expected):
    root = os.environ.get('AGR_TOW02_FIXTURE_ROOT')
    if not root:
        pytest.skip('set AGR_TOW02_FIXTURE_ROOT to local copied review fixtures')
    source = Path(root) / f'top_build-v{version}.npz'
    original = source.read_bytes()  # explicitly configured missing input is an error
    digest = hashlib.sha256(original).hexdigest()
    expected_hash = {'016': 'eca2de87fc3c597eee9d20a622f8c8bbe182955920e3b3041b8cec8fcc2575a1',
                     '017': '848cf3b3208532d11398df4150df52974d58b05fb1d2e89f5eeb99788a0bb384'}
    assert digest == expected_hash[version]
    with np.load(source, allow_pickle=False) as z:
        vertices = z['vertices'] - z['vertices'].min(0)
        faces = tuple(tuple(map(int, z['loop_vert'][s:s+n]))
                      for s,n in zip(z['loop_start'], z['loop_total']))
        parts = {name: PolyMesh(vertices.copy(), tuple(f for f, owner in zip(faces,z['owner']) if owner == k))
                 for k,name in enumerate(('top','glass'))}
    assert len(face_pairs(PolyMesh(vertices,faces), XviewTolerance())) == expected
    result = simplify_part(parts,'glass') if version == '016' else join_parts(parts)
    assert face_pairs(result.mesh, XviewTolerance()) == []
    assert len(result.mesh.faces) == 2882
    assert {p for labels in result.face_sources for p in labels} == {
        (name,i) for name,mesh in parts.items() for i in range(len(mesh.faces))}
    assert source.read_bytes() == original
