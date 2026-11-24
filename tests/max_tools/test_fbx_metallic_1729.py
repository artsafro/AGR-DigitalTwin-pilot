"""new-case: #1729 metallic map FBX round trip: the NPM/VPM metallic map is exported to the channel SINTEZ 2.5.6 reads, and a
Max FBX import never drops a customer `_m` map silently (readback of unconnected embedded maps).

Fixtures tests/fixtures/fbx_metallic_1729/*.fbx.gz.b64 are SYNTHETIC 1-plane scenes exported by 3ds Max 2026.3 batch
(tools/max/metallic_channel_probe_max.py, 2026-11-21), gzip + base64 text (no Git LFS, COORDINATION rule 57);
the other FBX here are written by `_fbx` below.
"""
import base64
import gzip
import importlib.util
import json
import os
import random
import struct
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / 'adapters' / 'max' / 'agr_tools'
FIX = ROOT / 'tests' / 'fixtures' / 'fbx_metallic_1729'


def _load(name, alias):
    spec = importlib.util.spec_from_file_location(alias, PKG / name)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[alias] = mod
    spec.loader.exec_module(mod)
    return mod


fc = _load('fbxmaps_core.py', 'agr_tools_fbxmaps_core_t1729')
fm = _load('fbxmaps_max.py', 'agr_tools_fbxmaps_max_t1729')
nc = _load('names_core.py', 'agr_tools_names_core_t1729')
tc = _load('tex_core.py', 'agr_tools_tex_core_t1729')


def test_max_reports_held_slot_to_reconnect_plan():
    from types import SimpleNamespace

    bitmap = SimpleNamespace(fileName='already_here.png')
    material = SimpleNamespace(name='Ground', reflectionMap=bitmap)
    rt = SimpleNamespace(Bitmaptexture='Bitmaptexture',
                         classOf=lambda obj: 'Bitmaptexture' if obj is bitmap else 'Standardmaterial')
    slots = fm.scene_materials(rt, fc.RECONNECT_SLOT, [material])
    plan = fc.reconnect_plan([{'file': 'missing_m.png',
                               'materials': [('Ground', 'ReflectionFactor', 'metalness')]}], slots)
    assert plan['connect'] == []
    assert 'Ground.reflectionMap already holds already_here.png' in plan['failures'][0]['reason']


# ---- minimal binary FBX 7400 writer (Objects: Material/Texture/Video, Connections) --------------------
def _prop(v):
    if isinstance(v, bytes):
        return b'R' + struct.pack('<I', len(v)) + v
    if isinstance(v, str):
        b = v.encode('utf-8')
        return b'S' + struct.pack('<I', len(b)) + b
    return b'L' + struct.pack('<q', v)


def _node(name, props=(), children=(), at=0):
    pb = b''.join(_prop(p) for p in props)
    head_len = 13 + len(name)
    body = b''
    cur = at + head_len + len(pb)
    for ch in children:
        raw = ch(cur)
        body += raw
        cur += len(raw)
    if children:
        body += b'\x00' * 13
    end = at + head_len + len(pb) + len(body)
    return struct.pack('<III', end, len(props), len(pb)) + bytes([len(name)]) + name.encode() + pb + body


def N(name, props=(), children=()):
    return lambda at: _node(name, props, children, at)


