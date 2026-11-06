"""new-case: AGR Tools 1.0 (#1024) material table (K3) logic, stdlib only. Stub of branch 0; owned by branch L (improve/issue-1024-materials).

Pure logic for `mat_table` (mat.table); no pymxs. Uses edit_core.py for reports and preview hashes; roles come from
contract_core.py (the glue reads them through host_max.MaxHost); the core never takes a host object.

* Library: `library/materials/materials.json` (pointer with sha256) -> `materials_vNNN.json` (K3, K5: git copy,
  maps on the Drive). `load_library` checks the pointer hash, the schema, unique ids/keys and that every RAL code is
  in `tools/materials/ral_classic.json` (one source of screen colours).
* Mid-poly carries LIBRARY ids on faces. `table_plan` checks per object: id in the library, no id >= 1001 on working
  geometry, glass ids only on `glass` objects (and nothing else on them).
* `renumber_dense`: the ids used by ONE mesh -> UDIM 1001.. without gaps, ascending library id. UDIM numbering is per
  mesh (owner answer V9 06.11.2026): the OKS body starts at 1001 and the windows/glass mesh starts at 1001 too.
* The project table rows follow `schemas/ProjectPassport.schema.json` `materials[]` (library_id, delivery_id, mesh,
  udim, npm_region).

Defect of the source this replaces (GeoAGR Multimat HP `btn_multimat` GeoAGR.ms:42706, #1024 «редакция 1» row 22,
`tex.multimat`): ID = UDIM - 1000 keeps every gap of the UDIM set (1001, 1002, 1005 -> IDs 1, 2, 5); here the UDIMs are
dense by construction and the Multi/Sub is built from the library, not from file names.
"""
import hashlib
import json
import os
import re

SCHEMA = 1
LIB_ID_MAX = 1000
UDIM_START = 1001
UDIM_MAX_PER_MESH = 100          # VPM: Main is one slot of up to 100 UDIM (docs/domain/materials.md:14-17)
CLASSES = ('paint', 'panel', 'tile', 'brick', 'paving', 'ground', 'mineral', 'roof', 'metal', 'wood', 'plastic',
           'glass', 'interior')
STATUSES = ('proposed', 'approved', 'conflict', 'quarantine')
RECIPES = ('solid', 'metric_pattern', 'greyscale_mask')
# grey base maps of tiles_core.BASE_MAPS (the three of #1024 K3 + the set of the materials audit, owner answer V12)
BASE_MAPS = ('facade_600x1200', 'ground_100x300', 'crumb_1x1', 'tile_600x600', 'tile_300x300', 'slab_900x300',
             'brick_250x65', 'panel_v1200', 'panel_v600')
RECORD_KEYS = {'library_id', 'key', 'name_ru', 'class', 'ral', 'rgb_srgb', 'rgb_note', 'roughness', 'metallic',
               'emissive', 'recipe', 'base_map', 'status', 'source', 'maf_v005_id'}
OPTIONAL_KEYS = {'opacity', 'note', 'questions'}
BYTE_FIELDS = ('roughness', 'metallic', 'emissive')
_KEY = re.compile(r'^[a-z][a-z0-9_]{1,63}$')
_VERSION = re.compile(r'^v\d{3}$')
_RAL = re.compile(r'^\d{4}$')
CODES = {
    'id_not_in_library': 'material ID of a face is not a library id',
    'udim_id_on_geometry': 'material ID >= 1001 on working geometry (UDIM numbers belong to vpm.build copies)',
    'glass_not_on_glass': 'glass library id on an object whose role is not glass',
    'non_glass_on_glass': 'non-glass library id on an object with role glass',
    'id_quarantine': 'library record in quarantine is not offered',
    'too_many_ids': 'more than 100 library ids on one mesh (one Main slot holds at most 100 UDIM)',
}


# ---- library ---------------------------------------------------------------------------------------------------
def _unique(pairs):
    out = {}
    for k, v in pairs:
        if k in out:
            raise ValueError('duplicate key: ' + repr(k))
        out[k] = v
    return out


def _reject(value):
    raise ValueError('non-finite number: ' + value)


def parse(text):
    """Strict JSON: duplicate keys and NaN/Infinity are errors."""
    return json.loads(text, object_pairs_hook=_unique, parse_constant=_reject)


def _read_text(path):
    with open(path, 'rb') as f:
        data = f.read()
    return data.replace(b'\r\n', b'\n')  # git checkouts may carry CRLF; the hash is over LF text


