"""new-case: Visual quick-start screenshots of the polygon in interactive 3ds Max (run inside Max).

Started by guide_drive.py as `3dsmax.exe -silent -U PythonHost guide_inside.py`. Env:
AGR_GUIDE_SCENE (polygon_all.max to open), AGR_GUIDE_OUT (new folder for PNGs + log.txt).
Real screen captures of the Max main window (viewports included), not renders:
01 AGR Tools menu, 02 panel opened, 03 whole polygon (top), then per base one view
through its camera and per station the panel after pressing the station's button on the
selected station objects. The scene is opened, never saved.
"""
import json
import os
import sys
import time
import traceback
from pathlib import Path

from pymxs import runtime as rt

try:
    from PySide6 import QtCore, QtWidgets
except ImportError:  # Max 2024
    from PySide2 import QtCore, QtWidgets

SCENE = os.environ.get('AGR_GUIDE_SCENE', '')
OUT = Path(os.environ.get('AGR_GUIDE_OUT', ''))
POLY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(POLY))
LOG = []
STEPS = []
SHOTS = []
# Buttons that open a file dialog: shown with their station view only, not pressed.
NOT_PRESSED = {'geojson'}


def log(kind, text):
    LOG.append('{} {}'.format(kind, text))
    (OUT / 'log.txt').write_text('\n'.join(LOG) + '\n', encoding='utf-8')


def main_window():
    import qtmax
    return qtmax.GetQMaxMainWindow()


def _valid(obj):
    try:
        import shiboken6 as shiboken
    except ImportError:  # Max 2024
        import shiboken2 as shiboken
    return obj is not None and shiboken.isValid(obj)


def _viewport_image():
    """The active viewport as Max renders it (Nitrous frame, not the desktop: other windows
    on top of Max do not leak into the picture)."""
    from PySide6 import QtGui
    path = OUT / '_viewport.png'
    dib = rt.gw.getViewportDib()
    dib.filename = str(path)
    rt.save(dib)
    rt.close(dib)
    img = QtGui.QImage(str(path))
    if img.isNull():
        raise RuntimeError('viewport capture is empty')
    return img


def grab(name, caption, side=None):
    """Viewport (left) + AGR Tools panel or the given widget picture (right), one PNG."""
    from PySide6 import QtGui
    app = QtWidgets.QApplication.instance()
    app.processEvents()
    left = _viewport_image()
    if side is None:
        side = panel_widget().grab().toImage()
    width = left.width() + 8 + side.width()
    height = max(left.height(), side.height())
    canvas = QtGui.QImage(width, height, QtGui.QImage.Format_RGB32)
    canvas.fill(QtGui.QColor(40, 40, 40))
    painter = QtGui.QPainter(canvas)
    painter.drawImage(0, 0, left)
    painter.drawImage(left.width() + 8, 0, side)
    painter.end()
    path = OUT / (name + '.png')
    if not canvas.save(str(path)):
        raise RuntimeError('screenshot not saved: ' + str(path))
    SHOTS.append({'file': path.name, 'caption': caption})
    (OUT / 'shots.json').write_text(json.dumps(SHOTS, ensure_ascii=False, indent=1), encoding='utf-8')
    log('PASS', 'shot ' + path.name)


def redraw():
    rt.completeRedraw()
    QtWidgets.QApplication.instance().processEvents()


def panel_widget():
    for dock in main_window().findChildren(QtWidgets.QDockWidget):
        if _valid(dock) and dock.objectName() == 'AgrToolsPanel':
            return dock
    raise RuntimeError('AGR Tools panel not found')


def step_open():
    main_window().showMaximized()
    if not rt.loadMaxFile(SCENE, quiet=True):
        raise RuntimeError('loadMaxFile failed: ' + SCENE)
    rt.viewport.setLayout(rt.Name('layout_1'))
    shade()
    log('INFO', 'opened ' + SCENE + ' max ' + str(rt.maxVersion()[0]))


def shade():
    """Shaded viewport: base colours filled, dark captions on top."""
    rt.viewport.SetRenderLevel(rt.Name('smoothhighlights'))


MENU = {}


def step_menu_open():
    win = main_window()
    menus = [m for m in win.findChildren(QtWidgets.QMenu)
             if _valid(m) and m.title().replace('&', '').strip() == 'AGR Tools']
    bar = win.menuWidget()
    if not menus and _valid(bar) and hasattr(bar, 'actions'):
        menus = [a.menu() for a in bar.actions()
                 if 'AGR Tools' in a.text().replace('&', '') and a.menu() is not None]
    if not menus:
        # Fallback: the menu bar strip itself (Qt-rendered), where «AGR Tools» sits.
        strip = win.grab().toImage().copy(0, 0, win.width(), 90)
        MENU['strip'] = strip
        log('INFO', 'AGR Tools QMenu not reachable from Python; menu bar strip used')
        return
    menu = menus[0]
    menu.popup(win.mapToGlobal(QtCore.QPoint(300, 60)))
    for _ in range(5):
        QtWidgets.QApplication.instance().processEvents()
        time.sleep(0.1)
    # Max rebuilds its menus; picture the popup now, not in the next step.
    MENU['image'] = menu.grab().toImage()
    menu.close()


