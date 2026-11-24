"""#65 pure functions: UDIM fold around the unchanged twinqa.npm_uv.check_meshes, U shift, frozen verdict."""
from __future__ import annotations

import copy
import math
import struct

from twinqa.npm_uv import check_meshes, load_layout

TARGET = "PanelVJ30_RAL5015"


def png_size(data: bytes):
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    return list(struct.unpack(">II", data[16:24]))


def tile_of(corners):
    cu = sum(p[0] for p in corners) / len(corners)
    cv = sum(p[1] for p in corners) / len(corners)
    return 1001 + math.floor(cu) + 10 * math.floor(cv), math.floor(cu), math.floor(cv)


def fold(meshes, atlas, tile_px):
    """Variant F: unchanged check_meshes per UDIM tile. tile_px {tile: [w, h]} of the Diffuse PNGs."""
    size = atlas["atlas"]
    tiles = {}
    for name, region in atlas["finishes"].items():
        tiles.setdefault(int(region["udim"]), {})[name] = region
    missing = sorted(t for t in tiles if tile_px.get(t) != [size, size])
    if missing:
        raise ValueError(f"no {size} px Diffuse PNG for tiles {missing}: {tile_px}")
    per_tile = {t: [] for t in tiles}
    orphan = []
    for mesh in meshes:
        geo = mesh.get("face_geometry") or {}
        polys, uvs = geo.get("polygons"), geo.get("polygon_uv")
        if not isinstance(polys, list) or not isinstance(uvs, list) or len(polys) != len(uvs):
            raise ValueError(f"{mesh.get('name')}: partial polygon_uv")
        buckets = {}
        for index, corners in enumerate(uvs):
            tile, fu, fv = tile_of(corners)
            folded = [[u - fu, v - fv] for u, v in corners]
            if tile not in tiles:
                orphan.append({"mesh": mesh.get("name"), "face": index, "tile": tile, "reason": "no region tile"})
                continue
            buckets.setdefault(tile, ([], []))
            buckets[tile][0].append(polys[index])
            buckets[tile][1].append(folded)
        for tile, (p, u) in buckets.items():
            per_tile[tile].append({"name": mesh.get("name"), "face_geometry": {"polygons": p, "polygon_uv": u}})
    out = {"faces": 0, "bad": list(orphan), "errors": [], "tiles": {}}
    for tile, regions in sorted(tiles.items()):
        layout = load_layout({"atlas": size, "cell": atlas["cell"], "pad": atlas["pad"], "finishes": regions})
        res = check_meshes(per_tile[tile], layout)
        out["faces"] += res["faces"]
        out["bad"] += [dict(b, tile=tile) for b in res["bad"]]
        out["errors"] += res["errors"]
        out["tiles"][tile] = {"faces": res["faces"], "bad": len(res["bad"]), "min_inner_px": res["min_inner_px"]}
    out["faces"] += len(orphan)
    return out


def target_faces(meshes, atlas):
    """[(mesh index, face index)] whose folded centroid lies in the TARGET region."""
    reg = atlas["finishes"][TARGET]
    tile = int(reg["udim"])
    hits = []
    for mi, mesh in enumerate(meshes):
        for fi, corners in enumerate(mesh["face_geometry"]["polygon_uv"]):
            t, fu, fv = tile_of(corners)
            cu = sum(p[0] for p in corners) / len(corners) - fu
            cv = sum(p[1] for p in corners) / len(corners) - fv
            if t == tile and reg["u0"] <= cu <= reg["u0"] + reg["size"] and reg["v0"] <= cv <= reg["v0"] + reg["size"]:
                hits.append((mi, fi))
    return hits


def margin_px(meshes, atlas, hits):
    """Clean distance in px of the TARGET faces' corners to the region's U-max edge (min over corners)."""
    reg, size = atlas["finishes"][TARGET], atlas["atlas"]
    u1 = reg["u0"] + reg["size"]
    return min((u1 - (u - math.floor(u))) * size
               for mi, fi in hits for u, _ in meshes[mi]["face_geometry"]["polygon_uv"][fi])


def shift(meshes, hits, s_px, size):
    out = copy.deepcopy(meshes)
    for mi, fi in hits:
        out[mi]["face_geometry"]["polygon_uv"][fi] = [[u + s_px / size, v]
                                                      for u, v in out[mi]["face_geometry"]["polygon_uv"][fi]]
    return out


def verdict(applicable, b007, b010, sens):
    """sens {s: (bad, expected_bad_bool)}; witness = the m+1 state must fire."""
    return ("confirmed" if applicable and b007 > b010 and all((b > 0) == e for b, e in sens.values())
            else "refuted")
