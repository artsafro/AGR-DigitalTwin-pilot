"""new-case: qa.zero_area and scene.census rework (#979, branch E3), plain pytest, no pymxs.

Team scripts (idea only, no code, #853), audit T04, all measured in Max 2024 or Python:
- FindThinFacesEditMesh (3).ms sha256 724206451d34d47e1bbc4b3b32890e5bf926b4d506805e4910ba9a4fe0104a39: acos in degrees
  against a radian threshold (0.087 deg instead of 5 deg), a face with a zero-length edge skipped;
- fbx_polygon_count.py sha256 9b4136621c4417d24fa1069adb06edcbe22585612e7ddb52f26889158a41441d: geometries by index
  only (no object names), ASCII FBX refused;
- scene_load_report.ms a9b76b4f...: polygons and triangles mixed; Optimise_info.ms b6725902... / _2 967f369d...:
  maps > 4096 on BOTH sides only (6000x3000 missed), crash on a missing map; agr_inspect_max.ms ea79dfc0...:
  instance pair counted twice, ANSI output (Cyrillic lost).
Each source model runs as a strict xfail (RED); suite_core / export_core are GREEN.
"""
import importlib.util
import json
import math
import struct
import sys
import zlib
from io import BytesIO
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / 'adapters/max/agr_tools'


def _load(name, mod):
    spec = importlib.util.spec_from_file_location(mod, PKG / name)
    m = importlib.util.module_from_spec(spec)
    sys.modules[mod] = m
    spec.loader.exec_module(m)
    return m


checks = _load('checks_core.py', 'agr_tools_checks_core')
core = _load('suite_core.py', 'agr_tools_suite_core_t9')
ex = _load('export_core.py', 'agr_tools_export_core_t9')
SRC = pytest.param('source', marks=pytest.mark.xfail(strict=True, reason='source behaviour (team-scripts audit T04)'))


def tri_with_angle(deg, size=1.0):
    """A triangle whose smallest angle is `deg` degrees (isosceles, apex angle `deg`)."""
    half = math.radians(deg) / 2.0
    return [(0.0, 0.0, 0.0), (size * math.cos(half), size * math.sin(half), 0.0),
            (size * math.cos(half), -size * math.sin(half), 0.0)]


def row(key, verts, tris, name=None, **kw):
    r = {'key': key, 'name': name or 'SM_A_{:03d}_Main'.format(key), 'superclass': 'geometry',
         'mesh': {'verts': verts, 'tris': tris}}
    r.update(kw)
    return r


ANGLES = (1.0, 3.0, 0.048, 45.0, 7.0)


# ---- qa.zero_area: sliver_face ----------------------------------------------------------------------------------
def find_thin_faces(verts, threshold_deg=5.0):
    """FindThinFacesEditMesh: acos gives DEGREES, the threshold is converted to radians; a>0/b>0/c>0 guard."""
    a, b, c = (math.dist(verts[1], verts[2]), math.dist(verts[0], verts[2]), math.dist(verts[0], verts[1]))
    if not (a > 0 and b > 0 and c > 0):
        return False
    angle = math.degrees(math.acos(max(-1.0, min(1.0, (b * b + c * c - a * a) / (2 * b * c)))))
    return min(angle, 180.0) < math.radians(threshold_deg)


def core_thin(verts, threshold_deg=5.0):
    f, _, _ = core.zero_area([row(1, verts, [(0, 1, 2)])], sliver_angle_deg=threshold_deg)
    return any(code in ('sliver_face', 'zero_area_face') for code, _d, _i in f.get(1, []))


@pytest.mark.parametrize('impl', [SRC, 'core'])
def test_sliver_threshold_is_degrees(impl):
    """1, 3 and 0.048 deg are below 5 deg; 45 and 7 deg are not (FindThinFaces flagged only 0.048)."""
    thin = find_thin_faces if impl == 'source' else core_thin
    assert [a for a in ANGLES if thin(tri_with_angle(a))] == [1.0, 3.0, 0.048]


