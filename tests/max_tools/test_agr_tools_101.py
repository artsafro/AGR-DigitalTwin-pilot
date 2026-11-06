"""AGR Tools 1.0.1 (#1024): regressions of the KPP1 end-to-end run of 1.0.0 (job 20261106-075555-c179f5f0, Max 2024).

Each blocker of the release run is a test that was RED on the 1.0.0 tree and is GREEN after its fix (one commit per
fix). The modules belong to several branches (L, M, N, P, Q, S, 0.8 checks); a patch release touches them together.
"""
import importlib.util
import json
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


# ---- stage 8: npm.to_vpm on the NPM of npm.build of the same run ---------------------------------------------------
npc = _load('npm_core.py', 'agr_tools_npm_core')
n2v = _load('npm2vpm_core.py', 'agr_tools_npm2vpm_core')


def _f32(x):
    return struct.unpack('f', struct.pack('f', x))[0]


def _vpm_copy_kpp1_like(rows=40):
    """A vpm.build body copy as KPP1: solid (plug) library ids, each in its dense tile of the table, the UV vertices
    of the grid cut lying EXACTLY on the tile lines (u = 3.0 / 4.0, v = 0.0 / 1.0) - as vpm.build writes them."""
    table = {12: 1004, 29: 1006, 3: 1002}
    verts, tris, mats, uvs, uv_tris = [], [], [], [], []
    for k, (lid, udim) in enumerate(sorted(table.items())):
        u0, v0 = (udim - 1001) % 10, (udim - 1001) // 10
        for row in range(rows):         # strips in the tile (one island each), the outer ones touch the tile lines
            y0, y1 = row / float(rows), (row + 1) / float(rows)
            base = len(verts)
            verts += [[k * 4.0, 0.0, y0 * 3.6], [k * 4.0 + 3.6, 0.0, y0 * 3.6], [k * 4.0 + 3.6, 0.0, y1 * 3.6],
                      [k * 4.0, 0.0, y1 * 3.6]]
            ub = len(uvs)
            uvs += [[u0 + 0.0, v0 + y0], [u0 + 1.0, v0 + y0], [u0 + 1.0, v0 + y1], [u0 + 0.0, v0 + y1]]
            for t in ((0, 1, 2), (0, 2, 3)):
                tris.append([base + i for i in t])
                uv_tris.append([ub + i for i in t])
                mats.append(lid)
    mesh = {'verts': verts, 'tris': tris, 'mat_ids': mats, 'uvs': uvs, 'uv_tris': uv_tris, 'part': 'body',
            'materials': {str(lid): {'name': 'L{:03d}'.format(lid), 'color': [100, 110, 120]} for lid in table}}
    return mesh, {str(k): v for k, v in table.items()}


def test_npm_round_trip_after_float32_storage():
    """RED on 1.0.0: npm.to_vpm refused `udim_mismatch` on the NPM that npm.build wrote in the same KPP1 run. Max keeps
    channel 1 in float32: an atlas UV of a plug cell (8 px of 512, scale 1/64) loses ~3e-8, (uv - shift) / scale
    makes it ~2e-6 VPM-UV units - over the 1e-6 tile tolerance for vertices that sit on the tile lines."""
    mesh, table = _vpm_copy_kpp1_like()
    p = npc.plan([mesh], {'name': 'SM_Kpp_1_001_Main', 'udim_table': table, 'max_size': 512}, {})
    assert not p['findings'] and {r['kind'] for r in p['table']} == {'plug'} and p['atlas']['size'] == 512   # as KPP1
    stored = [[_f32(u), _f32(v)] for u, v in p['uvs']]                # NPM copy channel 1 as Max stores it
    npm = {'verts': mesh['verts'], 'local': mesh['verts'], 'tris': mesh['tris'], 'mat_ids': mesh['mat_ids'],
           'uvs': stored, 'uv_tris': p['uv_tris']}
    res = n2v.plan_table(npm, n2v.table_rows({'table': p['table']}))
    assert not [f for f in res['findings'] if f[0] == 'udim_mismatch'], res['findings']
    back = res['parts']['body']
    worst = 0.0
    for k, f in enumerate(back['faces']):                              # restored VPM UV vs the vpm.build UV
        for i, j in zip(back['uv_tris'][k], mesh['uv_tris'][f]):
            worst = max(worst, abs(back['uvs'][i][0] - mesh['uvs'][j][0]), abs(back['uvs'][i][1] - mesh['uvs'][j][1]))
    assert worst < 1e-5            # 1e-5 of a 4096 px tile = 0.04 px


