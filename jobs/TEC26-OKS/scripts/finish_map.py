"""new-case: TEC26 per-building finish assignment from a Max Multi/Sub dump (pure Python, no Blender).

Used by build_master.py (Blender) and by the tests. Contracts (fail-closed, never a default finish):
- validate_spec: every finish has a unique UDIM and an integer sRGB triple; every source ID maps to declared
  finishes; empty IDs are disjoint from mapped IDs; a finish that names a KPP twin must carry exactly the KPP RGB
  («синий, жёлтый, серый должны биться»). A full (patterned) finish must deliver its KPP twin's texel density
  (contract_density); a different density needs an approved `density_exception` citing the user decision.
- assign_finishes: one finish per polygon; a polygon whose material ID is unmapped, or declared empty, raises
  ValueError naming the ID; NaN/inf coordinates raise. Split rule `below_zero`: a polygon whose highest vertex is at
  or below `zero_m` (±0.000) takes `below`, every other polygon `above`.
- perimeter_drop: for a footprint-aligned box body, every side of the plan must be covered by drop faces reaching
  <= -1.0 m (Artem 2026-10-22: «полигоны по периметру должны быть утоплены минимум на метр вниз»).
"""
import json
import math
import os
import re

DROP_MIN_M = -1.0


def fresh_out_dir(out, inputs):
    """Create a NEW output directory; refuse an existing one or one that is/contains/is inside an input."""
    import os
    o = os.path.realpath(out)
    for p in inputs:
        r = os.path.realpath(p)
        if o == r or r.startswith(o + os.sep) or o.startswith(r + os.sep):
            raise ValueError(f"output {out} aliases input {p}")
    if os.path.lexists(out):
        raise FileExistsError(f"output {out} already exists; choose a new version")
    os.makedirs(out)
    return out


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def validate_spec(spec, kpp_spec=None):
    fin = spec.get("finishes") or {}
    if not fin:
        raise ValueError("spec has no finishes")
    udims = [t.get("udim") for t in fin.values()]
    if len(set(udims)) != len(udims) or not all(isinstance(u, int) and 1001 <= u <= 1100 for u in udims):
        raise ValueError(f"finish UDIMs must be unique ints 1001..1100: {udims}")
    for name, t in fin.items():
        rgb = t.get("rgb")
        if not (isinstance(rgb, list) and len(rgb) == 3 and all(isinstance(c, int) and 0 <= c <= 255 for c in rgb)):
            raise ValueError(f"finish {name}: rgb must be three ints 0..255, got {rgb}")
        if t.get("kind") not in ("placeholder", "full"):
            raise ValueError(f"finish {name}: unsupported kind {t.get('kind')}")
        if t["kind"] == "full":
            S = t.get("S")
            if not (isinstance(S, (int, float)) and math.isfinite(S) and S > 0):
                raise ValueError(f"finish {name}: S must be a finite number > 0, got {S}")
            dens = spec["size_full"] / S
            if not 512 <= dens <= 1706:  # reg p.32 §6.2 band
                raise ValueError(f"finish {name}: density {dens:.0f} px/m outside 512..1706")
    src = spec.get("source_ids") or {}
    if not src:
        raise ValueError("spec has no source_ids")
    for sid, rule in src.items():
        names = [rule["above"], rule["below"]] if rule.get("split") == "below_zero" else [rule.get("finish")]
        if rule.get("split") not in (None, "below_zero"):
            raise ValueError(f"source ID {sid}: unsupported split {rule.get('split')}")
        for n in names:
            if n not in fin:
                raise ValueError(f"source ID {sid}: finish {n} is not declared")
    empty = {int(i) for i in spec.get("empty_ids", [])}
    clash = empty & {int(i) for i in src}
    if clash:
        raise ValueError(f"IDs both mapped and empty: {sorted(clash)}")
    if not isinstance(spec.get("zero_m"), (int, float)) or not math.isfinite(spec["zero_m"]):
        raise ValueError("zero_m must be a finite number")
    if spec.get("kpp_palette") and kpp_spec is None:
        raise ValueError("spec has a kpp_palette: validate it against the KPP spec (load_kpp())")
    if kpp_spec is not None:
        for name, ref in (spec.get("kpp_palette") or {}).items():
            k = kpp_spec["finishes"].get(ref["kpp_finish"])
            if k is None or k["udim"] != ref["kpp_udim"]:
                raise ValueError(f"{name}: KPP twin {ref} not found in the KPP spec")
            if fin[name]["rgb"] != k["rgb"]:
                raise ValueError(f"{name}: rgb {fin[name]['rgb']} != KPP {ref['kpp_finish']} {k['rgb']}")
            if fin[name]["kind"] == "full":  # same joints/noise/recess as the KPP VPM tile; only S/phase may differ
                for key in ("pattern", "P", "h_joints", "rough", "metal", "joint_half_mm"):
                    if fin[name].get(key) != k.get(key):
                        raise ValueError(f"{name}: {key} {fin[name].get(key)} != KPP {k.get(key)}")
                check_density_contract(name, spec, k, kpp_spec)
    return True


DECISION_REF = re.compile(r"^(D\d+|https://github\.com/\S+#issuecomment-\d+)$")


