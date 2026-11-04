"""new-case: AGR Tools 0.6.0 dockable Qt panel for 3ds Max (#808).

Draws ui_model; all scene work goes through a backend object, so the same widget runs
inside Max (MaxBackend over pymxs + runtime.py) and under pytest-qt (a fake backend).
Colours come from the widget palette; nothing here hard-codes a colour.
"""
import json
import time

import agr_tools_ui_model as model  # registered in sys.modules by runtime._load_core / the tests
from agr_tools_ui_qt import QtCore, QtGui, QtWidgets, disable_accelerators

OBJECT_NAME = 'AgrToolsPanel'
CHUNK = 25
COLUMNS = ('Объект', 'Проверка', 'Результат', 'Треб.')


def _rgb(color):
    return (color.red(), color.green(), color.blue())


def tint(icon, color, sizes=(24, 30, 36, 48)):
    """Recolour a monochrome icon with a section accent (alpha kept, colour replaced)."""
    out = QtGui.QIcon()
    for s in sizes:
        pm = icon.pixmap(s, s)
        if pm.isNull():
            continue
        img = pm.toImage().convertToFormat(QtGui.QImage.Format_ARGB32)
        p = QtGui.QPainter(img)
        p.setCompositionMode(QtGui.QPainter.CompositionMode_SourceIn)
        p.fillRect(img.rect(), color)
        p.end()
        out.addPixmap(QtGui.QPixmap.fromImage(img))
    return out


