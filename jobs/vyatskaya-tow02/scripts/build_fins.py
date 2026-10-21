"""TOW02 vertical fins ("lopatki", RC_TOW_Lapatki_02) rebuilt from measurements as closed quad meshes.

Engine gap: EG6 (panelised curtain-wall source: fins that follow a curve over floors, docs/backlog.md).

Pure numpy (+ matplotlib for the comparison PNGs), no bpy. Reads outputs/measure-v001/source_npz (fins and body
#198/#201/#210) and outputs/measure-v001/typical/fins.json; writes outputs/build-v003-fins/: fins.obj (+ fins.mtl; one
object `TOW02_fin_Fxx` per fin, world coordinates, Z up), fins_summary.json and comparison PNGs.

Model (building-local frame of inspect_sections.py, fixed fin frame: u across, v outward along the fin axis, the
1.6 deg skew to the wall is kept because the axis comes from the fin, not from the wall):
  ring(z) = c(z) + M(z) . P(t(z)), horizontal rings
  c(z)  measured path = centre of the source fin's horizontal section extents (every 0.05 m);
  P(t)  10-vertex profile (A 0.70 x 1.50 / B 0.95 x 1.35, same topology), vertex-wise linear A<->B with t linear in z
        from the measured morph start (~4.5) to the fin top;
  M(z)  stretch sqrt(1 + |c'|^2) along the slope direction (horizontal section of the swept profile).
Only the part outside the body is kept: the inner face sits at a fixed v (from the path) = the lowest outermost body
face (#198/#201/#210, sampled over the fin width every 0.05 m, z >= Z_STEP) minus EMBED. Below Z_STEP (colonnade, slab
underside 7.30 + EMBED) the whole profile is free-standing: 12-vertex rings and a hidden step face at Z_STEP. A fin
whose cut would come within MIN_CUT of its back (body behind the back somewhere) keeps the full profile.
Rings: 0, 2.25, 4.5 (sides < 3.8 m), S-curve rings every <= 1.7 m with ring chord error <= 8 mm, Z_STEP, then
<= 3.75 m to the top. Faces: notch faces = edge material (#204 / #221), everything else = fin material (#219 / #220).
A top cap that would lie on a body face of the same level (roof / ledge at 72.20 or 65.40) is moved by -CAP_DROP:
raised 8 mm above that face (user 2026-10-20 "+8 мм над кровлей"; >= 5 mm gap between parallel faces).

    py -3 jobs/vyatskaya-tow02/scripts/build_fins.py [output folder name under outputs/, default build-v003-fins]
"""
import json
import math
import re
import sys
import time
from pathlib import Path

import numpy as np

JOB = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(JOB / "scripts"))
from inspect_sections import LOCAL_ANGLE_DEG, load  # noqa: E402

MEAS = JOB / "outputs" / "measure-v001"
OUT = JOB / "outputs" / (sys.argv[1] if len(sys.argv) > 1 else "build-v003-fins")

EMBED = 0.010              # fin inner face at least this deep inside the body face (user rule)
CHORD_TOL = 0.008          # ring-to-ring chord error vs the measured model
BEND_MAX_STEP = 1.7
MAX_STEP = 3.75            # quads < 3.8 m per side
Z_STEP = 7.31              # slab underside 7.30 (bend_top/soffit.json) + EMBED; colonnade below
CAP_DROP = -0.008          # negative = raised: top cap 8 mm above a body face of the same level (user 2026-10-20)
MIN_CUT = 0.05             # keep the full profile if the cut is closer than this to the fin back
DZ = 0.05
Z_OFF = 0.013              # sample grid offset: keeps cuts off the source's horizontal faces (2-decimal levels)
BODY_MATS = ("#198", "#201", "#210")       # glass, frames/mullions, spandrels/piers
FIXED_LOW = (0.0, 2.25, 4.5)

# profile vertex order (right = +u): back R, chamfer R, tip-out R, tip-in R, notch R, notch L, tip-in L, ... back L
NOTCH_EDGES = {(3, 4), (4, 5), (5, 6)}       # loop edges (10-vertex indices) carrying the edge material


# ----------------------------------------------------------------------------------------------- geometry helpers
def hcut(co, tri, z):
    """Horizontal section of a triangle soup -> segments (k, 2, 2) in xy."""
    s = co[tri, 2] - z
    sel = (s.min(1) < 0) & (s.max(1) > 0)
    P, s = co[tri[sel]], s[sel]
    out = np.zeros((len(P), 2, 2))
    k = np.zeros(len(P), int)
    for a, b in ((0, 1), (1, 2), (2, 0)):
        c = s[:, a] * s[:, b] < 0
        t = s[c, a] / (s[c, a] - s[c, b])
        p = P[c, a, :2] + (P[c, b, :2] - P[c, a, :2]) * t[:, None]
        idx = np.where(c)[0]
        out[idx, np.minimum(k[idx], 1)] = p
        k[idx] += 1
    return out[k == 2]


def point_tri_dist(p, a, b, c):
    """Distance from points p (n,3) to triangles (n,3 each), pairwise (Ericson, vectorised)."""
    ab, ac, ap = b - a, c - a, p - a
    d1, d2 = (ab * ap).sum(-1), (ac * ap).sum(-1)
    bp = p - b
    d3, d4 = (ab * bp).sum(-1), (ac * bp).sum(-1)
    cp = p - c
    d5, d6 = (ab * cp).sum(-1), (ac * cp).sum(-1)
    va, vb, vc = d3 * d6 - d5 * d4, d5 * d2 - d1 * d6, d1 * d4 - d3 * d2
    den = np.where(np.abs(va + vb + vc) < 1e-18, 1e-18, va + vb + vc)
    v, w = vb / den, vc / den
    q = a + ab * v[..., None] + ac * w[..., None]
    sd = lambda x, y: x / np.where(np.abs(y) < 1e-18, 1e-18, y)  # noqa: E731
    r1 = (d1 <= 0) & (d2 <= 0)
    r2 = (d3 >= 0) & (d4 <= d3)
    r3 = (vc <= 0) & (d1 >= 0) & (d3 <= 0)
    r4 = (d6 >= 0) & (d5 <= d6)
    r5 = (vb <= 0) & (d2 >= 0) & (d6 <= 0)
    r6 = (va <= 0) & ((d4 - d3) >= 0) & ((d5 - d6) >= 0)
    q = np.where(r6[..., None], b + (c - b) * sd(d4 - d3, (d4 - d3) + (d5 - d6))[..., None], q)
    q = np.where(r5[..., None], a + ac * sd(d2, d2 - d6)[..., None], q)
    q = np.where(r4[..., None], c, q)
    q = np.where(r3[..., None], a + ab * sd(d1, d1 - d3)[..., None], q)
    q = np.where(r2[..., None], b, q)
    q = np.where(r1[..., None], a, q)
    return np.linalg.norm(p - q, axis=-1)


def nearest_dist(pts, tris, chunk=400):
    """Min distance from each point (n,3) to a set of triangles (m,3,3)."""
    if len(tris) == 0 or len(pts) == 0:
        return np.full(len(pts), np.inf)
    out = np.empty(len(pts))
    A, B, C = tris[None, :, 0], tris[None, :, 1], tris[None, :, 2]
    for i in range(0, len(pts), chunk):
        p = pts[i:i + chunk, None, :]
        out[i:i + chunk] = point_tri_dist(p, A, B, C).min(1)
    return out


