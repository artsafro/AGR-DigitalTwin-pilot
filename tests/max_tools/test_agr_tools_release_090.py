"""new-case: release branch R of AGR Tools 0.9.0 (#979): the 0.2 button atlas.npm (`runtime.atlas_preview` /
`atlas_apply`) on the npm profile of branch B — atlas shrunk to its content at the same texel (Ground 35 px/m),
diffuse written as 24-bit RGB PNG by the stdlib writer and the opacity as a separate 8-bit grey PNG, with a header
readback that fails closed.

RED on 0.8.x / main before R: atlas_preview packed with the 0.2 contract (profile None: always the AGR_ATLAS_SIZE
square, 2048), and _bind_atlas saved a Max bitmap with `pngio.setAlpha true` (RGBA, colour type 6) — branch B's
CHANGELOG: «Кнопка 0.2 (runtime.atlas_apply) пока пишет PNG через Max». Plain pytest with a fake pymxs runtime.
"""
import importlib.util
import os
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / 'adapters/max/agr_tools'


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


class _Tex:
    def __init__(self):
        self.name = ''
        self.filename = ''


class _Mat:
    def __init__(self):
        self.diffuse = None
        self.opacity = None
        self.diffuseMap = None
        self.opacityMap = None


class _Node:
    def __init__(self, name):
        self.name = name


def _fake_rt(tmp_path):
    return types.SimpleNamespace(
        Bitmaptexture=_Tex, color=lambda *c: tuple(c), getHandleByAnim=lambda n: 7,
        getDir=lambda what: str(tmp_path), name=lambda s: s)


@pytest.fixture
def rt_mod(monkeypatch, tmp_path):
    mod = _load(PKG / 'runtime.py', 'agr_tools_runtime_release_090')
    fake = _fake_rt(tmp_path)
    monkeypatch.setattr(mod, '_rt', lambda: fake)
    monkeypatch.setenv('AGR_TEST_OUTPUT', str(tmp_path / 'out'))
    return mod


# 4 x 3 m quad, UV island inside tile 1001
QUAD = {'vertices': [(0, 0, 0), (4, 0, 0), (4, 3, 0), (0, 3, 0)],
        'uvs': [(0.1, 0.2), (0.8, 0.2), (0.8, 0.7), (0.1, 0.7)],
        'faces': [[0, 1, 2], [0, 2, 3]], 'face_uvs': [[0, 1, 2], [0, 2, 3]], 'ids': [1, 1]}


def _texture_spec(alpha=None):
    rgb = [[(255, 0, 0)] * 4 + [(0, 0, 255)] * 4 for _ in range(8)]
    spec = {'dissolve': 1.0, 'rgb': rgb}
    if alpha is not None:
        spec['alpha'] = alpha
    return spec


def _wire(mod, monkeypatch, spec, mode='ground'):
    node = _Node('SM_Atlas_Main')
    mat = _Mat()
    monkeypatch.setattr(mod, '_targets', lambda nodes: [node])
    monkeypatch.setattr(mod, '_read_channel', lambda n: QUAD)
    monkeypatch.setattr(mod, '_material_names', lambda n, ids: ['Wall'] * len(ids))
    monkeypatch.setattr(mod, '_atlas_settings', lambda n: (mode, 2048))
    monkeypatch.setattr(mod, '_atlas_materials', lambda n: {'Wall': spec})
    monkeypatch.setattr(mod, '_unit_m', lambda: 1.0)
    monkeypatch.setattr(mod, '_submaterials', lambda n: {'Wall': mat})
    monkeypatch.setattr(mod, '_bitmap_texture', lambda t: isinstance(t, _Tex))
    monkeypatch.setattr(mod, '_require_neutral_bitmap_coordinates', lambda *a: None)
    return node, mat


def test_atlas_preview_packs_on_the_npm_profile_and_shrinks_to_content(rt_mod, monkeypatch):
    _wire(rt_mod, monkeypatch, _texture_spec())
    prev = rt_mod.atlas_preview(None)
    atlas = prev['report']['plan']['atlas']  # RED: no 'atlas' block, size always 2048
    assert atlas['profile'] == 'npm' == rt_mod.ATLAS_PROFILE
    assert atlas['sizes'] == [prev['images'][0]['size']] and atlas['sizes'][0] < 2048
    assert atlas['sizes'][0] in (256, 512, 1024)
    assert prev['plans'][0]['size'] == atlas['sizes'][0]
    assert abs(atlas['texel_px_per_m']['Wall'] - 35.0) <= 0.1  # Ground 35 ± 0.1 px/m (lab / branch B)
    for u, v in prev['plans'][0]['uvs']:
        assert 0.0 <= u <= 1.0 and 0.0 <= v <= 1.0


def _png(path):
    from importlib import import_module  # noqa: F401
    checks = _load(PKG / 'checks_core.py', 'agr_tools_checks_release_090')
    return checks.png_info(Path(path).read_bytes())


