"""new-case: a polygon install moves the user's AGR-Tools.bundle aside and restores it (#885)."""
from pathlib import Path


def _bundle(appdata):
    return Path(appdata) / 'Autodesk' / 'ApplicationPlugins' / 'AGR-Tools.bundle'


def _fill(root):
    root.mkdir(parents=True, exist_ok=True)
    (root / 'PackageContents.xml').write_bytes(b'<bundle>operator</bundle>')
    nested = root / 'Contents' / 'scripts'
    nested.mkdir(parents=True)
    (nested / 'agr.ms').write_bytes(b'maxscript-bytes')
    return {
        'PackageContents.xml': b'<bundle>operator</bundle>',
        'Contents/scripts/agr.ms': b'maxscript-bytes',
    }


def _read(root):
    found = {}
    for path in root.rglob('*'):
        if path.is_file():
            found[str(path.relative_to(root)).replace('\\', '/')] = path.read_bytes()
    return found


def test_stage_writes_slices_outside_the_user_bundle(tmp_path, monkeypatch):
    from test_polygon_support import stage_tools
    app = tmp_path / 'app'
    monkeypatch.setenv('APPDATA', str(app))
    source = Path(__file__).resolve().parents[2] / 'adapters' / 'max' / 'agr_tools'
    before = {path.name: path.read_bytes() for path in source.glob('*.py')}
    folder = stage_tools(tmp_path / 'stage')
    assert (folder / 'runtime.py').is_file()
    assert (folder / 'hygiene_core.py').is_file()
    assert (folder / 'uv_nudge_core.py').is_file()
    assert (folder / 'ucx_audit_core.py').is_file()
    assert not (source / 'hygiene_core.py').exists()
    assert {path.name: path.read_bytes() for path in source.glob('*.py')} == before
    assert not (app / 'Autodesk').exists()


def test_missing_bundle_is_left_missing(tmp_path):
    from test_polygon_support import preserve_user_bundle
    app = tmp_path / 'app'
    app.mkdir()
    with preserve_user_bundle(app):
        assert not _bundle(app).exists()
    assert not _bundle(app).exists()
    assert not list(app.rglob('*'))


def test_bundle_is_moved_aside_and_restored_byte_identical(tmp_path):
    from test_polygon_support import preserve_user_bundle
    app = tmp_path / 'app'
    original = _fill(_bundle(app))
    aside = _bundle(app).with_name('AGR-Tools.bundle.polygon-aside')
    with preserve_user_bundle(app):
        assert not _bundle(app).exists()
        assert _read(aside) == original
        replacement = _bundle(app)
        replacement.mkdir()
        (replacement / 'PackageContents.xml').write_bytes(b'NEW')
    assert not aside.exists()
    assert _read(_bundle(app)) == original


def test_restore_runs_when_the_block_raises(tmp_path):
    from test_polygon_support import preserve_user_bundle
    app = tmp_path / 'app'
    original = _fill(_bundle(app))
    try:
        with preserve_user_bundle(app):
            raise RuntimeError('install failed')
    except RuntimeError as exc:
        assert 'install failed' in str(exc)
    assert _read(_bundle(app)) == original
    assert not _bundle(app).with_name('AGR-Tools.bundle.polygon-aside').exists()