def contract_density(name, spec, kpp_spec):
    """px/m a full finish must deliver: the KPP twin's density (Artem 2026-10-22 «такой же тексель, как в VPM КПП»),
    or the value of an approved `density_exception` that cites the user decision (D<n> or the issue-comment URL)."""
    ref = (spec.get("kpp_palette") or {}).get(name)
    if ref is None:
        raise ValueError(f"{name}: full finish without a KPP twin has no density contract")
    k = kpp_spec["finishes"][ref["kpp_finish"]]
    exc = (spec.get("density_exception") or {}).get(name)
    if exc is not None:
        v = exc.get("px_per_m")
        if not (isinstance(exc.get("decision"), str) and DECISION_REF.match(exc["decision"])):
            raise ValueError(f"{name}: density_exception needs decision = D<n> or an issue-comment URL, got "
                             f"{exc.get('decision')!r}")
        if not (isinstance(v, (int, float)) and math.isfinite(v) and 512 <= v <= 1706):
            raise ValueError(f"{name}: density_exception px_per_m must be finite in 512..1706, got {v}")
        return float(v)
    return kpp_spec["size_full"] / k["S"]


def check_density_contract(name, spec, k, kpp_spec, tol=0.5):
    dens = spec["size_full"] / spec["finishes"][name]["S"]
    want = contract_density(name, spec, kpp_spec)
    if not abs(dens - want) <= tol:
        raise ValueError(f"{name}: texel density {dens:.1f} px/m != contract {want:.1f} px/m "
                         f"(KPP {kpp_spec['size_full'] / k['S']:.1f}; no approved density_exception)")


def load_kpp():
    return load(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "KPP1", "scripts",
                             "vpm_textures.json"))


def _finite(vertices):
    for v in vertices:
        if len(v) != 3 or not all(isinstance(c, (int, float)) and math.isfinite(c) for c in v):
            raise ValueError(f"non-finite or malformed vertex {v}")


def assign_finishes(vertices, faces, mat_ids, spec):
    """Return one finish name per polygon (fail-closed on unmapped / empty IDs)."""
    if not faces:
        raise ValueError("no polygons")
    if len(faces) != len(mat_ids):
        raise ValueError(f"{len(faces)} polygons but {len(mat_ids)} material IDs")
    _finite(vertices)
    src, empty, zero = spec["source_ids"], {int(i) for i in spec.get("empty_ids", [])}, spec["zero_m"]
    out = []
    for i, (f, m) in enumerate(zip(faces, mat_ids)):
        if int(m) in empty:
            raise ValueError(f"polygon {i}: material ID {m} is declared empty but has faces")
        rule = src.get(str(int(m)))
        if rule is None:
            raise ValueError(f"polygon {i}: material ID {m} has no finish mapping")
        if rule.get("split") == "below_zero":
            zmax = max(vertices[k][2] for k in f)
            out.append(rule["below"] if zmax <= zero else rule["above"])
        else:
            out.append(rule["finish"])
    return out


def facade_uv(vertices, face, lo, hi, tol=1e-3):
    """Metre UVs of a vertical face: u from the left corner of its facade seen from outside, v = world z.

    lo/hi: plan bbox (x, y) of the body. The facade is picked by the dominant horizontal normal axis; the winding
    follows the face (no mirrored islands). A face that is not vertical raises ValueError.
    """
    p = [vertices[k] for k in face]
    n = [0.0, 0.0, 0.0]
    for i in range(len(p)):
        a, b = p[i], p[(i + 1) % len(p)]
        n[0] += (a[1] - b[1]) * (a[2] + b[2])
        n[1] += (a[2] - b[2]) * (a[0] + b[0])
        n[2] += (a[0] - b[0]) * (a[1] + b[1])
    ln = math.sqrt(sum(c * c for c in n))
    if ln <= 0 or abs(n[2]) / ln > tol:
        raise ValueError(f"face {face} is not vertical; facade UV needs a wall face")
    if abs(n[1]) >= abs(n[0]):
        return [((q[0] - lo[0]) if n[1] < 0 else (hi[0] - q[0]), q[2]) for q in p]
    return [((q[1] - lo[1]) if n[0] > 0 else (hi[1] - q[1]), q[2]) for q in p]


def perimeter_drop(vertices, faces, finishes, drop_finish, tol=0.001):
    """Per plan side of the body bbox: covered length of drop faces reaching <= DROP_MIN_M (box bodies only)."""
    _finite(vertices)
    body = [k for f in faces for k in f if vertices[k][2] > 0.0]
    if not body:
        raise ValueError("no body above ±0.000")
    lo = [min(vertices[k][a] for k in body) for a in (0, 1)]
    hi = [max(vertices[k][a] for k in body) for a in (0, 1)]
    sides = {"x-": (0, lo[0], 1), "x+": (0, hi[0], 1), "y-": (1, lo[1], 0), "y+": (1, hi[1], 0)}
    report = {}
    for side, (axis, coord, along) in sides.items():
        iv = []
        for f, fin in zip(faces, finishes):
            p = [vertices[k] for k in f]
            if fin != drop_finish or min(q[2] for q in p) > DROP_MIN_M:
                continue
            if all(abs(q[axis] - coord) <= tol for q in p):
                iv.append((min(q[along] for q in p), max(q[along] for q in p)))
        iv.sort()
        covered, cur = 0.0, None
        for a, b in iv:
            if cur is None or a > cur[1] + tol:
                if cur:
                    covered += cur[1] - cur[0]
                cur = [a, b]
            else:
                cur[1] = max(cur[1], b)
        if cur:
            covered += cur[1] - cur[0]
        length = hi[along] - lo[along]
        report[side] = {"length_m": round(length, 4), "covered_m": round(covered, 4),
                        "ok": covered >= length - tol}
    return report
