"""new-case: pure model of the AGR Tools 0.6.0 panel (#808); no Qt, no pymxs.

Actions, sections, Russian labels and tooltips, report -> table rows, the batched
progress loop with cancel, dock-state parsing and palette-derived accents. Everything
here runs under plain pytest; ui_panel.py only draws it.
"""
import base64
import binascii
import colorsys
import json
import math
import os
from collections import namedtuple

VERSION = '0.6.0'

Action = namedtuple('Action', 'id tool icon section label tip reqs macro batch')

SECTIONS = ('Проверки', 'UV и атласы', 'Коллизии UCX', 'Экспорт', 'GeoJSON')

# id == icon name in tools/max/agr_icons.py; tool == runtime.ui() argument; macro == macroScript name.
# batch=True only for tools whose report is a per-object independent list (merge is exact).
ACTIONS = (
    Action('xview', 'xview', 'xview', 0, 'xView: перекрытия',
           'Ищет совпадающие вершины и перекрытые грани; выделяет объекты с ошибками.',
           ('NPM-2.3-7.a', 'NPM-2.3-9', 'VPM-2.3-11.a', 'VPM-2.3-13'), 'AGRToolsXView', True),
    Action('matid', 'matid', 'matid', 0, 'MatID',
           'Проверяет ID материалов граней против слотов Multi/Sub-Object.',
           ('NPM-2.4-5', 'VPM-2.4-5'), 'AGRToolsMatID', True),
    Action('names', 'names', 'names', 0, 'Имена NPM/VPM',
           'Проверяет имена объектов, материалов и текстур по маскам NPM/VPM (только чтение).',
           ('NPM-2.10-1', 'NPM-2.10-2', 'NPM-2.10-3.3.a', 'VPM-2.10-2.a', 'VPM-2.11-0.a', 'VPM-2.11-0.c'),
           'AGRToolsNames', False),
    Action('tris', 'tris', 'tris', 0, 'Треугольники по FBX',
           'Считает треугольники на каждый FBX и сравнивает с лимитом (только чтение).',
           ('NPM-2.3-6.a', 'NPM-2.3-6.b', 'VPM-2.3-9', 'VPM-2.3-10'), 'AGRToolsTris', False),
    Action('textures', 'textures', 'textures', 0, 'Текстуры (все)',
           'Проверяет формат, размер, альфу и отступы текстур всех объектов (только чтение).',
           ('NPM-2.5-1.a', 'NPM-2.5-2.a', 'NPM-2.5-3', 'NPM-2.5-4', 'NPM-2.5-5',
            'VPM-2.5-1.2', 'VPM-2.5-1.5', 'VPM-2.5-1.6', 'VPM-2.5-1.9'), 'AGRToolsTextures', False),
    Action('pivot', 'pivot', 'pivot', 0, 'Пивот',
           'Проверяет пивот: Z = 0 и один пивот на FBX, допуск 1 мм (только чтение).',
           ('VPM-2.9-4.b', 'VPM-2.9-5'), 'AGRToolsPivot', False),
    Action('nudge', 'nudge', 'nudge', 1, 'UV-сдвиг (пробно)',
           'Пробный расчёт сдвига UV-островов на целый тайл; сцену не меняет.',
           ('VPM-2.5-2.1.3.a',), 'AGRToolsNudge', False),
    Action('nudge_apply', 'nudge_apply', 'nudge_apply', 1, 'UV-сдвиг → копии',
           'Применяет последний пробный UV-сдвиг к новым экспортным копиям; оригиналы не трогает.',
           ('VPM-2.5-2.1.3.a',), 'AGRToolsNudgeApply', False),
    Action('atlas', 'atlas', 'atlas', 1, 'UDIM → атлас (пробно)',
           'Пробная сборка атласа NPM из UDIM-тайлов; сцену не меняет.',
           ('NPM-2.5-4', 'NPM-2.5-11.a'), 'AGRToolsAtlas', False),
    Action('atlas_apply', 'atlas_apply', 'atlas_apply', 1, 'Атлас → копии',
           'Применяет последний пробный атлас к новым экспортным копиям; оригиналы не трогает.',
           ('NPM-2.5-4', 'NPM-2.5-11.a'), 'AGRToolsAtlasApply', False),
    Action('texel', 'texel', 'texel', 1, 'Тексель',
           'Показывает минимум и медиану px/m по объектам и материалам (только чтение).',
           ('VPM-2.6-2', 'NPM-2.6-1'), 'AGRToolsTexel', False),
    Action('ucx', 'ucx', 'ucx', 2, 'UCX (пробно)',
           'Пробный расчёт выпуклых коллизий UCX_; сцену не меняет.',
           ('VPM-2.13-1.a', 'VPM-2.13-1.b', 'VPM-2.13-7.a', 'VPM-2.13-7.b'), 'AGRToolsUcx', False),
    Action('ucx_apply', 'ucx_apply', 'ucx_apply', 2, 'UCX → копии',
           'Создаёт UCX_-коллизии из последнего пробного расчёта на новых копиях.',
           ('VPM-2.13-1.a', 'VPM-2.13-1.b', 'VPM-2.13-7.a', 'VPM-2.13-7.b'), 'AGRToolsUcxApply', False),
    Action('cleanup', 'cleanup', 'cleanup', 3, 'Очистка (пробно)',
           'Пробная очистка перед экспортом: каналы UV, свойства, атрибуты; сцену не меняет.',
           ('VPM-2.3-11.e',), 'AGRToolsCleanup', False),
    Action('cleanup_apply', 'apply', 'cleanup_apply', 3, 'Очистка → копии',
           'Применяет последнюю пробную очистку к новым экспортным копиям.',
           ('VPM-2.3-11.e',), 'AGRToolsCleanupApply', False),
    Action('export', 'export', 'export', 3, 'Экспорт с проверкой',
           'Первое нажатие: пробный экспорт и все проверки; второе на том же выделении пишет FBX.',
           ('NPM-1.1-1', 'VPM-1.1-1', 'NPM-2.1-3.c'), 'AGRToolsExport', False),
    Action('geojson', 'geojson', 'geojson', 4, 'Проверка GeoJSON',
           'Проверяет паспорт GeoJSON проверяющим модулем twinqa (выбор файла).',
           ('GJ-1', 'GJ-2', 'GJ-3', 'VPM-2.2-1'), 'AGRToolsGeojson', False),
)
BY_ID = {a.id: a for a in ACTIONS}
BY_TOOL = {a.tool: a for a in ACTIONS}
OPEN_MACRO = 'AGRToolsOpen'
CATEGORY = 'AGR Tools'
ICON_PREFIX = 'AgrIcons/agr_'


