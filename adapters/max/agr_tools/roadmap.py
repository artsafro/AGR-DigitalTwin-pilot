"""new-case: «Путь» — the AGR Tools roadmap rollout, the tab rail data and GUIDE.md, all from ONE JSON (#860).

The source of truth is the plan's master table `docs/plans/agr-tools-suite.json` (#853), shipped inside the
package as `agr-tools-suite.json`. Nothing here is written twice by hand: the panel's flow diagram, the button
tooltips and «?» cards, the greyed planned buttons of the rail and `docs/agr-tools/GUIDE.md` (+ flow.svg) are
all rendered from it. Stdlib only; no Qt, no pymxs.
"""
import json
import math
import re

FLOW_ARROW = ' → '
MODE_RU = {'read': 'только чтение', 'select': 'только чтение, выделяет объекты',
           'copy': 'правит только копии', 'undo': 'правит сцену, отмена через Undo',
           'file': 'пишет новые файлы, исходники не трогает',
           'agent': 'запрос агенту и приём результата через шлюз'}
STEP_RU = ('Проверить и выделить — сцена не меняется', 'Исправить — копии / undo / новые файлы')
STEP_OF_MODE = {'read': 0, 'select': 0, 'copy': 1, 'undo': 1, 'file': 1, 'agent': 1}
# 1.0 conveyor (#1024, branch 0): stages 0-9 + the agent, row fields `stage` / `fate` (null on rows released before
# 1.0). fate: `stage` = a button of its stage, `step` = folded into the big button `step_of` (no own button),
# `tail` = stays 1.x, `obsolete` = replaced (kept for history).
STAGE_IDS = tuple(range(10)) + ('agent',)
FATES = ('stage', 'step', 'tail', 'obsolete')
STAGE_FIELDS = {'id', 'order', 'label_ru', 'big_button', 'icon', 'rows', 'steps', 'checks'}
# Rows of the new 1.0 buttons may carry an id prefix that is not a block (they live on the stage rail; `block` gives
# their colour). Block pages list only rows whose prefix is their block, so pages 0-9 stay as they were.
STAGE_PREFIXES = ('project', 'source', 'body', 'win', 'mat', 'vpm', 'npm', 'pack', 'agent')
BLOCK_FIELDS = {'id', 'number', 'title_ru', 'hue', 'added_because', 'short_ru', 'when_ru'}
ROW_FIELDS = {'id', 'block', 'label_ru', 'does_ru', 'source', 'verdict', 'verdict_note', 'evidence', 'reqs',
              'mode', 'mcp', 'priority', 'version', 'icon'}
