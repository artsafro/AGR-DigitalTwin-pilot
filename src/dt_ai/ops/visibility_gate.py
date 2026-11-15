"""Shared VPM visibility checker `dt qa visibility` (#1447, backlog Q10): hidden faces, back-visible faces, open edges.

Retro 2026-11-15 (job 4bk-k3): checks v004-v009 each rebuilt the visibility method from a brief and disagreed; some
"hidden face" deletions removed visible faces (A v007 reveals, roof A E2 post, L2 grille back panels). This module is
the one fixed method; every knob is in the report (`method`).

Method (fixed):
- Viewpoints, in this order: a dome around the checked parts, pedestrian rings (eye height above the ground), and one
  close eye `close.distance_m` in front of every pane (a checked face whose material matches `close.pane_materials`,
  along its normal; a close eye only looks at faces within `close.radius_m`).
- Rays: eye -> fixed target samples on the face. A ray is blocked by the first face it hits before the target,
  front or back (no back-face culling). Only checked-part faces whose material matches `materials.transparent`
  (glass, grille, railing glass) let rays through; context meshes are opaque in every material.
- Jitter: one mode, `target-fixed-16`: the eye is fixed, the target is 16 fixed points inside the face (area-weighted
  over its fan triangles, R2 sequence); no random numbers, so two runs give the same report.
- A face is front-visible when some eye on its front side reaches >= `front_n` of 16 samples, back-visible when some eye
  on its back side reaches >= `back_n` of 16. Hidden = neither. The first eye (in the fixed order) is reported.
- Context occluders: the real context meshes as given (no hull, no prism outline: the E2 post sat in the 0.3 m gap
  between a prism and the real pylon). The report states per context mesh whether it is watertight (open edges).
- Open edges of checked parts (boundary edges after a 1 um weld), measured at the midpoint and both ends: from each
  point back along the edge's own face to the surface of another part it leaves (the embed depth). Classes are data
  (`open_edges.classes`, first match wins): `embed` (min_m < depth < max_m at all three points, both limits strict,
  optional `materials` / `partners` globs) or `material` (own face material glob). Any other open edge is
  `not_allowed` with the measured depths.

Fail-closed: no checked parts, duplicate or clashing names, NaN / inf vertices, bad face indices, a material count that
does not match the faces, a material in neither `materials.transparent` nor `materials.opaque` (named), an unknown
config key, an n outside 1..16 or another jitter mode raise ValueError. A degenerate (zero-area) checked face goes to
`dropped` with its reason and fails the gate. `passed` = no hidden, no back-visible, no not_allowed open edge, nothing
dropped. Out of scope: overlaps (`dt qa xview` stays the overlap gate).
Pattern: none | new-case: deterministic first-hit visibility gate (numpy BVH, fixed jitter, real context occluders).
"""
import copy
import fnmatch
import json
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np

NAME = "visibility_gate"
VERSION = 1
JITTER = "target-fixed-16"
SAMPLES = 16
INPUTS = (".npz", ".fbx", ".blend")
DUMP_SCRIPT = Path(__file__).resolve().parents[3] / "tools" / "blender" / "visibility_dump.py"
GROUND = "<ground>"
WELD_M = 1e-6
DEGENERATE_M2 = 1e-10

DEFAULTS = {
    "materials": {"transparent": ["*glass*", "*grille*"], "opaque": []},
    "dome": {"elevations_deg": [15.0, 35.0, 60.0], "azimuths": 16, "zenith": True, "radius_factor": 2.5},
    "rings": {"radii_m": [10.0, 30.0], "azimuths": 24, "eye_height_m": 1.7},
    "close": {"distance_m": 2.0, "radius_m": 12.0, "pane_materials": ["*glass*"], "min_pane_area_m2": 0.05,
              "merge_m": 0.25},
    "ground": True,
    "ground_z": None,
    "jitter": JITTER,
    "front_n": 1,
    "back_n": 4,
    "hit_eps_m": 1e-4,
    "open_edges": {"search_m": 0.5,
                   "classes": [{"name": "embedded", "kind": "embed", "min_m": 0.0, "max_m": 0.02}]},
}
_CLASS_KEYS = {"embed": {"name", "kind", "min_m", "max_m", "materials", "partners"},
               "material": {"name", "kind", "materials"}}


@dataclass(frozen=True)
class VPart:
    name: str
    vertices: np.ndarray        # (n, 3) float64, world, metres
    faces: tuple                # polygon index tuples, 0-based
    materials: tuple            # one material name per face


# ---- config ---------------------------------------------------------------------------------------------------------

def _merge(base: dict, over: dict, where: str) -> dict:
    out = copy.deepcopy(base)
    for k, v in over.items():
        if k not in base:
            raise ValueError(f"unknown config key {where}{k!r}; known: {sorted(base)}")
        if isinstance(base[k], dict):
            if not isinstance(v, dict):
                raise ValueError(f"config {where}{k!r} must be a mapping")
            out[k] = _merge(base[k], v, f"{where}{k}.")
        else:
            out[k] = copy.deepcopy(v)
    return out


