"""new-case: #908 branch D native run of qa.package, export.zip, export.ground_fbx in locked batch Max (DISPOSABLE scene).
#979 branch E3 rework: export.zip writes a new `Сборка_*` run folder with ГОТОВО.txt / ОШИБКА.txt (AGR_Arxiv 1.5
contract); qa.package names each corrupt archive by its own code (no crash) and compares OKS/Ground passports;
export.cleanup keeps vertex channels, keys and AGR_EXPORT_PATH by default and removes them only on the copy (opt-in).

Run via the lab DCC runner; AGR_TEST_OUTPUT must name a NEW directory, AGR_TEST_PACKAGE the built MZP,
AGR_TOOLS_REPO the pilot checkout (validator), AGR_PYTHON its interpreter. Installs the MZP into OUT (no user folders
touched) and checks in the real Max Python through runtime.edits_080:

* qa.package: `0127_X.zip` + stray PNG, no profile -> NPM, V001 'foreign files: preview.png' (lab L04);
* export.zip: the acceptance folder of docs/experiments/export.zip.md -> exactly 0123_X.zip, SM_X.zip (with _Light, no
  _0011), SM_X_Ground.zip; decoys untouched; validator V001 pass; a second run writes nothing;
* export.ground_fbx: the acceptance scene of docs/experiments/export.ground_fbx.md (SM_X_GroundGlass created first)
  -> exactly 0123_X_Ground.fbx (5 Ground-family meshes) and 0123_X_01.fbx; plan independent of node order;
  originals unchanged; selection restored; a second run writes nothing. Blender readback (V002/V003/V012) is a
  separate Blender-slot job (run_agr_tools_package_readback.py) on these files.
Nothing is saved; the scene is never written. All data synthetic.
"""
import hashlib
import json
import os
import struct
import sys
import traceback
import zlib
import zipfile
from pathlib import Path

from pymxs import runtime as rt

OUT = Path(os.environ['AGR_TEST_OUTPUT'])
OUT.mkdir(parents=True, exist_ok=False)
PACKAGE = Path(os.environ['AGR_TEST_PACKAGE'])
os.environ['LOCALAPPDATA'] = str(OUT / 'localappdata')
summary = {'max_version': list(rt.maxVersion())[:3], 'package_sha256': hashlib.sha256(PACKAGE.read_bytes()).hexdigest(),
           'checks': {}, 'errors': {}}
assert not rt.maxFileName, 'only an empty batch document is allowed'
FBX = b'Kaydara FBX Binary  \x00\x1a\x00' + struct.pack('<I', 7400) + b'\x00' * 64


def check(name, fn):
    try:
        summary['checks'][name] = fn()
    except Exception:  # noqa: BLE001 - recorded; the run fails at the end
        summary['errors'][name] = traceback.format_exc()[-3000:]


def png(rgb, size=256):
    """Flat RGB PNG, stdlib only (Max Python has no PIL)."""
    raw = b''.join(b'\x00' + bytes(rgb) * size for _ in range(size))

    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff)
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', size, size, 8, 2, 0, 0, 0)) +
            chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b''))


def _p(v):
    if isinstance(v, int) and v > 1000:
        return b'L' + struct.pack('<q', v)
    if isinstance(v, int):
        return b'I' + struct.pack('<i', v)
    raw = v.encode('latin-1')
    return b'S' + struct.pack('<I', len(raw)) + raw


def _node(name, props=(), children=(), at=0):
    body = b''.join(_p(x) for x in props)
    kids, pos = b'', at + 13 + len(name) + len(body)
    for c in children:
        blob = _node(*c, at=pos)
        kids, pos = kids + blob, pos + len(blob)
    if children:
        kids += b'\x00' * 13
    end = at + 13 + len(name) + len(body) + len(kids)
    return struct.pack('<III', end, len(props), len(body)) + bytes([len(name)]) + name.encode() + body + kids