VERDICTS = ('done', 'take', 'take_fix', 'merge', 'new')
PRIORITIES = ('P1', 'P2', 'P3')
MCP = ('yes', 'no')
TEXT_FIELDS = ('id', 'label_ru', 'does_ru', 'source', 'evidence', 'reqs', 'icon')  # verdict_note may be empty
# Requirement id grammar of the plan: NPM/VPM chapters 1 and 2 (`NPM-2.3-11`, `VPM-2.5-2.1.3.a`), GeoJSON rows
# (`GJ-19.a`), or `-` alone. A matrix of known ids can be passed to load(requirements=...) (it lives in
# GeoAGR-private, not in the pilot); then every id must be in it.
REQ_RE = re.compile(r'(?:NPM|VPM)-[12]\.\d{1,2}-\d+(?:\.[0-9a-z]+)*|GJ-\d+(?:\.[a-z])?')
# Verified GeoAGR 13.64 button citations of the plan (`btn_<name> GeoAGR.ms:<line>`, #853: reference only, no code).
# A row citing a pinned button at another line, or an unpinned button, is an error; a new citation is added here
# after checking it against GeoAGR.ms (tests/max_tools/test_agr_tools_edits_090.py does it when GeoAGR-private is
# on the machine). Source: GeoAGR-private versions/13.64/GeoAGR.ms, T09 R2 (all citations correct, 05.11.2026).
GEOAGR_BUTTONS = {
    'btn_set_meters': 12547, 'btn_count_map': 15548, 'btn_TriangulateRight': 50991, 'btn_slice': 13928,
    'btn_Projection': 58102, 'btn_run': 57080, 'btn_EdgeWeld': 51802, 'btn_alpha_remove': 40195,
    'btn_UdimFitMat': 25021, 'btn_render_mat': 22888, 'btn_multimat': 42706, 'btn_count_colors': 39668,
    'btn_UCX_makeground': 62929, 'btn_UCX_rename': 62907, 'btn_udims_as_ids': 35920, 'btn_Udim_Rescale': 43253,
    'btn_bricks_unwrap': 33780, 'btn_ids_as_udims': 41355, 'btn_unwrap_material_from_lowpoly': 29390,
    'btn_check_names': 15355, 'btn_DoubleFaces': 49204, 'btn_omkte': 66030, 'btn_archivate': 66229,
    'btn_Lights': 56146,
    # Release 0.9.0 (#979 R): buttons the plan cites in the short form `btn_<name> :<line>`, and the buttons of the
    # 0.9 rows and 0.9 reworks (qa.address, qa.normals, export.pivot_place, tex.placeholders, ucx.triangulate).
    # Each line is the `on btn_<name> pressed do` handler of GeoAGR.ms 13.64 (checked 06.11.2026).
    'btn_set_alpha': 12554, 'btn_conv': 14191, 'btn_remove': 14196, 'btn_snap': 57196, 'btn_process': 56535,
    'btn_Streets_List': 42460, 'btn_View_Normals': 47595, 'btn_pivot_get': 64763, 'btn_pivot_set': 64778,
    'btn_resetXForm': 64709, 'btn_combine_two_models': 64730, 'btn_make_tex_diffuse': 42227,
    'btn_open_tex_normal': 42333, 'btn_open_tex_erm': 42409, 'btn_UCX_connect': 62890,
    # 1.0 (#1024, branch 0): the remaining buttons cited by the #1024 body and its «редакция 1» comment, each the
    # `on btn_<name> pressed do` line of GeoAGR.ms 13.64 (checked 06.11.2026).
    'btn_multimat_table': 41646, 'btn_Detriangulate': 48104, 'btn_MoveFaces': 49657, 'btn_TurboAttacher': 54814,
    'btn_UCX_move': 61446, 'btn_export_highpoly': 66904,
}
# Non-button GeoAGR.ms 13.64 lines cited by #1024 (reference only, #853), checked 06.11.2026: line -> what is there.
GEOAGR_LINES_1024 = {
    5236: 'UDIM Slicer block (5236-5280): island cut by the UV grid line (K6 idea)',
    16071: 'rollout uvDistortionViewer (udim.distortion source)',
    20050: 'fn fit_all_to_udim (vpm.build: defect not to repeat)',
    29390: 'on btn_unwrap_material_from_lowpoly (UnAtlas, npm.to_vpm: defect not to repeat)',
    31390: 'fn wrap_island_to_first_udim (vpm.build: defect not to repeat)',
    31473: 'fn process_and_align_island_universal (31473-31598, vpm.build: defect not to repeat)',
    32515: 'tile placement branch (32515-32603)',
    33785: 'clearUndoBuffer() (bricks unwrap: never repeat)',
    41653: 'rollout Controls (multimat table)',
    43960: 'rollout Tree «Lowpoly Tree maker» (place.tree_cards, tail)',
    45538: 'random pick of a window item (author note: pick by size, not at random)',
    54174: 'rollout ProjectScatterUI (place.scatter, tail)',
    56468: 'rollout LightPlacerRollout (light.place, tail)',
    56719: 'fn getPolyBorders (Geo Window Placer, win.place idea)',
    56942: 'fn getBorderAlignmentData (56942-57025, Geo Window Placer)',
    57117: 'local bestWin (57117-57124, window choice)',
}
# `btn_x GeoAGR.ms:123` and the short form `btn_x :123` used after a first GeoAGR.ms citation in the same source.
GEOAGR_CITE_RE = re.compile(r'\b(btn_\w+)\s+(?:GeoAGR\.ms)?:(\d+)')
STATUS_RU = {'ok': 'ок', 'errors': 'ошибки', 'not_run': 'не запускалось', 'planned': 'кнопок ещё нет',
             'no_checks': 'проверок нет, только действия'}


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


