"""new-case: AGR Tools 1.0 (#1024) material table (K3) logic, stdlib only. Stub of branch 0; owned by branch L (improve/issue-1024-materials).

Pure logic for `mat_table` (mat.table); no pymxs. Use edit_core.py for reports, preview hashes and new paths, contract_core.py for
roles, markers and ObjRef (the core never takes a host object).
"""


def load_library(path):
    """library/materials/materials.json pointer (sha256) -> materials_vNNN.json, validated (K3, K5: read from a copy).

    Returns {'version': str, 'sha256': str, 'materials': [record...], 'by_id': {library_id: record}};
    a record has library_id, key, name_ru, class, ral, rgb_srgb, roughness, metallic, emissive, recipe,
    base_map, status, source."""
    raise NotImplementedError('matlib_core.load_library: branch L (#1024)')


def renumber_dense(used_ids, start=1001):
    """Library ids used by ONE mesh -> UDIM tiles start.. without gaps, ascending library id (K3).

    UDIM numbering is per mesh (owner answer V9 06.11.2026): the OKS body starts at 1001 and the windows/glass
    mesh starts at 1001 too. Returns {library_id: udim}; an id <= 0 or >= 1001 is an error."""
    raise NotImplementedError('matlib_core.renumber_dense: branch L (#1024)')