def _fbx(materials, embed=True, extra_videos=()):
    """materials: {name: [(channel, file)]} -> bytes. Every file is a Texture with a Video (embedded if `embed`)."""
    objs, conns, nid = [], [], [100]

    def new():
        nid[0] += 1
        return nid[0]
    for mat, links in materials.items():
        mid = new()
        objs.append(N('Material', (mid, mat + '\x00\x01Material', '')))
        for channel, f in links:
            tid, vid = new(), new()
            objs.append(N('Texture', (tid, 'tex\x00\x01Texture', ''), [N('RelativeFilename', ('x.fbm\\' + f,))]))
            objs.append(N('Video', (vid, 'vid\x00\x01Video', 'Clip'),
                          [N('RelativeFilename', ('x.fbm\\' + f,)), N('Content', (b'PNG' + f.encode() if embed else b'',))]))
            conns.append(N('C', ('OO', vid, tid)))
            conns.append(N('C', ('OP', tid, mid, channel)))
    for f, content in extra_videos:
        objs.append(N('Video', (new(), 'vid\x00\x01Video', 'Clip'), [N('RelativeFilename', (f,)),
                                                                     N('Content', (content,))]))
    head = b'Kaydara FBX Binary  \x00\x1a\x00' + struct.pack('<I', 7400)
    out, at = head, len(head)
    for top in (N('Objects', (), objs), N('Connections', (), conns)):
        raw = top(at)
        out += raw
        at += len(raw)
    return out + b'\x00' * 13


def _fixture(case):
    raw = (FIX / '0001_Probe1729_{}_Ground.fbx.gz.b64'.format(case)).read_text(encoding='ascii')
    return gzip.decompress(base64.b64decode(raw))


@pytest.mark.parametrize('case', ['approve', 'decline', 'missing_media', 'unknown_channel', 'no_embedded',
                                 'ambiguous_slot', 'duplicate_material', 'changed_selection', 'empty', 'truncated'])
def test_panel_reconnect_selection(tmp_path, case):
    from contextlib import nullcontext
    from types import SimpleNamespace

    class Bitmap:
        def __init__(self, fileName):
            self.fileName = fileName

    name = 'map_m.png'
    src = tmp_path / 'copy.fbx'
    links = [('UnknownChannel' if case == 'unknown_channel' else 'ReflectionFactor', name)]
    if case == 'ambiguous_slot':
        links.append(('ReflectionColor', 'other_m.png'))
    data = _fbx({'Ground': links}, embed=case != 'no_embedded')
    if case == 'truncated':
        data = data[:30]
    src.write_bytes(data)
    folder = src.with_suffix('.fbm')
    folder.mkdir()
    if case != 'missing_media':
        (folder / name).write_bytes(b'PNG' + name.encode())
    selected = SimpleNamespace(name='Ground', reflectionMap=None)
    decoy = SimpleNamespace(name='Ground', reflectionMap=Bitmap(name))
    node = SimpleNamespace(material=selected)
    decoy_node = SimpleNamespace(material=decoy)
    rt = SimpleNamespace(selection=[] if case == 'empty' else [node], sceneMaterials=[decoy, selected],
                         getHandleByAnim=id, getNumSubMtls=lambda m: 0, Bitmaptexture=Bitmap,
                         classOf=lambda m: Bitmap if isinstance(m, Bitmap) else 'Standardmaterial',
                         getNumSubTexmaps=lambda m: int(hasattr(m, 'reflectionMap')),
                         getSubTexmap=lambda m, i: m.reflectionMap, getSubTexmapSlotName=lambda m, i: 'Reflection',
                         isProperty=hasattr, Name=str)
    if case == 'duplicate_material':
        rt.selection.append(decoy_node)
    prompts = []

    def confirm(before, plan):
        prompts.append(before['status'])
        assert [row['file'] for row in before['unconnected']] == [name]
        assert plan['connect'][0]['slot'] == 'reflectionMap'
        if case == 'changed_selection':
            rt.selection[:] = [decoy_node]
        return case != 'decline'

    def run():
        return fm.check_selection(rt, fc, str(src), confirm, lambda *_: nullcontext())

    errors = {'empty': 'Select the objects', 'truncated': 'FBX', 'duplicate_material': 'Duplicate material names: Ground',
              'changed_selection': 'changed'}
    if case in errors:
        with pytest.raises(ValueError, match=errors[case]):
            run()
    else:
        result = run()
        assert result['before']['status'] == ('no_embedded_maps' if case == 'no_embedded' else 'fail')
        if case == 'approve':
            assert result['after']['status'] == 'pass' and not result['failures']
        elif case == 'missing_media':
            assert result['after']['status'] == 'fail'
            assert 'not extracted' in result['failures'][0]['reason']
        else:
            assert result['after'] is None
        if case in ('unknown_channel', 'ambiguous_slot'):
            assert name in {row['file'] for row in result['failures']}
    assert len(prompts) == int(case in ('approve', 'decline', 'missing_media', 'changed_selection'))
    assert (selected.reflectionMap is not None) == (case == 'approve')
    assert src.read_bytes() == data and decoy.reflectionMap.fileName == name