def _num(x, where, lo=None, strict_lo=False):
    if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x):
        raise ValueError(f"config {where} must be a finite number, got {x!r}")
    if lo is not None and (x <= lo if strict_lo else x < lo):
        raise ValueError(f"config {where} = {x!r} out of range (must be {'>' if strict_lo else '>='} {lo})")
    return float(x)


def resolve_config(over: dict | None) -> dict:
    """Defaults merged with `over`; every value checked. Unknown keys and out-of-range values raise ValueError."""
    if over is not None and not isinstance(over, dict):
        raise ValueError("config must be a mapping")
    c = _merge(DEFAULTS, over or {}, "")
    if c["jitter"] != JITTER:
        raise ValueError(f"unsupported jitter mode {c['jitter']!r}; the only mode is {JITTER!r}")
    for k in ("front_n", "back_n"):
        if isinstance(c[k], bool) or not isinstance(c[k], int) or not 1 <= c[k] <= SAMPLES:
            raise ValueError(f"config {k} = {c[k]!r}; expected an integer 1..{SAMPLES}")
    for grp, keys in (("materials", ("transparent", "opaque")), ("close", ("pane_materials",))):
        for k in keys:
            if not isinstance(c[grp][k], list) or not all(isinstance(s, str) and s for s in c[grp][k]):
                raise ValueError(f"config {grp}.{k} must be a list of non-empty glob strings")
    d = c["dome"]
    d["elevations_deg"] = [_num(e, "dome.elevations_deg", 0) for e in d["elevations_deg"]]
    if any(e >= 90 for e in d["elevations_deg"]):
        raise ValueError("config dome.elevations_deg must be < 90 (use dome.zenith)")
    _num(d["radius_factor"], "dome.radius_factor", 1.0, strict_lo=True)
    r = c["rings"]
    r["radii_m"] = [_num(x, "rings.radii_m", 0) for x in r["radii_m"]]
    _num(r["eye_height_m"], "rings.eye_height_m", 0)
    for grp in ("dome", "rings"):
        a = c[grp]["azimuths"]
        if isinstance(a, bool) or not isinstance(a, int) or a < 0:
            raise ValueError(f"config {grp}.azimuths must be an integer >= 0")
    for k in ("distance_m", "radius_m", "merge_m"):
        _num(c["close"][k], f"close.{k}", 0.0, strict_lo=True)
    _num(c["close"]["min_pane_area_m2"], "close.min_pane_area_m2", 0)
    _num(c["hit_eps_m"], "hit_eps_m", 0.0, strict_lo=True)
    if not isinstance(c["ground"], bool):
        raise ValueError("config ground must be true or false")
    if c["ground_z"] is not None:
        _num(c["ground_z"], "ground_z")
    _num(c["open_edges"]["search_m"], "open_edges.search_m", 0.0, strict_lo=True)
    names = set()
    for cl in c["open_edges"]["classes"]:
        if not isinstance(cl, dict) or cl.get("kind") not in _CLASS_KEYS:
            raise ValueError(f"open-edge class {cl!r}: kind must be one of {sorted(_CLASS_KEYS)}")
        extra = set(cl) - _CLASS_KEYS[cl["kind"]]
        if extra:
            raise ValueError(f"open-edge class {cl.get('name')!r}: unknown keys {sorted(extra)}")
        if not isinstance(cl.get("name"), str) or not cl["name"] or cl["name"] in names | {"not_allowed"}:
            raise ValueError(f"open-edge class name {cl.get('name')!r} missing, duplicate or reserved")
        names.add(cl["name"])
        if cl["kind"] == "embed":
            lo = _num(cl.get("min_m"), f"class {cl['name']}.min_m")
            if _num(cl.get("max_m"), f"class {cl['name']}.max_m") <= lo:
                raise ValueError(f"open-edge class {cl['name']!r}: max_m must exceed min_m")
        elif not cl.get("materials"):
            raise ValueError(f"open-edge class {cl['name']!r}: kind material needs materials globs")
        for k in ("materials", "partners"):
            if k in cl and (not isinstance(cl[k], list) or not all(isinstance(s, str) and s for s in cl[k])):
                raise ValueError(f"open-edge class {cl['name']!r}: {k} must be a list of globs")
    return c


def _match(name: str, globs) -> bool:
    n = name.lower()
    return any(fnmatch.fnmatchcase(n, g.lower()) for g in globs)


# ---- geometry -------------------------------------------------------------------------------------------------------

