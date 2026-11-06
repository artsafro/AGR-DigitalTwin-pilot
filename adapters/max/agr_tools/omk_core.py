"""AGR Tools 1.0 (#1024) OMK TE code logic, stdlib only. Owned by branch T (improve/issue-1024-deliver-small).

Pure logic for `qa_omk_te` (qa.omk_te); no pymxs, no host objects. Plan mode `read`: the result is a report (and the
clipboard text the Max glue copies); the scene is never changed.

Source behaviour (lab L15, docs/experiments/qa.omk_te.md; GeoAGR Get OMK TE Code `GeoAGR.ms:66030-66187`):
Copy with an active filter takes row N of the WHOLE sorted table (`GeoAGR.ms:66134`), Paste takes the visible row
(`GeoAGR.ms:66147-66158`). Here the code is always taken from the filtered row by its KEY (the table line number),
never by an index into the full list (`pick_visible`). The model of the source defect is `source_copy_code`
(kept only so the regression test is RED on it).

The table is a USER file, its path is a parameter; the package ships no table and no copy of the GeoAGR CSV
(owner answer 06.11.2026, question 13/18). Table format (proposal of L15): UTF-8 (BOM allowed) or UTF-16 with BOM,
tab separated, header `place<TAB>code`, one code per cell, code = 4 digits (leading zeros kept).
"""
import re

TOOL = 'qa.omk_te'
CODE_LEN = 4
PLACE_COL = 'place'
CODE_COL = 'code'
SPLIT_RE = re.compile(r'[\s,;/]+')
DIGITS_RE = re.compile(r'^\d+$')


