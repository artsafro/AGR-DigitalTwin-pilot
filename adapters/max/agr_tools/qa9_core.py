"""new-case: AGR Tools 0.9 (#979) QA 0.9 logic, stdlib only, no pymxs (branch C, improve/issue-979-qa).

Four read-only rows of plan version 0.9; qa9_max.py reads the scene into plain rows, this module judges them:

* `qa.address`  — Address grammar + street directory (address_*), replaces GeoAGR Check Adress `GeoAGR.ms:15355`.
* `qa.normals`  — inward normals, double faces, missing second side, no smoothing groups (normals_*), replaces
                  GeoAGR Double Faces `GeoAGR.ms:49204` (LMB) / `GeoAGR.ms:49149` (RMB) and View Normals
                  `GeoAGR.ms:47595` (only the checks; nothing of the view override is repeated).
* `qa.sintez`   — our verdicts vs a SINTEZ AGR Checker report, rule by rule (sintez_*); idea of tools/sintez_parity.py.
* `qa.procedural_objects` — procedural / plugin objects by class name (procedural_*), data/procedural_classes.json.

GeoAGR code is not copied (#853); lines are cited only. Lab defects (docs/experiments/qa.address.md,
qa.normals.md, qa.procedural_objects.md) are pinned by tests/max_tools/test_agr_tools_qa9.py (RED on a model of
the source behaviour, GREEN here). Distances are metres: the glue converts with units.SystemType/SystemScale,
never with the string units.decodeValue (#979 «Единицы»).
"""
import json
import math
import os
import re

# =====================================================================================================
# qa.address
# =====================================================================================================
ADDRESS_CODES = ('addr_chars', 'addr_parts', 'addr_length', 'addr_case', 'addr_abbr', 'addr_translit',
                 'addr_street_unknown')
# Primary cause of an address = the first code of this order that the address has (lab L05: exactly one).
_PRIMARY = ('addr_chars', 'addr_parts:empty', 'addr_length', 'addr_case', 'addr_parts', 'addr_abbr',
            'addr_translit', 'addr_street_unknown')
# 254 = name limit of NPM/VPM 2.10.1 (standards/*_STANDARD.yaml max_characters) for the WHOLE name. The longest
# name built around an Address in AGR Tools is a VPM texture `T_<A>_020_GroundElGlass_Diffuse_7.1001.png`
# (39 characters besides the Address); 40 are kept for it. GeoAGR has no length check (lab L05 D3).
NAME_MAX = 254
WRAPPER = 40
ADDRESS_MAX = NAME_MAX - WRAPPER
STREET_FILES = {'omk_um.tsv': ('global_id', 'um_code', 'um_type', 'name', 'trans'),
                'settlements_wikidata.tsv': ('qid', 'kind', 'name')}

# Street types: transliterated full word (ГОСТ 7.79-2000 system B as in ОМК УМ UM_TRANS, marks dropped) ->
# short form of Приказ Минфина России № 171н (the abbr_clean column of SINTEZ 1.6.1
# documents/address_abbreviations_171n.csv, sha256 94830dfa…e290), transliterated and capitalised.
# None: the type is omitted («улица», GeoAGR ul5 form `Tverskaya_7`, lab L05). Words outside 171н keep their name.
STREET_TYPES = {
    'ulicza': None, 'pereulok': 'Per', 'proezd': 'Prd', 'ploshhad': 'Pl', 'naberezhnaya': 'Nab', 'shosse': 'Sh',
    'tupik': 'Tup', 'bulvar': 'Br', 'alleya': 'Al', 'prospekt': 'Prkt', 'prosek': 'Prk', 'proseka': 'Prka',
    'liniya': 'Ln', 'kilometr': 'Km', 'kolczo': 'Kczo', 'ploshhadka': 'Plka', 'doroga': 'Dor', 'proulok': 'Proul',
    'spusk': 'Sk', 'skver': 'Sr', 'sezd': 'Szd', 'vezd': 'Vzd', 'magistral': 'Mgstr', 'ryad': 'Ryad',
    'most': 'Most', 'estakada': 'Estakada', 'tonnel': 'Tonnel',
}
UL_SHORT = 'Ul'  # «ул.» written explicitly is accepted too (TverskayaUl_7)
# Settlement types (171н): the prefix written before the settlement name (`PosAkulovo_7`, lab L05 pass).
SETTLEMENT_PREFIXES = ('Pos', 'P', 'D', 'S', 'Pgt', 'Rp', 'Kp', 'Dp', 'Sl', 'X', 'G', 'Mkr', 'Kvl')
# House elements (171н): marker token followed by a number token.
HOUSE_MARKERS = {'K': 'корпус', 'Str': 'строение', 'Vld': 'владение', 'Dvld': 'домовладение', 'Zd': 'здание',
                 'Soor': 'сооружение', 'ZU': 'земельный участок', 'Uchk': 'участок'}
# Written although the rule says otherwise: warnings, not errors (lab L05 «Минимальная приёмка»).
HOUSE_WARN = {'D': 'D опускается: номер дома пишется без «D»/«Dom»', 'Dom': 'D опускается: номер дома пишется без «D»/«Dom»',
              'Uch': 'Uch → ZU (земельный участок, 171н)'}
_ORDINAL = re.compile(r'^(\d+)(j|yj|ij|oj|ya|aya|e|oe|ee|ye)([A-Z][A-Za-z]*)$')
_WORD = re.compile(r'^[A-Za-z]+$')
_NUMBER = re.compile(r'^\d+$')
_ALLOWED = re.compile(r'^[A-Za-z0-9_]*$')
_SEGMENT = re.compile(r'[A-Z][a-z]*|[a-z]+|\d+')

# ГОСТ 7.79-2000 system B without the marks (` and '), the form of ОМК УМ UM_TRANS; used for settlement names
# (Wikidata gives Cyrillic only). Street names keep their published UM_TRANS.
GOST_B = {'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo', 'ж': 'zh', 'з': 'z', 'и': 'i',
          'й': 'j', 'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't',
          'у': 'u', 'ф': 'f', 'х': 'x', 'ц': 'cz', 'ч': 'ch', 'ш': 'sh', 'щ': 'shh', 'ъ': '', 'ы': 'y', 'ь': '',
          'э': 'e', 'ю': 'yu', 'я': 'ya'}
_CYR_TYPES = {'улица': 'ulicza', 'переулок': 'pereulok', 'проезд': 'proezd', 'площадь': 'ploshhad',
              'набережная': 'naberezhnaya', 'шоссе': 'shosse', 'тупик': 'tupik', 'бульвар': 'bulvar',
              'аллея': 'alleya', 'проспект': 'prospekt', 'просек': 'prosek', 'линия': 'liniya', 'мост': 'most'}


def gost_b(text):
    out = []
    for c in str(text):
        t = GOST_B.get(c.lower())
        if t is None:
            out.append(c)
        else:
            out.append(t.capitalize() if c.isupper() else t)
    return ''.join(out)


