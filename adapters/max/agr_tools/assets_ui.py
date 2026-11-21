"""new-case: AGR Tools `assets` browser window (#1024): thumbnail grid, search, selection list, settings, import.

Qt through ui_qt.py (PySide6 in Max 2025+, PySide2 in Max 2024); colours from the palette (Max theme), like the
AGR Tools panel. The window talks to a backend object, so it also runs outside Max (offscreen screenshot, tests):
  backend.scan(lib_cfg, cache_dir) -> index;  backend.load(lib_cfg, cache_dir) -> index | None
  backend.import_assets(index, ids, settings, cache_dir) -> report;  backend.match(indexes) -> report (optional)
Launch in Max: assets_launch.ms (no change to the shared panel/menu/build files; see the PR for registration).
"""
import json
import os
from pathlib import Path

try:
    from ui_qt import QtCore, QtGui, QtWidgets, max_main_window, disable_accelerators
except ImportError:  # loaded by path (tests / launcher)
    import importlib.util
    import sys
    _p = Path(__file__).with_name('ui_qt.py')
    _s = importlib.util.spec_from_file_location('agr_tools_ui_qt', _p)
    _m = importlib.util.module_from_spec(_s)
    sys.modules['agr_tools_ui_qt'] = _m
    _s.loader.exec_module(_m)
    QtCore, QtGui, QtWidgets = _m.QtCore, _m.QtGui, _m.QtWidgets
    max_main_window, disable_accelerators = _m.max_main_window, _m.disable_accelerators

Qt = QtCore.Qt
THUMB = 192
CARD_W, CARD_H, IMG_H = 168, 214, 132
ID_ROLE, REC_ROLE, SEL_ROLE = int(Qt.UserRole) + 1, int(Qt.UserRole) + 2, int(Qt.UserRole) + 3


def load_core():
    import importlib.util
    import sys
    name = 'agr_tools_assets_core'
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name('assets_core.py'))
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
    return sys.modules[name]


core = load_core()


def settings_path():
    base = os.environ.get('LOCALAPPDATA') or os.path.expanduser('~')
    return os.path.join(base, 'AGRTools', 'assets_settings.json')


def load_settings():
    try:
        with open(settings_path(), encoding='utf-8') as f:
            return core.merge_settings(json.load(f))
    except (OSError, ValueError):
        return core.merge_settings({})


class _ThumbSignal(QtCore.QObject):
    done = QtCore.Signal(str, object)


