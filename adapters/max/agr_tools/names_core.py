"""new-case: AGR Tools 0.8 (#908) names logic, stdlib only (branch C, improve/issue-908-names).

Pure logic for `ucx_rename` (ucx.rename) and `qa_names_fix` (qa.names_fix); no pymxs. One grammar serves both:
the UCX collision mask `UCX_SM_<Address>_(Main|Ground)_NNN` and the SM/M/T masks of NPM/VPM are built and parsed
here, and checks_core.name_findings (the 0.5.0 names check) is the acceptance gate for every produced name.

Lab sources (docs/experiments/ucx.rename.md L01, qa.names_fix.md L03): GeoAGR UCX Rename `GeoAGR.ms:62907-62920`
and Material Cloner `GeoAGR.ms:55620-55769` were measured in Max 2024; no GeoAGR or team code is copied (#853).
Team scripts were read for ideas only: AlexYo_AGR_renamerV2.ms (sha256 2f49107c…41632: object -> M_/T_ names
from the object name, slot suffix by material property), AlexYo_CheckAssetNames_v8.ms (sha256 a3067e16…88cc1:
invisible characters, Cyrillic homoglyphs, transliteration), A101AGRLP.ms (sha256 86c43d4d…6926: map role by
`*_d*` substring, Ground FBX name with a doubled underscore at :388 — neither is taken over).

Fixed source defects (each has a regression test in tests/max_tools/test_agr_tools_names.py):
ucx.rename  U1 only UCX geometry is renamed (render model, helpers, cameras, lights are skipped and reported);
            U2 stable numbering by old number, then old name, then handle (not selection order);
            U3 the address is never trimmed (`Tverskaya_12`, `1st` survive); U4 prefix is case-insensitive,
            an inner `UCX_` is kept as address text, digits-only names are refused; U5 one grammar,
            3-digit 001..999, > 999 in one group is an error; names held by other nodes are not reused;
            U6 one undo record (glue). Idempotent: a second run plans no rename.
names_fix   N1 export copies only (glue); N2 objects, materials and map files are named by the masks, not only
            the material; N3 the mask is applied to the FILE NAME only, the folder is never rewritten;
            N4 a map is repointed only to a file that exists after the copy; a missing source is a failure in the
            report, not a silent repoint; N5 an existing destination file is never overwritten (reused, its hash
            reported); N6 a target's own material is not replaced unless `replace_material` is set, and either
            way it is reported; N7 every failure is in the report (no Listener-only messages).

0.9 rework (#979, branch E1; team-audit T06 cards, all measured in Max 2024; team scripts read for ideas, no code):
V1  a destination file that exists with OTHER content is never overwritten AND never linked (renamer V13
    `File.Copy overwrite`, Asset Material Renamer "skip existing" relinked a foreign file): the map stays on its
    source, the conflict is a failure; identical content is reused.
V2  slot table (V13): one role per slot; reflectionMap has no NPM/VPM role (V13 gave `_m` to specular AND
    reflection, one copy overwrote the other) and is reported, never renamed to `_m`.
V3  names come from the grammar, never by cutting characters (V13 "Bench" -> "Mnch"; prefix collision
    SM_Chair/XX_Chair -> one M_Chair_1); two targets with one name are ambiguous.
V4  `folder`: map copies into a separate folder (Asset Material Renamer), mask in the FILE name only.
V5  library profile `Brand_Name_Article_high|low` (CheckAssetNames v8): invisible characters, homoglyphs and
    transliteration in one pass (order cannot matter: "Стул_Дерево" -> "Stul_Derevo", never "Ctyl_Depevo");
    hyphens, digit-first segments and Max `.001` suffixes are refused with a reason, not passed.
V6  0 duplicate names: a produced name held by another scene object (not selected, not an export copy) is
    ambiguous (CheckNames fixed into an existing name; Max allows duplicates).
V7  names of the 7 roles from Address + OKS number + slot (A101LP), FBX names included, never `__` (A101 :388).
Transliteration: one table (`TRANSLIT`, `transliterate`) shared with qa.address (branch C). Й -> "y" here; GeoAGR
writes "j" (`GeoAGR.ms:194`): `translit_variants` gives both spellings for comparisons.
"""
import posixpath
import re
import unicodedata

UCX_MAX = 999
UCX_KINDS = ('Main', 'Ground')
UCX_MASK = re.compile(r'^UCX_SM_(?P<address>[A-Za-z0-9_]+)_(?P<kind>Main|Ground)_(?P<num>\d{3})$')
# Tolerant reader: any case of the prefix, repeated `UCX_` prefixes from earlier damage, optional `SM_`,
# kind in any case, any number width, or no number. The address is everything in between, untouched.
_UCX_READ = re.compile(r'^(?:ucx_)+(?:(?P<sm>sm)_)?(?P<address>.+?)_(?P<kind>main|ground)(?:_(?P<num>\d+))?$',
                       re.IGNORECASE)