def _validate(p: VPart, where: str) -> np.ndarray:
    v = np.asarray(p.vertices, dtype=np.float64)
    if v.ndim != 2 or v.shape[1] != 3:
        raise ValueError(f"{where} {p.name!r}: vertices must be (n, 3)")
    if not np.isfinite(v).all():
        raise ValueError(f"{where} {p.name!r}: NaN or inf vertex")
    if len(p.materials) != len(p.faces):
        raise ValueError(f"{where} {p.name!r}: {len(p.materials)} materials for {len(p.faces)} faces")
    for i, f in enumerate(p.faces):
        if len(f) < 3 or min(f) < 0 or max(f) >= len(v) or len(set(f)) != len(f):
            raise ValueError(f"{where} {p.name!r}: face {i} has bad vertex indices {tuple(f)}")
    return v


def _newell(pts: np.ndarray) -> np.ndarray:
    """Newell area vector of a polygon (length = area, direction = normal by winding)."""
    nxt = np.roll(pts, -1, axis=0)
    return 0.5 * np.array([np.sum((pts[:, 1] - nxt[:, 1]) * (pts[:, 2] + nxt[:, 2])),
                           np.sum((pts[:, 2] - nxt[:, 2]) * (pts[:, 0] + nxt[:, 0])),
                           np.sum((pts[:, 0] - nxt[:, 0]) * (pts[:, 1] + nxt[:, 1]))])


def _fan(pts: np.ndarray) -> np.ndarray:
    return np.stack([np.repeat(pts[:1], len(pts) - 2, 0), pts[1:-1], pts[2:]], axis=1)


_R2 = (0.7548776662466927, 0.5698402909980532)


def face_samples(pts) -> np.ndarray:
    """The 16 fixed target points of a polygon (`target-fixed-16`): area-weighted fan triangle, R2 (u, v), inset."""
    pts = np.asarray(pts, dtype=np.float64)
    tris = _fan(pts)
    areas = 0.5 * np.linalg.norm(np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0]), axis=1)
    cum = np.cumsum(areas) / areas.sum()
    out = np.empty((SAMPLES, 3))
    for k in range(SAMPLES):
        t = min(int(np.searchsorted(cum, (k + 0.5) / SAMPLES)), len(tris) - 1)
        u, v = (0.5 + (k + 1) * _R2[0]) % 1.0, (0.5 + (k + 1) * _R2[1]) % 1.0
        if u + v > 1.0:
            u, v = 1.0 - u, 1.0 - v
        a, b, c = tris[t]
        p = a + u * (b - a) + v * (c - a)
        out[k] = p + 0.02 * ((a + b + c) / 3.0 - p)          # 2 % toward the centroid: never on an edge
    return out


# ---- BVH + rays -----------------------------------------------------------------------------------------------------

class BVH:
    """Median-split bounding volume hierarchy over triangles; breadth-first vectorised ray traversal."""

    LEAF = 8

    def __init__(self, tris: np.ndarray):
        self.n = len(tris)
        lo, hi = tris.min(1), tris.max(1)
        cen = 0.5 * (lo + hi)
        order = np.arange(self.n)
        nlo, nhi, left, right, start, count = [], [], [], [], [], []
        stack = [(0, self.n, -1, 0)]
        while stack:
            s, e, parent, side = stack.pop()
            i = len(nlo)
            if parent >= 0:
                (left if side == 0 else right)[parent] = i
            idx = order[s:e]
            nlo.append(lo[idx].min(0) - 1e-7 if len(idx) else np.zeros(3))
            nhi.append(hi[idx].max(0) + 1e-7 if len(idx) else np.zeros(3))
            left.append(-1)
            right.append(-1)
            start.append(s)
            count.append(e - s)
            if e - s > self.LEAF:
                c = cen[idx]
                ax = int(np.argmax(c.max(0) - c.min(0)))
                mid = (e - s) // 2
                order[s:e] = idx[np.argpartition(c[:, ax], mid, kind="introselect")]
                stack.append((s + mid, e, i, 1))
                stack.append((s, s + mid, i, 0))
        self.nlo, self.nhi = np.array(nlo), np.array(nhi)
        self.left, self.right = np.array(left), np.array(right)
        self.start, self.count = np.array(start), np.array(count)
        self.order = order
        t = tris[order]
        self.a, self.e1, self.e2 = t[:, 0], t[:, 1] - t[:, 0], t[:, 2] - t[:, 0]

    def hits(self, o, d, tmin, tmax, keep, any_hit, chunk=20000):
        """(ray, triangle, t) of every hit with tmin < t < tmax for which keep(ray, tri, t) holds.

        any_hit: a ray leaves the traversal at its first kept hit (occlusion query)."""
        out_r, out_t, out_d = [], [], []
        if self.n == 0 or len(o) == 0:
            return np.zeros(0, int), np.zeros(0, int), np.zeros(0)
        for c0 in range(0, len(o), chunk):
            O, D = o[c0:c0 + chunk], d[c0:c0 + chunk]
            Tmin, Tmax = tmin[c0:c0 + chunk], tmax[c0:c0 + chunk]
            Ds = np.where(np.abs(D) < 1e-30, 1e-30, D)
            inv = 1.0 / Ds
            done = np.zeros(len(O), bool)
            fr = np.arange(len(O))
            fn = np.zeros(len(O), int)
            while fr.size:
                if any_hit:
                    m = ~done[fr]
                    fr, fn = fr[m], fn[m]
                t1 = (self.nlo[fn] - O[fr]) * inv[fr]
                t2 = (self.nhi[fn] - O[fr]) * inv[fr]
                tn = np.minimum(t1, t2).max(1)
                tf = np.maximum(t1, t2).min(1)
                ok = (tn <= tf) & (tf >= Tmin[fr]) & (tn <= Tmax[fr])
                fr, fn = fr[ok], fn[ok]
                leaf = self.left[fn] < 0
                lr, ln = fr[leaf], fn[leaf]
                if lr.size:
                    cnt = self.count[ln]
                    rr = np.repeat(lr, cnt)
                    off = np.arange(int(cnt.sum())) - np.repeat(np.cumsum(cnt) - cnt, cnt)
                    tt = np.repeat(self.start[ln], cnt) + off
                    t, valid = _mt(O[rr], D[rr], self.a[tt], self.e1[tt], self.e2[tt])
                    valid &= (t > Tmin[rr]) & (t < Tmax[rr])
                    rr, tt, t = rr[valid], self.order[tt[valid]], t[valid]
                    if rr.size:
                        k = keep(rr + c0, tt, t)
                        rr, tt, t = rr[k], tt[k], t[k]
                        out_r.append(rr + c0)
                        out_t.append(tt)
                        out_d.append(t)
                        if any_hit:
                            done[rr] = True
                inner = ~leaf
                fr = np.concatenate([fr[inner], fr[inner]])
                fn = np.concatenate([self.left[fn[inner]], self.right[fn[inner]]])
        if not out_r:
            return np.zeros(0, int), np.zeros(0, int), np.zeros(0)
        return np.concatenate(out_r), np.concatenate(out_t), np.concatenate(out_d)