class OmkError(ValueError):
    """A user-facing problem (Russian message, no mojibake). `code` is machine-readable."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


# ---- reading the table ------------------------------------------------------------------------------
def decode_table(data):
    """bytes -> str. UTF-8 (BOM allowed) and UTF-16 with BOM; anything else is an error, never guessed."""
    if not isinstance(data, (bytes, bytearray)):
        raise OmkError('table_encoding', 'Таблица ОМК ТЭ: ожидались байты файла.')
    data = bytes(data)
    if data.startswith((b'\xff\xfe', b'\xfe\xff')):
        try:
            return data.decode('utf-16')
        except UnicodeDecodeError:
            raise OmkError('table_encoding', 'Таблица ОМК ТЭ повреждена: UTF-16 не читается.') from None
    try:
        return data.decode('utf-8-sig')
    except UnicodeDecodeError:
        raise OmkError('table_encoding', 'Таблица ОМК ТЭ не в UTF-8 (и не UTF-16 с BOM): сохраните файл в UTF-8.') from None


def normalize_code(text):
    """One code token -> 4+ digit string with leading zeros (`905` -> `0905`), or None when it is not a number."""
    token = str(text).strip()
    if not DIGITS_RE.match(token):
        return None
    return token.rjust(CODE_LEN, '0')


def split_codes(cell):
    """All code tokens of a cell: `9047 9048` -> ['9047', '9048']; garbage tokens are kept as given (reported)."""
    return [t for t in SPLIT_RE.split(str(cell).strip()) if t]


def parse_table(text, place_col=PLACE_COL, code_col=CODE_COL):
    """Table text -> (rows, problems).

    rows: [{'key': <1-based file line>, 'place': str, 'code': '0905' or None, 'codes': [..all tokens..]}] of every
    usable row, in FILE order. A row is usable when it has a place and at least one code token.
    problems: [{'key': line, 'kind': 'empty_row'|'no_code'|'no_place'|'bad_code'|'many_codes'|'short_code', 'detail': str}].
    `many_codes` rows stay in rows (code None), the pick must choose one; they are never written silently."""
    lines = text.splitlines()
    if not lines:
        raise OmkError('table_empty', 'Таблица ОМК ТЭ пуста.')
    header = [h.strip().casefold() for h in lines[0].split('\t')]
    if isinstance(place_col, int) or isinstance(code_col, int):
        pi, ci, first = int(place_col) - 1, int(code_col) - 1, 0
    else:
        if place_col.casefold() not in header or code_col.casefold() not in header:
            raise OmkError('table_header', 'В таблице ОМК ТЭ нет заголовка «{}<TAB>{}» в первой строке.'.format(place_col, code_col))
        pi, ci, first = header.index(place_col.casefold()), header.index(code_col.casefold()), 1
    rows, problems = [], []
    for no, line in enumerate(lines, 1):
        if no <= first:
            continue
        if not line.strip():
            problems.append({'key': no, 'kind': 'empty_row', 'detail': 'строка {} пуста'.format(no)})
            continue
        cells = line.split('\t')
        place = cells[pi].strip() if pi < len(cells) else ''
        raw = cells[ci].strip() if ci < len(cells) else ''
        if not raw:
            problems.append({'key': no, 'kind': 'no_code', 'detail': 'строка {}: нет кода'.format(no)})
            continue
        if not place:
            problems.append({'key': no, 'kind': 'no_place', 'detail': 'строка {}: нет места'.format(no)})
            continue
        tokens = split_codes(raw)
        if len(tokens) > 1:
            problems.append({'key': no, 'kind': 'many_codes',
                             'detail': 'строка {}: в ячейке несколько кодов ({}), выберите один'.format(no, ' '.join(tokens))})
            rows.append({'key': no, 'place': place, 'code': None, 'codes': [normalize_code(t) or t for t in tokens]})
            continue
        code = normalize_code(tokens[0])
        if code is None:
            problems.append({'key': no, 'kind': 'bad_code', 'detail': 'строка {}: «{}» не код из цифр'.format(no, tokens[0])})
            continue
        if len(tokens[0]) < CODE_LEN:
            problems.append({'key': no, 'kind': 'short_code',
                             'detail': 'строка {}: код {} дополнен нулями до {}'.format(no, tokens[0], code)})
        rows.append({'key': no, 'place': place, 'code': code, 'codes': [code]})
    if not rows:
        raise OmkError('table_empty', 'В таблице ОМК ТЭ нет ни одной строки с местом и кодом.')
    return rows, problems


def sort_rows(rows):
    """Order for display: by place (case-insensitive) then code; rows without usable code (None) go last.
    Total order, so an empty/odd row can never break the sort (source defect: 26 pairs out of order)."""
    return sorted(rows, key=lambda r: (r['place'].casefold(), r['code'] is None, r['code'] or '', r['key']))


def filter_rows(rows, text):
    """Visible rows: case-insensitive substring in the place OR in any code (lab L15)."""
    needle = str(text or '').strip().casefold()
    if not needle:
        return list(rows)
    return [r for r in rows if needle in r['place'].casefold() or any(needle in c.casefold() for c in r['codes'])]


# ---- picking ------------------------------------------------------------------------------------------
def pick_visible(rows, text, index):
    """Row `index` (1-based) of the FILTERED, sorted list; the code comes from that row by its key."""
    visible = filter_rows(sort_rows(rows), text)
    if isinstance(index, bool) or not isinstance(index, int):
        raise OmkError('pick_index', 'Номер строки должен быть целым числом.')
    if not 1 <= index <= len(visible):
        raise OmkError('pick_range', 'Выбрана строка {}, а по фильтру «{}» видно строк: {}.'.format(index, text or '', len(visible)))
    return visible[index - 1]


def source_copy_code(rows, text, index):
    """MODEL OF THE SOURCE DEFECT (`GeoAGR.ms:66134`): the index of the visible list is applied to the whole
    sorted table. Used only by the regression test as the RED side; never called by the tool."""
    return sort_rows(rows)[index - 1]['code']


def choose_code(row, choice=None):
    """The one code of a row. A cell with several codes needs `choice` (1-based or the code itself)."""
    if row['code'] is not None:
        return row['code']
    codes = row['codes']
    if choice is None:
        raise OmkError('many_codes', 'В строке «{}» несколько кодов ({}): выберите один, ничего не записано.'.format(
            row['place'], ' '.join(codes)))
    if isinstance(choice, int) and not isinstance(choice, bool) and 1 <= choice <= len(codes):
        return codes[choice - 1]
    if str(choice) in codes:
        return str(choice)
    raise OmkError('many_codes', 'Код «{}» не из строки «{}» ({}).'.format(choice, row['place'], ' '.join(codes)))


# ---- options + report ----------------------------------------------------------------------------------
def omk_options(options):
    o = dict(options or {})
    unknown = set(o) - {'table', 'filter', 'pick', 'choice', 'place_column', 'code_column', 'copy'}
    if unknown:
        raise ValueError('unknown qa.omk_te options: ' + ', '.join(sorted(unknown)))
    table = o.get('table')
    if not isinstance(table, str) or not table.strip():
        raise OmkError('table_path', 'Не задан путь к таблице ОМК ТЭ (параметр table): своей таблицы в пакете нет.')
    return {'table': table.strip(), 'filter': str(o.get('filter') or ''), 'pick': o.get('pick', 1),
            'choice': o.get('choice'), 'place_column': o.get('place_column', PLACE_COL),
            'code_column': o.get('code_column', CODE_COL), 'copy': bool(o.get('copy', True))}


def scene_findings(ambiguous, code):
    """Scene-level findings (`plan.findings`, read by the test polygon for a report without scene objects):
    one pass entry for the chosen code, one fail entry per problem kind."""
    out = [{'name': 'code', 'status': 'pass'}] if code else []
    out += [{'name': k, 'status': 'fail'} for k in sorted({a['code'] for a in ambiguous})]
    return out


def error_item(err, path):
    return {'code': err.code, 'path': path, 'message': err.message}


def omk_report(edit, opts, rows, problems, picked_row, code, state_hash):
    """Read-mode report. objects stay empty (no scene objects); any problem or error is an `ambiguous` item, so the
    status is `fail` and nothing is claimed as a pass. done: the one chosen code."""
    done, ambiguous = [], []
    for p in problems:
        # a short code was repaired (info); the rest need a human decision
        if p['kind'] == 'short_code':
            continue
        ambiguous.append({'code': p['kind'], 'key': p['key'], 'message': p['detail']})
    if picked_row is not None and code is not None:
        done.append({'item': code, 'place': picked_row['place'], 'key': picked_row['key'], 'filter': opts['filter']})
    codes = [r['code'] for r in rows if r['code']]
    extra = {'findings': scene_findings(ambiguous, code),
             'table': opts['table'], 'rows': len(rows), 'visible': len(filter_rows(rows, opts['filter'])),
             'short_codes': sum(1 for p in problems if p['kind'] == 'short_code'),
             'repeated_codes': len(codes) - len(set(codes)), 'code': code,
             'clipboard': code if (code and opts['copy']) else None}
    return edit.report(TOOL, 'preview', objects=[], done=done, ambiguous=ambiguous, state_hash=state_hash, extra=extra)


def error_report(edit, opts_table, err, state_hash):
    """A table/pick problem as a failed report: Russian message, path, nothing written."""
    return edit.report(TOOL, 'preview', objects=[], ambiguous=[error_item(err, opts_table)], state_hash=state_hash,
                       extra={'findings': scene_findings([error_item(err, opts_table)], None), 'table': opts_table, 'rows': 0, 'visible': 0, 'short_codes': 0, 'repeated_codes': 0,
                              'code': None, 'clipboard': None})