_ADDRESS = re.compile(r'[A-Za-z0-9]+(?:_[A-Za-z0-9]+)*')

NPM_MAP = {'diffuse': 'd', 'normal': 'n', 'opacity': 'o', 'metalness': 'm', 'roughness': 'r'}
VPM_MAP = {'diffuse': 'Diffuse', 'normal': 'Normal', 'opacity': None, 'metalness': 'ERM', 'roughness': 'ERM',
           'emission': 'ERM'}
ROLES = ('diffuse', 'normal', 'opacity', 'metalness', 'roughness', 'emission')
TYPES = ('Main', 'MainGlass', 'Ground', 'GroundGlass', 'GroundEl', 'GroundElGlass', 'Flora')
MAX_SLOTS = 7
_UDIM_TAIL = re.compile(r'[._](?P<udim>1(?:0[0-9][1-9]|0[1-9]0|100))$')
_OKS = re.compile(r'^(?P<head>.*?)_(?P<oks>\d{1,3})_(?P<type>MainGlass|Main)$', re.IGNORECASE)

# Cyrillic letters that look like Latin ones (homoglyphs) and a plain transliteration for the rest.
_HOMOGLYPH = dict(zip('АВЕКМНОРСТХаеорсухіІ', 'ABEKMHOPCTXaeopcyxiI'))
_TRANSLIT = {'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e', 'ж': 'zh', 'з': 'z', 'и': 'i',
             'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't',
             'у': 'u', 'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'shch', 'ъ': '', 'ы': 'y',
             'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya'}
TRANSLIT = dict(_TRANSLIT)  # public read-only view (qa.address, udim.slots)
_TRANSLIT_ALT = {'й': ('y', 'j')}  # GeoAGR.ms:194 writes j

# Material slot -> map role (V13 slot table). None: the slot has no NPM/VPM texture role; a bitmap there is
# reported and left as is (reflection is NOT metalness: V13 named both `_m`).
SLOT_TABLE = {
    'PhysicalMaterial': (('base_color_map', 'diffuse'), ('bump_map', 'normal'), ('roughness_map', 'roughness'),
                         ('metalness_map', 'metalness'), ('cutout_map', 'opacity'), ('transparency_map', 'opacity'),
                         ('emission_map', 'emission'), ('reflectivity_map', None)),
    'Standardmaterial': (('diffuseMap', 'diffuse'), ('bumpMap', 'normal'), ('opacityMap', 'opacity'),
                         ('glossinessMap', 'roughness'), ('specularLevelMap', 'metalness'), ('reflectionMap', None),
                         ('specularMap', None)),
}
PROFILES = ('project', 'library')
LIBRARY_LODS = ('high', 'low')
_LIB_DUP = re.compile(r'\.\d{3}$')


# ---- UCX grammar ----------------------------------------------------------------------------------------
def is_ucx_like(name):
    """Any-case `UCX_` prefix (the reader decides whether the rest is parsable)."""
    return isinstance(name, str) and name[:4].upper() == 'UCX_'


def ucx_name(address, kind, number):
    if not _ADDRESS.fullmatch(str(address)):
        raise ValueError('UCX address must be Latin letters, digits and single "_": ' + repr(address))
    if kind not in UCX_KINDS:
        raise ValueError('UCX kind must be Main or Ground: ' + repr(kind))
    if type(number) is not int or not 1 <= number <= UCX_MAX:
        raise ValueError('UCX number must be 1..{}: {!r}'.format(UCX_MAX, number))
    out = 'UCX_SM_{}_{}_{:03d}'.format(address, kind, number)
    assert UCX_MASK.fullmatch(out)
    return out


def parse_ucx(name):
    """{'address', 'kind', 'number'(int|None), 'canonical'(bool)} or a reason string why it cannot be read.

    Never trims digits or underscores off the address (U3); `UCX_` in any case and repeated is one prefix (U4)."""
    if not is_ucx_like(name):
        return 'not a UCX name'
    m = _UCX_READ.fullmatch(name.strip())
    if not m:
        return 'UCX name without _Main/_Ground: ' + name
    address = m.group('address')
    if not m.group('sm') and address.upper().startswith('SM_'):
        address = address[3:]
    if not _ADDRESS.fullmatch(address) or address.isdigit():
        return 'UCX address is empty, digits only or has characters other than A-Z a-z 0-9 _: ' + name
    kind = m.group('kind').capitalize()
    num = int(m.group('num')) if m.group('num') is not None else None
    return {'address': address, 'kind': kind, 'number': num, 'canonical': bool(UCX_MASK.fullmatch(name))}


