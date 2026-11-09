"""Overlap gate `dt qa xview`: inv_xview on the local coordinates of every part, the postcondition of a build step (#527).

Review #514 (job vyatskaya-tow02): a job-local Blender overlap check said 0 where 3ds Max xView said 185 faces, while
`inv_xview` (contact rule) reproduced xView 185/185 and 0/0. This module is the gate the build loop calls.

Input: parts = named meshes with their vertices in place (float64, world) and the object location. `coords`:
- `local` (default): vertices minus the object location, float64 - the frame xView effectively measures in; site
  coordinates rounded to float32 give false contacts (review #514 XCHECK).
- `inplace`: world coordinates as stored.
- `as-stored`: the stored vertices with no location known (single-mesh NPZ of review #514); `local` refuses them.

Per part: Overlapping Vertices (ids in any vertex pair at <= vertex_m), Overlapping Faces (ids in any `contact` pair,
the xView selection), every face pair with its kind (contact / area / area+contact) and separation, every flagged face
with its partners, kinds and centre (in the checked frame; world = centre + location).

Bow-tie (non-manifold) vertices are their own finding: 3ds Max Editable Poly splits a vertex whose faces form two or
more edge-connected fans, then counts the split copies as Overlapping Vertices. Listed are
- `bowtie_vertices`: one vertex index with >= 2 fans (Poly would split it; inv_xview's vertex rule cannot see it);
- vertex pairs of kind `bowtie`: after welding every vertex pair (Max "Mesh + Weld"), the welded vertex has >= 2 fans,
  so converting back to Poly splits it again; kind `double` = a plain unwelded double that a weld removes.

Fail-closed: no parts, duplicate part names, an unknown part, profile or coords, NaN / inf vertices or location and
bad loop arrays raise ValueError; a part without faces fails. `passed` needs zero vertex pairs, zero face pairs of
any kind and zero bow-tie vertices in every part.
Pattern: none | new-case: overlap gate CLI over inv_xview on FBX/.blend/.npz parts in local coordinates (#527).
"""
import math
import os
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from dt_ai.ops import inv_xview
from dt_ai.ops.inv_quads import PolyMesh

NAME = "xview_gate"
COORDS = ("local", "inplace", "as-stored")
_LEGACY = {"vertices", "loop_total", "loop_start", "loop_vert"}


@dataclass(frozen=True)
class Part:
    name: str
    vertices: np.ndarray        # (n, 3) float64, in place (world)
    faces: tuple                # polygon index tuples, 0-based
    location: np.ndarray | None  # (3,) float64 object location; None = unknown


# ---- NPZ ------------------------------------------------------------------------------------------------------------

def _faces(lt, lv, ls=None, where=""):
    lt = np.asarray(lt)
    lv = np.asarray(lv)
    if lt.ndim != 1 or lv.ndim != 1 or lt.dtype.kind not in "iu" or lv.dtype.kind not in "iu":
        raise ValueError(f"{where}: loop arrays must be 1-D integer arrays")
    if (lt < 3).any():
        raise ValueError(f"{where}: a polygon has fewer than 3 loops")
    if int(lt.sum()) != len(lv):
        raise ValueError(f"{where}: {int(lt.sum())} loops for {len(lv)} loop vertices")
    if ls is None:
        ls = np.concatenate([[0], np.cumsum(lt)[:-1]]).astype(np.int64)
    ls = np.asarray(ls)
    if ls.shape != lt.shape or ls.dtype.kind not in "iu":
        raise ValueError(f"{where}: loop_start does not match loop_total")
    if len(lt) and (ls.min() < 0 or (ls + lt).max() > len(lv)):
        raise ValueError(f"{where}: loop arrays out of range")
    return tuple(tuple(int(i) for i in lv[s:s + n]) for s, n in zip(ls.tolist(), lt.tolist()))


def load_npz(path) -> list:
    """Parts of an NPZ: the dump format (names, v<i>, lt<i>, lv<i>, loc<i>) or the review #514 single-mesh format."""
    path = Path(path)
    with np.load(path, allow_pickle=False) as z:
        keys = set(z.files)
        if keys == _LEGACY:
            return [Part(path.stem, np.asarray(z["vertices"], dtype=np.float64),
                         _faces(z["loop_total"], z["loop_vert"], z["loop_start"], path.stem), None)]
        if "names" not in keys:
            raise ValueError(f"{path}: unknown NPZ keys {sorted(keys)}; expected 'names' + v/lt/lv/loc<i> "
                             f"or {sorted(_LEGACY)}")
        names = [str(n) for n in z["names"].tolist()]
        expected = {"names"} | {f"{k}{i}" for i in range(len(names)) for k in ("v", "lt", "lv", "loc")}
        if keys != expected:
            raise ValueError(f"{path}: NPZ keys do not match {len(names)} parts: missing "
                             f"{sorted(expected - keys)}, unknown {sorted(keys - expected)}")
        parts = []
        for i, n in enumerate(names):
            if z[f"v{i}"].dtype != np.float64:
                raise ValueError(f"{path}: part {n!r} vertices are {z[f'v{i}'].dtype}, expected float64")
            parts.append(Part(n, np.asarray(z[f"v{i}"]), _faces(z[f"lt{i}"], z[f"lv{i}"], where=n),
                              np.asarray(z[f"loc{i}"], dtype=np.float64)))
        return parts


