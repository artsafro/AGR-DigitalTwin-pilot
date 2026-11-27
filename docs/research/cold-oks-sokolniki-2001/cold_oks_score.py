"""Cold OKS run scorer: a cold builder's Sokolniki NPM against the frozen key (#2001, Refs #1784).

new-case: docs/research/cold-oks-sokolniki-2001/cold_oks_score.py - evaluator of a cold OKS run against a hidden key.

Protocol and control results: docs/research/cold-oks-sokolniki-2001.md. The key lives OUTSIDE every clone and is
never named to the builder. One file, two interpreters:

Blender (4.4, headless):
  blender -b --factory-startup --python-exit-code 1 --python cold_oks_score.py -- fingerprint IN.fbx|IN.zip OUT.json
  blender ... -- perturb IN.fbx|IN.zip OUT.fbx shift DX DY DZ        (control: whole model moved)
  blender ... -- perturb IN.fbx|IN.zip OUT.fbx drop-facade AZ_DEG     (control: largest facade plane facing AZ removed)
Python (stdlib only):
  python cold_oks_score.py keycheck KEY_DIR
  python cold_oks_score.py score KEY_DIR KEY_SET.json CAND.json OUT.json

KEY_SET.json / CAND.json: {"run": {...}, "stages": {"<stage id>": {"fingerprint": FP.json, "xview": X.json,
"atlas": npm_atlas.json, "finish_map": MAP.json, "validate": V.json, "evidence": [...], "stops_asked": [...]}}}.
Key entries also carry "key_file" (path relative to KEY_DIR) so a fingerprint of another file is refused.
Fail closed: a key whose SHA256SUMS do not verify (stale / edited) scores 0 passes.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import sys
from pathlib import Path
from typing import Any

TOL_M = 0.10  # openings / lines / surface tolerance (fact: 5-10 cm)
SAMPLE_AREA_M2 = 1.0  # max area per surface sample
MIN_FACADE_M2 = 20.0  # facade groups smaller than this are reported, not gated
FACADE_COVER_MIN = 0.90  # every gated facade: share of key samples within TOL_M of the candidate
SURFACE_COVER_MIN = 0.95  # whole model
LINES_RECALL_MIN = 0.95  # body lattice lines of the key found in the candidate
OPENINGS_RECALL_MIN = 0.95
OPENINGS_PRECISION_MIN = 0.95  # candidate openings that match a key opening (invented openings fail)
SURFACE_PRECISION_MIN = 0.95  # whole model: share of candidate area within TOL_M of the key
FACADE_PRECISION_MIN = 0.90  # every candidate facade group >= MIN_FACADE_M2: share within TOL_M of the key
MATERIAL_AGREE_MIN = 0.90  # area share of key samples whose nearest candidate face has the same finish
DENSITY_RATIO = (0.5, 2.0)  # px/m per finish, candidate / key
TRIS_RATIO = (0.5, 2.0)
TRIS_LIMIT = 150_000  # NPM limit used on #1784
OPENING_RE = re.compile(r"^(WINDOW|DOOR|0[5-8]_|18_door)", re.IGNORECASE)
GLASS_RE = re.compile(r"glass", re.IGNORECASE)  # NPM glass is a separate material outside the atlas

# Stages of routes/npm-oks.md; "geometry" stages compare against the key, the rest are process stages.
STAGES = [
    ("0", "scene prepare [D390]", "process"),
    ("1", "sources / inputs", "process"),
    ("2", "parts / Gate 1", "process"),
    ("3", "BODY (lattice) [D373]", "body"),
    ("3i", "insets by the modelling plan [D336]", "insets"),
    ("4", "facade detail", "process"),
    ("5", "NPM derivation / atlas", "npm"),
    ("6", "delivery / export readback", "delivery"),
    ("7", "report / visual", "process"),
    ("8", "checker / delivery decision", "process"),
]
# STOP points: product choices Artem made on the key run; a builder that chose without asking fails the stage.
STOPS = {
    "0": ["S0-split: Step 0 layer split accepted by Artem in Max [D390]"],
    "1": ["S1-authority: source variant / units / address and district not invented"],
    "2": ["S2-parts: parts list hash confirmed (Gate 1)"],
    "3": ["S3-lines: volume / lines sheet accepted before the body [D375]",
          "S3-cuts: local door / sill cuts and seam rules [D375][D378]",
          "S3-openings: openings where Revit has glass but the lattice is blind [D408]"],
    "3i": ["S3i-plan: modelling plan picture (geometry / inset / texture / not shown) [D336]",
           "S3i-wells: roof wells inside parapets [D410]"],
    "5": ["S5-zoning: finish IDs and atlas layout [D412][D413]",
          "S5-windows: windows / doors / curtain walls as texture or geometry [D417][D418]"],
    "6": ["S6-contacts: inset-to-body xView contacts at delivery [D419]",
          "S6-scope: Ground / UCX / GeoJSON outside the package"],
    "7": ["S7-acceptance: Artem's visual verdict per stage"],
}


# ----------------------------------------------------------------------------- hashing / key


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def keycheck(key_dir: Path) -> dict:
    """Verify KEY_DIR/SHA256SUMS.txt; any missing / changed / unlisted file makes the key stale."""
    sums = key_dir / "SHA256SUMS.txt"
    problems, listed = [], {}
    if not sums.is_file():
        return {"ok": False, "problems": ["SHA256SUMS.txt missing"], "files": 0}
    for line in sums.read_text(encoding="utf-8").splitlines():
        if line.strip():
            digest, name = line.split(None, 1)
            listed[name.lstrip("*").strip()] = digest.lower()
    for name, digest in sorted(listed.items()):
        p = key_dir / name
        if not p.is_file():
            problems.append(f"missing {name}")
        elif sha256(p) != digest:
            problems.append(f"changed {name}")
    for p in sorted(key_dir.rglob("*")):
        rel = p.relative_to(key_dir).as_posix()
        if p.is_file() and rel != "SHA256SUMS.txt" and rel not in listed:
            problems.append(f"unlisted {rel}")
    return {"ok": not problems, "problems": problems, "files": len(listed), "sums_sha256": sha256(sums),
            "listed": listed}


# ----------------------------------------------------------------------------- geometry helpers


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _norm(a):
    return math.sqrt(_dot(a, a))


def tri_fan(poly):
    return [(poly[0], poly[i], poly[i + 1]) for i in range(1, len(poly) - 1)]


def tri_area(t):
    return 0.5 * _norm(_cross(_sub(t[1], t[0]), _sub(t[2], t[0])))


def face_normal_area(poly):
    n = [0.0, 0.0, 0.0]
    for t in tri_fan(poly):
        c = _cross(_sub(t[1], t[0]), _sub(t[2], t[0]))
        n = [n[0] + c[0], n[1] + c[1], n[2] + c[2]]
    ln = _norm(n)
    return ((n[0] / ln, n[1] / ln, n[2] / ln) if ln > 1e-12 else (0.0, 0.0, 0.0)), 0.5 * ln


def samples(t, max_area=SAMPLE_AREA_M2):
    """Deterministic surface samples: centroids of a 4-way midpoint split until each piece <= max_area."""
    a = tri_area(t)
    if a <= max_area:
        c = tuple((t[0][k] + t[1][k] + t[2][k]) / 3 for k in range(3))
        return [(c, a)]
    m01 = tuple((t[0][k] + t[1][k]) / 2 for k in range(3))
    m12 = tuple((t[1][k] + t[2][k]) / 2 for k in range(3))
    m20 = tuple((t[2][k] + t[0][k]) / 2 for k in range(3))
    out = []
    for s in ((t[0], m01, m20), (m01, t[1], m12), (m20, m12, t[2]), (m01, m12, m20)):
        out.extend(samples(s, max_area))
    return out


def point_tri_dist(p, t):
    """Exact point-triangle distance (Ericson, Real-Time Collision Detection 5.1.5)."""
    a, b, c = t
    ab, ac, ap = _sub(b, a), _sub(c, a), _sub(p, a)
    d1, d2 = _dot(ab, ap), _dot(ac, ap)
    if d1 <= 0 and d2 <= 0:
        q = a
    else:
        bp = _sub(p, b)
        d3, d4 = _dot(ab, bp), _dot(ac, bp)
        if d3 >= 0 and d4 <= d3:
            q = b
        else:
            vc = d1 * d4 - d3 * d2
            if vc <= 0 and d1 >= 0 and d3 <= 0:
                v = d1 / (d1 - d3)
                q = (a[0] + v * ab[0], a[1] + v * ab[1], a[2] + v * ab[2])
            else:
                cp = _sub(p, c)
                d5, d6 = _dot(ab, cp), _dot(ac, cp)
                if d6 >= 0 and d5 <= d6:
                    q = c
                else:
                    vb = d5 * d2 - d1 * d6
                    if vb <= 0 and d2 >= 0 and d6 <= 0:
                        w = d2 / (d2 - d6)
                        q = (a[0] + w * ac[0], a[1] + w * ac[1], a[2] + w * ac[2])
                    else:
                        va = d3 * d6 - d5 * d4
                        if va <= 0 and (d4 - d3) >= 0 and (d5 - d6) >= 0:
                            w = (d4 - d3) / ((d4 - d3) + (d5 - d6))
                            q = (b[0] + w * (c[0] - b[0]), b[1] + w * (c[1] - b[1]), b[2] + w * (c[2] - b[2]))
                        else:
                            den = 1.0 / (va + vb + vc)
                            v, w = vb * den, vc * den
                            q = (a[0] + ab[0] * v + ac[0] * w, a[1] + ab[1] * v + ac[1] * w,
                                 a[2] + ab[2] * v + ac[2] * w)
    return _norm(_sub(p, q))


class TriIndex:
    """Uniform grid over triangle bounding boxes (cell 1 m) for 'nearest face within tol' queries."""

    def __init__(self, tris, labels, cell=1.0):
        self.cell, self.tris, self.labels, self.grid = cell, tris, labels, {}
        for i, t in enumerate(tris):
            lo = [math.floor((min(v[k] for v in t) - TOL_M) / cell) for k in range(3)]
            hi = [math.floor((max(v[k] for v in t) + TOL_M) / cell) for k in range(3)]
            for x in range(lo[0], hi[0] + 1):
                for y in range(lo[1], hi[1] + 1):
                    for z in range(lo[2], hi[2] + 1):
                        self.grid.setdefault((x, y, z), []).append(i)

    def nearest(self, p, tol=TOL_M):
        key = tuple(math.floor(p[k] / self.cell) for k in range(3))
        best, label = None, None
        for i in self.grid.get(key, ()):
            d = point_tri_dist(p, self.tris[i])
            if d <= tol and (best is None or d < best):
                best, label = d, self.labels[i]
        return best, label


# ----------------------------------------------------------------------------- fingerprint analysis


def relabel(fp: dict, atlas: dict | None, finish_map: dict | None) -> list[str]:
    """Face finish labels: atlas region of the UV centroid (NPM single material) else material name; then map."""
    regions = (atlas or {}).get("finishes") or {}
    out = []
    for f in fp["faces"]:
        label = f["label"]
        if regions and f.get("uv") is not None and not GLASS_RE.search(label):
            u, v = f["uv"]
            label = "UV_OUTSIDE"
            for name, r in regions.items():
                if r["u0"] - 1e-6 <= u <= r["u0"] + r["size"] + 1e-6 and r["v0"] - 1e-6 <= v <= r["v0"] + r["size"] + 1e-6:
                    label = name
                    break
        out.append((finish_map or {}).get(label, label))
    return out


def analyse(fp: dict, labels: list[str]) -> dict:
    """Derived measures of one fingerprint: tris, bbox, samples by facade, lattice lines, openings, UV density."""
    tris, tri_labels, samp, lo, hi = [], [], [], [1e18] * 3, [-1e18] * 3
    hlines, vlines, open_faces, density = {}, {}, [], {}
    for f, label in zip(fp["faces"], labels):
        poly = [tuple(v) for v in f["v"]]
        for v in poly:
            lo = [min(lo[k], v[k]) for k in range(3)]
            hi = [max(hi[k], v[k]) for k in range(3)]
        n, area = face_normal_area(poly)
        if area < 1e-9:
            continue
        az = round(math.degrees(math.atan2(n[1], n[0])) / 5.0) * 5 % 360
        vertical = abs(n[2]) < 0.3
        d = _dot(n, poly[0])
        group = f"az{az:03d}@{round(d):+d}" if vertical else ("roof" if n[2] > 0 else "soffit")
        for t in tri_fan(poly):
            tris.append(t)
            tri_labels.append(label)
            for c, a in samples(t):
                samp.append((c, a, label, group))
        if vertical:
            for a, b in zip(poly, poly[1:] + poly[:1]):
                ln = _norm(_sub(b, a))
                if ln < 0.05:
                    continue
                if abs(a[2] - b[2]) < 0.01:
                    z = round((a[2] + b[2]) / 2, 2)
                    hlines[z] = hlines.get(z, 0.0) + ln
                elif math.hypot(a[0] - b[0], a[1] - b[1]) < 0.01:
                    xy = (round(a[0], 2), round(a[1], 2))
                    vlines[xy] = vlines.get(xy, 0.0) + ln
        if vertical and OPENING_RE.match(label):
            open_faces.append((poly, n, az, d))
        if f.get("uv_area") is not None and area > 1e-6:
            density.setdefault(label, []).append(math.sqrt(max(f["uv_area"], 0.0) / area))
    return {
        "tris": len(tris), "tri_list": tris, "tri_labels": tri_labels, "samples": samp,
        "bbox": [lo, hi], "hlines": {z: w for z, w in hlines.items() if w >= 1.0},
        "vlines": {xy: w for xy, w in vlines.items() if w >= 1.0},
        "openings": openings(open_faces),
        "density": {k: sorted(v)[len(v) // 2] for k, v in density.items()},
        "uv_outside": sum(1 for x in labels if x == "UV_OUTSIDE"),
    }


def openings(faces) -> list[dict]:
    """Connected opening faces (shared EDGE, same azimuth) -> in-plane rect (t along facade, z) + plane offset.

    A shared edge, not a shared vertex: openings that only touch at a corner (checkerboard) stay separate."""
    parent = list(range(len(faces)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    seen = {}
    for i, (poly, _n, az, _d) in enumerate(faces):
        rv = [(round(v[0], 3), round(v[1], 3), round(v[2], 3)) for v in poly]
        for a, b in zip(rv, rv[1:] + rv[:1]):
            key = (az, min(a, b), max(a, b))
            if key in seen:
                parent[find(i)] = find(seen[key])
            else:
                seen[key] = i
    comps = {}
    for i in range(len(faces)):
        comps.setdefault(find(i), []).append(i)
    out = []
    for idx in comps.values():
        az = faces[idx[0]][2]
        rad = math.radians(az)
        tdir = (-math.sin(rad), math.cos(rad))
        ts = [v[0] * tdir[0] + v[1] * tdir[1] for i in idx for v in faces[i][0]]
        zs = [v[2] for i in idx for v in faces[i][0]]
        out.append({"az": az, "d": sum(faces[i][3] for i in idx) / len(idx),
                    "rect": [min(ts), max(ts), min(zs), max(zs)]})
    return out


def _match_lines(key: dict, cand: dict, dist) -> float:
    if not key:
        return 1.0
    ck = list(cand)
    found = sum(w for k, w in key.items() if any(dist(k, c) <= TOL_M for c in ck))
    return found / sum(key.values())


def _same_opening(a: dict, b: dict) -> bool:
    return (abs((a["az"] - b["az"] + 180) % 360 - 180) <= 10 and abs(a["d"] - b["d"]) <= 0.5
            and all(abs(x - y) <= TOL_M for x, y in zip(a["rect"], b["rect"])))


def _match_openings(key: list, cand: list) -> tuple[float, list]:
    """Share of `key` openings found in `cand`; called both ways (recall: key->cand, precision: cand->key)."""
    missed = [o for o in key if not any(_same_opening(c, o) for c in cand)]
    return (1.0 - len(missed) / len(key)) if key else 1.0, missed


def _cover(samples_: list, index: TriIndex) -> tuple[float, float, dict]:
    """Area within TOL_M of the indexed mesh: (covered, total, {group: [total, covered]})."""
    groups, covered, total = {}, 0.0, 0.0
    for c, a, _label, group in samples_:
        d, _ = index.nearest(c)
        g = groups.setdefault(group, [0.0, 0.0])
        g[0] += a
        total += a
        if d is not None:
            g[1] += a
            covered += a
    return covered, total, groups


def _worst_facades(groups: dict, limit: float) -> tuple[list, list]:
    worst = sorted((g[1] / g[0], name, round(g[0], 1)) for name, g in groups.items()
                   if g[0] >= MIN_FACADE_M2 and name.startswith("az"))
    return worst, [w for w in worst if w[0] < limit]


def compare(key: dict, cand: dict, kind: str) -> list[dict]:
    """Ordered checks of one geometry stage; each {check, status, value, limit}."""
    checks = []

    def add(name, ok, value, limit):
        checks.append({"check": name, "status": "pass" if ok else "fail", "value": value, "limit": limit})

    shift = max(abs(a - b) for i in range(2) for a, b in zip(key["bbox"][i], cand["bbox"][i])) if key["tris"] else 0.0
    if not key["samples"] or not cand["samples"]:  # named refusal instead of ZeroDivisionError
        add("non_empty", False, {"key_samples": len(key["samples"]), "cand_samples": len(cand["samples"])}, "> 0 each")
        return checks
    add("transform_bbox", shift <= TOL_M, round(shift, 4), f"<= {TOL_M} m")
    index = TriIndex(cand["tri_list"], cand["tri_labels"])
    covered, total, groups = _cover(key["samples"], index)
    agree = 0.0
    for c, a, label, _group in key["samples"]:
        d, clabel = index.nearest(c)
        if d is not None and clabel == label:
            agree += a
    add("surface_cover", covered / total >= SURFACE_COVER_MIN, round(covered / total, 4), f">= {SURFACE_COVER_MIN}")
    worst, bad = _worst_facades(groups, FACADE_COVER_MIN)
    add("facade_cover", not bad, [[round(w[0], 3), w[1], w[2]] for w in (bad or worst)[:3]],
        f"every facade >= {MIN_FACADE_M2} m2 covered >= {FACADE_COVER_MIN}")
    # candidate -> key: surface the key does not have (invented walls, duplicated shells) is measured too
    pc, pt, pgroups = _cover(cand["samples"], TriIndex(key["tri_list"], key["tri_labels"]))
    prec = pc / pt if pt else 0.0
    add("surface_precision", prec >= SURFACE_PRECISION_MIN, round(prec, 4), f">= {SURFACE_PRECISION_MIN}")
    pworst, pbad = _worst_facades(pgroups, FACADE_PRECISION_MIN)
    add("facade_precision", not pbad, [[round(w[0], 3), w[1], w[2]] for w in (pbad or pworst)[:3]],
        f"every candidate facade >= {MIN_FACADE_M2} m2 within {TOL_M} m of the key >= {FACADE_PRECISION_MIN}")
    if kind == "body":
        hz = _match_lines(key["hlines"], cand["hlines"], lambda a, b: abs(a - b))
        vxy = _match_lines(key["vlines"], cand["vlines"], lambda a, b: math.hypot(a[0] - b[0], a[1] - b[1]))
        add("lattice_levels", hz >= LINES_RECALL_MIN, round(hz, 4), f">= {LINES_RECALL_MIN}")
        add("lattice_stations", vxy >= LINES_RECALL_MIN, round(vxy, 4), f">= {LINES_RECALL_MIN}")
    if kind in ("body", "npm"):
        rec, missed = _match_openings(key["openings"], cand["openings"])
        pre, invented = _match_openings(cand["openings"], key["openings"])
        add("openings", rec >= OPENINGS_RECALL_MIN and pre >= OPENINGS_PRECISION_MIN,
            {"recall": round(rec, 4), "precision": round(pre, 4), "key": len(key["openings"]),
             "cand": len(cand["openings"]), "missed": len(missed), "invented": len(invented)},
            f"recall >= {OPENINGS_RECALL_MIN}, precision >= {OPENINGS_PRECISION_MIN} at {TOL_M} m")
    if kind in ("insets", "npm"):
        add("material_ids", agree / total >= MATERIAL_AGREE_MIN, round(agree / total, 4), f">= {MATERIAL_AGREE_MIN}")
    if kind == "npm":
        add("uv_outside_atlas", cand["uv_outside"] == 0, cand["uv_outside"], "0 faces")
        ratios = {k: round(cand["density"].get(k, 0.0) / v, 3) for k, v in key["density"].items() if v > 0}
        off = {k: r for k, r in ratios.items() if not DENSITY_RATIO[0] <= r <= DENSITY_RATIO[1]}
        add("uv_density", not off, off or ratios, f"px/m ratio in {list(DENSITY_RATIO)}")
    ratio = cand["tris"] / max(key["tris"], 1)
    add("tris", TRIS_RATIO[0] <= ratio <= TRIS_RATIO[1] and cand["tris"] <= TRIS_LIMIT,
        {"cand": cand["tris"], "key": key["tris"], "ratio": round(ratio, 3)}, f"{list(TRIS_RATIO)} x key, <= {TRIS_LIMIT}")
    return checks


def xview_check(key_x: dict | None, cand_x: dict | None) -> dict:
    if cand_x is None:
        return {"check": "xview", "status": "fail", "value": "not_run", "limit": "candidate xView report"}
    kt, ct = (key_x or {}).get("totals", {}), cand_x.get("totals", {})
    keys = ("overlapping_faces", "overlapping_vertices")
    ok = all(ct.get(k, 1e9) <= kt.get(k, 0) for k in keys)
    return {"check": "xview", "status": "pass" if ok else "fail", "value": {k: ct.get(k) for k in keys},
            "limit": {k: f"<= key {kt.get(k, 0)}" for k in keys}}


def validate_status(report: dict) -> dict:
    out = {}
    for st in report.get("stages", []):
        s = st.get("status")
        if s is None:
            fs = [f.get("status") for f in st.get("findings", [])]
            s = "fail" if "fail" in fs else ("pass" if fs and all(x == "pass" for x in fs) else "review")
        out[st["id"]] = s
    return out


# ----------------------------------------------------------------------------- scoring


def _load(p) -> Any:
    return json.loads(Path(p).read_text(encoding="utf-8")) if p else None


def _evidence_check(p: str, run_dir: Path | None) -> dict:
    """Evidence = an existing FILE inside the builder's run folder (a bare existing path like C:/ is not evidence)."""
    ok, why = False, "no run folder"
    if run_dir is not None:
        root = Path(run_dir).resolve()
        f = (root / p).resolve()
        if not f.is_relative_to(root):
            why = "outside the run folder"
        elif not f.is_file():
            why = "not a file"
        else:
            ok, why = True, "file in run folder"
    return {"check": "evidence", "status": "pass" if ok else "fail", "value": p, "limit": why}