def ucx_plan(items, occupied=()):
    """Plan the UCX renames of one run.

    items: [{'key', 'name', 'geometry'(bool)}] — key is a unique int (node handle). occupied: names held by nodes
    outside the run; they are never produced (an unselected `UCX_SM_A_Main_002` keeps number 2 taken).
    Returns {'rename': [{key, old, new}], 'unchanged': [{key, name}], 'skipped': [{key, name, reason}],
             'errors': [{group, keys, reason}]}; a group over 999 pieces is an error and nothing in it is renamed.
    """
    keys = [it['key'] for it in items]
    if len(set(keys)) != len(keys):
        raise ValueError('duplicate key in UCX plan')
    taken = set(occupied)
    groups, out = {}, {'rename': [], 'unchanged': [], 'skipped': [], 'errors': []}
    for it in items:
        name = str(it['name'])
        if not is_ucx_like(name):
            out['skipped'].append({'key': it['key'], 'name': name, 'reason': 'not a UCX piece (name has no UCX_ prefix)'})
            continue
        if not it.get('geometry'):
            out['skipped'].append({'key': it['key'], 'name': name, 'reason': 'UCX name on a non-geometry node'})
            continue
        parsed = parse_ucx(name)
        if isinstance(parsed, str):
            out['skipped'].append({'key': it['key'], 'name': name, 'reason': parsed})
            continue
        groups.setdefault((parsed['address'], parsed['kind']), []).append((it, parsed))
    for (address, kind), members in sorted(groups.items()):
        # U2: by old number (unnumbered last), then old name, then key — never by selection order.
        members.sort(key=lambda p: (p[1]['number'] is None, p[1]['number'] or 0, str(p[0]['name']), p[0]['key']))
        free = [n for n in range(1, UCX_MAX + 1) if ucx_name(address, kind, n) not in taken]
        group = 'UCX_SM_{}_{}'.format(address, kind)
        if len(members) > len(free):
            out['errors'].append({'group': group, 'keys': sorted(m[0]['key'] for m in members),
                                  'reason': '{} pieces > {} free numbers 001..{:03d}'.format(len(members), len(free), UCX_MAX)})
            continue
        for (it, _), number in zip(members, free):
            new = ucx_name(address, kind, number)
            if new == it['name']:
                out['unchanged'].append({'key': it['key'], 'name': new})
            else:
                out['rename'].append({'key': it['key'], 'old': str(it['name']), 'new': new})
    for k in out:
        out[k].sort(key=lambda r: (min(r['keys']) if 'keys' in r else r['key']))
    return out


# ---- object / material / texture masks ------------------------------------------------------------------
def clean_text(name):
    """Character-level clean-up only: invisible characters and edge blanks dropped, Cyrillic homoglyphs to Latin,
    other Cyrillic transliterated, spaces/dashes/dots to `_`, repeated `_` collapsed. Returns (text, changes)."""
    changes = []
    text = ''.join(c for c in str(name) if unicodedata.category(c) not in ('Cf', 'Cc'))
    if text != name:
        changes.append('invisible characters removed')
    stripped = text.strip()
    if stripped != text:
        changes.append('edge blanks removed')
    out = []
    # A word that mixes Latin letters with look-alike Cyrillic ones is a typo (homoglyphs -> Latin); a word of
    # Cyrillic letters is Russian text (transliterated as a whole, never half-homoglyph garbage).
    for word in re.split(r'([^\w]|_|\d)', stripped):
        latin = any('a' <= c.lower() <= 'z' for c in word)
        homoglyph_only = all(c in _HOMOGLYPH for c in word if c.lower() in _TRANSLIT)
        for c in word:
            if c in _HOMOGLYPH and latin and homoglyph_only:
                out.append(_HOMOGLYPH[c])
                changes.append('homoglyph ' + c)
            elif c.lower() in _TRANSLIT:
                t = _TRANSLIT[c.lower()]
                out.append(t.capitalize() if c.isupper() else t)
                changes.append('transliterated ' + c)
            else:
                out.append(c)
    text = ''.join(out)
    replaced = re.sub(r'[\s\-.]+', '_', text)
    if replaced != text:
        changes.append('space/dash/dot -> _')
    collapsed = re.sub(r'_+', '_', replaced).strip('_')
    if collapsed != replaced:
        changes.append('repeated/edge _ removed')
    return collapsed, sorted(set(changes))


def transliterate(text):
    """Cyrillic -> Latin by TRANSLIT (case kept on the first letter); other characters unchanged."""
    out = []
    for c in str(text):
        t = _TRANSLIT.get(c.lower())
        out.append(c if t is None else (t.capitalize() if c.isupper() else t))
    return ''.join(out)


def translit_variants(text):
    """Every accepted Latin spelling of a Cyrillic text (Й -> y or j, GeoAGR.ms:194), sorted; `transliterate`
    first."""
    variants = ['']
    for c in str(text):
        alts = _TRANSLIT_ALT.get(c.lower())
        if alts is None:
            t = transliterate(c)
            variants = [v + t for v in variants]
        else:
            variants = [v + (a.capitalize() if c.isupper() else a) for v in variants for a in alts]
    main = transliterate(text)
    return [main] + sorted(set(variants) - {main})