def test_npm_round_trip_still_refuses_a_real_tile_change():
    """The tolerance follows the float32 storage of the atlas UV; a face moved into another tile is still refused."""
    mesh, table = _vpm_copy_kpp1_like()
    p = npc.plan([mesh], {'name': 'SM_Kpp_1_001_Main', 'udim_table': dict(table, **{'12': 1005}), 'max_size': 512},
                 {})
    stored = [[_f32(u), _f32(v)] for u, v in p['uvs']]
    npm = {'verts': mesh['verts'], 'local': mesh['verts'], 'tris': mesh['tris'], 'mat_ids': mesh['mat_ids'],
           'uvs': stored, 'uv_tris': p['uv_tris']}
    res = n2v.plan_table(npm, n2v.table_rows({'table': p['table']}))
    codes = {f[0] for f in res['findings']}
    assert 'udim_mismatch' in codes


# ---- density 1000 px/m (owner answer 06.11 morning, materials audit Q1): UDIM tile 3.6 m = 3600 px ----------------
def test_density_default_1000_px_per_m_everywhere():
    vpm = _load('vpm_core.py', 'agr_tools_vpm_core')
    lay = _load('uvlayout_core.py', 'agr_tools_uvlayout_core')
    u10 = _load('udim10_core.py', 'agr_tools_udim10_core')
    tiles = _load('tiles_core.py', 'agr_tools_tiles_core')
    o = vpm.options({})
    assert o['texel_px_per_m'] == 1000.0 and o['tile_px'] == 3600 and lay.TILE_PX == 3600
    assert vpm.px_per_step(o) == pytest.approx(3600.0) and vpm.texel_of(o, 12) == pytest.approx(1000.0)
    assert u10.rescale_options({})['target_px_per_m'] == pytest.approx(1000.0)
    assert tiles.DEFAULTS['px_per_m'] == 1000.0
    # every module of the facade set lies whole in the 3.6 m period at 1000 px/m: 600 mm = 600 px, 1.2 m = 1200 px
    for module_m in (0.6, 1.2, 0.3, 0.9, 3.6):
        assert (module_m * 1000.0) == int(module_m * 1000.0 + 0.5) and (3.6 / module_m) == pytest.approx(round(3.6 / module_m))


# ---- stage 9: ucx.rename reads the pieces of the UCX builder --------------------------------------------------------
def test_ucx_rename_reads_builder_pieces():
    """RED on 1.0.0: «UCX name without _Main/_Ground: UCX_SM_Kpp_1_Main_AGR_ucx__01» - 98 of 98 KPP1 pieces skipped."""
    nc = _load('names_core.py', 'agr_tools_names_core')
    uc = _load('ucx_core.py', 'agr_tools_ucx_core')
    _export, pieces = uc.ucx_export_names('SM_Kpp_1_Main', 12)
    assert pieces[0] == 'UCX_SM_Kpp_1_Main_AGR_ucx__01'
    plan = nc.ucx_plan([{'key': i, 'name': n, 'geometry': True} for i, n in enumerate(pieces)])
    assert not plan['skipped'] and not plan['errors']
    assert [r['new'] for r in plan['rename']] == ['UCX_SM_Kpp_1_Main_{:03d}'.format(i) for i in range(1, 13)]
    assert nc.parse_ucx('UCX_SM_Kpp_1_Main_AGR_ucx__07') == {'address': 'Kpp_1', 'kind': 'Main', 'number': 7,
                                                             'canonical': False}
    assert isinstance(nc.parse_ucx('UCX_SM_Kpp_1_Roof_AGR_ucx__01'), str)    # still needs _Main / _Ground


# ---- stage 9: the working keys of the 1.0 buttons are pipeline props, not delivered lines ------------------------
KPP1_MAIN_UDP = ('agr_role = body\r\nagr_udim_table = {"12": 1004}\r\nagr_library = v001\r\n'
                 'AGR_EXPORT_PATH = C:/d/SM_Kpp_1.fbx\r\nMapChannel:1 = UV\r\n')


