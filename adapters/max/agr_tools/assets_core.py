"""new-case: AGR Tools `assets` module core (#1024): library index, browser model, import plan, helper matching.

Pure stdlib, no pymxs (Max 2024 Python 3.10 and pytest). The Max side is assets_max.py, the window assets_ui.py.
Idea source (no code copied, #853): AlexYo Asset Importer 1.0.2, GeoAGR-private
`sources/team-scripts/alexyo/AlexYo_AssetImporter_v1.0.2.mzp`, SHA256 4c910813...1db28a9d.

Chain: source adapter -> index (JSON cache) -> browser (search, selection) -> import plan -> Max merge -> layout
-> journal/passport; and for placement: scene helpers -> match against the index (+ album spec) -> rows for
place.schedule (placement itself is not implemented here).

Source adapters:
* flora_max  - one library .max (all species) + `PreviewFlora/<base>_PREVIEW.png` + `TextureFlora/*.png`
  (Flora A101: FLORIO_221.max). Object names come from Max (getMAXFileObjectNames) and are passed in.
* maf_zip    - one zip per asset `Manufacturer_Object_Article.zip` (MAF A101), recursive, read through the zip
  central directory without extracting; optional sidecar `<name>.json` (schema 3) gives identity/units/bbox.
"""
import datetime
import difflib
import hashlib
import json
import os
import random
import re
import zipfile

INDEX_SCHEMA = 'agr.assets.index/1'
INDEX_NAME = 'assets_index.json'
VERSIONS = ('high', 'low')
LAYER_FMT = 'ASSET_{lib}_{ver}'
PROP_ID, PROP_VER, PROP_LIB, PROP_SHA = 'agr_asset_id', 'agr_asset_version', 'agr_asset_lib', 'agr_asset_sha256'

# Flora A101: <species slug>_t<type>_h<height cm>; rows of Text_/IMG_ helpers, CRP_ = third-party proxy.
FLORA_BASE = r'(?P<base>(?P<species>[a-z0-9]+(?:_[a-z0-9]+)*?)_t(?P<variant>\d+)_h(?P<height>\d+))'
FLORA_NAME = re.compile(r'^(?P<prefix>Text_|IMG_|CRP_)?' + FLORA_BASE +
                        r'(?:_(?P<ver>high|low|VIZ_PROXY|VIZ))?$', re.IGNORECASE)
MAX_DUP = re.compile(r'\d{3}$')  # Max auto-rename tail (Name001)


# ---- small helpers -----------------------------------------------------------------------------------------
def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()


def sha256_file(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(chunk), b''):
            h.update(block)
    return h.hexdigest()


def fold(text):
    """Search folding: lower case, ё -> е, separators -> space."""
    t = str(text or '').lower().replace('ё', 'е')
    return re.sub(r'[\s_\-.]+', ' ', t).strip()


def stat_of(path):
    st = os.stat(path)
    return {'size': st.st_size, 'mtime': round(st.st_mtime, 3)}


def write_json_atomic(path, data):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


# ---- names --------------------------------------------------------------------------------------------------
def parse_flora(name):
    """Flora object name -> dict(prefix, base, species, variant, height_cm, ver) or None."""
    m = FLORA_NAME.match(str(name))
    if not m:
        return None
    ver = m.group('ver')
    return {'prefix': (m.group('prefix') or '').rstrip('_') or None, 'base': m.group('base'),
            'species': m.group('species'), 'variant': int(m.group('variant')),
            'height_cm': int(m.group('height')), 'ver': ver.lower() if ver else None}


def parse_maf(name):
    """`Manufacturer_Object_Article[_high|_low]` (Q28) -> dict or None. Article may hold '-', '.'; extra '_'
    segments go to the object part."""
    base = re.sub(r'_(high|low)$', '', str(name), flags=re.IGNORECASE)
    parts = base.split('_')
    if len(parts) < 3 or not all(parts):
        return None
    return {'manufacturer': parts[0], 'title': '_'.join(parts[1:-1]), 'article': parts[-1], 'base': base}


def version_of(node_name):
    """'high' / 'low' / None from an object name, tolerant of the Max duplicate tail (_high001)."""
    m = re.search(r'_(high|low)(\d{3})?$', str(node_name), re.IGNORECASE)
    return m.group(1).lower() if m else None