def sample_tris(tris, step):
    """Points on triangles (m,3,3) with spacing <= step (barycentric grid)."""
    out = []
    L = np.max(np.linalg.norm(tris - np.roll(tris, 1, 1), axis=2), axis=1)
    n = np.maximum(1, np.ceil(L / step).astype(int))
    for k in np.unique(n):
        T = tris[n == k]
        ij = np.array([(i, j) for i in range(k + 1) for j in range(k + 1 - i)], float) / k
        w = np.c_[1 - ij.sum(1), ij]
        out.append(np.einsum("pk,tkd->tpd", w, T).reshape(-1, 3))
    return np.concatenate(out) if out else np.zeros((0, 3))


def inside_polygon(p, poly):
    """Crossing-number point-in-polygon, p (n,2), poly closed (m+1,2)."""
    x, y = p[:, 0][:, None], p[:, 1][:, None]
    x0, y0, x1, y1 = poly[:-1, 0][None], poly[:-1, 1][None], poly[1:, 0][None], poly[1:, 1][None]
    cond = (y0 > y) != (y1 > y)
    xi = x0 + (y - y0) * (x1 - x0) / np.where(np.abs(y1 - y0) < 1e-15, 1e-15, y1 - y0)
    return ((cond & (x < xi)).sum(1) % 2) == 1


def to_world(xy):
    a = math.radians(LOCAL_ANGLE_DEG)
    c, s = math.cos(a), math.sin(a)
    return np.c_[xy[:, 0] * c - xy[:, 1] * s, xy[:, 0] * s + xy[:, 1] * c]


# ----------------------------------------------------------------------------------------------- profile templates
def profile_params(loop):
    """10-vertex symmetric profile parameters from a measured loop (u across, v outward, rect centre origin):
    [W half width, vb back, vc chamfer start, ut1 tip outer, vt tip, ut2 tip inner, un notch, vn notch bottom]."""
    p = np.unique(np.round(np.array(loop, float), 4), axis=0)
    u, v = p[:, 0], p[:, 1]
    au = np.abs(u)
    W, vt, vb = au.max(), v.max(), v.min()
    vc = v[au > W - 0.01].max()
    top = v > vt - 0.01
    ut1, ut2 = au[top].max(), au[top].min()
    notch = (au < ut2 - 0.01) & (v < vt - 0.05) & (v > vc)
    return np.array([W, vb, vc, ut1, vt, ut2, au[notch].max(), v[notch].mean()])


def profile_points(q):
    """(10,2) loop from parameters, order back R .. back L (u, v)."""
    W, vb, vc, ut1, vt, ut2, un, vn = q
    R = [(W, vb), (W, vc), (ut1, vt), (ut2, vt), (un, vn)]
    L = [(-x, y) for x, y in R[::-1]]
    return np.array(R + L)


# ----------------------------------------------------------------------------------------------- per-fin model
class Fin:
    def __init__(self, f, templates):
        self.f = f
        self.id = f["id"]
        a = math.radians(f["axis_angle_deg"])
        self.ax = np.array([math.cos(a), math.sin(a)])
        self.nr = np.array([-self.ax[1], self.ax[0]])
        self.o = np.array(f["base_rect_centre"], float)
        self.z_top = float(f["z_top"])
        self.z_cap = self.z_top
        self.morph = f["profile_morph"]                         # 'A->B' or 'B->A'
        qa, qb = templates["A"], templates["B"]
        self.q0, self.q1 = (qa, qb) if self.morph == "A->B" else (qb, qa)
        self.face_mat, self.edge_mat = f["face_mat"], f["edge_mat"]

    # frame
    def to_uv(self, xy):
        d = xy - self.o
        return np.stack([d @ self.nr, d @ self.ax], -1)

    def to_xy(self, uv):
        return self.o + uv[..., :1] * self.nr + uv[..., 1:2] * self.ax

    def predicted_centre(self, z):
        ks = sorted((float(k), v) for k, v in self.f["positions"].items() if v)
        zz = [k for k, _ in ks]
        return np.stack([np.interp(z, zz, [v["rect_centre"][0] for _, v in ks]),
                         np.interp(z, zz, [v["rect_centre"][1] for _, v in ks])], -1)

    # measured path
    def measure_path(self, fco, ftri):
        P = fco[ftri]
        cz = P[:, :, 2].mean(1)
        cxy = P[:, :, :2].mean(1)
        near = np.linalg.norm(cxy - self.predicted_centre(cz), axis=1) < 1.3
        self.tri = ftri[near]
        self.src_tris = fco[self.tri]
        zs = np.unique(np.r_[0.005, np.arange(Z_OFF, self.z_top, DZ), self.z_top - 0.005])
        rows = []
        for z in zs:
            S = hcut(fco, self.tri, z)
            if len(S) < 6:
                rows.append([z] + [np.nan] * 4)
                continue
            uv = self.to_uv(S.reshape(-1, 2))
            rows.append([z, uv[:, 0].min(), uv[:, 0].max(), uv[:, 1].min(), uv[:, 1].max()])
        r = np.array(rows)
        z = r[:, 0]
        ok = np.isfinite(r[:, 1])
        # glitch filter: a sample must agree with the median of its neighbours (width, depth, centre) within 4 mm;
        # removes cuts through the source's joint slivers between fin pieces (e.g. z 4.505-4.52)
        feats = np.c_[r[:, 2] - r[:, 1], r[:, 4] - r[:, 3], (r[:, 1] + r[:, 2]) / 2, (r[:, 3] + r[:, 4]) / 2]
        for _ in range(3):
            idx = np.where(ok)[0]
            F_ = feats[idx]
            med = np.array([np.median(F_[max(0, i - 3):i + 4], 0) for i in range(len(idx))])
            bad = np.abs(F_ - med).max(1) > 0.004
            ok[idx[bad]] = False
        self.n_path_rejected = int((~ok).sum())
        self.pz = z[ok]
        self.pc = np.c_[(r[ok, 1] + r[ok, 2]) / 2, (r[ok, 3] + r[ok, 4]) / 2]
        self.pw, self.pd = feats[ok, 0], feats[ok, 1]
        self.src_ext = r[ok]                                  # z, umin, umax, vmin, vmax (fixed frame)

    def c(self, z):
        z = np.atleast_1d(z)
        return np.stack([np.interp(z, self.pz, self.pc[:, 0]), np.interp(z, self.pz, self.pc[:, 1])], -1)

    def slope(self, z, h=0.25):
        z = np.atleast_1d(z)
        lo, hi = np.maximum(z - h, 0.0), np.minimum(z + h, self.z_top)
        return (self.c(hi) - self.c(lo)) / (hi - lo)[:, None]

    def fit_morph(self):
        """Morph start: width of the perpendicular section is linear in z from z_m0 to the top (t = 1 at the top)."""
        z = self.pz
        s = self.slope(z)
        k = np.sqrt(1 + (s ** 2).sum(1))
        su = np.divide(s[:, 0], np.linalg.norm(s, axis=1), out=np.zeros(len(z)), where=np.linalg.norm(s, axis=1) > 1e-9)
        wp = self.pw / (1 + (k - 1) * su ** 2)
        m = (z > 6) & (z < self.z_top - 0.3)
        p = np.polyfit(z[m], wp[m], 1)
        w0 = 2 * self.q0[0]
        self.z_m0 = float((w0 - p[1]) / p[0])
        self.morph_fit = dict(z_start=self.z_m0, width_top_fit=float(np.polyval(p, self.z_top)),
                              width_top_template=float(2 * self.q1[0]),
                              residual_max=float(np.abs(wp[m] - np.polyval(p, z[m])).max()))

    def t(self, z):
        return np.clip((np.atleast_1d(z) - self.z_m0) / (self.z_top - self.z_m0), 0, 1)

    def stretch(self, z):
        """(n,2,2) matrices in (u,v): I + (k-1) s^ s^T."""
        s = self.slope(z)
        n = np.linalg.norm(s, axis=1)
        k = np.sqrt(1 + n ** 2)
        sh = np.divide(s, n[:, None], out=np.zeros_like(s), where=n[:, None] > 1e-9)
        return np.eye(2)[None] + (k - 1)[:, None, None] * sh[:, :, None] * sh[:, None, :]

    def prof(self, z):
        """Profile parameters (n,8) at z."""
        t = self.t(z)[:, None]
        return self.q0[None] * (1 - t) + self.q1[None] * t

    def ring_uv(self, z, kind):
        """Ring points (n, nv, 2) in the fixed frame. kind: 'full' (10, back corners), 'cut' (10, inner corners at
        v_in), 'cut12' (12: back R, inner R, ..., inner L, back L)."""
        z = np.atleast_1d(z)
        q = self.prof(z)
        P = np.stack([profile_points(x) for x in q])                       # (n,10,2)
        M = self.stretch(z)
        H = np.einsum("nij,nkj->nki", M, P) + self.c(z)[:, None, :]
        if kind == "full":
            return H
        # inner side points: profile (+-W, vp) with (M p)_v = v_in (relative to c)
        W = q[:, 0]
        inner = []
        for sgn in (1.0, -1.0):
            vp = (self.v_in - M[:, 1, 0] * sgn * W) / M[:, 1, 1]
            p = np.stack([sgn * W, vp], -1)
            inner.append(np.einsum("nij,nj->ni", M, p) + self.c(z))
        iR, iL = inner
        if kind == "cut":
            return np.concatenate([iR[:, None], H[:, 1:9], iL[:, None]], 1)
        return np.concatenate([H[:, :1], iR[:, None], H[:, 1:9], iL[:, None], H[:, 9:]], 1)

    def ring_kind(self, z):
        if not self.cut:
            return "full"
        return "cut12" if z <= Z_STEP + 1e-9 else "cut"

    # rings
    def chord_error(self, z0, z1):
        zz = self.pz[(self.pz > z0) & (self.pz < z1)]
        if len(zz) == 0:
            return 0.0
        kind = "full" if (not self.cut or z1 <= Z_STEP + 1e-9) else "cut"
        R0, R1 = self.ring_uv(z0, kind)[0], self.ring_uv(z1, kind)[0]
        tt = ((zz - z0) / (z1 - z0))[:, None, None]
        exact = self.ring_uv(zz, kind)
        return float(np.linalg.norm(exact - (R0 * (1 - tt) + R1 * tt), axis=2).max())

    def place_rings(self, z_bend_end):
        brk = [0.0, 2.25, 4.5]
        stops = sorted({4.5, z_bend_end, self.z_cap} | ({Z_STEP} if self.cut else set()))
        zs = list(brk)
        self.ring_notes = []
        for a, b in zip(stops[:-1], stops[1:]):
            mx = BEND_MAX_STEP if b <= z_bend_end + 1e-9 else MAX_STEP
            cur = a
            while cur < b - 1e-9:
                cand = np.r_[np.arange(cur + 0.05, min(b, cur + mx) - 1e-9, 0.05), min(b, cur + mx)]
                best = None
                for zc in cand[::-1]:
                    if self.chord_error(cur, zc) <= CHORD_TOL:
                        best = zc
                        break
                if best is None:
                    best = cand[0]
                    self.ring_notes.append(f"chord > tol at {cur:.2f}")
                zs.append(round(float(best), 4))
                cur = best
        self.rings = sorted(set(round(z, 4) for z in zs))
        self.chord_max = max(self.chord_error(a, b) for a, b in zip(self.rings[:-1], self.rings[1:]))