def _reqs(r, requirements):
    text = r['reqs'].strip()
    if text == '-':
        return
    for token in text.split():
        if not REQ_RE.fullmatch(token):
            raise ValueError('row {} has a malformed requirement id {!r}'.format(r['id'], token))
        if requirements is not None and token not in requirements:
            raise ValueError('row {} cites an unknown requirement {}'.format(r['id'], token))


def _citations(r):
    for name, line in GEOAGR_CITE_RE.findall(r['source']):
        if name not in GEOAGR_BUTTONS:
            raise ValueError('row {} cites {} GeoAGR.ms:{}, not in roadmap.GEOAGR_BUTTONS'.format(r['id'], name, line))
        if int(line) != GEOAGR_BUTTONS[name]:
            raise ValueError('row {} cites {} at GeoAGR.ms:{}, verified line is {}'.format(
                r['id'], name, line, GEOAGR_BUTTONS[name]))


def load(text, requirements=None):
    """Parse and validate the master table; any gap is an error naming it (never a default).

    Beyond fields, blocks and duplicates (#860) it rejects (SYNTHESIS §4, T09 R3: 8 of 8 broken JSON passed):
    unknown verdict / priority / mcp, an id whose prefix is not its block, a version not in `versions[]` (or a row
    missing from its version's list), an empty text field, a malformed requirement id (or one outside
    `requirements` when given) and a GeoAGR button citation that differs from GEOAGR_BUTTONS."""
    suite = json.loads(text)
    if not isinstance(suite, dict) or suite.get('schema') != 1:
        raise ValueError('agr-tools-suite.json: schema 1 expected')
    blocks, rows = suite.get('blocks'), suite.get('rows')
    if not isinstance(blocks, list) or not isinstance(rows, list) or not blocks or not rows:
        raise ValueError('agr-tools-suite.json: blocks/rows missing')
    versions = suite.get('versions')
    if not isinstance(versions, list) or not versions or not all(
            isinstance(v, dict) and isinstance(v.get('version'), str) and isinstance(v.get('rows'), list)
            for v in versions):
        raise ValueError('agr-tools-suite.json: versions missing')
    listed = {v['version']: set(v['rows']) | set(v.get('steps') or ()) for v in versions}
    if len(listed) != len(versions):
        raise ValueError('agr-tools-suite.json: duplicate version')
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
    staged = {}
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
        for field, allowed in (('verdict', VERDICTS), ('priority', PRIORITIES), ('mcp', MCP)):
            if r[field] not in allowed:
                raise ValueError('row {} has unknown {} {!r}'.format(r['id'], field, r[field]))
        for field in TEXT_FIELDS:
            if not isinstance(r[field], str) or not r[field].strip():
                raise ValueError('row {} has an empty {}'.format(r.get('id'), field))
        prefix, _, rest = r['id'].partition('.')
        _stage_fields(r)
        if not rest or (prefix != r['block'] and not (prefix in STAGE_PREFIXES and r['stage'] is not None)):
            raise ValueError('row {}: id prefix is not its block {}'.format(r['id'], r['block']))
        if r['stage'] is not None:
            staged[r['id']] = r
        vkey(r['version'])
        if r['version'] not in listed:
            raise ValueError('row {} has version {} not in versions[]'.format(r['id'], r['version']))
        if r['id'] not in listed[r['version']]:
            raise ValueError('row {} is missing from versions[{}].rows'.format(r['id'], r['version']))
        _reqs(r, requirements)
        _citations(r)
    stray = sorted(set().union(*listed.values()) - seen)
    if stray:
        raise ValueError('versions[] names rows that do not exist: ' + ', '.join(stray))
    _stages(suite, staged, {r['id']: r for r in rows})
    return suite