def action(key):
    """Unknown id is an error naming it, never a default."""
    if key in BY_ID:
        return BY_ID[key]
    if key in BY_TOOL:
        return BY_TOOL[key]
    raise KeyError('unknown AGR Tools action: ' + repr(key))


def tooltip(a):
    return '{} Треб.: {}'.format(a.tip, ', '.join(a.reqs))


def icon_name(a):
    return ICON_PREFIX + a.icon


def sections():
    """[(title, [actions...]), ...] in work-step order."""
    return [(title, [a for a in ACTIONS if a.section == i]) for i, title in enumerate(SECTIONS)]


Row = namedtuple('Row', 'handle name check ok code detail ids')


def rows(report):
    """Report -> table rows. Each object gives one row per finding, or one OK row.
    A report without an objects list (texel, export) gives one summary row.
    Report-level failures (GeoJSON plan findings, an export stopped by a gate, a cancelled run) give
    their own error rows; status == 'fail' <=> at least one error row, else ValueError (#808 review P1)."""
    if not isinstance(report, dict) or 'tool' not in report:
        raise ValueError('not an AGR Tools report')
    check = report['tool']
    status = report.get('status')
    if status not in ('pass', 'fail'):
        raise ValueError('report without pass/fail status: ' + repr(status))
    objects = report.get('objects')
    if objects is None:
        return [Row(None, '—', check, status == 'pass', status, '', ())]
    if not isinstance(objects, list):
        raise ValueError('report objects is not a list')
    out = _object_rows(check, objects) + _report_rows(check, report)
    bad = any(not r.ok for r in out)
    if status == 'pass' and bad:
        raise ValueError('report status pass with error rows: ' + repr(check))
    if status == 'fail' and not bad:  # failed without a named cause (e.g. FBX read-back mismatch)
        out.append(Row(None, '—', check, False, 'fail', 'отчёт: status fail', ()))
    return out


