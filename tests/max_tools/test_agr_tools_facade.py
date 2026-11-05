"""new-case: AGR Tools 0.9 (#979) branch C: qa.facade_compare (facade_core.py, facade_max.py with a fake pymxs).

Acceptance of #979 §13: a synthetic facade with 6 vertical joints against a sheet with 6 -> pass, with 7 -> fail;
the renderer and the viewport settings are the same before and after (here: never touched — the model panel is a
rasterised mesh snapshot); the picture is a new file. Defect not to repeat: `apply_atlas_uv` swaps the renderer (T06).
Idea of the TEC26 scripts (jobs/TEC26-OKS/scripts/joint_count.py, compare_facades.py), rewritten on stdlib.
"""
import importlib.util
import struct
import sys
import types
import zlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / 'adapters/max/agr_tools'
FIX = Path(__file__).resolve().parent / 'fixtures_qa9'


def _load(name, alias):
    spec = importlib.util.spec_from_file_location(alias, PKG / name)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[alias] = mod
    spec.loader.exec_module(mod)
    return mod


ec = _load('edit_core.py', 'agr_tools_edit_core_facade_t')
fc = _load('facade_core.py', 'agr_tools_facade_core_t')
fm = _load('facade_max.py', 'agr_tools_facade_max_t')
BLUE = (70, 90, 200)


def panels(n=7, width=0.98, gap=0.02, h=3.0, y=0.0, seam=None):
    """A -y facade of n panels with `gap` between them (n-1 joints). seam: draw joints as dark strips, no gaps."""
    verts, faces = [], []
    x = 0.0
    for i in range(n):
        a, b = x, x + width
        k = len(verts)
        verts += [(a, y, 0.0), (b, y, 0.0), (b, y, h), (a, y, h)]
        faces += [(k, k + 1, k + 2), (k, k + 2, k + 3)]
        x = b + gap
    return verts, faces


def tris_of(vf, colour=BLUE):
    v, f = vf
    return [((v[a], v[b], v[c]), colour) for a, b, c in f]


def sheet(joints, px_per_m=50, width_m=6.98, height_m=3.0):
    """A drawn facade sheet: white paper, black outline, light fill, `joints` dark vertical lines."""
    W, H = int(width_m * px_per_m) + 40, int(height_m * px_per_m) + 40
    im = fc.Image(W, H, (255, 255, 255))
    x0, x1, y0, y1 = 20, 20 + int(width_m * px_per_m), 20, 20 + int(height_m * px_per_m)
    for yy in range(y0, y1):
        for xx in range(x0, x1):
            im.px[yy][xx] = (180, 190, 230)
        im.px[yy][x0] = im.px[yy][x1 - 1] = (0, 0, 0)
    for xx in range(x0, x1):
        im.px[y0][xx] = im.px[y1 - 1][xx] = (0, 0, 0)
    step = (x1 - x0) / (joints + 1)
    for k in range(1, joints + 1):
        xx = int(x0 + k * step)
        for yy in range(y0, y1):
            im.px[yy][xx] = (20, 20, 20)
    return im


def model(vf=None, px_per_m=100):
    return fc.rasterize(tris_of(vf or panels()), '-y', px_per_m)[0]


def test_acceptance_6_joints_vs_sheet_6_pass_and_7_fail():
    m = model()
    assert fc.count_joints(m)['joints'] == 6
    ok = fc.compare(fc.mask_background(sheet(6)), 50, {'vpm': m}, 100)
    bad = fc.compare(fc.mask_background(sheet(7)), 50, {'vpm': m}, 100)
    assert ok['ok'] and ok['sheet']['joints'] == 6
    assert not bad['ok'] and bad['reasons'] == ['VPM: швов 6 ≠ лист 7']


def test_joint_shown_as_dark_texture_strip_counts_too():
    v, f = panels(n=1, width=7.0)
    tex = fc.Image(700, 10, (180, 190, 230))
    for k in range(1, 7):
        for yy in range(10):
            tex.px[yy][k * 100] = (10, 10, 10)
    uvs = [((0, 0), (1, 0), (1, 1)), ((0, 0), (1, 1), (0, 1))]
    tris = [((v[a], v[b], v[c]), fc.texture_shader(tex, uv)) for (a, b, c), uv in zip(f, uvs)]
    assert fc.count_joints(fc.rasterize(tris, '-y', 100)[0])['joints'] == 6


def test_px_per_m_is_fixed_and_npm_panel_compared():
    img, view = fc.rasterize(tris_of(panels()), '-y', 100)
    assert view['size_px'] == [699, 301] and view['width_m'] == pytest.approx(6.98)
    npm = model(panels(n=6, width=1.15))
    c = fc.compare(fc.mask_background(sheet(6)), 50, {'vpm': model(), 'npm': npm}, 100)
    assert not c['ok'] and c['models']['npm']['joints'] == 5 and 'NPM' in c['reasons'][0]


