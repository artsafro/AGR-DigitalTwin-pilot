"""#1757 (#1752 r1): the INSTALLED AGR Tools assets browser must find the publish catalogue.

Installed layout = install.ms: every top-level `agr_tools/*` file of the MZP copied flat into
`<userScripts>/AGRTools-1.1.0/`. There the repo path `../../../library/published/catalogue.json` does not exist,
so before the fix an `accepted` published version was never shown. Fixed: the build ships the catalogue as
`published-catalogue.json`, and settings key `published_catalogue` (a configured path) overrides it.
"""
import importlib.util
import json
import sys
import types
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / 'adapters/max/agr_tools'
NAME = 'Acme_X_1'
ACC = NAME + '/v001/' + NAME + '.zip'
DRAFT = NAME + '/v002/' + NAME + '.zip'
OLD = 'a101/Old_Y_2.zip'


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _cat(path, records):
    path.write_text(json.dumps({'schema': 'agr-library-publish/1', 'records': records}), encoding='utf-8')
    return path


def _zip(path, base):
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, 'w') as zf:
        zf.writestr(base + '_high.fbx', b'h')


@pytest.fixture
def lib(tmp_path):
    root = tmp_path / 'maf'
    for rel in (ACC, DRAFT, OLD):
        _zip(root / rel, Path(rel).stem)
    return root


def _install(tmp_path, monkeypatch, records):
    """Build the real MZP with a catalogue holding `records`, install its top-level files like install.ms."""
    builder = _load(ROOT / 'tools/max/build_agr_tools.py', 'agr_builder_1757')
    src = _cat(tmp_path / 'repo_catalogue.json', records)
    monkeypatch.setattr(builder, 'PUBLISHED_CATALOGUE', src, raising=False)
    mzp = tmp_path / 'AGRTools.mzp'
    builder.build(mzp)
    dest = tmp_path / 'usermacros' / 'scripts' / 'AGRTools-1.1.0'
    dest.mkdir(parents=True)
    with zipfile.ZipFile(mzp) as zf:
        for n in zf.namelist():
            if n.startswith('agr_tools/') and n.count('/') == 1:
                (dest / n.split('/', 1)[1]).write_bytes(zf.read(n))
    return dest


def _core(dest):
    return _load(dest / 'assets_core.py', 'assets_core_installed_1757')


def _shown(core, lib, cache, **kw):
    idx = core.scan_maf(str(lib), str(cache), lib='maf', **kw)
    return sorted(r['source']['path'] for r in idx['assets'])


ACCEPTED = [{'name': NAME, 'version': 'v001', 'status': 'accepted'},
            {'name': NAME, 'version': 'v002', 'status': 'draft'}]


def test_installed_copy_shows_accepted_version_from_shipped_catalogue(tmp_path, monkeypatch, lib):
    """Reviewer probe: installed assets_core, no `published=` (as assets_ui MaxBackend.scan) -> v001 shown."""
    dest = _install(tmp_path, monkeypatch, ACCEPTED)
    core = _core(dest)
    assert not (dest / '..' / '..' / '..' / 'library' / 'published' / 'catalogue.json').exists()
    assert Path(core.published_catalogue_path()).resolve() == (dest / 'published-catalogue.json').resolve()
    assert core.published_gate(ACC, core.published_accepted()) is None
    assert _shown(core, lib, tmp_path / 'c') == [ACC, OLD]          # draft v002 stays hidden


def test_configured_catalogue_overrides_the_shipped_snapshot(tmp_path, monkeypatch, lib):
    dest = _install(tmp_path, monkeypatch, [])                        # shipped snapshot: nothing accepted
    core = _core(dest)
    assert _shown(core, lib, tmp_path / 'c0') == [OLD]
    live = _cat(tmp_path / 'live.json', ACCEPTED)
    acc = core.published_accepted(core.published_catalogue_path(str(live)))
    assert _shown(core, lib, tmp_path / 'c1', published=acc) == [ACC, OLD]
    assert core.merge_settings({'published_catalogue': str(live)})['published_catalogue'] == str(live)
    assert core.merge_settings({})['published_catalogue'] == ''
    for blank in ('', '   ', None):                                   # unset -> the shipped copy, never the repo
        assert core.published_catalogue_path(blank) == core.PACKAGED_CATALOGUE


@pytest.mark.parametrize('bad', ['missing', 'dir', 'garbage', 'empty'])
def test_configured_but_broken_catalogue_is_fail_closed_never_the_snapshot(tmp_path, monkeypatch, lib, bad):
    dest = _install(tmp_path, monkeypatch, ACCEPTED)                  # snapshot WOULD show v001
    core = _core(dest)
    path = {'missing': tmp_path / 'none.json', 'dir': tmp_path, 'garbage': tmp_path / 'g.json',
            'empty': tmp_path / 'e.json'}[bad]
    if bad == 'garbage':
        path.write_text('{not json', encoding='utf-8')
    if bad == 'empty':
        path.write_text('', encoding='utf-8')
    acc = core.published_accepted(core.published_catalogue_path(str(path)))
    assert acc == set()
    assert _shown(core, lib, tmp_path / 'c', published=acc) == [OLD]


def test_alternate_form_records_are_not_accepted(tmp_path, monkeypatch, lib):
    """Mixed valid + alternate-form records: only the exact `accepted` record is shown."""
    recs = [{'name': NAME, 'version': 'v001', 'status': 'accepted'},
            {'name': NAME, 'version': 'v002', 'status': 'Accepted'},
            {'name': NAME, 'status': 'accepted'}]
    dest = _install(tmp_path, monkeypatch, recs)
    core = _core(dest)
    assert core.published_accepted() == set()                        # truncated record -> whole file unusable
    _cat(dest / 'published-catalogue.json', recs[:2])
    assert _shown(core, lib, tmp_path / 'c') == [ACC, OLD]


def test_build_ships_catalogue_and_install_requires_it():
    builder = _load(ROOT / 'tools/max/build_agr_tools.py', 'agr_builder_1757b')
    entries, inputs = builder._collect()
    assert entries['published-catalogue.json'] == builder.PUBLISHED_CATALOGUE.read_bytes().replace(b'\r\n', b'\n')
    assert builder.PUBLISHED_CATALOGUE in inputs
    assert '"published-catalogue.json"' in (PKG / 'install.ms').read_text(encoding='utf-8-sig')


def test_ui_backend_scan_uses_the_configured_catalogue(tmp_path, monkeypatch, lib):
    dest = _install(tmp_path, monkeypatch, [])
    for m in ('agr_tools_assets_core', 'agr_tools_ui_qt'):
        monkeypatch.delitem(sys.modules, m, raising=False)
    ui = _load(dest / 'assets_ui.py', 'assets_ui_installed_1757')
    live = _cat(tmp_path / 'live.json', ACCEPTED)
    fake = types.SimpleNamespace(lib=lambda: 'maf', ed_lib=types.SimpleNamespace(text=lambda: str(lib)),
                                 s={'preview_dirs': [], 'published_catalogue': str(live)})
    cfg = ui.AssetsWindow._cfg(fake)
    assert cfg['published_catalogue'] == str(live)
    be = object.__new__(ui.MaxBackend)
    idx = be.scan(cfg, str(tmp_path / 'c'))
    assert sorted(r['source']['path'] for r in idx['assets']) == [ACC, OLD]
    idx = be.scan(dict(cfg, published_catalogue=''), str(tmp_path / 'c2'))   # shipped snapshot: nothing accepted
    assert sorted(r['source']['path'] for r in idx['assets']) == [OLD]