def _mt(o, d, a, e1, e2):
    """Moller-Trumbore, both sides, edges included (adjacent occluder triangles leave no crack)."""
    p = np.cross(d, e2)
    det = np.einsum("ij,ij->i", e1, p)
    ok = np.abs(det) > 1e-15
    inv = np.where(ok, 1.0 / np.where(ok, det, 1.0), 0.0)
    s = o - a
    u = np.einsum("ij,ij->i", s, p) * inv
    q = np.cross(s, e1)
    v = np.einsum("ij,ij->i", d, q) * inv
    t = np.einsum("ij,ij->i", e2, q) * inv
    ok &= (u >= -1e-9) & (v >= -1e-9) & (u + v <= 1 + 1e-9)
    return t, ok


# ---- the check ------------------------------------------------------------------------------------------------------

def _r(x, nd=4) -> list:
    return [round(float(c), nd) for c in x]


def _eyes(c: dict, lo: np.ndarray, hi: np.ndarray, ground_z: float, panes: list) -> list:
    centre = 0.5 * (lo + hi)
    radius = max(float(np.linalg.norm(hi - lo)) * 0.5, 1.0)
    eyes = []
    d = c["dome"]
    rd = d["radius_factor"] * radius
    for el in d["elevations_deg"]:
        for k in range(d["azimuths"]):
            az = 2 * math.pi * k / d["azimuths"]
            e = math.radians(el)
            eyes.append((f"dome:el{el:g}:az{k}", centre + rd * np.array([math.cos(e) * math.cos(az),
                                                                          math.cos(e) * math.sin(az), math.sin(e)]),
                         None))
    if d["zenith"]:
        eyes.append(("dome:zenith", centre + np.array([0.0, 0.0, rd]), None))
    r = c["rings"]
    rxy = float(np.linalg.norm((hi - lo)[:2])) * 0.5
    for rad in r["radii_m"]:
        for k in range(r["azimuths"]):
            az = 2 * math.pi * k / r["azimuths"]
            eyes.append((f"ring:r{rad:g}:az{k}", np.array([centre[0] + (rxy + rad) * math.cos(az),
                                                           centre[1] + (rxy + rad) * math.sin(az),
                                                           ground_z + r["eye_height_m"]]), None))
    cl, seen = c["close"], set()
    for pid, part, face, cen, n in panes:
        pos = cen + cl["distance_m"] * n
        key = tuple(np.round(pos / cl["merge_m"]).astype(np.int64).tolist())
        if key in seen:
            continue
        seen.add(key)
        eyes.append((f"close:{part}:f{face}", pos, cl["radius_m"]))
    return eyes


def _open_edges(v: np.ndarray, faces, keep_face) -> tuple:
    """Boundary and non-manifold edges after a WELD_M weld: lists of (i, j, face)."""
    keys = np.round(v / WELD_M).astype(np.int64)
    _, weld = np.unique(keys, axis=0, return_inverse=True)
    weld = weld.reshape(-1)
    use = {}
    for fi, f in enumerate(faces):
        if not keep_face[fi]:
            continue
        for a, b in zip(f, f[1:] + f[:1]):
            k = (min(weld[a], weld[b]), max(weld[a], weld[b]))
            if k[0] == k[1]:
                continue
            use.setdefault(k, []).append((a, b, fi))
    boundary = [u[0] for k, u in sorted(use.items()) if len(u) == 1]
    nonman = [u[0] for k, u in sorted(use.items()) if len(u) > 2]
    return boundary, nonman