def test_back_faces_culled_and_other_facades():
    v, f = panels()
    back = [(a, c, b) for a, b, c in f]
    with pytest.raises(ValueError, match='no face looks toward'):
        fc.rasterize(tris_of((v, back)), '-y', 100)
    assert fc.count_joints(fc.rasterize(tris_of((v, back)), '+y', 100)[0])['joints'] == 6
    with pytest.raises(ValueError, match='facade must be'):
        fc.rasterize(tris_of((v, f)), 'up', 100)
    with pytest.raises(ValueError, match='max_px'):
        fc.rasterize(tris_of((v, f)), '-y', 10000)


def test_image_formats_round_trip(tmp_path):
    s = sheet(6)
    png = fc.write_png(s)
    assert fc.read_png(png).px == s.px
    pgm = fc.write_pgm(s)
    back = fc.read_pnm(pgm)
    assert back.width == s.width and fc.count_joints(fc.mask_background(back))['joints'] == 6
    # BMP 24-bit bottom-up
    w, h = 3, 2
    rows = [[(10, 20, 30), (40, 50, 60), (70, 80, 90)], [(1, 2, 3), (4, 5, 6), (7, 8, 9)]]
    stride = (w * 3 + 3) // 4 * 4
    body = b''
    for r in reversed(rows):
        line = b''.join(bytes((p[2], p[1], p[0])) for p in r)
        body += line + b'\0' * (stride - len(line))
    hdr = b'BM' + struct.pack('<IHHI', 54 + len(body), 0, 0, 54) + struct.pack('<IiiHHIIiiII', 40, w, h, 1, 24, 0,
                                                                                len(body), 0, 0, 0, 0)
    bmp = fc.read_bmp(hdr + body)
    assert bmp.px == rows
    p = tmp_path / 'x.bmp'
    p.write_bytes(hdr + body)
    assert fc.read_image(str(p)).px == rows
    (tmp_path / 'x.jpg').write_bytes(b'\xff\xd8\xff')
    with pytest.raises(ValueError, match='unsupported image'):
        fc.read_image(str(tmp_path / 'x.jpg'))
    # PNG with a palette and Paeth filter rows decode
    raw = b'\x04' + bytes([0, 1, 0]) + b'\x00' + bytes([1, 0, 1])  # Paeth row -> 0, 1, 1
    chunk = lambda k, b: struct.pack('>I', len(b)) + k + b + struct.pack('>I', zlib.crc32(k + b) & 0xffffffff)
    pal = fc.read_png(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 3, 2, 8, 3, 0, 0, 0))
                      + chunk(b'PLTE', bytes([255, 0, 0, 0, 255, 0])) + chunk(b'IDAT', zlib.compress(raw))
                      + chunk(b'IEND', b''))
    assert pal.px[0] == [(255, 0, 0), (0, 255, 0), (0, 255, 0)] and pal.px[1][0] == (0, 255, 0)


def test_sheet_fixtures_for_the_polygon():
    for n in (6, 7):
        img = fc.mask_background(fc.read_image(str(FIX / 'facade_sheet_{}.pgm'.format(n))))
        assert fc.count_joints(img)['joints'] == n


def test_options_are_strict():
    with pytest.raises(ValueError, match='needs sheet'):
        fc.facade_options({})
    with pytest.raises(ValueError, match='sheet_px_per_m'):
        fc.facade_options({'sheet': 'a.png'})
    with pytest.raises(ValueError, match='unknown'):
        fc.facade_options({'sheet': 'a', 'sheet_px_per_m': 1, 'renderer': 'x'})
    with pytest.raises(ValueError, match='sheets'):
        fc.facade_options({'sheets': {'A': {'path': 'a'}}})
    o = fc.facade_options({'sheets': {'A': {'path': 'a', 'px_per_m': 50}}})
    assert o['sheets'] == {'A': {'path': 'a', 'px_per_m': 50}} and o['px_per_m'] == 100.0


# ---- glue with a fake pymxs: no renderer/viewport touched, new file only ---------------------------------
class _P:
    def __init__(self, x, y, z):
        self.x, self.y, self.z = x, y, z


class _C:
    def __init__(self, r, g, b):
        self.r, self.g, self.b = r, g, b


class _Mesh:
    def __init__(self, v, f):
        self.v, self.f = v, f
        self.numfaces = len(f)


class _Node:
    def __init__(self, handle, name, vf):
        self.handle, self.name, self.vf = handle, name, vf
        self.material = None
        self.wirecolor = _C(*BLUE)


class FakeMeshop:
    @staticmethod
    def getMapSupport(m, ch):
        return False