def library_name(name):
    """Library asset name `Brand_Name[_Name...]_Article_high|low` (CheckAssetNames v8 profile, V5).

    Returns {'name', 'changes'} or a reason string. Fixed: invisible characters, edge blanks, spaces -> `_`,
    homoglyphs/transliteration (one pass, order-free), Brand/Name first letter upper case, LOD lower case.
    Refused: hyphens, Max duplicate suffix `.NNN`, empty or digit-first segments, LOD not high/low, < 4 segments."""
    raw = str(name)
    if _LIB_DUP.search(raw.strip()):
        return 'Max duplicate suffix {}: rename by hand (two objects share the base name)'.format(raw.strip()[-4:])
    if '-' in raw:
        return 'hyphen in the name: segments are joined by "_" only'
    text = re.sub(r'\s+', '_', ''.join(c for c in raw if unicodedata.category(c) not in ('Cf', 'Cc')).strip())
    cleaned, changes = clean_text(text)
    if text != raw:
        changes = sorted(set(changes) | {'invisible characters or blanks fixed'})
    if '__' in text or text.startswith('_') or text.endswith('_'):
        return 'empty segment in ' + text
    if re.fullmatch(r'[A-Za-z0-9_]+', cleaned) is None:
        return 'characters other than A-Z a-z 0-9 _ remain: ' + cleaned
    parts = cleaned.split('_')
    if len(parts) < 4:
        return 'expected Brand_Name_Article_high|low (4+ segments): ' + cleaned
    lod = parts[-1].lower()
    if lod not in LIBRARY_LODS:
        return 'last segment must be high or low: ' + parts[-1]
    if any(p.lower() in LIBRARY_LODS for p in parts[:-1]):
        return 'high/low only as the last segment: ' + cleaned
    for p in parts[:-1]:
        if p[0].isdigit():
            return 'segment starts with a digit: {} in {}'.format(p, cleaned)
    fixed = [p[0].upper() + p[1:] for p in parts[:-2]] + [parts[-2], lod]
    out = '_'.join(fixed)
    if out != cleaned:
        changes = sorted(set(changes) | {'case fixed'})
    return {'name': out, 'changes': changes}


def role_names(address, oks=None, slot=1, code=None, model='npm'):
    """Names of the 7 roles (A101LP idea, V7): {type: {object, material, textures{role: stem}, fbx}}.

    NPM: SM_<Address>_<NNN>_Main|MainGlass (OKS 1..20), SM_<Address>_<Type> for Ground roles and Flora; FBX
    `<code>_<Address>_<NN>.fbx` / `<code>_<Address>_Ground.fbx` (code: 4 digits). VPM: Main/MainGlass/Ground/
    GroundGlass only, FBX SM_<Address>.fbx / SM_<Address>_Ground.fbx. Never a doubled `_` (A101AGRLP.ms:388)."""
    if not _ADDRESS.fullmatch(str(address)):
        raise ValueError('address must be Latin letters, digits and single "_": ' + repr(address))
    if model not in ('npm', 'vpm'):
        raise ValueError('model must be npm or vpm')
    if model == 'npm':
        if type(oks) is not int or not 1 <= oks <= 20:
            raise ValueError('NPM OKS number must be 1..20: ' + repr(oks))
        if code is not None and not re.fullmatch(r'\d{4}', str(code)):
            raise ValueError('FBX code must be 4 digits: ' + repr(code))
    types = TYPES if model == 'npm' else ('Main', 'MainGlass', 'Ground', 'GroundGlass')
    out = {}
    for t in types:
        building = t in ('Main', 'MainGlass')
        obj = {'address': address, 'oks': '{:03d}'.format(oks) if model == 'npm' and building else None, 'type': t}
        textures = {}
        for role in ROLES:
            stem = texture_stem(obj, model, role, slot)
            if stem:
                textures[role] = stem
        if model == 'npm':
            fbx = None if code is None else ('{}_{}_{:02d}.fbx'.format(code, address, oks) if building
                                              else '{}_{}_Ground.fbx'.format(code, address))
        else:
            fbx = 'SM_{}.fbx'.format(address) if building else 'SM_{}_Ground.fbx'.format(address)
        names = {'object': '_'.join(['SM', address] + ([obj['oks']] if obj['oks'] else []) + [t]),
                 'material': material_name(obj, slot), 'textures': textures, 'fbx': fbx}
        for v in [names['object'], names['material'], names['fbx'] or ''] + list(textures.values()):
            assert '__' not in v, v
        out[t] = names
    return out