# ---- records ------------------------------------------------------------------------------------------------
def make_record(lib, kind, base, **kw):
    rec = {'id': lib + ':' + base, 'lib': lib, 'kind': kind, 'name': base,
           'manufacturer': None, 'title': None, 'article': None, 'species': None, 'variant': None,
           'height_cm': None, 'versions': {}, 'preview': None, 'preview_match': None,
           'source': None, 'meta': None, 'warnings': []}
    rec.update(kw)
    return rec


def badge(rec):
    tags = [v[0].upper() for v in VERSIONS if v in rec['versions']]
    return '[' + ']['.join(tags) + ']' if tags else '[-]'


def search_text(rec):
    parts = [rec['name'], rec.get('manufacturer'), rec.get('title'), rec.get('article'), rec.get('species'),
             't{}'.format(rec['variant']) if rec.get('variant') is not None else None,
             'h{}'.format(rec['height_cm']) if rec.get('height_cm') is not None else None]
    meta = rec.get('meta') or {}
    parts += [meta.get('title'), meta.get('category'), rec.get('category')]
    return fold(' '.join(str(p) for p in parts if p))


# ---- Flora adapter (one .max + previews) ---------------------------------------------------------------------
def flora_layout(root):
    """Locate the parts of a Flora library folder: the .max (exactly one), PreviewFlora, TextureFlora."""
    maxes = sorted(f for f in os.listdir(root) if f.lower().endswith('.max'))
    if len(maxes) != 1:
        raise ValueError('expected exactly one .max in {}, found {}'.format(root, maxes))
    sub = {d.lower(): d for d in os.listdir(root) if os.path.isdir(os.path.join(root, d))}
    return {'max': maxes[0], 'previews': sub.get('previewflora'), 'textures': sub.get('textureflora'),
            'proxies': sub.get('proxyfloraviz'), 'viz_textures': sub.get('texturefloraviz')}


def _preview_names(root, previews_dir):
    if not previews_dir:
        return {}
    out = {}
    for f in os.listdir(os.path.join(root, previews_dir)):
        m = re.match(r'^(.+)_PREVIEW\.png$', f, re.IGNORECASE)
        if m:
            out[m.group(1)] = previews_dir + '/' + f
    return out


def flora_records(lib, object_names, previews, fuzzy_cutoff=0.85, generated=None):
    """Group library object names into species records. previews: {base: relative path}.

    Returns (records, report). A record needs a high or low mesh; Text_/IMG_ rows are helpers, CRP_ is a
    third-party proxy (recognised and reported, never imported). Preview match is exact by base, else a
    difflib candidate with the same _t/_h tail (flagged `fuzzy`), else none."""
    groups, foreign = {}, []
    for n in object_names:
        p = parse_flora(n)
        if p is None:
            foreign.append(str(n))
            continue
        g = groups.setdefault(p['base'], {'parsed': p, 'objects': {}, 'helpers': [], 'proxy': []})
        if p['prefix'] == 'CRP':
            g['proxy'].append(str(n))
        elif p['prefix']:
            g['helpers'].append(str(n))
        else:
            g['objects'].setdefault(p['ver'] or 'none', []).append(str(n))
    records, labels_only, proxies = [], [], []
    used_previews = set()
    for base in sorted(groups):
        g = groups[base]
        if g['proxy']:
            proxies.extend(g['proxy'])
        if not any(v in g['objects'] for v in VERSIONS):
            if not g['proxy']:
                labels_only.append(base)
            continue
        p = g['parsed']
        versions = {v: {'objects': sorted(g['objects'][v])} for v in VERSIONS if v in g['objects']}
        rec = make_record(lib, 'flora', base, species=p['species'], variant=p['variant'],
                          height_cm=p['height_cm'], title=p['species'].replace('_', ' '), versions=versions)
        extra = sorted(k for k in g['objects'] if k not in VERSIONS)
        if extra:
            rec['extra_versions'] = {k: sorted(g['objects'][k]) for k in extra}
        if base in previews:
            rec['preview'], rec['preview_match'] = previews[base], 'exact'
        records.append(rec)
    for r in records:
        if r['preview']:
            used_previews.add(r['name'])
    free = [b for b in previews if b not in used_previews]
    for r in records:
        if r['preview']:
            continue
        tail = '_t{}_h{}'.format(r['variant'], r['height_cm'])
        cands = [b for b in free if b.endswith(tail)]
        best = difflib.get_close_matches(r['name'], cands, n=2, cutoff=fuzzy_cutoff)
        if len(best) == 1 or (len(best) == 2 and difflib.SequenceMatcher(None, r['name'], best[0]).ratio() >
                              difflib.SequenceMatcher(None, r['name'], best[1]).ratio()):
            r['preview'], r['preview_match'] = previews[best[0]], 'fuzzy'
            r['warnings'].append('preview by similar name: ' + best[0])
            free.remove(best[0])
        elif r['name'] in (generated or {}):
            r['preview'], r['preview_match'] = generated[r['name']], 'generated'
            r['warnings'].append('preview rendered by AGR Tools (no A101 preview)')
        else:
            r['preview_match'] = 'none'
            r['warnings'].append('no preview')
    report = {'species': len(records), 'labels_without_model': labels_only,
              'third_party_proxies': sorted(proxies), 'foreign_objects': sorted(foreign),
              'previews_unused': sorted(free),
              'preview_match': {k: sum(1 for r in records if r['preview_match'] == k)
                                for k in ('exact', 'fuzzy', 'generated', 'none')}}
    return records, report


