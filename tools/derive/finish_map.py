"""new-case: shared atlas finish-spec validation and fresh output reservation (#1902)."""
import json
import math
import os
import re


def fresh_out_dir(out, inputs):
    """Create a NEW output directory; refuse an existing one or one that is/contains/is inside an input."""
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


def validate_elevations(name, t):
    """`pattern: elevations` (#1925 [D417]): drawings inside the tile, not overlapping, panes inside each drawing."""
    rgb = t.get("glass_rgb")
    if not (isinstance(rgb, list) and len(rgb) == 3 and all(isinstance(c, int) and 0 <= c <= 255 for c in rgb)):
        raise ValueError(f"finish {name}: elevations need glass_rgb as three ints 0..255, got {rgb}")
    cells = t.get("cells")
    if not isinstance(cells, dict) or not cells:
        raise ValueError(f"finish {name}: elevations need nonempty cells")
    boxes = []
    for cn, c in cells.items():
        u0, v0, u1, v1 = c["box"]
        w, h = c["size"]
        if not (0 <= u0 < u1 <= t["S"] and 0 <= v0 < v1 <= t["S"] and w > 0 and h > 0):
            raise ValueError(f"finish {name}: cell {cn} box {c['box']} / size {c['size']} outside the {t['S']} m tile")
        for b in boxes:
            if u0 < b[2] and b[0] < u1 and v0 < b[3] and b[1] < v1:
                raise ValueError(f"finish {name}: cell {cn} overlaps another cell")
        boxes.append((u0, v0, u1, v1))
        for p in c["panes"]:
            if not (0 <= p[0] < p[1] <= w + 1e-6 and 0 <= p[2] < p[3] <= h + 1e-6):
                raise ValueError(f"finish {name}: cell {cn} pane {p} outside its {w} x {h} m drawing")


def validate_spec(spec, kpp_spec=None, *, legend_check=None):
    """legend_check: optional caller-owned legend validator (job shims route their overrides here)."""
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
            if t.get("pattern") == "elevations":
                validate_elevations(name, t)
    src = spec.get("source_ids") or {}
    if not src:
        raise ValueError("spec has no source_ids")
    if any(r.get("split") == "facade" for r in src.values()) or spec.get("facades") is not None:
        validate_facades(spec)
    for sid, rule in src.items():
        if rule.get("split") == "below_zero":
            names = [rule["above"], rule["below"]]
        elif rule.get("split") == "facade":
            names = sorted({f["finish"] for f in spec["facades"].values()})
        else:
            names = [rule.get("finish")]
        if rule.get("split") not in (None, "below_zero", "facade"):
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
        raise ValueError("spec has a kpp_palette: supply the KPP reference spec explicitly (--kpp-spec)")
    if kpp_spec is not None:
        for name, ref in (spec.get("kpp_palette") or {}).items():
            k = kpp_spec["finishes"].get(ref["kpp_finish"])
            if k is None or k["udim"] != ref["kpp_udim"]:
                raise ValueError(f"{name}: KPP twin {ref} not found in the KPP spec")
            if fin[name]["rgb"] != k["rgb"]:
                raise ValueError(f"{name}: rgb {fin[name]['rgb']} != KPP {ref['kpp_finish']} {k['rgb']}")
            if fin[name]["kind"] == "full" and k["kind"] == "placeholder":  # user texture in the KPP colour
                check_user_texture(name, spec)
                check_density_contract(name, spec, density_twin(name, spec, kpp_spec), kpp_spec)
            elif fin[name]["kind"] == "full":  # same joints/noise/recess as the KPP VPM tile; only S/phase may differ
                for key in ("pattern", "P", "h_joints", "rough", "metal", "joint_half_mm"):
                    if fin[name].get(key) != k.get(key):
                        raise ValueError(f"{name}: {key} {fin[name].get(key)} != KPP {k.get(key)}")
                check_density_contract(name, spec, k, kpp_spec)
    for name, t in fin.items():
        if t.get("pattern") == "user_vjoints" and name not in (spec.get("kpp_palette") or {}):
            raise ValueError(f"{name}: a user-texture finish needs a kpp_palette twin (colour + density contract)")
        if t.get("pattern") == "user_vjoints" and not any(f.get("finish") == name
                                                          for f in (spec.get("facades") or {}).values()):
            raise ValueError(f"{name}: a user_vjoints finish needs a facade rib contract (spec facades: ribs per "
                             f"field from the building's colour-solution sheet); the joint period is not free")
    if spec.get("facades") is not None or "legend" in spec:
        (legend_check or validate_legend)(spec, kpp_spec)
    return True


LEGEND_TEXTURES = {"ribbed": ("user_vjoints",), "plain": (None,)}   # legend texture -> allowed finish patterns