def parse_object(name, model):
    """{'address', 'oks'(str|None), 'type', 'name'} for an SM object name of `model` ('npm'|'vpm'), or a reason.

    Repairs only what is unambiguous: characters (clean_text), the `SM_` prefix case or absence, the type token
    case, the NPM OKS number width (`_1_Main` -> `_001_Main`, 1..20). The address is otherwise kept as written."""
    if model not in ('npm', 'vpm'):
        raise ValueError('model must be npm or vpm: ' + repr(model))
    text, _ = clean_text(name)
    if not text:
        return 'empty name'
    if re.fullmatch(r'[A-Za-z0-9_]+', text) is None:
        return 'characters other than A-Z a-z 0-9 _ remain after clean-up: ' + text
    tokens = text.split('_')
    if tokens[0].upper() == 'SM':
        tokens = tokens[1:]
    elif tokens[0].upper() in ('UCX', 'M', 'T'):
        return 'not an SM object name: ' + text
    if len(tokens) < 2:
        return 'no Address and geometry type: ' + text
    types = {t.lower(): t for t in TYPES}
    kind = types.get(tokens[-1].lower())
    if kind is None:
        return 'last element is not a geometry type ({}): {}'.format('/'.join(TYPES), text)
    if model == 'vpm' and kind not in ('Main', 'MainGlass', 'Ground', 'GroundGlass'):
        return 'VPM has no {} objects: {}'.format(kind, text)
    body = tokens[:-1]
    oks = None
    if model == 'npm' and kind in ('Main', 'MainGlass'):
        if len(body) < 2 or not body[-1].isdigit():
            return 'no OKS number before {} (NPM SM_Address_NNN_{}): {}'.format(kind, kind, text)
        n = int(body[-1])
        if not 1 <= n <= 20:
            return 'OKS number {} outside 001..020: {}'.format(body[-1], text)
        oks, body = '{:03d}'.format(n), body[:-1]
    if not body or (len(body) == 1 and body[0].isdigit()):
        return 'no Address element: ' + text
    address = '_'.join(body)
    parts = ['SM', address] + ([oks] if oks else []) + [kind]
    return {'address': address, 'oks': oks, 'type': kind, 'name': '_'.join(parts)}


def material_name(obj, slot):
    """M_<Address>[_NNN]_<Type>_<Slot> (NPM-2.10-3.5, VPM-2.10-4.4)."""
    if type(slot) is not int or not 1 <= slot <= MAX_SLOTS:
        raise ValueError('SlotNumber must be 1..7: ' + repr(slot))
    return '_'.join(['M', obj['address']] + ([obj['oks']] if obj['oks'] else []) + [obj['type'], str(slot)])


def texture_stem(obj, model, role, slot, udim=None):
    """File stem by NPM-2.10-3.4 / VPM-2.10-4.3, or None when the role has no map in that model.

    NPM: T_<Address>[_NNN]_<Type>_<d|n|o|m|r>_<Slot>; VPM: T_<Address>[_Ground]_<Diffuse|ERM|Normal>_<Slot>.<UDIM>
    (buildings carry no type token; Ground/GroundGlass carry `_Ground`)."""
    if role not in ROLES:
        raise ValueError('unknown map role: ' + repr(role))
    if type(slot) is not int or not 1 <= slot <= MAX_SLOTS:
        raise ValueError('SlotNumber must be 1..7: ' + repr(slot))
    if model == 'npm':
        suffix = NPM_MAP.get(role)
        if suffix is None:
            return None
        return '_'.join(['T', obj['address']] + ([obj['oks']] if obj['oks'] else []) + [obj['type'], suffix, str(slot)])
    suffix = VPM_MAP.get(role)
    if suffix is None:
        return None
    udim = 1001 if udim is None else int(udim)
    if not 1001 <= udim <= 1100:
        raise ValueError('UDIM must be 1001..1100: ' + repr(udim))
    ground = ['Ground'] if obj['type'].startswith('Ground') else []
    return '_'.join(['T', obj['address']] + ground + [suffix, str(slot)]) + '.' + str(udim)


def udim_of(path):
    """UDIM tile written at the end of a file stem (`.1001` / `_1001`), else None."""
    stem = posixpath.splitext(posixpath.basename(str(path).replace('\\', '/')))[0]
    m = _UDIM_TAIL.search(stem)
    return int(m.group('udim')) if m else None


def target_path(source, stem, folder=None):
    """New file name `<stem><ext>` in the source folder, or in `folder` (V4, Asset Material Renamer: copies into a
    separate folder). The mask never touches folder names (N3)."""
    src = str(source)
    base_folder = src if folder is None else str(folder).rstrip('\\/') + '/x'
    sep = '\\' if '\\' in base_folder and '/' not in base_folder else '/'
    norm = src.replace('\\', '/')
    dirname, base = posixpath.split(norm)
    if folder is not None:
        dirname = str(folder).replace('\\', '/').rstrip('/')
    ext = posixpath.splitext(base)[1].lower()
    out = (dirname + '/' if dirname else '') + stem + ext
    return out.replace('/', sep) if sep == '\\' else out


# ---- names_fix plan -------------------------------------------------------------------------------------
def _material_slots(material):
    """[(slot, submaterial dict)] — a single material is slot 1; a Multi/Sub gives its used sub-materials in
    ascending material ID order, numbered 1..k (SlotNumber is sequential from 1, NPM-2.10-3.4)."""
    if material.get('subs') is None:
        return [(1, material)]
    used = [s for s in sorted(material['subs'], key=lambda s: s['id']) if s.get('used', True)]
    return [(i, s) for i, s in enumerate(used, 1)]