class Section(QtWidgets.QWidget):
    """Collapsible block: accent stripe + header button + grid of action buttons in two columns."""

    def __init__(self, title, color=None, parent=None):
        super().__init__(parent)
        self.color = color
        outer = QtWidgets.QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(4)
        self.stripe = QtWidgets.QFrame(self)
        self.stripe.setFixedWidth(4)
        self.stripe.setAutoFillBackground(True)
        outer.addWidget(self.stripe)
        col = QtWidgets.QWidget(self)
        outer.addWidget(col, 1)
        lay = QtWidgets.QVBoxLayout(col)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)
        self.header = QtWidgets.QToolButton(col)
        self.header.setText(title)
        self.header.setCheckable(True)
        self.header.setChecked(True)
        self.header.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        self.header.setArrowType(QtCore.Qt.DownArrow)
        self.header.setAutoRaise(True)
        font = self.header.font()
        font.setBold(True)
        self.header.setFont(font)
        self.header.toggled.connect(self._toggle)
        self.body = QtWidgets.QWidget(col)
        self.grid = QtWidgets.QGridLayout(self.body)
        self.grid.setContentsMargins(4, 0, 0, 4)
        self.grid.setSpacing(3)
        lay.addWidget(self.header)
        lay.addWidget(self.body)
        if color is not None:
            self.set_color(color)

    def set_color(self, color):
        self.color = color
        pal = self.stripe.palette()
        pal.setColor(QtGui.QPalette.Window, color)
        self.stripe.setPalette(pal)
        hp = self.header.palette()
        hp.setColor(QtGui.QPalette.ButtonText, color)
        hp.setColor(QtGui.QPalette.WindowText, color)
        self.header.setPalette(hp)

    def _toggle(self, on):
        self.body.setVisible(on)
        self.header.setArrowType(QtCore.Qt.DownArrow if on else QtCore.Qt.RightArrow)

    def add(self, button):
        n = self.grid.count()
        self.grid.addWidget(button, n // 2, n % 2)


class AgrPanel(QtWidgets.QDockWidget):
    def __init__(self, backend, parent=None):
        super().__init__(parent)
        self.backend = backend
        self.setObjectName(OBJECT_NAME)
        self.setWindowTitle('AGR Tools ' + model.VERSION)
        self.setAllowedAreas(QtCore.Qt.AllDockWidgetAreas)
        self.accelerators_disabled = disable_accelerators(self)
        self._running = False
        self._cancel = False
        self.report = None
        self.row_data = []
        self.buttons = {}
        self._build()
        self.dockLocationChanged.connect(self.save_state)
        self.topLevelChanged.connect(self.save_state)

    # ---- layout -------------------------------------------------------------------------
    def _build(self):
        body = QtWidgets.QWidget(self)
        lay = QtWidgets.QVBoxLayout(body)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(4)
        head = QtWidgets.QHBoxLayout()
        logo = QtWidgets.QLabel(body)
        logo.setPixmap(self.backend.icon('tools').pixmap(36, 36))
        title = QtWidgets.QLabel('<b>AGR Tools</b> ' + model.VERSION, body)
        head.addWidget(logo)
        head.addWidget(title)
        head.addStretch()
        head.addWidget(QtWidgets.QLabel('Область:', body))
        self.scope = QtWidgets.QComboBox(body)
        self.scope.addItems(['Выделение', 'Вся сцена'])
        self.scope.setToolTip('Выделение: выделенные объекты (если ничего не выделено, вся геометрия). '
                              'Вся сцена: вся геометрия.')
        head.addWidget(self.scope)
        self.profile = QtWidgets.QComboBox(body)
        self.profile.addItems(['НПМ/ВПМ: по имени FBX'])
        self.profile.setEnabled(False)
        self.profile.setToolTip('Тип модели (НПМ/ВПМ, ОКС/Ground) берётся из AGR_EXPORT_PATH каждого объекта; '
                                'значения по умолчанию нет.')
        head.addWidget(self.profile)
        lay.addLayout(head)

        scroll = QtWidgets.QScrollArea(body)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        holder = QtWidgets.QWidget(scroll)
        hl = QtWidgets.QVBoxLayout(holder)
        hl.setContentsMargins(0, 0, 0, 0)
        self.sections = []
        self.section_actions = []
        for title, actions in model.sections():
            sec = Section(title, None, holder)
            self.section_actions.append(actions)
            for a in actions:
                b = QtWidgets.QToolButton(sec.body)
                b.setObjectName('agr_' + a.id)
                b.setText(a.label)
                b.setIconSize(QtCore.QSize(24, 24))
                b.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
                b.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
                b.setToolTip(model.tooltip(a))
                b.clicked.connect(lambda _=False, key=a.id: self.run(key))
                sec.add(b)
                self.buttons[a.id] = b
            hl.addWidget(sec)
            self.sections.append(sec)
        hl.addStretch()
        scroll.setWidget(holder)
        lay.addWidget(scroll, 3)

        prog = QtWidgets.QHBoxLayout()
        self.status = QtWidgets.QLabel('Готово', body)
        self.bar = QtWidgets.QProgressBar(body)
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        self.cancel_btn = QtWidgets.QToolButton(body)
        self.cancel_btn.setText('Отмена')
        self.cancel_btn.setIcon(self.backend.icon('cancel'))
        self.cancel_btn.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self.request_cancel)
        prog.addWidget(self.status, 2)
        prog.addWidget(self.bar, 3)
        prog.addWidget(self.cancel_btn)
        lay.addLayout(prog)

        self.summary = QtWidgets.QLabel('', body)
        lay.addWidget(self.summary)
        self.table = QtWidgets.QTableWidget(0, len(COLUMNS), body)
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.cellClicked.connect(self._row_clicked)
        lay.addWidget(self.table, 4)

        foot = QtWidgets.QHBoxLayout()
        self.select_btn = QtWidgets.QToolButton(body)
        self.select_btn.setText('Выделить ошибки')
        self.select_btn.setIcon(self.backend.icon('select'))
        self.select_btn.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        self.select_btn.clicked.connect(self.select_errors)
        self.save_btn = QtWidgets.QToolButton(body)
        self.save_btn.setText('Сохранить отчёт JSON…')
        self.save_btn.clicked.connect(self.save_report)
        foot.addWidget(self.select_btn)
        foot.addWidget(self.save_btn)
        foot.addStretch()
        lay.addLayout(foot)
        self.setWidget(body)
        self._icons = {a.id: self.backend.icon(a.icon) for a in model.ACTIONS}
        self.apply_theme()

    # ---- theme --------------------------------------------------------------------------
    def _base_text(self):
        pal = self.palette()
        return _rgb(pal.color(QtGui.QPalette.Base)), _rgb(pal.color(QtGui.QPalette.Text))

    def apply_theme(self):
        """Section stripes, headers and icon tints from the current palette (Max Dark/Light)."""
        base, text = self._base_text()
        for idx, (sec, actions) in enumerate(zip(self.sections, self.section_actions)):
            color = QtGui.QColor(*model.section_accent(idx, base, text))
            sec.set_color(color)
            for a in actions:
                self.buttons[a.id].setIcon(tint(self._icons[a.id], color))
        self._theme_key = (base, text)

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QtCore.QEvent.PaletteChange and getattr(self, '_theme_key', None) is not None                 and self._base_text() != self._theme_key:
            self.apply_theme()
            if self.report is not None:
                self.show_report(self.report)

    def accents(self):
        base, text = self._base_text()
        return {k: QtGui.QColor(*model.accent(k, base, text)) for k in ('error', 'ok', 'warn')}

    # ---- running ------------------------------------------------------------------------
    def set_busy(self, busy):
        self._running = busy
        for b in self.buttons.values():
            b.setEnabled(not busy)
        self.scope.setEnabled(not busy)
        self.select_btn.setEnabled(not busy)
        self.save_btn.setEnabled(not busy)
        self.cancel_btn.setEnabled(busy)

    def request_cancel(self):
        self._cancel = True
        self.status.setText('Отмена…')

    def _cancelled(self):
        QtWidgets.QApplication.processEvents()
        return self._cancel or self.backend.progress_cancelled()

    def _progress(self, label, done, total):
        pct = model.percent(done, total)
        self.bar.setValue(pct)
        self.status.setText('{}: {} / {} объектов'.format(label, done, total))
        if not self.backend.progress_update(pct):
            self._cancel = True
        QtWidgets.QApplication.processEvents()

    def run(self, key):
        """Panel entry for every action. Re-entry while running is refused (processEvents)."""
        if self._running:
            return None
        a = model.action(key)
        self._cancel = False
        self.set_busy(True)
        self.backend.progress_start(a.label)
        started = time.perf_counter()
        report, error = None, None
        try:
            scope_all = self.scope.currentIndex() == 1
            if a.batch:
                nodes = self.backend.targets(scope_all)
                report = model.run_batched(
                    a.tool, lambda chunk: self.backend.run_chunk(a.tool, chunk), nodes, CHUNK,
                    lambda d, t: self._progress(a.label, d, t), self._cancelled)
                self.backend.select_failed(report)
                self.backend.log(report)
            else:
                self.bar.setRange(0, 0)  # busy: one indivisible runtime call
                QtWidgets.QApplication.processEvents()
                report = self.backend.run_tool(a.tool, scope_all)
        except model.Cancelled as exc:
            error = 'Отменено: {}'.format(exc)
            report = exc.partial
        except Exception as exc:  # shown in the panel and re-raised to Listener by the backend
            error = '{}: {}'.format(type(exc).__name__, exc)
            self.backend.log_error(a.tool, exc)
        finally:
            self.bar.setRange(0, 100)
            self.backend.progress_end()
            self.set_busy(False)
        self.last_seconds = time.perf_counter() - started
        self.show_report(report, error)
        return report

    # ---- results ------------------------------------------------------------------------
    def show_report(self, report, error=None):
        self.report = report
        acc = self.accents()
        self.row_data = model.rows(report) if report is not None else []
        self.table.setRowCount(len(self.row_data))
        for i, r in enumerate(self.row_data):
            a = model.BY_TOOL.get(r.check)
            reqs = ', '.join(a.reqs) if a else ''
            res = 'OK' if r.ok else (r.code + (': ' + r.detail if r.detail else ''))
            for j, text in enumerate((r.name, a.label if a else r.check, res, reqs)):
                item = QtWidgets.QTableWidgetItem(text)
                if j == 2:
                    item.setForeground(QtGui.QBrush(acc['ok' if r.ok else 'error']))
                    item.setIcon(self.backend.icon('ok' if r.ok else 'error'))
                self.table.setItem(i, j, item)
        self.table.resizeColumnsToContents()
        text = model.summary(self.row_data) if self.row_data else ''
        if error:
            text = (text + ' · ' if text else '') + error
        self.summary.setText(text)
        pal = self.summary.palette()
        bad = error or any(not r.ok for r in self.row_data)
        pal.setColor(QtGui.QPalette.WindowText, acc['error'] if bad else acc['ok'])
        self.summary.setPalette(pal)
        self.status.setText('Готово' if not error else 'Остановлено')
        self.bar.setValue(100 if report is not None and not error else self.bar.value())

    def _row_clicked(self, row, _col):
        if 0 <= row < len(self.row_data):
            self.backend.select_row(self.row_data[row])

    def select_errors(self):
        if self.report is not None:
            self.backend.select_failed(self.report)

    def save_report(self):
        if self.report is None:
            return None
        path = self.backend.save_path()
        if not path:
            return None
        with open(path, 'x', encoding='utf-8') as f:  # never overwrites
            json.dump(self.report, f, ensure_ascii=False, indent=1, allow_nan=False)
        return path

    # ---- dock state ---------------------------------------------------------------------
    def state(self):
        main = self.parent()
        area = main.dockWidgetArea(self) if isinstance(main, QtWidgets.QMainWindow) else 2
        area = int(getattr(area, 'value', area))
        geo = bytes(self.saveGeometry().toBase64()).decode('ascii') if self.isFloating() else ''
        return model.parse_dock(json.dumps({'floating': self.isFloating(), 'area': area,
                                            'geometry': geo, 'visible': self.isVisible()}))

    def save_state(self, *_):
        self.backend.save_settings(model.dump_dock(self.state()))

    def closeEvent(self, event):
        self.save_state()
        super().closeEvent(event)


def place(panel, main, state):
    """Dock (or float) the panel where it was last time."""
    if isinstance(main, QtWidgets.QMainWindow):
        area = QtCore.Qt.DockWidgetArea(state['area'])
        main.addDockWidget(area, panel)
    if state['floating']:
        panel.setFloating(True)
        if state['geometry']:
            panel.restoreGeometry(QtCore.QByteArray.fromBase64(state['geometry'].encode('ascii')))