def light_fbx(cipher):
    """Binary FBX 7400: `<cipher>_Root` null with one `<cipher>_Omni_001` light parented (Light FBX rules, #979)."""
    objects = [('Model', (5000, cipher + '_Root\x00\x01Model', 'Null'), ()),
               ('Model', (6000, cipher + '_Omni_001\x00\x01Model', 'Light'), ()),
               ('NodeAttribute', (7000, cipher + '_Omni_001\x00\x01NodeAttribute', 'Light'),
                [('Properties70', (), [('P', ('LightType', 'enum', '', '', 0))])])]
    links = [('C', ('OO', 5000, 0)), ('C', ('OO', 7000, 6000)), ('C', ('OO', 6000, 5000))]
    out = FBX[:27]
    for n in (('Objects', (), objects), ('Connections', (), links)):
        out += _node(*n, at=len(out))
    return out + b'\x00' * 13


def geojson():
    """A complete VPM passport (the polygon's valid_oks.geojson, V011 pass): a stub would fail the validator, and
    export.zip then rightly writes ОШИБКА.txt (#979)."""
    return (Path(os.environ['AGR_TOOLS_REPO']) / 'test-polygon' / 'geojson' / 'valid_oks.geojson').read_bytes()


def install():
    rt.execute('global AGRToolsInstallRoot; global AGRToolsStartupRoot')
    rt.AGRToolsInstallRoot = str(OUT / 'installed') + '/'
    rt.AGRToolsStartupRoot = str(OUT / 'startup') + '/'
    rt.makeDir(rt.AGRToolsStartupRoot, all=True)
    rt.fileIn(str(PACKAGE))
    assert rt.execute('global AGRToolsRegistered; AGRToolsRegistered == true'), 'MZP macros not registered'
    sys.path.insert(0, str(OUT / 'installed'))
    import runtime as agr
    return agr


agr = install()
summary['runtime_version'] = agr.VERSION
summary['validator_python'] = os.environ.get('AGR_PYTHON')


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def stage(table, sid):
    return next(s for s in table['stages'] if s['id'] == sid)


def qa_package():
    d = OUT / 'qa'
    d.mkdir()
    z = d / '0127_X.zip'
    with zipfile.ZipFile(z, 'w') as f:
        for n, data in (('0127_X_01.fbx', FBX), ('0127_X_Ground.fbx', FBX), ('preview.png', png((1, 1, 1)))):
            f.writestr(n, data)
    r = agr.edits_080('qa.package', 'preview', options={'path': str(z), 'scene': False})
    (table,) = r['plan']['reports']
    assert table['profile'] == 'npm' and table['exit_code'] == 1, table
    assert any('foreign files: preview.png' in f for f in stage(table, 'V001')['non_pass']), stage(table, 'V001')
    assert agr.parse_report(json.dumps(r)) == r and r['status'] == 'fail'
    return {'profile': table['profile'], 'exit_code': table['exit_code'],
            'stages': {s['id']: s['status'] for s in table['stages']}}


def zip_folder():
    d = OUT / 'zip'
    d.mkdir()
    files = {'0123_X_01.fbx': FBX, '0123_X_02.fbx': FBX, '0123_X_Ground.fbx': FBX, 'SM_X.fbx': FBX,
             'SM_X_Light.fbx': light_fbx('SM_X'), 'SM_X.geojson': geojson(), 'SM_X_Ground.fbx': FBX,
             'SM_X_Ground_Light.fbx': light_fbx('SM_X_Ground'), 'SM_X_Ground.geojson': geojson(),
             'SM_X_0011.fbx': FBX,
             'SM_X_0011.geojson': geojson(), 'T_X_0011_Diffuse_1.1001.png': png((1, 2, 3)),
             '0123_Other_01.fbx': FBX, 'notes.txt': b'decoy'}
    for m, c in (('Diffuse', (120, 110, 100)), ('ERM', (0, 170, 0)), ('Normal', (128, 128, 255))):
        files['T_X_{}_1.1001.png'.format(m)] = png(c)
        files['T_X_Ground_{}_1.1001.png'.format(m)] = png(c)
    for n, data in files.items():
        (d / n).write_bytes(data)
    return d