def validate_legend(spec, kpp_spec=None):
    """The binding facade legend «Условные обозначения» [D171] (Artem 2026-10-22, all TEC26): every finish sits in one
    legend row; the RAL in the finish name = the row RAL (and, via kpp_palette, the KPP colour); a ribbed row (sandwich
    panels) only holds sandwich-joint finishes, a plain row only joint-free ones - a sandwich wall never stays
    untextured. Unknown finishes in a row and unknown textures are errors naming them."""
    rows = spec.get("legend")
    if not isinstance(rows, list) or not rows:
        raise ValueError("spec has no facade legend (hatch -> material -> RAL -> texture); required for TEC26 facades")
    fin = spec["finishes"]
    seen = {}
    for i, r in enumerate(rows):
        tex = r.get("texture")
        if tex not in LEGEND_TEXTURES:
            raise ValueError(f"legend row {i}: unsupported texture {tex!r} (allowed {sorted(LEGEND_TEXTURES)})")
        ral = str(r.get("ral", ""))
        if not re.fullmatch(r"\d{4}", ral):
            raise ValueError(f"legend row {i}: RAL must be four digits, got {ral!r}")
        for n in r.get("finishes") or []:
            if n not in fin:
                raise ValueError(f"legend row {i}: finish {n} is not declared in finishes")
            seen.setdefault(n, []).append(i)
            m = re.search(r"RAL(\d{4})", n)
            if not m or m.group(1) != ral:
                raise ValueError(f"{n}: legend row {i} says RAL {ral}, the finish name says "
                                 f"{m.group(1) if m else 'no RAL'}")
            pat = fin[n].get("pattern")
            if pat not in LEGEND_TEXTURES[tex]:
                raise ValueError(f"{n}: legend row {i} is {tex} but the finish pattern is {pat or 'plain'}")
    for n in fin:
        if n not in seen:
            raise ValueError(f"{n}: no legend row (every finish must map to one hatch of the facade legend)")
        if len(seen[n]) > 1:
            raise ValueError(f"{n}: in {len(seen[n])} legend rows {seen[n]}")
    if kpp_spec is not None:
        for n, ref in (spec.get("kpp_palette") or {}).items():
            k = kpp_spec["finishes"][ref["kpp_finish"]]
            km = re.search(r"RAL(\d{4})", ref["kpp_finish"])
            if not km or km.group(1) != re.search(r"RAL(\d{4})", n).group(1):
                raise ValueError(f"{n}: KPP twin {ref['kpp_finish']} is another RAL")
            if fin[n]["rgb"] != k["rgb"]:
                raise ValueError(f"{n}: rgb {fin[n]['rgb']} != KPP {ref['kpp_finish']} {k['rgb']} (same RAL = same colour)")
    return True


NORMALS = {"+x": (0, 1), "-x": (0, -1), "+y": (1, 1), "-y": (1, -1)}  # facade outward normal -> (axis index, sign)


def validate_facades(spec):
    """Per-facade rib contract ([D169], operator measurements on the building's own colour-solution sheet):
    `ribs` strips spread EVENLY over the panel field of `field_m` metres, so joints sit at field_lo + k * field_m / ribs
    (k = 1 .. ribs - 1; symmetric by construction) and the finish period P[0] must equal field_m / ribs. Fail-closed."""
    facades = spec.get("facades")
    if not isinstance(facades, dict) or not facades:
        raise ValueError("split 'facade' needs a non-empty spec facades block (rib contract per facade)")
    fin = spec.get("finishes") or {}
    seen, pitch = set(), {}
    for name, f in facades.items():
        n, fname, ribs, W = f.get("normal"), f.get("finish"), f.get("ribs"), f.get("field_m")
        if n not in NORMALS or n in seen:
            raise ValueError(f"facade {name}: normal must be one of {sorted(NORMALS)}, once each; got {n}")
        seen.add(n)
        t = fin.get(fname)
        if t is None or t.get("kind") != "full" or t.get("pattern") != "user_vjoints":
            raise ValueError(f"facade {name}: finish {fname} must be a declared full user_vjoints finish")
        if not (isinstance(ribs, int) and not isinstance(ribs, bool) and ribs >= 2):
            raise ValueError(f"facade {name}: ribs must be an int >= 2, got {ribs}")
        if not (isinstance(W, (int, float)) and math.isfinite(W) and W > 0):
            raise ValueError(f"facade {name}: field_m must be finite > 0, got {W}")
        P = t.get("P")
        p = W / ribs
        if not (isinstance(P, list) and P and isinstance(P[0], (int, float)) and abs(P[0] - p) <= 1e-6):
            raise ValueError(f"facade {name}: finish {fname} period P {P} != field {W} m / {ribs} ribs = {p:.6f} m "
                             f"(the rib count comes from the sheet, not from the texture image)")
        if fname in pitch and abs(pitch[fname] - p) > 1e-6:
            raise ValueError(f"facade {name}: finish {fname} is shared by facades with different pitches")
        pitch[fname] = p
    return True


