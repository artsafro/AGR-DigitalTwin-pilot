"""new-case: «Путь» — the AGR Tools roadmap rollout, the tab rail data and GUIDE.md, all from ONE JSON (#860).

The source of truth is the plan's master table `docs/plans/agr-tools-suite.json` (#853), shipped inside the
package as `agr-tools-suite.json`. Nothing here is written twice by hand: the panel's flow diagram, the button
tooltips and «?» cards, the greyed planned buttons of the rail and `docs/agr-tools/GUIDE.md` (+ flow.svg) are
all rendered from it. Stdlib only; no Qt, no pymxs.
"""
import json
import math

FLOW_ARROW = ' → '
MODE_RU = {'read': 'только чтение', 'select': 'только чтение, выделяет объекты',
           'copy': 'правит только копии', 'undo': 'правит сцену, отмена через Undo',
           'file': 'пишет новые файлы, исходники не трогает'}
STEP_RU = ('Проверить и выделить — сцена не меняется', 'Исправить — копии / undo / новые файлы')
STEP_OF_MODE = {'read': 0, 'select': 0, 'copy': 1, 'undo': 1, 'file': 1}
BLOCK_FIELDS = {'id', 'number', 'title_ru', 'hue', 'added_because', 'short_ru', 'when_ru'}
ROW_FIELDS = {'id', 'block', 'label_ru', 'does_ru', 'source', 'verdict', 'verdict_note', 'evidence', 'reqs',
              'mode', 'mcp', 'priority', 'version', 'icon'}
STATUS_RU = {'ok': 'ок', 'errors': 'ошибки', 'not_run': 'не запускалось', 'planned': 'кнопок ещё нет'}


def vkey(version):
    """'0.7' / '0.7.0' / '1.x' -> sortable tuple; 'x' sorts after every number."""
    out = []
    for part in str(version).split('.'):
        out.append((1, 0) if part == 'x' else (0, int(part)))
    while len(out) < 3:
        out.append((0, 0))
    return tuple(out)


def shipped(row_version, package_version):
    return vkey(row_version) <= vkey(package_version)


def load(text):
    """Parse and validate the master table; any gap is an error naming it (never a default)."""
    suite = json.loads(text)
    if not isinstance(suite, dict) or suite.get('schema') != 1:
        raise ValueError('agr-tools-suite.json: schema 1 expected')
    blocks, rows = suite.get('blocks'), suite.get('rows')
    if not isinstance(blocks, list) or not isinstance(rows, list) or not blocks or not rows:
        raise ValueError('agr-tools-suite.json: blocks/rows missing')
    ids = set()
    for b in blocks:
        missing = BLOCK_FIELDS - set(b)
        if missing:
            raise ValueError('block {} lacks {}'.format(b.get('id'), sorted(missing)))
        if b['hue'] is not None and not (isinstance(b['hue'], (int, float)) and 0 <= b['hue'] < 360):
            raise ValueError('block {} hue {!r}'.format(b['id'], b['hue']))
        ids.add(b['id'])
    if [b['number'] for b in blocks] != list(range(len(blocks))):
        raise ValueError('blocks are not numbered 0..N in order')
    seen = set()
    for r in rows:
        missing = ROW_FIELDS - set(r)
        if missing:
            raise ValueError('row {} lacks {}'.format(r.get('id'), sorted(missing)))
        if r['id'] in seen:
            raise ValueError('duplicate row ' + r['id'])
        seen.add(r['id'])
        if r['block'] not in ids:
            raise ValueError('row {} has unknown block {}'.format(r['id'], r['block']))
        if r['mode'] not in MODE_RU:
            raise ValueError('row {} has unknown mode {}'.format(r['id'], r['mode']))
        vkey(r['version'])
    return suite


def load_file(path):
    with open(path, encoding='utf-8') as f:
        return load(f.read())


def block(suite, block_id):
    for b in suite['blocks']:
        if b['id'] == block_id:
            return b
    raise KeyError('unknown block: ' + repr(block_id))


def row(suite, row_id):
    for r in suite['rows']:
        if r['id'] == row_id:
            return r
    raise KeyError('unknown plan row: ' + repr(row_id))


def block_rows(suite, block_id):
    """Rows of a block in work order: version, then table order."""
    order = {r['id']: i for i, r in enumerate(suite['rows'])}
    mine = [r for r in suite['rows'] if r['block'] == block_id]
    return sorted(mine, key=lambda r: (vkey(r['version']), order[r['id']]))


def state(r, package_version):
    return 'done' if shipped(r['version'], package_version) else 'planned'


def planned_label(r):
    return 'в версии ' + str(r['version'])