def _metal_slot():
    return next(slot for slot, role in nc.SLOT_TABLE['Standardmaterial'] if role == 'metalness')


# ---- acceptance 4a: export -> FBX readback, the `_m` map on the SINTEZ channel ----------------------------
def test_1729_standard_metallic_export_lands_on_sintez_channel():
    """Incident: SLOT_TABLE put `_m` on specularLevelMap -> Max FBX SpecularFactor -> SINTEZ 2.5.6 fail."""
    channels = {'diffuseMap': None, 'glossinessMap': None, _metal_slot(): None}
    files = {'diffuseMap': 'T_A_1_Ground_d_1.png', 'glossinessMap': 'T_A_1_Ground_r_1.png',
             _metal_slot(): 'T_A_1_Ground_m_1.png'}
    for slot in channels:
        channels[slot] = fc.export_channel(slot)
    doc = fc.read_material_maps(_fbx({'M_A_1_Ground_1': [(channels[s], files[s]) for s in channels]}))
    assert channels[_metal_slot()] in fc.METALLIC_CHANNELS, channels
    assert fc.metallic_channel_findings(doc) == []
    # the incident file itself (map on SpecularFactor) fails
    bad = fc.read_material_maps(_fbx({'M_A_1_Ground_1': [('DiffuseColor', files['diffuseMap']),
                                                          ('SpecularFactor', 'T_A_1_Ground_m_1.png')]}))
    assert [r['channel'] for r in fc.metallic_channel_findings(bad)] == ['SpecularFactor']


@pytest.mark.parametrize('case, failing', [('stdspecularLevel', 1), ('stdreflection', 0), ('physmetalness', 0)])
def test_1729_real_max2026_export_fixtures(case, failing):
    doc = fc.read_material_maps(_fixture(case))
    found = fc.metallic_channel_findings(doc)
    assert len(found) == failing, found
    if failing:
        assert found[0]['channel'] == 'SpecularFactor' and found[0]['file'].endswith('_m_1.png')
    assert len(doc['embedded']) == 3


def test_1729_slot_table_resolves_v13_explicitly():
    std = dict(nc.SLOT_TABLE['Standardmaterial'])
    assert std['reflectionMap'] == 'metalness' and std['specularLevelMap'] is None
    assert [r for _s, r in nc.SLOT_TABLE['Standardmaterial']].count('metalness') == 1  # V2: one slot per role
    assert 'SINTEZ' in nc.SLOT_NOTES['specularLevelMap']
    nm = (PKG / 'names_max.py').read_text(encoding='utf-8')
    assert "('specularLevelMap', None), ('reflectionMap', 'metalness')" in nm
    assert tc.role_of_slot('Reflection') == 'metalness' and tc.role_of_slot('reflectionMap') == 'metalness'
    assert tc.role_of_slot('Specular Level') is None and tc.role_of_slot('specularLevelMap') is None
    for other in ('Reflectivity Map', 'reflectivity_map', 'Reflection Color Map', 'refl_color_map', 'coat_reflection'):
        assert tc.role_of_slot(other) is None, other
    assert tc.role_of_slot('metalness_map') == 'metalness'


