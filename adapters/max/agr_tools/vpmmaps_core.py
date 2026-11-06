"""new-case: AGR Tools 1.0 (#1024) shared module vpmmaps logic, stdlib only. Stub of branch 0; owned by branch N (improve/issue-1024-vpm-maps).

Pure logic for the cross-branch functions below; no pymxs. Use edit_core.py for reports, preview hashes and new paths, contract_core.py for
roles, markers and ObjRef (the core never takes a host object).
"""


def build_maps(udim_table, library, out_dir, options=None):
    """D + ERM + N maps of the VPM step of vpm.build, by names_core grammar, into NEW files of out_dir (K3).

    udim_table: {mesh name: {library_id: udim}} (matlib_core.renumber_dense per mesh); library: load_library().
    Returns {'maps': [{'mesh', 'udim', 'kind': 'D'|'ERM'|'N', 'path', 'sha256'}], 'skipped': [...]}."""
    raise NotImplementedError('vpmmaps_core.build_maps: branch N (#1024)')