def scan_flora(root, object_names, lib='flora', old_index=None, hash_source=True, extra_preview_dirs=()):
    """Index a Flora library folder. object_names: names inside the .max (from Max, or the cached list).
    extra_preview_dirs: folders of generated <base>_PREVIEW.png (absolute paths), used only where the library
    has neither an exact nor a similar-name preview."""
    lay = flora_layout(root)
    max_path = os.path.join(root, lay['max'])
    st = stat_of(max_path)
    old_src = (old_index or {}).get('sources', {}).get(lay['max'])
    sha = None
    if old_src and old_src.get('size') == st['size'] and old_src.get('mtime') == st['mtime']:
        sha = old_src.get('sha256')
    if sha is None and hash_source:
        sha = sha256_file(max_path)
    generated = {}
    for d in extra_preview_dirs:
        for base, rel in _preview_names(os.path.dirname(d), os.path.basename(d)).items():
            generated.setdefault(base, os.path.normpath(os.path.join(os.path.dirname(d), rel)))
    records, report = flora_records(lib, object_names, _preview_names(root, lay['previews']), generated=generated)
    for r in records:
        r['source'] = {'path': lay['max'], 'sha256': sha}
    src = dict(st, sha256=sha, objects=sorted(str(n) for n in object_names))
    return new_index(lib, 'flora_max', root, records, {lay['max']: src}, report, layout=lay)


def flora_needs_names(root, old_index):
    """True when the cached object list cannot be reused (new or changed .max): the Max side must read names."""
    lay = flora_layout(root)
    old_src = (old_index or {}).get('sources', {}).get(lay['max'])
    st = stat_of(os.path.join(root, lay['max']))
    return not (old_src and old_src.get('size') == st['size'] and old_src.get('mtime') == st['mtime']
                and old_src.get('objects'))


# ---- MAF adapter (zip per asset) -----------------------------------------------------------------------------
def _zip_names(zf):
    out = []
    for info in zf.infolist():
        if info.is_dir():
            continue
        name = info.filename
        if not info.flag_bits & 0x800:  # not UTF-8 flagged: Windows zips use cp866
            try:
                name = name.encode('cp437').decode('cp866')
            except (UnicodeError, ValueError):
                pass
        out.append((info, name))
    return out