@pytest.mark.parametrize('impl', [SRC, 'core'])
def test_face_with_a_zero_length_edge_is_found(impl):
    verts = [(0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (1.0, 0.0, 0.0)]
    assert (find_thin_faces if impl == 'source' else core_thin)(verts)


def test_sliver_is_advisory_and_separate_from_zero_area():
    verts = tri_with_angle(1.0) + [(5.0, 0.0, 0.0), (5.0, 0.0, 0.0), (6.0, 0.0, 0.0)]
    f, _, summary = core.zero_area([row(1, verts, [(0, 1, 2), (3, 4, 5)])], sliver_angle_deg=5.0)
    got = {c: ids for c, _d, ids in f[1]}
    assert got['sliver_face'] == (1,) and got['zero_area_face'] == (2,)
    assert summary['advisory'] == ['sliver_face'] and summary['sliver_angle_deg'] == 5.0
    # the angle is optional: by default only the 0.2 mm altitude rule runs (a 1 deg, 1 m triangle passes)
    assert 'sliver_face' not in [c for c, _d, _i in core.zero_area([row(1, verts, [(0, 1, 2)])])[0].get(1, [])]
    assert core.SLIVER_ANGLE_DEG is None and core.SLIVER_HEIGHT_M == 0.0002
    assert 'рекомендация' in next(d for c, d, _i in f[1] if c == 'sliver_face')
    rep = core.report('zero_area', [row(1, verts, [(0, 1, 2), (3, 4, 5)])], f, [], summary)
    assert rep['status'] == 'fail' and 'sliver_face' in [x['code'] for x in rep['objects'][0]['findings']]


def test_altitude_below_0_2_mm_is_a_sliver_even_with_wide_angles():
    """A 1 mm x 0.1 mm right triangle: smallest angle 5.7 deg (not thin by angle) but altitude < 0.2 mm."""
    verts = [(0.0, 0.0, 0.0), (0.001, 0.0, 0.0), (0.0, 0.0001, 0.0)]
    small, height, is_thin = core.sliver(*verts)
    assert small > 5.0 and height < core.SLIVER_HEIGHT_M and is_thin
    big = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)]
    assert core.sliver(*big)[2] is False


def test_preflight_ignores_the_advisory_code():
    def full(key, verts, tris):
        return {'key': key, 'name': 'SM_A_001_Main', 'fbx': 'C:/x/0101_A_01.fbx', 'superclass': 'geometry',
                'cls': 'Editable_Poly', 'faces': len(tris), 'verts': len(verts), 'materials': [],
                'parent': None, 'children': 0, 'group': False, 'animated': False, 'modifiers': [], 'layer': '0',
                'scale': (1.0, 1.0, 1.0), 'rotation': (0.0, 0.0, 0.0, 1.0), 'mirror': False,
                'bbox': ((0, 0, 0), (1, 1, 0)), 'instances': 1, 'zero_m': 0.0, 'roof_set': False,
                'mesh': {'verts': verts, 'tris': tris}}
    thin = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.5, 0.0001, 0.0)]  # altitude 0.1 mm
    f, _, _ = core.zero_area([full(1, thin, [(0, 1, 2)])])
    assert [c for c, _d, _i in f[1]] == ['sliver_face']
    audit = sys.modules.get('agr_tools_audit_t9')
    if audit is None:
        sys.path.insert(0, str(ROOT / 'src'))
        from twinqa.geometry import ucx_audit as audit
        sys.path.pop(0)
    scene = {'unit_type': 'meters', 'unit_scale': 1.0, 'file_in_gamma': 1.0, 'file_out_gamma': 1.0,
             'path': 'C:/s.max'}
    pf, _, summary = core.preflight([full(1, thin, [(0, 1, 2)])], audit, scene)
    assert not any(c == 'sliver_face' for c, _d, _i in pf.get(1, []))
    assert 'sliver_face' not in core.CODES['preflight']


# ---- qa.zero_area: FBX cross-check after export (no Max) --------------------------------------------------------
def _prop(v):
    if isinstance(v, int):
        return b'L' + struct.pack('<q', v)
    raw = v.encode('latin-1')
    return b'S' + struct.pack('<I', len(raw)) + raw


def _array(code, values, compress=True):
    fmt = {'d': 'd', 'i': 'i'}[code]
    raw = struct.pack('<' + fmt * len(values), *values)
    blob = zlib.compress(raw) if compress else raw
    return code.encode() + struct.pack('<III', len(values), 1 if compress else 0, len(blob)) + blob


