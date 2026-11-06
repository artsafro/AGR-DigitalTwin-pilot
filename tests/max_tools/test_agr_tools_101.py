"""AGR Tools 1.0.1 (#1024): regressions of the KPP1 end-to-end run of 1.0.0 (job 20261106-075555-c179f5f0, Max 2024).

Each blocker of the release run is a test that was RED on the 1.0.0 tree and is GREEN after its fix (one commit per
fix). The modules belong to several branches (L, M, N, P, Q, S, 0.8 checks); a patch release touches them together.
"""
import importlib.util
import struct
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / 'adapters/max/agr_tools'
LIB = ROOT / 'library/materials/materials.json'


def _load(filename, name):
    mod = sys.modules.get(name)
    if mod is None:
        spec = importlib.util.spec_from_file_location(name, PKG / filename)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
    return mod


ml = _load('matlib_core.py', 'agr_tools_matlib_core')
tc = _load('tex_core.py', 'agr_tools_tex_core')
vc = _load('vpmmaps_core.py', 'agr_tools_vpmmaps_core')


# ---- stage 6: one scale of roughness / metallic / emissive ------------------------------------------------------
# Contract (1.0.1): the library record is the single source and keeps 8-bit levels 0..255 (materials_v001.json
# "byte_fields", dt_ai MaterialRegistry `Byte`, tiles_core ERM). Consumers that write an 8-bit ERM texel take the
# level as it is; only the Physical material (0..1 float) normalises, at its own boundary (matlib_core.sub_spec).
def test_vpm_maps_from_the_real_library_kpp1_ids(tmp_path):
    """RED on 1.0.0: «roughness must be a number in 0..1: 150» (vpm.build step 6 with library_path, KPP1 e2e)."""
    lib = ml.load_library(str(LIB))
    ids = [1, 3, 9, 12, 16, 29, 35]
    table = {'SM_Kpp_1_Main': {lid: 1001 + i for i, lid in enumerate(ids)}}
    res = vc.build_maps(table, lib, str(tmp_path))
    erm = [m for m in res['maps'] if m['kind'] == 'ERM']
    assert len(erm) == len(ids)
    for m in erm:
        lid = ids[m['udim'] - 1001]
        rec = lib['by_id'][lid]
        px = tc.decode_png(Path(m['path']).read_bytes())[0].px
        assert tuple(px[0:3]) == (rec['emissive'], rec['roughness'], rec['metallic'])   # the level itself, no rescale


def test_erm_level_contract_bytes_only():
    rec = {'emissive': 0, 'roughness': 150, 'metallic': 255}
    assert vc.erm_colour(rec) == (0, 150, 255)
    for bad in (0.5, 256, -1, True, '150'):
        with pytest.raises(ValueError):
            vc.erm_colour(dict(rec, roughness=bad))


def test_physical_boundary_still_normalises():
    lib = ml.load_library(str(LIB))
    rec = lib['by_id'][12]
    sub = ml.sub_spec(rec)
    assert sub['roughness'] == rec['roughness'] / 255.0 and 0 <= sub['metallic'] <= 1


# ---- stage 6: udim.plugs on the output of vpm.build ---------------------------------------------------------------
pc = _load('udimplug_core.py', 'agr_tools_udimplug_core')
ec = _load('edit_core.py', 'agr_tools_edit_core')
KPP1_VPM_TABLE = {'1': 1001, '3': 1002, '9': 1003, '12': 1004, '16': 1005, '29': 1006, '35': 1007}   # vpm_table.json
WALL = [(0, 0, 0), (2, 0, 0), (2, 0, 3)]


def test_plug_tile_from_the_mesh_table_core():
    """vpm.build keeps library ids on the copy and puts id 12 into 1004: the plug of id 12 goes to 1004, not 1012."""
    o = pc.plug_options({'udim_table': KPP1_VPM_TABLE})
    plan = pc.plug_plan([{'face': 1, 'matid': 12, 'verts': WALL}, {'face': 2, 'matid': 29, 'verts': WALL},
                         {'face': 3, 'matid': 7, 'verts': WALL}], o)
    assert [(f['face'], f['udim']) for f in plan['faces']] == [(1, 1004), (2, 1006)]
    assert plan['skipped'][0]['code'] == 'plug_matid' and plan['skipped'][0]['face'] == 3   # id not in the table
    assert pc.plug_check([plan['faces'][0]['uv']], 1004)
    with pytest.raises(ValueError):
        pc.plug_options({'udim_table': {'12': 1004, '29': 1004}})     # one tile for two ids
    with pytest.raises(ValueError):
        pc.plug_options({'udim_table': {'12': 2004}})


class _P3:
    def __init__(self, x, y, z):
        self.x, self.y, self.z = x, y, z


