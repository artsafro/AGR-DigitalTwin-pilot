"""new-case: AGR Tools 1.0 (#1024) shared module openings logic, stdlib only. Stub of branch 0; owned by branch J (improve/issue-1024-windows).

Pure logic for the cross-branch functions below; no pymxs. Use edit_core.py for reports, preview hashes and new paths, contract_core.py for
roles, markers and ObjRef (the core never takes a host object).
"""


def find_openings(mesh, options=None):
    """The ONE opening recognition (K1/K2), read by win.place (J), body.capsules (K) and npm.to_vpm (Q).

    mesh: contract_core HostAdapter.mesh() dict {'verts': [[x, y, z]...] metres world, 'faces': [[i...]...],
    'mat_ids': [...], 'ref': ObjRef}. options: {'min_side_m': 0.1, ...} (owner J).
    Returns [{'id': int, 'border': [[x, y, z]...] metres, 'frame': {'origin': [x, y, z], 'x': [..], 'y': [..],
    'z': [..]} (z = wall normal outwards), 'w': m, 'h': m, 'sill': m, 'depth': m, 'wall': ObjRef['name'],
    'corner': bool}]: the fields of the agr_opening marker (contract_core.OPENING_FIELDS) plus border and frame."""
    raise NotImplementedError('openings_core.find_openings: branch J (#1024)')
