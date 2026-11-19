"""Crop a dump_mesh.py npz to a world box (#1619 stage-2 close-up sheets). new-case: close-up crop for wire_sheet.py.

uv run python crop_dump.py DUMP.npz OUT.npz XMIN YMIN ZMIN XMAX YMAX ZMAX
Keeps the faces (raw `fi` triangles and rejoined `ji` polygons) whose every vertex lies in the box; the vertex arrays
are compacted to the kept faces and re-indexed. Refuses OUT equal to the input and an empty crop.
"""
import os
import sys

import numpy as np


def keep_faces(n, idx, inside):
    """(new n, new idx, mask per face) for packed polygons whose every vertex is inside."""
    out_n, out_i, mask, k = [], [], [], 0
    for c in n:
        f = idx[k:k + c]
        k += c
        ok = bool(inside[f].all())
        mask.append(ok)
        if ok:
            out_n.append(c)
            out_i.extend(f)
    return np.array(out_n, dtype=np.int32), np.array(out_i, dtype=np.int64), np.array(mask, bool)


def main(argv=None):
    a = argv if argv is not None else sys.argv[1:]
    src, out = a[0], a[1]
    lo, hi = np.array([float(v) for v in a[2:5]]), np.array([float(v) for v in a[5:8]])
    if os.path.realpath(src) == os.path.realpath(out):
        sys.exit("refused: output equals the input")
    d = dict(np.load(src))
    vin = ((d["verts"] >= lo) & (d["verts"] <= hi)).all(1)
    jin = ((d["jverts"] >= lo) & (d["jverts"] <= hi)).all(1)
    fn, fi, fm = keep_faces(d["fn"], d["fi"], vin)
    jn, ji, jm = keep_faces(d["jn"], d["ji"], jin)
    if not len(jn):
        sys.exit("refused: empty crop")
    uvk = np.repeat(fm, d["fn"])
    d.update(fn=fn, mats=d["mats"][fm], uvn=d["uvn"][fm], uvf=d["uvf"][uvk], jn=jn, jmats=d["jmats"][jm])
    # compact the vertex arrays (wire_sheet frames the view on all vertices)
    for vk, ik, idx in (("verts", "fi", fi), ("jverts", "ji", ji)):
        used, inv = np.unique(idx, return_inverse=True)
        d[vk] = d[vk][used]
        d[ik] = inv.astype(np.int64)
    np.savez(out, **d)
    print(out, "faces", len(fn), "rejoined", len(jn))


if __name__ == "__main__":
    main()