# ----------------------------------------------------------------------------------------------- body sampling
def body_samples(fins, bco, btri):
    """For every fin: rows (z, u_rel, v_rel_outermost) and all hits (z, u_abs, v_abs) of the body along rays parallel
    to the fin axis, across the fin width, z >= Z_STEP - 0.4."""
    boxes = []
    for fn in fins:
        xy = fn.to_xy(np.c_[fn.pc[:, 0], fn.pc[:, 1]])
        boxes.append((xy.min(0) - 2.5, xy.max(0) + 2.5))
    P = bco[btri]
    lo, hi = P.min(1), P.max(1)
    keep = np.zeros(len(btri), bool)
    for b0, b1 in boxes:
        keep |= (hi[:, 0] > b0[0]) & (lo[:, 0] < b1[0]) & (hi[:, 1] > b0[1]) & (lo[:, 1] < b1[1])
    keep &= hi[:, 2] > Z_STEP - 0.5
    btri = btri[keep]
    zs = np.arange(Z_STEP - 0.4 + Z_OFF, 72.2, DZ)
    res = {fn.id: dict(rows=[], hits=[]) for fn in fins}
    for z in zs:
        S = hcut(bco, btri, z)
        if len(S) == 0:
            continue
        mid = S.mean(1)
        for fn in fins:
            if z > fn.z_top - 0.003:
                continue
            c = fn.c(z)[0]
            cxy = fn.to_xy(c)
            sel = np.linalg.norm(mid - cxy, axis=1) < 3.0
            if not sel.any():
                continue
            Q = fn.to_uv(S[sel].reshape(-1, 2)).reshape(-1, 2, 2) - c
            q = fn.prof(np.array([z]))[0]
            hw = fn.ring_uv(np.array([z]), "full")[0][:, 0] - c[0]
            us = np.linspace(hw.min() + 0.005, hw.max() - 0.005, 25)
            U0, U1, V0, V1 = Q[:, 0, 0], Q[:, 1, 0], Q[:, 0, 1], Q[:, 1, 1]
            span = (np.minimum(U0, U1)[:, None] <= us) & (np.maximum(U0, U1)[:, None] >= us) & \
                (np.abs(U1 - U0)[:, None] > 1e-9)
            tt = (us[None] - U0[:, None]) / np.where(np.abs(U1 - U0) > 1e-9, U1 - U0, 1)[:, None]
            V = V0[:, None] + tt * (V1 - V0)[:, None]
            vt = q[4] * 1.02 + 0.05
            valid = span & (V <= vt) & (V >= -1.8)
            Vm = np.where(valid, V, -np.inf).max(0)
            for u, v in zip(us, Vm):
                res[fn.id]["rows"].append((z, u, v))
            ii, jj = np.nonzero(valid)
            for i, j in zip(ii, jj):
                res[fn.id]["hits"].append((z, us[j] + c[0], V[i, j] + c[1]))
    for k in res:
        res[k] = {kk: np.array(vv) for kk, vv in res[k].items()}
        rows = res[k]["rows"]
        if len(rows):
            E = rows[:, 2].reshape(-1, 25)                  # (z, u) grid, 25 rays per height
            bad = np.isinf(E)
            n_bad = np.zeros_like(E)
            Ep = np.pad(np.where(bad, 1.0, 0.0), 1)
            for di in (-1, 0, 1):
                for dj in (-1, 0, 1):
                    n_bad += Ep[1 + di:1 + di + E.shape[0], 1 + dj:1 + dj + E.shape[1]]
            iso = bad & (n_bad == 1)                        # a lone ray through a crack of the source mesh
            Ef = np.pad(np.where(bad, np.inf, E), 1, constant_values=np.inf)
            nb = np.full(E.shape, np.inf)
            for di in (-1, 0, 1):
                for dj in (-1, 0, 1):
                    if di or dj:
                        nb = np.minimum(nb, Ef[1 + di:1 + di + E.shape[0], 1 + dj:1 + dj + E.shape[1]])
            E[iso] = nb[iso]
            rows[:, 2] = E.ravel()
            res[k]["bridged_rays"] = int(iso.sum())
    return res


