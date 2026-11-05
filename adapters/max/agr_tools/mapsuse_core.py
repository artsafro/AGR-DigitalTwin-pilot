"""new-case: AGR Tools 0.9 (#979) maps usage report logic, stdlib only. Owned by branch D
(improve/issue-979-export-scene-light).

Pure logic for `scene_maps_usage` (scene.maps_usage); no pymxs. Read only: the report says which map files the
scene uses, which files in the maps folder(s) are extra and which used maps are missing. Nothing is deleted,
moved or relinked.

Sources compared (team zavod, T08; no code copied, #853): `audit_scene_maps.ms`
(SHA256 e9601693458995c2b7e2cb0bd8ca546175960a83ed969a6802b5273930c4a382), `zavod_lib_maps.ms` guessPaths
(SHA256 17cf0942739d0f83dc73169e3273e8c0b63f2a34790097957c4e165cffb08b03), `collect_scene_maps.ms` as the
negative example (SHA256 ce77809fe39f52ccf5fa34582f6547db589c4aeff656b4ab4b30897790c97290). Fixed defects
(regression tests in tests/max_tools/test_agr_tools_mapsuse.py):
* a hand walker of Multimaterial/materialList: maps of Blend, DoubleSided, Shell, a renderable spline, lights and
  the environment were «extra» (8 of 12 reported, 6 false). The glue enumerates every BitmapTexture class
  instance + the AssetManager + the shared scene.missing_maps enumerator (tex_max._scene_maps);
* full-path compare only: a file used through another folder (or after a relink) was «extra». Here the paths are
  normalised (case, separators, `..`) and same-name files are compared by content (SHA256);
* a missing map silently replaced by any file with the same base name: here a missing map stays missing and a
  same-name file is only named as a candidate;
* bulk `deleteFile` without backup: there is no delete at all.
Extra files go to `plan.ambiguous`: a person decides (the maps folder may be shared with another scene).
"""
import os
import re

TOOL = 'scene.maps_usage'
IMAGE_EXTS = ('.png', '.jpg', '.jpeg', '.tga', '.tif', '.tiff', '.bmp', '.exr', '.hdr', '.psd', '.dds', '.gif')
NOT_MAPS = ('.cgeo', '.vrmesh', '.abc', '.max', '.fbx')  # proxies and scenes are never «maps» (T08 zavod_lib_maps)
OPTION_KEYS = {'folders', 'recursive'}
_TILE = re.compile(r'<udim>|<uvtile>|<uv>', re.I)


def norm(path):
    """Comparable key of a path: absolute, normalised separators and `..`, case-folded (Windows)."""
    return os.path.normcase(os.path.normpath(os.path.abspath(str(path))))


def maps_options(options):
    opts = dict(options or {})
    extra = set(opts) - OPTION_KEYS
    if extra:
        raise ValueError('unknown scene.maps_usage options: ' + ', '.join(sorted(extra)))
    folders = opts.get('folders')
    if folders is not None:
        if not isinstance(folders, list) or not folders or not all(isinstance(f, str) and f.strip() for f in folders):
            raise ValueError('folders must be a non-empty list of folder paths')
        folders = [os.path.abspath(f) for f in folders]
    recursive = opts.get('recursive', True)
    if not isinstance(recursive, bool):
        raise ValueError('recursive must be true or false')
    return {'folders': folders, 'recursive': recursive}


def is_map_file(path):
    ext = os.path.splitext(str(path))[1].lower()
    return ext in IMAGE_EXTS and ext not in NOT_MAPS


def list_folder(folder, recursive=True, walk=os.walk, listdir=os.listdir, isfile=os.path.isfile):
    """Image files of one maps folder (sorted)."""
    out = []
    if recursive:
        for base, _dirs, files in walk(folder):
            out += [os.path.join(base, f) for f in files if is_map_file(f)]
    else:
        out = [os.path.join(folder, f) for f in listdir(folder) if is_map_file(f) and isfile(os.path.join(folder, f))]
    return sorted(out, key=str.lower)


def _tile_regex(path):
    """Regex over normalised paths for a tiled map (`<UDIM>` / `<UVTILE>` tokens), else None."""
    key = norm(path)
    if not _TILE.search(key):
        return None
    parts = _TILE.split(key)
    return re.compile('^' + r'[\w\-]+'.join(re.escape(p) for p in parts) + '$')


def merge_records(records):
    """{norm path: {path, owners, sources}} from the glue records [{path, owners, source}]."""
    merged = {}
    for rec in records:
        if not rec.get('path'):
            continue
        key = norm(rec['path'])
        row = merged.setdefault(key, {'path': rec['path'], 'owners': [], 'sources': set()})
        for o in rec.get('owners') or []:
            if o not in row['owners']:
                row['owners'].append(o)
        row['sources'].add(rec.get('source') or 'material')
    return merged


