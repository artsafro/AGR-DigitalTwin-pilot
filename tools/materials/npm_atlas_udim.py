"""Collapse a VPM-shaped UDIM / Multi-Sub mesh into one NPM atlas (diffuse RGB + separate opacity) (#546).

Pattern: none | new-case: NPM atlas from a UDIM mesh - per-material crop of the used UV area, uniform affine UV
move into one 2048/1024 atlas, Ground texel band 10-40 px/m, pilot padding >= 8 px.

A Python re-implementation of the logic of the team script `VPM_to_NPM.ms` (Drive copy, 706 lines; no MAXScript
copied). Line ranges of the script are cited in `tools/materials/README.md`, section "NPM atlas from a UDIM mesh".

Normative references (docs/domain/uv-textures.md, standards/NPM_STANDARD.yaml):
- reg p.9 §5.4: >= 8 px between neighbouring islands with unique images (`island_padding_px_min` 8; the script
  uses 6 px). Here every island keeps >= padding px to its cell edge, so two islands are >= 2 x padding apart.
- reg p.9 §5.5, [D020]: no alpha in any NPM image; opacity only as a separate `_o_` map.
- reg p.10 §6.1, [D097]: NPM Ground relief density 10..40 px per linear metre (inclusive bounds).
- reg p.3-4, conflict #5: a 128x128 one-colour placeholder exists only for flat Metallic/Roughness maps. This tool
  writes no MR maps, so it never writes a 128 px placeholder; a one-colour diffuse becomes a flat "plug" cell in the
  diffuse atlas. A small but patterned map (the script's <= 512 px plug rule) stays a texture cell.

Algorithm choices (not normative): shelf packing by cell height; Ground target texel searched down from 35 px/m by
x0.96 steps; OKS scale bisected; Lanczos resampling of a tile-wrapped crop; plug faces scaled one by one about
their centroid (flat colour, so overlap inside the plug cell is harmless).

Texel density is directional: per fan triangle the singular values of the metre -> pixel map; both the least and
the most stretched direction must sit in the band (an area mean hides anisotropy).

Inputs: an OBJ + MTL (`usemtl` per face; `map_Kd` may hold `<UDIM>`; `Kd` for flat materials; optional `map_d`;
`d` / `Tr` multiply the opacity; any directive the atlas cannot carry is an error, harmless scalars are reported)
or an in-memory `UdimMesh` + `MaterialSource` map. FBX is not read: convert to OBJ first (error, not a guess).
Mesh units are metres times `unit_m`. Outputs (new files only, inputs never written): `<base>_d.png` (RGB),
`<base>_o.png` (L, only when some material is transparent), `<base>.obj` + `<base>.mtl` (same geometry, one
material, remapped UV) and `<base>_report.json`.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image

ATLAS_SIZES = (1024, 2048)
PADDING_MIN_PX = 8  # standards/NPM_STANDARD.yaml textures.island_padding_px_min
GROUND_MIN, GROUND_MAX = 10.0, 40.0  # reg p.10 §6.1 [D097]
TARGET_PX_M = 35.0  # script default (VPM_to_NPM.ms:31)
PLUG_PX_M = 12.5  # script default (VPM_to_NPM.ms:32)
PLUG_CELL_PX = 16  # OKS plug interior (VPM_to_NPM.ms:38)
BACKGROUND = (90, 90, 90)  # script atlas clear colour (VPM_to_NPM.ms:382)
EPS = 1e-6


class AtlasError(ValueError):
    """Input or configuration the packer refuses (names the element)."""


@dataclass(frozen=True)
class MaterialSource:
    name: str
    diffuse: Path | None = None  # may contain <UDIM>
    color: tuple[int, int, int] | None = None  # flat material (Kd x 255)
    opacity: Path | None = None  # optional separate opacity map (may contain <UDIM>)
    dissolve: float = 1.0  # MTL `d` (or 1 - `Tr`): multiplies the opacity
    ignored: tuple[tuple[str, str, str], ...] = ()  # (directive, value, reason) not carried into the atlas


@dataclass(frozen=True)
class UdimMesh:
    vertices: np.ndarray  # (N, 3) in mesh units
    uvs: np.ndarray  # (M, 2)
    faces: tuple[tuple[int, ...], ...]
    face_uvs: tuple[tuple[int, ...], ...]
    face_materials: tuple[str, ...]
    normals: np.ndarray | None = None
    face_normals: tuple[tuple[int, ...], ...] | None = None
    name: str = "mesh"


@dataclass
class _Rec:
    name: str
    faces: list[int]
    tile: int = 1001
    tu: int = 0
    tv: int = 0
    W: int = 0
    H: int = 0
    rgb: np.ndarray | None = None
    alpha: np.ndarray | None = None
    plug: bool = False
    color: tuple[int, int, int] = (128, 128, 128)
    plug_alpha: int = 255
    dens: dict[int, tuple[float, float]] = field(default_factory=dict)  # face -> (min, max) source px/m
    x0: float = 0.0
    x1: float = 0.0
    y0: float = 0.0
    y1: float = 0.0
    k: float = 1.0
    dw: int = 0
    dh: int = 0
    cx: int = 0
    cy: int = 0
    bx0: float = 0.0
    by0: float = 0.0
    sources: list[str] = field(default_factory=list)


# ---------------------------------------------------------------- geometry helpers
def _face_texel(pts_m: np.ndarray, px: np.ndarray) -> tuple[float, float] | None:
    """Directional density of one face: (min, max) singular value over its fan triangles of the affine map
    metre -> pixel (px per linear metre along the least / most stretched direction). None: no triangle has area."""
    lo, hi = math.inf, 0.0
    for i in range(1, len(pts_m) - 1):
        e1, e2 = pts_m[i] - pts_m[0], pts_m[i + 1] - pts_m[0]
        l1 = float(np.linalg.norm(e1))
        n = np.cross(e1, e2)
        an = float(np.linalg.norm(n))
        if l1 <= 1e-12 or an <= 2e-12:  # triangle area <= 1e-12 m2
            continue
        x = e1 / l1
        y = np.cross(n, x) / an
        g = np.array([[l1, float(e2 @ x)], [0.0, float(e2 @ y)]])
        q = np.stack([px[i] - px[0], px[i + 1] - px[0]], axis=1)
        sv = np.linalg.svd(q @ np.linalg.inv(g), compute_uv=False)
        lo, hi = min(lo, float(sv[1])), max(hi, float(sv[0]))
    return None if hi == 0.0 and lo == math.inf else (lo, hi)


def _plane_offsets(pts_m: np.ndarray) -> np.ndarray:
    """Face corners in metres in its own plane (Newell normal, first edge as x), centred on the centroid."""
    n = np.zeros(3)
    for i in range(len(pts_m)):
        n += np.cross(pts_m[i], pts_m[(i + 1) % len(pts_m)])
    c = pts_m.mean(axis=0)
    nl = float(np.linalg.norm(n))
    if nl <= 2e-12:
        return np.zeros((len(pts_m), 2))
    n /= nl
    x = None
    for i in range(len(pts_m)):
        e = pts_m[(i + 1) % len(pts_m)] - pts_m[i]
        e = e - (e @ n) * n
        if np.linalg.norm(e) > 1e-12:
            x = e / np.linalg.norm(e)
            break
    y = np.cross(n, x)
    d = pts_m - c
    return np.stack([d @ x, d @ y], axis=1)


def _same_path(a: Path, b: Path) -> bool:
    ra, rb = os.path.normcase(str(a.resolve())), os.path.normcase(str(b.resolve()))
    return ra == rb


# ---------------------------------------------------------------- OBJ / MTL
def _finite(vals: list[float], what: str, line_no: int) -> list[float]:
    if not all(math.isfinite(v) for v in vals):
        raise AtlasError(f"line {line_no}: non-finite {what}")
    return vals


def read_obj(path: Path) -> tuple[UdimMesh, dict[str, MaterialSource]]:
    path = Path(path)
    if path.suffix.lower() == ".fbx":
        raise AtlasError(f"{path.name}: FBX input is not read by this tool; export the mesh to OBJ+MTL")
    if path.suffix.lower() != ".obj":
        raise AtlasError(f"{path.name}: unsupported mesh format (OBJ expected)")
    verts, uvs, normals, faces, fuv, fn, fmat = [], [], [], [], [], [], []
    mtllibs: list[Path] = []
    cur = None
    name = path.stem
    for no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        tag, *rest = line.split()
        if tag == "v":
            verts.append(_finite([float(t) for t in rest[:3]], "vertex", no))
        elif tag == "vt":
            uvs.append(_finite([float(t) for t in rest[:2]], "uv", no))
        elif tag == "vn":
            normals.append(_finite([float(t) for t in rest[:3]], "normal", no))
        elif tag == "f":
            if cur is None:
                raise AtlasError(f"line {no}: face before any usemtl")
            vi, ti, ni = [], [], []
            for tok in rest:
                parts = tok.split("/")
                if len(parts) < 2 or not parts[1]:
                    raise AtlasError(f"line {no}: face {len(faces)} has no UV index")
                vi.append(int(parts[0]) - 1)
                ti.append(int(parts[1]) - 1)
                ni.append(int(parts[2]) - 1 if len(parts) > 2 and parts[2] else -1)
            if len(vi) < 3:
                raise AtlasError(f"line {no}: face with fewer than 3 vertices")
            faces.append(tuple(vi))
            fuv.append(tuple(ti))
            fn.append(tuple(ni))
            fmat.append(cur)
        elif tag == "usemtl":
            cur = " ".join(rest)
        elif tag == "mtllib":
            mtllibs.append(path.parent / " ".join(rest))
        elif tag in ("o", "g"):
            name = " ".join(rest) or name
        elif tag == "s":
            continue
        else:
            raise AtlasError(f"line {no}: unsupported OBJ statement {tag!r}")
    if not faces:
        raise AtlasError(f"{path.name}: no faces")
    has_n = any(i >= 0 for f in fn for i in f)
    if has_n and any(i < 0 for f in fn for i in f):
        raise AtlasError(f"{path.name}: normals on some faces only")
    mesh = UdimMesh(np.array(verts, float).reshape(-1, 3), np.array(uvs, float).reshape(-1, 2), tuple(faces),
                    tuple(fuv), tuple(fmat), np.array(normals, float).reshape(-1, 3) if has_n else None,
                    tuple(fn) if has_n else None, name)
    mats: dict[str, MaterialSource] = {}
    for lib in mtllibs:
        mats.update(read_mtl(lib))
    return mesh, mats


# MTL directives this tool does not carry into the NPM atlas but that cannot change the diffuse / opacity
# result; each one is reported per material in `ignored_mtl` (never dropped silently).
_MTL_IGNORED = {
    "Ka": "ambient colour: the NPM atlas carries diffuse and opacity only",
    "Ks": "specular colour: the NPM atlas carries diffuse and opacity only",
    "Ns": "specular exponent: the NPM atlas carries diffuse and opacity only",
    "Ni": "index of refraction: the NPM atlas carries diffuse and opacity only",
    "illum": "illumination model: the NPM atlas carries diffuse and opacity only",
}
# scalar directives accepted only at their neutral value (anything else changes the look -> error)
_MTL_NEUTRAL = {"Ke": (0.0, 0.0, 0.0), "Tf": (1.0, 1.0, 1.0)}
_MTL_MAPS = ("map_Kd", "map_d")


def _map_file(path: Path, no: int, cur: str, tag: str, rest: list[str]) -> Path:
    for tok in rest:
        if tok.startswith("-"):
            raise AtlasError(f"{path.name} line {no}: material {cur!r}: {tag} option {tok!r} (texture transform/"
                             f"clamp/blend) is not supported; bake it into the map")
    if not rest:
        raise AtlasError(f"{path.name} line {no}: material {cur!r}: {tag} without a file")
    return path.parent / " ".join(rest)


def read_mtl(path: Path) -> dict[str, MaterialSource]:
    """Fail-closed MTL reader: every directive is carried (Kd, map_Kd, map_d, d/Tr), reported as ignored with its
    reason (`_MTL_IGNORED`, neutral Ke/Tf, Kd under map_Kd), or an error naming the material and directive."""
    path = Path(path)
    if not path.is_file():
        raise AtlasError(f"mtllib {path.name}: file not found")
    out: dict[str, dict] = {}
    cur = None
    for no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        tag, *rest = line.split()
        if tag == "newmtl":
            cur = " ".join(rest)
            if cur in out:
                raise AtlasError(f"{path.name} line {no}: material {cur!r} defined twice")
            out[cur] = {"ignored": []}
            continue
        if cur is None:
            raise AtlasError(f"{path.name} line {no}: directive {tag!r} before any newmtl")
        m = out[cur]
        where = f"{path.name} line {no}: material {cur!r}"
        if tag in m and tag != "ignored":
            raise AtlasError(f"{where}: directive {tag!r} given twice")
        if tag == "Kd":
            m[tag] = tuple(_finite([float(t) for t in rest[:3]], "Kd", no))
        elif tag in _MTL_MAPS:
            m[tag] = _map_file(path, no, cur, tag, rest)
        elif tag in ("d", "Tr"):
            if any(t.startswith("-") for t in rest) or len(rest) != 1:
                raise AtlasError(f"{where}: {tag} {' '.join(rest)} is not supported (one value 0..1 expected)")
            v = _finite([float(rest[0])], tag, no)[0]
            if not 0.0 <= v <= 1.0:
                raise AtlasError(f"{where}: {tag} {rest[0]} outside 0..1")
            m[tag] = v
        elif tag in _MTL_IGNORED:
            m["ignored"].append((tag, " ".join(rest), _MTL_IGNORED[tag]))
        elif tag in _MTL_NEUTRAL:
            v = tuple(_finite([float(t) for t in rest[:3]], tag, no))
            if v != _MTL_NEUTRAL[tag]:
                raise AtlasError(f"{where}: {tag} {' '.join(rest)} is not supported (only the neutral value)")
            m["ignored"].append((tag, " ".join(rest), "neutral value, no effect"))
        elif tag.startswith("map_") or tag in ("bump", "disp", "decal", "refl", "norm"):
            raise AtlasError(f"{where}: map directive {tag!r} is not carried into the NPM atlas (diffuse + "
                             f"opacity only); remove it or bake it into map_Kd")
        else:
            raise AtlasError(f"{where}: unsupported MTL directive {tag!r}")
    res = {}
    for n, m in out.items():
        d = 1.0
        if "d" in m and "Tr" in m and abs(m["d"] - (1.0 - m["Tr"])) > 1e-6:
            raise AtlasError(f"{path.name}: material {n!r}: d and Tr disagree (d {m['d']}, Tr {m['Tr']})")
        if "d" in m:
            d = m["d"]
        elif "Tr" in m:
            d = 1.0 - m["Tr"]
        color = None
        if "Kd" in m:
            color = tuple(int(round(min(max(c, 0.0), 1.0) * 255)) for c in m["Kd"])
            if "map_Kd" in m and m["Kd"] != (1.0, 1.0, 1.0):
                m["ignored"].append(("Kd", " ".join(map(str, m["Kd"])),
                                     "map_Kd replaces Kd (3ds Max OBJ convention); tint not applied"))
        res[n] = MaterialSource(n, m.get("map_Kd"), color, m.get("map_d"), d, tuple(m["ignored"]))
    return res


# ---------------------------------------------------------------- analysis
def _load_rgb_alpha(path: Path, what: str) -> tuple[np.ndarray, np.ndarray | None]:
    if not path.is_file():
        raise AtlasError(f"{what}: map {path} not found")
    with Image.open(path) as im:
        im.load()
        has_alpha = im.mode in ("RGBA", "LA", "PA") or (im.mode == "P" and "transparency" in im.info)
        rgba = np.asarray(im.convert("RGBA"))
    alpha = rgba[..., 3].copy() if has_alpha and rgba[..., 3].min() < 255 else None
    return rgba[..., :3].copy(), alpha


def _udim_path(p: Path, tile: int) -> Path:
    s = str(p)
    for tok in ("<UDIM>", "<udim>"):
        s = s.replace(tok, str(tile))
    return Path(s)


def analyze(mesh: UdimMesh, materials: dict[str, MaterialSource], unit_m: float = 1.0) -> list[_Rec]:
    if not math.isfinite(unit_m) or unit_m <= 0:
        raise AtlasError(f"unit_m must be a positive finite number, got {unit_m}")
    if not mesh.faces:
        raise AtlasError("mesh has no faces")
    if not (len(mesh.faces) == len(mesh.face_uvs) == len(mesh.face_materials)):
        raise AtlasError("faces, face_uvs and face_materials differ in length")
    for arr, what in ((mesh.vertices, "vertex"), (mesh.uvs, "uv")):
        if arr.size and not np.isfinite(arr).all():
            raise AtlasError(f"non-finite {what} coordinate")
    nv, nt = len(mesh.vertices), len(mesh.uvs)
    recs: dict[str, _Rec] = {}
    owner: dict[int, str] = {}
    for f, (vi, ti, m) in enumerate(zip(mesh.faces, mesh.face_uvs, mesh.face_materials)):
        if len(vi) != len(ti) or len(vi) < 3:
            raise AtlasError(f"face {f}: vertex/UV index count mismatch or < 3")
        if min(vi) < 0 or max(vi) >= nv or min(ti) < 0 or max(ti) >= nt:
            raise AtlasError(f"face {f}: index out of range")
        if m not in materials:
            raise AtlasError(f"face {f}: material {m!r} has no definition (MTL / material map)")
        recs.setdefault(m, _Rec(m, [])).faces.append(f)
        for t in ti:
            if owner.setdefault(t, m) != m:
                raise AtlasError(f"UV vertex {t} is shared by materials {owner[t]!r} and {m!r}; split the UV seam")
    out = []
    for name in sorted(recs):
        r = recs[name]
        src = materials[name]
        idx = sorted({t for f in r.faces for t in mesh.face_uvs[f]})
        uv = mesh.uvs[idx]
        umn, vmn = uv.min(axis=0)
        umx, vmx = uv.max(axis=0)
        r.tu, r.tv = int(math.floor((umn + umx) / 2)), int(math.floor((vmn + vmx) / 2))
        if not (0 <= r.tu <= 9 and 0 <= r.tv <= 9):
            raise AtlasError(f"material {name!r}: UV centre outside the UDIM grid 1001..1100")
        if umn < r.tu - EPS or umx > r.tu + 1 + EPS or vmn < r.tv - EPS or vmx > r.tv + 1 + EPS:
            raise AtlasError(f"material {name!r}: UV island crosses a UDIM tile border")
        r.tile = 1001 + r.tu + 10 * r.tv
        dis = src.dissolve
        if not (isinstance(dis, (int, float)) and math.isfinite(dis) and 0.0 <= dis <= 1.0):
            raise AtlasError(f"material {name!r}: dissolve {dis} outside 0..1")
        if src.diffuse is not None:
            p = _udim_path(src.diffuse, r.tile)
            r.rgb, r.alpha = _load_rgb_alpha(p, f"material {name!r}")
            r.sources.append(str(p))
            r.H, r.W = r.rgb.shape[:2]
            if src.opacity is not None:
                if r.alpha is not None:
                    raise AtlasError(f"material {name!r}: both diffuse alpha and map_d opacity")
                po = _udim_path(src.opacity, r.tile)
                orgb, oal = _load_rgb_alpha(po, f"material {name!r} opacity")
                if oal is not None or orgb.shape[:2] != (r.H, r.W):
                    raise AtlasError(f"material {name!r}: opacity map must be grey, same size as diffuse")
                r.alpha = orgb[..., 0].copy()
                r.sources.append(str(po))
            if dis < 1.0:  # MTL d / Tr multiplies the opacity (map or opaque)
                base = np.full((r.H, r.W), 255.0) if r.alpha is None else r.alpha.astype(float)
                r.alpha = np.clip(np.rint(base * dis), 0, 255).astype(np.uint8)
            flat_rgb = bool((r.rgb == r.rgb[0, 0]).all())
            flat_a = r.alpha is None or bool((r.alpha == r.alpha[0, 0]).all())
            if flat_rgb and flat_a:  # one-colour map -> plug (pilot rule; script: <= 512 px, VPM_to_NPM.ms:167)
                r.plug, r.color = True, tuple(int(c) for c in r.rgb[0, 0])
                r.plug_alpha = 255 if r.alpha is None else int(r.alpha[0, 0])
        elif src.color is not None:
            if src.opacity is not None:
                raise AtlasError(f"material {name!r}: map_d without map_Kd is not supported")
            r.plug, r.color, r.W, r.H = True, tuple(int(c) for c in src.color), 1, 1
            r.plug_alpha = int(round(255 * dis))
        else:
            raise AtlasError(f"material {name!r}: neither map_Kd nor Kd")
        # used UV rect in source pixel space (y down)
        r.x0, r.x1 = (umn - r.tu) * r.W, (umx - r.tu) * r.W
        r.y0, r.y1 = (1 - (vmx - r.tv)) * r.H, (1 - (vmn - r.tv)) * r.H
        for f in r.faces:
            t = _face_texel(mesh.vertices[list(mesh.faces[f])] * unit_m, _src_px(mesh, r, f))
            if t is not None:
                r.dens[f] = t
        out.append(r)
    return out


# ---------------------------------------------------------------- planning
def _plug_extent(mesh: UdimMesh, r: _Rec, mode: str, plug_px_m: float, cell_px: int,
                 unit_m: float) -> tuple[float, float, dict]:
    """Per plug face: corner offsets (atlas px) about the cell centre. Ground: the face laid flat in its own plane at
    exactly plug_px_m in every direction (flat colour, so the source UV shape carries nothing). OKS: the source UV
    shape scaled to fit cell_px."""
    offs, ext_x, ext_y = {}, 0.0, 0.0
    for f in r.faces:
        if mode == "ground":
            o = _plane_offsets(mesh.vertices[list(mesh.faces[f])] * unit_m) * plug_px_m
        else:
            pts = _src_px(mesh, r, f)
            size = float((pts.max(axis=0) - pts.min(axis=0)).max())
            o = (pts - pts.mean(axis=0)) * (cell_px / size if size > 0 else 0.0)
        offs[f] = o
        ext_x = max(ext_x, 2 * float(np.abs(o[:, 0]).max()))
        ext_y = max(ext_y, 2 * float(np.abs(o[:, 1]).max()))
    return ext_x, ext_y, offs


def _src_px(mesh: UdimMesh, r: _Rec, f: int) -> np.ndarray:
    uv = mesh.uvs[list(mesh.face_uvs[f])]
    return np.stack([(uv[:, 0] - r.tu) * r.W, (1 - (uv[:, 1] - r.tv)) * r.H], axis=1)


def _cell(r: _Rec, pad: int, k: float) -> None:
    r.k = k
    gap = pad + 1  # >= pad px between the island and the cell edge
    r.dw = int(math.ceil((r.x1 - r.x0) * k)) + 2 * gap
    r.dh = int(math.ceil((r.y1 - r.y0) * k)) + 2 * gap
    r.bx0, r.by0 = r.x0 - gap / k, r.y0 - gap / k


def _shelf(recs: list[_Rec], size: int) -> bool:
    x = y = shelf = 0
    for r in sorted(recs, key=lambda q: (-q.dh, -q.dw, q.name)):
        if r.dw > size or r.dh > size:
            return False
        if x + r.dw > size:
            x, y, shelf = 0, y + shelf, 0
        if y + r.dh > size:
            return False
        r.cx, r.cy = x, y
        x += r.dw
        shelf = max(shelf, r.dh)
    return True


def plan(mesh: UdimMesh, recs: list[_Rec], *, mode: str, size: int, pad: int, target: float,
         plug_px_m: float, plug_cell: int, unit_m: float = 1.0) -> dict:
    if mode not in ("ground", "oks"):
        raise AtlasError(f"mode must be ground or oks, got {mode!r}")
    if size not in ATLAS_SIZES:
        raise AtlasError(f"atlas size must be one of {ATLAS_SIZES}, got {size}")
    if not isinstance(pad, int) or pad < PADDING_MIN_PX:
        raise AtlasError(f"padding must be an integer >= {PADDING_MIN_PX} px, got {pad}")
    for v, what in ((target, "target"), (plug_px_m, "plug texel")):
        if not math.isfinite(v) or not GROUND_MIN <= v <= GROUND_MAX:
            raise AtlasError(f"{what} {v} px/m outside the Ground band {GROUND_MIN}..{GROUND_MAX}")
    plug_scales: dict[str, dict] = {}
    for r in recs:
        if mode == "ground" and not r.dens:
            raise AtlasError(f"material {r.name!r}: no face with measurable UV and geometry area")
        if r.plug:
            r.x1, r.y1, plug_scales[r.name] = _plug_extent(mesh, r, mode, plug_px_m, plug_cell, unit_m)
            r.x0 = r.y0 = 0.0
            _cell(r, pad, 1.0)
    tex = [r for r in recs if not r.plug]

    def bounds(r: _Rec) -> tuple[float, float, float]:
        # directional bounds: the least stretched direction of every face >= 10, the most stretched <= 40, with a
        # 3 % margin (script margin, VPM_to_NPM.ms:194-196; the script measures area density, not direction)
        mean = sorted(math.sqrt(a * b) for a, b in r.dens.values())
        smin = min(a for a, _ in r.dens.values())
        smax = max(b for _, b in r.dens.values())
        lo = GROUND_MIN * 1.03 / smin if smin > 1e-9 else math.inf
        return mean[(len(mean) - 1) // 2], lo, GROUND_MAX * 0.97 / smax

    used = None
    if mode == "ground":
        for r in tex:
            med, lo, hi = bounds(r)
            if lo > hi:
                smin = min(a for a, _ in r.dens.values())
                smax = max(b for _, b in r.dens.values())
                raise AtlasError(f"material {r.name!r}: directional texel spread {smin:.2f}..{smax:.2f} source "
                                 f"px/m (ratio {smax / max(smin, 1e-300):.2f}) cannot fit the band "
                                 f"{GROUND_MIN}..{GROUND_MAX} with one uniform scale")
        t = target
        while t >= GROUND_MIN * 1.05 - 1e-9:
            for r in tex:
                med, lo, hi = bounds(r)
                _cell(r, pad, max(lo, min(hi, t / med)))
            if _shelf(recs, size):
                used = t
                break
            t *= 0.96
    else:
        def fits(s: float) -> bool:
            for r in tex:
                _cell(r, pad, s)
            return _shelf(recs, size)
        if fits(1.0):
            used = 1.0
        elif fits(0.004):
            lo, hi = 0.004, 1.0
            for _ in range(24):
                mid = (lo + hi) / 2
                lo, hi = (mid, hi) if fits(mid) else (lo, mid)
            fits(lo)
            used = lo
    if used is None:
        raise AtlasError(f"materials {[r.name for r in recs]} do not fit one {size} atlas")
    return {"used": used, "plug_scales": plug_scales}


# ---------------------------------------------------------------- raster + UV
def _crop(arr: np.ndarray, r: _Rec) -> Image.Image:
    bw, bh = r.dw / r.k, r.dh / r.k
    ix0, iy0 = math.floor(r.bx0) - 2, math.floor(r.by0) - 2
    ix1, iy1 = math.ceil(r.bx0 + bw) + 2, math.ceil(r.by0 + bh) + 2
    h, w = arr.shape[:2]
    sub = np.take(np.take(arr, np.arange(iy0, iy1) % h, axis=0), np.arange(ix0, ix1) % w, axis=1)
    box = (r.bx0 - ix0, r.by0 - iy0, r.bx0 - ix0 + bw, r.by0 - iy0 + bh)
    return Image.fromarray(np.ascontiguousarray(sub)).resize((r.dw, r.dh), Image.Resampling.LANCZOS, box=box)


def build(mesh: UdimMesh, recs: list[_Rec], planned: dict, size: int) -> dict:
    rgb = np.empty((size, size, 3), np.uint8)
    rgb[:] = BACKGROUND
    alpha = np.full((size, size), 255, np.uint8)
    any_alpha = False
    for r in recs:
        ys, xs = slice(r.cy, r.cy + r.dh), slice(r.cx, r.cx + r.dw)
        if r.plug:
            rgb[ys, xs] = r.color
            alpha[ys, xs] = r.plug_alpha
            any_alpha |= r.plug_alpha < 255
        else:
            rgb[ys, xs] = np.asarray(_crop(r.rgb, r))
            if r.alpha is not None:
                alpha[ys, xs] = np.asarray(_crop(r.alpha, r))
                any_alpha = True
    # remapped UV: textured faces share their UV vertices (one affine per material); plug faces get own vertices
    new_uv: list[tuple[float, float]] = []
    new_fuv: list[tuple[int, ...]] = []
    shared: dict[int, int] = {}
    byname = {r.name: r for r in recs}
    for f, m in enumerate(mesh.face_materials):
        r = byname[m]
        pts = _src_px(mesh, r, f)
        if r.plug:
            o = planned["plug_scales"][m][f]
            ax = r.cx + r.dw / 2 + o[:, 0]
            ay = r.cy + r.dh / 2 + o[:, 1]
            ids = []
            for x, y in zip(ax, ay):
                new_uv.append((x / size, 1 - y / size))
                ids.append(len(new_uv) - 1)
            new_fuv.append(tuple(ids))
            continue
        ids = []
        for t, (px, py) in zip(mesh.face_uvs[f], pts):
            if t not in shared:
                x = r.cx + (px - r.bx0) * r.k
                y = r.cy + (py - r.by0) * r.k
                new_uv.append((x / size, 1 - y / size))
                shared[t] = len(new_uv) - 1
            ids.append(shared[t])
        new_fuv.append(tuple(ids))
    return {"rgb": rgb, "alpha": alpha if any_alpha else None, "uvs": np.array(new_uv, float),
            "face_uvs": tuple(new_fuv)}


# ---------------------------------------------------------------- measurement (works on any output)
def measure(mesh: UdimMesh, uvs: np.ndarray, face_uvs, cells: dict[str, list[int]], size: int, *, mode: str,
            pad_min: int, unit_m: float = 1.0) -> dict:
    """Read-back metrics: UV inside [0,1] and inside its cell, padding to the cell edge, texel px/m per material."""
    per: dict[str, dict] = {}
    for f, m in enumerate(mesh.face_materials):
        if m not in cells:
            raise AtlasError(f"face {f}: material {m!r} has no atlas cell")
        uv = uvs[list(face_uvs[f])]
        px = np.stack([uv[:, 0] * size, (1 - uv[:, 1]) * size], axis=1)
        e = per.setdefault(m, {"faces": 0, "outside_01": 0, "outside_cell": 0, "bbox": [1e18, 1e18, -1e18, -1e18],
                               "dens": []})
        e["faces"] += 1
        e["outside_01"] += int(((uv < -EPS) | (uv > 1 + EPS)).any())
        x, y, w, h = cells[m]
        e["outside_cell"] += int(((px[:, 0] < x - EPS) | (px[:, 0] > x + w + EPS) | (px[:, 1] < y - EPS)
                                  | (px[:, 1] > y + h + EPS)).any())
        b = e["bbox"]
        b[:] = [min(b[0], float(px[:, 0].min())), min(b[1], float(px[:, 1].min())),
                max(b[2], float(px[:, 0].max())), max(b[3], float(px[:, 1].max()))]
        t = _face_texel(mesh.vertices[list(mesh.faces[f])] * unit_m, px)
        if t is not None:
            e["dens"].append(t)
    rows, ok = {}, True
    for m in sorted(per):
        e = per[m]
        x, y, w, h = cells[m]
        b = e["bbox"]
        padding = min(b[0] - x, b[1] - y, x + w - b[2], y + h - b[3])
        d = e["dens"]
        row = {"faces": e["faces"], "cell_px": cells[m], "island_bbox_px": [round(v, 3) for v in b],
               "padding_px": round(padding, 3), "uv_outside_01": e["outside_01"], "uv_outside_cell": e["outside_cell"],
               "texel_min": round(min(a for a, _ in d), 3) if d else None,
               "texel_max": round(max(b for _, b in d), 3) if d else None,
               "faces_without_area": e["faces"] - len(d)}
        # inclusive bounds (reg '>= 8 px', '>= 10 and <= 40'); EPS absorbs float noise only
        row["padding_ok"] = bool(padding >= pad_min - EPS)
        row["texel_in_band"] = bool(d and len(d) == e["faces"] and GROUND_MIN - EPS <= min(a for a, _ in d)
                                    and max(b for _, b in d) <= GROUND_MAX + EPS) if mode == "ground" else None
        row["passed"] = bool(row["padding_ok"] and not row["uv_outside_01"] and not row["uv_outside_cell"]
                             and row["texel_in_band"] is not False)
        ok &= row["passed"]
        rows[m] = row
    names = sorted(per)
    gap = None
    for i, a in enumerate(names):  # island bboxes of different materials never overlap
        for bname in names[i + 1:]:
            p, q = per[a]["bbox"], per[bname]["bbox"]
            dx = max(q[0] - p[2], p[0] - q[2])
            dy = max(q[1] - p[3], p[1] - q[3])
            g = max(dx, dy)
            gap = g if gap is None else min(gap, g)
    if gap is not None and gap < 2 * pad_min - EPS:
        ok = False
    return {"passed": bool(ok and rows), "materials": rows, "min_island_gap_px": None if gap is None else round(gap, 3)}


# ---------------------------------------------------------------- writing
def _fmt(v: float) -> str:
    return repr(float(v))


def _obj_text(mesh: UdimMesh, uvs: np.ndarray, face_uvs, base: str) -> str:
    out = [f"# NPM atlas copy of {mesh.name} (tools/materials/npm_atlas_udim.py)", f"mtllib {base}.mtl",
           f"o {mesh.name}"]
    out += [f"v {_fmt(a)} {_fmt(b)} {_fmt(c)}" for a, b, c in mesh.vertices]
    out += [f"vt {_fmt(a)} {_fmt(b)}" for a, b in uvs]
    if mesh.normals is not None:
        out += [f"vn {_fmt(a)} {_fmt(b)} {_fmt(c)}" for a, b, c in mesh.normals]
    out.append(f"usemtl {base}")
    for f, vi in enumerate(mesh.faces):
        ti = face_uvs[f]
        if mesh.face_normals is not None:
            ni = mesh.face_normals[f]
            out.append("f " + " ".join(f"{v + 1}/{t + 1}/{n + 1}" for v, t, n in zip(vi, ti, ni)))
        else:
            out.append("f " + " ".join(f"{v + 1}/{t + 1}" for v, t in zip(vi, ti)))
    return "\n".join(out) + "\n"


def pack(mesh: UdimMesh, materials: dict[str, MaterialSource], *, mode: str = "ground", size: int = 2048,
         pad: int = PADDING_MIN_PX, target: float = TARGET_PX_M, plug_px_m: float = PLUG_PX_M,
         plug_cell: int = PLUG_CELL_PX, unit_m: float = 1.0) -> dict:
    """Pure in-memory pack: returns atlas arrays, new UV and the measured report. Never touches files."""
    recs = analyze(mesh, materials, unit_m)
    planned = plan(mesh, recs, mode=mode, size=size, pad=pad, target=target, plug_px_m=plug_px_m,
                   plug_cell=plug_cell, unit_m=unit_m)
    built = build(mesh, recs, planned, size)
    cells = {r.name: [r.cx, r.cy, r.dw, r.dh] for r in recs}
    meas = measure(mesh, built["uvs"], built["face_uvs"], cells, size, mode=mode, pad_min=pad, unit_m=unit_m)
    for r in recs:
        row = meas["materials"][r.name]
        row.update({"kind": "plug" if r.plug else "texture", "udim": r.tile, "sources": r.sources,
                    "source_size_px": [r.W, r.H] if not (r.plug and not r.sources) else None,
                    "scale_k": None if r.plug else round(r.k, 6),
                    "source_texel_min": round(min(a for a, _ in r.dens.values()), 3) if r.dens else None,
                    "source_texel_max": round(max(b for _, b in r.dens.values()), 3) if r.dens else None,
                    "dissolve": materials[r.name].dissolve,
                    "ignored_mtl": [{"directive": a, "value": v, "reason": why}
                                    for a, v, why in materials[r.name].ignored],
                    "opacity": "map" if r.alpha is not None else ("flat" if r.plug and r.plug_alpha < 255 else "none")})
    report = {"tool": "tools/materials/npm_atlas_udim.py", "mode": mode, "atlas_size": size, "padding_px": pad,
              "target_px_m": target, "used": round(planned["used"], 6), "plug_px_m": plug_px_m,
              "opacity_map": built["alpha"] is not None, "faces": len(mesh.faces),
              "materials_in": len({*mesh.face_materials}),
              "texel_rule": "directional: min/max singular value of the metre->pixel map per fan triangle", **meas}
    return {**built, "report": report, "cells": cells}


def write_outputs(mesh: UdimMesh, result: dict, out_dir: Path, base: str, inputs: list[Path]) -> dict[str, Path]:
    out_dir = Path(out_dir)
    paths = {"diffuse": out_dir / f"{base}_d.png", "obj": out_dir / f"{base}.obj", "mtl": out_dir / f"{base}.mtl",
             "report": out_dir / f"{base}_report.json"}
    if result["alpha"] is not None:
        paths["opacity"] = out_dir / f"{base}_o.png"
    for p in paths.values():
        for i in inputs:
            if _same_path(p, i) or _same_path(Path(str(p) + ".partial"), i):
                raise AtlasError(f"output {p} resolves to input {i}")
        if p.exists() or Path(str(p) + ".partial").exists():
            raise AtlasError(f"output {p} already exists; use a new versioned folder")
    out_dir.mkdir(parents=True, exist_ok=True)
    mtl = [f"newmtl {base}", "Kd 1 1 1", f"map_Kd {paths['diffuse'].name}"]
    if "opacity" in paths:
        mtl.append(f"map_d {paths['opacity'].name}")
    blobs = {
        "obj": _obj_text(mesh, result["uvs"], result["face_uvs"], base).encode("utf-8"),
        "mtl": ("\n".join(mtl) + "\n").encode("utf-8"),
        "report": json.dumps({**result["report"], "outputs": {k: v.name for k, v in paths.items()}},
                             indent=2, ensure_ascii=False).encode("utf-8"),
    }
    tmp = {k: Path(str(p) + ".partial") for k, p in paths.items()}
    try:
        Image.fromarray(result["rgb"], "RGB").save(tmp["diffuse"], format="PNG")
        if "opacity" in paths:
            Image.fromarray(result["alpha"], "L").save(tmp["opacity"], format="PNG")
        for k, data in blobs.items():
            tmp[k].write_bytes(data)
        for k, p in paths.items():
            os.replace(tmp[k], p)
    finally:
        for t in tmp.values():
            if t.exists():
                t.unlink()
    return paths


def readback(paths: dict[str, Path], source: UdimMesh, cells: dict[str, list[int]], *, mode: str, pad_min: int,
             unit_m: float = 1.0) -> dict:
    """Measure the WRITTEN files: OBJ geometry equals the source, PNGs are RGB / L of the atlas size, UV metrics."""
    back, _ = read_obj(paths["obj"])
    if len(back.faces) != len(source.faces) or back.faces != source.faces \
            or not np.array_equal(back.vertices, source.vertices):
        raise AtlasError(f"{paths['obj']}: geometry differs from the source mesh")
    with Image.open(paths["diffuse"]) as im:
        dmode, dsize = im.mode, im.size
    if dmode != "RGB":
        raise AtlasError(f"{paths['diffuse']}: mode {dmode}, expected RGB without alpha")
    size = dsize[0]
    if dsize != (size, size) or size not in ATLAS_SIZES:
        raise AtlasError(f"{paths['diffuse']}: size {dsize}")
    if "opacity" in paths:
        with Image.open(paths["opacity"]) as im:
            if im.mode != "L" or im.size != dsize:
                raise AtlasError(f"{paths['opacity']}: mode {im.mode} size {im.size}, expected L {dsize}")
    probe = UdimMesh(back.vertices, back.uvs, back.faces, back.face_uvs, source.face_materials, name=back.name)
    return measure(probe, back.uvs, back.face_uvs, cells, size, mode=mode, pad_min=pad_min, unit_m=unit_m)


def render_uv_overlay(atlas_png: Path, obj: Path, out_png: Path, cells: dict[str, list[int]] | None = None) -> None:
    """Evidence picture: remapped UV edges (read back from the written OBJ) over the written atlas."""
    from PIL import ImageDraw

    mesh, _ = read_obj(obj)
    with Image.open(atlas_png) as im:
        img = im.convert("RGB")
    size = img.width
    draw = ImageDraw.Draw(img)
    for x, y, w, h in (cells or {}).values():
        draw.rectangle([x, y, x + w - 1, y + h - 1], outline=(255, 0, 255))
    for ti in mesh.face_uvs:
        pts = [(mesh.uvs[t][0] * size, (1 - mesh.uvs[t][1]) * size) for t in ti]
        draw.line(pts + [pts[0]], fill=(255, 255, 0))
    img.save(out_png)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("obj", type=Path, help="source OBJ (with mtllib); FBX is refused")
    ap.add_argument("--out-dir", type=Path, required=True, help="new versioned folder for the outputs")
    ap.add_argument("--base", help="output base name (default T_<obj stem>_NPM)")
    ap.add_argument("--mode", choices=("ground", "oks"), default="ground")
    ap.add_argument("--size", type=int, default=2048)
    ap.add_argument("--padding", type=int, default=PADDING_MIN_PX)
    ap.add_argument("--target", type=float, default=TARGET_PX_M)
    ap.add_argument("--plug-texel", type=float, default=PLUG_PX_M)
    ap.add_argument("--unit-m", type=float, default=1.0, help="metres per mesh unit")
    ap.add_argument("--overlay", type=Path, help="optional UV-overlay evidence PNG")
    a = ap.parse_args(argv)
    try:
        mesh, mats = read_obj(a.obj)
        base = a.base or f"T_{a.obj.stem}_NPM"
        res = pack(mesh, mats, mode=a.mode, size=a.size, pad=a.padding, target=a.target, plug_px_m=a.plug_texel,
                   unit_m=a.unit_m)
        inputs = [a.obj] + [a.obj.parent / ln.split(None, 1)[1].strip()
                            for ln in a.obj.read_text(encoding="utf-8").splitlines() if ln.startswith("mtllib ")]
        inputs += [Path(s) for r in res["report"]["materials"].values() for s in r["sources"]]
        if a.overlay is not None:
            out_names = [f"{base}{sfx}" for sfx in ("_d.png", "_o.png", ".obj", ".mtl", "_report.json")]
            for i in inputs + [a.out_dir / n for n in out_names] + [a.out_dir / (n + ".partial") for n in out_names]:
                if _same_path(a.overlay, i):
                    raise AtlasError(f"overlay {a.overlay} resolves to input or output {i}")
            if a.overlay.exists():
                raise AtlasError(f"overlay {a.overlay} already exists")
        if not res["report"]["passed"]:
            print(json.dumps(res["report"], indent=2, ensure_ascii=False))
            print("error: measured atlas fails (see report); nothing written", file=sys.stderr)
            return 1
        paths = write_outputs(mesh, res, a.out_dir, base, inputs)
        meas = readback(paths, mesh, res["cells"], mode=a.mode, pad_min=a.padding, unit_m=a.unit_m)
        if a.overlay is not None:
            render_uv_overlay(paths["diffuse"], paths["obj"], a.overlay, res["cells"])
    except (AtlasError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if not meas["passed"]:
        print(json.dumps(meas, indent=2, ensure_ascii=False))
        print("error: read-back of the written files fails", file=sys.stderr)
        return 1
    r = res["report"]
    print(f"ok: {paths['diffuse']} {r['atlas_size']}px used={r['used']} materials={len(r['materials'])} "
          f"min_gap={r['min_island_gap_px']}px opacity={r['opacity_map']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