def export_zip():
    d = zip_folder()
    before = {p.name: sha(p) for p in d.iterdir()}
    p = agr.edits_080('export.zip', 'preview', options={'folder': str(d)})
    assert p['plan']['done'] == ['0123_X.zip', 'SM_X.zip', 'SM_X_Ground.zip'], p['plan']
    r = agr.edits_080('export.zip', 'apply', p)
    assert r['plan']['done'] == p['plan']['done'], r['plan']
    run = Path(r['plan']['run_folder'])
    assert run.parent == d and run.name.startswith('Сборка_') and r['plan']['marker'] == 'ГОТОВО.txt', r['plan']
    assert sorted(set(os.listdir(d)) - set(before)) == [run.name], os.listdir(d)
    new = sorted(n for n in os.listdir(run) if n.endswith('.zip'))
    assert new == ['0123_X.zip', 'SM_X.zip', 'SM_X_Ground.zip'], new
    assert (run / 'ГОТОВО.txt').is_file() and not (run / 'ОШИБКА.txt').exists() and (run / 'report.json').is_file()
    with zipfile.ZipFile(run / 'SM_X.zip') as z:
        names = z.namelist()
    assert 'SM_X_Light.fbx' in names and not any('0011' in n for n in names), names
    assert {n: sha(d / n) for n in before} == before
    v = {t['target'].replace('\\', '/').rsplit('/', 1)[-1]: {s: stage(t, s)['status'] for s in ('V001', 'V012')}
         for t in r['plan']['reports']}
    assert all(x['V001'] == 'pass' and x['V012'] != 'fail' for x in v.values()), v
    stamp = {n: sha(run / n) for n in os.listdir(run)}
    p2 = agr.edits_080('export.zip', 'preview', options={'folder': str(d)})
    r2 = agr.edits_080('export.zip', 'apply', p2)
    run2 = Path(r2['plan']['run_folder'])
    assert run2 != run and {n: sha(run / n) for n in os.listdir(run)} == stamp
    assert not list(d.rglob('*.partial'))
    return {'run_folder': run.name, 'second_run_folder': run2.name, 'archives': new, 'validator': v,
            'marker': r['plan']['marker'], 'skipped': sorted(s['item'] for s in p['plan']['skipped']),
            'status': r['status']}


def _encrypt_geojson(z):
    raw = bytearray(z.read_bytes())
    at = 0
    while True:
        at = bytes(raw).find(b'PK', at)
        if at < 0:
            break
        sig = bytes(raw[at:at + 4])
        if sig == b'PK\x03\x04':
            n = struct.unpack_from('<H', raw, at + 26)[0]
            if bytes(raw[at + 30:at + 30 + n]).endswith(b'.geojson'):
                raw[at + 6] |= 1
        elif sig == b'PK\x01\x02':
            n = struct.unpack_from('<H', raw, at + 28)[0]
            if bytes(raw[at + 46:at + 46 + n]).endswith(b'.geojson'):
                raw[at + 8] |= 1
        at += 4
    z.write_bytes(bytes(raw))


def qa_package_corpus():
    """#979: each corrupt case its own code, no crash; OKS vs Ground passports compared."""
    d = OUT / 'corpus'
    d.mkdir()
    base = {'SM_X.fbx': FBX, 'SM_X.geojson': geojson()}
    for m, c in (('Diffuse', (120, 110, 100)), ('ERM', (0, 170, 0)), ('Normal', (128, 128, 255))):
        base['T_X_{}_1.1001.png'.format(m)] = png(c)
    got = {}
    for case, extra in (('traversal', {'../SM_X_Light.fbx': FBX}), ('nested', {'sub/SM_X_Light.fbx': FBX}),
                        ('not_png', {'T_X_Diffuse_1.1001.png': b'not a png'}), ('encrypted', {})):
        (d / case).mkdir()
        z = d / case / 'SM_X.zip'
        with zipfile.ZipFile(z, 'w') as f:
            for n, data in dict(base, **extra).items():
                f.writestr(n, data)
        if case == 'encrypted':
            _encrypt_geojson(z)
        r = agr.edits_080('qa.package', 'preview', options={'path': str(z), 'scene': False})
        (table,) = r['plan']['reports']
        got[case] = sorted(c for s in table['stages'] for c in s.get('codes', []) if c.startswith(('zip', 'png')))
    assert got == {'traversal': ['zip_traversal'], 'nested': ['zip_nested'], 'not_png': ['png_not_png'],
                   'encrypted': ['zip_encrypted']}, got
    pair = OUT / 'pair'
    pair.mkdir()
    for stem, dev in (('SM_X', 'A'), ('SM_X_Ground', 'B')):
        with zipfile.ZipFile(pair / (stem + '.zip'), 'w') as f:
            f.writestr(stem + '.fbx', FBX)
            f.writestr(stem + '.geojson', json.dumps({'type': 'FeatureCollection', 'features': [
                {'type': 'ObjectFeature', 'properties': {'address': 'X', 'developer': dev}}]}).encode())
    r = agr.edits_080('qa.package', 'preview', options={'path': str(pair), 'scene': False})
    cross = {o['name']: [f['code'] for f in o['findings'] if f['code'].startswith('geojson')] for o in r['objects']}
    assert cross == {'SM_X.zip': ['geojson_cross'], 'SM_X_Ground.zip': ['geojson_cross']}, cross
    return {'codes': got, 'cross': cross}