def usage(records, files, exists, digest):
    """Classify the scene maps and the folder files.

    records: [{path, owners:[{handle,node,material,map,hidden}], source}] from the enumerators (resolved paths).
    files: image files found in the maps folders. exists(path) -> bool; digest(path) -> sha256 hex (called
    only for same-name files). Returns {'used', 'missing', 'extra', 'copies'} lists of rows.
    """
    merged = merge_records(records)
    used, missing = [], []
    tiles = []
    for key in sorted(merged, key=str.lower):
        row = merged[key]
        rx = _tile_regex(row['path'])
        base = {'path': row['path'], 'owners': sorted(row['owners'], key=lambda o: (o.get('node') or '',
                                                                                   o.get('material') or '')),
                'sources': sorted(row['sources'])}
        if rx is not None:
            tiles.append((rx, base))
            continue
        (used if exists(row['path']) else missing).append(base)
    used_keys = {norm(r['path']): r for r in used}
    by_name = {}
    for r in used + missing:
        by_name.setdefault(os.path.basename(norm(r['path'])), []).append(r)
    extra, copies = [], []
    tile_hits = {id(base): [] for _, base in tiles}
    for f in files:
        key = norm(f)
        if key in used_keys:
            continue
        hit = next((base for rx, base in tiles if rx.match(key)), None)
        if hit is not None:
            tile_hits[id(hit)].append(f)
            continue
        same = by_name.get(os.path.basename(key), [])
        live = [r for r in same if norm(r['path']) in used_keys]
        lost = [r for r in same if norm(r['path']) not in used_keys]
        mine = digest(f) if live else None
        twin = next((r for r in live if digest(r['path']) == mine), None)
        if twin is not None:
            copies.append({'path': f, 'same_as': twin['path'], 'sha256': mine,
                           'note': 'та же карта по другому пути: сцена использует ' + twin['path']})
            continue
        notes = []
        if live:
            notes.append('одноимённая карта сцены с другим содержимым: ' + ', '.join(r['path'] for r in live))
        if lost:
            notes.append('кандидат для пропавшей карты (не подставляется): ' + ', '.join(r['path'] for r in lost))
        extra.append({'path': f, 'note': '; '.join(notes)})
    for rx, base in tiles:
        found = sorted(tile_hits[id(base)], key=str.lower)
        if found:
            used.append(dict(base, tiles=found))
        else:
            missing.append(dict(base, tiles=[], note='тайлы не найдены в папках карт'))
    for r in missing:
        cands = [f for f in files if os.path.basename(norm(f)) == os.path.basename(norm(r['path']))]
        r['candidates'] = sorted(cands, key=str.lower)
    return {'used': sorted(used, key=lambda r: r['path'].lower()),
            'missing': sorted(missing, key=lambda r: r['path'].lower()),
            'extra': extra, 'copies': copies}


def table(result):
    lines = ['status | path | owners / note', '-' * 32]
    for kind in ('used', 'missing', 'copies', 'extra'):
        for r in result[kind]:
            who = ', '.join(sorted({'{}/{}'.format(o.get('node') or '-', o.get('material') or '-')
                                    for o in r.get('owners', [])})) or r.get('note') or '-'
            lines.append('{} | {} | {}'.format(kind, r['path'], who))
    return lines


def maps_report(edit, result, scope, folders, state_hash, notes=()):
    """Read report: objects = scope nodes that own scene maps (finding `map_missing` per missing map);
    plan.used / missing / extra / copies; extra files and owner-less missing maps are `ambiguous`."""
    found = {h: {'name': name, 'findings': []} for h, name in scope}
    for r in result['missing']:
        for o in r['owners']:
            h = o.get('handle')
            if h in found:
                flags = ' [hidden]' if o.get('hidden') else ''
                f = edit.finding('map_missing', (), '{} ({}){}'.format(r['path'], o.get('material') or '-', flags))
                if f not in found[h]['findings']:
                    found[h]['findings'].append(f)
    objects = [edit.entry(h, v['name'], v['findings']) for h, v in sorted(found.items())]
    ambiguous = [{'item': r['path'], 'kind': 'extra', 'reason': 'файл в папке карт не используется сценой; '
                  'удаления нет, решение за человеком' + ('; ' + r['note'] if r['note'] else '')}
                 for r in result['extra']]
    ambiguous += [{'item': r['path'], 'kind': 'missing_unowned', 'reason': 'пропавшая карта без узла-владельца '
                   '(AssetManager / окружение / материал вне сцены)'}
                  for r in result['missing'] if not any(o.get('handle') for o in r['owners'])]
    summary = {k: len(result[k]) for k in ('used', 'missing', 'extra', 'copies')}
    plan = {'read_only': True, 'deletes': False, 'folders': list(folders), 'summary': summary,
            'used': result['used'], 'missing': result['missing'], 'extra': result['extra'],
            'copies': result['copies'], 'table': table(result), 'notes': list(notes)}
    return edit.report(TOOL, 'preview', objects, [], [], ambiguous, state_hash=state_hash, extra=plan)
