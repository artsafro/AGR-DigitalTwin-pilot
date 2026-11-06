"""new-case: AGR Tools 1.0 (#1024) window type generator logic, stdlib only. Stub of branch 0; owned by branch J (improve/issue-1024-windows).

Pure logic for `win_generate` (win.generate); no pymxs. Use edit_core.py for reports, preview hashes and new paths, contract_core.py for
roles, markers and ObjRef (the core never takes a host object).
"""


def build_type(entry, standard, options=None):
    """One window type mesh by the library standard (K2).

    entry: a record of library/windows/window_types.json (id, role, width_m, height_m, panes_m, sections,
    transoms, ...); standard: library/windows/standard.json per family (F100 windows, F73 doors, F58; glass 80 mm
    from the frame face; face axis per type, owner answers 06.11.2026); options: {'variant': 'vpm'|'npm'}.
    Returns {'verts': [[x, y, z]...] metres in the type frame, 'faces': [[i...]...], 'mat_ids': [...],
    'parts': {'frame': [face idx], 'glass': [face idx]}, 'face_axis_m': float, 'status': 'ok'|'quarantine',
    'why': [str]}."""
    raise NotImplementedError('windowgen_core.build_type: branch J (#1024)')
