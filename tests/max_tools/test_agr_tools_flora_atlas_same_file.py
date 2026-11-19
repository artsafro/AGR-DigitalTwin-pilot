"""new-case: atlas.flora accepts an opacity slot that points at the diffuse RGBA PNG itself (#1024, A101 Flora).

A101 FLORIO_221.max materials put the same RGBA PNG in diffuseMap and opacityMap (measured, AGR Lab job
20261106-020154-451ed182). atlas.flora answered `opacity_mismatch` ("both diffuse alpha and an opacity map") for
every species; with the same file it now uses the diffuse alpha (native: job 20261106-031446-91a1235d, 5 species ->
one 2048 atlas + `_o`, every face in the atlas). A different opacity file next to a diffuse alpha still fails.
"""
import importlib.util
import sys
import hashlib
from types import SimpleNamespace
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _glue():
    spec = importlib.util.spec_from_file_location('agr_tools_flora_atlas_max_same',
                                                  ROOT / 'adapters/max/agr_tools/flora_atlas_max.py')
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_same_file_normalises_case_separators_and_relative_parts(tmp_path):
    g = _glue()
    p = tmp_path / 'TextureFlora' / 'lipa_t1_h550_low.png'
    assert g._same_file(str(p), str(p).replace('\\', '/'))
    assert g._same_file(str(p), str(tmp_path / 'TextureFlora' / '..' / 'TextureFlora' / 'lipa_t1_h550_low.png'))
    assert g._same_file(str(p), str(p).upper()) == (str(p).upper() == str(p) or sys.platform == 'win32')
    assert not g._same_file(str(p), str(tmp_path / 'TextureFlora' / 'lipa_t1_h550_low_o.png'))


def test_mismatch_branch_still_present_for_a_different_opacity_file():
    text = (ROOT / 'adapters/max/agr_tools/flora_atlas_max.py').read_text(encoding='utf-8')
    same = text.index("_same_file(oinfo['path'], info['path'])")
    both = text.index("'both diffuse alpha and an opacity map'")
    assert same < both  # the same-file case is decided first; any other file keeps the refusal


def _core():
    spec = importlib.util.spec_from_file_location('agr_tools_atlas_core_same', ROOT / 'adapters/max/agr_tools/atlas_core.py')
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


class _Ctx(object):
    def __init__(self, options):
        self.options, self.core = options, _core()


def test_groundel_texel_option_none_only_for_npm_profile():
    import pytest
    g = _glue()
    assert g._groundel_options(_Ctx({'profile': 'npm'}), 'preview', None)['texel'] == 'ground'  # default unchanged
    assert g._groundel_options(_Ctx({'profile': 'npm', 'texel': 'none'}), 'preview', None)['texel'] == 'none'
    with pytest.raises(ValueError, match="needs profile 'npm'"):
        g._groundel_options(_Ctx({'texel': 'none'}), 'preview', None)
    with pytest.raises(ValueError, match="'ground' or 'none'"):
        g._groundel_options(_Ctx({'profile': 'npm', 'texel': 35}), 'preview', None)


@pytest.mark.parametrize('texel', [None, '', 'NONE', 0, 35, True, [], {}, float('nan'), float('inf')])
def test_groundel_invalid_texel_is_refused(texel):
    with pytest.raises(ValueError, match='options.texel'):
        _glue()._groundel_options(_Ctx({'profile': 'npm', 'texel': texel}), 'preview', None)


def test_texel_none_routes_to_the_oks_mode_of_pack():
    text = (ROOT / 'adapters/max/agr_tools/flora_atlas_max.py').read_text(encoding='utf-8')
    assert "mode='oks' if options.get('texel') == 'none' else 'ground'" in text


