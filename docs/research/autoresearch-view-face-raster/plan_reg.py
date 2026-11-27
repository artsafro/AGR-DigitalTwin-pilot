"""GT derivation: register PDF plan p36 (vector) to the model footprint (Revit walls z=1.4) under
4 rigid/mirror transforms; independent of elevation views."""
import json, sys, numpy as np, pymupdf as fitz
PDF = r'C:/Users/artsafro/Desktop/!3D viz/Alex_World/АГР_зона 2.1 — 1.pdf'
FP = r'C:/Users/artsafro/.AGR_Project/jobs/OBR22-K02/outputs/footprint-z1.4.geojson'
RES = 0.2
d = fitz.open(PDF); p = d[35]
ws = {w[4]: w for w in p.get_text('words') if w[1] < 320}
x21 = (ws['2.1'][0] + ws['2.1'][2]) / 2; x225 = (ws['2.25'][0] + ws['2.25'][2]) / 2
mpp = 88.220 / (x225 - x21)          # 88220 mm between axes 2.1 and 2.25 (dimension on sheet)
segs = []
for g in p.get_drawings():
    r = g['rect']
    if not (150 < r.x0 and r.x1 < 830 and 105 < r.y0 and r.y1 < 265): continue
    if not ((g.get("width") or 0) >= 0.45 or (g.get("fill") and tuple(g["fill"]) == (0.0, 0.0, 0.0))): continue   # thick strokes + black fills = cut walls
    for it in g['items']:
        if it[0] == 'l': segs.append((it[1].x, it[1].y, it[2].x, it[2].y))
        elif it[0] == 're':
            q = it[1]; segs += [(q.x0,q.y0,q.x1,q.y0),(q.x1,q.y0,q.x1,q.y1),(q.x1,q.y1,q.x0,q.y1),(q.x0,q.y1,q.x0,q.y0)]
P = np.array(segs, float)
P[:, [0, 2]] *= mpp; P[:, [1, 3]] *= -mpp     # page y down -> plan y up
def pts_from_segs(S):
    out = []
    for x0, y0, x1, y1 in S:
        n = max(2, int(np.hypot(x1-x0, y1-y0) / (RES/2)))
        t = np.linspace(0, 1, n); out.append(np.c_[x0+(x1-x0)*t, y0+(y1-y0)*t])
    return np.vstack(out)
pp = pts_from_segs(P)
g = json.load(open(FP)); ms = []
for poly in g['coordinates']:
    for ring in poly:
        r = np.array(ring)
        ms += [(*r[i], *r[i+1]) for i in range(len(r)-1)]
mp = pts_from_segs(np.array(ms))
def raster(pts, lo, shape):
    im = np.zeros(shape); ij = ((pts - lo) / RES).astype(int)
    ok = (ij[:,0]>=0)&(ij[:,1]>=0)&(ij[:,0]<shape[1])&(ij[:,1]<shape[0])
    im[ij[ok,1], ij[ok,0]] = 1
    # dilate 1 cell
    im = np.maximum.reduce([np.roll(np.roll(im, a, 0), b, 1) for a in (-1,0,1) for b in (-1,0,1)])
    return im
res = {}
for name, M in {'identity': [[1,0],[0,1]], 'rot180': [[-1,0],[0,-1]], 'mirror_y': [[1,0],[0,-1]], 'mirror_x': [[-1,0],[0,1]]}.items():
    q = pp @ np.array(M).T
    q = q - q.mean(0) + mp.mean(0)
    lo = np.minimum(q.min(0), mp.min(0)) - 15
    hi = np.maximum(q.max(0), mp.max(0)) + 15
    shape = (int((hi[1]-lo[1])/RES)+1, int((hi[0]-lo[0])/RES)+1)
    A = raster(q, lo, shape); B = raster(mp, lo, shape)
    C = np.real(np.fft.ifft2(np.fft.fft2(B) * np.conj(np.fft.fft2(A))))
    k = np.unravel_index(np.argmax(C), C.shape)
    res[name] = {'overlap_frac_model': round(float(C[k] / B.sum()), 4), 'shift_cells': [int(k[0]), int(k[1])]}
print(json.dumps({'m_per_pt': mpp, 'plan_pts': len(pp), 'model_pts': len(mp), 'res': res}, indent=1))