def fold(text):
    """Spelling-insensitive key: the transliteration variants ГОСТ 7.79-B (ОМК УМ) / names_core / GeoAGR
    (`GeoAGR.ms:194`: Й→J, Х→H, Ц→Cz) fall together: shch=shh, kh=x, ts=cz, j=y, yo=e (lab: Й → Y/J)."""
    s = str(text).lower()
    for a, b in (('shch', 'shh'), ('kh', 'x'), ('ts', 'cz'), ('j', 'y'), ('yo', 'e'), ('yy', 'y')):
        s = s.replace(a, b)
    return s


def _cap(word):
    return word[:1].upper() + word[1:]


def _street_words(trans):
    """UM_TRANS -> words without the transliteration marks; a numeric ordinal `1-aya` stays one word `1aya`."""
    raw = [w for w in re.split(r'[\s\-]+', trans.replace('`', '').replace("'", '')) if w]
    words = []
    for w in raw:
        if words and words[-1].isdigit() and w.isalpha() and w.islower() and len(w) <= 3:
            words[-1] += w
        else:
            words.append(w)
    return words


def _numeric_ordinal(name):
    """`2-й Котельнический переулок` -> '2j' (ГОСТ-B of the suffix), else None."""
    m = re.match(r'^(\d+)-(\w+)\s', name)
    if not m:
        return None
    return m.group(1) + gost_b(m.group(2)).lower()


def street_keys(name, trans):
    """(canonical, accepted keys, full-type keys) of one ОМК УМ street (None if it has no single-token form)."""
    if '№' in trans or '№' in name:
        return None  # «проектируемый проезд № 1438»: number inside the name, no one-token Address form
    words = _street_words(trans)
    if not words:
        return None
    typed = [i for i, w in enumerate(words) if w.lower() in STREET_TYPES]
    t = typed[-1] if typed else None
    numeric = _numeric_ordinal(name)
    firsts = [words[0]] + ([numeric] if numeric and not words[0][:1].isdigit() else [])
    accepted, full = [], []
    for first in firsts:
        ws = [first] + words[1:]
        if t is None:
            accepted.append(''.join(_cap(w) for w in ws))
            continue
        rest = ws[:t] + ws[t + 1:]
        abbr = STREET_TYPES[ws[t].lower()]
        long_ = _cap(ws[t].lower())
        shorts = ([UL_SHORT] if abbr is None else [abbr])
        if abbr is None:
            accepted.append(''.join(_cap(w) for w in rest))
        for s in shorts:
            for pos in (t, len(rest)):  # where it stands, or at the end (GeoAGR ul5 form)
                accepted.append(''.join(_cap(w) for w in rest[:pos] + [s] + rest[pos:]))
        for pos in (t, len(rest)):
            full.append(''.join(_cap(w) for w in rest[:pos] + [long_] + rest[pos:]))
    accepted = list(dict.fromkeys(a for a in accepted if a))
    return accepted[0], accepted, list(dict.fromkeys(full))


def _cyr_core(name):
    """Cyrillic street name without its type word, for the hint of a Cyrillic Address (`Тверская_7`)."""
    ws = [w for w in name.lower().replace('ё', 'е').split() if w not in _CYR_TYPES]
    return ' '.join(ws)


class Directory:
    """Streets (ОМК УМ) + settlements (Wikidata) of data/streets; lookups by exact token, case, fold."""

    def __init__(self, streets, settlements, sources):
        self.exact, self.casefold, self.folded, self.full, self.cyr = {}, {}, {}, {}, {}
        self.sources = sources
        self.count = {'streets': 0, 'settlements': 0, 'skipped': 0}
        for name, trans in streets:
            keys = street_keys(name, trans)
            if keys is None:
                self.count['skipped'] += 1
                continue
            self.count['streets'] += 1
            canon, accepted, full = keys
            for k in accepted:
                self._add(k, canon)
            for k in full:
                self.full.setdefault(fold(k), canon)
            core = _cyr_core(name)
            if core not in self.cyr or len(canon) < len(self.cyr[core]):
                self.cyr[core] = canon  # «Тверская» -> the street (Tverskaya), not the square (TverskayaPl)
        for name in settlements:
            base = re.sub(r'\s*\(.*?\)\s*', ' ', name).strip()
            base = re.sub(r'^(посёлок|поселок|деревня|село|хутор)\s+', '', base, flags=re.I)
            latin = ''.join(_cap(w) for w in re.split(r'[\s\-]+', gost_b(base)) if w)
            if not re.fullmatch(r'[A-Za-z0-9]+', latin or '-'):
                self.count['skipped'] += 1
                continue
            self.count['settlements'] += 1
            self._add(latin, latin)
            for p in SETTLEMENT_PREFIXES:
                self._add(p + latin, p + latin)
            self.cyr.setdefault(base.lower().replace('ё', 'е'), latin)

    def _add(self, key, canon):
        self.exact.setdefault(key, canon)
        self.casefold.setdefault(key.casefold(), canon)
        self.folded.setdefault(fold(key), canon)

    def lookup(self, token):
        """(code or None, hint): None = known; addr_case / addr_abbr / addr_translit / addr_street_unknown."""
        if token in self.exact:
            return None, self.exact[token]
        if token.casefold() in self.casefold:
            return 'addr_case', self.casefold[token.casefold()]
        f = fold(token)
        if f in self.full:
            return 'addr_abbr', self.full[f]
        segs = _SEGMENT.findall(token)
        longs = {fold(w): w for w in STREET_TYPES if STREET_TYPES[w] is not None or w == 'ulicza'}
        for s in segs:
            if fold(s) in longs or fold(s) in ('ulitsa', 'ulica'):
                short = STREET_TYPES.get(longs.get(fold(s), 'ulicza'))
                return 'addr_abbr', '{} → {}'.format(s, short or '(опускается)')
        if f in self.folded:
            return 'addr_translit', self.folded[f]
        return 'addr_street_unknown', None


def read_table(path, columns):
    """Strict UTF-8 (no BOM) tab table with the exact header; a broken dictionary is an error (lab L05 D10, D11)."""
    with open(path, 'rb') as f:
        raw = f.read()
    if raw.startswith(b'\xef\xbb\xbf') or raw.startswith(b'\xff\xfe') or raw.startswith(b'\xfe\xff'):
        raise ValueError('street dictionary {}: BOM, expected plain UTF-8'.format(os.path.basename(path)))
    try:
        text = raw.decode('utf-8')
    except UnicodeDecodeError as exc:
        raise ValueError('street dictionary {}: not UTF-8 ({})'.format(os.path.basename(path), exc)) from None
    lines = text.split('\n')
    if lines and lines[-1] == '':
        lines.pop()
    if not lines or tuple(lines[0].split('\t')) != columns:
        raise ValueError('street dictionary {}: header must be {}'.format(os.path.basename(path), '\t'.join(columns)))
    rows = []
    for i, line in enumerate(lines[1:], 2):
        cells = line.split('\t')
        if len(cells) != len(columns) or any(not c.strip() for c in cells):
            raise ValueError('street dictionary {}: line {} has {} cells'.format(os.path.basename(path), i, len(cells)))
        rows.append(dict(zip(columns, cells)))
    if not rows:
        raise ValueError('street dictionary {}: empty'.format(os.path.basename(path)))
    return rows