def step_menu_shot():
    if 'image' in MENU:
        grab('01_menu', 'Главное меню 3ds Max -> AGR Tools: первая строка «AGR Tools» открывает панель',
             side=MENU['image'])
        return
    if 'strip' not in MENU:
        raise RuntimeError('menu was not opened')
    grab('01_menu', 'Строка главного меню 3ds Max: пункт «AGR Tools» -> «AGR Tools» открывает панель',
         side=MENU['strip'])


def step_panel():
    rt.execute('macros.run "AGR Tools" "AGRToolsOpen"')
    QtWidgets.QApplication.instance().processEvents()
    dock = panel_widget()
    dock.setFloating(True)
    dock.resize(620, 1000)
    dock.show()


def step_panel_shot():
    panel_widget()
    grab('02_panel', 'AGR Tools -> AGR Tools: открылась панель справа (кнопки по блокам, таблица результата внизу)')


def step_overview():
    rt.viewport.setType(rt.Name('view_top'))
    rt.clearSelection()
    rt.execute('max zoomext sel all')
    redraw()


def step_overview_shot():
    grab('03_polygon_top', 'Вид сверху на весь полигон: цветные базы 0.1 ... 0.7 слева направо')


def _catalog():
    return json.loads((POLY / 'catalog.json').read_text(encoding='utf-8'))['objects']


def _expected(button):
    return json.loads((POLY / 'expected' / (button + '.json')).read_text(encoding='utf-8'))


def base_steps():
    import polygon_core as core
    model = sys.modules.get('agr_tools_ui_model')
    catalog = _catalog()
    for base in core.bases():
        version = base['version']
        cam = rt.getNodeByName('_cam_База ' + version)

        def view(cam=cam, version=version):
            if cam is None:
                raise RuntimeError('camera _cam_База {} missing'.format(version))
            rt.clearSelection()
            rt.viewport.setCamera(cam)
            shade()
            redraw()

        STEPS.append(view)
        STEPS.append(lambda version=version: grab(
            'b{}_view'.format(version.replace('.', '_')),
            'База {}: Views -> Cameras -> _cam_База {}. Подписи станций над объектами'.format(version, version)))
        for spec in core.stations():
            if spec['version'] != version:
                continue
            doc = _expected(spec['button'])

            def press(spec=spec, doc=doc):
                names = [o['name'] for o in catalog if o['scene'] == 'polygon_all' and o.get('station') == spec['id']]
                nodes = [rt.getNodeByName(n) for n in names]
                nodes = [n for n in nodes if n is not None]
                rt.clearSelection()
                if nodes:
                    rt.select(nodes)
                tool = doc['tool']
                if tool in NOT_PRESSED:
                    log('SKIP', '{} {} opens a file dialog'.format(spec['id'], tool))
                    return
                live = sys.modules.get('agr_tools_ui_model') or model
                action = live.BY_TOOL[tool]
                button = panel_widget().findChild(QtWidgets.QAbstractButton, 'agr_' + action.id)
                if button is None:
                    raise RuntimeError('panel button agr_{} missing'.format(action.id))
                button.click()
                redraw()
                log('INFO', 'pressed {} on {}'.format(action.id, names))

            STEPS.append(press)
            STEPS.append(lambda spec=spec: grab(
                's{}'.format(spec['id'].replace('.', '_')),
                'Станция {}: выдели объекты станции -> нажми кнопку -> таблица внизу панели'.format(spec['id'])))


def quit_max():
    log('INFO', 'done, {} shots'.format(len(SHOTS)))
    rt.quitMax(rt.Name('noPrompt'))


def run_next():
    if not STEPS:
        quit_max()
        return
    fn = STEPS.pop(0)
    try:
        fn()
    except Exception as exc:  # noqa: BLE001 - a failed step is logged, the tour goes on
        log('ERROR', '{}: {}\n{}'.format(getattr(fn, '__name__', 'step'), exc, traceback.format_exc()))
    QtCore.QTimer.singleShot(1500, run_next)


def start():
    try:
        STEPS.extend([step_open, step_menu_open, step_menu_shot, step_panel, step_panel_shot,
                      step_overview, step_overview_shot, base_steps])
    except Exception as exc:  # noqa: BLE001
        log('ERROR', str(exc))
    run_next()


if not SCENE or not OUT.is_dir():
    raise SystemExit('AGR_GUIDE_SCENE / AGR_GUIDE_OUT not set')
log('INFO', 'start ' + time.strftime('%Y-%m-%d %H:%M:%S'))
QtCore.QTimer.singleShot(8000, start)