def test_agr_working_keys_held_off_the_cleanup_gate_and_the_delivery():
    """RED on 1.0.0: export.checked gate cleanup failed on the VPM Main (clear_user_defined_lines agr_role, ...): the
    KPP1 run removed the lines by hand before pack.deliver B."""
    sys.path.insert(0, str(ROOT / 'src'))
    try:
        from twinqa.export_hygiene import repair_plan
    finally:
        sys.path.pop(0)
    ex = _load('export_core.py', 'agr_tools_export_core_101')
    rtm = _load('runtime.py', 'agr_runtime_101')
    dump = {'name': 'SM_Kpp_1_Main', 'custom_attributes': {'base': [], 'node': [], 'modifiers': [], 'materials': []},
            'user_props': rtm._delivery_props(KPP1_MAIN_UDP), 'map_channels': [1]}
    assert dump['user_props'] == 'MapChannel:1 = UV\r\n'               # what the gate and the FBX copy see
    (item,) = repair_plan([dump])['objects']
    assert item['actions'] == [] and item['unrepairable'] == []
    # export.cleanup on a copy keeps them as pipeline data, never as a line to clear
    raw = dict(dump, user_props=KPP1_MAIN_UDP)
    (kept,) = ex.cleanup_plan(repair_plan([raw]), [{'vertex_channels': [], 'keys': 0}])['objects']
    assert kept['actions'] == [] and len(kept['kept_udp']) == 4
    assert ex.pipeline_key('agr_role') and ex.pipeline_key('AGR_EXPORT_PATH') and not ex.pipeline_key('foo')
    assert not ex.pipeline_key('AGR_role')                          # only the two exact families


def test_ucx_piece_has_channel_1_named_uv(monkeypatch):
    """RED on 1.0.0: export.checked cleanup «map channel 1 missing: no UV to rename» on all 98 KPP1 UCX pieces."""
    import types
    calls = []

    class Node:
        material = 'x'

    class PO:
        def setMapSupport(self, n, ch, on):
            calls.append(('support', ch, on))

        def defaultMapFaces(self, n, ch):
            calls.append(('default', ch))

    fake = types.SimpleNamespace(point3=lambda *a: a, mesh=lambda **k: Node(), convertToPoly=lambda n: None,
                                 polyop=PO(), setUserProp=lambda n, k, v: calls.append(('prop', k, v)),
                                 units=types.SimpleNamespace(SystemType='meters', SystemScale=1.0))
    monkeypatch.setitem(sys.modules, 'pymxs', types.SimpleNamespace(runtime=fake))
    rtm = _load('runtime.py', 'agr_runtime_101')
    monkeypatch.setattr(rtm, '_unit_m', lambda: 1.0)
    rtm._make_ucx_mesh('UCX_SM_Kpp_1_Main_001', [[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1]],
                       [[0, 1, 2], [0, 1, 3], [0, 2, 3], [1, 2, 3]])
    assert ('support', 1, True) in calls and ('default', 1) in calls and ('prop', 'MapChannel:1', 'UV') in calls


def test_vpm_copy_names_its_channel_1():
    src = (PKG / 'vpm_max.py').read_text(encoding='utf-8')
    assert "rt.setUserProp(c, 'MapChannel:1', 'UV')" in src and "rt.setUserProp(c, UDIM_PROP," in src


# ---- stage 6: maps of vpm.build named by the address, planned before the copies ----------------------------------
def test_vpm_maps_named_by_the_address_of_the_working_body(tmp_path):
    """RED on 1.0.1-pre (KPP1 e2e 20261106-101005-9a657979): with the roughness fixed, step 6 refused «mesh name
    'BODY_AGRLibraryv001_001' is not an SM object name» AFTER the copies and vpm_table.json were written. The maps
    take the SM name of options.address (T_<Address>_<map>_<slot>.<UDIM>.png)."""
    vpm = _load('vpm_core.py', 'agr_tools_vpm_core')
    lib = ml.load_library(str(LIB))
    plan = {'options': vpm.options({'address': 'Kpp_1', 'glass_ids': [39]}),
            'objects': [{'key': 1, 'name': 'BODY_AGRLibraryv001_001', 'findings': [], 'parts': [
                {'name': 'BODY_AGRLibraryv001_001', 'summary': {'part': 'body', 'udim_table': {'3': 1001, '29': 1002}}},
                {'name': 'BODY_AGRLibraryv001_001_glass', 'summary': {'part': 'glass', 'udim_table': {'39': 1001}}}]}]}
    table = vpm.maps_table(plan)
    assert table == {'SM_Kpp_1_Main': {3: 1001, 29: 1002}, 'SM_Kpp_1_MainGlass': {39: 1001}}
    res = vc.plan_maps(table, lib, str(tmp_path), {'slot': {'SM_Kpp_1_MainGlass': 2}})
    names = sorted(m['name'] for m in res['maps'])
    assert 'T_Kpp_1_Diffuse_1.1001.png' in names and 'T_Kpp_1_ERM_1.1002.png' in names and not res['skipped']
    with pytest.raises(ValueError):
        vpm.options({'address': 'Kpp 1'})
    # without the address the working name still refuses (now in the preview: vpm_max plans step 6 before copies)
    bare = dict(plan, options=vpm.options({}))
    with pytest.raises(ValueError):
        vc.plan_maps(vpm.maps_table(bare), lib, str(tmp_path))
    src = (PKG / 'vpm_max.py').read_text(encoding='utf-8')
    assert src.index('if maps_error:\n        raise ValueError') < src.index('_session_core().in_session')


