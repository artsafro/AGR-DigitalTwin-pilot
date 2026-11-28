"""#159 POST-HOC diagnostic (declared after the H159 score, not a keep): drawn W/H vs the ortho ray-cast silhouette
extent per side (all geometry, not #157 wall clusters). Inputs: #145 ELV rays-1.npz (depth), #151 Olimpijsky
types-1.npz (type id), and run.py rows.json.

new-case: docs/research/autoresearch-view-face-realism/posthoc.py - #159 post-hoc silhouette-extent diagnostic
"""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

NPZ = {
    'elv': ('G:/Мой диск/AGR-evidence/145-view-face-elv/run1/rays-1.npz', 'depth'),
    'olimpijsky': ('G:/Мой диск/AGR-evidence/159-view-face-realism/inputs/olimpijsky-types-1.npz', 'type'),
}
TAU_W, TAU_H = 1.2, 1.0


def extents(z, key):
    res = float(z['res'])
    out = {}
    for az in z['az']:
        a = z[f'az{int(az):03d}_{key}']
        hit = np.isfinite(a) & (a > 0) if key == 'depth' else a >= 0
        cols, rows = np.where(hit.any(axis=0))[0], np.where(hit.any(axis=1))[0]
        out[int(az)] = (round(float(cols[-1] - cols[0] + 1) * res, 2), round(float(rows[-1] - rows[0] + 1) * res, 2))
    return out


def main():
    rows = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    pins, ext = {}, {}
    for name, (path, key) in NPZ.items():
        pins[name] = hashlib.sha256(Path(path).read_bytes()).hexdigest()
        ext[name] = extents(np.load(path, allow_pickle=True), key)
    table, inside = [], {'full': 0, 'full_n': 0}
    for r in rows:
        if r['kind'] == 'fragment_top_cut':
            continue
        W, H = ext[r['album']][int(r['gt_az']) % 360]
        dW, dH = round(r['W'] - W, 2), round(r['H'] - H, 2)
        ok = bool(abs(dW) <= TAU_W and abs(dH) <= TAU_H)
        if r['kind'] == 'full':
            inside['full_n'] += 1
            inside['full'] += ok
        table.append({'view': f"{r['album']} {r['view']}", 'kind': r['kind'], 'drawn': [r['W'], r['H']],
                      'silhouette': [W, H], 'dW': dW, 'dH': dH, 'inside': ok})
    print(json.dumps({'pins': pins, 'extents': ext, 'inside': inside, 'rows': table}, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