def save_npz(path, parts) -> None:
    """Write parts in the dump format (the format tools/blender/xview_dump.py writes)."""
    data = {"names": np.array([p.name for p in parts], dtype=str)}
    for i, p in enumerate(parts):
        data[f"v{i}"] = np.asarray(p.vertices, dtype=np.float64)
        data[f"lt{i}"] = np.array([len(f) for f in p.faces], dtype=np.int64)
        data[f"lv{i}"] = np.array([x for f in p.faces for x in f], dtype=np.int64)
        data[f"loc{i}"] = np.zeros(3) if p.location is None else np.asarray(p.location, dtype=np.float64)
    with open(path, "wb") as fh:
        np.savez(fh, **data)


# ---- bow-tie --------------------------------------------------------------------------------------------------------

def fans(faces, nv: int) -> dict:
    """vertex -> number of edge-connected face fans around it, for vertices with >= 2 fans (non-manifold)."""
    parent: dict = {}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    first: dict = {}
    corners: dict = {}
    for k, f in enumerate(faces):
        g = [x for i, x in enumerate(f) if x != f[i - 1]]   # a weld can repeat an index; drop consecutive copies
        if len(set(g)) < 3:
            continue
        for i, x in enumerate(g):
            c = (k, i)
            parent[c] = c
            corners.setdefault(x, []).append(c)
            for y in (g[i - 1], g[(i + 1) % len(g)]):
                key = (x, y)
                if key in first:
                    a, b = find(first[key]), find(c)
                    if a != b:
                        parent[a] = b
                else:
                    first[key] = c
    out = {}
    for x, cs in corners.items():
        n = len({find(c) for c in cs})
        if n > 1:
            out[x] = n
    return out


def _weld_map(nv: int, a, b) -> np.ndarray:
    rep = np.arange(nv)

    def root(x):
        while rep[x] != x:
            rep[x] = rep[rep[x]]
            x = rep[x]
        return x

    for x, y in zip(a, b):
        rx, ry = root(int(x)), root(int(y))
        if rx != ry:
            rep[max(rx, ry)] = min(rx, ry)
    return np.array([root(i) for i in range(nv)])


# ---- report ---------------------------------------------------------------------------------------------------------

def _r(x) -> list:
    return [float(c) for c in np.asarray(x, dtype=np.float64)]


def part_gate(p: Part, tol: inv_xview.XviewTolerance, coords: str) -> dict:
    v = np.asarray(p.vertices, dtype=np.float64)
    if v.ndim != 2 or v.shape[1] != 3:
        raise ValueError(f"part {p.name!r}: vertices must be (n, 3)")
    if not np.isfinite(v).all():
        raise ValueError(f"part {p.name!r}: vertices must be finite")
    loc = None if p.location is None else np.asarray(p.location, dtype=np.float64)
    if loc is not None and (loc.shape != (3,) or not np.isfinite(loc).all()):
        raise ValueError(f"part {p.name!r}: location must be 3 finite numbers")
    if coords == "local":
        if loc is None:
            raise ValueError(f"part {p.name!r}: no object location stored; use --coords as-stored or inplace")
        v = v - loc
    mesh = PolyMesh(v, p.faces)
    r = inv_xview.part_report(p.name, mesh, tol)
    centre = [v[list(f)].mean(0) for f in mesh.faces]
    a = np.array([x - 1 for x, _, _ in r.vertex_pairs], dtype=np.int64)
    b = np.array([y - 1 for _, y, _ in r.vertex_pairs], dtype=np.int64)
    weld = _weld_map(len(v), a, b)
    welded_bowtie = fans([tuple(int(weld[i]) for i in f) for f in mesh.faces], len(v))
    vpairs = [{"a": x, "b": y, "distance_m": d, "centre": _r((v[x - 1] + v[y - 1]) / 2),
               "kind": "bowtie" if int(weld[x - 1]) in welded_bowtie else "double"} for x, y, d in r.vertex_pairs]
    bowtie = [{"vertex": x + 1, "fans": n, "centre": _r(v[x])} for x, n in sorted(fans(mesh.faces, len(v)).items())]
    fpairs, per_face = [], {}
    for i, j, kind, sep in r.face_pairs:
        fpairs.append({"a": i, "b": j, "kind": kind, "separation_m": sep,
                       "centre": _r((centre[i - 1] + centre[j - 1]) / 2)})
        for x, y in ((i, j), (j, i)):
            e = per_face.setdefault(x, {"id": x, "partners": [], "kinds": [], "xview": False,
                                        "centre": _r(centre[x - 1])})
            e["partners"].append(y)
            e["kinds"].append(kind)
            e["xview"] = e["xview"] or "contact" in kind
    by_kind = {k: sum(fp["kind"] == k for fp in fpairs) for k in ("contact", "area", "area+contact")}
    passed = bool(mesh.faces) and not vpairs and not fpairs and not bowtie
    return {"part": p.name, "location": None if loc is None else _r(loc), "vertices_count": len(v),
            "faces_count": len(mesh.faces),
            "overlapping_vertices": len(r.vertices), "overlapping_faces": len(r.xview_faces),
            "vertex_pairs": vpairs, "face_pairs": fpairs, "face_pairs_by_kind": by_kind,
            "xview_faces": list(r.xview_faces), "faces": [per_face[k] for k in sorted(per_face)],
            "bowtie_vertices": bowtie, "passed": passed,
            "reasons": ([] if mesh.faces else ["no faces"])}