def test_agr_zero_m_is_a_pipeline_key():
    """RED on 1.0.1-pre (KPP1 e2e 20261106-101005-9a657979): the +-0.000 of the building (AGR_ZERO_M, read by
    model.perimeter_drop / qa.preflight, suite_max) was a `clear_user_defined_lines` line of the cleanup gate."""
    ex = _load('export_core.py', 'agr_tools_export_core_101')
    rtm = _load('runtime.py', 'agr_runtime_101')
    assert ex.pipeline_key('AGR_ZERO_M') and 'AGR_ZERO_M' in rtm._HELD_OFF
    assert rtm._delivery_props('AGR_ZERO_M = 0.0\r\nMapChannel:1 = UV\r\n') == 'MapChannel:1 = UV\r\n'


def test_export_copy_keeps_the_user_prop_buffer(monkeypatch):
    """RED on 1.0.1-pre (diag job 20261106-102248-4ac77ac1, final scene of KPP1 e2e 20261106-101005-9a657979): the
    qa.names_fix copy SM_Kpp_1_Main had no `MapChannel:1 = UV` / agr_udim_table - Max `copy` drops the buffer."""
    import types

    class N:
        def __init__(self, name, buf=''):
            self.name, self.buf, self.material = name, buf, None

    def copy(n):                                     # as Max: the buffer is not copied
        return N(n.name)

    rt = types.SimpleNamespace(copy=copy, uniqueName=lambda s: s + '01', isValidNode=lambda n: True,
                               delete=lambda x: None, getUserPropBuffer=lambda n: n.buf,
                               setUserPropBuffer=lambda n, b: setattr(n, 'buf', b))
    monkeypatch.setitem(sys.modules, 'pymxs', types.SimpleNamespace(runtime=rt))
    em = _load('edit_max.py', 'agr_tools_edit_max_101')
    src = N('Kpp_1_VPM_Main', 'agr_udim_table = {"12": 1004}\r\nMapChannel:1 = UV\r\n')
    ((orig, c),) = em.export_copies([src], suffix='_AGR_export_names_')
    assert orig is src and c.name == 'Kpp_1_VPM_Main_AGR_export_names_01' and c.buf == src.buf


# ---- materials audit Q2-Q11 (owner answers 06.11 morning) ----------------------------------------------------------
# Library data of the 1.0.1 patch: materials_v002.json (v001 stays as released), one commit per audit question.
tl = _load('tiles_core.py', 'agr_tools_tiles_core')
UDIM_STEP_M = 3.6


def test_q2_typical_cassette_is_600x600_and_divides_the_udim_step():
    """RED before Q2: record 12 used panel_v600 (module 0.6 x the whole 3.6 m, no horizontal joints)."""
    lib = ml.load_library(str(LIB))
    rec = next(r for r in lib['materials'] if r['class'] == 'panel' and r['ral'] == '7047' and 'cassette' in r['key'])
    assert rec['library_id'] == 12 and rec['base_map'] == 'tile_600x600' and 'Q2' not in rec.get('questions', [])
    s, found = tl.spec(rec['base_map'])
    assert s['module'] == [0.6, 0.6] and s['counts'] == [6, 6] and s['stretch_pct'] == [0.0, 0.0] and not found
    for m in s['module']:
        px = m * s['px_per_m']
        assert px == round(px) == 600                       # whole pixels at 1000 px/m
        assert UDIM_STEP_M / m == pytest.approx(6)
    assert s['size_px'] == 3600
    # the KPP1 cassette 0.6 x 0.55 is a project texture of KPP: no library base map carries a 0.55 module
    for r in lib['materials']:
        if r['base_map']:
            assert 0.55 not in tl.spec(r['base_map'])[0].get('module_in', [])


