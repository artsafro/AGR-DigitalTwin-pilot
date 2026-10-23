"""Test oracle (#556): the per-triangle-pair xView contact test `inv_xview` used before the fast core became its engine.

Kept only here, for the tests; production code calls `inv_xview_fast.contact_tri_pairs`.
Pattern: none | new-case: test-only oracle of the pre-#556 per-triangle-pair xView contact test (#556).
"""
import numpy as np

from dt_ai.ops import inv_xview as X


def ref_contact(v, tris, nrm, s, t, poly_key, owner, nv, face_m):
    hit = np.zeros(len(s), dtype=bool)
    a, b, c = (v[tris[s, k]] for k in range(3))
    e0, e1 = b - a, c - a
    d00, d01, d11 = X._dot(e0, e0), X._dot(e0, e1), X._dot(e1, e1)
    den = d00 * d11 - d01 * d01
    for k in range(3):
        p_id = tris[t, k]
        own = X._owns(poly_key, owner[s] * nv + p_id)
        w = v[p_id] - a
        dist = X._dot(w, nrm[s])
        q = w - dist[:, None] * nrm[s]
        d20, d21 = X._dot(q, e0), X._dot(q, e1)
        bv = (d11 * d20 - d01 * d21) / den
        bw = (d00 * d21 - d01 * d20) / den
        inside = (bv >= -1e-12) & (bw >= -1e-12) & (bv + bw <= 1 + 1e-12)
        hit |= inside & (np.abs(dist) <= face_m) & ~own
    return hit