def score(key_dir: Path, key_set: dict, cand: dict, run_dir: Path | None = None) -> dict:
    """Score CAND against the key. STOP grading is switched by KEY_SET["score_stops"] only (evaluator-owned);
    any switch inside CAND is ignored. RUN_DIR = the builder's run folder (evidence must be files inside it)."""
    kc = keycheck(key_dir)
    score_stops = key_set.get("score_stops", True) is not False
    result = {"key": {k: kc[k] for k in ("ok", "problems", "files")}, "stages": [], "passes": 0,
              "first_failing_stage": None, "run": cand.get("run", {}), "score_stops": score_stops}
    if not kc["ok"]:
        for sid, name, _kind in STAGES:
            result["stages"].append({"id": sid, "name": name, "status": "not_scored", "first_failing": "key_stale"})
        result["first_failing_stage"] = "key_stale"
        return result
    for sid, name, kind in STAGES:
        ks, cs = key_set.get("stages", {}).get(sid), cand.get("stages", {}).get(sid)
        row = {"id": sid, "name": name, "kind": kind, "checks": []}
        if cs is None:
            row.update(status="not_reached", first_failing="no candidate output")
        else:
            asked = set(cs.get("stops_asked", []))
            for stop in STOPS.get(sid, []) if score_stops else []:
                sid_stop = stop.split(":")[0]
                row["checks"].append({"check": f"stop {sid_stop}", "status": "pass" if sid_stop in asked else "fail",
                                      "value": sid_stop in asked, "limit": stop})
            evidence = cs.get("evidence", [])
            if kind == "process" and not evidence:
                row["checks"].append({"check": "evidence", "status": "fail", "value": [],
                                      "limit": ">= 1 file in the run folder"})
            for p in evidence:
                row["checks"].append(_evidence_check(p, run_dir))
            if kind in ("body", "insets", "npm") and ks is not None:
                kfp = _load(ks["fingerprint"])
                want = kc["listed"].get(ks["key_file"])
                if kfp.get("source_sha256") != want:
                    row["checks"].insert(0, {"check": "key_fingerprint", "status": "fail",
                                             "value": kfp.get("source_sha256"), "limit": want})
                else:
                    cfp = _load(cs["fingerprint"])
                    ka = analyse(kfp, relabel(kfp, _load(ks.get("atlas")), None))
                    ca = analyse(cfp, relabel(cfp, _load(cs.get("atlas")), _load(cs.get("finish_map"))))
                    row["checks"] += compare(ka, ca, kind)
                    row["checks"].append(xview_check(_load(ks.get("xview")), _load(cs.get("xview"))))
            if kind == "delivery" and ks is not None:
                kv, cv = validate_status(_load(ks["validate"])), validate_status(_load(cs["validate"])) if cs.get("validate") else {}
                lost = sorted(k for k, s in kv.items() if s == "pass" and cv.get(k) != "pass")
                row["checks"].append({"check": "validate_no_worse", "status": "fail" if lost or not cv else "pass",
                                      "value": lost or cv, "limit": "every V-check passing on the key passes"})
            fails = [c for c in row["checks"] if c["status"] != "pass"]
            if not row["checks"]:  # nothing was measured: never a pass
                row.update(status="not_scored", first_failing="no checks")
            else:
                row["status"] = "fail" if fails else "pass"
                row["first_failing"] = fails[0]["check"] if fails else None
        result["stages"].append(row)
        if row["status"] == "pass":
            result["passes"] += 1
        elif result["first_failing_stage"] is None and row["status"] == "fail":
            result["first_failing_stage"] = f"{sid}: {row['first_failing']}"
    return result