def _stage_fields(r):
    if 'stage' not in r or 'fate' not in r:
        raise ValueError('row {} lacks stage/fate (#1024)'.format(r['id']))
    stage, fate = r['stage'], r['fate']
    if stage is not None and stage not in STAGE_IDS:
        raise ValueError('row {} has unknown stage {!r}'.format(r['id'], stage))
    if fate is not None and fate not in FATES:
        raise ValueError('row {} has unknown fate {!r}'.format(r['id'], fate))
    if (stage is None) != (fate in (None, 'tail', 'obsolete')):
        raise ValueError('row {}: stage {!r} does not fit fate {!r}'.format(r['id'], stage, fate))
    if fate in ('stage', 'step') and r['version'] != '1.0':
        raise ValueError('row {}: fate {} needs version 1.0'.format(r['id'], fate))
    if fate in ('tail', 'obsolete') and r['version'] != '1.x':
        raise ValueError('row {}: fate {} needs version 1.x'.format(r['id'], fate))
    if fate is None and r['version'] in ('1.0', '1.x'):
        raise ValueError('row {} of version {} has no fate'.format(r['id'], r['version']))
    if (fate == 'step') != ('step_of' in r):
        raise ValueError('row {}: step_of goes with fate step only'.format(r['id']))
    if r['mode'] == 'agent' and stage != 'agent':
        raise ValueError('row {}: mode agent only on the agent stage'.format(r['id']))


def _stages(suite, staged, by_id):
    stages = suite.get('stages')
    if not isinstance(stages, list) or [s.get('id') for s in stages] != list(STAGE_IDS):
        raise ValueError('agr-tools-suite.json: stages 0-9 + agent expected in order')
    covered, steps = [], []
    for i, s in enumerate(stages):
        missing = STAGE_FIELDS - set(s)
        if missing:
            raise ValueError('stage {} lacks {}'.format(s['id'], sorted(missing)))
        if s['order'] != i or not str(s['label_ru']).strip() or not str(s['icon']).strip():
            raise ValueError('stage {}: order/label/icon'.format(s['id']))
        if s['big_button'] not in s['rows']:
            raise ValueError('stage {}: big button {} is not one of its rows'.format(s['id'], s['big_button']))
        for rid in s['rows'] + s['steps']:
            r = by_id.get(rid)
            if r is None or r['stage'] != s['id']:
                raise ValueError('stage {} lists {} of another stage'.format(s['id'], rid))
            if (rid in s['steps']) != (r['fate'] == 'step'):
                raise ValueError('stage {}: {} is listed as the wrong kind'.format(s['id'], rid))
            if r['fate'] == 'step' and r['step_of'] not in s['rows']:
                raise ValueError('row {}: step_of {} is not a button of its stage'.format(rid, r['step_of']))
        for rid in s['checks']:
            r = by_id.get(rid)
            if r is None or r['version'] in ('1.0', '1.x'):
                raise ValueError('stage {}: check {} must be a released row'.format(s['id'], rid))
        covered += s['rows']
        steps += s['steps']
    if sorted(covered + steps) != sorted(staged) or len(set(covered)) != len(covered):
        raise ValueError('stages do not cover the staged rows exactly once')
    v10 = {v['version']: v for v in suite['versions']}.get('1.0')
    if v10 is not None and (v10['rows'] != covered or sorted(v10.get('steps', [])) != sorted(steps)):
        raise ValueError('versions[1.0].rows/steps differ from the stage buttons/steps')


def stage_buttons(suite):
    """The 1.0 buttons (fate stage) in station order 1.0.1..1.0.N: stage order, then the stage's row order."""
    return [rid for s in suite['stages'] for rid in s['rows']]


def stage_of(suite, stage_id):
    for s in suite['stages']:
        if s['id'] == stage_id:
            return s
    raise KeyError('unknown stage: ' + repr(stage_id))


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
    mine = [r for r in suite['rows'] if r['block'] == block_id and r['id'].partition('.')[0] == block_id]
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
    """{block id: ok|errors|not_run|planned|no_checks} from the last reports of this scene.

    reports: {plan row id: report dict}. A block with no shipped button is `planned`; with shipped buttons but
    no read-only check (only fix actions) `no_checks`. A report
    whose status is not exactly 'pass' counts as errors (fail-closed), never as ok.
    """
    out = {}
    for b in suite['blocks']:
        checks = [r for r in block_rows(suite, b['id'])
                  if state(r, package_version) == 'done' and STEP_OF_MODE[r['mode']] == 0]
        if not checks:
            shipped_any = any(state(r, package_version) == 'done' for r in block_rows(suite, b['id']))
            out[b['id']] = 'no_checks' if shipped_any else 'planned'
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