def check(parts, context, config: dict | None = None) -> dict:
    """Visibility report of `parts` (checked meshes) among `context` (opaque occluders, not checked)."""
    c = resolve_config(config)
    parts, context = list(parts), list(context)
    if not parts:
        raise ValueError("no checked parts")
    names = [p.name for p in parts + context]
    dup = sorted({n for n in names if names.count(n) > 1})
    if dup:
        raise ValueError(f"duplicate part / context names {dup}")
    if GROUND in names:
        raise ValueError(f"{GROUND!r} is reserved")
    verts = [_validate(p, "part") for p in parts] + [_validate(p, "context") for p in context]
    unmapped = sorted({m for p in parts for m in p.materials
                       if not _match(m, c["materials"]["transparent"]) and not _match(m, c["materials"]["opaque"])})
    if unmapped:
        raise ValueError(f"unmapped materials {unmapped}: add each to config materials.transparent or .opaque")

    # faces: centroid, unit normal, area, fan triangles
    F_part, F_local, F_cen, F_n, F_area, F_opaque, F_checked = [], [], [], [], [], [], []
    tri, tri_face = [], []
    dropped = []
    for pi, (p, v) in enumerate(zip(parts + context, verts)):
        checked = pi < len(parts)
        for fi, f in enumerate(p.faces):
            pts = v[list(f)]
            nn = _newell(pts)
            area = float(np.linalg.norm(nn))
            gid = len(F_part)
            F_part.append(pi)
            F_local.append(fi)
            F_cen.append(pts.mean(0))
            F_area.append(area)
            F_n.append(nn / area if area > DEGENERATE_M2 else np.zeros(3))
            F_checked.append(checked)
            F_opaque.append(not checked or not _match(p.materials[fi], c["materials"]["transparent"]))
            if area <= DEGENERATE_M2:
                dropped.append({"part": p.name, "face": fi, "context": not checked,
                                "reason": f"degenerate face (area {area:.3g} m2)"})
                continue
            t = _fan(pts)
            tri.append(t)
            tri_face.extend([gid] * len(t))
    F_part, F_cen, F_n = np.array(F_part), np.array(F_cen), np.array(F_n)
    F_area, F_opaque, F_checked = np.array(F_area), np.array(F_opaque), np.array(F_checked)
    F_ok = F_area > DEGENERATE_M2
    allv = np.concatenate([verts[i] for i in range(len(parts))])
    lo, hi = allv.min(0), allv.max(0)                     # checked parts: ground level
    scene = np.concatenate(verts)                         # dome and rings stand outside parts AND context
    slo, shi = scene.min(0), scene.max(0)
    ground_z = float(lo[2]) if c["ground_z"] is None else float(c["ground_z"])
    tri = np.concatenate(tri) if tri else np.zeros((0, 3, 3))
    tri_face = np.array(tri_face, dtype=np.int64)
    if c["ground"]:
        span = (float(np.linalg.norm(shi - slo)) * 0.5 + 1.0) * c["dome"]["radius_factor"] * 4 + \
            max(c["rings"]["radii_m"] or [0.0]) * 4
        cx, cy = 0.5 * (slo[0] + shi[0]), 0.5 * (slo[1] + shi[1])
        q = np.array([[cx - span, cy - span, ground_z], [cx + span, cy - span, ground_z],
                      [cx + span, cy + span, ground_z], [cx - span, cy + span, ground_z]])
        tri = np.concatenate([tri, _fan(q)])
        tri_face = np.concatenate([tri_face, [-1, -1]])
    tri_opaque = np.array([True if f < 0 else bool(F_opaque[f]) for f in tri_face.tolist()], dtype=bool)
    occ_idx = np.flatnonzero(tri_opaque)
    occ = BVH(tri[occ_idx])
    occ_face = tri_face[occ_idx]

    panes = []
    for g in np.flatnonzero(F_checked & F_ok):
        p = parts[F_part[g]]
        fi = int(F_local[g])
        if _match(p.materials[fi], c["close"]["pane_materials"]) and F_area[g] >= c["close"]["min_pane_area_m2"]:
            panes.append((int(F_part[g]), p.name, fi, F_cen[g], F_n[g]))
    eyes = _eyes(c, slo, shi, ground_z, panes)

    # samples of every checked, non-degenerate face
    chk = np.flatnonzero(F_checked & F_ok)
    S = np.zeros((len(F_part), SAMPLES, 3))
    for g in chk:
        p = parts[F_part[g]]
        S[g] = face_samples(verts[F_part[g]][list(p.faces[F_local[g]])])
    front = {}                      # gid -> (eye id, hits)
    back = {}
    eps = c["hit_eps_m"]
    for eid, pos, radius in eyes:
        side = np.einsum("ij,ij->i", F_n[chk], pos - F_cen[chk])
        want = ((side > 1e-9) & np.array([g not in front for g in chk], bool)) | \
               ((side < -1e-9) & np.array([g not in back for g in chk], bool))
        if radius is not None:
            want &= np.linalg.norm(F_cen[chk] - pos, axis=1) <= radius
        cand = chk[want]
        if not cand.size:
            continue
        tg = S[cand].reshape(-1, 3)
        d = tg - pos
        dist = np.linalg.norm(d, axis=1)
        d = d / dist[:, None]
        target = np.repeat(cand, SAMPLES)
        o = np.repeat(pos[None], len(tg), 0)
        r, _t, _ = occ.hits(o, d, np.full(len(tg), 1e-9), dist - eps,
                            lambda rr, tt, t: occ_face[tt] != target[rr], any_hit=True)
        blocked = np.zeros(len(tg), bool)
        blocked[r] = True
        seen = (~blocked).reshape(-1, SAMPLES).sum(1)
        cside = np.einsum("ij,ij->i", F_n[cand], pos - F_cen[cand])
        for g, n_seen, s in zip(cand.tolist(), seen.tolist(), cside.tolist()):
            if s > 0 and g not in front and n_seen >= c["front_n"]:
                front[g] = (eid, n_seen)
            elif s < 0 and g not in back and n_seen >= c["back_n"]:
                back[g] = (eid, n_seen)

    # open edges
    allbvh = BVH(tri)
    tri_part = np.array([F_part[f] if f >= 0 else -1 for f in tri_face.tolist()], dtype=np.int64)
    tri_n = np.array([F_n[f] if f >= 0 else (0.0, 0.0, 1.0) for f in tri_face.tolist()]).reshape(-1, 3)
    pnames = names + [GROUND]
    classes = c["open_edges"]["classes"]
    reports = []
    for pi, p in enumerate(parts):
        v = verts[pi]
        gids = np.flatnonzero(F_part == pi)
        keep = F_ok[gids]
        boundary, nonman = _open_edges(v, p.faces, keep)
        edges = {cl["name"]: [] for cl in classes}
        edges["not_allowed"] = []
        if boundary:
            ea = np.array([v[a] for a, b, f in boundary])
            eb = np.array([v[b] for a, b, f in boundary])
            fg = gids[[f for a, b, f in boundary]]
            e = eb - ea
            e /= np.linalg.norm(e, axis=1)[:, None]
            dout = np.cross(e, F_n[fg])
            mid = 0.5 * (ea + eb)
            flip = np.einsum("ij,ij->i", dout, F_cen[fg] - mid) > 0
            dout[flip] *= -1
            dout /= np.maximum(np.linalg.norm(dout, axis=1), 1e-30)[:, None]
            o = np.concatenate([ea, mid, eb])
            d = -np.concatenate([dout, dout, dout])
            nE = len(boundary)
            r, tt, t = allbvh.hits(o, d, np.full(3 * nE, -1e-9), np.full(3 * nE, c["open_edges"]["search_m"]),
                                   lambda rr, tt, t: tri_part[tt] != pi, any_hit=False)
            best_t = np.full(3 * nE, np.inf)
            best_tri = np.full(3 * nE, -1)
            for ri, ti, tv in sorted(zip(r.tolist(), tt.tolist(), t.tolist()), key=lambda x: (x[0], x[2], x[1])):
                if tv < best_t[ri]:
                    best_t[ri], best_tri[ri] = tv, ti
            depth, partner = [], []
            for k in range(3 * nE):
                if best_tri[k] < 0:
                    depth.append(None)
                    partner.append(None)
                    continue
                exiting = float(np.dot(tri_n[best_tri[k]], d[k])) > 0
                depth.append(max(float(best_t[k]), 0.0) if exiting else None)
                partner.append(pnames[tri_part[best_tri[k]]] if tri_part[best_tri[k]] >= 0 else GROUND)
            for k, (a, b, f) in enumerate(boundary):
                ds = {"a": depth[k], "mid": depth[nE + k], "b": depth[2 * nE + k]}
                prt = sorted({x for x in (partner[k], partner[nE + k], partner[2 * nE + k]) if x})
                rec = {"vertices": [int(a), int(b)], "face": int(f), "material": p.materials[f],
                       "a": _r(v[a]), "b": _r(v[b]),
                       "depths_m": {kk: None if x is None else round(x, 6) for kk, x in ds.items()},
                       "partners": prt}
                cls = None
                for cl in classes:
                    if "materials" in cl and not _match(p.materials[f], cl["materials"]):
                        continue
                    if cl["kind"] == "material":
                        cls = cl["name"]
                        break
                    vals = list(ds.values())
                    if any(x is None for x in vals) or not all(cl["min_m"] < x < cl["max_m"] for x in vals):
                        continue
                    if "partners" in cl and not all(_match(x, cl["partners"]) for x in prt):
                        continue
                    cls = cl["name"]
                    break
                if cls is None:
                    rec["reason"] = "no allowed class: " + (
                        "not embedded at " + ", ".join(k for k, x in ds.items() if x is None)
                        if any(x is None for x in ds.values()) else "embed depth outside every class range")
                    edges["not_allowed"].append(rec)
                else:
                    edges[cls].append(rec)
        hidden, backv, visfrom = [], [], []
        for g in gids.tolist():
            if not F_ok[g]:
                continue
            fi = int(F_local[g])
            base = {"face": fi, "material": p.materials[fi], "centroid": _r(F_cen[g])}
            if g in back:
                backv.append({**base, "eye": back[g][0], "hits": back[g][1]})
            if g in front:
                visfrom.append({"face": fi, "eye": front[g][0], "hits": front[g][1]})
            elif g not in back:
                hidden.append(base)
        reports.append({"part": p.name, "faces": len(p.faces), "front_visible": len(visfrom),
                        "hidden": hidden, "back_visible": backv, "visible_from": visfrom,
                        "open_edges": edges,
                        "non_manifold_edges": [{"vertices": [int(a), int(b)], "face": int(f)} for a, b, f in nonman]})
    ctx = []
    for ci, p in enumerate(context):
        keep = F_ok[F_part == len(parts) + ci]
        boundary, _nm = _open_edges(verts[len(parts) + ci], p.faces, keep)
        ctx.append({"name": p.name, "faces": len(p.faces), "open_edges": len(boundary), "watertight": not boundary})
    summary = {"hidden": sum(len(r["hidden"]) for r in reports),
               "back_visible": sum(len(r["back_visible"]) for r in reports),
               "open_edges": {k: sum(len(r["open_edges"][k]) for r in reports)
                              for k in [cl["name"] for cl in classes] + ["not_allowed"]},
               "dropped": len(dropped)}
    passed = not summary["hidden"] and not summary["back_visible"] and not summary["open_edges"]["not_allowed"] \
        and not dropped
    return {"tool": "dt qa visibility", "version": VERSION, "issue": 1447, "passed": passed,
            "method": {**c, "samples": SAMPLES, "ground_z_used": round(ground_z, 6)},
            "eyes": {"dome": sum(e[0].startswith("dome:") for e in eyes),
                     "ring": sum(e[0].startswith("ring:") for e in eyes),
                     "close": sum(e[0].startswith("close:") for e in eyes),
                     "list": [{"id": e[0], "pos": _r(e[1])} for e in eyes]},
            "summary": summary, "parts": reports, "context": ctx, "dropped": dropped}


