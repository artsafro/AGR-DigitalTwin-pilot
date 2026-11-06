"""new-case: AGR Tools 1.0 (#1024) shared module uvlayout logic, stdlib only. Stub of branch 0; owned by branch M (improve/issue-1024-vpm-layout).

Pure logic for the cross-branch functions below; no pymxs. Use edit_core.py for reports, preview hashes and new paths, contract_core.py for
roles, markers and ObjRef (the core never takes a host object).
"""


def layout_seamless(islands, grid_zero_m, module_m, texel_px_per_m, tile_px, options=None):
    """K6 seam-to-seam layout: islands keep their texel, move only by whole tile vectors (bricks: whole repeats).

    islands: [{'id': ..., 'uv': [[u, v]...], 'world': [[x, y, z]...] metres, 'library_id': int}];
    grid_zero_m: the project grid zero from the passport; module_m: module per recipe; UDIM step 3.6 m
    (owner answer 06.11.2026). Returns {'islands': [{'id', 'shift': [du, dv] integers, 'tile': udim,
    'cut': bool}], 'seam_texels': float (norm 0), 'moved': [{'id', 'why'}]}."""
    raise NotImplementedError('uvlayout_core.layout_seamless: branch M (#1024)')