CLEAN_UDP = 'AGR_EXPORT_PATH = C:/x/0101_A_01.fbx\r\nfoo = bar\r\nMapChannel:1 = UV\r\n'
KEYS_FN = '''fn agrE3Keys b m = (
    with animate on (
        for t in #(0, 10, 20, 30, 40, 50, 60) do at time t (b.pos.x = 5000 + t; b.pos.y = 5000 - t)
        at time 0 m.opacity = 100
        at time 50 m.opacity = 80
    )
    ok
)'''


def cleanup_subject():
    """Editable Poly with a base CA, UDP (AGR_EXPORT_PATH, foo), vertex colour and 14 node + 2 material keys."""
    rt.units.SystemType = rt.Name('meters')
    b = rt.Box(name='SM_A_001_Main', length=2, width=2, height=2, pos=rt.Point3(5000, 5000, 0), mapcoords=True)
    rt.convertToPoly(b)
    rt.polyop.setMapSupport(b, 0, True)
    ca = rt.execute('attributes agrE3Data (parameters main (note type:#string default:"x"))')
    rt.custAttributes.add(b.baseObject, ca)
    m = rt.Standardmaterial(name='M_A_001_Main_1')
    b.material = m
    rt.setUserPropBuffer(b, CLEAN_UDP)
    rt.execute(KEYS_FN)(b, m)
    return b


def export_cleanup():
    b = cleanup_subject()
    facts0 = agr._cleanup_facts(b)
    assert 0 in facts0['vertex_channels'] and facts0['keys'] == 16, facts0  # 14 node + 2 material
    before = (agr.snapshot([b]), facts0, str(rt.getUserPropBuffer(b)))
    out = {'original_facts': facts0}
    for label, opts in (('default', None), ('opt_in', {'channels': True, 'keys': True})):
        p = agr.cleanup_preview([b], opts)
        copies, after = agr.cleanup_apply([b], p)
        (c,) = copies
        facts = agr._cleanup_facts(c)
        udp = str(rt.getUserPropBuffer(c))
        out[label] = {'actions': sorted(a['action'] for a in p['plan']['objects'][0]['actions']),
                      'copy_facts': facts, 'copy_udp': udp, 'after': after['status']}
        assert 'AGR_EXPORT_PATH = C:/x/0101_A_01.fbx' in udp and 'foo' not in udp, udp
        if label == 'default':
            assert facts == facts0, (facts, facts0)
        else:
            assert facts == {'vertex_channels': [], 'keys': 0}, facts
        rt.delete(c)
        assert (agr.snapshot([b]), agr._cleanup_facts(b), str(rt.getUserPropBuffer(b))) == before, 'original changed'
    rt.delete(b)
    return out


def ground_scene(tex):
    rt.units.SystemType = rt.Name('meters')
    x0, y0, z0 = 12345.678, -6789.012, 150.0
    mats = {}

    def material(kind):
        if kind not in mats:
            m = rt.Standardmaterial(name='M_X_' + kind + '_1')
            if kind.endswith('Glass'):
                m.opacity = 50
            else:
                m.diffuseMap = rt.Bitmaptexture(filename=str(tex))
            mats[kind] = m
        return mats[kind]
    nodes = []
    for i, (name, kind) in enumerate((('SM_X_GroundGlass', 'GroundGlass'), ('SM_X_Ground', 'Ground'),
                                      ('SM_X_GroundEl', 'GroundEl'), ('SM_X_GroundElGlass', 'GroundElGlass'),
                                      ('SM_X_Flora', 'Flora'), ('SM_X_001_Main', '001_Main'))):
        b = rt.Box(name=name, length=4, width=4, height=2, pos=rt.Point3(x0 + 10 * i, y0, z0))
        rt.convertToPoly(b)  # quads: the exporter must triangulate
        b.material = material(kind)
        nodes.append(b)
    helper = rt.Sphere(name='Smoke_908D_Selected', radius=1, pos=rt.Point3(x0, y0 + 50, z0))
    return nodes, helper