class FakeRT:
    undefined = None
    meshop = FakeMeshop()
    Multimaterial = 'Multimaterial'

    def __init__(self, nodes, unit='meters'):
        object.__setattr__(self, 'nodes', nodes)
        object.__setattr__(self, 'selection', list(nodes))
        object.__setattr__(self, 'units', types.SimpleNamespace(SystemType=unit, SystemScale=1.0))
        object.__setattr__(self, 'renderers', types.SimpleNamespace(current='Scanline'))

    def __setattr__(self, key, value):
        raise AssertionError('read-only button wrote rt.' + key)

    def isValidNode(self, n):
        return True

    def getHandleByAnim(self, n):
        return n.handle

    def getNodeByName(self, name):
        return next((n for n in self.nodes if n.name == name), None)

    def snapshotAsMesh(self, n):
        return _Mesh(*n.vf)

    def getFace(self, m, i):
        a, b, c = m.f[i - 1]
        return _P(a + 1, b + 1, c + 1)

    def getVert(self, m, i):
        return _P(*m.v[i - 1])

    def getFaceMatID(self, m, i):
        return 1

    def delete(self, m):
        pass

    def classOf(self, x):
        return 'Editable_Mesh'


@pytest.fixture
def fake(monkeypatch):
    def install(nodes, unit='meters'):
        rt = FakeRT(nodes, unit)
        mod = types.ModuleType('pymxs')
        mod.runtime = rt
        monkeypatch.setitem(sys.modules, 'pymxs', mod)
        return rt
    return install


def _ctx(options, out):
    emax = types.SimpleNamespace(snapshot=lambda nodes: [[n.handle, n.name] for n in nodes])
    agr = types.SimpleNamespace(reports_dir=lambda: str(out))
    return types.SimpleNamespace(agr=agr, core=fc, edit=ec, emax=emax, options=dict(options))


def _scaled(vf, k):
    v, f = vf
    return [(x * k, y * k, z * k) for x, y, z in v], f


def test_glue_pass_and_fail_new_files_renderer_untouched(fake, tmp_path):
    rt = fake([_Node(1, 'SM_Facade6_Main', panels()), _Node(2, 'SM_Facade6b_Main', panels(y=5))])
    opts = {'sheets': {'SM_Facade6_Main': {'path': str(FIX / 'facade_sheet_6.pgm'), 'px_per_m': 50},
                       'SM_Facade6b_Main': {'path': str(FIX / 'facade_sheet_7.pgm'), 'px_per_m': 50}}}
    r = fm.qa_facade_compare(_ctx(opts, tmp_path), 'preview', None, None)
    ec.check_preview('qa.facade_compare', r)
    assert [(o['name'], [f['code'] for f in o['findings']]) for o in r['objects']] == \
        [('SM_Facade6_Main', []), ('SM_Facade6b_Main', ['facade_joints'])]
    imgs = [Path(f['image']) for f in r['plan']['facades']]
    assert all(p.is_file() and p.read_bytes()[:8] == b'\x89PNG\r\n\x1a\n' for p in imgs)
    assert rt.renderers.current == 'Scanline' and r['plan']['renderer_used'] is False
    again = fm.qa_facade_compare(_ctx(opts, tmp_path), 'preview', None, None)
    assert [Path(f['image']).name for f in again['plan']['facades']] == ['facade_SM_Facade6_Main_v002.png',
                                                                         'facade_SM_Facade6b_Main_v002.png']
    assert all(p.is_file() for p in imgs)  # never overwritten


def test_glue_centimetre_scene_same_counts(fake, tmp_path):
    fake([_Node(1, 'SM_F_Main', _scaled(panels(), 100.0))], unit='centimeters')
    r = fm.qa_facade_compare(_ctx({'sheet': str(FIX / 'facade_sheet_6.pgm'), 'sheet_px_per_m': 50}, tmp_path),
                             'preview', None, None)
    assert r['status'] == 'pass' and r['plan']['facades'][0]['vpm'] == 6


def test_glue_refusals(fake, tmp_path):
    fake([])
    with pytest.raises(ValueError, match='select the VPM'):
        fm.qa_facade_compare(_ctx({'sheet': 'x.pgm', 'sheet_px_per_m': 50}, tmp_path), 'preview', None, None)
    with pytest.raises(ValueError, match='read-only'):
        fm.qa_facade_compare(_ctx({}, tmp_path), 'apply', None, {})
    fake([_Node(1, 'A', panels())])
    r = fm.qa_facade_compare(_ctx({'sheets': {'A': {'path': str(FIX / 'facade_sheet_6.pgm'), 'px_per_m': 50}}},
                                  tmp_path), 'preview', None, None)
    assert r['status'] == 'pass'
    fake([_Node(1, 'A', panels()), _Node(2, 'B', panels())])
    r = fm.qa_facade_compare(_ctx({'sheets': {'A': {'path': str(FIX / 'facade_sheet_6.pgm'), 'px_per_m': 50}}},
                                  tmp_path), 'preview', None, None)
    assert [s['item'] for s in r['plan']['skipped']] == ['B']