def test_q3_brick_250x65_fits_14_by_48_with_a_1_5_percent_tolerance():
    """RED before Q3: the default stretch tolerance 1.2 % applied to bricks too; the owner fixed 1.5 % for bricks."""
    s, found = tl.spec('brick_250x65')
    assert s['counts'] == [14, 48] and not found
    assert 'Q3' not in ml.load_library(str(LIB))['by_id'][17].get('questions', [])
    assert s['module_in'] == [0.26, 0.075]                  # 250 + 10 mm joint, 65 + 10 mm: step 75 mm exactly
    assert s['module'][1] == pytest.approx(0.075) and s['stretch_pct'][1] == 0.0
    assert s['module'][0] * 1000 == pytest.approx(257.142857, abs=1e-5) and s['stretch_pct'][0] == pytest.approx(-1.0989, abs=1e-3)
    _, found = tl.spec('brick_250x65', {'max_stretch_pct': 1.5})
    assert not found
    # a 1.4 % stretch is inside the brick tolerance (RED with the 1.2 % default), 2 % is still a finding
    _, found = tl.spec('brick_250x65', {'module': [0.25358, 0.075]})
    assert not found
    s2, found = tl.spec('brick_250x65', {'module': [0.2521, 0.075]})
    assert s2['counts'][0] == 14 and s2['stretch_pct'][0] == pytest.approx(2.0, abs=0.01)
    assert [c for c, _ in found] == ['module_stretched']
    assert tl.DEFAULTS['max_stretch_pct'] == 1.2            # other base maps keep the 1.2 % default


def test_q4_ral_8023_7024_9006_7035_are_marked_screen_approximations():
    """RED before Q4: RAL 8023 was missing (brick record 17 had ral = null)."""
    doc = json.loads((ROOT / 'tools/materials/ral_classic.json').read_text(encoding='utf-8'))
    want = {'8023': '#A65E2E', '7024': '#474A51', '9006': '#A5A5A5', '7035': '#D7D7D7'}
    assert {c: doc['colors'][c] for c in want} == want
    assert set(doc['approximate']['codes']) == set(want) and 'screen approximation' in doc['approximate']['note'].lower()
    ral = ml.ral_table(str(ROOT / 'tools/materials/ral_classic.json'))
    # records carrying these RAL validate against the table (id 17 brick = 8023, 7 and 14 = 7024, 35 = 9006)
    lib = ml.load_library(str(LIB))
    for lid, code in ((17, '8023'), (7, '7024'), (14, '7024'), (35, '9006')):
        assert lib['by_id'][lid]['ral'] == code and lib['by_id'][lid]['rgb_srgb'] == ml.hex_rgb(want[code])
    probe = dict(lib['by_id'][17], ral='7035', rgb_srgb=ml.hex_rgb('#D7D7D7'))
    ml.validate_library({'schema': 1, 'version': 'v002', 'materials': [probe]}, ral)
    assert 'Q4' not in lib['by_id'][17].get('questions', [])


def test_q5_ribbed_panel_is_a_pattern_of_n_ribs_per_field_not_a_tile():
    """RED before Q5: record 11 carried a constant rib_pitch_m 0.19532 and the string ribs = per_facade."""
    import copy
    lib = ml.load_library(str(LIB))
    r = lib['by_id'][11]
    assert r['recipe'] == {'kind': 'metric_pattern', 'pattern': 'ribs_per_field', 'params': ['field_m', 'ribs']}
    assert r['base_map'] is None and 'rib_pitch_m' not in r['recipe'] and 'Q5' not in r.get('questions', [])
    assert ml.rib_pitch_m(5.86, 30) == pytest.approx(5.86 / 30) and ml.rib_pitch_m(2.4, 12) == pytest.approx(0.2)
    for field, ribs in ((0, 5), (-1.0, 5), (2.4, 0), (2.4, 2.5), (2.4, True), (float('nan'), 3)):
        with pytest.raises(ValueError):
            ml.rib_pitch_m(field, ribs)
    ral = ml.ral_table(str(ROOT / 'tools/materials/ral_classic.json'))
    doc = {'schema': 1, 'version': 'v002', 'materials': [copy.deepcopy(r)]}
    ml.validate_library(doc, ral)
    doc['materials'][0]['recipe']['rib_pitch_m'] = 0.19532       # a constant pitch contradicts N ribs per field
    with pytest.raises(ValueError, match='ribs_per_field'):
        ml.validate_library(doc, ral)
    doc['materials'][0]['recipe'] = {'kind': 'metric_pattern', 'pattern': 'ribs_per_field', 'params': ['field_m']}
    with pytest.raises(ValueError, match='ribs_per_field'):
        ml.validate_library(doc, ral)