def tooltip(suite, r):
    """Hover text: what it does + when it is needed + requirement ids."""
    b = block(suite, r['block'])
    return '{}\nКогда: {}\nРежим: {}\nТреб.: {}'.format(r['does_ru'], b['when_ru'], MODE_RU[r['mode']], r['reqs'])


def card(suite, r, package_version):
    """«?» card: what, when, input, result, read-only or modifies, related buttons."""
    b = block(suite, r['block'])
    step = STEP_OF_MODE[r['mode']]
    related = [x['label_ru'] for x in block_rows(suite, r['block'])
               if x['id'] != r['id'] and STEP_OF_MODE[x['mode']] == step]
    return {
        'title': '{} ({})'.format(r['label_ru'], r['id']),
        'what': r['does_ru'],
        'when': b['when_ru'],
        'input': 'Выделение или вся сцена (переключатель «Область»); тип модели — из AGR_EXPORT_PATH объекта.'
        if r['mode'] in ('read', 'select') else 'Последний пробный прогон той же кнопки на том же выделении.',
        'result': 'JSON-отчёт (schema 1): таблица находок по объектам; объекты с ошибками выделяются.',
        'mode': MODE_RU[r['mode']],
        'reqs': r['reqs'],
        'state': 'есть в этой версии' if state(r, package_version) == 'done' else planned_label(r),
        'block': '{} {}'.format(b['number'], b['title_ru']),
        'related': related,
        'why': r['evidence'],
    }


def card_text(c):
    lines = [c['title'], '', 'Что делает: ' + c['what'], 'Когда нужна: ' + c['when'], 'Вход: ' + c['input'],
             'Результат: ' + c['result'], 'Сцена: ' + c['mode'], 'Требования: ' + c['reqs'],
             'Статус: ' + c['state'], 'Блок: ' + c['block']]
    if c['related']:
        lines.append('Связанные кнопки: ' + ', '.join(c['related']))
    if c['why'] and c['why'] != '-':
        lines.append('Почему есть: ' + c['why'])
    return '\n'.join(lines)


def flow(suite, package_version):
    """Diagram nodes in pipeline order; each node = a block with its steps and buttons."""
    nodes = []
    for b in suite['blocks']:
        steps = []
        for i, title in enumerate(STEP_RU):
            buttons = [{'id': r['id'], 'label': r['label_ru'], 'state': state(r, package_version),
                        'version': r['version'], 'icon': r['icon']}
                       for r in block_rows(suite, b['id']) if STEP_OF_MODE[r['mode']] == i]
            if buttons:
                steps.append({'title': title, 'buttons': buttons})
        done = sum(1 for s in steps for x in s['buttons'] if x['state'] == 'done')
        total = sum(len(s['buttons']) for s in steps)
        nodes.append({'id': b['id'], 'number': b['number'], 'title': b['title_ru'], 'short': b['short_ru'],
                      'hue': b['hue'], 'when': b['when_ru'], 'steps': steps, 'done': done, 'total': total})
    return nodes


def live_status(suite, reports, package_version):
    """{block id: ok|errors|not_run|planned} from the last reports of this scene.

    reports: {plan row id: report dict}. A block with no shipped read-only check is `planned`. A report
    whose status is not exactly 'pass' counts as errors (fail-closed), never as ok.
    """
    out = {}
    for b in suite['blocks']:
        checks = [r for r in block_rows(suite, b['id'])
                  if state(r, package_version) == 'done' and STEP_OF_MODE[r['mode']] == 0]
        if not checks:
            out[b['id']] = 'planned'
            continue
        got = [reports[r['id']] for r in checks if r['id'] in reports]
        if any(not isinstance(rep, dict) or rep.get('status') != 'pass' for rep in got):
            out[b['id']] = 'errors'
        elif got:
            out[b['id']] = 'ok'
        else:
            out[b['id']] = 'not_run'
    return out


def next_step(suite, status):
    """«Следующий шаг»: the first block in pipeline order with errors or not run."""
    for b in suite['blocks']:
        s = status.get(b['id'])
        if s in ('errors', 'not_run'):
            what = 'исправить ошибки' if s == 'errors' else 'запустить проверки'
            return '{} {}: {}'.format(b['number'], b['title_ru'], what), b['id']
    return 'Все проверки чистые — можно экспортировать.', None


# ---- docs/agr-tools/GUIDE.md and flow.svg ------------------------------------------------------------
def _esc(text):
    return str(text).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


