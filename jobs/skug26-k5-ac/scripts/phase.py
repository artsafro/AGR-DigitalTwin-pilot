import sys, glob, os, numpy as np
from scipy.spatial import cKDTree
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

d = sys.argv[1]; prefix = sys.argv[2]; elems = sys.argv[3]
E = {int(r[0]): r[1:] for r in np.loadtxt(os.path.join(d, elems), delimiter=",", ndmin=2)}
for f in sorted(glob.glob(os.path.join(d, prefix + "_*.csv")), key=lambda s: int(s.split("_")[-1][:-4])):
    k = int(f.split("_")[-1][:-4]); n = E[k][3:6]
    p = np.loadtxt(f, delimiter=",")
    right = np.cross(-n, [0, 0, 1]); right /= np.linalg.norm(right)
    u = p @ right; z = p[:, 2]
    umin, umax, zmin, zmax = u.min(), u.max(), z.min(), z.max()
    m = 0.004
    inn = (u > umin + m) & (u < umax - m) & (z > zmin + m) & (z < zmax - m)
    q = np.c_[u[inn], z[inn]]
    pr = cKDTree(q).query_pairs(0.012, output_type="ndarray")
    g = coo_matrix((np.ones(len(pr)), (pr[:, 0], pr[:, 1])), shape=(len(q), len(q)))
    kk, lab = connected_components(g, directed=False)
    cs = np.array([q[lab == i].mean(0) for i in range(kk) if (lab == i).sum() >= 6])
    print(f"elem {k}: holes {len(cs)}, width {umax-umin:.3f}, left margin {cs[:,0].min()-umin:.3f}, right margin {umax-cs[:,0].max():.3f}, bottom {cs[:,1].min()-zmin:.3f}, top {zmax-cs[:,1].max():.3f}")