def test_q6_lawn_rolled_and_lawn_reinforced_are_two_records():
    """RED before Q6: the library had only lawn_reinforced (OKS-GRD-05 merged the pair of Vatutino recipes)."""
    lib = ml.load_library(str(LIB))
    by_key = {r['key']: r for r in lib['materials']}
    rolled, reinforced = by_key['lawn_rolled'], by_key['lawn_reinforced']
    assert rolled['library_id'] != reinforced['library_id'] and rolled['library_id'] == 41
    assert rolled['class'] == reinforced['class'] == 'ground'
    assert rolled['rgb_srgb'] != reinforced['rgb_srgb']
    recipes = json.loads((ROOT / 'tools/materials/ground_recipes.json').read_text(encoding='utf-8'))['slots']
    assert rolled['source']['ground_recipe'] == 'LawnRolled' and reinforced['source']['ground_recipe'] == 'LawnReinforced'
    assert recipes['LawnRolled']['family'] == 'lawn' and recipes['LawnReinforced']['family'] == 'ecogrid'
    assert rolled['source']['audit_id'] == reinforced['source']['audit_id'] == 'OKS-GRD-05'
    assert 'Q6' not in rolled.get('questions', []) and 'Q6' not in reinforced.get('questions', [])
    for r in (rolled, reinforced):
        assert r['source']['ground_recipe'] in recipes


def test_q7_ground_coverings_live_in_a_separate_ground_table_referenced_by_the_oks_table(tmp_path):
    """RED before Q7: the GRD/PAV records (paving + ground classes) were inside materials_v002.json."""
    import shutil
    folder = ROOT / 'library/materials'
    oks = json.loads((folder / 'materials_v002.json').read_text(encoding='utf-8'))
    ground = json.loads((folder / 'ground_v001.json').read_text(encoding='utf-8'))
    assert {r['class'] for r in ground['materials']} == {'ground', 'paving'}
    assert not {r['class'] for r in oks['materials']} & {'ground', 'paving'}
    assert oks['ground_ref']['file'] == 'ground_v001.json'
    lib = ml.load_library(str(LIB))
    assert lib['ground']['version'] == 'v001' and lib['ground']['sha256'] == oks['ground_ref']['sha256']
    gids = {r['library_id'] for r in ground['materials']}
    assert gids == {18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 41}                     # ids are stable, none renumbered
    assert gids <= set(lib['by_id']) and not gids & {r['library_id'] for r in oks['materials']}
    assert sorted(lib['by_id']) == list(lib['by_id']) and len(lib['materials']) == 41
    assert lib['by_id'][26]['key'] == 'lawn_reinforced' and lib['by_id'][18]['class'] == 'paving'
    # a changed ground table is refused (the OKS table pins its sha256), a missing one too
    for k in ('materials.json', 'materials_v002.json'):
        shutil.copy(folder / k, tmp_path / k)
    (tmp_path / 'ground_v001.json').write_bytes((folder / 'ground_v001.json').read_bytes().replace(b'"v001"', b'"v001" ', 1))
    with pytest.raises(ValueError, match='ground'):
        ml.load_library(str(tmp_path / 'materials.json'))
    (tmp_path / 'ground_v001.json').unlink()
    with pytest.raises(FileNotFoundError):
        ml.load_library(str(tmp_path / 'materials.json'))
    # a ground/paving class record inside the OKS table is a defect once the Ground table is referenced
    moved = json.loads(json.dumps(oks))
    moved['materials'].append(dict(ground['materials'][0], library_id=900, key='stray_paving'))
    (tmp_path / 'materials_v002.json').write_text(json.dumps(moved), encoding='utf-8')
    (tmp_path / 'ground_v001.json').write_bytes((folder / 'ground_v001.json').read_bytes())
    direct = ml.load_library
    with pytest.raises(ValueError, match='Ground table'):
        direct(str(tmp_path / 'materials_v002.json'))