# MAF category from the A101 object title (CamelCase transliteration). Order matters: specific keys first.
# Vocabulary follows the album specification types (maf_spec_vedomost_3.xlsx); the sheet itself is inconsistent
# (a pergola and a carousel are typed «Качели» there), so the title decides and the sheet type is kept apart.
MAF_CATEGORIES = (
    ('pesochnyystolik', 'Игровое оборудование'), ('stoliks', 'Игровое оборудование'),
    ('pesochica', 'Песочница'), ('pesochnica', 'Песочница'),
    ('kreslo', 'Кресло'), ('stul', 'Кресло'),
    ('divan', 'Скамья'), ('skame', 'Скамья'), ('skamy', 'Скамья'),
    ('lezhak', 'Парковый лежак'), ('stol', 'Стол'), ('barnaya', 'Стол'),
    ('urna', 'Урна'), ('tbo', 'Контейнерная площадка'),
    ('naves', 'Навес'), ('pergola', 'Пергола'),
    ('kachalka', 'Качалка'), ('kacheligamak', 'Гамак'), ('gamak', 'Гамак'), ('kacheli', 'Качели'),
    ('karusel', 'Карусель'), ('gorka', 'Горка'),
    ('igrovoykompleks', 'Игровой комплекс'), ('detskayaploshadka', 'Игровой комплекс'), ('domik', 'Игровой комплекс'),
    ('sportivnoe', 'Спортивное оборудование'), ('oborydovanieworkout', 'Спортивное оборудование'),
    ('turnik', 'Спортивное оборудование'), ('brevn', 'Спортивное оборудование'),
    ('balans', 'Спортивное оборудование'), ('balancir', 'Спортивное оборудование'),
    ('polosyprepyatstviy', 'Спортивное оборудование'),
    ('igrovaya', 'Игровое оборудование'), ('igrovoyelement', 'Игровое оборудование'),
    ('ostrovok', 'Игровое оборудование'), ('vertushka', 'Игровое оборудование'), ('penek', 'Игровое оборудование'),
    ('piramida', 'Игровое оборудование'), ('raskopki', 'Игровое оборудование'), ('igrapeskom', 'Игровое оборудование'),
    ('veloparkovka', 'Велопарковка'), ('amfiteatr', 'Амфитеатр'), ('amphiteather', 'Амфитеатр'),
    ('parklet', 'Парклет'), ('inform', 'Информационный стенд'), ('pristvolnaya', 'Приствольная решётка'),
)


def maf_category(title):
    """Category of a MAF from its object title, or None (NoName… and unknown words are left to a human)."""
    t = re.sub(r'[^a-z]', '', str(title or '').lower())
    for key, cat in MAF_CATEGORIES:
        if t.startswith(key) or (len(key) >= 5 and key in t):
            return cat
    return None


def inspect_maf_zip(path, base):
    """Versions, preview member and sidecar of one MAF zip, central directory only (plus the small json)."""
    want = {'max': base + '.max', 'preview': base + '.png', 'json': base + '.json',
            'high_fbx': base + '_high.fbx', 'low_fbx': base + '_low.fbx'}
    want = {k: v.lower() for k, v in want.items()}
    found, members = {}, []
    with zipfile.ZipFile(path) as zf:
        for info, name in _zip_names(zf):
            b = name.replace('\\', '/').rsplit('/', 1)[-1]
            members.append({'name': name, 'size': info.file_size})
            for k, v in want.items():
                if b.lower() == v:
                    found[k] = info.filename
        meta = None
        if 'json' in found:
            try:
                meta = json.loads(zf.read(found['json']).decode('utf-8'))
            except (ValueError, UnicodeError):
                meta = {'error': 'unreadable sidecar json'}
    return found, members, meta


def scan_maf(root, cache_dir, lib='maf', old_index=None, hash_sources=False, progress=None):
    """Index a MAF folder (recursive). Unchanged zips (size+mtime) reuse their record; previews are extracted once
    into <cache>/previews/. Unreadable / partially synced zips go to `problems`, never stop the scan."""
    old = {r['source']['path']: r for r in (old_index or {}).get('assets', []) if r.get('source')}
    old_src = (old_index or {}).get('sources', {})
    zips = []
    for dirpath, _dirs, files in os.walk(root):
        for f in files:
            if f.lower().endswith('.zip'):
                zips.append(os.path.relpath(os.path.join(dirpath, f), root).replace('\\', '/'))
    zips.sort(key=str.lower)
    records, sources, problems = [], {}, []
    for i, rel in enumerate(zips):
        path = os.path.join(root, rel)
        base = os.path.splitext(os.path.basename(rel))[0]
        try:
            st = stat_of(path)
            prev = old_src.get(rel)
            if prev and prev.get('size') == st['size'] and prev.get('mtime') == st['mtime'] and rel in old:
                rec = old[rel]
                if rec.get('title') and 'category' not in rec:  # index written before categories
                    rec['category'] = maf_category(rec['title'])
                if not rec.get('preview') or os.path.isfile(os.path.join(cache_dir, rec['preview'])):
                    records.append(rec)
                    sources[rel] = prev
                    continue
            found, members, meta = inspect_maf_zip(path, base)
            p = parse_maf(base)
            rec = make_record(lib, 'maf', base, versions={}, meta=meta)
            if p:
                rec.update(manufacturer=p['manufacturer'], title=p['title'], article=p['article'],
                           category=maf_category(p['title']))
            else:
                rec['warnings'].append('name is not Manufacturer_Object_Article (Q28)')
            ident = (meta or {}).get('identity') or {}
            if p and ident and (ident.get('manufacturer'), ident.get('object_name'), ident.get('article')) != (
                    p['manufacturer'], p['title'], p['article']):
                rec['warnings'].append('sidecar identity differs from the file name')
            for v in VERSIONS:
                geo = ((meta or {}).get('geometry') or {}).get(v) or {}
                declared = ((meta or {}).get('versions') or {}).get(v)
                if (v + '_fbx') in found or declared:
                    rec['versions'][v] = {'objects': geo.get('object_names') or [base + '_' + v],
                                          'fbx': (v + '_fbx') in found, 'max': 'max' in found}
            if 'max' not in found:
                rec['warnings'].append('no .max in the archive (FBX only)')
            if 'preview' in found:
                rel_prev = 'previews/' + lib + '/' + base + '.png'
                dest = os.path.join(cache_dir, rel_prev)
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                with zipfile.ZipFile(path) as zf, open(dest + '.tmp', 'wb') as out:
                    out.write(zf.read(found['preview']))
                os.replace(dest + '.tmp', dest)
                rec['preview'], rec['preview_match'] = rel_prev, 'exact'
            else:
                rec['preview_match'] = 'none'
                rec['warnings'].append('no preview')
            sha = sha256_file(path) if hash_sources else None
            rec['source'] = {'path': rel, 'sha256': sha, 'members': len(members),
                             'unpacked_bytes': sum(m['size'] for m in members)}
            sources[rel] = dict(st, sha256=sha)
            records.append(rec)
        except (OSError, zipfile.BadZipFile, ValueError, KeyError) as exc:
            problems.append({'path': rel, 'error': '{}: {}'.format(type(exc).__name__, exc)})
        if progress:
            progress(i + 1, len(zips), rel)
    report = {'archives': len(zips), 'indexed': len(records), 'problems': problems,
              'with_sidecar': sum(1 for r in records if r.get('meta'))}
    return new_index(lib, 'maf_zip', root, records, sources, report)


