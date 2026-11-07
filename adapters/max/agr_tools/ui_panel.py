"""new-case: AGR Tools 0.6.0 dockable Qt panel for 3ds Max (#808).

Draws ui_model; all scene work goes through a backend object, so the same widget runs
inside Max (MaxBackend over pymxs + runtime.py) and under pytest-qt (a fake backend).
Colours come from the widget palette; nothing here hard-codes a colour.
"""
import json
import time

import agr_tools_roadmap as roadmap  # «Путь» data from agr-tools-suite.json (0.7.0, #860)
import agr_tools_ui_model as model  # registered in sys.modules by runtime._load_core / the tests
from agr_tools_ui_qt import QtCore, QtGui, QtWidgets, disable_accelerators

OBJECT_NAME = 'AgrToolsPanel'


def _params():
    """params_core (1.1 parameter form): the module runtime.panel() registered, else the sibling file."""
    import importlib.util
    import os
    import sys
    key = 'agr_tools_params_core'
    if key not in sys.modules:
        spec = importlib.util.spec_from_file_location(
            key, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'params_core.py'))
        mod = importlib.util.module_from_spec(spec)
        sys.modules[key] = mod
        spec.loader.exec_module(mod)
    return sys.modules[key]
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


# rail icon per block (plan make_mockup BLOCK_ICON, limited to icons shipped in this version)
_BLOCK_ICON = {'scene': 'census', 'model': 'drop', 'tex': 'textures', 'ucx': 'ucx', 'udim': 'texel',
               'atlas': 'atlas', 'place': 'pivot', 'qa': 'preflight', 'export': 'export', 'light': 'roadmap'}



def grey_button(parent, name, text, tip, style=QtCore.Qt.ToolButtonTextOnly):
    """A visible, disabled button: planned rows «в версии 1.x» (0.7, #860) and wip stage buttons «в работе, #1024».
    The tooltip still says what the row does; a disabled button never runs anything."""
    btn = QtWidgets.QToolButton(parent)
    btn.setObjectName(name)
    btn.setText(text)
    btn.setToolTip(tip)
    btn.setToolButtonStyle(style)
    btn.setEnabled(False)
    return btn


def _action_step(suite, a):
    """0 = check (scene unchanged), 1 = fix (copies/undo/files). *_apply and export always fix."""
    if a.id.endswith('_apply') or a.id == 'export':
        return 1
    return roadmap.STEP_OF_MODE[roadmap.row(suite, model.row_of(a.id))['mode']]