def names_fix_plan(state, options):
    """Plan of qa.names_fix from a plain scene state (glue: names_max.read_state). Pure; changes nothing.

    state = {'objects': [{key, name, geometry, model(str|None), material(dict|None), ucx(bool)}],
             'files': {path: {'exists': bool, 'sha256': str|None}}, 'export_names': [names on the export layer]}
    material = {key, name, class, subs: None | [{id, used, key, name, class, maps}], maps: [{key, role, path,
                name}]} — maps of a sub-material sit in its own dict.
    options: model ('npm'|'vpm'|None = per object), donor (object name|None), replace_material (bool);
    0.9: profile ('project'|'library'), folder (absolute folder for the map copies, V4), address + oks (names
    of the role from the type token of each object, V7). state may hold 'scene_names': names of the other scene
    objects (not selected, not export copies) that a produced name must not repeat (V6).
    """
    model_opt = options.get('model')
    if model_opt not in (None, 'npm', 'vpm'):
        raise ValueError('options.model must be npm, vpm or absent')
    replace = bool(options.get('replace_material', False))
    if not isinstance(options.get('replace_material', False), bool):
        raise ValueError('options.replace_material must be true/false')
    profile = options.get('profile') or 'project'
    if profile not in PROFILES:
        raise ValueError('options.profile must be project or library')
    folder = options.get('folder')
    if folder is not None and (not isinstance(folder, str) or not re.match(r'^(?:[A-Za-z]:[\\/]|[\\/]{2}|/)', folder)):
        raise ValueError('options.folder must be an absolute folder path')
    address_opt, oks_opt = options.get('address'), options.get('oks')
    if address_opt is not None and not _ADDRESS.fullmatch(str(address_opt)):
        raise ValueError('options.address must be Latin letters, digits and single "_"')
    if oks_opt is not None and (type(oks_opt) is not int or not 1 <= oks_opt <= 20):
        raise ValueError('options.oks must be 1..20')
    if oks_opt is not None and address_opt is None:
        raise ValueError('options.oks needs options.address')
    if profile == 'library' and (address_opt is not None or model_opt is not None):
        raise ValueError('library profile takes no address/oks/model')
    scene_names = set(state.get('scene_names', ()))
    donor_name = options.get('donor')
    objects = state['objects']
    files = state['files']
    donor = None
    if donor_name is not None:
        hits = [o for o in objects if o['name'] == donor_name]
        if len(hits) != 1:
            raise ValueError('options.donor must name exactly one selected object: ' + repr(donor_name))
        donor = hits[0]
        if donor['material'] is None:
            raise ValueError('donor {} has no material'.format(donor_name))
    plan = {'objects': [], 'skipped': [], 'ambiguous': [], 'files': [], 'materials': [], 'failures': []}
    ucx_items = [{'key': o['key'], 'name': o['name'], 'geometry': o['geometry']} for o in objects if o.get('ucx')]
    ucx = ucx_plan(ucx_items)  # copies live on the export layer: working names are not "occupied"
    export_names = set(state.get('export_names', ()))
    for r in ucx['rename'] + [{'key': u['key'], 'old': u['name'], 'new': u['name']} for u in ucx['unchanged']]:
        if r['new'] in scene_names:
            plan['ambiguous'].append({'keys': [r['key']], 'item': r['new'],
                                      'reason': 'another scene object already has this name (Max allows duplicates; '
                                                'a fix must not make one)'})
            continue
        if r['new'] in export_names:
            plan['ambiguous'].append({'keys': [r['key']], 'item': r['new'],
                                      'reason': 'an export copy with this name already exists (repeat run): '
                                                'delete or rename it first, nothing is overwritten'})
            continue
        plan['objects'].append({'key': r['key'], 'old': r['old'], 'new': r['new'], 'kind': 'ucx'})
    for s in ucx['skipped']:
        plan['skipped'].append({'key': s['key'], 'item': s['name'], 'reason': s['reason']})
    for e in ucx['errors']:
        plan['ambiguous'].append({'keys': e['keys'], 'item': e['group'], 'reason': e['reason']})
    seen_targets = {}
    for o in objects:
        if o.get('ucx'):
            continue
        if not o['geometry']:
            plan['skipped'].append({'key': o['key'], 'item': o['name'], 'reason': 'not geometry'})
            continue
        if profile == 'library':
            model = 'library'
            parsed = library_name(o['name'])
            if isinstance(parsed, dict):
                parsed = {'address': parsed['name'], 'oks': None, 'type': None, 'name': parsed['name'],
                          'library': True, 'changes': parsed['changes']}
        else:
            model = model_opt or o.get('model')
            if model is None and address_opt is not None:
                model = 'npm' if oks_opt is not None else None
            if model is None:
                guess = parse_object(o['name'], 'npm')
                if isinstance(guess, dict) and guess['oks']:
                    model = 'npm'
                elif isinstance(guess, str) and 'OKS' not in guess:
                    plan['skipped'].append({'key': o['key'], 'item': o['name'], 'reason': guess})
                    continue
            if model is None:
                plan['skipped'].append({'key': o['key'], 'item': o['name'],
                                        'reason': 'model unknown (NPM or VPM): set options.model or AGR_EXPORT_PATH'})
                continue
            parsed = (parse_object(o['name'], model) if address_opt is None
                      else _role_object(o['name'], model, address_opt, oks_opt))
        if isinstance(parsed, str):
            plan['skipped'].append({'key': o['key'], 'item': o['name'], 'reason': parsed})
            continue
        new = parsed['name']
        if new in seen_targets:
            plan['ambiguous'].append({'keys': sorted([seen_targets[new], o['key']]), 'item': new,
                                      'reason': 'two selected objects map to the same name'})
            continue
        if new in export_names:
            plan['ambiguous'].append({'keys': [o['key']], 'item': new,
                                      'reason': 'an export copy with this name already exists (repeat run): '
                                                'delete or rename it first, nothing is overwritten'})
            continue
        if new in scene_names:
            plan['ambiguous'].append({'keys': [o['key']], 'item': new,
                                      'reason': 'another scene object already has this name (Max allows duplicates; '
                                                'a fix must not make one)'})
            continue
        seen_targets[new] = o['key']
        entry = {'key': o['key'], 'old': o['name'], 'new': new, 'kind': 'sm', 'model': model}
        plan['objects'].append(entry)
        material, source = o['material'], 'own'
        if donor is not None and o is not donor:
            if material is None:
                material, source = donor['material'], 'donor'
            elif replace:
                plan['materials'].append({'key': o['key'], 'material': material['name'], 'action': 'replaced by donor',
                                          'donor': donor['name']})
                material, source = donor['material'], 'donor'
            else:
                plan['materials'].append({'key': o['key'], 'material': material['name'], 'action': 'kept (own material)',
                                          'donor': donor['name']})
        entry['material_source'] = source
        if material is None:
            plan['failures'].append({'key': o['key'], 'item': o['name'], 'reason': 'no material: nothing to name'})
            continue
        _plan_material(plan, o['key'], parsed, model, material, files, folder)
    for k in ('objects', 'skipped', 'files', 'materials', 'failures'):
        plan[k].sort(key=lambda r: (r['key'], str(r.get('slot', '')), str(r.get('role', '')), str(r.get('item', ''))))
    plan['ambiguous'].sort(key=lambda r: r['keys'])
    return plan