def gate_report(parts, profile: str = "NPM", coords: str = "local", names=None,
                tol: inv_xview.XviewTolerance | None = None) -> dict:
    """The gate over `parts` (or the `names` among them). No part to check is an error, never a vacuous pass."""
    if coords not in COORDS:
        raise ValueError(f"unknown coords {coords!r}; expected one of {COORDS}")
    tol = (tol or inv_xview.tolerance_for(profile)).validate()
    parts = list(parts)
    seen = [p.name for p in parts]
    dup = sorted({n for n in seen if seen.count(n) > 1})
    if dup:
        raise ValueError(f"duplicate part names: {dup}")
    if names is not None:
        names = list(dict.fromkeys(names))
        missing = [n for n in names if n not in seen]
        if missing:
            raise ValueError(f"parts not in the input: {missing}; available: {seen[:20]}")
        parts = [p for p in parts if p.name in names]
    if not parts:
        raise ValueError("no parts to check")
    reps = [part_gate(p, tol, coords) for p in parts]
    total = {k: sum(r[k] for r in reps) for k in ("overlapping_vertices", "overlapping_faces")}
    total["vertex_pairs"] = sum(len(r["vertex_pairs"]) for r in reps)
    total["face_pairs"] = sum(len(r["face_pairs"]) for r in reps)
    total["face_pairs_by_kind"] = {k: sum(r["face_pairs_by_kind"][k] for r in reps)
                                   for k in ("contact", "area", "area+contact")}
    total["bowtie_vertices"] = sum(len(r["bowtie_vertices"]) for r in reps)
    total["bowtie_pairs"] = sum(vp["kind"] == "bowtie" for r in reps for vp in r["vertex_pairs"])
    total["parts_without_faces"] = sum(not r["faces_count"] for r in reps)
    return {"name": NAME, "kernel": inv_xview.NAME, "profile": profile, "coords": coords,
            "thresholds": {"vertex_m": tol.vertex_m, "face_m": tol.face_m, "parallel_cos_min": tol.parallel_cos_min},
            "totals": total, "passed": all(r["passed"] for r in reps), "parts": reps}


def summary_lines(rep: dict) -> list:
    t = rep["totals"]
    k = t["face_pairs_by_kind"]
    lines = [f"{p['part']}: Overlapping Faces {p['overlapping_faces']}, Overlapping Vertices "
             f"{p['overlapping_vertices']} ({len(p['vertex_pairs'])} pairs, "
             f"{sum(vp['kind'] == 'bowtie' for vp in p['vertex_pairs'])} bow-tie), bow-tie vertices "
             f"{len(p['bowtie_vertices'])}"
             + ("" if p["passed"] else " FAIL") for p in rep["parts"][:50]]
    lines.append(f"xview {rep['profile']} {rep['coords']}: Overlapping Faces {t['overlapping_faces']}, Overlapping "
                 f"Vertices {t['overlapping_vertices']} ({t['vertex_pairs']} pairs, {t['bowtie_pairs']} bow-tie); "
                 f"face pairs {t['face_pairs']} (contact {k['contact']}, area {k['area']}, area+contact "
                 f"{k['area+contact']}); bow-tie vertices {t['bowtie_vertices']}; "
                 f"{'PASS' if rep['passed'] else 'FAIL'}")
    return lines


# ---- CLI: dt qa xview -----------------------------------------------------------------------------------------------

DUMP_SCRIPT = Path(__file__).resolve().parents[3] / "tools" / "blender" / "xview_dump.py"
INPUTS = (".npz", ".fbx", ".blend")


def _sha256(path: Path) -> str:
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