def _node(name, props=b'', nprops=0, children=(), at=0):
    head = 13 + len(name)
    kids, pos = b'', at + head + len(props)
    for c in children:
        blob = _node(*c, at=pos)
        kids += blob
        pos += len(blob)
    if children:
        kids += b'\x00' * 13
    end = at + head + len(props) + len(kids)
    return struct.pack('<III', end, nprops, len(props)) + bytes([len(name)]) + name.encode() + props + kids


def binary_fbx(meshes):
    """meshes: [(name, verts flat, polygon index with ~last)] -> binary FBX 7400 with Geometry/Model/Connections."""
    objects, links = [], []
    for i, (name, verts, index) in enumerate(meshes):
        gid, mid = 1000 + i, 2000 + i
        gprops = _prop(gid) + _prop('Geometry::' + name) + _prop('Mesh')
        objects.append(('Geometry', gprops, 3, [('Vertices', _array('d', verts), 1, ()),
                                                ('PolygonVertexIndex', _array('i', index, compress=False), 1, ())]))
        objects.append(('Model', _prop(mid) + _prop(name + '\x00\x01Model') + _prop('Mesh'), 3, ()))
        links.append(('C', _prop('OO') + _prop(gid) + _prop(mid), 3, ()))
        links.append(('C', _prop('OO') + _prop(mid) + b'L' + struct.pack('<q', 0), 3, ()))
    out = b'Kaydara FBX Binary  \x00\x1a\x00' + struct.pack('<I', 7400)
    for name, props, n, kids in (('Objects', b'', 0, objects), ('Connections', b'', 0, links)):
        out += _node(name, props, n, kids, at=len(out))
    return out + b'\x00' * 13


def ascii_fbx(meshes):
    lines = ['; FBX 7.4.0 project file', 'Objects:  {']
    conns = ['Connections:  {']
    for i, (name, verts, index) in enumerate(meshes):
        gid, mid = 1000 + i, 2000 + i
        lines += ['\tGeometry: {}, "Geometry::{}", "Mesh" {{'.format(gid, name),
                  '\t\tVertices: *{} {{'.format(len(verts)), '\t\t\ta: ' + ','.join(repr(float(v)) for v in verts),
                  '\t\t}', '\t\tPolygonVertexIndex: *{} {{'.format(len(index)),
                  '\t\t\ta: ' + ','.join(str(v) for v in index), '\t\t}', '\t}',
                  '\tModel: {}, "Model::{}", "Mesh" {{'.format(mid, name), '\t}']
        conns += ['\tC: "OO",{},{}'.format(gid, mid), '\tC: "OO",{},0'.format(mid)]
    return '\n'.join(lines + ['}'] + conns + ['}']).encode('utf-8')


GOOD = ('SM_A_001_Main', [0, 0, 0, 1, 0, 0, 0, 1, 0], [0, 1, ~2])
ZERO = ('SM_A_002_Main', [0, 0, 0, 1, 0, 0, 2, 0, 0, 0, 0, 1], [0, 1, ~2, 0, 1, 2, ~3])  # collinear tri + a quad


def fbx_polygon_count(data):
    """fbx_polygon_count.py: binary only ('not a binary FBX'), geometries reported by index, no names."""
    if not data.startswith(b'Kaydara FBX Binary'):
        raise ValueError('not a binary FBX')
    meshes = ex.fbx_meshes(data)
    return {'geometry_{}'.format(i): m for i, m in enumerate(meshes)}


def core_fbx(data):
    rows = core.fbx_rows(ex.fbx_meshes(data))
    f, _, _ = core.zero_area(rows)
    return {r['name']: [c for c, _d, _i in f.get(r['key'], [])] for r in rows}


@pytest.mark.parametrize('impl', [SRC, 'core'])
@pytest.mark.parametrize('writer', [binary_fbx, ascii_fbx])
def test_fbx_zero_area_by_object_name(impl, writer):
    data = writer([GOOD, ZERO])
    got = (fbx_polygon_count if impl == 'source' else core_fbx)(data)
    assert 'SM_A_002_Main' in got and 'zero_area_face' in got['SM_A_002_Main'] and got['SM_A_001_Main'] == []