def test_1729_names_fix_reports_specular_level_with_sintez_reason():
    state = {'objects': [{'key': 1, 'name': 'SM_Bench_001_Main', 'geometry': True, 'ucx': False, 'model': 'npm',
                          'material': {'name': 'Old', 'class': 'Standardmaterial', 'subs': None, 'maps': [
                              {'key': 'specularLevelMap', 'role': None, 'path': 'C:/t/spec.png', 'name': 'map'},
                              {'key': 'reflectionMap', 'role': 'metalness', 'path': 'C:/t/refl.png',
                               'name': 'map'}]}}],
        'files': {'C:/t/spec.png': {'exists': True, 'sha256': 's' * 64},
                  'C:/t/refl.png': {'exists': True, 'sha256': 'r' * 64}}, 'export_names': []}
    plan = nc.names_fix_plan(state, {})
    m = [f for f in plan['files'] if f['target'].endswith('_m_1.png')]
    assert len(m) == 1 and m[0]['source'] == 'C:/t/refl.png', plan['files']
    assert any('specularLevelMap' in f['reason'] and 'SINTEZ' in f['reason'] for f in plan['failures'])


# ---- acceptance 3 + 4b: import readback ------------------------------------------------------------------
CUSTOMER = {'M_P_ZU_7_A_Ground_1': [('DiffuseColor', 'T_P_ZU_7_A_Ground_d_1.png'),
                                    ('ShininessExponent', 'T_P_ZU_7_A_Ground_r_1.png'),
                                    ('ReflectionFactor', 'T_P_ZU_7_A_Ground_m_1.png')]}


def test_1729_import_embedded_m_left_unconnected_fails():
    doc = fc.read_material_maps(_fbx(CUSTOMER))
    # what Max 2026.3 connects after the import (measured): diffuse + glossiness, the ReflectionFactor map dropped
    scene = ['C:/w/x.fbm/T_P_ZU_7_A_Ground_d_1.png', 'C:/w/x.fbm/T_P_ZU_7_A_Ground_r_1.png']
    rb = fc.import_readback(doc, scene)
    assert rb['status'] == 'fail' and not rb['passed']
    assert [(r['file'], r['role']) for r in rb['unconnected']] == [('T_P_ZU_7_A_Ground_m_1.png', 'metalness')]
    plan = fc.reconnect_plan(rb['unconnected'], {'M_P_ZU_7_A_Ground_1': {'class': 'Standardmaterial', 'slots': {}}})
    assert plan['failures'] == []
    assert [(c['slot'], c['role']) for c in plan['connect']] == [('reflectionMap', 'metalness')]
    # after the reconnect the readback passes; alias spelling of the same file (case, folder) counts as connected
    after = fc.import_readback(doc, scene + ['D:\\OTHER\\t_p_zu_7_a_ground_M_1.PNG'])
    assert after['status'] == 'pass' and after['unconnected'] == []


def test_1729_reconnect_failures_are_named():
    doc = fc.read_material_maps(_fbx({'M_A': [('SpecularFactor', 'T_A_s_1.png'), ('ReflectionFactor', 'T_A_m_1.png'),
                                              ('DiffuseColor', 'T_A_d_1.png')],
                                      'M_Gone': [('ReflectionFactor', 'T_G_m_1.png')]}))
    rows = fc.unconnected_embedded(doc, [])
    plan = fc.reconnect_plan(rows, {'M_A': {'class': 'Standardmaterial', 'slots': {'diffuseMap': 'C:/q/other.png'}}})
    reasons = ' | '.join(f['reason'] for f in plan['failures'])
    assert 'SpecularFactor has no map role' in reasons          # unknown role: named, not defaulted
    assert 'material M_Gone not in the scene' in reasons
    assert 'M_A.diffuseMap already holds other.png' in reasons  # occupied slot never overwritten
    assert [c['file'] for c in plan['connect']] == ['T_A_m_1.png']
    every = {r['file'] for r in rows}
    assert every == {c['file'] for c in plan['connect']} | {f['file'] for f in plan['failures']}


