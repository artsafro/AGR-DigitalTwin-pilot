"""KPP1 lattice body check: closed rings per level, through stations, local defect map per lattice cell.

Pattern: new-case | new-case: ring/loop closure and per-cell local signal of a facade body measured on the ring
lattice it was planned on (Artem 2026-11-21: every level a closed ring around the whole envelope, no loop that dies
on the next facade; acceptance sheets carry the local-signal map, decision 5 of body-mesh-method §6).

Input: a mesh (world vertices `verts` (N,3), per-face vertex counts `fn`, flat indices `fi` - the npz of
docs/research/body-modelling-1618/dump_mesh.py) and the lattice JSON of `lattice_input.py`.
Facade faces = |n.z| < 0.1 with every vertex within BAND m of the ring (inside or outside) and z in the level range;
horizontal faces (|n.z| > 0.9) within the band count as reveal sills/heads (their edges join a ring at a level).
A vertex is placed on the ring by its nearest side: s (perimeter coordinate) and depth d (inward > 0).

- level z closed: the horizontal edges at z (1 mm) cover the whole perimeter [0, P) in s (gaps listed);
- station s through: the vertical edges at s (1 mm) cover [zmin, zmax] (gaps listed);
- cell (station interval x level interval) defects: tri / ngon faces, diagonal edges (neither horizontal nor
  vertical, > 1 mm), T-vertices (a vertex strictly inside a face edge, 1 mm), non-manifold edges (> 2 faces);
  every facade face is assigned to exactly one cell by its centroid (faces outside the lattice are counted).
Fail-closed: no facade face, non-finite vertex, bad lattice -> ValueError.
"""
import json
import math
import os
import sys
from pathlib import Path

import numpy as np

BAND = 1.0
TOL = 1e-3


def ring_frame(lat):
    xy = lat.get('rings', [{}])[0].get('xy') if isinstance(lat, dict) else None
    if not isinstance(xy, list) or len(xy) < 3:
        raise ValueError('lattice: ring missing')
    P = np.array(xy, float)
    if not np.isfinite(P).all():
        raise ValueError('lattice: ring not finite')
    segs, s = [], 0.0
    for i in range(len(P)):
        p, q = P[i], P[(i + 1) % len(P)]
        L = float(np.hypot(*(q - p)))
        if L <= TOL:
            raise ValueError('lattice: degenerate ring side %d' % i)
        t = (q - p) / L
        segs.append((s, L, p, t, np.array([-t[1], t[0]])))
        s += L
    return segs, s


def place(verts, segs, perim):
    """(s, d, side) per vertex: nearest ring side in plan (ties -> lower side index)."""
    best = np.full(len(verts), np.inf)
    S = np.zeros(len(verts))
    D = np.zeros(len(verts))
    K = np.full(len(verts), -1)
    xy = verts[:, :2]
    for k, (s0, L, p, t, n) in enumerate(segs):
        u = np.clip((xy - p) @ t, 0.0, L)
        foot = p + u[:, None] * t
        dist = np.hypot(*(xy - foot).T)
        better = dist < best - 1e-9
        best = np.where(better, dist, best)
        S = np.where(better, (s0 + u) % perim, S)
        D = np.where(better, (xy - p) @ n, D)
        K = np.where(better, k, K)
    return S, D, K


def station_lines(S_st, segs, perim):
    """Per station: ring point p and its inward direction m (side normal; at a ring corner the mitre of the two
    normals, so a recessed corner vertex - built along the bisector - lies on its station line)."""
    out = []
    for s in S_st:
        s = s % perim
        k = max(i for i, g in enumerate(segs) if g[0] <= s + 1e-4)
        s0, L, p, t, n = segs[k]
        m = n
        if abs(s - s0) <= 1e-4:
            m = n + segs[k - 1][4]
        out.append((p + t * (s - s0), m / np.linalg.norm(m)))
    return out


def _cover(intervals, lo, hi):
    """Gaps of the union of intervals inside [lo, hi] (each gap > TOL)."""
    iv = sorted((max(lo, a), min(hi, b)) for a, b in intervals if b > lo and a < hi)
    gaps, cur = [], lo
    for a, b in iv:
        if a > cur + TOL:
            gaps.append([round(cur, 4), round(a, 4)])
        cur = max(cur, b)
    if hi > cur + TOL:
        gaps.append([round(cur, 4), round(hi, 4)])
    return gaps