def load_directory(folder):
    """Directory of data/streets (both files required): missing or broken file -> ValueError, never a pass."""
    import hashlib
    sources = {}
    tables = {}
    for name, cols in STREET_FILES.items():
        path = os.path.join(folder, name)
        if not os.path.isfile(path):
            raise ValueError('street dictionary missing: ' + path)
        tables[name] = read_table(path, cols)
        with open(path, 'rb') as f:
            sources[name] = {'rows': len(tables[name]), 'sha256': hashlib.sha256(f.read()).hexdigest()}
    streets = [(r['name'], r['trans']) for r in tables['omk_um.tsv']]
    settlements = [r['name'] for r in tables['settlements_wikidata.tsv']]
    return Directory(streets, settlements, sources)


def _names_core():
    """names_core (owner E1) read-only: the transliteration of free text, shared with qa.names_fix."""
    import importlib.util
    import sys
    mod = sys.modules.get('agr_tools_names_core')
    if mod is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'names_core.py')
        spec = importlib.util.spec_from_file_location('agr_tools_names_core', path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules['agr_tools_names_core'] = mod
        spec.loader.exec_module(mod)
    return mod


def _msg(code, level, token, text, hint=None, kind=None):
    return {'code': code, 'level': level, 'token': token, 'text': text, 'hint': hint,
            'kind': kind or code}


def _cyr_hint(text, directory):
    """Latin suggestion of a text with forbidden characters: directory street/settlement first, else names_core."""
    parts = re.split(r'[_\s]+', text.strip())
    head = []
    for i in range(len(parts), 0, -1):
        key = ' '.join(parts[:i]).lower().replace('ё', 'е')
        if key in directory.cyr:
            head = [directory.cyr[key]] + parts[i:]
            break
    if head:
        rest = '_'.join(head[1:])
        clean = _names_core().clean_text(rest)[0] if rest else ''
        return '_'.join(x for x in (head[0], clean) if x)
    return _names_core().clean_text(text)[0]


def check_address(text, directory, max_length=ADDRESS_MAX):
    """All messages of one Address: {'primary': code|None, 'messages': [...]} (level error|warn).

    Fixes of the lab L05 defects: whole-token comparison (D4), empty tokens kept (D2), length (D3), house parts
    anywhere after the number (D1, D9), no token mutation between rules (D6), case as its own code (D7),
    characters reported once (D8), digits apart checked on every token (D12), one machine result (D13)."""
    msgs = []
    if not isinstance(text, str):
        raise ValueError('Address must be text: ' + repr(text))
    if text == '':
        msgs.append(_msg('addr_parts', 'error', '', 'пустой адрес', kind='addr_parts:empty'))
        return _result(text, msgs)
    if not _ALLOWED.match(text):
        bad = sorted({c for c in text if not re.match(r'[A-Za-z0-9_]', c)})
        shown = ', '.join(repr(c) if not c.isspace() else 'пробел' for c in bad)
        msgs.append(_msg('addr_chars', 'error', text, 'недопустимые символы: ' + shown + ' (только A-Z a-z 0-9 _)',
                         _cyr_hint(text, directory)))
        return _result(text, msgs)
    if len(text) > max_length:
        msgs.append(_msg('addr_length', 'error', text, 'длина {} > {} (имя целиком ≤ {}, NPM/VPM 2.10.1)'.format(
            len(text), max_length, NAME_MAX)))
    tokens = text.split('_')
    empty = [i + 1 for i, t in enumerate(tokens) if t == '']
    if empty:
        msgs.append(_msg('addr_parts', 'error', text, 'лишний «_»: пустой элемент на позиции ' +
                         ', '.join(map(str, empty)), '_'.join(t for t in tokens if t), kind='addr_parts:empty'))
    tokens = [t for t in tokens if t]
    if not tokens:
        return _result(text, msgs)
    first_num = next((i for i, t in enumerate(tokens) if _NUMBER.match(t)), None)
    for t in tokens:
        if not (_NUMBER.match(t) or _WORD.match(t) or _ORDINAL.match(t)):
            msgs.append(_msg('addr_parts', 'error', t, 'цифры отделяются от букв «_»: ' + t,
                             re.sub(r'(?<=\d)(?=[A-Za-z])|(?<=[A-Za-z])(?=\d)', '_', t)))
    locality = tokens[:first_num] if first_num is not None else list(tokens)
    house = tokens[first_num:] if first_num is not None else []
    if first_num is None and not any(m['code'] == 'addr_parts' and m['kind'] == 'addr_parts' for m in msgs):
        msgs.append(_msg('addr_parts', 'error', text, 'нет номера дома (Улица_Дом)'))
    # warnings D/Dom/Uch directly before the house number
    while locality and locality[-1] in HOUSE_WARN and len(locality) > 1:
        tok = locality.pop()
        msgs.append(_msg('addr_abbr', 'warn', tok, HOUSE_WARN[tok], 'ZU' if tok == 'Uch' else None))
    for t in locality:
        if t.upper() in {k.upper() for k in HOUSE_WARN} and t not in HOUSE_WARN:
            msgs.append(_msg('addr_case', 'error', t, 'регистр элемента: ' + t))
    street_like = [t for t in locality if t not in HOUSE_WARN]
    if not street_like and first_num == 0:
        msgs.append(_msg('addr_parts', 'error', text, 'адрес начинается с номера: нет улицы'))
    types_lower = {fold(w): w for w in STREET_TYPES} | {fold(v): v for v in STREET_TYPES.values() if v} | \
        {fold(UL_SHORT): UL_SHORT, fold('ulitsa'): 'ulitsa'}
    streets = []
    for t in street_like:
        if fold(t) in types_lower:
            msgs.append(_msg('addr_parts', 'error', t, 'тип улицы пишется слитно с названием: «{}» отдельным '
                                                       'элементом'.format(t)))
        elif _WORD.match(t) or _ORDINAL.match(t):
            streets.append(t)
    if len(streets) > 2:
        msgs.append(_msg('addr_parts', 'error', text, 'больше двух элементов до номера дома: ' + ', '.join(streets)))
    for i, t in enumerate(streets[:2]):
        if _WORD.match(t) and not t[0].isupper():
            code, hint = directory.lookup(t)
            msgs.append(_msg('addr_case', 'error', t, 'элемент начинается со строчной буквы: ' + t, hint))
            continue
        if _WORD.match(t) and len(t) > 3 and t.isupper():
            code, hint = directory.lookup(t)
            msgs.append(_msg('addr_case', 'error', t, 'элемент заглавными: ' + t, hint))
            continue
        code, hint = directory.lookup(t)
        if code is None:
            continue
        text_ = {'addr_case': 'регистр не как в справочнике: {} → {}',
                 'addr_abbr': 'тип улицы не сокращён: {} ({})',
                 'addr_translit': 'транслит не как в справочнике (ГОСТ 7.79-Б, ОМК УМ): {} → {}',
                 'addr_street_unknown': 'улицы/поселения нет в справочнике: {}{}'}[code]
        msgs.append(_msg(code, 'error', t, text_.format(t, hint or ''), hint))
    # house part: number [letter] (marker number)*
    seen = set()
    i = 1
    while i < len(house):
        t = house[i]
        if i == 1 and _WORD.match(t) and len(t) == 1 and t.isupper() and t not in HOUSE_MARKERS and t not in HOUSE_WARN:
            i += 1  # литера: 7_A
            continue
        if t in HOUSE_MARKERS or t in HOUSE_WARN:
            if t in HOUSE_WARN:
                msgs.append(_msg('addr_abbr', 'warn', t, HOUSE_WARN[t], 'ZU' if t == 'Uch' else None))
            if t in seen:
                msgs.append(_msg('addr_parts', 'error', t, 'элемент дома повторён: ' + t))
            seen.add(t)
            if i + 1 >= len(house) or not _NUMBER.match(house[i + 1]):
                msgs.append(_msg('addr_parts', 'error', t, 'после «{}» нужен номер'.format(t)))
                i += 1
            else:
                i += 2
            continue
        if _WORD.match(t) and t.casefold() in {k.casefold() for k in HOUSE_MARKERS}:
            msgs.append(_msg('addr_case', 'error', t, 'регистр элемента дома: ' + t,
                             next(k for k in HOUSE_MARKERS if k.casefold() == t.casefold())))
        elif _NUMBER.match(t):
            msgs.append(_msg('addr_parts', 'error', t, 'номер без элемента (K/Str/Vld/ZU …): ' + t))
        elif _WORD.match(t) or _ORDINAL.match(t):
            msgs.append(_msg('addr_parts', 'error', t, 'неизвестный элемент после номера дома: ' + t))
        i += 1
    return _result(text, msgs)


def _result(text, msgs):
    errors = [m for m in msgs if m['level'] == 'error']
    primary = None
    for kind in _PRIMARY:
        hit = [m for m in errors if m['kind'] == kind]
        if hit:
            primary = hit[0]
            break
    return {'address': text, 'status': 'fail' if errors else 'pass',
            'primary': primary['code'] if primary else None,
            'messages': [{k: v for k, v in m.items() if k != 'kind'} for m in msgs]}


def address_of_name(name):
    """Address of a scene object name (`SM_<A>[_NNN]_<Type>`), the raw text — no clean-up, so a defect stays
    visible. None for UCX_/M_/T_ and names without the SM_ form."""
    from_types = ('Main', 'MainGlass', 'Ground', 'GroundGlass', 'GroundEl', 'GroundElGlass', 'Flora')
    tokens = str(name).split('_')
    if len(tokens) < 3 or tokens[0] != 'SM' or tokens[-1] not in from_types:
        return None
    body = tokens[1:-1]
    if tokens[-1] in ('Main', 'MainGlass') and len(body) > 1 and re.fullmatch(r'0\d\d', body[-1]):
        body = body[:-1]  # NPM OKS number 001..020 (zero-padded; a house number never starts with 0)
    return '_'.join(body)


def address_report(edit, items, directory, state_hash, max_length=ADDRESS_MAX, skipped=(), extra=None):
    """items: [(handle, name, address)]. One finding per failing object (the primary cause, others in detail);
    warnings and every message per address in plan.addresses."""
    if not items:
        raise ValueError('qa.address: empty input (no objects with an Address, no addresses)')
    cache = {}
    objects, warnings = [], []
    for handle, name, address in items:
        if address not in cache:
            cache[address] = check_address(address, directory, max_length)
        res = cache[address]
        findings = []
        if res['primary']:
            main = next(m for m in res['messages'] if m['code'] == res['primary'] and m['level'] == 'error')
            others = ['{}: {}'.format(m['code'], m['text']) for m in res['messages']
                      if m['level'] == 'error' and m is not main]
            detail = '{!r}: {}'.format(address, main['text'])
            if main['hint']:
                detail += ' → ' + str(main['hint'])
            if others:
                detail += ' | также: ' + '; '.join(others)
            findings.append(edit.finding(res['primary'], (), detail))
        for m in res['messages']:
            if m['level'] == 'warn':
                warnings.append({'name': name, 'address': address, 'code': m['code'], 'text': m['text']})
        objects.append(edit.entry(handle, name, findings))
    plan = {'read_only': True, 'addresses': [cache[a] for a in sorted(cache)], 'warnings': warnings,
            'max_length': max_length, 'directory': {'files': directory.sources, 'count': directory.count},
            'summary': {'objects': len(objects), 'addresses': len(cache),
                        'failed': sum(1 for a in cache.values() if a['status'] == 'fail'),
                        'warnings': len(warnings)}}
    plan.update(extra or {})
    return edit.report('qa.address', 'preview', objects, [], list(skipped), [], state_hash=state_hash, extra=plan)


# =====================================================================================================
# qa.normals
# =====================================================================================================
NORMALS_CODES = ('normal_inward', 'double_face', 'double_side_offset', 'missing_double_side', 'sg_none')
NORMALS_DEFAULTS = {
    'model': 'vpm',           # vpm: glass/Flora/opacity need a second side (VPM-2.12-3); npm: never (NPM-2.3-13)
    'cos': 0.99,              # |n1·n2| >= 0.99 is "parallel" (GeoAGR Double Faces GeoAGR.ms:49204 uses 0.99)
    'same_min_m': 0.005,      # co-directional overlap closer than 5 mm z-fights (VPM-2.3-13: 5..20 mm)
    'pair_max_m': 0.02,       # opposite faces within 2 cm are a pair (GeoAGR 0.02, here in metres)
    'side_min_m': 0.003,      # second side offset 3..10 mm (VPM-2.12-3)
    'side_max_m': 0.01,
    'weld_m': 1e-6,
    'max_faces': 200000,      # per object; above it the object is skipped with a reason, never a silent pass
}
DOUBLE_SIDED_TYPES = ('MainGlass', 'GroundGlass', 'GroundElGlass', 'Flora')


def normals_options(options):
    opts = dict(NORMALS_DEFAULTS)
    for k, v in (options or {}).items():
        if k not in NORMALS_DEFAULTS:
            raise ValueError('unknown qa.normals option: ' + k)
        if k == 'model':
            if v not in ('vpm', 'npm'):
                raise ValueError('model must be vpm or npm')
        elif isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0:
            raise ValueError('qa.normals option {} must be a positive number'.format(k))
        opts[k] = v
    if not 0 < opts['cos'] < 1 or opts['side_min_m'] > opts['side_max_m']:
        raise ValueError('qa.normals: cos in (0,1) and side_min_m <= side_max_m')
    return opts


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _norm(a):
    return math.sqrt(_dot(a, a))


def object_kind(name, options=None):
    """Geometry type token of an SM name (MainGlass, Flora, …) or None."""
    tail = str(name).rsplit('_', 1)[-1]
    return tail if tail in ('Main', 'MainGlass', 'Ground', 'GroundGlass', 'GroundEl', 'GroundElGlass', 'Flora') else None


def _weld(verts, tol):
    keys, out = {}, []
    q = 1.0 / tol
    for p in verts:
        k = (round(p[0] * q), round(p[1] * q), round(p[2] * q))
        out.append(keys.setdefault(k, len(keys)))
    return out


def _clip(poly, a, b, inside_sign):
    """Sutherland–Hodgman clip of a 2D polygon by the half plane left of a->b (inside_sign = orientation)."""
    out = []
    n = len(poly)
    for i in range(n):
        p, q = poly[i], poly[(i + 1) % n]
        sp = inside_sign * ((b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0]))
        sq = inside_sign * ((b[0] - a[0]) * (q[1] - a[1]) - (b[1] - a[1]) * (q[0] - a[0]))
        if sp >= 0:
            out.append(p)
        if (sp >= 0) != (sq >= 0):
            t = sp / (sp - sq)
            out.append((p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])))
    return out