class _MeshNode:
    """An Editable_Mesh copy of vpm.build: triangles, library ids, channel 1, user prop agr_udim_table."""
    def __init__(self, name, handle, props=None):
        self.name, self.handle, self.props = name, handle, dict(props or {})
        self.verts = [_P3(0, 0, 0), _P3(2, 0, 0), _P3(2, 0, 3), _P3(0, 0, 3)]
        self.faces = [(1, 2, 3), (1, 3, 4)]
        self.mat = [12, 29]
        self.map_verts = [_P3(3.1, 0.1, 0), _P3(3.2, 0.1, 0), _P3(3.2, 0.2, 0), _P3(3.1, 0.2, 0)]
        self.map_faces = [(1, 2, 3), (1, 3, 4)]
        self.kind = 'mesh'


class _Meshop:
    def __init__(self, rt):
        self.rt = rt

    def getMapSupport(self, n, ch):
        return True

    def setMapSupport(self, n, ch, on):
        pass

    def getNumMapVerts(self, n, ch):
        return len(n.map_verts)

    def setNumMapVerts(self, n, ch, count, keep=False):
        n.map_verts = (n.map_verts + [_P3(0, 0, 0)] * count)[:count]

    def setMapVert(self, n, ch, i, p):
        import struct as st
        n.map_verts[i - 1] = _P3(*[st.unpack('f', st.pack('f', c))[0] for c in (p.x, p.y, p.z)])

    def setMapFace(self, n, ch, f, p):
        n.map_faces[f - 1] = (int(p.x), int(p.y), int(p.z))

    def getMapFace(self, n, ch, f):
        return _P3(*n.map_faces[f - 1])

    def getMapVert(self, n, ch, i):
        return n.map_verts[i - 1]


class _RT:
    Editable_Poly, Editable_Mesh = 'Editable_Poly', 'Editable_Mesh'

    def __init__(self):
        self.meshop = _Meshop(self)
        self.selection = []

    def isKindOf(self, n, cls):
        return (cls == 'Editable_Mesh' and n.kind == 'mesh') or (cls == 'Editable_Poly' and n.kind == 'poly')

    def getUserProp(self, n, key):
        return n.props.get(key)

    def getNumFaces(self, n):
        return len(n.faces)

    def getFaceSelection(self, n):
        return [0] * len(n.faces)

    def getFace(self, n, f):
        return _P3(*n.faces[f - 1])

    def getVert(self, n, i):
        return n.verts[i - 1]

    def getFaceMatID(self, n, f):
        return n.mat[f - 1]

    def Point3(self, x, y, z):
        return _P3(x, y, z)

    def update(self, n):
        pass

    def getHandleByAnim(self, n):
        return n.handle

    def isValidNode(self, n):
        return True

    def delete(self, nodes):
        pass


def _plugs_ctx(rt, options=None):
    import contextlib
    import copy
    import types
    um = _load('udimplug_max.py', 'agr_tools_udimplug_max_101')

    def export_copies(nodes, suffix='_AGR_export_', layer=None):
        out = []
        for n in nodes:
            c = copy.deepcopy(n)
            c.name, c.handle = n.name + suffix + '01', n.handle + 1000
            out.append((n, c))
        rt.copies = [c for _, c in out]
        return out

    emax = types.SimpleNamespace(export_copies=export_copies, session=lambda label: contextlib.nullcontext(),
                                 snapshot=lambda nodes: [{'h': n.handle, 'mv': [(p.x, p.y) for p in n.map_verts]}
                                                         for n in nodes])
    ctx = types.SimpleNamespace(core=pc, edit=ec, emax=emax, options=options,
                                host=types.SimpleNamespace(m_per_unit=lambda: 1.0))
    return um, ctx


def test_plugs_on_the_vpm_copy_editable_mesh(monkeypatch):
    """RED on 1.0.0: «no object can get plugs: ...: not an Editable_Poly» on the vpm.build copy (KPP1 e2e)."""
    import json
    import types
    rt = _RT()
    monkeypatch.setitem(sys.modules, 'pymxs', types.SimpleNamespace(runtime=rt))
    node = _MeshNode('SM_Kpp_1_Main', 7, {'agr_udim_table': json.dumps(KPP1_VPM_TABLE)})
    um, ctx = _plugs_ctx(rt)
    pre = um.udim_plugs(ctx, 'preview', [node], None)
    assert pre['status'] == 'pass', pre
    assert pre['plan']['done'][0]['tiles'] == {'1004': 1, '1006': 1}
    assert pre['plan']['done'][0]['udim_source'] == 'agr_udim_table'
    app = um.udim_plugs(ctx, 'apply', [node], pre)
    copy_ = rt.copies[0]
    assert app['plan']['copies'] == [copy_.name]
    tri = [copy_.map_verts[i - 1] for i in copy_.map_faces[0]]            # face 1 (id 12) -> tile 1004 centre
    assert all(3.0 < p.x < 4.0 and 0.0 < p.y < 1.0 for p in tri)
    assert [(p.x, p.y) for p in node.map_verts][:2] == [(3.1, 0.1), (3.2, 0.1)]   # the source is not touched