def _is_byte(v):
    return type(v) is int and 0 <= v <= 255


def validate_library(doc, ral=None):
    """Schema of materials_vNNN.json. `ral`: {code: '#RRGGBB'} of ral_classic.json (None: RAL not cross-checked).
    Returns the list of records; any defect is a ValueError naming the record."""
    if not isinstance(doc, dict) or doc.get('schema') != SCHEMA:
        raise ValueError('library: schema 1 expected')
    if not isinstance(doc.get('version'), str) or not _VERSION.match(doc['version']):
        raise ValueError('library: version vNNN expected')
    recs = doc.get('materials')
    if not isinstance(recs, list) or not 1 <= len(recs) <= LIB_ID_MAX:
        raise ValueError('library: materials must be a non-empty list')
    ids, keys = set(), set()
    for r in recs:
        at = 'library record {!r}'.format(r.get('library_id') if isinstance(r, dict) else r)
        if not isinstance(r, dict) or not RECORD_KEYS <= set(r) or set(r) - RECORD_KEYS - OPTIONAL_KEYS:
            raise ValueError(at + ': keys {} (+ optional {})'.format(sorted(RECORD_KEYS), sorted(OPTIONAL_KEYS)))
        lid = r['library_id']
        if isinstance(lid, bool) or not isinstance(lid, int) or not 1 <= lid <= LIB_ID_MAX:
            raise ValueError(at + ': library_id must be an integer 1..1000')
        if lid in ids:
            raise ValueError(at + ': duplicate library_id')
        ids.add(lid)
        if not isinstance(r['key'], str) or not _KEY.match(r['key']) or r['key'] in keys:
            raise ValueError(at + ': key must be unique snake_case')
        keys.add(r['key'])
        if not isinstance(r['name_ru'], str) or not r['name_ru'].strip():
            raise ValueError(at + ': name_ru')
        if r['class'] not in CLASSES:
            raise ValueError(at + ': class must be one of {}'.format(CLASSES))
        if r['ral'] is not None:
            if not isinstance(r['ral'], str) or not _RAL.match(r['ral']):
                raise ValueError(at + ': ral must be a 4-digit RAL Classic code or null')
            if ral is not None and r['ral'] not in ral:
                raise ValueError(at + ': RAL {} is not in ral_classic.json'.format(r['ral']))
        rgb = r['rgb_srgb']
        if not isinstance(rgb, list) or len(rgb) != 3 or not all(_is_byte(c) for c in rgb):
            raise ValueError(at + ': rgb_srgb must be [r, g, b] bytes')
        if ral is not None and r['ral'] is not None and rgb != hex_rgb(ral[r['ral']]):
            raise ValueError(at + ': rgb_srgb differs from ral_classic.json {}'.format(r['ral']))
        for k in BYTE_FIELDS:
            if not _is_byte(r[k]):
                raise ValueError(at + ': {} must be a byte 0..255 (MaterialRegistry)'.format(k))
        recipe = r['recipe']
        if not isinstance(recipe, dict) or recipe.get('kind') not in RECIPES:
            raise ValueError(at + ': recipe.kind must be one of {}'.format(RECIPES))
        if recipe['kind'] == 'greyscale_mask':
            if recipe.get('base_map') not in BASE_MAPS or r['base_map'] != recipe['base_map']:
                raise ValueError(at + ': greyscale_mask needs base_map in {} (same as the record)'.format(BASE_MAPS))
        elif r['base_map'] is not None:
            raise ValueError(at + ': base_map only with recipe greyscale_mask')
        if r['status'] not in STATUSES:
            raise ValueError(at + ': status must be one of {}'.format(STATUSES))
        if not isinstance(r['source'], dict):
            raise ValueError(at + ': source must be an object')
        if r['maf_v005_id'] is not None and (type(r['maf_v005_id']) is not int or r['maf_v005_id'] < 1):
            raise ValueError(at + ': maf_v005_id must be a positive integer or null')
        if r['class'] == 'glass':
            op = r.get('opacity')
            if isinstance(op, bool) or not isinstance(op, (int, float)) or not 0 < op < 1:
                raise ValueError(at + ': glass needs opacity 0..1')
    return recs


def hex_rgb(text):
    h = str(text).lstrip('#')
    if not re.match(r'^[0-9A-Fa-f]{6}$', h):
        raise ValueError('colour #RRGGBB expected: ' + repr(text))
    return [int(h[i:i + 2], 16) for i in (0, 2, 4)]