def _report_rows(check, report):
    """Error rows for failures that live outside report['objects']."""
    out = []
    plan = report.get('plan')
    if isinstance(plan, dict):
        findings = plan.get('findings')
        if findings is not None:
            if not isinstance(findings, list):
                raise ValueError('plan findings is not a list')
            name = os.path.basename(str(plan.get('path') or '')) or '—'
            for f in findings:
                if not isinstance(f, dict) or 'status' not in f:
                    raise ValueError('plan finding without status: ' + repr(f))
                if f['status'] == 'pass':
                    continue
                code = str(f.get('name', '?'))
                if f['status'] != 'fail':
                    code += ': ' + str(f['status'])
                out.append(Row(None, name, check, False, code,
                               'получено {}, ожидалось {}'.format(f.get('observed', ''), f.get('expected', '')), ()))
        stopped = plan.get('stopped')
        if stopped not in (None, 'texel'):
            out.append(Row(None, '—', check, False, 'stopped', 'остановлено проверкой ' + str(stopped), ()))
    cancelled = report.get('cancelled')
    if cancelled:
        out.append(Row(None, '—', check, False, 'cancelled',
                       'отменено: {} / {}'.format(cancelled.get('done'), cancelled.get('total')), ()))
    return out


def _object_rows(check, objects):
    out = []
    for o in objects:
        findings = o.get('findings')
        if not isinstance(findings, list):
            raise ValueError('object without findings list: ' + repr(o.get('name')))
        handle = o.get('handle')
        name = str(o.get('name', ''))
        if not findings:
            out.append(Row(handle, name, check, True, 'ok', '', ()))
        for f in findings:
            out.append(Row(handle, name, check, False, str(f.get('code', '')), str(f.get('detail', '')),
                           tuple(f.get('ids') or ())))
    return out


def counts(row_list):
    bad = sum(1 for r in row_list if not r.ok)
    return bad, len(row_list) - bad


def summary(row_list):
    bad, ok = counts(row_list)
    return 'Ошибок {} · ОК {}'.format(bad, ok)


def chunks(items, size):
    if size < 1:
        raise ValueError('chunk size must be >= 1')
    items = list(items)
    return [items[i:i + size] for i in range(0, len(items), size)]


def merge(tool, parts):
    """Merge per-chunk reports of a batch tool. Duplicate handles are an error."""
    objects, seen = [], set()
    for p in parts:
        if p.get('tool') != tool:
            raise ValueError('chunk report of another tool: ' + repr(p.get('tool')))
        for o in p['objects']:
            if o['handle'] in seen:
                raise ValueError('duplicate handle in chunks: ' + repr(o['handle']))
            seen.add(o['handle'])
            objects.append(o)
    return {'schema': 1, 'tool': tool,
            'status': 'fail' if any(o['findings'] for o in objects) else 'pass', 'objects': objects}


class Cancelled(Exception):
    def __init__(self, message, partial=None, done=0):
        super().__init__(message)
        self.partial = partial
        self.done = done


def run_batched(tool, fn, nodes, size, progress, cancelled):
    """Run fn(chunk) per chunk; progress(done, total) after each; cancelled() before each.
    A cancel raises Cancelled with the partial report attached (never a pass)."""
    nodes = list(nodes)
    if not nodes:
        raise ValueError('empty target set')
    parts, done = [], 0
    progress(0, len(nodes))
    for chunk in chunks(nodes, size):
        if cancelled():
            partial = None
            if parts:  # a cancelled run is never a pass, even when every finished chunk was clean
                partial = merge(tool, parts)
                partial['status'] = 'fail'
                partial['cancelled'] = {'done': done, 'total': len(nodes)}
            raise Cancelled('cancelled at {} / {}'.format(done, len(nodes)), partial, done)
        parts.append(fn(chunk))
        done += len(chunk)
        progress(done, len(nodes))
    return merge(tool, parts)


