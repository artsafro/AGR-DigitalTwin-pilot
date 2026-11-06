"""new-case: the Claude dock inside 3ds Max (#1024 branch U, agent.dock): a thin QDockWidget over agr_dock_core.

Input line, streamed answer text, one card per tool call; a card of a held D108 preview gets «Применить». The press
(1) confirms that preview id inside this Max process (agr_gate.confirm - the only way a plan can run) and (2) asks
the daemon to apply it (POST /agr/apply) on a worker thread; the Max side work runs on the main thread through the
listener's queue (Qt timer), so the UI never blocks and the scene is never touched off the main thread. The answer
(applied: one undo record; rolled_back: the question) is shown on the card.

The CLI runs in a QProcess (agr_dock_core.command); its session id is kept per document so the next Max session
resumes it (`--resume`). PySide6 (Max 2025+) or PySide2 (Max 2024).
"""
import json
import os
import sys
import threading
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import agr_dock_core as core  # noqa: E402
import agr_gate  # noqa: E402
import agr_registry  # noqa: E402

try:
    from PySide6 import QtCore, QtWidgets
    Signal = QtCore.Signal
except ImportError:  # 3ds Max 2024
    from PySide2 import QtCore, QtWidgets
    Signal = QtCore.Signal


def post_apply(url, token, preview_id, timeout=3600):
    """POST <daemon>/agr/apply (worker thread)."""
    base = url.rsplit('/mcp', 1)[0]
    req = urllib.request.Request(base + '/agr/apply', data=json.dumps({'preview_id': preview_id}).encode('utf-8'),
                                 headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'},
                                 method='POST')
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as exc:
        try:
            return json.loads(exc.read().decode('utf-8'))
        except ValueError:
            return {'status': 'error', 'error': str(exc)}
    except OSError as exc:
        return {'status': 'error', 'error': str(exc)}


class _Bus(QtCore.QObject):
    applied = Signal(str, object)


class Card(QtWidgets.QFrame):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setFrameShape(QtWidgets.QFrame.StyledPanel)
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(6, 4, 6, 4)
        self.title = QtWidgets.QLabel(title)
        self.title.setWordWrap(True)
        self.body = QtWidgets.QLabel('')
        self.body.setWordWrap(True)
        self.body.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        self.button = QtWidgets.QPushButton('Применить')
        self.button.setVisible(False)
        self.tool = ''
        lay.addWidget(self.title)
        lay.addWidget(self.body)
        lay.addWidget(self.button)
        self.preview_id = None