def ral_table(path):
    """{code: '#RRGGBB'} of tools/materials/ral_classic.json."""
    doc = parse(_read_text(path).decode('utf-8'))
    colors = doc.get('colors') if isinstance(doc, dict) else None
    if not isinstance(colors, dict) or not colors:
        raise ValueError('ral_classic.json without colors')
    return colors


def _ral_beside(lib_dir):
    """ral_classic.json of the same checkout: <repo>/library/materials -> <repo>/tools/materials."""
    p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(lib_dir))), 'tools', 'materials',
                     'ral_classic.json')
    return p if os.path.isfile(p) else None


def load_library(path):
    """library/materials/materials.json pointer (sha256) -> materials_vNNN.json, validated (K3, K5: read from a copy).

    Returns {'version': str, 'sha256': str, 'materials': [record...], 'by_id': {library_id: record}};
    a record has library_id, key, name_ru, class, ral, rgb_srgb, roughness, metallic, emissive, recipe,
    base_map, status, source. A direct materials_vNNN.json path is read without a pointer (sha256 of its text)."""
    path = os.path.abspath(os.fspath(path))
    folder = os.path.dirname(path)
    text = _read_text(path)
    doc = parse(text.decode('utf-8'))
    pointer = None
    if isinstance(doc, dict) and 'current' in doc:
        pointer = path
        if doc.get('schema') != SCHEMA or not isinstance(doc.get('current'), str) or not isinstance(
                doc.get('sha256'), str):
            raise ValueError('materials.json pointer: {schema, current, version, sha256} expected')
        name = doc['current']
        if os.path.basename(name) != name or not re.match(r'^materials_v\d{3}\.json$', name):
            raise ValueError('materials.json pointer: current must be materials_vNNN.json beside it')
        target = os.path.join(folder, name)
        text = _read_text(target)
        sha = hashlib.sha256(text).hexdigest()
        if sha != doc['sha256']:
            raise ValueError('library {} sha256 {} differs from the pointer {}'.format(name, sha, doc['sha256']))
        lib = parse(text.decode('utf-8'))
        if doc.get('version') != lib.get('version'):
            raise ValueError('library version differs from the pointer')
        path = target
    else:
        lib = doc
        sha = hashlib.sha256(text).hexdigest()
    ral_path = _ral_beside(folder)  # signature fixed by branch 0: (path) only
    ral = ral_table(ral_path) if ral_path else None
    recs = validate_library(lib, ral)
    return {'version': lib['version'], 'sha256': sha, 'materials': recs,
            'by_id': {r['library_id']: r for r in recs}, 'path': path, 'pointer': pointer,
            'ral_checked': ral is not None}


# ---- UDIM renumbering ------------------------------------------------------------------------------------------
def renumber_dense(used_ids, start=1001):
    """Library ids used by ONE mesh -> UDIM tiles start.. without gaps, ascending library id (K3).

    UDIM numbering is per mesh (owner answer V9 06.11.2026): the OKS body starts at 1001 and the windows/glass
    mesh starts at 1001 too. Returns {library_id: udim}; an id <= 0 or >= 1001 is an error."""
    if isinstance(start, bool) or not isinstance(start, int) or not UDIM_START <= start <= 1999:
        raise ValueError('start must be a UDIM 1001..1999: {!r}'.format(start))
    ids = set()
    for i in used_ids:
        if isinstance(i, bool) or not isinstance(i, int):
            raise ValueError('library id must be an integer: {!r}'.format(i))
        if i <= 0 or i >= UDIM_START:
            raise ValueError('library id {} is not 1..1000 (UDIM numbers are not library ids)'.format(i))
        ids.add(i)
    ids = sorted(ids)
    if not ids:
        raise ValueError('renumber_dense: no library ids')
    if len(ids) > UDIM_MAX_PER_MESH or start + len(ids) - 1 > 1999:
        raise ValueError('renumber_dense: {} ids do not fit one UDIM slot'.format(len(ids)))
    return {lid: start + k for k, lid in enumerate(ids)}