def export_ground_fbx():
    d = OUT / 'ground'
    d.mkdir()
    tex = OUT / 'T_X_Ground_d_1.png'
    tex.write_bytes(png((90, 120, 80)))
    nodes, helper = ground_scene(tex)
    emax = agr._load_core('edit_max.py', 'agr_tools_edit_max')
    before = emax.snapshot(nodes)
    opts = {'folder': str(d), 'code': '0123', 'scene': False}
    p1 = agr.edits_080('export.ground_fbx', 'preview', nodes=nodes, options=opts)
    p2 = agr.edits_080('export.ground_fbx', 'preview', nodes=list(reversed(nodes)), options=opts)
    assert p1 == p2, 'plan depends on node order'
    files = {f['name']: f['nodes'] for f in p1['plan']['files']}
    assert files == {'0123_X_Ground.fbx': sorted(['SM_X_GroundGlass', 'SM_X_Ground', 'SM_X_GroundEl',
                                                  'SM_X_GroundElGlass', 'SM_X_Flora']),
                     '0123_X_01.fbx': ['SM_X_001_Main']}, files
    assert p1['status'] == 'pass', p1['objects']
    rt.select(helper)
    r = agr.edits_080('export.ground_fbx', 'apply', p1, nodes=nodes)
    assert sorted(os.listdir(d)) == ['0123_X_01.fbx', '0123_X_Ground.fbx'], os.listdir(d)
    assert [str(n.name) for n in rt.selection] == ['Smoke_908D_Selected'], [str(n.name) for n in rt.selection]
    assert emax.snapshot(nodes) == before, 'working objects changed'
    v = {t['file']: {s['id']: s['status'] for s in t['stages'] if s['id'] in ('V001', 'V002', 'V012')}
         for t in r['plan']['reports']}
    assert all(x['V002'] != 'fail' for x in v.values()), v
    stamp = {n: sha(d / n) for n in os.listdir(d)}
    p3 = agr.edits_080('export.ground_fbx', 'preview', nodes=nodes, options=opts)
    assert p3['plan']['done'] == [] and len(p3['plan']['skipped']) == 2, p3['plan']
    r3 = agr.edits_080('export.ground_fbx', 'apply', p3, nodes=nodes)
    assert r3['plan']['done'] == [] and {n: sha(d / n) for n in os.listdir(d)} == stamp
    out = OUT / 'readback_inputs'
    out.mkdir()
    for n in stamp:
        (out / n).write_bytes((d / n).read_bytes())
    return {'files': files, 'done': r['plan']['done'], 'status': r['status'], 'validator': v,
            'sha256': stamp, 'second_run_done': r3['plan']['done']}


PROPS = {'address': 'г. Москва, ул. Тестовая, д. 1', 'okrug': 'ЦАО', 'rajon': 'Арбат', 'name': 'Жилой дом',
         'developer': 'ООО Застройщик', 'designer': 'ООО Проектировщик', 'cadNum': '77:01:0001001:1',
         'FNO_code': '010 004', 'FNO_name': 'Общежитие', 'ZU_area': 1200.5, 'h_relief': 150.0, 'h_otn': 45.0,
         'h_abs': 195.0, 's_obsh': 9000.0, 's_naz': 8000.0, 's_podz': 1000.0, 'spp_gns': 9500.0, 'act_AGR': '',
         'other': ''}