def check(verts, fn, fi, lat):
    verts = np.asarray(verts, float)
    fn = np.asarray(fn, int)
    fi = np.asarray(fi, int)
    if verts.ndim != 2 or verts.shape[1] != 3 or not len(verts):
        raise ValueError('mesh: no vertices')
    if not np.isfinite(verts).all():
        raise ValueError('mesh: non-finite vertex')
    if fn.sum() != len(fi) or (fn < 3).any():
        raise ValueError('mesh: face index table inconsistent')
    segs, perim = ring_frame(lat)
    S_st = [float(x) for x in lat.get('stations_s', [])]
    Z = [float(z) for z in lat.get('levels', [])]
    if len(S_st) < 3 or len(Z) < 2 or any(not math.isfinite(v) for v in S_st + Z):
        raise ValueError('lattice: stations/levels missing or not finite')
    z0, z1 = Z[0], Z[-1]
    S, D, K = place(verts, segs, perim)
    starts = np.concatenate([[0], np.cumsum(fn)[:-1]])
    faces = [fi[a:a + n] for a, n in zip(starts, fn)]
    fac, hor = [], []
    for f_id, f in enumerate(faces):
        v = verts[f]
        nrm = np.zeros(3)
        for i in range(len(f)):  # Newell normal (works for ngons)
            a, b = v[i], v[(i + 1) % len(f)]
            nrm += [(a[1] - b[1]) * (a[2] + b[2]), (a[2] - b[2]) * (a[0] + b[0]), (a[0] - b[0]) * (a[1] + b[1])]
        ln = np.linalg.norm(nrm)
        if ln < 1e-12:
            continue
        nz = abs(nrm[2]) / ln
        if (np.abs(D[f]) > BAND).any() or (v[:, 2] < z0 - TOL).any() or (v[:, 2] > z1 + TOL).any():
            continue
        if nz < 0.1:
            fac.append(f_id)
        elif nz > 0.9:
            hor.append(f_id)
    if not fac:
        raise ValueError('mesh: no facade face within %.2f m of the ring and z %.3f..%.3f' % (BAND, z0, z1))
    use = fac + hor
    # edges with face count
    ecount = {}
    for f_id in use:
        f = faces[f_id]
        for i in range(len(f)):
            a, b = int(f[i]), int(f[(i + 1) % len(f)])
            ecount.setdefault((min(a, b), max(a, b)), []).append(f_id)

    def ds(a, b):  # signed s-interval of an edge (wrap at the perimeter start)
        sa, sb = S[a], S[b]
        if abs(sb - sa) > perim / 2:
            return [(max(sa, sb), perim), (0.0, min(sa, sb))]
        return [(min(sa, sb), max(sa, sb))]
    st_lines = station_lines(S_st, segs, perim)

    def on_station(v, i):
        p, m = st_lines[i]
        w = verts[v, :2] - p
        return abs(w[0] * m[1] - w[1] * m[0]) <= TOL and -BAND <= w @ m <= BAND
    lev = {j: [] for j in range(len(Z))}
    stn = {i: [] for i in range(len(S_st))}
    diag = []
    for (a, b) in ecount:
        pa, pb = verts[a], verts[b]
        dz = abs(pa[2] - pb[2])
        dxy = math.hypot(pa[0] - pb[0], pa[1] - pb[1])
        if dz <= TOL:
            for j, z in enumerate(Z):
                if abs(pa[2] - z) <= TOL and abs(pb[2] - z) <= TOL:
                    lev[j] += ds(a, b)
        elif dxy <= TOL:
            for i in range(len(S_st)):
                if on_station(a, i):
                    stn[i].append((min(pa[2], pb[2]), max(pa[2], pb[2])))
        else:
            diag.append((a, b))
    # T-vertices: a lattice vertex strictly inside an edge
    used_v = np.unique(np.concatenate([faces[f] for f in use]))
    P = verts[used_v]
    tvert = []
    for (a, b) in ecount:
        pa, pb = verts[a], verts[b]
        d = pb - pa
        L2 = float(d @ d)
        if L2 <= TOL * TOL:
            continue
        t = (P - pa) @ d / L2
        cand = (t > 1e-6) & (t < 1 - 1e-6)
        if not cand.any():
            continue
        q = pa + np.outer(t[cand], d)
        dist = np.linalg.norm(P[cand] - q, axis=1)
        ok = dist <= TOL
        for v, tv in zip(used_v[cand][ok], t[cand][ok]):
            if v not in (a, b) and math.sqrt(L2) * min(tv, 1 - tv) > TOL:
                tvert.append((int(v), a, b))
    nonman = [e for e, fl in ecount.items() if len(fl) > 2]
    # cells
    Sx = S_st + [perim]

    def cell_of(pt_s, pt_z):
        i = int(np.searchsorted(Sx, pt_s % perim, side='right')) - 1
        j = int(np.searchsorted(Z, pt_z, side='right')) - 1
        return (min(max(i, 0), len(S_st) - 1), min(max(j, 0), len(Z) - 2))

    def centroid_cell(ids):
        ss = S[ids]
        if ss.max() - ss.min() > perim / 2:
            ss = np.where(ss < perim / 2, ss + perim, ss)
        return cell_of(float(ss.mean()) % perim, float(verts[ids, 2].mean()))
    cells = {}

    def bump(c, k, n=1):
        cells.setdefault(c, {'faces': 0, 'tri': 0, 'ngon': 0, 'diagonal': 0, 't_vertex': 0, 'non_manifold': 0})
        cells[c][k] += n
    for f_id in use:
        f = faces[f_id]
        c = centroid_cell(np.asarray(f))
        bump(c, 'faces')
        if len(f) == 3:
            bump(c, 'tri')
        elif len(f) > 4:
            bump(c, 'ngon')
    for a, b in diag:
        bump(centroid_cell(np.array([a, b])), 'diagonal')
    for v, a, b in tvert:
        bump(centroid_cell(np.array([v])), 't_vertex')
    for a, b in nonman:
        bump(centroid_cell(np.array([a, b])), 'non_manifold')
    bad = {c: v for c, v in cells.items() if any(v[k] for k in ('tri', 'ngon', 'diagonal', 't_vertex', 'non_manifold'))}
    levels = []
    for j, z in enumerate(Z):
        gaps = _cover(lev[j], 0.0, perim)
        levels.append({'z': z, 'closed': not gaps, 'gaps_s': gaps[:20], 'gap_m': round(sum(b - a for a, b in gaps), 4)})
    stations = []
    for i, s in enumerate(S_st):
        gaps = _cover(stn[i], z0, z1)
        stations.append({'s': s, 'through': not gaps, 'gaps_z': gaps[:20],
                         'gap_m': round(sum(b - a for a, b in gaps), 4)})
    nface = len(use)
    return {
        'perimeter': round(perim, 5), 'levels': levels, 'stations': stations,
        'cells': [{'i': c[0], 'j': c[1], **v} for c, v in sorted(cells.items())],
        'summary': {
            'faces': nface, 'facade_faces': len(fac), 'horizontal_faces': len(hor),
            'quads': sum(1 for f in use if len(faces[f]) == 4), 'tris': sum(1 for f in use if len(faces[f]) == 3),
            'ngons': sum(1 for f in use if len(faces[f]) > 4), 'diagonal_edges': len(diag),
            't_vertices': len(tvert), 'non_manifold_edges': len(nonman),
            'levels_closed': sum(r['closed'] for r in levels), 'levels': len(levels),
            'stations_through': sum(r['through'] for r in stations), 'stations': len(stations),
            'cells_with_faces': len(cells), 'cells_with_defects': len(bad),
            'cells_defect_share': round(len(bad) / max(1, len(cells)), 4)}}


def main(argv):
    if len(argv) != 3:
        raise SystemExit('usage: python lattice_check.py MESH.npz LATTICE.json OUT.json')
    mesh, latp, out = (Path(a) for a in argv)
    tmp = out.with_name(out.name + '.partial')
    for p in (mesh, latp):
        if p.resolve() in (out.resolve(), tmp.resolve()):
            raise SystemExit('output aliases input: %s' % out)
    m = np.load(mesh)
    rep = check(m['verts'], m['fn'], m['fi'], json.loads(latp.read_text(encoding='utf-8-sig')))
    rep['inputs'] = {'mesh': str(mesh).replace('\\', '/'), 'lattice': str(latp).replace('\\', '/')}
    tmp.write_text(json.dumps(rep, indent=1, allow_nan=False), encoding='utf-8')
    os.replace(tmp, out)
    print(json.dumps(rep['summary']))


if __name__ == '__main__':
    main(sys.argv[1:])