class RowScroll(QtWidgets.QScrollArea):
    """One row that scrolls sideways when the dock is narrow; its height always fits the whole row (big buttons,
    status, second row) plus the scroll bar, measured when the layout asks (after fonts and icons are set)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)

    def setWidget(self, widget):
        super().setWidget(widget)
        widget.installEventFilter(self)  # icons/theme set later grow the row: follow its layout requests
        self.updateGeometry()

    def eventFilter(self, obj, event):
        if obj is self.widget() and event.type() == QtCore.QEvent.LayoutRequest:
            self.updateGeometry()
        return super().eventFilter(obj, event)

    def sizeHint(self):
        hint = super().sizeHint()
        inner = self.widget()
        if inner is not None:
            hint.setHeight(inner.sizeHint().height() + self.horizontalScrollBar().sizeHint().height())
        return hint

    def minimumSizeHint(self):
        hint = super().minimumSizeHint()
        hint.setHeight(self.sizeHint().height())
        return hint


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
        self.expanded = True  # not checkable: a checked QToolButton gets the highlight fill in Max
        self.header.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        self.header.setArrowType(QtCore.Qt.DownArrow)
        self.header.setAutoRaise(True)
        font = self.header.font()
        font.setBold(True)
        self.header.setFont(font)
        self.header.clicked.connect(lambda: self._toggle(not self.expanded))
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
        self.expanded = on
        self.body.setVisible(on)
        self.header.setArrowType(QtCore.Qt.DownArrow if on else QtCore.Qt.RightArrow)

    def add(self, button):
        n = self.grid.count()
        self.grid.addWidget(button, n // 2, n % 2)


class AgrPanel(QtWidgets.QDockWidget):
    def __init__(self, backend, parent=None, clock=None):
        super().__init__(parent)
        self.backend = backend
        self._clock = clock or time.perf_counter
        self._mark = 0.0
        self._since = 0.0
        self._estimate = 0.0
        self.setObjectName(OBJECT_NAME)
        self.setWindowTitle('AGR Tools ' + model.VERSION)
        self.setAllowedAreas(QtCore.Qt.AllDockWidgetAreas)
        # Closing deletes the widget; the next open builds a fresh one from the saved dock state.
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.accelerators_disabled = disable_accelerators(self)
        self._running = False
        self._cancel = False
        self.report = None
        self.row_data = []
        self.buttons = {}
        self.form_tool = None  # 1.1: stage row whose parameter form is open (params_core.FIELDS)
        self.form_widgets = {}
        self.form_last = {}  # tool -> the values of its last run (this session)
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
        self.logo = logo
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

        self.suite = self.backend.suite()
        self.next_label = QtWidgets.QLabel('', body)
        self.next_label.setObjectName('agr_next_step')
        self.next_label.setWordWrap(True)
        lay.addWidget(self.next_label)
        work = QtWidgets.QHBoxLayout()
        work.setSpacing(4)
        self.rail = QtWidgets.QListWidget(body)
        self.rail.setObjectName('agr_rail')
        self.rail.setIconSize(QtCore.QSize(24, 24))
        self.rail.setFixedWidth(128)
        self.rail.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Expanding)
        self.pages = QtWidgets.QStackedWidget(body)
        work.addWidget(self.rail)
        work.addWidget(self.pages, 1)
        lay.addLayout(work, 3)
        self.sections = []
        self.section_blocks = []
        self.section_actions = []
        self.planned = {}
        self.stage_buttons = {}  # 1.0 stage buttons (#1024): action id -> button (big and small), disabled while wip
        layout_rail = model.rail(self.suite['blocks'], self.suite['rows'])
        self.blocks = [b for b, _, _ in layout_rail]
        self._build_path_page()
        for b, done, planned in layout_rail:
            self._build_block_page(b, done, planned)
        self.rail.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.rail.setCurrentRow(0)

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
        self._icons = {a.id: self.backend.icon(a.icon) for a in model.ALL_ACTIONS}
        self.apply_theme()
        self.refresh_path()

    def _scroll(self, widget):
        scroll = QtWidgets.QScrollArea(self.pages)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll.setWidget(widget)
        return scroll

    def _build_path_page(self):
        """«Путь»: the pipeline as clickable nodes in block colours, steps and buttons inside, live status."""
        item = QtWidgets.QListWidgetItem('Путь')
        item.setToolTip('Как пользоваться: блоки по порядку работы, что делает каждая кнопка и когда она нужна.')
        self.rail.addItem(item)
        holder = QtWidgets.QWidget(self.pages)
        hl = QtWidgets.QVBoxLayout(holder)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(2)
        self.nodes = {}
        self._build_stage_rail(holder, hl)
        self._build_form(holder, hl)
        for i, n in enumerate(roadmap.flow(self.suite, model.VERSION)):
            if i:
                arrow = QtWidgets.QLabel('↓', holder)
                arrow.setAlignment(QtCore.Qt.AlignHCenter)
                hl.addWidget(arrow)
            sec = Section('{} {}'.format(n['number'], n['title']), None, holder)
            sec.header.setToolTip('Когда: ' + n['when'])
            open_btn = QtWidgets.QToolButton(sec.body)
            open_btn.setObjectName('agr_open_' + n['id'])
            open_btn.setText('Открыть вкладку →')
            open_btn.setAutoRaise(True)
            open_btn.clicked.connect(lambda _=False, idx=n['number']: self.open_block(idx))
            status = QtWidgets.QLabel('', sec.body)
            status.setObjectName('agr_status_' + n['id'])
            sec.grid.addWidget(status, 0, 0)
            sec.grid.addWidget(open_btn, 0, 1)
            row_i = 1
            for step in n['steps']:
                lab = QtWidgets.QLabel('<i>{}</i>'.format(step['title']), sec.body)
                sec.grid.addWidget(lab, row_i, 0, 1, 2)
                row_i += 1
                for x in step['buttons']:
                    r = roadmap.row(self.suite, x['id'])
                    b = QtWidgets.QToolButton(sec.body)
                    b.setObjectName('agr_path_' + x['id'])
                    b.setText(x['label'] if x['state'] == 'done' else '{} · {}'.format(
                        x['label'], roadmap.planned_label(r)))
                    b.setToolTip(roadmap.tooltip(self.suite, r))
                    b.setToolButtonStyle(QtCore.Qt.ToolButtonTextOnly)
                    b.setAutoRaise(True)
                    b.setEnabled(x['state'] == 'done')
                    b.clicked.connect(lambda _=False, idx=n['number']: self.open_block(idx))
                    q = QtWidgets.QToolButton(sec.body)
                    q.setObjectName('agr_help_' + x['id'])
                    q.setText('?')
                    q.setToolTip('Карточка кнопки: что, когда, вход, результат, связанные кнопки')
                    q.clicked.connect(lambda _=False, rid=x['id']: self.show_card(rid))
                    sec.grid.addWidget(b, row_i, 0)
                    sec.grid.addWidget(q, row_i, 1, QtCore.Qt.AlignLeft)
                    row_i += 1
            hl.addWidget(sec)
            self.nodes[n['id']] = (sec, status)
        hl.addStretch()
        self.pages.addWidget(self._scroll(holder))

    def _stage_button(self, parent, a, big):
        """A 1.0 stage button (#1024): disabled while wip, tooltip «в работе, #1024» + what the plan row does."""
        tip = model.tooltip(a) + '\n' + roadmap.tooltip(self.suite, roadmap.row(self.suite, a.tool))
        btn = grey_button(parent, 'agr_wip_' + a.tool, a.label, tip,
                          QtCore.Qt.ToolButtonTextUnderIcon if big else QtCore.Qt.ToolButtonIconOnly)
        btn.setIconSize(QtCore.QSize(36, 36) if big else QtCore.QSize(20, 20))
        btn.setAutoRaise(not big)
        btn.setEnabled(not a.wip)
        btn.clicked.connect(lambda _=False, key=a.id: self.run(key))
        self.stage_buttons[a.id] = btn
        return btn

    def _build_stage_rail(self, holder, hl):
        """1.0 conveyor (#1024): a row of big stage buttons (icon, label, stage status from the passport), under each
        a second row with the stage's small buttons (plan stages[].rows minus big_button)."""
        head = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel('<b>{}</b>'.format(model.MENU_100), holder)
        title.setObjectName('agr_stage_title')
        head.addWidget(title)
        head.addStretch()
        dock = QtWidgets.QToolButton(holder)  # 1.1: «Claude-док» of the agent stage (agentbridge_max.agent_dock)
        dock.setObjectName('agr_agent_dock')
        dock.setText(model.DOCK_LABEL)
        dock.setToolTip(model.DOCK_TIP)
        dock.setIcon(self.backend.icon(model.DOCK_ICON))
        dock.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        dock.setAutoRaise(True)
        dock.setEnabled(hasattr(self.backend, 'agent_dock'))
        dock.clicked.connect(self.open_agent_dock)
        self.dock_btn = dock
        head.addWidget(dock)
        hl.addLayout(head)
        row_w = QtWidgets.QWidget()
        row = QtWidgets.QHBoxLayout(row_w)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        self.stages = {}
        for st in model.stage_rail(self.suite):
            col = QtWidgets.QWidget(row_w)
            col.setObjectName('agr_stage_{}'.format(st.id))
            cl = QtWidgets.QVBoxLayout(col)
            cl.setContentsMargins(0, 0, 0, 0)
            cl.setSpacing(1)
            big = self._stage_button(col, st.big, True)
            big.setText(st.label)
            cl.addWidget(big, 0, QtCore.Qt.AlignHCenter)
            status = QtWidgets.QLabel('', col)
            status.setObjectName('agr_stage_status_{}'.format(st.id))
            status.setAlignment(QtCore.Qt.AlignHCenter)
            cl.addWidget(status)
            second = QtWidgets.QHBoxLayout()
            second.setSpacing(1)
            second.addStretch()
            small = [self._stage_button(col, a, False) for a in st.small]
            for b in small:
                second.addWidget(b)
            second.addStretch()
            cl.addLayout(second)
            cl.addStretch()
            row.addWidget(col)
            self.stages[st.id] = (big, status, small)
        row.addStretch()
        scroll = RowScroll(holder)
        scroll.setObjectName('agr_stage_rail')
        scroll.setWidget(row_w)
        hl.addWidget(scroll)

    # ---- 1.1 parameter form of the stage buttons ------------------------------------------------------------
    def _build_form(self, holder, hl):
        """A compact form under the stage rail: the options of one stage row (params_core.FIELDS), defaults from
        the passport and the last run; «Выполнить» = preview, the next «Выполнить» with the same values = apply."""
        box = QtWidgets.QGroupBox('', holder)
        box.setObjectName('agr_form')
        lay = QtWidgets.QVBoxLayout(box)
        lay.setContentsMargins(6, 4, 6, 4)
        self.form_hint = QtWidgets.QLabel('', box)
        self.form_hint.setObjectName('agr_form_hint')
        self.form_hint.setWordWrap(True)
        lay.addWidget(self.form_hint)
        self.form_grid = QtWidgets.QFormLayout()
        self.form_grid.setFieldGrowthPolicy(QtWidgets.QFormLayout.AllNonFixedFieldsGrow)
        lay.addLayout(self.form_grid)
        row = QtWidgets.QHBoxLayout()
        self.form_run = QtWidgets.QPushButton('Выполнить', box)
        self.form_run.setObjectName('agr_form_run')
        self.form_run.clicked.connect(self.run_form)
        self.form_close = QtWidgets.QPushButton('Скрыть', box)
        self.form_close.setObjectName('agr_form_close')
        self.form_close.clicked.connect(self.close_form)
        row.addStretch()
        row.addWidget(self.form_run)
        row.addWidget(self.form_close)
        lay.addLayout(row)
        box.setVisible(False)
        self.form_box = box
        hl.addWidget(box)

    def _form_context(self, tool):
        ctx = self.backend.form_context(tool) if hasattr(self.backend, 'form_context') else {}
        ctx = dict(ctx or {})
        ctx['last'] = dict(self.form_last.get(tool) or {})
        return ctx

    def open_form(self, key):
        """Show the parameter form of a stage row filled with its defaults (passport, last run)."""
        a = model.action(key)
        params = _params()
        fields = params.fields(a.tool)
        values = params.defaults(a.tool, self._form_context(a.tool))
        while self.form_grid.rowCount():
            self.form_grid.removeRow(0)
        self.form_widgets = {}
        for f in fields:
            if f.kind == 'bool':
                w = QtWidgets.QCheckBox(self.form_box)
                w.setChecked(bool(values.get(f.key)))
            elif f.kind == 'choice':
                w = QtWidgets.QComboBox(self.form_box)
                w.addItems(list(f.choices))
                v = values.get(f.key)
                if v in f.choices:
                    w.setCurrentIndex(list(f.choices).index(v))
            else:
                w = QtWidgets.QLineEdit(self.form_box)
                w.setText(params.text_of(f, values.get(f.key)))
                w.setPlaceholderText(f.hint)
            w.setObjectName('agr_form_' + f.key)
            w.setToolTip(f.hint)
            self.form_grid.addRow(f.label, w)
            self.form_widgets[f.key] = (f, w)
        self.form_tool = a.tool
        self.form_box.setTitle('Параметры: {} ({})'.format(a.label, a.tool))
        gap = params.missing(a.tool, params.parse(a.tool, self.form_values()))
        self.form_hint.setText('Заполните: ' + '; '.join(gap) if gap else
                               'Проверьте значения и нажмите «Выполнить»: сначала предпросмотр, '
                               'повторное «Выполнить» с теми же значениями применяет его.')
        self.form_box.setVisible(True)
        self.rail.setCurrentRow(0)  # the form lives on «Путь» under the stage rail (a macro may open it from any page)
        self.status.setText('{}: заполните параметры и нажмите «Выполнить»'.format(a.label))
        return self.form_box

    def form_values(self):
        out = {}
        for key, (f, w) in self.form_widgets.items():
            if f.kind == 'bool':
                out[key] = w.isChecked()
            elif f.kind == 'choice':
                out[key] = w.currentText()
            else:
                out[key] = w.text()
        return out

    def close_form(self):
        self.form_box.setVisible(False)
        self.form_tool = None

    def run_form(self):
        """«Выполнить»: options from the form; an empty required field or a bad value is said, never run."""
        if self.form_tool is None:
            return None
        params = _params()
        tool = self.form_tool
        try:
            options = params.parse(tool, self.form_values())
        except ValueError as exc:
            self.form_hint.setText(str(exc))
            self.status.setText('{}: {}'.format(model.action(tool).label, exc))
            return None
        gap = params.missing(tool, options)
        if gap:
            self.form_hint.setText('Заполните: ' + '; '.join(gap))
            self.status.setText('{}: заполните {}'.format(model.action(tool).label, '; '.join(gap)))
            return None
        self.form_last[tool] = options
        return self.run(model.action(tool).id, options=options)

    def open_agent_dock(self):
        """«Claude-док» (1.1): the dock of branch U through the backend; an error is shown, never swallowed."""
        try:
            self.backend.agent_dock()
            self.status.setText('{}: открыт'.format(model.DOCK_LABEL))
        except Exception as exc:  # noqa: BLE001 - shown in the panel and in Listener by the backend
            self.status.setText('{}: {}: {}'.format(model.DOCK_LABEL, type(exc).__name__, exc))
            if hasattr(self.backend, 'log_error'):
                self.backend.log_error('agent.dock', exc)

    def refresh_stages(self):
        """Stage status under each big button from the project passport (reader: branch F; none = «не начат»).
        A passport that cannot be read is said so on every stage, never shown as a guessed status."""
        passport = self.backend.passport() if hasattr(self.backend, 'passport') else None
        try:
            status = {st.id: model.STAGE_STATUS_RU[st.status] for st in model.stage_rail(self.suite, passport)}
            error = ''
        except ValueError as exc:
            status = {sid: 'паспорт: ошибка' for sid in self.stages}
            error = str(exc)
        for sid, (_big, label, _small) in self.stages.items():
            label.setText(status[sid])
            label.setToolTip(error)
        self.stage_status = status
        return status

    def _build_block_page(self, b, done, planned):
        item = QtWidgets.QListWidgetItem('{} {}'.format(b['number'], b['short_ru']))
        item.setToolTip('{}\nКогда: {}'.format(b['title_ru'], b['when_ru']))
        self.rail.addItem(item)
        holder = QtWidgets.QWidget(self.pages)
        hl = QtWidgets.QVBoxLayout(holder)
        hl.setContentsMargins(0, 0, 0, 0)
        head = QtWidgets.QLabel('<b>{} {}</b><br>{}'.format(b['number'], b['title_ru'], b['when_ru']), holder)
        head.setWordWrap(True)
        hl.addWidget(head)
        for step, title in enumerate(roadmap.STEP_RU):
            acts = [a for a in done if _action_step(self.suite, a) == step]
            rows_ = [r for r in planned if roadmap.STEP_OF_MODE[r['mode']] == step]
            if not acts and not rows_:
                continue
            sec = Section(title, None, holder)
            for a in acts:
                btn = QtWidgets.QToolButton(sec.body)
                btn.setObjectName('agr_' + a.id)
                btn.setText(a.label)
                btn.setIconSize(QtCore.QSize(24, 24))
                btn.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
                btn.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
                btn.setToolTip(model.tooltip(a) + '\n' + roadmap.tooltip(
                    self.suite, roadmap.row(self.suite, model.row_of(a.id))))
                btn.clicked.connect(lambda _=False, key=a.id: self.run(key))
                sec.add(btn)
                self.buttons[a.id] = btn
            for r in rows_:
                btn = grey_button(sec.body, 'agr_planned_' + r['id'],
                                  '{} · {}'.format(r['label_ru'], roadmap.planned_label(r)), roadmap.tooltip(self.suite, r))
                btn.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
                sec.add(btn)
                self.planned[r['id']] = btn
            hl.addWidget(sec)
            self.sections.append(sec)
            self.section_blocks.append(b)
            self.section_actions.append(acts)
        hl.addStretch()
        self.pages.addWidget(self._scroll(holder))

    def open_block(self, number):
        self.rail.setCurrentRow(number + 1)

    def card(self, row_id):
        return roadmap.card(self.suite, roadmap.row(self.suite, row_id), model.VERSION)

    def show_card(self, row_id):
        c = self.card(row_id)
        box = QtWidgets.QMessageBox(self)
        box.setWindowTitle('AGR Tools · ' + c['title'])
        box.setText(roadmap.card_text(c))
        box.setModal(False)
        box.show()
        self._card_box = box
        return box

    def live_status(self):
        reports = {}
        for tool, rep in (self.backend.last_reports() or {}).items():
            if tool in model.BY_TOOL:
                reports[model.row_of(model.BY_TOOL[tool].id)] = rep
        return roadmap.live_status(self.suite, reports, model.VERSION)

    def refresh_path(self):
        """Live status on the diagram + «Следующий шаг» from the last reports of this scene; stage statuses."""
        self.refresh_stages()
        status = self.live_status()
        acc = self.accents()
        for bid, (_sec, label) in self.nodes.items():
            s = status[bid]
            label.setText('Статус: ' + roadmap.STATUS_RU[s])
            pal = label.palette()
            if s in ('ok', 'errors'):
                pal.setColor(QtGui.QPalette.WindowText, acc['ok' if s == 'ok' else 'error'])
            else:
                pal.setColor(QtGui.QPalette.WindowText, self.palette().color(QtGui.QPalette.WindowText))
            label.setPalette(pal)
        text, _ = roadmap.next_step(self.suite, status)
        self.next_label.setText('Следующий шаг: ' + text)
        self.status_by_block = status
        return status

    # ---- theme --------------------------------------------------------------------------
    def _base_text(self):
        pal = self.palette()
        return _rgb(pal.color(QtGui.QPalette.Base)), _rgb(pal.color(QtGui.QPalette.Text))

    def block_color(self, b):
        base, text = self._base_text()
        window = _rgb(self.palette().color(QtGui.QPalette.Window))
        return QtGui.QColor(*model.block_accent(b['hue'], window, base, text))

    def apply_theme(self):
        """Block colours (rail, section stripes, headers, icon tints) from the current palette (Max Dark/Light)."""
        base, text = self._base_text()
        colors = {b['id']: self.block_color(b) for b in self.blocks}
        for sec, b, actions in zip(self.sections, self.section_blocks, self.section_actions):
            color = colors[b['id']]
            sec.set_color(color)
            for a in actions:
                self.buttons[a.id].setIcon(tint(self._icons[a.id], color))
        for i, b in enumerate(self.blocks):
            item = self.rail.item(i + 1)
            item.setForeground(QtGui.QBrush(colors[b['id']]))
            item.setIcon(tint(self.backend.icon(_BLOCK_ICON[b['id']]), colors[b['id']]))
            self.nodes[b['id']][0].set_color(colors[b['id']])
        for aid, btn in self.stage_buttons.items():  # stage buttons in the colour of their plan row's block
            btn.setIcon(tint(self._icons[aid], colors[roadmap.row(self.suite, model.BY_ID[aid].tool)['block']]))
        self.rail.item(0).setIcon(tint(self.backend.icon('roadmap'), QtGui.QColor(*text)))
        self.logo.setPixmap(tint(self.backend.icon('tools'), QtGui.QColor(*text), (36,)).pixmap(36, 36))
        self._theme_key = (base, text)

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QtCore.QEvent.PaletteChange and getattr(self, '_theme_key', None) is not None                 and self._base_text() != self._theme_key:
            try:
                self.apply_theme()
            except ValueError as exc:  # unreachable 3:1 contrast: keep the old colours, say so (never pale)
                self.status.setText('Цвета блоков: ' + str(exc))
                return
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
        for aid, b in self.stage_buttons.items():  # a wip stage button stays disabled after a run too
            b.setEnabled(not busy and not model.BY_ID[aid].wip)
        self.rail.setEnabled(not busy)
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

    def _on_batch_item(self):
        """After one object: pump the Qt loop on elapsed time, not every N objects.

        Max 2024 blocked for 1.36 s inside a 25-object chunk. Predicting the next
        object from the one just finished keeps the gap under 0.1 s without calling
        the tool once per object (that would redo the MaxScript setup on 2026).
        Cancel is not raised here: the chunk's results would be lost. run_batched
        reads the flag before the next chunk (about 0.9 s later on Max 2024).
        """
        now = self._clock()
        cost = now - self._mark
        self._mark = now
        pump, self._since, self._estimate = model.object_pump(
            self._since, self._estimate, cost, model.PUMP_BUDGET_S)
        if pump:
            QtWidgets.QApplication.processEvents()
            self._mark = self._clock()

    def run(self, key, options=None):
        """Panel entry for every action. Re-entry while running is refused (processEvents).
        1.1: a stage row with a parameter form (params_core) pressed without options opens its form instead of
        running without parameters (the 1.0 panel passed only the selection and the row refused)."""
        if self._running:
            return None
        a = model.action(key)
        if a.wip:  # 1.0 stage button still in work (#1024): never runs, says so
            self.status.setText('{}: {}'.format(a.label, model.WIP_TIP))
            return None
        if options is None and _params().has_form(a.tool):
            self.open_form(a.id)
            return None
        self._cancel = False
        self.set_busy(True)
        self.backend.progress_start(a.label)
        started = time.perf_counter()
        report, error = None, None
        try:
            scope_all = self.scope.currentIndex() == 1
            if a.batch:
                nodes = self.backend.targets(scope_all)
                self._mark = self._clock()
                self._since = 0.0
                self._estimate = 0.0
                report = model.run_batched(
                    a.tool, lambda chunk: self.backend.run_chunk(
                        a.tool, chunk, on_item=self._on_batch_item), nodes, CHUNK,
                    lambda d, t: self._progress(a.label, d, t), self._cancelled)
                self.backend.select_failed(report)
                self.backend.log(report)
            else:
                self.bar.setRange(0, 0)  # busy: one indivisible runtime call
                QtWidgets.QApplication.processEvents()
                report = (self.backend.run_tool(a.tool, scope_all) if options is None else
                          self.backend.run_tool(a.tool, scope_all, options))
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
        self.refresh_path()
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
        self.status.setText('Остановлено' if error else ('Есть ошибки' if bad else 'Готово'))
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