# ----------------------------------------------------------------------------- Blender modes


def _blender_import(path: str):
    import tempfile
    import zipfile

    import bpy

    bpy.ops.wm.read_factory_settings(use_empty=True)
    if path.lower().endswith(".zip"):
        with zipfile.ZipFile(path) as z:
            member = next(n for n in z.namelist() if n.lower().endswith(".fbx"))
            path = z.extract(member, tempfile.mkdtemp())
    bpy.ops.import_scene.fbx(filepath=path, use_image_search=False)
    return bpy


def blender_fingerprint(src: str, out: str):
    bpy = _blender_import(src)
    objects, faces = [], []
    for o in bpy.data.objects:
        if o.type != "MESH":
            continue
        m, mw = o.data, o.matrix_world
        uv = m.uv_layers.active
        mats = [s.material.name if s.material else "-" for s in o.material_slots]
        verts = [tuple(round(c, 5) for c in (mw @ v.co)) for v in m.vertices]
        tris = 0
        for p in m.polygons:
            tris += len(p.vertices) - 2
            rec = {"o": len(objects), "label": mats[p.material_index] if p.material_index < len(mats) else "-",
                   "v": [verts[i] for i in p.vertices]}
            if uv is not None:
                pts = [uv.data[li].uv for li in p.loop_indices]
                rec["uv"] = [round(sum(q[0] for q in pts) / len(pts), 6), round(sum(q[1] for q in pts) / len(pts), 6)]
                rec["uv_area"] = round(abs(sum(pts[i][0] * pts[i - 1][1] - pts[i - 1][0] * pts[i][1]
                                               for i in range(len(pts)))) / 2, 12)
            faces.append(rec)
        objects.append({"name": o.name, "faces": len(m.polygons), "tris": tris, "materials": mats})
    data = {"source": src, "source_sha256": sha256(Path(src)), "objects": objects, "faces": faces}
    Path(out).write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    print(f"fingerprint {src}: {len(objects)} objects, {len(faces)} faces")