def summary_lines(rep: dict) -> list:
    s = rep["summary"]
    lines = [f"dt qa visibility: {'PASSED' if rep['passed'] else 'NOT PASSED'} - {s['hidden']} hidden, "
             f"{s['back_visible']} back-visible faces, open edges {s['open_edges']}, {s['dropped']} dropped; "
             f"eyes dome {rep['eyes']['dome']} / ring {rep['eyes']['ring']} / close {rep['eyes']['close']}"]
    for r in rep["parts"]:
        oe = {k: len(x) for k, x in r["open_edges"].items() if x}
        lines.append(f"  {r['part']}: {r['faces']} faces, {len(r['hidden'])} hidden, {len(r['back_visible'])} "
                     f"back-visible, open edges {oe}")
    for cx in rep["context"]:
        if not cx["watertight"]:
            lines.append(f"  context {cx['name']}: NOT watertight ({cx['open_edges']} open edges)")
    return lines


# ---- I/O ------------------------------------------------------------------------------------------------------------

def save_npz(path, parts) -> None:
    """Parts with materials: names, v<i>, lt<i>, lv<i>, loc<i>, mi<i> (slot per face), mn<i> (slot names)."""
    data = {"names": np.array([p.name for p in parts], dtype=str)}
    for i, p in enumerate(parts):
        slots = sorted(set(p.materials))
        data[f"v{i}"] = np.asarray(p.vertices, dtype=np.float64)
        data[f"lt{i}"] = np.array([len(f) for f in p.faces], dtype=np.int64)
        data[f"lv{i}"] = np.array([x for f in p.faces for x in f], dtype=np.int64)
        data[f"loc{i}"] = np.zeros(3)
        data[f"mi{i}"] = np.array([slots.index(m) for m in p.materials], dtype=np.int64)
        data[f"mn{i}"] = np.array(slots, dtype=str)
    with open(path, "wb") as fh:
        np.savez(fh, **data)