def _preview(monkeypatch, tmp_path, other_folder=False, px=None, channels=4):
    """Synthetic PNGs; only the Max scene boundary is replaced, not image IO or atlas planning."""
    g, core = _glue(), _core()
    spec = importlib.util.spec_from_file_location('edit_core_same', ROOT / 'adapters/max/agr_tools/edit_core.py')
    edit = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(edit)
    tq = core.texqa()
    source = tmp_path / 'diffuse' / 'tree.png'
    source.parent.mkdir()
    source.write_bytes(tq.write_png(2, 2, bytes(px or [10, 80, 20, 0, 10, 80, 20, 255] * 2), channels))
    opacity = source
    if other_folder:
        opacity = tmp_path / 'opacity' / 'tree.png'
        opacity.parent.mkdir()
        opacity.write_bytes(source.read_bytes())
    material = SimpleNamespace(name='Synthetic_tree')
    node = SimpleNamespace(name='Synthetic_flora', material=material, baseObject=object(), modifiers=[])
    helpers = SimpleNamespace(
        resolve=lambda p: str(Path(p).resolve()) if Path(p).is_file() else None,
        md5=lambda b: hashlib.md5(b).hexdigest(), target_nodes=lambda ns: ns,
        handle=lambda n: '1', sub_materials=lambda n: [(None, material)],
        material_maps=lambda m: [{'slot': 'diffuse', 'path': str(source)},
                                 {'slot': 'opacity', 'path': str(opacity)}])
    rt = SimpleNamespace(GeometryClass='geometry', superClassOf=lambda n: 'geometry',
                         getHandleByAnim=lambda n: 1, classOf=lambda n: 'Synthetic')
    ctx = SimpleNamespace(core=core, edit=edit, options={},
                          emax=SimpleNamespace(snapshot=lambda ns: [{}]),
                          agr=SimpleNamespace(_load_core=lambda *args: helpers))
    mesh = {'vertices': [(0, 0, 0), (1, 0, 0), (0, 1, 0)], 'faces': [[0, 1, 2]],
            'uvs': [(0, 0), (1, 0), (0, 1)], 'face_uvs': [[0, 1, 2]], 'ids': [101]}
    monkeypatch.setattr(g, '_rt', lambda: rt)
    monkeypatch.setattr(g, 'read_uv_mesh', lambda n: mesh)
    before = {p: p.read_bytes() for p in (source, opacity)}
    report = g.atlas_flora(ctx, 'preview', [node], None)
    assert all(p.read_bytes() == data for p, data in before.items())
    return report


def test_preview_rejects_different_files_with_identical_basename(monkeypatch, tmp_path):
    report = _preview(monkeypatch, tmp_path, other_folder=True)
    assert 'opacity_mismatch' in str(report)
    assert not report['plan']['done']


def test_preview_accepts_same_rgba_file_and_reports_one_face(monkeypatch, tmp_path):
    report = _preview(monkeypatch, tmp_path)
    assert 'opacity_mismatch' not in str(report)
    assert report['plan']['atlas']['opacity'] is True
    assert report['plan']['done'] == [{'object': 'Synthetic_flora', 'faces': 1, 'instance_of': None}]


# #1382: the same-file decision comes before the alpha test. An opaque diffuse that is its own opacity map has no
# cutout; before the fix it fell into the separate-opacity branch and its RED channel became the atlas alpha.
OPAQUE_RGBA = [200, 80, 20, 255, 0, 80, 20, 255] * 2  # red = 0 on two pixels: channel(0) would cut them out
OPAQUE_RGB = [200, 80, 20, 0, 80, 20] * 2


def _codes(report):
    return [f['code'] for o in report['objects'] for f in o['findings']]


@pytest.mark.parametrize('px, channels', [(OPAQUE_RGBA, 4), (OPAQUE_RGB, 3)], ids=['rgba_fully_opaque', 'rgb_no_alpha'])
def test_preview_same_file_opaque_diffuse_has_no_cutout(monkeypatch, tmp_path, px, channels):
    report = _preview(monkeypatch, tmp_path, px=px, channels=channels)
    assert _codes(report) == []
    assert report['plan']['atlas']['opacity'] is False
    assert report['plan']['done'] == [{'object': 'Synthetic_flora', 'faces': 1, 'instance_of': None}]


def test_preview_same_file_partial_alpha_control_keeps_cutout(monkeypatch, tmp_path):
    report = _preview(monkeypatch, tmp_path, px=[200, 80, 20, 0, 0, 80, 20, 255] * 2)
    assert _codes(report) == []
    assert report['plan']['atlas']['opacity'] is True


def test_probe_same_file_opacity_follows_diffuse_alpha_only(monkeypatch, tmp_path):
    """Generated probe (seed 1382, 60 cases): opacity is True iff the diffuse has an alpha value < 255."""
    import random
    rnd = random.Random(1382)
    for i in range(60):
        channels = rnd.choice([3, 4])
        px = []
        for _ in range(4):
            px += [rnd.choice([0, 255, rnd.randrange(256)]) for _ in range(3)]
            if channels == 4:
                px.append(rnd.choice([255, 255, 255, rnd.randrange(256)]))
        case = tmp_path / str(i)
        case.mkdir()
        report = _preview(monkeypatch, case, px=px, channels=channels)
        expected = channels == 4 and min(px[3::4]) < 255
        assert _codes(report) == [], (i, px)
        assert report['plan']['atlas']['opacity'] is expected, (i, channels, px)