def maf_member_filter(name, use_fbx, versions):
    """Which archive members an import needs. MAX route: the .max and every texture (not the FBX, the preview
    `<name>.png` or the sidecar). FBX route: only `<name>_<version>.fbx` of the chosen versions (media embedded)."""
    n = name.lower()
    fbx = {'{}_{}.fbx'.format(n, v) for v in versions}

    def keep(base):
        b = base.lower()
        if use_fbx:
            return b in fbx
        return not b.endswith('.fbx') and b not in (n + '.png', n + '.json')
    return keep


def extract_members(zip_path, dest, keep):
    """Extract members whose basename passes keep() into dest (flat: basenames only, no traversal). A file that
    already exists with the same size is reused; a different one is replaced through a temporary file.
    Returns {basename lower: path}."""
    os.makedirs(dest, exist_ok=True)
    out = {}
    with zipfile.ZipFile(zip_path) as zf:
        for info, name in _zip_names(zf):
            base = name.replace('\\', '/').rsplit('/', 1)[-1]
            if not base or base in ('.', '..') or not keep(base):
                continue
            target = os.path.join(dest, base)
            if not (os.path.isfile(target) and os.path.getsize(target) == info.file_size):
                with zf.open(info) as src, open(target + '.tmp', 'wb') as dst:
                    while True:
                        block = src.read(1 << 20)
                        if not block:
                            break
                        dst.write(block)
                os.replace(target + '.tmp', target)
            out[base.lower()] = target
    return out


# ---- index --------------------------------------------------------------------------------------------------
def new_index(lib, adapter, root, records, sources, report, **extra):
    idx = {'schema': INDEX_SCHEMA, 'lib': lib, 'adapter': adapter, 'root': root, 'scanned_at': now_iso(),
           'sources': sources, 'assets': sorted(records, key=lambda r: r['name'].lower()), 'report': report}
    idx.update(extra)
    ids = [r['id'] for r in idx['assets']]
    dup = sorted({i for i in ids if ids.count(i) > 1})
    if dup:
        idx['report']['duplicate_ids'] = dup
    return idx


def index_path(cache_dir, lib):
    return os.path.join(cache_dir, lib + '_' + INDEX_NAME)


def load_index(cache_dir, lib):
    path = index_path(cache_dir, lib)
    if not os.path.isfile(path):
        return None
    with open(path, encoding='utf-8') as f:
        idx = json.load(f)
    if idx.get('schema') != INDEX_SCHEMA:
        raise ValueError('unsupported index schema {!r} in {}'.format(idx.get('schema'), path))
    return idx