def _role_object(name, model, address, oks):
    """V7: the object takes the name of its role (type token of the current name) under the given address/OKS."""
    text, _ = clean_text(name)
    kind = {t.lower(): t for t in TYPES}.get((text.split('_') or [''])[-1].lower())
    if kind is None:
        return 'role unknown: the name does not end with {}'.format('/'.join(TYPES))
    if model == 'npm' and kind in ('Main', 'MainGlass') and not oks:
        return 'options.oks is needed for NPM {}'.format(kind)
    if model == 'vpm' and kind not in ('Main', 'MainGlass', 'Ground', 'GroundGlass'):
        return 'VPM has no {} objects'.format(kind)
    names = role_names(address, oks, 1, None, model) if model == 'vpm' or oks else None
    if names is None:  # NPM Ground roles without an OKS number: same grammar, no number
        return {'address': address, 'oks': None, 'type': kind, 'name': 'SM_{}_{}'.format(address, kind)}
    oks_text = '{:03d}'.format(oks) if model == 'npm' and kind in ('Main', 'MainGlass') else None
    return {'address': address, 'oks': oks_text, 'type': kind, 'name': names[kind]['object']}


def _library_material(obj, slot):
    return 'M_' + obj['name'] + ('' if slot == 1 else '_{}'.format(slot))


def _library_stem(obj, role):
    suffix = NPM_MAP.get(role)
    return None if suffix is None else 'T_{}_{}'.format(obj['name'], suffix)