def load_npz(path) -> list:
    from dt_ai.ops.xview_gate import _faces

    path = Path(path)
    with np.load(path, allow_pickle=False) as z:
        if "names" not in z.files:
            raise ValueError(f"{path}: no 'names' key; expected the visibility dump format")
        names = [str(n) for n in z["names"].tolist()]
        expected = {"names"} | {f"{k}{i}" for i in range(len(names)) for k in ("v", "lt", "lv", "loc", "mi", "mn")}
        if set(z.files) != expected:
            raise ValueError(f"{path}: NPZ keys do not match {len(names)} parts: missing "
                             f"{sorted(expected - set(z.files))}, unknown {sorted(set(z.files) - expected)}")
        out = []
        for i, n in enumerate(names):
            faces = _faces(z[f"lt{i}"], z[f"lv{i}"], where=n)
            mi, mn = z[f"mi{i}"], [str(s) or "<none>" for s in z[f"mn{i}"].tolist()]
            if mi.shape != (len(faces),) or mi.dtype.kind not in "iu" or (len(mi) and (mi.min() < 0 or
                                                                                       mi.max() >= len(mn))):
                raise ValueError(f"{path}: part {n!r} material slots out of range or not one per face")
            out.append(VPart(n, np.asarray(z[f"v{i}"], dtype=np.float64), faces, tuple(mn[k] for k in mi.tolist())))
        return out