def test_1729_fail_closed_inputs():
    with pytest.raises(ValueError, match='not a binary FBX'):
        fc.read_material_maps(b'; FBX 7.4.0 project file\n')
    with pytest.raises(ValueError, match='not a binary FBX'):
        fc.read_material_maps(b'')
    good = _fbx(CUSTOMER)
    with pytest.raises(ValueError):
        fc.read_material_maps(good[:len(good) // 2])
    with pytest.raises(ValueError, match='required'):
        fc.unconnected_embedded(fc.read_material_maps(good), None)
    none = fc.import_readback(fc.read_material_maps(_fbx(CUSTOMER, embed=False)), [])
    assert none['status'] == 'no_embedded_maps' and none['passed'] is False
    dup = fc.read_material_maps(_fbx(CUSTOMER, extra_videos=[('T_P_ZU_7_A_Ground_m_1.png', b'OTHER')]))
    rb = fc.import_readback(dup, [r for links in CUSTOMER.values() for _c, r in links])
    assert rb['status'] == 'fail' and 'different content' in rb['conflicts'][0]
    with pytest.raises(KeyError, match='not measured'):
        fc.export_channel('opacityMap')


def test_1729_probe_every_embedded_map_connected_or_listed():
    """Generated: 300 seeds, 1-6 materials x 1-5 maps on random channels, random subset connected."""
    channels = list(fc.FBX_ROLES) + ['SpecularFactor', 'Weird|Channel']
    for seed in range(300):
        rnd = random.Random(seed)
        mats = {'M_{}'.format(i): [(rnd.choice(channels), 'T_{}_{}_{}.png'.format(i, j, rnd.choice('dmrno')))
                                   for j in range(rnd.randint(1, 5))] for i in range(rnd.randint(1, 6))}
        doc = fc.read_material_maps(_fbx(mats))
        files = [f for links in mats.values() for _c, f in links]
        connected = [f for f in files if rnd.random() < 0.5]
        rb = fc.import_readback(doc, connected)
        assert {r['file'] for r in rb['unconnected']} == set(files) - set(connected), seed
        assert rb['passed'] == (set(connected) == set(files)), seed
        for r in rb['unconnected']:
            ch = [c for c, f in sum(mats.values(), []) if f == r['file']]
            assert r['role'] == fc.FBX_ROLES.get(ch[0]), (seed, r)
        assert all(fc.FBX_ROLES.get(c) is None or r for c, r in [(l['channel'], l['role'])
                                                                  for ls in doc['materials'].values() for l in ls])


def test_1729_cli_fresh_process_refuses_output_alias(tmp_path):
    fbx = tmp_path / 'c.fbx'
    fbx.write_bytes(_fbx(CUSTOMER))
    scene = tmp_path / 'import.json'
    scene.write_text(json.dumps({'connected': [{'file': 'T_P_ZU_7_A_Ground_d_1.png'}]}), encoding='utf-8')
    cli = [sys.executable, str(ROOT / 'tools' / 'qa' / 'fbx_maps_readback.py')]
    before = (fbx.read_bytes(), scene.read_bytes())
    for out in (fbx, scene):
        r = subprocess.run(cli + ['import', str(fbx), '--scene', str(scene), '--output', str(out)],
                           capture_output=True, text=True)
        assert r.returncode == 2 and 'input' in r.stderr
    assert (fbx.read_bytes(), scene.read_bytes()) == before
    out = tmp_path / 'rb.json'
    r = subprocess.run(cli + ['import', str(fbx), '--scene', str(scene), '--output', str(out)],
                       capture_output=True, text=True)
    assert r.returncode == 1 and 'unconnected=2' in r.stdout
    rb = json.loads(out.read_text(encoding='utf-8'))
    assert sorted(x['file'] for x in rb['unconnected']) == ['T_P_ZU_7_A_Ground_m_1.png', 'T_P_ZU_7_A_Ground_r_1.png']
    r = subprocess.run(cli + ['import', str(fbx), '--scene', str(scene), '--output', str(out)],
                       capture_output=True, text=True)
    assert r.returncode == 2 and 'never reused' in r.stderr
    spec = tmp_path / '0001_Probe1729_stdspecularLevel_Ground.fbx'
    spec.write_bytes(_fixture('stdspecularLevel'))
    r = subprocess.run(cli + ['channels', str(spec)],
                       capture_output=True, text=True)
    assert r.returncode == 1 and 'SpecularFactor' in r.stdout