def flow_svg(suite, package_version, colour):
    """Deterministic SVG of the pipeline: one box per block in its colour, arrows in order.

    colour(block) -> '#rrggbb' (derived from the theme by the caller; light theme for the repo picture).
    """
    nodes = flow(suite, package_version)
    w, h, gap, cols = 210, 92, 34, 5
    rows_n = math.ceil(len(nodes) / cols)
    width = cols * w + (cols - 1) * gap + 40
    height = rows_n * h + (rows_n - 1) * gap + 40
    out = ['<svg xmlns="http://www.w3.org/2000/svg" width="{}" height="{}" viewBox="0 0 {} {}" '
           'font-family="Segoe UI, Arial, sans-serif">'.format(width, height, width, height),
           '<rect width="100%" height="100%" fill="#ffffff"/>']
    pos = []
    for i, n in enumerate(nodes):
        r, c = divmod(i, cols)
        if r % 2:
            c = cols - 1 - c  # snake: the second row runs right-to-left so arrows stay short
        pos.append((20 + c * (w + gap), 20 + r * (h + gap)))
    for i in range(len(nodes) - 1):
        (x1, y1), (x2, y2) = pos[i], pos[i + 1]
        if y1 == y2:
            a, b = (x1 + w, x2) if x2 > x1 else (x1, x2 + w)
            out.append('<path d="M{} {}H{}" stroke="#555555" stroke-width="2" fill="none" '
                       'marker-end="url(#a)"/>'.format(a, y1 + h // 2, b))
        else:
            out.append('<path d="M{} {}V{}" stroke="#555555" stroke-width="2" fill="none" '
                       'marker-end="url(#a)"/>'.format(x1 + w // 2, y1 + h, y2))
    out.insert(2, '<defs><marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
                  'orient="auto"><path d="M0 0L10 5L0 10Z" fill="#555555"/></marker></defs>')
    for n, (x, y) in zip(nodes, pos):
        col = colour(n)
        dash = ' stroke-dasharray="6 4"' if n['done'] == 0 else ''
        out.append('<rect x="{}" y="{}" width="{}" height="{}" rx="8" fill="#ffffff" stroke="{}" '
                   'stroke-width="2.5"{}/>'.format(x, y, w, h, col, dash))
        out.append('<rect x="{}" y="{}" width="8" height="{}" rx="3" fill="{}"/>'.format(x, y, h, col))
        out.append('<text x="{}" y="{}" font-size="15" font-weight="bold" fill="{}">{} {}</text>'.format(
            x + 18, y + 26, col, n['number'], _esc(n['short'])))
        out.append('<text x="{}" y="{}" font-size="12" fill="#333333">{}</text>'.format(
            x + 18, y + 48, _esc(n['title'])))
        out.append('<text x="{}" y="{}" font-size="12" fill="#333333">кнопок: {} из {}</text>'.format(
            x + 18, y + 70, n['done'], n['total']))
    out.append('</svg>')
    return '\n'.join(out) + '\n'


def guide_md(suite, package_version, svg_name='flow.svg'):
    """docs/agr-tools/GUIDE.md (RU). Generated; a test regenerates it and expects no diff."""
    nodes = flow(suite, package_version)
    out = ['<!-- Generated by tools/max/build_agr_guide.py from docs/plans/agr-tools-suite.json; do not edit. -->',
           '# AGR Tools {}: путь и кнопки'.format(package_version), '',
           'Это та же справка, что вкладка «Путь» в панели 3ds Max: обе собраны из одной таблицы '
           '`docs/plans/agr-tools-suite.json`.', '',
           '![Путь AGR]({})'.format(svg_name), '',
           'Порядок работы: ' + FLOW_ARROW.join('{} {}'.format(n['number'], n['short']) for n in nodes) + '.',
           'В панели узел показывает состояние по последним отчётам сцены: ок, ошибки или не запускалось. '
           'Строка «Следующий шаг» называет первый блок с ошибками или без прогона.', '',
           'Кнопки «в версии 0.x» ещё не сделаны; в панели они серые.', '']
    for n in nodes:
        out += ['## {} {}'.format(n['number'], n['title']), '', '**Когда:** ' + n['when'], '',
                'Кнопок в этой версии: {} из {}.'.format(n['done'], n['total']), '']
        for s in n['steps']:
            out += ['### ' + s['title'], '', '| Кнопка | Что делает | Режим | Требования | Есть |',
                    '|---|---|---|---|---|']
            for x in s['buttons']:
                r = row(suite, x['id'])
                have = 'да' if x['state'] == 'done' else planned_label(r)
                out.append('| {} (`{}`) | {} | {} | {} | {} |'.format(
                    r['label_ru'], r['id'], r['does_ru'].replace('|', '/'), MODE_RU[r['mode']], r['reqs'], have))
            out.append('')
    return '\n'.join(out).rstrip('\n') + '\n'
