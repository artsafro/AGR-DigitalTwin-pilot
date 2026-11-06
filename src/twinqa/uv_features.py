"""Features per UV face: count transparent blobs of a texture inside every face's UV polygon.

new-case: generic readback check "N alpha holes per face" from a UV dump CSV and an RGBA texture,
generalised from the job script jobs/skug26-k5-ac/scripts/uvverify.py (retro T3, Advances #149).

Input rows are ``name, face_index, material_id, u0, v0, u1, v1, ...`` (the uvdump CSV), either as
CSV text lines or as already split sequences. A feature is a 4-connected blob of pixels with
alpha < ``alpha_threshold``; it belongs to a face when its centroid (pixel centres) lies inside the
face's UV polygon mapped into the face's own UDIM tile. Only problems are findings, all ``fail``:
empty input, unreadable texture or no alpha channel, invalid/duplicated rows, faces outside the
expected tile, a count different from ``expected``, a face with no expected key and an expected key
that matched no face. Zero findings means every face was checked and matched.

Texel density is not computed here: a UV dump has no 3D positions; use
``dt_ai.ops.texel_density_readout`` for that.
"""
import math
from dataclasses import dataclass

import numpy as np
import shapely
from PIL import Image

from twinqa.report import Finding
from twinqa.uv import tile_origin, udim_of

EPS = 1e-6
UDIM_PAGES = [31]  # reg p.31 §2.1.2-2.1.3: geometry in one tile, tiles from 1001


@dataclass(frozen=True)
class UVFace:
    name: str
    face: int
    material: str
    uv: list  # [(u, v), ...]


def _fail(name, observed, expected, data=None, pages=None):
    return Finding(name, "fail", observed, expected, list(pages or []), evidence="uv_features",
                   data=dict(data or {}))


def parse_row(row) -> UVFace:
    """One CSV row (text or sequence) -> UVFace. Raises ValueError naming the defect."""
    parts = [p.strip() for p in (row.split(",") if isinstance(row, str) else row)]
    if len(parts) < 9 or (len(parts) - 3) % 2:
        raise ValueError(f"need name,face,material and >= 3 (u,v) pairs, got {len(parts)} fields")
    coords = [float(x) for x in parts[3:]]
    if not all(math.isfinite(c) for c in coords):
        raise ValueError("non-finite UV coordinate")
    return UVFace(parts[0], int(parts[1]), parts[2], list(zip(coords[0::2], coords[1::2])))


def read_uv_csv(path) -> list[str]:
    """Non-empty lines of a uvdump CSV, unparsed (parsing errors become findings)."""
    with open(path, encoding="utf-8") as fh:
        return [line for line in fh if line.strip()]


def label_features(alpha: np.ndarray, threshold: int):
    """Centroids (x, y in pixel units, pixel centres at +0.5) of 4-connected blobs with alpha < threshold.

    Run-length union-find: no scipy, linear in the number of runs.
    """
    mask = np.asarray(alpha) < threshold
    parent: list[int] = []

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    runs = []  # (row, start, end, id)
    prev: list[tuple[int, int, int]] = []
    for r in range(mask.shape[0]):
        d = np.diff(np.concatenate(([0], mask[r].astype(np.int8), [0])))
        starts, ends = np.flatnonzero(d == 1), np.flatnonzero(d == -1)
        cur = []
        j = 0
        for s, e in zip(starts.tolist(), ends.tolist()):
            rid = len(parent)
            parent.append(rid)
            while j < len(prev) and prev[j][1] <= s:
                j += 1
            k = j
            while k < len(prev) and prev[k][0] < e:
                a, b = find(rid), find(prev[k][2])
                if a != b:
                    parent[max(a, b)] = min(a, b)
                k += 1
            cur.append((s, e, rid))
            runs.append((r, s, e, rid))
        prev = cur
    acc: dict[int, list[float]] = {}
    for r, s, e, rid in runs:
        n = e - s
        a = acc.setdefault(find(rid), [0.0, 0.0, 0.0])
        a[0] += n
        a[1] += (s + e) / 2 * n  # sum of (col + 0.5)
        a[2] += (r + 0.5) * n
    return np.array([(sx / n, sy / n) for n, sx, sy in acc.values()]).reshape(-1, 2)