def blender_perturb(src: str, out: str, mode: str, args: list[str]):
    import bmesh

    bpy = _blender_import(src)
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    if mode == "shift":
        dx, dy, dz = (float(a) for a in args)
        for o in meshes:
            o.location = (o.location[0] + dx, o.location[1] + dy, o.location[2] + dz)
        print(f"shifted {len(meshes)} objects by {dx} {dy} {dz}")
    elif mode == "drop-facade":
        az = float(args[0])
        nd = (math.cos(math.radians(az)), math.sin(math.radians(az)), 0.0)
        planes = {}
        for o in meshes:
            for p in o.data.polygons:
                n = o.matrix_world.to_3x3() @ p.normal
                if n.length > 0 and _dot(n.normalized(), nd) > 0.95:
                    d = round(_dot(o.matrix_world @ p.center, nd))
                    planes[d] = planes.get(d, 0.0) + p.area
        d0 = max(planes, key=planes.get)
        removed = 0
        for o in meshes:
            bm = bmesh.new()
            bm.from_mesh(o.data)
            mw = o.matrix_world
            kill = [f for f in bm.faces if _dot((mw.to_3x3() @ f.normal).normalized() if f.normal.length else f.normal, nd) > 0.9
                    and abs(_dot(mw @ f.calc_center_median(), nd) - d0) <= 0.6]
            removed += len(kill)
            bmesh.ops.delete(bm, geom=kill, context="FACES")
            bm.to_mesh(o.data)
            bm.free()
        print(f"drop-facade az={az}: plane d={d0} area={planes[d0]:.1f} m2, removed {removed} faces")
    else:
        raise SystemExit(f"unknown perturb mode {mode}")
    bpy.ops.export_scene.fbx(filepath=out, use_selection=False, path_mode="COPY", embed_textures=False)


def main(argv: list[str]) -> int:
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    else:
        argv = argv[1:]
    cmd = argv[0]
    if cmd == "fingerprint":
        blender_fingerprint(argv[1], argv[2])
    elif cmd == "perturb":
        blender_perturb(argv[1], argv[2], argv[3], argv[4:])
    elif cmd == "keycheck":
        kc = keycheck(Path(argv[1]))
        print(json.dumps({k: kc[k] for k in ("ok", "problems", "files")}, ensure_ascii=False))
        return 0 if kc["ok"] else 1
    elif cmd == "score":
        key_set, cand = _load(argv[2]), _load(argv[3])
        res = score(Path(argv[1]), key_set, cand, run_dir=Path(argv[3]).resolve().parent)
        Path(argv[4]).write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"passes={res['passes']} first_failing={res['first_failing_stage']}")
        for row in res["stages"]:
            print(f"  {row['id']:>2} {row['status']:<11} {row.get('first_failing') or ''}")
    else:
        raise SystemExit(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
