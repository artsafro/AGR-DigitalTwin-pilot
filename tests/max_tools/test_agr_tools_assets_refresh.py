"""new-case: synthetic hostile probes for the legacy assets PR refresh (#1024)."""
import importlib.util
import sys
import types
import zipfile
from pathlib import Path

import pytest

PKG = Path(__file__).resolve().parents[2] / 'adapters/max/agr_tools'


def load(name):
    spec = importlib.util.spec_from_file_location('refresh_' + name, PKG / (name + '.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


core = load('assets_core')


@pytest.mark.parametrize('key,value', [(k, v) for k in ('fbx_scale', 'gap_m', 'row_limit_m')
                                      for v in (float('nan'), float('inf'), -1)])
def test_settings_reject_invalid_numbers(key, value):
    with pytest.raises(ValueError, match=key):
        core.merge_settings({key: value})


def test_extraction_rejects_same_size_stale_file(tmp_path):
    archive = tmp_path / 'source.zip'
    with zipfile.ZipFile(archive, 'w') as z:
        z.writestr('asset.max', b'new')
    dest = tmp_path / 'out'
    dest.mkdir()
    (dest / 'asset.max').write_bytes(b'old')
    with pytest.raises(ValueError, match='existing'):
        core.extract_members(str(archive), str(dest), lambda _: True)
    assert (dest / 'asset.max').read_bytes() == b'old'


def test_extraction_rejects_input_alias_before_any_write(tmp_path):
    archive = tmp_path / 'source.zip'
    with zipfile.ZipFile(archive, 'w') as z:
        z.writestr('innocent.max', b'new')
        z.writestr('source.zip', b'clobber')
    before = archive.read_bytes()
    with pytest.raises(ValueError, match='input'):
        core.extract_members(str(archive), str(tmp_path), lambda _: True)
    assert archive.read_bytes() == before
    assert not (tmp_path / 'innocent.max').exists()


def test_extraction_rejects_duplicate_flattened_names(tmp_path):
    archive = tmp_path / 'source.zip'
    with zipfile.ZipFile(archive, 'w') as z:
        z.writestr('a/model.max', b'one')
        z.writestr('b/MODEL.max', b'two')
    with pytest.raises(ValueError, match='duplicate'):
        core.extract_members(str(archive), str(tmp_path / 'out'), lambda _: True)
    assert not (tmp_path / 'out' / 'model.max').exists()


def test_extraction_preserves_predictable_temp_sentinel(tmp_path):
    archive = tmp_path / 'source.zip'
    with zipfile.ZipFile(archive, 'w') as z:
        z.writestr('asset.max', b'new')
    dest = tmp_path / 'out'
    dest.mkdir()
    (dest / 'asset.max.tmp').write_bytes(b'sentinel')
    core.extract_members(str(archive), str(dest), lambda _: True)
    assert (dest / 'asset.max.tmp').read_bytes() == b'sentinel'


def test_texture_plan_detects_equal_length_content_conflict(tmp_path):
    src, dst = tmp_path / 'src', tmp_path / 'dst'
    src.mkdir()
    dst.mkdir()
    (src / 'map.png').write_bytes(b'new')
    (dst / 'map.png').write_bytes(b'old')
    plan = core.texture_plan(['map.png'], [str(src)], str(dst))
    assert plan['conflicts'] == [str(dst / 'map.png')]
    assert not plan['map'] and not plan['copy']


def test_duplicate_ids_are_not_merged_twice():
    rec = core.make_record('test', 'flora', 'tree', versions={'high': {'objects': ['tree_high']}},
                           source={'path': 'lib.max', 'sha256': 'a' * 64})
    with pytest.raises(ValueError, match='duplicate'):
        core.import_plan({'assets': [rec]}, [rec['id'], rec['id']], ['high'])


def test_source_copy_rechecks_cached_bytes(tmp_path, monkeypatch):
    fake = types.ModuleType('pymxs')
    fake.runtime = types.SimpleNamespace()
    monkeypatch.setitem(sys.modules, 'pymxs', fake)
    mx = load('assets_max')
    src = tmp_path / 'lib.max'
    src.write_bytes(b'original')
    sha = core.sha256_file(str(src))
    cache = tmp_path / 'cache'
    cached = cache / 'sources' / (sha[:12] + '_lib.max')
    cached.parent.mkdir(parents=True)
    cached.write_bytes(b'tampered')
    with pytest.raises(ValueError, match='cache'):
        mx.source_copy({'root': str(tmp_path)}, {'source': {'path': 'lib.max', 'sha256': sha}}, str(cache))
    assert src.read_bytes() == b'original'


@pytest.mark.parametrize('status', ['not_in_index', 'no_version', 'blocked_by_audit'])
def test_import_does_not_report_refused_rows_as_done(tmp_path, monkeypatch, status):
    import contextlib
    fake = types.ModuleType('pymxs')
    fake.runtime = types.SimpleNamespace(Name=lambda x: x, objects=[],
        disableSceneRedraw=lambda: None, enableSceneRedraw=lambda: None, freeSceneBitmaps=lambda: None)
    fake.undo = lambda *args: contextlib.nullcontext()
    monkeypatch.setitem(sys.modules, 'pymxs', fake)
    mx = load('assets_max')
    monkeypatch.setattr(mx, 'm_per_unit', lambda: 1.0)
    monkeypatch.setattr(mx.core, 'import_plan', lambda *a: [{'id': 'unknown', 'status': status}])
    result = mx.run_import({'adapter': 'flora_max', 'lib': 'flora', 'assets': [],
                           'layout': {'textures': None, 'viz_textures': None}}, ['unknown'], {},
                          str(tmp_path), scene_label='synthetic.max', localappdata=str(tmp_path))
    assert result['status'] == 'failed'
    assert result['errors']


def test_json_write_preserves_temp_sentinel(tmp_path):
    target = tmp_path / 'index.json'
    sentinel = tmp_path / 'index.json.tmp'
    sentinel.write_bytes(b'keep')
    core.write_json_atomic(str(target), {'value': 1})
    assert sentinel.read_bytes() == b'keep'


def test_all_assets_dependencies_ship():
    root = PKG.parents[2]
    spec = importlib.util.spec_from_file_location('refresh_builder', root / 'tools/max/build_agr_tools.py')
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    install = (PKG / 'install.ms').read_text(encoding='utf-8')
    for name in ('assets_core.py', 'assets_max.py', 'assets_ui.py', 'assets_library.py',
                 'assets_textures.py', 'assets_launch.ms'):
        assert name in builder.FILES, name
        assert '"' + name + '"' in install, name