def test_q9_library_rgb_is_ral_classic_unless_marked_as_a_project_override():
    """RED before Q9: no `rgb_override` marker existed and records 4, 7, 32 still listed Q9 as open."""
    import copy
    lib = ml.load_library(str(LIB))
    ral = ml.ral_table(str(ROOT / 'tools/materials/ral_classic.json'))
    assert ral['1021'] == '#F6B600' and ral['7024'] == '#474A51'
    for r in lib['materials']:
        if r['ral'] is not None and not r.get('rgb_override'):
            assert r['rgb_srgb'] == ml.hex_rgb(ral[r['ral']]), r['key']
    assert lib['by_id'][4]['rgb_srgb'] == [246, 182, 0] and lib['by_id'][7]['rgb_srgb'] == [71, 74, 81]
    for lid in (4, 7, 32):
        assert 'Q9' not in lib['by_id'][lid].get('questions', []) and 'Q9' in lib['by_id'][lid]['rgb_note']
    # the KPP value (238, 201, 0) is a project override of the KPP passport: refused in the library unless marked
    probe = copy.deepcopy(lib['by_id'][4])
    probe['rgb_srgb'] = [238, 201, 0]
    doc = {'schema': 1, 'version': 'v002', 'materials': [probe]}
    with pytest.raises(ValueError, match='differs from ral_classic'):
        ml.validate_library(doc, ral)
    probe['rgb_override'] = True
    ml.validate_library(doc, ral)
    probe['rgb_override'] = 'yes'
    with pytest.raises(ValueError, match='rgb_override'):
        ml.validate_library(doc, ral)


def test_q11_joint_5_mm_is_approved_for_paving_100x300_and_tile_600x1200():
    """RED before Q11: the 5 mm joint was recorded as provisional (tiles_core sources, ground recipes, records)."""
    for name in ('facade_600x1200', 'ground_100x300'):
        s, _ = tl.spec(name)
        assert s['joint'] == 0.005 and 'approved' in s['source'] and 'Q11' in s['source'], name
    recipes = json.loads((ROOT / 'tools/materials/ground_recipes.json').read_text(encoding='utf-8'))['slots']
    paving = [n for n, b in recipes.items() if b.get('family') == 'tile']
    assert paving == ['TileLight', 'TileRed', 'TileDark']
    for n in paving:
        body = recipes[n]
        assert body['nominal_tile_mm'] == [100, 300] and body['joint_mm'] == 5
        assert 'joint_mm' not in {f['field'] for f in body['provisional']}
        assert [(a['field'], a['value']) for a in body['approved']] == [('joint_mm', 5)]
    lib = ml.load_library(str(LIB))
    for lid in (14, 18):
        assert 'Q11' not in lib['by_id'][lid].get('questions', []) and 'Q11' in lib['by_id'][lid]['note']


def test_vpm_maps_read_the_grey_masks_of_mat_tiles(tmp_path):
    """RED on 1.0.1-pre (KPP1 e2e 20261106-102522-ac59f4c6): D and N of the mask recipes (panels, cassette, tile)
    were skipped «base map 'panel_v600' ... not found as PNG in map_dir» - mat.tiles writes <base>_mask.png and
    vpm.build did not pass a map_dir at all."""
    vpm = _load('vpm_core.py', 'agr_tools_vpm_core')
    lib = ml.load_library(str(LIB))
    masks = tmp_path / 'tiles'
    masks.mkdir()
    grey = bytearray()
    for y in range(8):
        for x in range(8):
            grey += bytes([255 if x % 4 else 0] * 3)
    base = lib['by_id'][12]['base_map']                                                      # the cassette mask
    (masks / (base + '_mask.png')).write_bytes(tc.encode_png(tc.Image(8, 8, 3, grey)))     # name as tiles_max
    o = vpm.options({'address': 'Kpp_1', 'map_dir': str(masks)})
    assert o['map_dir'] == str(masks)
    res = vc.plan_maps({'SM_Kpp_1_Main': {12: 1001}}, lib, str(tmp_path / 'o'), {'map_dir': o['map_dir']})
    assert sorted(m['kind'] for m in res['maps']) == ['D', 'ERM', 'N'] and not res['skipped']
    src = (PKG / 'vpm_max.py').read_text(encoding='utf-8')
    assert src.count(', _maps_options(o))') == 2          # plan_maps and build_maps both get map_dir