def save_index(cache_dir, idx):
    write_json_atomic(index_path(cache_dir, idx['lib']), idx)
    return index_path(cache_dir, idx['lib'])


def preview_abspath(idx, rec, cache_dir):
    if not rec.get('preview'):
        return None
    if os.path.isabs(rec['preview']):
        return rec['preview']
    if idx['adapter'] == 'flora_max':
        return os.path.join(idx['root'], rec['preview'])
    return os.path.join(cache_dir, rec['preview'])


# ---- browser model ------------------------------------------------------------------------------------------
def search(records, query):
    """All query tokens must occur in the folded name/manufacturer/title/article/species/t/h text."""
    toks = fold(query).split()
    if not toks:
        return list(records)
    return [r for r in records if all(t in search_text(r) for t in toks)]


class Selection(object):
    """Ordered selection of asset ids (click toggles, double click in the list removes, clear)."""

    def __init__(self, ids=()):
        self.ids = []
        for i in ids:
            self.add(i)

    def add(self, i):
        if i not in self.ids:
            self.ids.append(i)

    def toggle(self, i):
        if i in self.ids:
            self.ids.remove(i)
            return False
        self.ids.append(i)
        return True

    def remove(self, i):
        if i in self.ids:
            self.ids.remove(i)

    def clear(self):
        self.ids = []

    def keep_only(self, valid):
        valid = set(valid)
        self.ids = [i for i in self.ids if i in valid]


DEFAULT_SETTINGS = {'libraries': {}, 'cache_dir': '', 'project_dir': '', 'versions': ['high', 'low'],
                    'materials': 'reuse', 'textures': 'project', 'fbx_scale': 1.0, 'source': 'max',
                    'gap_m': 1.0, 'row_limit_m': 40.0, 'selection': [], 'preview_dirs': []}


def merge_settings(saved):
    s = json.loads(json.dumps(DEFAULT_SETTINGS))
    for k, v in (saved or {}).items():
        if k in s:
            s[k] = v
    if s['materials'] not in ('reuse', 'copy'):
        raise ValueError('materials must be reuse or copy')
    if s['textures'] not in ('project', 'library'):
        raise ValueError('textures must be project or library')
    if not set(s['versions']) <= set(VERSIONS) or not s['versions']:
        raise ValueError('versions must be a non-empty subset of high/low')
    if float(s['fbx_scale']) <= 0:
        raise ValueError('fbx_scale must be > 0')
    return s


# ---- import plan --------------------------------------------------------------------------------------------
def import_plan(index, ids, versions=VERSIONS, in_scene=()):
    """What to merge. in_scene: set of (asset id, version) already in the scene (user props) -> skipped, so a
    second import adds nothing (lesson of lab L08: re-run must not duplicate)."""
    by_id = {r['id']: r for r in index['assets']}
    in_scene = set(tuple(x) for x in in_scene)
    rows = []
    for i in ids:
        rec = by_id.get(i)
        if rec is None:
            rows.append({'id': i, 'status': 'not_in_index'})
            continue
        for v in versions:
            row = {'id': i, 'name': rec['name'], 'version': v, 'layer': LAYER_FMT.format(lib=rec['lib'], ver=v)}
            if v not in rec['versions']:
                row['status'] = 'no_version'
            elif (i, v) in in_scene:
                row['status'] = 'already_in_scene'
            else:
                row.update(status='merge', objects=list(rec['versions'][v]['objects']),
                           source=rec['source']['path'], sha256=rec['source'].get('sha256'),
                           props={PROP_ID: i, PROP_VER: v, PROP_LIB: rec['lib'],
                                  PROP_SHA: rec['source'].get('sha256') or ''})
            rows.append(row)
    return rows


def is_generic_material_name(name):
    """Max #renameMtlDups names a merged duplicate 'Material #25' (measured, job 20261106-021313-4741eca1)."""
    return bool(re.match(r'^Material #\d+$', str(name)))


def copy_material_name(node_name, taken):
    """Readable name for a material imported as a copy: <node>_copy, _copy2, ... not in `taken`."""
    base = str(node_name) + '_copy'
    name, i = base, 1
    while name in taken:
        i += 1
        name = '{}{}'.format(base, i)
    return name