def outline_samples(fn, outline_edges, z_range=(37.5, 64.7)):
    """Outermost face of the typical body outline (recessed intervals at outline - depth) along the same rays."""
    rows = []
    segs = []
    for e in outline_edges:
        a, b = np.array(e["a"]), np.array(e["b"])
        d = (b - a) / e["length"]
        nrm = np.array([d[1], -d[0]])                       # outward = right of a CCW edge
        cuts = [(0.0, e["length"], 0.0)]
        if e["intervals"]:
            cuts = [(iv["t0"], iv["t1"], iv["depth_median"] if iv["kind"].startswith("recessed") else 0.0)
                    for iv in e["intervals"]]
        for t0, t1, dep in cuts:
            segs.append((a + d * t0 - nrm * dep, a + d * t1 - nrm * dep))
    segs = np.array(segs)
    zs = fn.pz[(fn.pz >= z_range[0]) & (fn.pz <= min(z_range[1], fn.z_top))]
    for z in zs[::4]:
        c = fn.c(z)[0]
        Q = fn.to_uv(segs.reshape(-1, 2)).reshape(-1, 2, 2) - c
        hw = fn.ring_uv(np.array([z]), "full")[0][:, 0] - c[0]
        us = np.linspace(hw.min() + 0.005, hw.max() - 0.005, 25)
        U0, U1, V0, V1 = Q[:, 0, 0], Q[:, 1, 0], Q[:, 0, 1], Q[:, 1, 1]
        span = (np.minimum(U0, U1)[:, None] <= us) & (np.maximum(U0, U1)[:, None] >= us) & \
            (np.abs(U1 - U0)[:, None] > 1e-9)
        tt = (us[None] - U0[:, None]) / np.where(np.abs(U1 - U0) > 1e-9, U1 - U0, 1)[:, None]
        V = V0[:, None] + tt * (V1 - V0)[:, None]
        valid = span & (V <= 1.0) & (V >= -1.8)
        Vm = np.where(valid, V, -np.inf).max(0)
        rows += [(z, u, v) for u, v in zip(us, Vm)]
    return np.array(rows) if rows else np.zeros((0, 3))


# ----------------------------------------------------------------------------------------------- mesh
def build_mesh(fn):
    """Vertices (n,3) local, quads (list of 4-tuples), materials per quad, face roles."""
    verts, quads, mats, roles = [], [], [], []
    ring_idx = []

    def add(pts, z):
        i0 = len(verts)
        for p in pts:
            verts.append((p[0], p[1], z))
        return list(range(i0, i0 + len(pts)))

    # orientation: profile loop must be CCW in plan
    test = fn.to_xy(fn.ring_uv(np.array([fn.z_top - 0.01]), "full")[0])
    area = 0.5 * np.sum(test[:, 0] * np.roll(test[:, 1], -1) - np.roll(test[:, 0], -1) * test[:, 1])
    ccw = area > 0

    def loop(idx):
        return idx if ccw else idx[::-1]

    rings = []
    for z in fn.rings:
        kind = fn.ring_kind(z)
        if kind == "cut12":
            pts12 = fn.to_xy(fn.ring_uv(np.array([z]), "cut12")[0])
            ids12 = add(pts12, z)
            if abs(z - Z_STEP) < 1e-9:
                rings.append(("cut12", ids12))
                rings.append(("cut", ids12[1:11]))
            else:
                rings.append(("cut12", ids12))
        else:
            pts = fn.to_xy(fn.ring_uv(np.array([z]), kind)[0])
            rings.append((kind, add(pts, z)))

    def notch_edge(kind, i, n):
        j = (i + 1) % n
        if kind == "cut12":
            i, j = i - 1, j - 1                         # 12 -> 10 numbering (back corners excluded)
        return (i, j) in NOTCH_EDGES

    for (k0, r0), (k1, r1) in zip(rings[:-1], rings[1:]):
        if r1 == r0[1:11]:                               # the step pair at Z_STEP
            q = (r0[0], r0[1], r0[10], r0[11])           # back R, inner R, inner L, back L  -> normal +z
            quads.append(q if ccw else q[::-1])
            mats.append(fn.face_mat)
            roles.append("step")
            continue
        n = len(r0)
        for i in range(n):
            j = (i + 1) % n
            q = (r0[i], r0[j], r1[j], r1[i])
            quads.append(q if ccw else (r0[j], r0[i], r1[i], r1[j]))
            mats.append(fn.edge_mat if notch_edge(k0, i, n) else fn.face_mat)
            role = "side"
            if k0 == "cut" and i == n - 1:
                role = "inner"
            if k0 in ("full", "cut12") and i == n - 1:
                role = "back"
            roles.append(role)

    def cap(kind, r, up):
        if kind == "cut12":
            groups = [(r[0], r[1], r[10], r[11])] + [tuple(r[1:11][k] for k in g) for g in
                                                     [(0, 1, 8, 9), (1, 2, 3, 4), (1, 4, 5, 8), (5, 6, 7, 8)]]
        else:
            groups = [tuple(r[k] for k in g) for g in [(0, 1, 8, 9), (1, 2, 3, 4), (1, 4, 5, 8), (5, 6, 7, 8)]]
        for g in groups:
            # profile order is CW-in-(u,v) == CCW in plan when ccw; up cap keeps loop order, down cap reverses
            g = g if (up == ccw) else g[::-1]
            quads.append(g)
            mats.append(fn.face_mat)
            roles.append("cap_top" if up else "cap_bottom")

    cap(*rings[0], up=False)
    cap(*rings[-1], up=True)
    V = np.array(verts)
    return V, quads, mats, roles


def check_mesh(V, quads):
    """Closedness, orientation, signed volume, planarity, convexity, sizes."""
    from collections import Counter
    de = Counter()
    for q in quads:
        for i in range(4):
            de[(q[i], q[(i + 1) % 4])] += 1
    und = Counter()
    for (a, b), n in de.items():
        und[tuple(sorted((a, b)))] += n
    open_e = sum(1 for e, n in und.items() if n == 1)
    nonman = sum(1 for e, n in und.items() if n > 2)
    bad_orient = sum(1 for (a, b), n in de.items() if n > 1 or de.get((b, a), 0) != 1)
    Q = V[np.array(quads)]
    vol = 0.0
    for t in ((0, 1, 2), (0, 2, 3)):
        a, b, c = Q[:, t[0]], Q[:, t[1]], Q[:, t[2]]
        vol += np.einsum("ij,ij->i", a, np.cross(b, c)).sum() / 6
    side = np.linalg.norm(Q - np.roll(Q, -1, 1), axis=2)
    n1 = np.cross(Q[:, 1] - Q[:, 0], Q[:, 3] - Q[:, 0])
    n2 = np.cross(Q[:, 3] - Q[:, 2], Q[:, 1] - Q[:, 2])
    diag = np.linalg.norm(Q[:, 2] - Q[:, 0], axis=1)
    nonplanar = np.abs(np.einsum("ij,ij->i", Q[:, 2] - Q[:, 0], np.cross(Q[:, 1] - Q[:, 0], Q[:, 3] - Q[:, 0])))
    nonplanar = nonplanar / np.maximum(np.linalg.norm(np.cross(Q[:, 1] - Q[:, 0], Q[:, 3] - Q[:, 0]), axis=1), 1e-12)
    convex = (np.einsum("ij,ij->i", n1, n2) > 0)
    area = 0.5 * (np.linalg.norm(n1, axis=1) + np.linalg.norm(n2, axis=1))
    return dict(open_edges=open_e, non_manifold_edges=nonman, inconsistent_edges=bad_orient,
                signed_volume_m3=float(vol), outward=bool(vol > 0), quads=len(quads), tris=0, ngons=0,
                max_side_m=float(side.max()), min_side_m=float(side.min()), min_area_m2=float(area.min()),
                max_nonplanarity_m=float(nonplanar.max()), nonconvex_quads=int((~convex).sum()),
                max_diag_m=float(diag.max()))