def _area2(poly):
    s = 0.0
    for i in range(len(poly)):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % len(poly)]
        s += x1 * y2 - x2 * y1
    return s / 2.0


def _overlap(ti, tj, n):
    """(area m², centroid 3D on the plane of ti) of the overlap of tj projected onto the plane of ti (normal n)."""
    ax = max(range(3), key=lambda k: abs(n[k]))
    u, v = [k for k in range(3) if k != ax]
    a = [(p[u], p[v]) for p in ti]
    b = [(p[u], p[v]) for p in tj]
    sign = 1.0 if _area2(a) > 0 else -1.0
    poly = b
    for k in range(3):
        if not poly:
            return 0.0, None
        poly = _clip(poly, a[k], a[(k + 1) % 3], sign)
    if len(poly) < 3:
        return 0.0, None
    a2 = _area2(poly)
    if a2 == 0:
        return 0.0, None
    cx = sum((poly[i][0] + poly[(i + 1) % len(poly)][0]) * (poly[i][0] * poly[(i + 1) % len(poly)][1] -
             poly[(i + 1) % len(poly)][0] * poly[i][1]) for i in range(len(poly))) / (6 * a2)
    cy = sum((poly[i][1] + poly[(i + 1) % len(poly)][1]) * (poly[i][0] * poly[(i + 1) % len(poly)][1] -
             poly[(i + 1) % len(poly)][0] * poly[i][1]) for i in range(len(poly))) / (6 * a2)
    c = [0.0, 0.0, 0.0]
    c[u], c[v] = cx, cy
    p0 = ti[0]
    # point on the plane of ti: n.(c - p0) = 0 solved for the dominant axis
    c[ax] = p0[ax] - (n[u] * (cx - p0[u]) + n[v] * (cy - p0[v])) / n[ax]
    return abs(a2) / max(abs(n[ax]), 1e-12), tuple(c)


