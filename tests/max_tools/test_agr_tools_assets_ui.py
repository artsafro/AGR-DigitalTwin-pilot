"""new-case: AGR Tools `assets` window (#1024) offscreen with a fake backend: grid, search, selection list,
settings round trip, import grouped by library. Skips when no PySide is installed
(`uv run --with PySide6 pytest tests/max_tools/test_agr_tools_assets_ui.py`)."""
import importlib.util
import os
import sys
from pathlib import Path

import pytest

pytest.importorskip('PySide6')
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / 'adapters/max/agr_tools'


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def ui(tmp_path, monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path / 'lad'))
    mod = _load(PKG / 'assets_ui.py', 'agr_tools_assets_ui_test')
    from PySide6 import QtWidgets
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    return mod, app


class FakeBackend(object):
    def __init__(self, core, tmp_path):
        self.core, self.calls = core, []
        root = tmp_path / 'flora'
        (root / 'PreviewFlora').mkdir(parents=True)
        (root / 'L.max').write_bytes(b'x')
        names = ['alpha_tree_t1_h500_high', 'alpha_tree_t1_h500_low', 'beta_bush_t2_h80_high',
                 'beta_bush_t2_h80_low', 'gamma_vine_t1_h140_high']
        self.idx = core.scan_flora(str(root), names, lib='flora')

    def load(self, cfg, cache):
        return self.idx if cfg['lib'] == 'flora' else None

    def scan(self, cfg, cache):
        return self.idx

    def import_assets(self, index, ids, settings, cache):
        self.calls.append((index['lib'], list(ids), settings['versions'], settings['materials']))
        return {'status': 'done', 'counts': {'merged': len(ids), 'skipped': 0, 'errors': 0}, 'errors': []}


def test_window_search_select_import_and_settings(ui, tmp_path, monkeypatch):
    mod, app = ui
    be = FakeBackend(mod.core, tmp_path)
    s = {'cache_dir': str(tmp_path / 'cache'), 'libraries': {'flora': 'x'}, 'materials': 'copy'}
    w = mod.AssetsWindow(be, settings=s)
    assert w.model.rowCount() == 3
    w.search.setText('bush')
    assert [r['name'] for r in w.model.records] == ['beta_bush_t2_h80']
    w._card_clicked(w.model.index_of(0))
    w.search.setText('')
    w._toggle('flora:alpha_tree_t1_h500')
    assert w.sel.count() == 2 and w.lbl_sel.text() == 'Выбрано: 2'
    w.chk_low.setChecked(False)
    monkeypatch.setattr(mod.QtWidgets.QMessageBox, 'information', lambda *a, **k: None)
    w.do_import()
    assert be.calls == [('flora', ['flora:beta_bush_t2_h80', 'flora:alpha_tree_t1_h500'], ['high'], 'copy')]
    w.close()
    again = mod.load_settings()
    assert again['selection'] == ['flora:beta_bush_t2_h80', 'flora:alpha_tree_t1_h500']
    assert again['versions'] == ['high'] and again['materials'] == 'copy'
    w2 = mod.AssetsWindow(be, settings=again)
    assert w2.sel.count() == 2
    w2._clear()
    assert w2.sel.count() == 0 and not w2.cmb_src.isEnabled()  # Flora: MAX only
    pix = w2.grab()
    assert pix.width() > 0


def test_selection_of_an_unloaded_library_survives(ui, tmp_path):
    mod, app = ui
    be = FakeBackend(mod.core, tmp_path)
    w = mod.AssetsWindow(be, settings={'cache_dir': str(tmp_path / 'c'), 'libraries': {'flora': 'x'},
                                       'selection': ['maf:Adx_Stol_1', 'flora:alpha_tree_t1_h500', 'flora:gone']})
    assert w.model.selection.ids == ['maf:Adx_Stol_1', 'flora:alpha_tree_t1_h500']
    assert 'нет 3' in w.status.text()  # counted from the records (the fake library has no previews)