# ----------------------------------------------------------------------------------------------- deviation
def deviation(fn, V, quads, roles):
    """Model surface -> source fin surface and source (modelled part) -> model, metres."""
    Q = V[np.array(quads)]
    T = np.concatenate([Q[:, [0, 1, 2]], Q[:, [0, 2, 3]]])
    R = np.r_[roles, roles]
    src_all = fn.src_tris
    nrm = np.cross(src_all[:, 1] - src_all[:, 0], src_all[:, 2] - src_all[:, 0])
    nz = np.abs(nrm[:, 2]) / np.maximum(np.linalg.norm(nrm, axis=1), 1e-12)
    zc = src_all[:, :, 2].mean(1)
    src_side = src_all[nz < 0.9]                               # (near-)horizontal faces are internal joints ...
    src = src_all[(nz < 0.9) | (zc < 0.01) | (zc > fn.z_top - 0.01)]    # ... except the real bottom and top
    # model -> source (inner face and step face are cuts, not on the source surface)
    mt = T[~np.isin(R, ["inner", "step"])]
    pts = sample_tris(mt, 0.12)
    d_ms = np.empty(len(pts))
    slo, shi = src[:, :, 2].min(1), src[:, :, 2].max(1)
    order = np.argsort(pts[:, 2])
    pts = pts[order]
    for i in range(0, len(pts), 300):
        p = pts[i:i + 300]
        z0, z1 = p[:, 2].min() - 0.05, p[:, 2].max() + 0.05
        cand = src[(shi >= z0) & (slo <= z1)]
        d_ms[i:i + 300] = nearest_dist(p, cand)
    # source -> model: points of the modelled part only
    sp = sample_tris(src_side, 0.10)
    sp = sp[(sp[:, 2] > 0.003) & (sp[:, 2] < fn.z_top - 0.003)]
    if fn.cut:
        uv = fn.to_uv(sp[:, :2]) - fn.c(sp[:, 2])
        keep = (sp[:, 2] <= Z_STEP) | (uv[:, 1] > fn.v_in + 0.015)
        sp = sp[keep]
    # source faces deep inside the model are the source's internal joint/overlap faces (the source fin is built of
    # overlapping pieces); points outside the model are always kept, and a too fat model shows in model->source
    inside_deep = np.zeros(len(sp), bool)
    zr = np.round(sp[:, 2] / 0.02) * 0.02
    for zq in np.unique(zr):
        m = zr == zq
        poly = model_section(fn, float(zq))
        inside_deep[m] = inside_polygon(sp[m, :2], poly)
    order = np.argsort(sp[:, 2])
    sp, inside_deep = sp[order], inside_deep[order]
    mlo, mhi = T[:, :, 2].min(1), T[:, :, 2].max(1)
    d_sm = np.empty(len(sp))
    for i in range(0, len(sp), 300):
        p = sp[i:i + 300]
        z0, z1 = p[:, 2].min() - 0.05, p[:, 2].max() + 0.05
        cand = T[(mhi >= z0) & (mlo <= z1)]
        d_sm[i:i + 300] = nearest_dist(p, cand)
    internal = inside_deep & (d_sm > 0.015)
    n_internal = int(internal.sum())
    d_sm = d_sm[~internal]
    sp = sp[~internal]
    worst = sp[np.argmax(d_sm)] if len(sp) else None
    # source piece joints (near-horizontal internal faces): the source has slivers/folds within a few cm of them
    jz = np.unique(np.round(zc[(nz >= 0.9) & (zc > 0.01) & (zc < fn.z_top - 0.01)], 2))
    def off_joint(zz):
        if len(jz) == 0:
            return np.ones(len(zz), bool)
        return np.abs(zz[:, None] - jz[None]).min(1) > 0.05
    om, os_ = off_joint(pts[:, 2]), off_joint(sp[:, 2])

    def where(p):
        q = fn.to_uv(p[:2]) - fn.c(p[2])[0]
        return dict(z=float(p[2]), u=float(q[0]), v=float(q[1]))
    w_off = dict(model_to_source=where(pts[om][np.argmax(d_ms[om])]), source_to_model=where(sp[os_][np.argmax(d_sm[os_])]))
    wm = pts[np.argmax(d_ms)]
    wm_uv = fn.to_uv(wm[:2]) - fn.c(wm[2])[0]
    return dict(model_to_source_worst_at=dict(z=float(wm[2]), u=float(wm_uv[0]), v=float(wm_uv[1])),
                model_to_source_max=float(d_ms.max()), model_to_source_p95=float(np.percentile(d_ms, 95)),
                source_to_model_max=float(d_sm.max()), source_to_model_p95=float(np.percentile(d_sm, 95)),
                model_to_source_max_off_joints=float(d_ms[om].max()),
                source_to_model_max_off_joints=float(d_sm[os_].max()),
                worst_off_joints_at=w_off, source_joint_levels=[float(x) for x in jz],
                n_model_pts=int(len(pts)), n_source_pts=int(len(sp)), n_source_internal_pts_excluded=n_internal,
                source_to_model_worst_z=float(worst[2]) if worst is not None else None)


def inner_face_v(fn, V, quads, roles, z, ua):
    """v (fixed frame) of the model's inner face at heights z and across-positions ua (arrays); nan outside it."""
    inner = {}
    for q, role in zip(quads, roles):
        if role == "inner":
            for vi in q:
                inner.setdefault(round(V[vi, 2], 4), []).append(fn.to_uv(V[vi, :2]))
    zk = np.array(sorted(inner))
    A = np.array([np.unique(np.round(np.array(inner[k]), 7), axis=0) for k in zk])     # (nr, 2, 2) sorted by u
    k = np.clip(np.searchsorted(zk, z) - 1, 0, len(zk) - 2)
    tt = ((z - zk[k]) / (zk[k + 1] - zk[k]))[:, None, None]
    L = A[k] * (1 - tt) + A[k + 1] * tt                           # (n, 2, 2): inner face line at each z
    s_ = (ua - L[:, 0, 0]) / (L[:, 1, 0] - L[:, 0, 0])
    vf = L[:, 0, 1] + s_ * (L[:, 1, 1] - L[:, 0, 1])
    return np.where((s_ >= -0.01) & (s_ <= 1.01) & (z >= zk[0]) & (z <= zk[-1]), vf, np.nan)


def embed_check(fn, rows, V, quads, roles):
    """Embed of the model's inner face below the outermost body face at every sampled (z, u): body v - face v."""
    if not fn.cut or len(rows) == 0:
        return None
    r = rows[rows[:, 0] >= Z_STEP]
    c = fn.c(r[:, 0])
    ua = r[:, 1] + c[:, 0]
    vf = inner_face_v(fn, V, quads, roles, r[:, 0], ua)
    e = r[:, 2] + c[:, 1] - vf
    ok = np.isfinite(vf)
    return np.c_[r[ok, 0], ua[ok], e[ok]]