def test_bind_atlas_writes_24bit_diffuse_and_a_separate_grey_opacity(rt_mod, monkeypatch):
    alpha = [[0] * 4 + [255] * 4 for _ in range(8)]
    node, mat = _wire(rt_mod, monkeypatch, _texture_spec(alpha), mode='oks')
    prev = rt_mod.atlas_preview(None)
    image = prev['images'][0]
    rt_mod._bind_atlas(node, image)
    size = image['size']
    assert _png(mat.diffuseMap.filename) == (size, size, 8, 2, False)  # RED: RGBA colour type 6 via Max save
    assert _png(mat.opacityMap.filename) == (size, size, 8, 0, False)
    assert mat.diffuseMap.filename != mat.opacityMap.filename
    files = rt_mod._atlas_file_readback(node, image)
    assert files == {'diffuseMap': {'size': size, 'bit_depth': 8, 'color_type': 2},
                     'opacityMap': {'size': size, 'bit_depth': 8, 'color_type': 0}}


def test_atlas_readback_fails_closed_on_an_rgba_diffuse(rt_mod, monkeypatch, tmp_path):
    node, mat = _wire(rt_mod, monkeypatch, _texture_spec())
    prev = rt_mod.atlas_preview(None)
    image = prev['images'][0]
    rt_mod._bind_atlas(node, image)
    assert mat.opacityMap is None  # no alpha in the source: no opacity atlas
    tq = _load(PKG / 'texqa_core.py', 'agr_tools_texqa_release_090')
    size = image['size']
    rgba = tmp_path / 'rgba.png'
    rgba.write_bytes(tq.write_png(size, size, bytes(size * size * 4), 4))
    mat.diffuseMap.filename = str(rgba)
    with pytest.raises(RuntimeError, match='colour type 6'):
        rt_mod._atlas_file_readback(node, image)


def test_publish_png_never_overwrites(rt_mod, tmp_path):
    tex = rt_mod._publish_png(b'\x89PNG-test', 'AGR_atlas_diffuse')
    path = Path(tex.filename)
    assert path.parent == tmp_path / 'out' / 'atlases' and path.read_bytes() == b'\x89PNG-test'
    with pytest.raises(FileExistsError):
        with open(path, 'xb'):
            pass
    assert os.path.basename(str(path)).startswith('AGR_atlas_diffuse-')


# ---- polygon station 0.2.2 (atlas.npm on the npm profile, scene atlas_npm) ---------------------------------------
def _run_polygon():
    sys.path.insert(0, str(ROOT / 'test-polygon'))
    return _load(ROOT / 'test-polygon' / 'run_polygon.py', 'agr_run_polygon_release_090')


def _apply_report(diffuse_ct=2, opacity_ct=0, texel=35.02, profile='npm'):
    return {'status': 'pass', 'objects': [], 'plan': {'tiles': [1001], 'cells': {}, 'dropped': [], 'atlas': {
        'profile': profile, 'sizes': [256], 'texel_px_per_m': {'M_Polygon_AtlasTex_Main_1': texel},
        'files': [{'diffuseMap': {'size': 256, 'bit_depth': 8, 'color_type': diffuse_ct},
                   'opacityMap': {'size': 256, 'bit_depth': 8, 'color_type': opacity_ct}}]}}}


def test_station_022_expects_the_npm_apply_on_the_textured_scene():
    import json
    doc = json.loads((ROOT / 'test-polygon/expected/atlas.npm.json').read_text(encoding='utf-8'))
    check = doc['apply_atlas']
    assert check['scene'] == 'atlas_npm' and check['profile'] == 'npm' and check['texel_px_per_m'] == 35.0
    assert check['files'] == {'diffuseMap': {'bit_depth': 8, 'color_type': 2},
                              'opacityMap': {'bit_depth': 8, 'color_type': 0}}
    tex = [o for o in doc['objects'] if o['scene'] == 'atlas_npm']
    assert [(o['name'], o['expect'], o['codes']) for o in tex] == [('SM_Polygon_AtlasTex_Main', 'fail', ['atlas_cell'])]


@pytest.mark.parametrize('kw,word', [({}, ''), ({'diffuse_ct': 6}, 'diffuseMap'), ({'opacity_ct': 4}, 'opacityMap'),
                                     ({'texel': 128.0}, 'texel'), ({'profile': None}, 'profile')])
def test_apply_atlas_problem_names_each_difference(kw, word):
    rp = _run_polygon()
    doc = rp.core.load_expected('atlas.npm')
    got = rp.apply_atlas_problem(doc['apply_atlas'], _apply_report(**kw))
    assert (got == '') if not word else (word in got)
    assert 'plan.atlas' in rp.apply_atlas_problem(doc['apply_atlas'], {'status': 'pass', 'plan': {}})


def test_compare_actual_counts_a_24bit_violation_on_station_022():
    rp = _run_polygon()
    runs = [{'button': 'atlas.npm', 'scene': 'atlas_npm', 'tool': 'atlas_apply', 'names': ['SM_Polygon_AtlasTex_Main'],
             'report': _apply_report(diffuse_ct=6), 'apply_expected': 'pass', 'apply_status': 'pass'}]
    got = [m for m in rp.compare_actual({'schema': 1, 'runs': runs})
           if m['button'] == 'atlas.npm' and m['scene'] == 'atlas_npm' and m['kind'] == 'apply']
    assert len(got) == 1 and 'colour' not in got[0]['detail'] and 'diffuseMap' in got[0]['detail']
    runs[0]['report'] = _apply_report()
    assert not [m for m in rp.compare_actual({'schema': 1, 'runs': runs})
                if m['button'] == 'atlas.npm' and m['scene'] == 'atlas_npm' and m['kind'] == 'apply']