# ---- mat.table plan --------------------------------------------------------------------------------------------
def object_findings(edit, item, library):
    """Findings of one object {'role', 'ids': {id: faces}} against the library (K3 checks)."""
    by_id = library['by_id']
    ids = sorted(int(i) for i in item['ids'])
    role = item.get('role')
    out = []
    udim = [i for i in ids if i >= UDIM_START]
    if udim:
        out.append(edit.finding('udim_id_on_geometry', udim, 'IDs {} >= 1001 on working geometry'.format(udim)))
    unknown = [i for i in ids if i < UDIM_START and i not in by_id]
    if unknown:
        out.append(edit.finding('id_not_in_library', unknown,
                                'IDs {} are not in library {}'.format(unknown, library['version'])))
    known = [i for i in ids if i in by_id]
    quarantine = [i for i in known if by_id[i]['status'] == 'quarantine']
    if quarantine:
        out.append(edit.finding('id_quarantine', quarantine, 'library records in quarantine'))
    glass = [i for i in known if by_id[i]['class'] == 'glass']
    if role == 'glass':
        other = [i for i in known if by_id[i]['class'] != 'glass']
        if other:
            out.append(edit.finding('non_glass_on_glass', other, 'role glass carries non-glass ids {}'.format(other)))
    elif glass:
        out.append(edit.finding('glass_not_on_glass', glass,
                                'glass ids {} on role {!r}: glass is a separate object (role glass)'.format(glass, role)))
    if len([i for i in known]) > UDIM_MAX_PER_MESH:
        out.append(edit.finding('too_many_ids', [], '{} ids on one mesh'.format(len(known))))
    return out


def table_plan(edit, items, library):
    """items: [{'handle', 'name', 'role', 'ids': {library_id: faces}}] -> (entries, table, multisub, skipped).

    table: passport `materials[]` rows of the objects without findings, UDIM dense per mesh from 1001 (V9);
    multisub: library records of every id used by those objects (one Multi/Sub by the library)."""
    if not items:
        raise ValueError('mat.table: empty input (select the mid-poly objects)')
    entries, table, used, skipped = [], [], set(), []
    for it in items:
        if not it['ids']:
            skipped.append(edit.skipped(it['name'], 'no faces / no material IDs'))
            continue
        found = object_findings(edit, it, library)
        entries.append(edit.entry(it['handle'], it['name'], found))
        if found:
            continue
        udims = renumber_dense(it['ids'])
        for lid, udim in sorted(udims.items()):
            table.append({'library_id': lid, 'delivery_id': udim - 1000, 'mesh': it['name'], 'udim': udim,
                          'npm_region': None})
        used |= set(udims)
    multisub = [sub_spec(library['by_id'][i]) for i in sorted(used)]
    return entries, table, multisub, skipped


def sub_spec(rec):
    """Physical sub-material of one library record (Standard/Physical only: docs/domain/materials.md:5-6)."""
    return {'id': rec['library_id'], 'name': 'L{:03d}_{}'.format(rec['library_id'], rec['key']),
            'class': rec['class'], 'rgb': list(rec['rgb_srgb']), 'roughness': rec['roughness'] / 255.0,
            'metallic': rec['metallic'] / 255.0, 'emissive': rec['emissive'] / 255.0,
            'opacity': float(rec.get('opacity', 1.0))}


def multisub_name(library):
    return 'AGR_Library_{}'.format(library['version'])


def table_doc(library, table, passport):
    """Sidecar of the passport (jobs/<ID>/materials_table*.json): passport `materials[]` rows + library pin."""
    return {'schema': 1, 'kind': 'agr.materials_table', 'library': {'version': library['version'],
                                                                     'sha256': library['sha256']},
            'passport': passport, 'udim_rule': 'per mesh from 1001, ascending library id (V9 06.11.2026)',
            'materials': table}


def udim_tables(table):
    """{mesh: {library_id: udim}} for vpmmaps_core.build_maps (branch N) and the user prop agr_udim_table."""
    out = {}
    for row in table:
        out.setdefault(row['mesh'], {})[row['library_id']] = row['udim']
    return out


def report(edit, mode, entries, table, multisub, skipped, library, state_hash=None, done=(), extra=None):
    plan = {'library': {'version': library['version'], 'sha256': library['sha256'],
                        'ral_checked': library['ral_checked']},
            'table': table, 'multisub': {'name': multisub_name(library), 'ids': [m['id'] for m in multisub]}}
    plan.update(extra or {})
    if not done:
        done = sorted({row['mesh'] for row in table})
    return edit.report('mat.table', mode, objects=entries, done=list(done), skipped_=skipped,
                       state_hash=state_hash, extra=plan)