def cap_overlap(fn, V, quads, roles, htris):
    """Share and area of the model top cap lying on a horizontal body face at the same level (+-5 mm)."""
    Q = V[np.array([q for q, r in zip(quads, roles) if r == "cap_top"])]
    T = np.concatenate([Q[:, [0, 1, 2]], Q[:, [0, 2, 3]]])
    area = 0.5 * np.linalg.norm(np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]), axis=1).sum()
    if len(htris) == 0:
        return dict(share=0.0, area_m2=0.0, cap_area_m2=float(area))
    p = sample_tris(T, 0.02)[:, :2]
    a, b, c = htris[:, 0, :2], htris[:, 1, :2], htris[:, 2, :2]
    inside = np.zeros(len(p), bool)
    for i in range(0, len(p), 500):
        q = p[i:i + 500, None, :]
        v0, v1, v2 = c - a, b - a, q - a
        d00, d01, d11 = (v0 * v0).sum(-1), (v0 * v1).sum(-1), (v1 * v1).sum(-1)
        d20, d21 = (v2 * v0).sum(-1), (v2 * v1).sum(-1)
        den = np.where(np.abs(d00 * d11 - d01 * d01) < 1e-18, 1e-18, d00 * d11 - d01 * d01)
        u_ = (d11 * d20 - d01 * d21) / den
        v_ = (d00 * d21 - d01 * d20) / den
        inside[i:i + 500] = ((u_ >= -1e-9) & (v_ >= -1e-9) & (u_ + v_ <= 1 + 1e-9)).any(1)
    return dict(share=float(inside.mean()), area_m2=float(inside.mean() * area), cap_area_m2=float(area))


def coplanar_check(fn, hits, V, quads, roles, tol=0.005):
    """Body faces lying in the inner face plane: per sampled height, the share of rays with a body hit within tol of
    the inner face. Returns (max share, heights with share > 0.3)."""
    h = hits[hits[:, 0] >= Z_STEP]
    vf = inner_face_v(fn, V, quads, roles, h[:, 0], h[:, 1])
    near = np.abs(h[:, 2] - vf) < tol
    if not near.any():
        return 0.0, 0, None
    zs = np.unique(h[:, 0])
    share = []
    for z in zs:
        m = h[:, 0] == z
        u_all = np.unique(np.round(h[m, 1], 4))
        u_near = np.unique(np.round(h[m & near, 1], 4))
        share.append(len(u_near) / max(len(u_all), 1))
    share = np.array(share)
    bad = share > 0.3
    # a body face crossing the (sloped) inner face shows on 1-2 heights; an overlap would persist over many
    run, best = 0, 0
    for k in range(len(zs)):
        run = run + 1 if bad[k] and (k == 0 or zs[k] - zs[k - 1] < DZ * 1.5) and (run or bad[k]) else (1 if bad[k] else 0)
        best = max(best, run)
    return float(share.max()), int(bad.sum()), float(best * DZ)


# ----------------------------------------------------------------------------------------------- output
_VERSION_RE = re.compile(r"^build-v(\d+)")


def next_free_fins_version(outputs: Path) -> str:
    """Next free ``build-vNNN-fins`` name under ``outputs``, skipping every version already used by a build.

    The version counter is shared with the master builds (``build-vNNN`` without a suffix), so a re-run of the
    default ``build-v003-fins`` after ``build-v013`` names ``build-v014-fins`` rather than reusing ``v013``.
    """
    max_v = 0
    if outputs.is_dir():
        for d in outputs.iterdir():
            m = _VERSION_RE.match(d.name)
            if m and d.is_dir():
                max_v = max(max_v, int(m.group(1)))
    return f"build-v{max_v + 1:03d}-fins"


def ensure_output_available(out: Path) -> None:
    """Create ``out`` if it is free; refuse (never overwrite) an existing, non-empty output version.

    An empty existing directory is reused (fresh-directory behaviour); anything else raises ``FileExistsError``
    with a clear message naming the next free version.
    """
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        raise FileExistsError(
            f"output version {out.name!r} already exists and is non-empty; refusing to overwrite it. "
            f"Use the next free version instead: {next_free_fins_version(out.parent)!r}."
        )
    out.mkdir(parents=True, exist_ok=True)


def write_obj(fins, path_obj, path_mtl, colors):
    lines = ["# TOW02 fins (build_fins.py, EG6). World coordinates, metres, Z up.", f"mtllib {path_mtl.name}"]
    off = 1
    for fn in fins:
        V = fn.V
        W = np.c_[to_world(V[:, :2]), V[:, 2]]
        lines.append(f"o TOW02_fin_{fn.id}")
        lines += [f"v {x:.5f} {y:.5f} {z:.5f}" for x, y, z in W]
        cur = None
        order = sorted(range(len(fn.quads)), key=lambda i: fn.mats[i])
        for i in order:
            m = fn.mats[i]
            if m != cur:
                lines.append(f"usemtl Material_{m.lstrip('#')}")
                cur = m
            lines.append("f " + " ".join(str(off + v) for v in fn.quads[i]))
        off += len(V)
    path_obj.write_text("\n".join(lines) + "\n", encoding="utf-8")
    mtl = []
    for m, rgb in colors.items():
        mtl += [f"newmtl Material_{m.lstrip('#')}", "Kd {:.3f} {:.3f} {:.3f}".format(*rgb), "d 1.0", ""]
    path_mtl.write_text("\n".join(mtl), encoding="utf-8")


