"""new-case: polygon station objects of #1024 branch L (mat.table, mat.tiles, tex.plug_colour).

build_scene.py calls make(obj, rt) -> node for every L.json object with `"builder": "L_build"`; obj['extra'] (metres,
the station scenes frag_l_* are in metres):
* {"kind": "ids_box", "ids": [...], "agr_role": role, "size": [w, l, h], "at": [x, y, z], "agr_tile": {...}} - an
  Editable_Mesh box whose 12 faces carry the library ids cyclically (mid-poly ids), user prop agr_role (contract K1)
  and optionally agr_tile (JSON overrides of mat.tiles). NOTE: build_scene._props (shared) then REPLACES the user prop
  buffer of every fragment node (native job 20261106-045136-6234cfee: agr_tile/agr_role lost), so the stations use face
  ids and station options only; agr_tile is covered by run_agr_tools_materials_native.py directly;
* {"kind": "plug_plane", "texture": file, "pattern": "solid" | "first_blue_10", "rgb": [r, g, b], "at": [x, y, z]} -
  a Plane with a Standard material whose diffuse bitmap is a synthetic 64x64 PNG written beside the polygon output
  (AGR_POLYGON_OUT/l_textures, else a temp folder): `first_blue_10` puts 10 % blue first in scan order (lab L14).
"""
import importlib.util
import json
import os
import tempfile
from pathlib import Path


def _tex_core():
    root = Path(os.environ.get('AGR_POLYGON_ROOT') or Path(__file__).resolve().parents[2])
    spec = importlib.util.spec_from_file_location('agr_lbuild_tex_core',
                                                  root / 'adapters' / 'max' / 'agr_tools' / 'tex_core.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _texture(name, pattern, rgb):
    out = os.environ.get('AGR_POLYGON_OUT')
    folder = Path(out) / 'l_textures' if out else Path(tempfile.gettempdir()) / 'agr_polygon_l_textures'
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    w = h = 64
    px = bytearray(bytes(rgb) * (w * h))
    if pattern == 'first_blue_10':
        for i in range(int(w * h * 0.10)):
            px[i * 3:i * 3 + 3] = bytes((0, 0, 255))
    elif pattern != 'solid':
        raise RuntimeError('L_build: unknown texture pattern ' + repr(pattern))
    tc = _tex_core()
    data = tc.encode_png(tc.Image(w, h, 3, bytes(px)))
    if path.exists() and path.read_bytes() != data:
        raise RuntimeError('L_build: refusing to overwrite a different ' + str(path))
    path.write_bytes(data)
    return str(path)


def make(obj, rt):
    ex = obj.get('extra') or {}
    kind = ex.get('kind')
    if kind == 'ids_box':
        w, l, h = ex['size']
        node = rt.Box(name=obj['name'], width=w, length=l, height=h, mapcoords=True)
        node.pos = rt.Point3(*ex.get('at', (0.0, 0.0, 0.0)))
        rt.convertToMesh(node)
        ids = [int(i) for i in ex['ids']]
        for f in range(1, int(rt.getNumFaces(node)) + 1):
            rt.setFaceMatID(node, f, ids[(f - 1) % len(ids)])
        rt.update(node)
        rt.setUserProp(node, 'agr_role', ex.get('agr_role', 'body'))
        if ex.get('agr_tile'):
            rt.setUserProp(node, 'agr_tile', json.dumps(ex['agr_tile']))
        return node
    if kind == 'plug_plane':
        node = rt.Plane(name=obj['name'], width=2.0, length=2.0, lengthsegs=1, widthsegs=1, mapcoords=True)
        node.pos = rt.Point3(*ex.get('at', (0.0, 0.0, 0.0)))
        mat = rt.StandardMaterial(name='M_' + obj['name'])
        mat.diffuseMap = rt.BitmapTexture(filename=_texture(ex['texture'], ex.get('pattern', 'solid'), ex['rgb']))
        node.material = mat
        return node
    raise RuntimeError('L_build: unknown kind {!r} for {}'.format(kind, obj['name']))
