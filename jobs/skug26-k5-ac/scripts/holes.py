import sys, numpy as np
from scipy.sparse.csgraph import connected_components
from scipy.spatial import cKDTree

p = np.loadtxt(sys.argv[1], delimiter=",")
c = p.mean(0)
_, _, vt = np.linalg.svd(p - c, full_matrices=False)
# axes: largest in-plane spread, vertical (z) preferred as v
u_ax, v_ax, n_ax = vt[0], vt[1], vt[2]
q = (p - c) @ np.stack([u_ax, v_ax]).T
# make v the most vertical in-plane axis
if abs(v_ax[2]) < abs(u_ax[2]):
    q = q[:, ::-1]; u_ax, v_ax = v_ax, u_ax
umin, umax = q[:, 0].min(), q[:, 0].max()
vmin, vmax = q[:, 1].min(), q[:, 1].max()
m = 0.004
inner = (q[:, 0] > umin + m) & (q[:, 0] < umax - m) & (q[:, 1] > vmin + m) & (q[:, 1] < vmax - m)
qi = q[inner]
t = cKDTree(qi)
pairs = t.query_pairs(0.012, output_type="ndarray")
from scipy.sparse import coo_matrix
n = len(qi)
g = coo_matrix((np.ones(len(pairs)), (pairs[:, 0], pairs[:, 1])), shape=(n, n))
k, lab = connected_components(g, directed=False)
cent, rad = [], []
for i in range(k):
    pts = qi[lab == i]
    if len(pts) < 6: continue
    cc = pts.mean(0); cent.append(cc); rad.append(np.linalg.norm(pts - cc, axis=1).mean())
cent = np.array(cent)
print(f"plate {umax-umin:.4f} x {vmax-vmin:.4f} m (u x v), normal {n_ax.round(3)}, v-axis {v_ax.round(3)}")
print("holes", len(cent), "radius mean", np.mean(rad).round(4), "min", np.min(rad).round(4), "max", np.max(rad).round(4))
us = np.unique(np.round(cent[:, 0] - umin, 3)); vs = np.unique(np.round(cent[:, 1] - vmin, 3))
print("cols", len(us), us); print("rows", len(vs), vs)
hc = cent.mean(0); pc = np.array([(umin + umax) / 2, (vmin + vmax) / 2])
off = hc - pc
print("hole-field offset from plate centre (u,v) m:", off.round(4), "world:", (off[0] * u_ax + off[1] * v_ax).round(4))
print("plate world centre:", (c + pc[0] * u_ax + pc[1] * v_ax).round(4))
odd = [(r, cc) for r, cc in zip(rad, cent) if abs(r - np.median(rad)) > 0.002]
print("odd", [(round(r, 4), (cc - [umin, vmin]).round(3)) for r, cc in odd])