def rnd(x, nd=4):
    if isinstance(x, dict):
        return {k: rnd(v, nd) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [rnd(v, nd) for v in x]
    if isinstance(x, (float, np.floating)):
        return None if not np.isfinite(x) else round(float(x), nd)
    if isinstance(x, np.integer):
        return int(x)
    if isinstance(x, np.bool_):
        return bool(x)
    return x


def main():
    t0 = time.time()
    ensure_output_available(OUT)
    data = json.loads((MEAS / "typical" / "fins.json").read_text(encoding="utf-8"))
    typ = json.loads((MEAS / "typical" / "typical_floor.json").read_text(encoding="utf-8"))
    outline = typ["b_contour"]["body_outline_spandrel_level"]["edges"]

    # templates: average of the measured loops (A = narrow, B = wide)
    acc = {"A": [], "B": []}
    for f in data["fins"]:
        b, t = f["profile_morph"].split("->")
        acc[b].append(profile_params(f["profile_bottom"]["loop_uv_dp8mm"]))
        acc[t].append(profile_params(f["profile_top"]["loop_uv_dp8mm"]))
    templates = {k: np.mean(v, 0) for k, v in acc.items()}
    spread = {k: np.ptp(np.array(v), 0).max() for k, v in acc.items()}

    fco, ftri, fmat = load("RC_TOW_Lapatki_02")
    bco, btri, bmat = load("RC_TOW_02")
    bm = np.array([m.split()[-1] for m in bmat])
    P_ = bco[btri]
    n_ = np.cross(P_[:, 1] - P_[:, 0], P_[:, 2] - P_[:, 0])
    horiz_body = P_[np.abs(n_[:, 2]) / np.maximum(np.linalg.norm(n_, axis=1), 1e-12) > 0.999]
    btri = btri[np.isin(bm, BODY_MATS)]

    fins = [Fin(f, templates) for f in data["fins"]]
    for fn in fins:
        fn.measure_path(fco, ftri)
        fn.fit_morph()
        fn.cut = True
        fn.v_in = 0.0
    print(f"paths {time.time() - t0:.0f}s")
    samples = body_samples(fins, bco, btri)
    print(f"body {time.time() - t0:.0f}s")

    summary = dict(
        generator="jobs/vyatskaya-tow02/scripts/build_fins.py (EG6)",
        frame="OBJ in world coordinates (metres, Z up; world = local rotated back by 56.7 deg: "
              "(x c - y s, x s + y c, z)); fin frame u across, v outward along the fin axis",
        rules=dict(embed_min_m=EMBED, chord_tol_m=CHORD_TOL, bend_max_ring_step_m=BEND_MAX_STEP,
                   max_ring_step_m=MAX_STEP, z_step=Z_STEP, min_cut_m=MIN_CUT),
        templates={k: dict(zip(["half_width", "v_back", "v_chamfer", "u_tip_out", "v_tip", "u_tip_in", "u_notch",
                                "v_notch"], v.tolist())) for k, v in templates.items()},
        template_spread_max_m=spread,
        materials={"Material_219": "Material #219 (fin face, #219 fins)", "Material_204": "Material #204 (notch, #219 fins)",
                   "Material_220": "Material #220 (fin face, #220 fins)", "Material_221": "Material #221 (notch, #220 fins)",
                   "note": "all four map to material id 28 (decor) per jobs/vyatskaya-tow02/materials.json"},
        fins={})

    for fn in fins:
        s = samples[fn.id]
        rows = s["rows"]
        r = rows[rows[:, 0] >= Z_STEP]
        e_src = float(r[:, 2].min())
        orows = outline_samples(fn, outline)
        e_out = float(orows[:, 2].min()) if len(orows) else np.inf
        # back of the fin relative to the path (highest over z) -> cut must stay MIN_CUT in front of it
        zz = fn.pz[fn.pz >= Z_STEP]
        back = (fn.ring_uv(zz, "full")[:, [0, 9], 1] - fn.c(zz)[:, 1:2]).max()
        v_in = min(e_src, e_out) - EMBED
        vc_min = float((fn.ring_uv(zz, "full")[:, [1, 8], 1] - fn.c(zz)[:, 1:2]).min())
        fn.cut = bool(np.isfinite(v_in) and v_in > back + MIN_CUT and v_in < vc_min - 0.02)
        fn.v_in = float(v_in) if fn.cut else None
        hz_all = horiz_body[np.abs(horiz_body[:, :, 2].mean(1) - fn.z_top) < 0.005]
        cxy = fn.to_xy(fn.c(fn.z_top - 0.01))[0]
        hz_all = hz_all[np.linalg.norm(hz_all[:, :, :2].mean(1) - cxy, axis=1) < 20]
        top_ov_source_level = None
        for attempt in range(2):
            fn.place_rings(float(fn.f["bend_z_end"] or 33.25))
            fn.V, fn.quads, fn.mats, fn.roles = build_mesh(fn)
            emb = embed_check(fn, rows, fn.V, fn.quads, fn.roles)
            it = 0
            while fn.cut and emb is not None and len(emb) and emb[:, 2].min() < EMBED - 1e-6 and it < 5:
                fn.v_in -= (EMBED - emb[:, 2].min()) + 0.0005
                fn.place_rings(float(fn.f["bend_z_end"] or 33.25))
                fn.V, fn.quads, fn.mats, fn.roles = build_mesh(fn)
                emb = embed_check(fn, rows, fn.V, fn.quads, fn.roles)
                it += 1
            if attempt == 0:
                top_ov_source_level = cap_overlap(fn, fn.V, fn.quads, fn.roles, hz_all)
                if top_ov_source_level["share"] == 0:
                    break
                fn.z_cap = fn.z_top - CAP_DROP
        chk = check_mesh(fn.V, fn.quads)
        dev = deviation(fn, fn.V, fn.quads, fn.roles)
        # outline-based embed in the typical zone (body built from the typical outline)
        emb_out = None
        if fn.cut and len(orows):
            emb_out = embed_check(fn, orows, fn.V, fn.quads, fn.roles)
        # parallel-face clearance: all body hits vs the inner face
        clear = None
        if fn.cut:
            sh, nbad, run = coplanar_check(fn, s["hits"], fn.V, fn.quads, fn.roles)
            clear = dict(max_share_of_rays_with_body_face_within_5mm=sh, heights_over_30pct=nbad,
                         longest_run_over_30pct_m=run)
        hz = horiz_body[np.abs(horiz_body[:, :, 2].mean(1) - fn.z_cap) < 0.005]
        hz = hz[np.linalg.norm(hz[:, :, :2].mean(1) - cxy, axis=1) < 20]
        top_ov = dict(at_source_top=top_ov_source_level, z_cap=fn.z_cap,
                      at_model_cap=cap_overlap(fn, fn.V, fn.quads, fn.roles, hz))
        # source fin back exposed (body face deeper than the back), full fins only
        exposed = None
        if not fn.cut:
            vb_rel = np.interp(r[:, 0], zz, (fn.ring_uv(zz, "full")[:, [0, 9], 1] - fn.c(zz)[:, 1:2]).min(1))
            ex = r[:, 2] < vb_rel + EMBED
            exposed = dict(samples=int(ex.sum()), of=int(len(r)),
                           z_range=[float(r[ex, 0].min()), float(r[ex, 0].max())] if ex.any() else None,
                           min_body_face_rel=e_src, back_rel_max=float(back))
        n_nohit = int(np.isinf(r[:, 2]).sum())
        fn.summary = dict(
            type=fn.f["type"], face=fn.f["face"], face_mat=fn.face_mat, edge_mat=fn.edge_mat,
            z_top=fn.z_top, morph=fn.morph, morph_fit=fn.morph_fit,
            mode="cut (outside part)" if fn.cut else "full profile (body face behind the fin back somewhere)",
            v_in_from_path=fn.v_in,
            body_face_min_rel_path=dict(source=e_src, typical_outline=e_out if np.isfinite(e_out) else None),
            rings=len(fn.rings), ring_z=fn.rings, ring_notes=fn.ring_notes, chord_error_max=fn.chord_max,
            verts=int(len(fn.V)), quads=len(fn.quads),
            embed_m=None if emb is None else dict(min=float(emb[:, 2].min()), max=float(emb[:, 2].max()),
                                                   samples=int(len(emb)), z_of_min=float(emb[np.argmin(emb[:, 2]), 0])),
            embed_vs_typical_outline_m=None if emb_out is None or not len(emb_out) else
            dict(min=float(emb_out[:, 2].min()), max=float(emb_out[:, 2].max())),
            inner_face_coplanar_with_body=clear,
            top_cap_on_body_face_at_same_level=top_ov,
            source_back_exposed=exposed,
            body_rays_without_hit=n_nohit, body_rays_bridged=s.get("bridged_rays", 0),
            path_samples=int(len(fn.pz)), path_samples_rejected=fn.n_path_rejected,
            deviation_m=dev, mesh=chk)
        summary["fins"][fn.id] = fn.summary
        print(fn.id, fn.summary["mode"][:4], "rings", len(fn.rings), "q", len(fn.quads),
              "vin", None if fn.v_in is None else round(fn.v_in, 3),
              "emb", None if emb is None else (round(emb[:, 2].min(), 4), round(emb[:, 2].max(), 3)),
              "dev", round(dev["model_to_source_max"], 4), round(dev["source_to_model_max"], 4),
              round(dev["source_to_model_p95"], 4), "chord", round(fn.chord_max, 4),
              "closed", chk["open_edges"] == 0 and chk["inconsistent_edges"] == 0, chk["outward"],
              f"{time.time() - t0:.0f}s")

    colors = {"#219": (0.80, 0.78, 0.74), "#204": (0.35, 0.33, 0.30), "#220": (0.74, 0.78, 0.80),
              "#221": (0.30, 0.33, 0.35)}
    write_obj(fins, OUT / "fins.obj", OUT / "fins.mtl", colors)
    tot = dict(fins=len(fins), verts=sum(len(f.V) for f in fins), quads=sum(len(f.quads) for f in fins),
               cut=[f.id for f in fins if f.cut], full_profile=[f.id for f in fins if not f.cut],
               deviation_max_m=max(max(f.summary["deviation_m"]["model_to_source_max"],
                                       f.summary["deviation_m"]["source_to_model_max"]) for f in fins),
               deviation_max_off_source_joints_m=max(max(f.summary["deviation_m"]["model_to_source_max_off_joints"],
                                                         f.summary["deviation_m"]["source_to_model_max_off_joints"])
                                                     for f in fins),
               deviation_p95_max_m=max(max(f.summary["deviation_m"]["model_to_source_p95"],
                                           f.summary["deviation_m"]["source_to_model_p95"]) for f in fins),
               embed_min_m=min(f.summary["embed_m"]["min"] for f in fins if f.summary["embed_m"]),
               embed_max_m=max(f.summary["embed_m"]["max"] for f in fins if f.summary["embed_m"]),
               rings_min_max=[min(len(f.rings) for f in fins), max(len(f.rings) for f in fins)],
               chord_error_max_m=max(f.chord_max for f in fins),
               all_closed=all(f.summary["mesh"]["open_edges"] == 0 and f.summary["mesh"]["inconsistent_edges"] == 0
                              and f.summary["mesh"]["non_manifold_edges"] == 0 for f in fins),
               all_outward=all(f.summary["mesh"]["outward"] for f in fins))
    summary["totals"] = tot
    (OUT / "fins_summary.json").write_text(json.dumps(rnd(summary), indent=1, ensure_ascii=False), encoding="utf-8")
    figures(fins, samples, fco, bco, btri)
    print("done", f"{time.time() - t0:.0f}s", json.dumps(rnd(tot)))


# ----------------------------------------------------------------------------------------------- figures
def model_section(fn, z):
    """Model horizontal section at z: closed polyline (local xy) interpolated between rings."""
    rz = np.array(fn.rings)
    k = min(max(np.searchsorted(rz, z) - 1, 0), len(rz) - 2)
    # same formula as the mesh vertices (ring_uv), interpolated linearly between rings
    z0, z1 = rz[k], rz[k + 1]
    kind = "full" if not fn.cut else ("cut12" if z1 <= Z_STEP + 1e-9 else "cut")
    R0, R1 = fn.ring_uv(np.array([z0]), kind)[0], fn.ring_uv(np.array([z1]), kind)[0]
    tt = (z - z0) / (z1 - z0)
    P = fn.to_xy(R0 * (1 - tt) + R1 * tt)
    return np.vstack([P, P[:1]])


def figures(fins, samples, fco, bco, btri):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    byid = {f.id: f for f in fins}
    # 1) elevation in the fin frame: v (outward) vs z, source extents, model tip / inner face, body face
    fig, axs = plt.subplots(2, 13, figsize=(52, 22), sharey=True)
    for ax, fn in zip(axs.flat, fins):
        e = fn.src_ext
        z = e[:, 0]
        cv = fn.c(z)[:, 1]
        ax.plot(e[:, 4] - cv, z, color="tab:red", lw=1.5, label="source tip")
        ax.plot(e[:, 3] - cv, z, color="tab:blue", lw=1.5, label="source back")
        zz = np.linspace(0.005, fn.z_top - 0.005, 600)
        mt, mb = [], []
        for zq in zz:
            P = fn.to_uv(model_section(fn, zq)[:-1])
            mt.append(P[:, 1].max())
            mb.append(P[:, 1].min())
        cz = fn.c(zz)[:, 1]
        ax.plot(np.array(mt) - cz, zz, "k--", lw=1, label="model tip")
        ax.plot(np.array(mb) - cz, zz, "k:", lw=1.2, label="model inner face / back")
        rows = samples[fn.id]["rows"]
        if len(rows):
            ax.plot(rows[:, 2], rows[:, 0], ".", color="0.5", ms=1, label="body face (source)")
        for zr in fn.rings:
            ax.axhline(zr, color="g", lw=0.3)
        s = fn.summary
        ax.set_title(f"{fn.id} {s['mode'][:4]} rings {s['rings']}\nemb "
                     + ("-" if s["embed_m"] is None else f"{s['embed_m']['min'] * 1000:.0f}-{s['embed_m']['max'] * 1000:.0f} mm")
                     + f"  dev {max(s['deviation_m']['model_to_source_max'], s['deviation_m']['source_to_model_max']) * 1000:.1f} mm",
                     fontsize=10)
        ax.set_xlim(-1.0, 1.0)
        ax.grid(alpha=0.3)
    axs.flat[0].legend(fontsize=8, loc="lower left")
    fig.suptitle("Fin elevation in the fin frame (v outward from the path, metres) vs z; green = rings", fontsize=16)
    plt.savefig(OUT / "fins_elevation.png", dpi=40, bbox_inches="tight")
    plt.close(fig)

    # 2) plan zooms: representative fins x heights
    reps = ["F01", "F02", "F05", "F08", "F11", "F14", "F21", "F25"]
    zs = [2.0, 7.0, 9.5, 13.6, 19.0, 25.0, 31.5, 48.0, 64.0, 70.0]
    sel_b = btri
    P = bco[sel_b]
    blo, bhi = P[:, :, 2].min(1), P[:, :, 2].max(1)
    fig, axs = plt.subplots(len(reps), len(zs), figsize=(4 * len(zs), 4 * len(reps)))
    for r_, fid in enumerate(reps):
        fn = byid[fid]
        for c_, z in enumerate(zs):
            ax = axs[r_, c_]
            if z > fn.z_top:
                ax.axis("off")
                continue
            cxy = fn.to_xy(fn.c(z))[0]
            S = hcut(fco, fn.tri, z)
            for s in S:
                ax.plot(s[:, 0], s[:, 1], color="m", lw=2.2)
            m = (blo < z) & (bhi > z)
            Pb = P[m]
            near = np.linalg.norm(Pb[:, :, :2].mean(1) - cxy, axis=1) < 2.5
            B = hcut(bco, sel_b[m][near], z)
            for s in B:
                ax.plot(s[:, 0], s[:, 1], color="0.55", lw=0.6)
            M = model_section(fn, z)
            ax.plot(M[:, 0], M[:, 1], "k-", lw=0.9)
            ax.set_xlim(cxy[0] - 1.3, cxy[0] + 1.3)
            ax.set_ylim(cxy[1] - 1.3, cxy[1] + 1.3)
            ax.set_aspect("equal")
            ax.set_title(f"{fid} z={z}", fontsize=9)
            ax.tick_params(labelsize=6)
    fig.suptitle("Plan sections: source fin (magenta), model (black), body #198/#210 (grey)", fontsize=16)
    plt.savefig(OUT / "fins_plan_zooms.png", dpi=45, bbox_inches="tight")
    plt.close(fig)

    # 3) whole plan at several heights
    fig, axs = plt.subplots(1, 4, figsize=(48, 13))
    for ax, z in zip(axs, [2.0, 13.6, 25.0, 48.0]):
        S = hcut(fco, ftri_all(fco, fins), z)
        for s in S:
            ax.plot(s[:, 0], s[:, 1], color="m", lw=1.6)
        m = (blo < z) & (bhi > z)
        for s in hcut(bco, sel_b[m], z):
            ax.plot(s[:, 0], s[:, 1], color="0.6", lw=0.4)
        for fn in fins:
            if z <= fn.z_top:
                M = model_section(fn, z)
                ax.plot(M[:, 0], M[:, 1], "k-", lw=0.7)
                ax.text(*M[:-1].mean(0), fn.id, fontsize=7)
        ax.set_aspect("equal")
        ax.grid(alpha=0.3)
        ax.set_title(f"z = {z}: source fins magenta, model black, body grey", fontsize=12)
    plt.savefig(OUT / "fins_plan_overview.png", dpi=45, bbox_inches="tight")
    plt.close(fig)


def ftri_all(fco, fins):
    return np.concatenate([fn.tri for fn in fins])


if __name__ == "__main__":
    main()