def mesh_normals(obj, opts):
    """Findings of one object: obj {handle, name, verts [(x,y,z) m], faces [(a,b,c) 0-based], sg [int],
    face_ids [int] (id reported per triangle: poly face for Editable_Poly, else triangle 1-based),
    double_sided (bool)}. Returns (findings [(code, ids, detail)], info)."""
    verts, faces = obj['verts'], obj['faces']
    ids = obj.get('face_ids') or [i + 1 for i in range(len(faces))]
    if len(ids) != len(faces):
        raise ValueError('face_ids do not match faces: ' + obj['name'])
    for p in verts:
        if len(p) != 3 or not all(isinstance(c, (int, float)) and math.isfinite(c) for c in p):
            raise ValueError('non-finite vertex in ' + obj['name'])
    if not faces:
        return [], {'faces': 0, 'elements': 0, 'closed': 0, 'open': 0, 'skipped': 'no faces'}
    w = _weld(verts, opts['weld_m'])
    tris = [tuple(verts[k] for k in f) for f in faces]
    wf = [tuple(w[k] for k in f) for f in faces]
    normals, areas, cents = [], [], []
    for t in tris:
        c = _cross(_sub(t[1], t[0]), _sub(t[2], t[0]))
        ln = _norm(c)
        areas.append(ln / 2.0)
        normals.append((c[0] / ln, c[1] / ln, c[2] / ln) if ln > 0 else (0.0, 0.0, 0.0))
        cents.append(tuple((t[0][k] + t[1][k] + t[2][k]) / 3.0 for k in range(3)))
    # elements: faces connected through a shared (welded) vertex
    parent = list(range(len(faces)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    first = {}
    for fi, f in enumerate(wf):
        for v in f:
            if v in first:
                a, b = find(fi), find(first[v])
                if a != b:
                    parent[a] = b
            else:
                first[v] = fi
    elements = {}
    for fi in range(len(faces)):
        elements.setdefault(find(fi), []).append(fi)
    edges = {}
    for fi, f in enumerate(wf):
        for k in range(3):
            a, b = f[k], f[(k + 1) % 3]
            if a != b:
                edges.setdefault((min(a, b), max(a, b)), []).append((fi, a, b))
    found, closed_of = [], {}
    inward_ids, n_closed, n_open = set(), 0, 0
    for root, members in elements.items():
        mset = set(members)
        closed = all(len(edges[(min(f[k], f[(k + 1) % 3]), max(f[k], f[(k + 1) % 3]))]) == 2
                     for fi in members for f in (wf[fi],) for k in range(3) if f[k] != f[(k + 1) % 3])
        closed_of[root] = closed
        if not closed:
            n_open += 1
            continue
        n_closed += 1
        parity = {members[0]: 0}
        stack, ok = [members[0]], True
        while stack and ok:
            fi = stack.pop()
            f = wf[fi]
            for k in range(3):
                a, b = f[k], f[(k + 1) % 3]
                if a == b:
                    continue
                for gj, ga, gb in edges[(min(a, b), max(a, b))]:
                    if gj == fi or gj not in mset:
                        continue
                    same_dir = (ga == a and gb == b)  # consistent neighbours traverse the edge the other way
                    want = parity[fi] ^ (1 if same_dir else 0)
                    if gj not in parity:
                        parity[gj] = want
                        stack.append(gj)
                    elif parity[gj] != want:
                        ok = False
        if not ok:
            found.append(('normal_inward', [], 'элемент неориентируем (лента Мёбиуса/самопересечение): {} граней, '
                                              'направление наружу не определено'.format(len(members))))
            continue
        vol = 0.0
        for fi in members:
            t = tris[fi]
            s = 1.0 if parity[fi] == 0 else -1.0
            vol += s * _dot(t[0], _cross(t[1], t[2])) / 6.0
        if abs(vol) < 1e-12:
            continue
        bad = 1 if vol > 0 else 0
        flipped = [fi for fi in members if parity[fi] == bad]
        if flipped:
            fid = sorted({ids[fi] for fi in flipped})
            inward_ids |= set(fid)
            found.append(('normal_inward', fid, '{} из {} граней замкнутого элемента смотрят внутрь ({:.0%})'.format(
                len(flipped), len(members), len(flipped) / len(members))))
    # candidate pairs through a spatial hash (all pairs, not one pair per face: lab L05 D3). Triangles of one
    # face id (a poly face) are summed: the gap is the separation at the centroid of the overlap area, so a face
    # tilted about its centre keeps its gap (lab: 0 / 1 mm / 2 cm / 5 cm at 0° and 5°).
    reach = opts['pair_max_m']
    ext = sorted(max(max(p[k] for p in t) - min(p[k] for p in t) for k in range(3)) for t in tris)
    cell = max(ext[int(len(ext) * 0.9)] if ext else 1.0, reach * 2, 1e-3)
    grid = {}
    for fi, t in enumerate(tris):
        if areas[fi] <= 0:
            continue
        lo = [int(math.floor((min(p[k] for p in t) - reach) / cell)) for k in range(3)]
        hi = [int(math.floor((max(p[k] for p in t) + reach) / cell)) for k in range(3)]
        span = (hi[0] - lo[0] + 1) * (hi[1] - lo[1] + 1) * (hi[2] - lo[2] + 1)
        if span > 4096:
            lo = hi = [int(math.floor(cents[fi][k] / cell)) for k in range(3)]
        for x in range(lo[0], hi[0] + 1):
            for y in range(lo[1], hi[1] + 1):
                for z in range(lo[2], hi[2] + 1):
                    grid.setdefault((x, y, z), []).append(fi)
    elem_of = {}
    for root, members in elements.items():
        for fi in members:
            elem_of[fi] = root

    def plane(fi):
        n = normals[fi]
        return (round(n[0] * 1000), round(n[1] * 1000), round(n[2] * 1000), round(_dot(n, tris[fi][0]) * 1e4))
    planes = [plane(fi) for fi in range(len(faces))]
    copy_of, seen_tri = [], {}
    for fi in range(len(faces)):  # 0 for the first triangle on a vertex triple, 1 for its exact duplicate, ...
        key = frozenset(wf[fi])
        copy_of.append(seen_tri.get(key, 0))
        seen_tri[key] = copy_of[-1] + 1
    pp = list(range(len(faces)))

    def pfind(x):
        while pp[x] != x:
            pp[x] = pp[pp[x]]
            x = pp[x]
        return x
    for users in edges.values():
        for ui in range(len(users)):
            for uj in range(ui + 1, len(users)):
                (fi, a1, b1), (gj, a2, b2) = users[ui], users[uj]
                # a manifold neighbour in the same plane walks the edge the other way; an exact duplicate (the
                # same vertices, the same way round) is never merged into the patch of its original
                if a1 == b2 and b1 == a2 and planes[fi] == planes[gj] and copy_of[fi] == copy_of[gj]:
                    ra, rb = pfind(fi), pfind(gj)
                    if ra != rb:
                        pp[ra] = rb
    # Coplanar part of an element: the unit of a pair, whatever the triangulation (poly or triangle ids).
    patch_of = [pfind(fi) for fi in range(len(faces))]
    patch_area = {}
    for fi in range(len(faces)):
        patch_area[patch_of[fi]] = patch_area.get(patch_of[fi], 0.0) + areas[fi]
    seen, acc = set(), {}
    for bucket in grid.values():
        for ai in range(len(bucket)):
            i = bucket[ai]
            for bj in range(ai + 1, len(bucket)):
                j = bucket[bj]
                key = (i, j) if i < j else (j, i)
                if key in seen or patch_of[i] == patch_of[j]:
                    continue
                seen.add(key)
                i, j = key
                d = _dot(normals[i], normals[j])
                if abs(d) < opts['cos']:
                    continue
                area, c = _overlap(tris[i], tris[j], normals[i])
                if area <= 1e-12:
                    continue
                signed = _dot(_sub(c, tris[j][0]), normals[j])
                pk = (patch_of[i], patch_of[j]) if patch_of[i] < patch_of[j] else (patch_of[j], patch_of[i])
                a = acc.setdefault(pk + (d > 0,), [0.0, 0.0, set()])
                a[0] += area
                a[1] += area * (signed if patch_of[i] == pk[0] else -signed if d > 0 else signed)
                a[2] |= {i, j}
    pairs = []
    for (pa, pb, same), (area, moment, tri_set) in sorted(acc.items(), key=lambda kv: sorted(kv[1][2])):
        if area <= max(1e-9, 0.01 * min(patch_area[pa], patch_area[pb])):
            continue
        gap = abs(moment / area)
        if gap > reach:
            continue
        pairs.append((sorted({ids[t] for t in tri_set}), same, gap, tri_set))
    partner = set()
    double_sided = bool(obj.get('double_sided')) and opts['model'] == 'vpm'
    for both, same, gap, tri_set in pairs:
        fa, fb = both[0], both[-1]
        names = ', '.join(map(str, both))
        if same:
            if gap < opts['same_min_m']:
                found.append(('double_face', both, 'сонаправленные грани {}: зазор {:.4f} м < {} м '
                                                   '(VPM-2.3-13)'.format(names, gap, opts['same_min_m'])))
            continue
        roots = {elem_of[t] for t in tri_set}
        if len(roots) == 1 and closed_of[next(iter(roots))]:
            continue  # two sides of one closed thin body (pane, plate): not a double face
        partner |= tri_set
        if double_sided:
            if not opts['side_min_m'] <= gap <= opts['side_max_m']:
                found.append(('double_side_offset', both, 'вторая сторона граней {}: смещение {:.4f} м вне '
                                                          '{}..{} м (VPM-2.12-3)'.format(names, gap,
                                                                                         opts['side_min_m'],
                                                                                         opts['side_max_m'])))
        else:
            why = 'NPM-2.3-13: полигоны с opacity односторонние' if obj.get('double_sided') else                 'двойная грань там, где второй стороны быть не должно'
            found.append(('double_face', both, 'встречные грани {}: зазор {:.4f} м ({})'.format(
                names, gap, why)))
    if double_sided:
        lonely = [fi for fi in range(len(faces)) if fi not in partner and not closed_of[elem_of[fi]]
                  and areas[fi] > 0]
        if lonely:
            fid = sorted({ids[fi] for fi in lonely})
            found.append(('missing_double_side', fid, '{} граней без второй стороны (стекло/Flora/opacity, '
                                                      'VPM-2.12-3)'.format(len(fid))))
    sg = obj.get('sg')
    if sg is not None:
        if len(sg) != len(faces):
            raise ValueError('smoothing groups do not match faces: ' + obj['name'])
        if all(int(s) == 0 for s in sg):
            found.append(('sg_none', [], 'нет групп сглаживания ни на одной из {} граней (NPM-2.3-15, '
                                         'VPM-2.3-14)'.format(len(faces))))
    info = {'faces': len(faces), 'elements': len(elements), 'closed': n_closed, 'open': n_open,
            'pairs': len(pairs), 'double_sided': double_sided}
    return found, info


def normals_report(edit, objects, opts, state_hash, skipped=(), extra=None):
    if not objects and not skipped:
        raise ValueError('qa.normals: empty target set')
    entries, infos = [], {}
    skipped = list(skipped)
    for obj in objects:
        if len(obj['faces']) > opts['max_faces']:
            skipped.append(edit.skipped(obj['name'], '{} граней > max_faces {}'.format(len(obj['faces']),
                                                                                        opts['max_faces'])))
            continue
        found, info = mesh_normals(obj, opts)
        merged = {}
        for code, ids, detail in found:
            key = (code, tuple(ids) if code != 'double_face' else ())
            merged.setdefault(code, []).append((ids, detail))
        fl = []
        for code in NORMALS_CODES:
            for ids, detail in merged.get(code, []):
                fl.append(edit.finding(code, ids, detail))
        entries.append(edit.entry(obj['handle'], obj['name'], fl))
        infos[obj['name']] = info
    if not entries:
        raise ValueError('qa.normals: nothing checked: ' + '; '.join(s['reason'] for s in skipped))
    plan = {'read_only': True, 'units': 'm', 'thresholds': {k: v for k, v in opts.items()}, 'objects_info': infos}
    plan.update(extra or {})
    return edit.report('qa.normals', 'preview', entries, [], skipped, [], state_hash=state_hash, extra=plan)


# =====================================================================================================
# qa.sintez
# =====================================================================================================
SINTEZ_CODES = ('sintez_mismatch', 'sintez_unmatched')
# Rule -> our evidence. Only rules whose SINTEZ 1.6.1 check and ours measure the same thing
# (docs/agr/sintez_checks_1.6.1.json status same/partial). `pre`: qa.preflight codes (any = fail);
# `pkg`: qa.package validator stage + finding name.
SINTEZ_RULES = (
    {'side': 'hp', 'req': '2.3.18', 'pre': ('xform_scale', 'xform_rotation', 'xform_mirror'), 'what': 'трансформации сброшены'},
    {'side': 'lp', 'req': '2.3.14', 'pre': ('xform_scale', 'xform_rotation', 'xform_mirror'), 'what': 'трансформации сброшены'},
    {'side': 'hp', 'req': '2.3.11', 'pre': ('isolated_vertex', 'zero_length_edge', 'zero_area_face'), 'what': 'дубли и висячие элементы'},
    {'side': 'lp', 'req': '2.3.7', 'pre': ('isolated_vertex', 'zero_length_edge', 'zero_area_face'), 'what': 'дубли и висячие элементы'},
    {'side': 'hp', 'req': '2.3.8', 'pre': ('hyg_hierarchy', 'hyg_group'), 'what': 'нет иерархии и групп'},
    {'side': 'hp', 'req': '2.3.17', 'pkg': ('V003', 'triangulated'), 'what': 'триангуляция перед FBX'},
    {'side': 'lp', 'req': '2.3.11', 'pkg': ('V003', 'triangulated'), 'what': 'триангуляция перед FBX'},
)


def _req(x):
    return str(x).strip().replace('а', 'a')  # SINTEZ writes 2.9.4а with a Cyrillic а (tools/sintez_parity.py)


def sintez_verdicts(doc):
    """{(side, req): {'status': pass|fail|review|not_measured, 'raw': row}} of a SINTEZ checker report
    (jobs/KPP1/scripts/run_agr_checker.py: {'error', 'hp': [...], 'lp': [...]}). Broken report -> ValueError."""
    if not isinstance(doc, dict) or 'hp' not in doc or 'lp' not in doc:
        raise ValueError('SINTEZ report: expected keys hp and lp (run_agr_checker.py JSON)')
    if doc.get('error'):
        raise ValueError('SINTEZ report has a run error: ' + str(doc['error'])[:300])
    out = {}
    for side in ('hp', 'lp'):
        rows = doc[side]
        if not isinstance(rows, list):
            raise ValueError('SINTEZ report: {} is not a list'.format(side))
        for r in rows:
            if not isinstance(r, dict) or not str(r.get('req_num', '')).strip():
                continue
            req = _req(r['req_num'])
            key = (side, req)
            errors, recs, state = r.get('errors_count'), r.get('recommendations_count'), r.get('state')
            if r.get('auto') is not True or state not in ('verified', 'failed'):
                status = 'not_measured'
            else:
                if any(type(n) is not int or n < 0 for n in (errors, recs)):
                    raise ValueError('SINTEZ report: invalid counts for ' + req)
                if state == 'verified' and errors:
                    raise ValueError('SINTEZ report: verified with errors for ' + req)
                status = 'fail' if errors else 'review' if recs else 'pass'
            prev = out.get(key)
            if prev and prev['status'] != 'not_measured' and status != 'not_measured' and prev['status'] != status:
                status = 'fail' if 'fail' in (prev['status'], status) else 'review'
            if prev is None or status != 'not_measured':
                out[key] = {'status': status, 'raw': {k: r.get(k) for k in ('req_num', 'name', 'state', 'auto',
                                                                             'errors_count',
                                                                             'recommendations_count')}}
    if not any(v['status'] != 'not_measured' for v in out.values()):
        raise ValueError('SINTEZ report: no measured automatic rule')
    return out


def _preflight_codes(report):
    """{handle: set(codes)} and object names of a qa.preflight report (suite_core shape)."""
    if not isinstance(report, dict) or report.get('tool') != 'preflight' or not isinstance(report.get('objects'), list):
        raise ValueError('our report must be a qa.preflight report (tool: preflight)')
    out, names = {}, {}
    for o in report['objects']:
        out[o['handle']] = {f['code'] for f in o['findings']}
        names[o['handle']] = o['name']
    return out, names


def _package_findings(report):
    """{(stage, finding name): fail?} of a qa.package report (plan.reports[].stages[].non_pass)."""
    if not isinstance(report, dict) or report.get('tool') != 'qa.package':
        raise ValueError('package report must be a qa.package report')
    seen = {}
    for table in report['plan'].get('reports', []):
        for st in table['stages']:
            fails = {x.split(': ', 2)[1] for x in st['non_pass'] if x.startswith('fail: ') and ': ' in x[6:]}
            seen.setdefault(st['id'], set()).update(fails)
    return seen


def sintez_compare(sintez, preflight=None, package=None):
    """Rows rule -> ours / SINTEZ / agreement over SINTEZ_RULES plus every SINTEZ fail we do not map."""
    if preflight is None and package is None:
        raise ValueError('qa.sintez needs our report: qa.preflight (scene or file) and/or qa.package')
    pre = _preflight_codes(preflight) if preflight is not None else None
    pkg = _package_findings(package) if package is not None else None
    rows = []
    mapped = set()
    for rule in SINTEZ_RULES:
        key = (rule['side'], rule['req'])
        mapped.add(key)
        theirs = sintez.get(key, {'status': 'not_measured', 'raw': None})
        ours, culprits = 'not_measured', []
        if 'pre' in rule and pre is not None:
            culprits = sorted(h for h, codes in pre[0].items() if codes & set(rule['pre']))
            ours = 'fail' if culprits else 'pass'
        if 'pkg' in rule and pkg is not None:
            stage, fname = rule['pkg']
            if stage in pkg:
                ours = 'fail' if fname in pkg[stage] else 'pass'
        if theirs['status'] == 'not_measured' and ours == 'not_measured':
            continue
        a, b = ours != 'fail', theirs['status'] != 'fail'
        if 'not_measured' in (ours, theirs['status']):
            agree = None
        else:
            agree = a == b
        rows.append({'side': rule['side'], 'req': rule['req'], 'what': rule['what'], 'ours': ours,
                     'sintez': theirs['status'], 'agreement': agree, 'culprits': culprits,
                     'sintez_raw': theirs['raw']})
    for key, v in sorted(sintez.items()):
        if key in mapped or v['status'] != 'fail':
            continue
        rows.append({'side': key[0], 'req': key[1], 'what': (v['raw'] or {}).get('name') or '', 'ours': 'not_measured',
                     'sintez': 'fail', 'agreement': None, 'culprits': [], 'sintez_raw': v['raw']})
    return rows


def sintez_report(edit, rows, state_hash, nodes=None, extra=None):
    """nodes: [(handle, name)] of the scene check (findings on the objects), None: one object per rule row."""
    if not rows:
        raise ValueError('qa.sintez: no rule measured on both sides')
    bad = []
    for r in rows:
        if r['agreement'] is False:
            bad.append(('sintez_mismatch', r, 'правило {} {} ({}): наш вердикт {}, SINTEZ {}'.format(
                r['side'], r['req'], r['what'], r['ours'], r['sintez'])))
        elif r['sintez'] == 'fail' and r['ours'] == 'not_measured':
            bad.append(('sintez_unmatched', r, 'правило {} {} ({}): SINTEZ fail, у нас не проверяется'.format(
                r['side'], r['req'], r['what'])))
    objects = []
    if nodes is not None:
        found = {h: [] for h, _ in nodes}
        for code, r, detail in bad:
            targets = r['culprits'] if r['ours'] == 'fail' else [h for h, _ in nodes]
            for h in targets:
                if h in found:
                    found[h].append(edit.finding(code, (), detail))
        objects = [edit.entry(h, n, found[h]) for h, n in sorted(nodes)]
    else:
        for i, r in enumerate(rows, 1):
            fl = [edit.finding(code, (), detail) for code, rr, detail in bad if rr is r]
            objects.append(edit.entry(i, 'SINTEZ {} {}'.format(r['side'], r['req']), fl))
    table = [{k: r[k] for k in ('side', 'req', 'what', 'ours', 'sintez', 'agreement')} for r in rows]
    plan = {'read_only': True, 'table': table, 'rows': rows,
            'summary': {'rules': len(rows), 'agree': sum(1 for r in rows if r['agreement'] is True),
                        'mismatch': sum(1 for r in rows if r['agreement'] is False),
                        'unmatched': sum(1 for c, _, _ in bad if c == 'sintez_unmatched'),
                        'one_side_only': sum(1 for r in rows if r['agreement'] is None)}}
    plan.update(extra or {})
    return edit.report('qa.sintez', 'preview', objects, [], [], [], state_hash=state_hash, extra=plan)


def read_json_file(path, what):
    try:
        with open(path, 'rb') as f:
            raw = f.read()
    except OSError as exc:
        raise ValueError('{}: cannot read {}: {}'.format(what, path, exc)) from None
    try:
        return json.loads(raw.decode('utf-8-sig'))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValueError('{}: not a UTF-8 JSON file {}: {}'.format(what, path, exc)) from None


# =====================================================================================================
# qa.procedural_objects
# =====================================================================================================
PROCEDURAL_CODES = ('proc_object', 'proc_missing_plugin')
TRIS_WARNING = 'треугольники этих объектов не посчитаны в qa.tris (снимок Max и FBX расходятся, L07)'
_MISSING = re.compile(r'^Missing_', re.IGNORECASE)


def load_classes(path):
    """data/procedural_classes.json -> {class_lower: entry}; strict (owner C, #979, class names only)."""
    doc = read_json_file(path, 'procedural_classes.json')
    if not isinstance(doc, dict) or doc.get('owner') != 'C' or doc.get('issue') != '#979' \
            or not isinstance(doc.get('classes'), list) or not doc['classes']:
        raise ValueError('procedural_classes.json: owner C / issue #979 / non-empty classes required')
    out = {}
    for e in doc['classes']:
        if not isinstance(e, dict) or not {'class', 'product', 'measured', 'source'} <= set(e):
            raise ValueError('procedural_classes.json: class entry needs class/product/measured/source: ' + repr(e))
        if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', str(e['class'])) or _MISSING.match(e['class']):
            raise ValueError('procedural_classes.json: bad class name ' + repr(e['class']))
        key = e['class'].lower()
        if key in out:
            raise ValueError('procedural_classes.json: duplicate class ' + e['class'])
        out[key] = e
    return out


def procedural_scan(rows, classes, available):
    """rows: [{handle, name, cls, superclass, hidden, frozen}] of scene nodes. available: set of class names
    present in this Max (lower case). Returns (hits, products)."""
    hits = []
    for r in rows:
        cls = str(r['cls'])
        e = classes.get(cls.lower())
        if _MISSING.match(cls):
            hits.append(dict(r, code='proc_missing_plugin', product=None,
                             reason='объект отсутствующего плагина ({}): Max держит заглушку, геометрии в FBX не будет'
                             .format(cls)))
        elif e is not None:
            hits.append(dict(r, code='proc_object', product=e['product'],
                             reason='процедурный объект {} ({}): свернуть в Editable Poly до экспорта'.format(
                                 e['class'], e['product'])))
    products = {}
    for e in classes.values():
        p = products.setdefault(e['product'], {'product': e['product'], 'classes': [], 'installed': []})
        p['classes'].append(e['class'])
        if e['class'].lower() in available:
            p['installed'].append(e['class'])
    rows_out = []
    for p in sorted(products.values(), key=lambda x: x['product']):
        p['status'] = 'установлен' if p['installed'] else 'плагин не установлен'
        rows_out.append(p)
    return hits, rows_out


def procedural_report(edit, rows, hits, products, state_hash, extra=None):
    """objects: every scanned node (offenders carry the finding). plan.procedural: the STABLE list that
    export.batch (branch D) reads through runtime.edits_090('qa.procedural_objects', 'preview'):
    [{handle, name, class, superclass, product, code, hidden, frozen}] sorted by handle."""
    if not rows:
        raise ValueError('qa.procedural_objects: empty target set')
    by = {h['handle']: h for h in hits}
    objects = []
    for r in sorted(rows, key=lambda x: x['handle']):
        h = by.get(r['handle'])
        fl = [edit.finding(h['code'], (), h['reason'])] if h else []
        objects.append(edit.entry(r['handle'], r['name'], fl))
    procedural = [{'handle': h['handle'], 'name': h['name'], 'class': str(h['cls']), 'superclass': str(h['superclass']),
                   'product': h['product'], 'code': h['code'], 'hidden': bool(h.get('hidden')),
                   'frozen': bool(h.get('frozen'))} for h in sorted(hits, key=lambda x: x['handle'])]
    plan = {'read_only': True, 'procedural': procedural, 'blocking': [p['handle'] for p in procedural],
            'products': products, 'warnings': [TRIS_WARNING] if procedural else [],
            'summary': {'scanned': len(rows), 'procedural': len(procedural),
                        'missing_plugin': sum(1 for p in procedural if p['code'] == 'proc_missing_plugin')}}
    plan.update(extra or {})
    return edit.report('qa.procedural_objects', 'preview', objects, [], [], [], state_hash=state_hash, extra=plan)