def test_fbx_meshes_reads_names_vertices_and_polygons():
    (good, zero) = ex.fbx_meshes(binary_fbx([GOOD, ZERO]))
    assert good['name'] == 'SM_A_001_Main' and good['verts'] == [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)]
    assert zero['polygons'] == [[0, 1, 2], [0, 1, 2, 3]]
    assert ex.fbx_meshes(ascii_fbx([GOOD, ZERO])) == ex.fbx_meshes(binary_fbx([GOOD, ZERO]))
    with pytest.raises(ValueError):
        ex.fbx_meshes(b'garbage')


def test_fbx_cli_writes_a_report(tmp_path):
    import subprocess
    path = tmp_path / 'SM_A.fbx'
    path.write_bytes(binary_fbx([GOOD, ZERO]))
    proc = subprocess.run([sys.executable, str(ROOT / 'tools/qa/fbx_zero_area.py'), str(path)], capture_output=True)
    assert proc.returncode == 1, proc.stderr
    rep = json.loads(proc.stdout.decode('utf-8'))
    assert rep['tool'] == 'zero_area' and rep['status'] == 'fail'
    assert {o['name']: [f['code'] for f in o['findings']] for o in rep['objects']}['SM_A_002_Main'] == \
        ['zero_area_face']


# ---- scene.census ------------------------------------------------------------------------------------------------
def crow(key, name, faces=12, layer='0', instances=1, materials=None, bbox=((0, 0, 0), (1, 1, 1)), **kw):
    r = {'key': key, 'name': name, 'superclass': 'geometry', 'faces': faces, 'layer': layer,
         'instances': instances, 'materials': materials or [], 'bbox': bbox}
    r.update(kw)
    return r


def mat(name, maps=(), missing=(), sizes=None):
    return {'name': name, 'cls': 'Standardmaterial', 'maps': list(maps), 'missing': list(missing),
            'opacity': 1.0, 'sizes': dict(sizes or {})}


def test_census_triangles_by_layer_prefix_and_heaviest():
    rows = [crow(1, 'SM_A_001_Main', faces=150000, layer='OKS'), crow(2, 'SM_A_Ground', faces=20, layer='Ground'),
            crow(3, 'UCX_SM_A_001_Main_001', faces=12, layer='OKS'),
            {'key': 4, 'name': 'Camera001', 'superclass': 'camera', 'faces': 0, 'layer': '0', 'instances': 1,
             'materials': [], 'bbox': None}]
    _f, _d, s = core.census(rows)
    assert s['triangles'] == 150032 and s['triangles_by_layer'] == {'OKS': 150012, 'Ground': 20}
    assert s['triangles_by_prefix'] == {'SM': 150020, 'UCX': 12}
    assert s['heaviest'][0] == ['SM_A_001_Main', 150000] and s['heavy_meshes'] == ['SM_A_001_Main']


def optimise_info_large(sizes):
    """Optimise_info: width AND height > 4096."""
    return [p for p, (w, h) in sizes.items() if w > 4096 and h > 4096]


def core_large(sizes):
    _f, _d, s = core.census([crow(1, 'SM_A_001_Main', materials=[mat('M', list(sizes), (), sizes)])])
    return [m['path'] for m in s['large_maps']]


@pytest.mark.parametrize('impl', [SRC, 'core'])
def test_large_map_on_either_side(impl):
    sizes = {'a_6000x3000.png': (6000, 3000), 'b_8192.png': (8192, 8192), 'c_4096.png': (4096, 4096)}
    got = (optimise_info_large if impl == 'source' else core_large)(sizes)
    assert sorted(got) == ['a_6000x3000.png', 'b_8192.png']


def inspect_instance_groups(rows):
    """agr_inspect_max: every member of an instance group counted as a group."""
    return sum(1 for r in rows if r['instances'] > 1)


def core_instance_groups(rows):
    return core.census(rows)[2]['instance_groups']


@pytest.mark.parametrize('impl', [SRC, 'core'])
def test_one_instance_pair_is_one_group(impl):
    rows = [crow(1, 'SM_A_001_Main', instances=2, base_key=77), crow(2, 'SM_A_002_Main', instances=2, base_key=77),
            crow(3, 'SM_A_003_Main')]
    assert (inspect_instance_groups if impl == 'source' else core_instance_groups)(rows) == 1