class AgentDock(QtWidgets.QDockWidget):
    def __init__(self, repo, exe=None, profile='modeller', auth='local', parent=None, doc=None, daemon=None):
        super().__init__('AGR Claude', parent)
        self.setObjectName('AGRClaudeDock')
        self.repo, self.profile, self.auth = repo, core.check_profile(profile), auth
        self.exe = exe or os.path.join(os.path.expanduser('~'), '.local', 'bin', 'claude.exe')
        self.doc = doc or 'untitled'
        self.daemon = daemon  # registry entry {url, token}
        self.stream = core.Stream()
        self.proc = None
        self.cards = {}
        self.bus = _Bus()
        self.bus.applied.connect(self._on_applied)
        w = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(w)
        self.status = QtWidgets.QLabel('')
        self.log = QtWidgets.QTextBrowser()
        self.cards_box = QtWidgets.QVBoxLayout()
        cards_w = QtWidgets.QWidget()
        cards_w.setLayout(self.cards_box)
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(cards_w)
        row = QtWidgets.QHBoxLayout()
        self.input = QtWidgets.QLineEdit()
        self.input.setPlaceholderText('Задача агенту…')
        self.send_btn = QtWidgets.QPushButton('Отправить')
        row.addWidget(self.input)
        row.addWidget(self.send_btn)
        lay.addWidget(self.status)
        lay.addWidget(self.log, 3)
        lay.addWidget(scroll, 2)
        lay.addLayout(row)
        self.setWidget(w)
        self.send_btn.clicked.connect(self.send)
        self.input.returnPressed.connect(self.send)
        self._set_status()

    def _set_status(self, extra=''):
        sid = self.stream.session or core.load_session(self.doc)
        self.status.setText('профиль {} · {} · сессия {}{}'.format(self.profile, self.auth, (sid or '—')[:8],
                                                                   ' · ' + extra if extra else ''))

    # -- CLI ------------------------------------------------------------------------------------------------------
    def start_cli(self):
        if self.proc is not None and self.proc.state() != QtCore.QProcess.NotRunning:
            return self.proc
        cfg = core.write_mcp_config({'mcpServers': {'agr': {'type': 'http', 'url': self.daemon['url'],
                                                            'headers': {'Authorization': 'Bearer '
                                                                        + self.daemon['token']}}}})
        argv = core.command(self.exe, cfg, session=core.load_session(self.doc))
        env = core.environment(os.environ, self.auth)
        proc = QtCore.QProcess(self)
        qenv = QtCore.QProcessEnvironment()
        for k, v in env.items():
            qenv.insert(k, v)
        proc.setProcessEnvironment(qenv)
        proc.setWorkingDirectory(self.repo)
        proc.readyReadStandardOutput.connect(self._on_stdout)
        proc.readyReadStandardError.connect(lambda: self.log.append(
            '<i>' + bytes(proc.readAllStandardError()).decode('utf-8', 'replace')[-500:] + '</i>'))
        proc.start(argv[0], argv[1:])
        self.proc = proc
        return proc

    def send(self, text=None):
        text = text if isinstance(text, str) else self.input.text()
        if not text.strip():
            return
        self.input.clear()
        self.log.append('<b>Вы:</b> ' + _esc(text))
        proc = self.start_cli()
        proc.write(core.user_message(text).encode('utf-8'))

    def _on_stdout(self):
        data = bytes(self.proc.readAllStandardOutput())
        for ev in self.stream.feed_bytes(data):
            self.on_event(ev)

    # -- events (also fed directly by tests) ----------------------------------------------------------------------
    def on_event(self, ev):
        kind, value = ev
        if kind == 'session':
            core.save_session(self.doc, value)
            self._set_status()
        elif kind == 'text':
            self.log.append(_esc(value))
        elif kind == 'tool':
            card = Card(core.card_title(value))
            card.tool = value.get('name') or ''
            self.cards[value['id']] = card
            self.cards_box.addWidget(card)
        elif kind == 'tool_result':
            card = self.cards.get(value['id'])
            if card is None:
                return
            card.body.setText(_esc(value['text'])[:1200])
            if core.applicable(card.tool, value):
                card.preview_id = value['preview_id']
                card.button.setVisible(True)
                card.button.clicked.connect(lambda _=False, c=card: self.apply_card(c))
        elif kind == 'result':
            self._set_status('ошибка' if value['is_error'] else 'готово')
        elif kind == 'error':
            self.log.append('<i>' + _esc(value) + '</i>')

    def apply_card(self, card):
        """«Применить»: confirm in this Max process, then ask the daemon to run it (worker thread)."""
        pid = card.preview_id
        agr_gate.confirm(pid)
        card.button.setEnabled(False)
        card.body.setText(card.body.text() + '\n… применяется')
        daemon = self.daemon

        def work():
            ans = post_apply(daemon['url'], daemon['token'], pid)
            self.bus.applied.emit(pid, ans)
        threading.Thread(target=work, daemon=True).start()

    def _on_applied(self, pid, ans):
        for card in self.cards.values():
            if card.preview_id == pid:
                st = ans.get('status')
                if st in ('applied', 'rolled_back'):
                    card.button.setVisible(False)
                if st == 'applied':
                    card.body.setText('Применено: одна запись Undo «{}».'.format(ans.get('undo_label')))
                elif st == 'rolled_back':
                    card.body.setText('Откат (хеши восстановлены: {}).\n{}'.format(ans.get('rollback_proved'),
                                                                                  ans.get('question')))
                else:
                    card.body.setText('{}: {}'.format(st, ans.get('error') or ans.get('why') or ''))
                    card.button.setEnabled(True)
        if self.proc is not None and self.proc.state() != QtCore.QProcess.NotRunning:
            note = 'Пользователь нажал «Применить» для {}: {}.'.format(pid[:12], ans.get('status'))
            self.proc.write(core.user_message(note).encode('utf-8'))


def _esc(text):
    return (str(text).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('\n', '<br>'))


def max_main_window():
    """The Max main window as a QMainWindow (qtmax in 2025+, MaxPlus-free path in 2024)."""
    try:
        import qtmax
        return qtmax.GetQMaxMainWindow()
    except ImportError:
        from pymxs import runtime as rt  # noqa: F401
        for w in QtWidgets.QApplication.topLevelWidgets():
            if isinstance(w, QtWidgets.QMainWindow):
                return w
    return None


def open_dock(repo, daemon, profile='modeller', auth='local', exe=None):
    from pymxs import runtime as rt
    doc = os.path.join(str(rt.maxFilePath), str(rt.maxFileName)) if str(rt.maxFileName) else 'untitled'
    main = max_main_window()
    dock = AgentDock(repo, exe=exe, profile=profile, auth=auth, parent=main, doc=doc, daemon=daemon)
    if main is not None:
        main.addDockWidget(QtCore.Qt.RightDockWidgetArea, dock)
    dock.show()
    return dock