DECISION_REF = re.compile(r"^(D\d+|https://github\.com/\S+#issuecomment-\d+)$")


def contract_density(name, spec, kpp_spec):
    """px/m a full finish must deliver: the KPP twin's density (KPP density contract),
    or the value of an approved `density_exception` that cites the user decision (D<n> or the issue-comment URL)."""
    ref = (spec.get("kpp_palette") or {}).get(name)
    if ref is None:
        raise ValueError(f"{name}: full finish without a KPP twin has no density contract")
    k = density_twin(name, spec, kpp_spec)
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


def density_twin(name, spec, kpp_spec):
    """The patterned KPP finish whose texel density `name` must deliver: its colour twin when that is patterned,
    else the declared `density_twin` (a user texture in the colour of a plain KPP finish)."""
    ref = (spec.get("kpp_palette") or {}).get(name)
    if ref is None:
        raise ValueError(f"{name}: full finish without a KPP twin has no density contract")
    k = kpp_spec["finishes"].get(ref["kpp_finish"])
    if k is not None and k["kind"] == "full":
        return k
    dt = ref.get("density_twin")
    kd = kpp_spec["finishes"].get((dt or {}).get("kpp_finish"))
    if not dt or kd is None or kd["udim"] != dt.get("kpp_udim") or kd["kind"] != "full":
        raise ValueError(f"{name}: KPP twin {ref.get('kpp_finish')} is plain; density_twin {dt} must name a patterned "
                         f"KPP finish (no density contract otherwise)")
    return kd


HEX64 = re.compile(r"^[0-9a-f]{64}$")


def check_user_texture(name, spec):
    """A `user_vjoints` finish: vertical joints only, laid out every P[0] by whole-period u shifts. The user image gives
    the joint profile (columns first_joint_px, kept 1:1 at the finish density - not resampled) and the panel colour/noise;
    the period P[0] is the facade rib contract (validate_facades), independent of the image's own joint spacing."""
    t = spec["finishes"][name]
    if t.get("pattern") != "user_vjoints":
        raise ValueError(f"{name}: a full finish on a plain KPP twin must be pattern user_vjoints, got {t.get('pattern')}")
    if t.get("h_joints") is not False or t.get("shift") != [True, False]:
        raise ValueError(f"{name}: vertical joints only: h_joints must be false and shift [true, false]")
    P = t.get("P")
    if not (isinstance(P, list) and len(P) == 2 and all(isinstance(x, (int, float)) and math.isfinite(x) and x > 0
                                                          for x in P)):
        raise ValueError(f"{name}: P must be two finite periods > 0, got {P}")
    st = t.get("source_texture") or {}
    if not (isinstance(st.get("path"), str) and isinstance(st.get("sha256"), str) and HEX64.match(st["sha256"])):
        raise ValueError(f"{name}: source_texture needs path and a lowercase hex sha256, got {st}")
    per, fj = st.get("period_px"), st.get("first_joint_px")
    if not (isinstance(per, int) and isinstance(fj, list) and len(fj) == 2 and all(isinstance(x, int) for x in fj)
            and 0 <= fj[0] < fj[1] and (fj[1] - fj[0]) % 2 == 0):
        raise ValueError(f"{name}: source_texture period_px / first_joint_px [a, b) malformed: {per}, {fj}")
    want = P[0] * spec["size_full"] / t["S"]
    if not (isinstance(per, int) and per > 0 and fj[1] <= per):
        raise ValueError(f"{name}: source_texture period_px {per} must be an int > 0 that holds the declared joint {fj}")
    # [D169] (supersedes the 0.60 m step): his texture supplies the colour, noise and ONE joint's profile;
    # the repeat comes from the sheet (facades.ribs), so the tile period `want` may differ from the source period.
    if not want >= 4 * (fj[1] - fj[0]):
        raise ValueError(f"{name}: tile period {want:.1f} px leaves no panel between {fj[1] - fj[0]} px joints")
    oz = t.get("outline_z_m")
    if oz is not None and not (isinstance(oz, list) and len(oz) == 2 and all(isinstance(x, (int, float)) and
                                                                            math.isfinite(x) for x in oz)
                               and 0 < oz[0] < oz[1] < t["S"] - spec["pad_m"]):
        raise ValueError(f"{name}: outline_z_m must be [z_lo, z_hi] inside the tile, got {oz}")


def check_density_contract(name, spec, k, kpp_spec, tol=0.5):
    dens = spec["size_full"] / spec["finishes"][name]["S"]
    want = contract_density(name, spec, kpp_spec)
    if not abs(dens - want) <= tol:
        raise ValueError(f"{name}: texel density {dens:.1f} px/m != contract {want:.1f} px/m "
                         f"(KPP {kpp_spec['size_full'] / k['S']:.1f}; no approved density_exception)")