def test_bbox_spans_all_objects_and_far_and_cyrillic_names():
    rows = [crow(1, 'SM_A_001_Main', bbox=((0, 0, 0), (1, 1, 1))),
            crow(2, 'SM_Дом_Main', bbox=((20000, 0, 0), (20001, 1, 1)))]
    _f, _d, s = core.census(rows, {'renderer': 'Scanline', 'scene_missing': []})
    assert s['bbox_m'] == [[0, 0, 0], [20001, 1, 1]]
    assert s['far_from_origin'] == ['SM_Дом_Main'] and s['cyrillic_names'] == ['SM_Дом_Main']
    assert s['renderer'] == 'Scanline'


def test_census_dump_is_utf8_with_cyrillic():
    rows = [crow(1, 'SM_Дом_Main')]
    f, d, s = core.census(rows)
    rep = core.report('census', rows, f, d, s)
    raw = core.census_dump(rep)
    assert 'SM_Дом_Main'.encode('utf-8') in raw and b'?' not in raw.replace(b'"?"', b'')
    assert json.loads(raw.decode('utf-8')) == rep


def usedmaps_only(rows):
    """0.7 census before #886/#979: only paths usedMaps returns; a Bitmaptexture with a missing file is dropped."""
    return {r['name'] for r in rows for m in r['materials'] if m['missing']}


def core_missing(rows):
    f, _d, _s = core.census(rows)
    return {r['name'] for r in rows if any(c == 'missing_map' for c, _x, _i in f.get(r['key'], []))}


@pytest.mark.parametrize('impl', [SRC, 'core'])
def test_missing_map_from_the_shared_enumerator(impl):
    """Polygon 0.7.1 known bug census-usedmaps-drops-missing-file: SM_Polygon_007_Main -> missing_map."""
    rows = [crow(1, 'SM_Polygon_007_Main', materials=[mat('M_Polygon_007_Main_1')],
                 extra_missing=['C:/x/test-polygon/missing/T_Polygon_007_Main_d_1.png']),
            crow(2, 'SM_Polygon_001_Main', materials=[mat('M', ['ok.png'])], extra_missing=[])]
    assert (usedmaps_only if impl == 'source' else core_missing)(rows) == {'SM_Polygon_007_Main'}


def test_missing_map_is_reported_once_and_scene_level_maps_listed():
    p = 'C:/x/missing.png'
    rows = [crow(1, 'SM_A_001_Main', materials=[mat('M', [p], [p])], extra_missing=[p])]
    f, _d, s = core.census(rows, {'renderer': None, 'scene_missing': ['C:/x/orphan.png']})
    assert [c for c, _x, _i in f[1]] == ['missing_map']
    assert s['missing_maps'] == ['C:/x/missing.png', 'C:/x/orphan.png'] and s['missing_maps_scene'] == ['C:/x/orphan.png']
    with pytest.raises(ValueError, match='unreadable map entry'):
        core.census([crow(1, 'SM_A_001_Main', extra_missing=[''])])


def _png_head(w, h):
    return b'\x89PNG\r\n\x1a\n' + struct.pack('>I', 13) + b'IHDR' + struct.pack('>II', w, h) + b'\x08\x02\x00\x00\x00'


def test_image_size_from_headers_never_raises():
    from PIL import Image
    b = BytesIO()
    Image.new('RGB', (6000, 3000)).save(b, 'JPEG')
    assert core.image_size(_png_head(6000, 3000)) == (6000, 3000)
    assert core.image_size(b.getvalue()[:65536]) == (6000, 3000)
    bmp = BytesIO()
    Image.new('RGB', (64, 32)).save(bmp, 'BMP')
    tga = BytesIO()
    Image.new('RGB', (128, 16)).save(tga, 'TGA')
    assert core.image_size(bmp.getvalue()) == (64, 32) and core.image_size(tga.getvalue()) == (128, 16)
    for junk in (b'', b'\x89PNG', b'\xff\xd8\xff', b'random bytes here'):
        assert core.image_size(junk) is None


def test_census_findings_are_still_only_missing_maps():
    """Everything new is summary (report only): heavy meshes, large maps, names are not findings."""
    rows = [crow(1, 'SM_Дом_Main', faces=200000, materials=[mat('M', ['big.png'], (), {'big.png': [8192, 8192]})],
                 bbox=((50000, 0, 0), (50001, 1, 1)))]
    f, _d, s = core.census(rows)
    assert f == {} and s['heavy_meshes'] and s['large_maps'] and s['cyrillic_names'] and s['far_from_origin']