UNIT_SYSTEMS = ("METRIC", "IMPERIAL", "NONE")


def to_metres(parts, manifest: dict) -> tuple:
    """Blender units of the dump -> metres: vertices and location times `scene.unit_settings.scale_length`.

    The dump stores raw Blender units; a .blend with scale_length 0.001 (millimetre scene) holds 1000 for 1 m. A
    missing, non-finite or non-positive scale, an unknown unit system, or a unitless scene (system NONE) with a
    scale other than 1 is an error: no verdict without known metres. Returns (parts in metres, unit provenance).
    """
    if "unit_scale" not in manifest or "unit_system" not in manifest:
        raise ValueError("Blender manifest has no unit_scale / unit_system; cannot convert to metres")
    scale, system = manifest["unit_scale"], manifest["unit_system"]
    if isinstance(scale, bool) or not isinstance(scale, (int, float)) or not math.isfinite(scale) or scale <= 0:
        raise ValueError(f"unsupported Blender unit scale {scale!r}; expected a finite positive scale_length")
    if system not in UNIT_SYSTEMS:
        raise ValueError(f"unsupported Blender unit system {system!r}; expected one of {UNIT_SYSTEMS}")
    if system == "NONE" and scale != 1:
        raise ValueError(f"Blender unit system NONE with unit scale {scale!r}: units unknown, cannot convert to metres")
    s = float(scale)
    out = [Part(p.name, np.asarray(p.vertices, dtype=np.float64) * s, p.faces,
                None if p.location is None else np.asarray(p.location, dtype=np.float64) * s) for p in parts]
    return out, {"unit_system": system, "unit_scale": s, "coordinates": "m"}


def _owned(path: Path, ident) -> bool:
    try:
        st = os.lstat(path)
    except FileNotFoundError:
        return False
    return (st.st_dev, st.st_ino) == ident


def publish(data: bytes, dest: Path) -> None:
    """Write `data` to a new `dest`, never replacing or writing through any existing file (no-clobber).

    The bytes go to an exclusively created, uniquely named temporary file beside `dest` (`tempfile.mkstemp`,
    O_EXCL), then are published with `os.link` (fails if `dest` exists); on file systems without hard links, Windows
    `os.rename` (also fails if `dest` exists). The temporary file is removed only while it is still ours (same inode).
    """
    import tempfile

    fd, tmp = tempfile.mkstemp(prefix=dest.name + ".", suffix=".partial", dir=dest.parent)
    tmp = Path(tmp)
    st = os.fstat(fd)
    ident = (st.st_dev, st.st_ino)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        try:
            os.link(tmp, dest)
        except FileExistsError:
            raise ValueError(f"{dest} exists (created by another writer during the run); nothing replaced") from None
        except OSError:
            if os.name != "nt":
                raise
            try:
                os.rename(tmp, dest)            # Windows: refuses an existing destination
            except FileExistsError:
                raise ValueError(f"{dest} exists (created by another writer during the run); nothing replaced") \
                    from None
    finally:
        if _owned(tmp, ident):
            os.unlink(tmp)


def run(src, out, profile="NPM", coords="local", parts=None, blender=None, timeout=3600) -> dict:
    """Load `src` (.npz directly, .fbx / .blend through headless Blender), gate it, write `out`; return the report.

    `out` (and, for FBX/.blend, `<out>.blender.log`) must be new and must not be the input; both are published by
    `publish` (exclusive unique temporary file + no-clobber link), so a file another writer creates at either name
    during the run is kept and the run fails. The Blender dump lives in a fresh temporary folder beside `out` and is
    removed afterwards; Blender units are converted to metres (`to_metres`); the input is never written or deleted.
    """
    import json
    import shutil
    import tempfile

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
    sha = _sha256(src)
    dump = None
    units = {"unit_system": None, "unit_scale": None, "coordinates": "m"}   # .npz: dump format, metres
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
        names = [o["name"] for o in dump.get("objects", [])]
        if names != [p.name for p in loaded]:
            raise ValueError(f"Blender manifest objects {names[:10]} do not match the dumped parts")
        loaded, units = to_metres(loaded, dump)
    rep = gate_report(loaded, profile, coords, parts)
    if _sha256(src) != sha:
        raise ValueError(f"input changed during the run: {src}")
    rep["input"] = {"path": str(src), "sha256": sha, "kind": ext[1:],
                    "parts_in_file": [p.name for p in loaded],
                    "not_selected": [p.name for p in loaded if p.name not in {q["part"] for q in rep["parts"]}],
                    "units": units,
                    "dropped": [] if dump is None else dump.get("dropped", []),
                    "blender": None if dump is None else {"version": dump.get("blender"), "log": str(log),
                                                         "scene": dump.get("scene")}}
    publish(json.dumps(rep, ensure_ascii=False, indent=1).encode("utf-8"), out)
    return rep