def export_geojson_write():
    """The point comes only from runtime.edits_080('export.pivot_place', 'preview'). While branch A is not in main
    that row answers not_implemented; then (and only then) a stand-in with A's preview shape is used and recorded."""
    import base64
    d = OUT / 'geojson'
    d.mkdir()
    real = agr.edits_080
    used = {}

    def edits(tool, mode, preview=None, nodes=None, options=None):
        r = real(tool, mode, preview, nodes, options)
        if tool == 'export.pivot_place' and r['status'] == 'not_implemented':
            lo, hi = rt.Point3(1e30, 1e30, 1e30), rt.Point3(-1e30, -1e30, -1e30)
            for n in nodes:
                lo, hi = rt.Point3(min(lo.x, n.min.x), min(lo.y, n.min.y), 0), rt.Point3(max(hi.x, n.max.x), max(hi.y, n.max.y), 0)
            used['pivot'] = 'stand-in: export.pivot_place not_implemented (branch A not in main)'
            return {'schema': 1, 'tool': tool, 'status': 'pass', 'objects': [],
                    'plan': {'mode': 'preview', 'pivot_value': [(lo.x + hi.x) / 2, (lo.y + hi.y) / 2, 150.0],
                             'floor': {'z': '150.0000', 'source': 'explicit'}}}
        used.setdefault('pivot', 'branch A export.pivot_place preview')
        return r
    agr.edits_080 = edits
    try:
        rt.units.SystemType = rt.Name('meters')
        main = rt.Box(name='SM_X_Main', length=10, width=20, height=30, pos=rt.Point3(12345.678, -6789.012, 150.0))
        glass = rt.Box(name='SM_X_MainGlass', length=1, width=20, height=30, pos=rt.Point3(12345.678, -6783.0, 150.0))
        gm = rt.Standardmaterial(name='M_X_MainGlass_1')
        gm.diffuse, gm.opacity, gm.glossiness = rt.color(200, 220, 255), 50, 90
        glass.material = gm
        bm = rt.Bitmap(256, 256, color=rt.color(90, 120, 80))
        jpg = OUT / 'preview_256.jpg'
        bm.filename = str(jpg)
        rt.save(bm)
        rt.close(bm)
        opts = {'folder': str(d), 'image': str(jpg), 'properties': PROPS, 'pivot': {'floor_z': '150.000'}}
        rt.select(main)
        p = agr.edits_080('export.geojson_write', 'preview', nodes=[main, glass], options=opts)
        assert p['status'] == 'pass' and p['plan']['done'] == ['SM_X.geojson'], p
        r = agr.edits_080('export.geojson_write', 'apply', p, nodes=[main, glass])
        assert r['plan']['done'] == ['SM_X.geojson'] and r['status'] == 'pass', r['objects']
        doc = json.loads((d / 'SM_X.geojson').read_text(encoding='utf-8'))
        feat = doc['features'][0]
        assert base64.b64decode(feat['properties']['imageBase64'], validate=True) == jpg.read_bytes()
        assert list(feat['Glasses'][0]) == ['M_X_MainGlass_1'], feat['Glasses']
        assert [str(n.name) for n in rt.selection] == ['SM_X_Main']
        stamp = sha(d / 'SM_X.geojson')
        p2 = agr.edits_080('export.geojson_write', 'preview', nodes=[main, glass], options=opts)
        r2 = agr.edits_080('export.geojson_write', 'apply', p2, nodes=[main, glass])
        assert r2['plan']['done'] == [] and sha(d / 'SM_X.geojson') == stamp and os.listdir(d) == ['SM_X.geojson']
        return {'pivot': used['pivot'], 'coordinates': feat['geometry']['coordinates'],
                'check': {f['name']: f['status'] for f in r['plan']['check']}, 'second_run_done': r2['plan']['done'],
                'glasses': feat['Glasses']}
    finally:
        agr.edits_080 = real


for name, fn in (('qa_package', qa_package), ('qa_package_corpus', qa_package_corpus), ('export_zip', export_zip),
                 ('export_cleanup', export_cleanup), ('export_ground_fbx', export_ground_fbx),
                 ('export_geojson_write', export_geojson_write)):
    check(name, fn)
summary['scene_saved'] = bool(str(rt.maxFileName))
(OUT / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding='utf-8')
print('AGR_908D_SUMMARY ' + json.dumps(summary, ensure_ascii=True)[:3000])
assert not summary['errors'] and not summary['scene_saved'], sorted(summary['errors'])