class _ThumbJob(QtCore.QRunnable):
    def __init__(self, key, src, dst, signal):
        super(_ThumbJob, self).__init__()
        self.key, self.src, self.dst, self.signal = key, src, dst, signal

    def run(self):
        img = None
        if self.dst and os.path.isfile(self.dst):
            img = QtGui.QImage(self.dst)
        if (img is None or img.isNull()) and self.src and os.path.isfile(self.src):
            img = QtGui.QImage(self.src)
            if not img.isNull():
                img = img.scaled(THUMB, THUMB, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                try:
                    os.makedirs(os.path.dirname(self.dst), exist_ok=True)
                    img.save(self.dst, 'PNG')
                except OSError:
                    pass
        try:
            self.signal.done.emit(self.key, img if img is not None and not img.isNull() else None)
        except RuntimeError:
            pass  # window closed


class AssetModel(QtCore.QAbstractListModel):
    def __init__(self, parent=None):
        super(AssetModel, self).__init__(parent)
        self.records, self.lib_index, self.cache_dir = [], None, ''
        self.selection = core.Selection()
        self._pix, self._pending = {}, set()
        self._signal = _ThumbSignal()
        self._signal.done.connect(self._thumb_ready)
        self._pool = QtCore.QThreadPool.globalInstance()

    def set_index(self, index, cache_dir, query=''):
        self.beginResetModel()
        self.lib_index, self.cache_dir = index, cache_dir
        self.records = core.search(index['assets'], query) if index else []
        self.endResetModel()

    def rowCount(self, parent=QtCore.QModelIndex()):
        return 0 if parent.isValid() else len(self.records)

    def data(self, idx, role=Qt.DisplayRole):
        if not idx.isValid():
            return None
        r = self.records[idx.row()]
        if role == Qt.DisplayRole:
            return r['name']
        if role == ID_ROLE:
            return r['id']
        if role == REC_ROLE:
            return r
        if role == SEL_ROLE:
            return r['id'] in self.selection.ids
        if role == Qt.DecorationRole:
            pix = self._pix.get(r['id'])
            if pix is None:
                self._request(r)
            return pix
        if role == Qt.ToolTipRole:
            return '\n'.join([r['name']] + r.get('warnings', []))
        return None

    def _request(self, r):
        if r['id'] in self._pending or not self.lib_index:
            return
        src = core.preview_abspath(self.lib_index, r, self.cache_dir)
        if not src:
            return
        self._pending.add(r['id'])
        dst = os.path.join(self.cache_dir, 'thumbs', r['lib'], r['name'] + '.png') if self.cache_dir else ''
        self._pool.start(_ThumbJob(r['id'], src, dst, self._signal))

    def _thumb_ready(self, key, img):
        self._pending.discard(key)
        if img is None:
            return
        self._pix[key] = QtGui.QPixmap.fromImage(img)
        for row, r in enumerate(self.records):
            if r['id'] == key:
                i = self.index_of(row)
                self.dataChanged.emit(i, i)
                break

    def index_of(self, row):
        return self.createIndex(row, 0)

    def refresh(self):
        if self.records:
            self.dataChanged.emit(self.index_of(0), self.index_of(len(self.records) - 1))


class CardDelegate(QtWidgets.QStyledItemDelegate):
    def sizeHint(self, option, index):
        return QtCore.QSize(CARD_W, CARD_H)

    def paint(self, p, option, index):
        pal = option.palette
        r = index.data(REC_ROLE)
        sel = bool(index.data(SEL_ROLE))
        rect = option.rect.adjusted(3, 3, -3, -3)
        p.save()
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        p.setBrush(pal.color(QtGui.QPalette.Highlight) if sel else pal.color(QtGui.QPalette.Base))
        p.setPen(QtGui.QPen(pal.color(QtGui.QPalette.Highlight if sel else QtGui.QPalette.Mid), 2 if sel else 1))
        p.drawRoundedRect(rect, 5, 5)
        img = QtCore.QRect(rect.left() + 5, rect.top() + 5, rect.width() - 10, IMG_H)
        pix = index.data(Qt.DecorationRole)
        text_col = pal.color(QtGui.QPalette.HighlightedText if sel else QtGui.QPalette.Text)
        if isinstance(pix, QtGui.QPixmap) and not pix.isNull():
            s = pix.scaled(img.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            p.drawPixmap(img.left() + (img.width() - s.width()) // 2, img.top() + (img.height() - s.height()) // 2, s)
        else:
            p.setPen(text_col)
            p.drawText(img, Qt.AlignCenter, 'нет превью' if r.get('preview_match') == 'none' else '…')
        f = p.font()
        f.setPointSizeF(max(6.5, f.pointSizeF() - 1.5))
        f.setBold(True)
        p.setFont(f)
        p.setPen(text_col)
        warn = ' !' if r.get('warnings') else ''
        p.drawText(img.adjusted(3, 2, -3, -2), Qt.AlignLeft | Qt.AlignTop, core.badge(r) + warn)
        f.setBold(False)
        p.setFont(f)
        if r['kind'] == 'maf' and r.get('manufacturer'):
            lines = [r.get('category') or '—', r.get('title') or '',
                     '{} · {}'.format(r['manufacturer'], r.get('article') or '')]
        else:
            lines = [(r.get('title') or r['name']), 'тип {}  ·  h {} см'.format(r.get('variant'), r.get('height_cm'))
                     if r.get('variant') is not None else '', 'превью по похожему имени' if r.get('preview_match') == 'fuzzy' else '']
        fm = QtGui.QFontMetrics(f)
        y = img.bottom() + 6
        for ln in lines[:3]:
            p.drawText(QtCore.QRect(rect.left() + 5, y, rect.width() - 10, fm.height()), Qt.AlignHCenter,
                       fm.elidedText(ln, Qt.ElideRight, rect.width() - 10))
            y += fm.height()
        p.restore()


class AssetsWindow(QtWidgets.QWidget):
    LIBS = (('flora', 'Flora'), ('maf', 'МАФ'))

    def __init__(self, backend, parent=None, settings=None):
        super(AssetsWindow, self).__init__(parent)
        self.backend = backend
        self.setWindowTitle('AGR Tools — Ассеты')
        self.setWindowFlags(Qt.Window)
        self.resize(1180, 760)
        self.s = core.merge_settings(settings if settings is not None else load_settings())
        self.indexes = {}
        self.model = AssetModel(self)
        self._build()
        self._restore()
        self.load_current()

    # ---- UI ----
    def _build(self):
        root = QtWidgets.QVBoxLayout(self)
        top = QtWidgets.QHBoxLayout()
        self.cmb_lib = QtWidgets.QComboBox()
        for key, label in self.LIBS:
            self.cmb_lib.addItem(label, key)
        self.cmb_lib.currentIndexChanged.connect(self._lib_changed)
        top.addWidget(self.cmb_lib)
        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText('Поиск: вид, производитель, название, артикул, h…')
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._filter)
        top.addWidget(self.search, 1)
        self.chk_high = QtWidgets.QCheckBox('High (ВПМ)')
        self.chk_low = QtWidgets.QCheckBox('Low (НПМ)')
        top.addWidget(self.chk_high)
        top.addWidget(self.chk_low)
        top.addWidget(QtWidgets.QLabel('Источник:'))
        self.cmb_src = QtWidgets.QComboBox()
        self.cmb_src.addItem('MAX', 'max')
        self.cmb_src.addItem('FBX', 'fbx')
        top.addWidget(self.cmb_src)
        top.addWidget(QtWidgets.QLabel('FBX ×'))
        self.spn_fbx = QtWidgets.QDoubleSpinBox()
        self.spn_fbx.setDecimals(4)
        self.spn_fbx.setRange(0.0001, 100000.0)
        self.spn_fbx.setToolTip('Множитель масштаба FBX (МАФ). Для MAX не используется.')
        top.addWidget(self.spn_fbx)
        self.cmb_src.currentIndexChanged.connect(self._src_changed)
        top.addWidget(QtWidgets.QLabel('Материалы:'))
        self.cmb_mtl = QtWidgets.QComboBox()
        self.cmb_mtl.addItem('из сцены', 'reuse')
        self.cmb_mtl.addItem('копия', 'copy')
        top.addWidget(self.cmb_mtl)
        top.addWidget(QtWidgets.QLabel('Текстуры:'))
        self.cmb_tex = QtWidgets.QComboBox()
        self.cmb_tex.addItem('в проект', 'project')
        self.cmb_tex.addItem('из библиотеки', 'library')
        top.addWidget(self.cmb_tex)
        root.addLayout(top)

        split = QtWidgets.QSplitter(Qt.Horizontal)
        self.view = QtWidgets.QListView()
        self.view.setModel(self.model)
        self.view.setItemDelegate(CardDelegate(self.view))
        self.view.setViewMode(QtWidgets.QListView.IconMode)
        self.view.setResizeMode(QtWidgets.QListView.Adjust)
        self.view.setMovement(QtWidgets.QListView.Static)
        self.view.setUniformItemSizes(True)
        self.view.setSpacing(4)
        self.view.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        self.view.clicked.connect(self._card_clicked)
        split.addWidget(self.view)
        right = QtWidgets.QWidget()
        rl = QtWidgets.QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        self.lbl_sel = QtWidgets.QLabel()
        rl.addWidget(self.lbl_sel)
        self.sel = QtWidgets.QListWidget()
        self.sel.setToolTip('Двойной клик — убрать из выбора')
        self.sel.itemDoubleClicked.connect(lambda it: self._toggle(it.data(ID_ROLE)))
        rl.addWidget(self.sel, 1)
        b = QtWidgets.QPushButton('Очистить выбор')
        b.clicked.connect(self._clear)
        rl.addWidget(b)
        split.addWidget(right)
        split.setSizes([880, 300])
        root.addWidget(split, 1)

        grid = QtWidgets.QGridLayout()
        self.ed_lib = self._path_row(grid, 0, 'Библиотека:')
        self.ed_cache = self._path_row(grid, 1, 'Индекс/кеш:')
        self.ed_proj = self._path_row(grid, 2, 'Папка проекта:')
        root.addLayout(grid)
        bottom = QtWidgets.QHBoxLayout()
        self.btn_scan = QtWidgets.QPushButton('Сканировать библиотеку')
        self.btn_scan.clicked.connect(self.scan)
        bottom.addWidget(self.btn_scan)
        self.btn_match = QtWidgets.QPushButton('Сопоставить')
        self.btn_match.setToolTip('Хелперы сцены (блоки DWG) ↔ индекс библиотеки и спецификация альбома')
        self.btn_match.clicked.connect(self.match)
        self.btn_match.setEnabled(hasattr(self.backend, 'match'))
        bottom.addWidget(self.btn_match)
        self.btn_remove = QtWidgets.QPushButton('Убрать импортированное')
        self.btn_remove.setToolTip('Удалить из сцены объекты этой библиотеки с метками agr_asset_* (откат импорта;'
                                   ' Undo после merge в Max 2024 batch падает, см. docs/agr-tools/assets.md)')
        self.btn_remove.clicked.connect(self.remove_imported)
        self.btn_remove.setEnabled(hasattr(self.backend, 'remove_imported'))
        bottom.addWidget(self.btn_remove)
        self.status = QtWidgets.QLabel()
        bottom.addWidget(self.status, 1)
        self.btn_import = QtWidgets.QPushButton('Импорт')
        self.btn_import.setMinimumWidth(140)
        self.btn_import.clicked.connect(self.do_import)
        bottom.addWidget(self.btn_import)
        root.addLayout(bottom)
        disable_accelerators(self)

    def _path_row(self, grid, row, label):
        grid.addWidget(QtWidgets.QLabel(label), row, 0)
        ed = QtWidgets.QLineEdit()
        grid.addWidget(ed, row, 1)
        b = QtWidgets.QPushButton('…')
        b.setFixedWidth(28)
        b.clicked.connect(lambda: self._browse(ed))
        grid.addWidget(b, row, 2)
        return ed

    def _browse(self, ed):
        d = QtWidgets.QFileDialog.getExistingDirectory(self, 'Папка', ed.text())
        if d:
            ed.setText(d)

    # ---- settings ----
    def lib(self):
        return self.cmb_lib.currentData()

    def _restore(self):
        s = self.s
        self.chk_high.setChecked('high' in s['versions'])
        self.chk_low.setChecked('low' in s['versions'])
        self.cmb_src.setCurrentIndex(max(0, self.cmb_src.findData(s['source'])))
        self.spn_fbx.setValue(float(s['fbx_scale']))
        self.cmb_mtl.setCurrentIndex(max(0, self.cmb_mtl.findData(s['materials'])))
        self.cmb_tex.setCurrentIndex(max(0, self.cmb_tex.findData(s['textures'])))
        self.ed_cache.setText(s['cache_dir'])
        self.ed_proj.setText(s['project_dir'])
        self.model.selection = core.Selection(s.get('selection') or [])
        self._lib_changed()

    def collect(self):
        s = dict(self.s)
        libs = dict(s['libraries'])
        libs[self.lib()] = self.ed_lib.text().strip()
        versions = [v for v, c in (('high', self.chk_high), ('low', self.chk_low)) if c.isChecked()]
        s.update(libraries=libs, versions=versions or ['high'], source=self.cmb_src.currentData(),
                 fbx_scale=self.spn_fbx.value(), materials=self.cmb_mtl.currentData(),
                 textures=self.cmb_tex.currentData(), cache_dir=self.ed_cache.text().strip(),
                 project_dir=self.ed_proj.text().strip(), selection=list(self.model.selection.ids))
        return core.merge_settings(s)

    def save(self):
        self.s = self.collect()
        try:
            core.write_json_atomic(settings_path(), self.s)
        except OSError:
            pass

    def closeEvent(self, e):
        self.save()
        super(AssetsWindow, self).closeEvent(e)

    # ---- data ----
    def _lib_changed(self, *_):
        self.ed_lib.setText(self.s['libraries'].get(self.lib(), ''))
        self.cmb_src.setEnabled(self.lib() == 'maf')
        if self.lib() == 'flora':
            self.cmb_src.setCurrentIndex(0)
        self._src_changed()
        self.load_current()

    def _src_changed(self, *_):
        self.spn_fbx.setEnabled(self.cmb_src.currentData() == 'fbx')

    def _cfg(self):
        return {'lib': self.lib(), 'root': self.ed_lib.text().strip(), 'preview_dirs': list(self.s.get('preview_dirs') or [])}

    def load_current(self):
        idx = self.indexes.get(self.lib())
        if idx is None and self.ed_cache.text().strip():
            try:
                idx = self.backend.load(self._cfg(), self.ed_cache.text().strip())
            except Exception as exc:  # noqa: BLE001 - shown to the user
                self.status.setText('Индекс не загружен: {}'.format(exc))
        if idx is not None:
            self.indexes[self.lib()] = idx
        self._filter()

    def _filter(self, *_):
        idx = self.indexes.get(self.lib())
        self.model.set_index(idx, self.ed_cache.text().strip(), self.search.text())
        if idx:
            loaded = {i['lib'] for i in self.indexes.values()}  # prune only libraries whose index is loaded
            known = {r['id'] for i in self.indexes.values() for r in i['assets']}
            self.model.selection.keep_only(x for x in self.model.selection.ids
                                           if x in known or x.split(':', 1)[0] not in loaded)
            pm = {}
            for r in idx['assets']:
                pm[r.get('preview_match') or 'none'] = pm.get(r.get('preview_match') or 'none', 0) + 1
            self.status.setText('{}: {} из {} · превью: точно {}, похоже {}, нет {}'.format(
                dict(self.LIBS)[self.lib()], len(self.model.records), len(idx['assets']),
                pm.get('exact', '—'), pm.get('fuzzy', '—'), pm.get('none', '—')))
        self._refresh_sel()

    def scan(self):
        cfg, cache = self._cfg(), self.ed_cache.text().strip()
        if not cfg['root'] or not cache:
            QtWidgets.QMessageBox.warning(self, 'Ассеты', 'Укажите папку библиотеки и папку индекса.')
            return
        QtWidgets.QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            self.indexes[self.lib()] = self.backend.scan(cfg, cache)
        except Exception as exc:  # noqa: BLE001
            QtWidgets.QMessageBox.critical(self, 'Ассеты', 'Скан не выполнен:\n{}'.format(exc))
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()
        self.save()
        self._filter()
        rep = (self.indexes.get(self.lib()) or {}).get('report', {})
        if rep.get('problems'):
            QtWidgets.QMessageBox.warning(self, 'Ассеты', 'Не прочитаны (докачиваются или битые):\n' + '\n'.join(
                p['path'] for p in rep['problems'][:15]))

    # ---- selection ----
    def _card_clicked(self, i):
        self._toggle(i.data(ID_ROLE))

    def _toggle(self, asset_id):
        self.model.selection.toggle(asset_id)
        self.model.refresh()
        self._refresh_sel()

    def _clear(self):
        self.model.selection.clear()
        self.model.refresh()
        self._refresh_sel()

    def _refresh_sel(self):
        self.sel.clear()
        for i in self.model.selection.ids:
            it = QtWidgets.QListWidgetItem(i.split(':', 1)[1])
            it.setData(ID_ROLE, i)
            self.sel.addItem(it)
        self.lbl_sel.setText('Выбрано: {}'.format(len(self.model.selection.ids)))

    # ---- actions ----
    def do_import(self):
        ids = list(self.model.selection.ids)
        if not ids:
            QtWidgets.QMessageBox.information(self, 'Ассеты', 'Ничего не выбрано.')
            return
        self.save()
        by_lib = {}
        for i in ids:
            by_lib.setdefault(i.split(':', 1)[0], []).append(i)
        msgs = []
        QtWidgets.QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            for lib_id, part in by_lib.items():
                idx = next((x for x in self.indexes.values() if x['lib'] == lib_id), None)
                if idx is None:
                    msgs.append('{}: индекс не загружен'.format(lib_id))
                    continue
                rep = self.backend.import_assets(idx, part, self.s, self.s['cache_dir'])
                c = rep.get('counts', {})
                msgs.append('{}: {} — импортировано {}, пропущено {}, ошибок {}'.format(
                    lib_id, rep.get('status'), c.get('merged'), c.get('skipped'), c.get('errors')))
                msgs += rep.get('errors', [])[:10]
        except Exception as exc:  # noqa: BLE001
            msgs.append('Импорт не выполнен: {}'.format(exc))
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()
        self.status.setText(msgs[0] if msgs else '')
        QtWidgets.QMessageBox.information(self, 'Ассеты', '\n'.join(msgs))

    def remove_imported(self):
        gone = self.backend.remove_imported(self.lib())
        self.status.setText('Убрано объектов: {}'.format(len(gone)))

    def match(self):
        rep = self.backend.match(list(self.indexes.values()))
        t = rep.get('totals', {})
        QtWidgets.QMessageBox.information(self, 'Сопоставить', 'Сопоставлено {matched}, неоднозначно {ambiguous}, '
                                                                'нет в библиотеке {missing}'.format(**t))


class MaxBackend(object):
    """Backend inside 3ds Max (assets_max.py): Flora from the library .max, MAF from the archives."""

    def __init__(self):
        import importlib.util
        import sys
        name = 'agr_tools_assets_max'
        if name not in sys.modules:
            spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name('assets_max.py'))
            mod = importlib.util.module_from_spec(spec)
            sys.modules[name] = mod
            spec.loader.exec_module(mod)
        self.mx = sys.modules[name]

    def load(self, cfg, cache_dir):
        return core.load_index(cache_dir, cfg['lib'])

    def scan(self, cfg, cache_dir):
        if cfg['lib'] == 'flora':
            return self.mx.scan_flora(cfg['root'], cache_dir, lib='flora',
                                      extra_preview_dirs=cfg.get('preview_dirs') or ())
        idx = core.scan_maf(cfg['root'], cache_dir, lib='maf', old_index=core.load_index(cache_dir, 'maf'))
        core.save_index(cache_dir, idx)
        return idx

    def remove_imported(self, lib):
        return self.mx.remove_imported(lib=lib)

    def import_assets(self, index, ids, settings, cache_dir):
        return self.mx.run_import(index, ids, settings, cache_dir)


_window = None


def show(backend=None):
    """One window per Max session; a second call raises the existing one."""
    global _window
    if _window is not None:
        try:
            _window.show()
            _window.raise_()
            _window.activateWindow()
            return _window
        except RuntimeError:
            _window = None
    _window = AssetsWindow(backend or MaxBackend(), parent=max_main_window())
    _window.show()
    return _window