def _load_alpha(texture_path):
    with Image.open(texture_path) as img:
        bands = img.getbands()
        if "A" not in bands:
            raise ValueError(f"texture has no alpha channel (bands {''.join(bands)})")
        return np.asarray(img.getchannel("A"))


def count_features_per_face(uv_rows, texture_path, *, alpha_threshold=128, expected=None, tile=None):
    """Findings for a UV dump against a texture; [] means all faces checked and matched.

    expected: {face name or material id: features per face}; the name wins over the material.
    tile: UDIM every face must lie in (centroid tile and all vertices), or None to skip.
    """
    if type(alpha_threshold) is not int or not 1 <= alpha_threshold <= 256:
        raise ValueError("alpha_threshold must be an int in 1..256")
    if tile is not None:
        tile_origin(tile)  # raises for a tile outside 1001..1100
    expected = {str(k): v for k, v in (expected or {}).items()}
    for k, v in expected.items():
        if type(v) is not int or v < 0:
            raise ValueError(f"expected count for {k!r} must be a non-negative int, got {v!r}")
    findings = []
    rows = list(uv_rows)
    if not rows:
        return [_fail("uv_features.input", "0 UV rows", ">= 1 UV row")]
    try:
        alpha = _load_alpha(texture_path)
    except (OSError, ValueError) as exc:
        return [_fail("uv_features.texture", f"{texture_path}: {exc}", "readable texture with alpha",
                      {"texture": str(texture_path)})]
    h, w = alpha.shape
    centroids = label_features(alpha, alpha_threshold)
    faces, seen = [], set()
    for i, row in enumerate(rows):
        try:
            f = parse_row(row)
        except ValueError as exc:
            findings.append(_fail("uv_features.invalid_row", f"row {i}: {exc}", "name,face,material,u,v,...",
                                  {"row": i}))
            continue
        if (f.name, f.face) in seen:
            findings.append(_fail("uv_features.duplicate_face", f"row {i}: {f.name} face {f.face} repeated",
                                  "each (name, face) once", {"row": i, "name": f.name, "face": f.face}))
            continue
        seen.add((f.name, f.face))
        faces.append(f)
    used_keys = set()
    for f in faces:
        ident = {"name": f.name, "face": f.face, "material": f.material}
        own = udim_of(f.uv)
        if own is None:
            findings.append(_fail("uv_features.wrong_tile", f"{f.name} face {f.face}: centroid outside UDIM grid",
                                  f"tile {tile}" if tile else "tile 1001..1100", ident, UDIM_PAGES))
            continue
        if tile is not None and own != tile:
            findings.append(_fail("uv_features.wrong_tile", f"{f.name} face {f.face}: tile {own}", f"tile {tile}",
                                  {**ident, "tile": own}, UDIM_PAGES))
        tu, tv = tile_origin(own)
        if not all(tu - EPS <= u <= tu + 1 + EPS and tv - EPS <= v <= tv + 1 + EPS for u, v in f.uv):
            findings.append(_fail("uv_features.cross_tile", f"{f.name} face {f.face}: vertex leaves tile {own}",
                                  f"all vertices in tile {own}", {**ident, "tile": own}, UDIM_PAGES))
        poly = shapely.Polygon([((u - tu) * w, (1 - (v - tv)) * h) for u, v in f.uv])
        count = int(shapely.contains_xy(poly, centroids[:, 0], centroids[:, 1]).sum()) if len(centroids) else 0
        if not expected:
            continue
        key = f.name if f.name in expected else f.material if f.material in expected else None
        if key is None:
            findings.append(_fail("uv_features.unmapped", f"{f.name} face {f.face} (material {f.material}): "
                                  f"no expected count, got {count}", "name or material in expected",
                                  {**ident, "count": count}))
            continue
        used_keys.add(key)
        if count != expected[key]:
            findings.append(_fail("uv_features.mismatch", f"{f.name} face {f.face}: {count} features",
                                  f"{expected[key]} ({key})", {**ident, "key": key, "count": count}))
    for key in sorted(set(expected) - used_keys):
        findings.append(_fail("uv_features.expected_unused", f"expected key {key!r} matched no face",
                              "every expected key matches a face", {"key": key}))
    return findings