def plan_hash(rows):
    return hashlib.sha256(json.dumps(rows, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()


def texture_plan(paths, search_dirs, project_dir=None):
    """Resolve bitmap paths by basename against search_dirs (first hit wins, case-insensitive).
    Returns {'map': {old: new}, 'copy': [(src, dst)], 'missing': [old]}. With project_dir the file is copied
    there (never over an existing different file of the same name: that is a conflict)."""
    listing = []
    for d in search_dirs:
        if d and os.path.isdir(d):
            listing.append((d, {f.lower(): f for f in os.listdir(d)}))
    out = {'map': {}, 'copy': [], 'missing': [], 'conflicts': []}
    for old in sorted(set(p for p in paths if p)):
        base = old.replace('\\', '/').rsplit('/', 1)[-1]
        hit = None
        for d, names in listing:
            if base.lower() in names:
                hit = os.path.join(d, names[base.lower()])
                break
        if hit is None:
            out['missing'].append(old)
            continue
        if project_dir:
            dst = os.path.join(project_dir, os.path.basename(hit))
            if os.path.isfile(dst) and os.path.getsize(dst) != os.path.getsize(hit):
                out['conflicts'].append(dst)
                continue
            if not os.path.isfile(dst):
                out['copy'].append((hit, dst))
            out['map'][old] = dst
        else:
            out['map'][old] = hit
    return out


def layout_rows(groups, gap_m=1.0, row_limit_m=40.0):
    """Lay out imported assets from the origin: one column per asset (High in front, Low behind it along +Y),
    columns along +X; a column that would pass row_limit_m starts a new band further along +Y.

    groups: [{'id', 'boxes': {version: (min xyz, max xyz, pivot xyz)}}] in metres (world, after merge).
    Returns {id: {version: (dx, dy, dz)}}: bbox min x/y to the slot, pivot z to 0."""
    moves = {}
    x = band_y = band_depth = 0.0
    for g in groups:
        boxes = g['boxes']
        order = [v for v in VERSIONS if v in boxes] + sorted(v for v in boxes if v not in VERSIONS)
        if not order:
            continue
        width = max(boxes[v][1][0] - boxes[v][0][0] for v in order)
        depth = sum(boxes[v][1][1] - boxes[v][0][1] for v in order) + gap_m * (len(order) - 1)
        if x > 0 and x + width > row_limit_m:
            x, band_y, band_depth = 0.0, band_y + band_depth + gap_m, 0.0
        y = band_y
        moves[g['id']] = {}
        for v in order:
            lo, hi, piv = boxes[v]
            moves[g['id']][v] = (x - lo[0], y - lo[1], -piv[2])
            y += (hi[1] - lo[1]) + gap_m
        x += width + gap_m
        band_depth = max(band_depth, depth)
    return moves


# ---- matching scene helpers with the library ("Сопоставить") -------------------------------------------------
def helper_key(name):
    """Helper / DWG block name -> candidate base: strips a _high/_low suffix (with its Max duplicate tail).
    A bare 3-digit tail is NOT stripped here: MAF articles may end in digits (Mesto_Kachalka_161100);
    match_names tries it only when the full name is not in the library."""
    return re.sub(r'_(high|low)(\d{3})?$', '', str(name).strip(), flags=re.IGNORECASE)


def _resolve_key(name, lib):
    k = helper_key(name)
    if k.lower() not in lib and MAX_DUP.search(k) and k[:-3].lower() in lib:
        return k[:-3]
    return k


def match_names(names, indexes, aliases=None):
    """Match helper names against one or more indexes.

    Exact base (case-insensitive) -> matched; else an alias table {helper key: library base}; else every
    library base that starts with the key + '_' (e.g. 'lipa' -> lipa_t1_h550): one -> matched (via prefix),
    several -> ambiguous, none -> missing. Returns {key: {count, status, ids, via}} plus totals."""
    lib = {}
    for idx in indexes:
        for r in idx['assets']:
            lib.setdefault(r['name'].lower(), []).append(r['id'])
    aliases = {k.lower(): v.lower() for k, v in (aliases or {}).items()}
    counts, resolved = {}, {}
    for n in names:
        k = resolved[str(n)] = _resolve_key(n, lib)
        counts[k] = counts.get(k, 0) + 1
    out = {}
    for k, c in sorted(counts.items(), key=lambda kv: kv[0].lower()):
        kl = k.lower()
        row = {'count': c, 'ids': [], 'via': None}
        if kl in lib:
            row.update(ids=lib[kl], via='exact')
        elif kl in aliases and aliases[kl] in lib:
            row.update(ids=lib[aliases[kl]], via='alias')
        else:
            pref = sorted(i for b, ids in lib.items() if b.startswith(kl + '_') for i in ids)
            row.update(ids=pref, via='prefix' if pref else None)
        row['status'] = 'matched' if len(row['ids']) == 1 else ('ambiguous' if row['ids'] else 'missing')
        out[k] = row
    totals = {s: sum(r['count'] for r in out.values() if r['status'] == s)
              for s in ('matched', 'ambiguous', 'missing')}
    return {'names': out, 'resolved': resolved, 'totals': totals,
            'green': totals['ambiguous'] == 0 and totals['missing'] == 0}


def reconcile_spec(spec_rows, match, indexes):
    """Album specification [{'name', 'qty'}] vs matched helpers: ok / short / excess / not_in_library /
    no_helpers. Missing library objects become `add_to_library` tasks."""
    rows, tasks = [], []
    names = match['names']
    for s in spec_rows:
        k = helper_key(s['name'])
        m = names.get(k)
        if m is None:  # declared but no helper: still look the name up in the library
            m = dict(match_names([k], indexes)['names'][k], count=0)
        qty = int(s.get('qty') or 0)
        if not m['ids']:
            status = 'not_in_library'
            tasks.append({'task': 'add_to_library', 'name': k, 'qty': qty})
        elif m['count'] == 0:
            status = 'no_helpers'
        elif m['count'] < qty:
            status = 'short'
        elif m['count'] > qty:
            status = 'excess'
        else:
            status = 'ok'
        rows.append({'name': k, 'qty': qty, 'helpers': m['count'], 'library': m['ids'], 'status': status})
    listed = {helper_key(s['name']) for s in spec_rows}
    extra = sorted(k for k in names if k not in listed)
    green = all(r['status'] == 'ok' for r in rows) and not extra and match['green']
    return {'rows': rows, 'helpers_not_in_spec': extra, 'tasks': tasks, 'green': green}


def placement_rows(helpers, match, kind_of, seed=None):
    """Interface to place.schedule (place_core.schedule_plan rows), NOT the placement itself.
    helpers: [{'name', 'x', 'y', 'rotation_deg'}] (metres, from helper pivots). MAF keeps the helper rotation;
    Flora rotation 0, or random about Z when a seed is given. Only matched names produce rows."""
    rnd = random.Random(seed) if seed is not None else None
    rows = []
    for i, h in enumerate(helpers, 1):
        m = match['names'].get(match['resolved'].get(str(h['name']), helper_key(h['name'])))
        if not m or m['status'] != 'matched':
            continue
        asset_id = m['ids'][0]
        if kind_of(asset_id) == 'maf':
            rot = float(h.get('rotation_deg') or 0.0)
        else:
            rot = round(rnd.uniform(0.0, 360.0), 3) if rnd else 0.0
        rows.append({'id': 'H{:04d}'.format(i), 'model': asset_id.split(':', 1)[1], 'asset_id': asset_id,
                     'x': float(h['x']), 'y': float(h['y']), 'rotation_deg': rot})
    return rows


# ---- journal and passport (contract K1, #1024) ---------------------------------------------------------------
def journal_path(scene_path, localappdata):
    """%LOCALAPPDATA%/AGRTools/journal/<sha1(scene)>.jsonl; sha1 of the normalised scene path ('untitled' for an
    unsaved scene). Branch 0 owns the shared writer; this is the same line format until it lands."""
    key = os.path.normcase(os.path.abspath(scene_path)) if scene_path else 'untitled'
    return os.path.join(localappdata, 'AGRTools', 'journal',
                        hashlib.sha1(key.encode('utf-8')).hexdigest() + '.jsonl')


def journal_line(tool, mode, status, counts, preview_sha=None, duration_s=None, actor='panel', **extra):
    line = {'ts': now_iso(), 'tool': tool, 'mode': mode, 'status': status, 'counts': counts,
            'preview_sha': preview_sha, 'duration': None if duration_s is None else round(duration_s, 3),
            'actor': actor}
    line.update(extra)
    return line


def append_journal(path, line):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'a', encoding='utf-8') as f:
        f.write(json.dumps(line, ensure_ascii=False) + '\n')


def passport_patch(passport, record):
    """Append an import record under passport['assets']['imports'] (new dict; the input is not changed)."""
    p = json.loads(json.dumps(passport))
    p.setdefault('assets', {}).setdefault('imports', []).append(record)
    return p