def run(src, out, context=(), parts=None, config=None, blender=None, timeout=3600) -> dict:
    """Load `src` (.npz, or .fbx / .blend through headless Blender), check, publish the report at a new `out`."""
    import shutil
    import tempfile

    from dt_ai.ops.xview_gate import UNIT_SYSTEMS, _sha256, publish

    src, out = Path(src), Path(out)
    ext = src.suffix.lower()
    if ext not in INPUTS:
        raise ValueError(f"unsupported input {src.name!r}; expected one of {INPUTS}")
    if not src.is_file():
        raise ValueError(f"input not found: {src}")
    log = out.with_name(out.name + ".blender.log")
    for p in (out, log):
        if p.resolve() == src.resolve():
            raise ValueError(f"{p} is the input; write the report elsewhere")
    if out.exists():
        raise ValueError(f"{out} exists; write a new versioned report")
    if not out.parent.is_dir():
        raise ValueError(f"report folder does not exist: {out.parent}")
    resolve_config(config)                       # config errors before any Blender run
    sha = _sha256(src)
    dump = None
    units = {"unit_system": None, "unit_scale": None, "coordinates": "m"}
    if ext == ".npz":
        loaded = load_npz(src)
    else:
        if log.exists():
            raise ValueError(f"{log} exists; write a new versioned report")
        from dt_ai.core.blender_runner import run_blender
        if not DUMP_SCRIPT.is_file():
            raise ValueError(f"Blender dump script not found: {DUMP_SCRIPT}")
        tmp = Path(tempfile.mkdtemp(prefix=out.name + ".dump-", dir=out.parent))
        tmp_log = tmp / "blender.log"
        try:
            npz, manifest = tmp / "parts.npz", tmp / "manifest.json"
            try:
                dump = run_blender(DUMP_SCRIPT, [src.resolve(), npz, manifest], executable=blender,
                                   output_json=manifest, outputs=[npz], timeout=timeout, log_path=tmp_log)
            finally:
                if tmp_log.is_file():
                    publish(tmp_log.read_bytes(), log)
            loaded = load_npz(npz)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        if [o["name"] for o in dump.get("objects", [])] != [p.name for p in loaded]:
            raise ValueError("Blender manifest objects do not match the dumped parts")
        scale, system = dump.get("unit_scale"), dump.get("unit_system")
        if isinstance(scale, bool) or not isinstance(scale, (int, float)) or not math.isfinite(scale) or scale <= 0 \
                or system not in UNIT_SYSTEMS or (system == "NONE" and scale != 1):
            raise ValueError(f"unsupported Blender units {system!r} / {scale!r}; cannot convert to metres")
        loaded = [VPart(p.name, p.vertices * float(scale), p.faces, p.materials) for p in loaded]
        units = {"unit_system": system, "unit_scale": float(scale), "coordinates": "m"}
    by = {p.name: p for p in loaded}
    context = list(context or [])
    missing = [n for n in context + list(parts or []) if n not in by]
    if missing:
        raise ValueError(f"objects not in the input: {missing}; present: {sorted(by)[:40]}")
    both = sorted(set(context) & set(parts or []))
    if both:
        raise ValueError(f"objects named both as part and as context: {both}")
    chosen = list(parts) if parts else [n for n in by if n not in set(context)]
    rep = check([by[n] for n in chosen], [by[n] for n in context], config)
    if _sha256(src) != sha:
        raise ValueError(f"input changed during the run: {src}")
    rep["input"] = {"path": str(src), "sha256": sha, "kind": ext[1:], "objects_in_file": [p.name for p in loaded],
                    "not_selected": [p.name for p in loaded if p.name not in set(chosen) | set(context)],
                    "units": units, "dropped_objects": [] if dump is None else dump.get("dropped", []),
                    "blender": None if dump is None else {"version": dump.get("blender"), "log": str(log)}}
    publish(json.dumps(rep, ensure_ascii=False, indent=1).encode("utf-8"), out)
    return rep