def _plan_material(plan, key, obj, model, material, files, folder=None):
    slots = _material_slots(material)
    library = bool(obj.get('library'))
    if library and material.get('subs') is not None:
        plan['failures'].append({'key': key, 'item': material['name'],
                                 'reason': 'library profile: one material per asset, Multi/Sub is not renamed'})
        return
    if len(slots) > MAX_SLOTS:
        plan['failures'].append({'key': key, 'item': material['name'],
                                 'reason': '{} used sub-materials > SlotNumber 7'.format(len(slots))})
        return
    if material.get('subs') is not None:
        multi = '_'.join(['M', obj['address']] + ([obj['oks']] if obj['oks'] else []) + [obj['type']])
        plan['materials'].append({'key': key, 'path': [], 'old': material['name'], 'new': multi, 'action': 'rename'})
    for slot, sub in slots:
        path = [] if material.get('subs') is None else [sub['id']]
        plan['materials'].append({'key': key, 'path': path, 'old': sub['name'],
                                  'new': _library_material(obj, slot) if library else material_name(obj, slot),
                                  'action': 'rename', 'slot': slot})
        by_stem = {}
        if sub.get('unsupported'):
            plan['failures'].append({'key': key, 'item': sub['name'],
                                     'reason': 'material class {} : its maps are not read; files not renamed'.format(
                                         sub.get('class'))})
        for mp in sub.get('maps') or ():
            role, src = mp['role'], mp['path']
            item = '{} {}'.format(sub['name'], role if role is not None else mp['key'])
            if role is None:  # V2: slot without a texture role (reflection is not `_m`)
                plan['failures'].append({'key': key, 'item': item,
                                         'reason': '{}: slot has no NPM/VPM texture role; map left as is'.format(
                                             mp['key'])})
                continue
            if role not in ROLES:
                plan['failures'].append({'key': key, 'item': item, 'reason': 'map slot role unknown: ' + str(role)})
                continue
            if library:
                stem = _library_stem(obj, role)
            else:
                stem = texture_stem(obj, model, role, slot, udim_of(src) if model == 'vpm' else None)
            if stem is None:
                plan['failures'].append({'key': key, 'item': item,
                                         'reason': '{} map has no {} texture mask; left as is'.format(role, model.upper())})
                continue
            if stem in by_stem and by_stem[stem] != src:
                plan['failures'].append({'key': key, 'item': item, 'reason': 'two different files map to ' + stem})
                continue
            by_stem[stem] = src
            dst = target_path(src, stem, folder) if src else None
            info_src = files.get(src) or {'exists': False, 'sha256': None}
            info_dst = files.get(dst) or {'exists': False, 'sha256': None}
            row = {'key': key, 'slot': slot, 'role': role, 'map': mp['key'], 'name': stem, 'source': src, 'target': dst,
                   'sub': path}
            if dst is not None and dst == src and info_src['exists']:
                row['action'] = 'rename map only (file already named)'
            elif info_dst['exists'] and info_src['exists'] and info_src['sha256'] != info_dst['sha256']:
                # V1: another file already holds the mask name: never overwritten, never linked
                row['action'] = 'keep: target exists with other content'
                row['same_content'] = False
                row['target_sha256'] = info_dst['sha256']
                plan['failures'].append({'key': key, 'item': item,
                                         'reason': '{} exists with other content (sha256 {}…): not overwritten and not '
                                                   'linked; the map stays on {}'.format(
                                                       dst, str(info_dst['sha256'])[:12], src)})
            elif info_dst['exists']:
                row['action'] = 'reuse existing file (not overwritten)'
                row['same_content'] = info_src['exists'] and info_src['sha256'] == info_dst['sha256']
                row['target_sha256'] = info_dst['sha256']
            elif info_src['exists']:
                row['action'] = 'copy'
                row['source_sha256'] = info_src['sha256']
            else:
                row['action'] = 'clear on copy (source missing)'
                plan['failures'].append({'key': key, 'item': item,
                                         'reason': 'source file missing: {}; the map is cleared on the copy, never '
                                                   'repointed to a file that does not exist'.format(src or '(empty path)')})
            plan['files'].append(row)


def check_names(plan, checks_core):
    """Every produced name against the 0.5.0 names check of its model: [(key, name, code, detail)].

    Address style findings (name_case, name_digits) are left to the names check: the address is never rewritten."""
    bad = []
    style = ('name_case', 'name_digits')

    def findings(name, role, model):
        if model != 'library':
            return [(c, d) for c, d in checks_core.name_findings(name, role, model) if c not in style]
        if role == 'SM':
            got = library_name(name)
            return [] if isinstance(got, dict) and got['name'] == name else [('name_library', str(got))]
        stem = name[:-4] if name.endswith('.png') else name
        ok = re.fullmatch(r'{}_[A-Za-z0-9_]+'.format(role), stem) and '__' not in stem
        return [] if ok else [('name_library', '{} name outside {}_<asset>: {}'.format(role, role, stem))]

    for o in plan['objects']:
        model = 'vpm' if o['kind'] == 'ucx' else o['model']
        for code, detail in findings(o['new'], 'SM', model):
            bad.append((o['key'], o['new'], code, detail))
    models = {o['key']: o.get('model') for o in plan['objects']}
    for m in plan['materials']:
        if m.get('action') == 'rename' and 'slot' in m:
            for code, detail in findings(m['new'], 'M', models[m['key']]):
                bad.append((m['key'], m['new'], code, detail))
    for f in plan['files']:
        for code, detail in findings(f['name'] + '.png', 'T', models[f['key']]):
            bad.append((f['key'], f['name'], code, detail))
    return bad