def percent(done, total):
    if total <= 0:
        return 0
    return max(0, min(100, int(done * 100 // total)))


# Dock state: {'floating': bool, 'area': int, 'geometry': base64 str, 'visible': bool}
DOCK_AREAS = (1, 2, 4, 8)  # Qt.LeftDockWidgetArea .. BottomDockWidgetArea
DEFAULT_DOCK = {'floating': False, 'area': 2, 'geometry': '', 'visible': True}


def dump_dock(state):
    return json.dumps(parse_dock(json.dumps(state)), sort_keys=True)


def parse_dock(text):
    """Bad or partial saved state falls back to the default dock (right side), never crashes."""
    try:
        data = json.loads(text) if text else {}
    except (TypeError, ValueError):
        return dict(DEFAULT_DOCK)
    if not isinstance(data, dict):
        return dict(DEFAULT_DOCK)
    out = dict(DEFAULT_DOCK)
    if isinstance(data.get('floating'), bool):
        out['floating'] = data['floating']
    if isinstance(data.get('visible'), bool):
        out['visible'] = data['visible']
    if data.get('area') in DOCK_AREAS and not isinstance(data.get('area'), bool):
        out['area'] = data['area']
    geo = data.get('geometry')
    if isinstance(geo, str) and geo:
        try:
            base64.b64decode(geo, validate=True)
            out['geometry'] = geo
        except (binascii.Error, ValueError):
            pass
    return out


def _lum(rgb):
    def ch(c):
        c = c / 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (ch(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


_HUES = {'error': 0.0, 'ok': 1.0 / 3.0, 'warn': 1.0 / 7.0}
# Section accents (Artem 2026-11-04: «разбавить цветовыми оттенками»): hue per work step, chosen
# >= 30 degrees away from the status hues red 0 and green 120 so a section never reads as a status.
SECTION_HUES = (210.0, 275.0, 35.0, 185.0, 320.0)  # Проверки, UV, UCX, Экспорт, GeoJSON (degrees)
STATUS_HUES_DEG = (0.0, 120.0)


def hue_gap(a, b):
    d = abs(a - b) % 360.0
    return min(d, 360.0 - d)


def section_accent(index, base_rgb, text_rgb):
    if not isinstance(index, int) or isinstance(index, bool) or not 0 <= index < len(SECTIONS):
        raise KeyError('unknown section: ' + repr(index))
    return _accent_hue(SECTION_HUES[index] / 360.0, base_rgb, text_rgb)


def accent(kind, base_rgb, text_rgb):
    """Accent colour derived from the theme: hue by meaning, lightness from the palette text,
    pushed until the contrast against the table base is >= 3 (WCAG large/UI)."""
    if kind not in _HUES:
        raise KeyError('unknown accent: ' + repr(kind))
    return _accent_hue(_HUES[kind], base_rgb, text_rgb)


def _accent_hue(hue, base_rgb, text_rgb):
    for v in (*base_rgb, *text_rgb):
        if not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v) or not 0 <= v <= 255:
            raise ValueError('bad palette colour')
    dark = _lum(base_rgb) < _lum(text_rgb)
    light = colorsys.rgb_to_hls(*(c / 255.0 for c in text_rgb))[1]
    lightness = min(0.72, max(0.55, light * 0.8)) if dark else max(0.22, min(0.38, light + 0.25))
    for _ in range(40):
        rgb = tuple(int(round(c * 255)) for c in colorsys.hls_to_rgb(hue, lightness, 0.6))
        if contrast(rgb, base_rgb) >= 3.0:
            return rgb
        lightness = lightness + 0.02 if dark else lightness - 0.02
        lightness = min(0.95, max(0.05, lightness))
    raise ValueError('no accent with contrast >= 3 for this palette')


def theme_name(window_rgb):
    return 'Dark' if _lum(window_rgb) < 0.2 else 'Light'


# ---- MAXScript entry points (generated; tests compare them with the committed files) -------------
import uuid as _uuid  # noqa: E402

MENU_ID = '0b5898ec-a68d-43ff-a95f-b60edcdd8b43'
UPGRADE_CODE = '{BA2C2E6E-54F9-402E-8875-3D616C9030FD}'
_NS = _uuid.UUID('f44d56e0-ac87-46b8-b5ff-e908e08e376b')
MACRO_TABLE = 647394  # ActionTable id of macroScripts (measured in Max, see PR)
CLASSIC_MACRO = 'AGRToolsClassic'
DOCUMENTED_GLOBALS = ('AGRToolsRoot', 'AGRToolsRegistered', 'AGRToolsDialog', 'AGRToolsRegisterMenus')


def stable_id(key):
    return str(_uuid.uuid5(_NS, key))


def product_code(version=VERSION):
    return '{' + stable_id('AGR Tools ' + version).upper() + '}'


def _ms(text):
    return text.replace('\\', '\\\\').replace('"', '\\"')


_CLASSIC = '''macroScript AGRToolsClassic category:"AGR Tools" tooltip:"AGR Tools (classic rollout)" buttonText:"AGR Tools (classic)"
(
    on execute do (
        global AGRToolsDialog
        try (destroyDialog AGRToolsDialog) catch ()
        rollout AGRToolsDialog "AGR Tools" width:360 (
{buttons}
            label info "JSON report in Listener; checks select offenders."
{handlers}
        )
        createDialog AGRToolsDialog
    )
)
'''


def macros_ms():
    lines = ['-- Generated by ui_model.macros_ms() (AGR Tools {}). Own implementation.'.format(VERSION),
             '-- Every action is a macroScript (toolbar/menu/hotkey) calling the Python runtime.']
    lines.append('macroScript {} category:"{}" buttonText:"AGR Tools" tooltip:"Открыть панель AGR Tools" '
                 'iconName:"{}tools"'.format(OPEN_MACRO, CATEGORY, ICON_PREFIX))
    lines.append('(on execute do (try (python.Execute "agr_tools_runtime.panel()") catch ('
                 'format "AGR_TOOLS_PANEL_FALLBACK %\\n" (getCurrentException()); '
                 'macros.run "{}" "{}")))'.format(CATEGORY, CLASSIC_MACRO))
    for a in ACTIONS:
        lines.append('macroScript {} category:"{}" buttonText:"{}" tooltip:"{}" iconName:"{}"'.format(
            a.macro, CATEGORY, _ms(a.label), _ms(tooltip(a)), icon_name(a)))
        lines.append('(on execute do python.Execute "agr_tools_runtime.ui(\'{}\')")'.format(a.tool))
    buttons = '\n'.join('            button b_{} "{}" width:340'.format(a.id, _ms(a.label)) for a in ACTIONS)
    handlers = '\n'.join('            on b_{} pressed do python.Execute "agr_tools_runtime.ui(\'{}\')"'.format(
        a.id, a.tool) for a in ACTIONS)
    return '\n'.join(lines) + '\n' + _CLASSIC.format(buttons=buttons, handlers=handlers)


def menu_ms():
    out = ['-- Generated by ui_model.menu_ms() (AGR Tools {}): main menu "AGR Tools", Max 2025+ CuiMenuManager.'.format(
        VERSION),
        '-- #cuiRegisterMenus fires at start-up and on every menu preset change. Only macroScripts are allowed.',
        'global AGRToolsRegisterMenus',
        'fn AGRToolsRegisterMenus = (',
        '    local mgr = callbacks.notificationParam()',
        '    local sub = mgr.mainMenuBar.CreateSubMenu "{}" "AGR Tools"'.format(MENU_ID),
        '    sub.CreateAction "{}" {} "{}`{}"'.format(stable_id(OPEN_MACRO), MACRO_TABLE, OPEN_MACRO, CATEGORY)]
    for i, (title, actions) in enumerate(sections()):
        out.append('    sub.CreateSeparator "{}"'.format(stable_id('sep' + str(i))))
        out.append('    local s{} = sub.CreateSubMenu "{}" "{}"'.format(i, stable_id('section' + str(i)), _ms(title)))
        for a in actions:
            out.append('    s{}.CreateAction "{}" {} "{}`{}"'.format(i, stable_id(a.macro), MACRO_TABLE, a.macro,
                                                                     CATEGORY))
    out += ['    ok',
            ')',
            'if (maxVersion())[1] >= 27000 do (',
            '    callbacks.removeScripts id:#agrTools',
            '    callbacks.addScript #cuiRegisterMenus AGRToolsRegisterMenus id:#agrTools',
            '    -- installed after the menus were built (MZP, post-start-up): re-apply the current preset once',
            '    local mgr = maxOps.GetICuiMenuMgr()',
            '    if mgr != undefined and (mgr.GetMenuById "{}") == undefined do'.format(MENU_ID),
            '        mgr.LoadConfiguration (mgr.GetCurrentConfiguration())',
            ')',
            '']
    return '\n'.join(out)
