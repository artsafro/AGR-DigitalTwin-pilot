"""new-case: review-texture gate contract and native saved-file regression (#1365)."""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'tools/review/review_textures.py'


def load():
    spec = importlib.util.spec_from_file_location('review_textures', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('value', [0.25, 0.5, 1, 2])
def test_joint_sampling(value):
    gate = load()
    row = {'joint_m': 0.01, 'tile_m': 4}
    # 10mm joint over a 4m tile: at 512px it occupies 1.28 texels.
    result = gate.joint_sampling(row, int(512 * value))
    assert result['texels'] == pytest.approx(1.28 * value)
    assert result['status'] == ('pass' if value == 2 else 'review')
    assert gate.joint_sampling({'joint_m': 0.01, 'tile_m': 4}, 800)['status'] == 'review'


@pytest.mark.parametrize('value', [{}, {'ids': []}, {'ids': [{'object': 'Brick', 'id': 1, 'extra': 1}]},
                                  {'ids': [{'object': 'Brick', 'id': True}]},
                                  {'ids': [{'object': '', 'id': 1}]},
                                  {'ids': [{'object': 'Brick', 'id': 0}]},
                                  {'ids': [{'object': 'Brick', 'id': 1}] * 2},
                                  {'ids': [{'object': 'Brick', 'id': 1, 'joint_m': float('nan'), 'tile_m': 4}]},
                                  {'ids': [{'object': 'Brick', 'id': 1, 'joint_m': .01}]},
                                  {'ids': [{'object': 'Brick', 'id': 1}], 'unknown': 1}])
def test_invalid_contract(value):
    with pytest.raises(ValueError):
        load().validate_manifest(value)


@pytest.mark.parametrize('value', [0, -1, float('nan'), float('inf'), True, '512'])
def test_invalid_viewport_limit(value):
    with pytest.raises(ValueError):
        load().joint_sampling({'joint_m': .01, 'tile_m': 4}, value)


def test_output_protection(tmp_path):
    gate = load()
    source = tmp_path / 'source.blend'
    source.write_bytes(b'source')
    manifest = tmp_path / 'scope.json'
    manifest.write_bytes(b'manifest')
    alias = tmp_path / 'alias.json'
    alias.hardlink_to(source)
    for target in (source, manifest, alias, tmp_path / '.' / 'source.blend'):
        with pytest.raises((ValueError, FileExistsError)):
            gate.write_report(target, {'status': 'pass'}, [source, manifest])
    target = tmp_path / 'report.json'
    target.write_bytes(b'foreign report')
    with pytest.raises(FileExistsError):
        gate.write_report(target, {'status': 'pass'}, [source, manifest])
    assert source.read_bytes() == b'source'
    assert manifest.read_bytes() == b'manifest'
    assert target.read_bytes() == b'foreign report'


def test_max_viewport_limit_uses_published_readonly_property():
    from types import SimpleNamespace
    rt = SimpleNamespace(NitrousGraphicsManager=SimpleNamespace(
        GetActiveViewportSetting=lambda: SimpleNamespace(TextureSizeLimit=512)),
        getNodeByName=lambda *args, **kwargs: None)
    result = load().check_max(rt, {'ids': [{'object': 'Unknown', 'id': 1}]})
    assert result['viewport_limit'] == 512
    assert result['status'] == 'fail'
    assert result['ids'][0]['reason'] == 'unknown object: Unknown'


@pytest.mark.parametrize('cls,enabled,amount', [
    ('Standardmaterial', 'diffuseMapEnable', 'diffuseMapAmount'),
    ('PhysicalMaterial', 'base_color_map_on', 'base_weight'),
])
@pytest.mark.parametrize('fault,value', [
    ('enabled', False), ('enabled', None), ('amount', 0), ('amount', -1),
    ('amount', float('nan')), ('amount', float('inf')), ('amount', None),
    ('viewport', False), ('viewport', None),
])
def test_max_material_visibility(tmp_path, cls, enabled, amount, fault, value):
    from types import SimpleNamespace
    path = tmp_path / 'synthetic.png'
    path.write_bytes(b'synthetic file evidence; bitmap dimensions supplied by native seam')
    material = SimpleNamespace(name='Synthetic', **{enabled: True, amount: 1, 'showInViewport': True})
    tex = SimpleNamespace(filename=str(path), bitmap=SimpleNamespace(width=256, height=256))
    slot = 'diffuseMap' if cls == 'Standardmaterial' else 'base_color_map'
    setattr(material, slot, tex)
    rt = SimpleNamespace(classOf=lambda obj: cls if obj is material else 'Bitmaptexture',
                         getProperty=lambda obj, name: getattr(obj, name))
    prop = {'enabled': enabled, 'amount': amount, 'viewport': 'showInViewport'}[fault]
    if value is None:
        delattr(material, prop)
    else:
        setattr(material, prop, value)
    before = vars(material).copy()
    with pytest.raises(ValueError, match=prop):
        load().max_material(rt, material)
    assert vars(material) == before


@pytest.mark.parametrize('cls,enabled,amount,slot', [
    ('Standardmaterial', 'diffuseMapEnable', 'diffuseMapAmount', 'diffuseMap'),
    ('PhysicalMaterial', 'base_color_map_on', 'base_weight', 'base_color_map'),
])
def test_max_material_visibility_reset(tmp_path, cls, enabled, amount, slot):
    from types import SimpleNamespace
    path = tmp_path / 'synthetic.png'
    path.write_bytes(b'synthetic')
    material = SimpleNamespace(name='Synthetic', **{enabled: True, amount: .5, 'showInViewport': True})
    tex = SimpleNamespace(filename=str(path), bitmap=SimpleNamespace(width=256, height=256))
    setattr(material, slot, tex)
    rt = SimpleNamespace(classOf=lambda obj: cls if obj is material else 'Bitmaptexture',
                         getProperty=lambda obj, name: getattr(obj, name))
    gate = load()
    expected = gate.max_material(rt, material)
    for prop in (enabled, amount, 'showInViewport'):
        original = getattr(material, prop)
        setattr(material, prop, False if type(original) is bool else 0)
        for _ in range(2):
            with pytest.raises(ValueError, match=prop):
                gate.max_material(rt, material)
        setattr(material, prop, original)
        assert gate.max_material(rt, material) == expected


@pytest.mark.parametrize('cls', ['undefined', 'Multimaterial', 'UnknownShader'])
def test_max_material_unsupported(cls):
    from types import SimpleNamespace
    with pytest.raises(ValueError, match=cls):
        load().max_material(SimpleNamespace(classOf=lambda _: cls), None)


def test_skill_contract():
    for name in ('validate-delivery', '3dsmax-mcp-dev'):
        text = (ROOT / '.agents/skills' / name / 'SKILL.md').read_text(encoding='utf-8')
        assert 'REVIEW_TEXTURES.md' in text
        if name == '3dsmax-mcp-dev':
            assert 'global' in text and 'ask-first' in text
        assert (ROOT / '.claude/skills' / name / 'SKILL.md').read_text(encoding='utf-8') == text


@pytest.mark.blender
def test_native_blender_saved_file(tmp_path):
    from dt_ai.core.blender_runner import run_blender
    result = run_blender(ROOT / 'tests/blender/run_review_textures_1365.py',
                         [SCRIPT, tmp_path], output_json=tmp_path / 'native.json',
                         log_path=tmp_path / 'native.log')
    assert result['empty']['status'] == 'fail'
    assert result['linked']['status'] == 'pass'
    assert result['packed']['status'] == 'pass'
    for key in ('missing', 'unlinked', 'wrong_output', 'unknown_id', 'unused_id'):
        assert result[key]['status'] == 'fail', key
    assert result['repeated'] == result['linked']
    assert result['unchanged_sources'] is True
