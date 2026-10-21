"""Build the v004 MAF material ID list from the atlases the library MAFs use (issue #524).

Pattern: verify actual artifacts, not exporter return codes (docs/domain/patterns/INDEX.md).
new-case: material ID list derived from atlas cells + MAF specification rows (#524, first deliverable).

Inputs (all read-only):
  --materials   library/maf/fbx_materials.json   (Blender readback of the library FBX: material -> images)
  --uv-dump     <uv_dump.json>                   (tools/library/maf_uv_dump.py: per-material UV faces)
  --max-maps    <max_maps.json>                  (tools/library/maf_max_maps_job.py: scene bitmap files)
  --maps-dir    <dir> (repeatable)               (where the referenced images are looked up, by file name)
  --extra-atlas <png> (repeatable)               (Artem's concept atlases; no library MAF binds them)
  --schedule    jobs/VATUTINO-SITE/maf/site-schedule.json (MAF specification rows, material column)
  --seed        library/maf/material_ids_v004_seed.json   (the proposed ID list: id, key, kind, target)
  --ral         tools/materials/ral_classic.json
Outputs: --out-json, --out-md (small text, committed) and --evidence-dir (PNG contact sheet + atlas
overlays, never committed; rule 57). No output may resolve to an input; on any input error nothing
is written and the exit code is 2.

Every input element ends in the output or in a reported list with its reason: texture refs ->
found / missing / empty-bitmap; library material names -> id / excluded / unmapped; atlas cells
-> id / unmapped; specification rows -> ids / gap. Status stays ``proposed``.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import ntpath
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from maf_atlas_cells import segment  # noqa: E402

KIND_CELLS = {  # which cell kinds an id kind may take
    'paint': {'solid'}, 'plastic': {'solid', 'patterned'}, 'rubber': {'solid'},
    'translucent': {'solid'}, 'metal': {'solid', 'patterned'}, 'wood': {'patterned'},
    'mineral': {'patterned'}, 'opacity': {'patterned'}, 'sheet': {'patterned', 'solid'},
}
MATCH_TOL = {'solid': 18.0, 'patterned': 12.0}  # mean |dRGB| to the id target
MIN_CELL_SHARE = 1.0 / 1024  # cells below this share of the atlas are fragments
JUNK_RE = re.compile(r'^(Material(\.\d+)?|Material #\d+(\.\d+)?|\d\d - Default(\.\d+)?|Untitled_Diffuse.*'
                     r'|Diffuse|Me|Mst_\d+|MAF|Light|lab|Dots Stroke)$', re.I)
SLOT_RE = re.compile(r'(Slot #\d+)$')
NUMERIC_RE = re.compile(r'^\d+$')
GROUND_RE = re.compile(r'(^M_|^T_|^)(\d\d_\d\d_\d+_\d+.*|[A-Z][A-Za-z_]+_(ZU|Vl|Kv)_.*)_Ground(El)?(_|$)')
IMG_GROUND_RE = re.compile(r'_Ground_(Diffuse|d|ERM|Normal|m|n|r)_')  # GroundEl sets are MAF atlases


OPACITY_RE = re.compile(r'(_O|Opacity(_LOW)?)\.png$', re.I)


class InputError(ValueError):
    pass


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def _load(path: str) -> dict:
    if not os.path.isfile(path):
        raise InputError(f'input not found: {path}')
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def _rgb(hexc: str) -> tuple[int, int, int]:
    if not isinstance(hexc, str) or not re.fullmatch(r'#[0-9A-Fa-f]{6}', hexc):
        raise InputError(f'bad colour {hexc!r}')
    return tuple(int(hexc[i:i + 2], 16) for i in (1, 3, 5))


def _dist(a: str, b: str) -> float:
    return sum(abs(x - y) for x, y in zip(_rgb(a), _rgb(b))) / 3.0


def _maf(fbx: str) -> str:
    m = re.match(r'(MAF_\d+)', fbx)
    if not m:
        raise InputError(f'FBX name without MAF id: {fbx}')
    return m.group(1)


def load_seed(seed: dict, ral: dict) -> list[dict]:
    ids = seed.get('ids')
    if not isinstance(ids, list) or not ids:
        raise InputError('seed has no ids')
    seen_id, seen_key, out = set(), set(), []
    for e in ids:
        i, key, kind = e.get('id'), e.get('key'), e.get('kind')
        if not isinstance(i, int) or i <= 0 or i in seen_id:
            raise InputError(f'seed id must be a unique positive int: {i!r}')
        if not key or key in seen_key:
            raise InputError(f'seed key missing or duplicated: {key!r}')
        if kind not in KIND_CELLS:
            raise InputError(f'seed id {i}: unknown kind {kind!r}')
        target = e.get('hex')
        if e.get('ral'):
            target = ral.get(str(e['ral'])) or target
            if not target:
                raise InputError(f'seed id {i}: RAL {e["ral"]} not in the RAL table and no hex given')
        targets = [target] + list(e.get('also', []))
        for t in targets:
            _rgb(t)
        cells = set(e.get('cells') or KIND_CELLS[kind])
        if not cells <= {'solid', 'patterned'}:
            raise InputError(f'seed id {i}: bad cells {sorted(cells)}')
        seen_id.add(i)
        seen_key.add(key)
        out.append(dict(e, target=target.upper(), targets=[t.upper() for t in targets], cell_kinds=sorted(cells)))
    return out


def texture_refs(materials: dict) -> tuple[dict, dict]:
    """basename -> {mafs, materials}; plus empty-path refs {material: mafs}."""
    refs = collections.defaultdict(lambda: {'mafs': set(), 'materials': set(), 'raw_path': None})
    empty = collections.defaultdict(set)
    for fi in materials['files']:
        maf = _maf(fi['fbx'])
        for mt in fi['materials']:
            for t in mt.get('textures', []):
                b = ntpath.basename((t.get('filepath') or '').rstrip('\\/'))
                if not b or b == '..':
                    empty[mt['name']].add(maf)
                    continue
                r = refs[b]
                r['mafs'].add(maf)
                r['materials'].add(mt['name'])
                r['raw_path'] = r['raw_path'] or t['filepath']
    return refs, empty


def find_images(names, maps_dirs) -> dict:
    """name -> list of absolute paths (every maps dir, top level only, exact file name)."""
    hits = collections.defaultdict(list)
    for d in maps_dirs:
        if not os.path.isdir(d):
            raise InputError(f'maps dir not found: {d}')
        present = set(os.listdir(d))
        for n in names:
            if n in present:
                hits[n].append(os.path.join(d, n).replace('\\', '/'))
    return hits


def classify_material(name: str) -> tuple[str, str]:
    """('junk'|'ground'|'marker'|'meaningful', reason)."""
    base = SLOT_RE.sub('', name).strip()
    if NUMERIC_RE.match(name):
        return 'marker', '3ds Max multi-sub slot named by a bare number (MatID marker colour), no material meaning'
    if GROUND_RE.search(name) or name.startswith('ID_') and re.match(r'ID_\d+$', name):
        return 'ground', 'Ground/GroundEl material of another site (site set, not a library material)'
    if JUNK_RE.match(base) or base.startswith('Material #') or base.startswith('Стул_Опорный'):
        return 'junk', '3ds Max / Blender default or slot name, no material meaning'
    return 'meaningful', ''


def uv_cells(uv_dump: dict, image_name: str, atlas: dict) -> dict:
    """Map UV faces of every material bound to ``image_name`` onto the atlas cells."""
    W, H = atlas['size']
    cells = atlas['cells']
    use = collections.defaultdict(lambda: {'faces': 0, 'mafs': set(), 'min_margin_px': None, 'corner_faces': 0})
    uncovered = {'faces': 0, 'mafs': set()}
    for fi in uv_dump['files']:
        maf = _maf(fi['fbx'])
        for mat in fi.get('materials', {}).values():
            if not any(ntpath.basename(im.get('filepath') or '') == image_name for im in mat.get('images', [])):
                continue
            for face in mat.get('faces', []):
                n = len(face) // 2
                if n < 3 or len(face) % 2 or not all(math.isfinite(v) for v in face):
                    raise InputError(f'{fi["fbx"]}: bad UV face {face[:8]}')
                cu = sum(face[0::2]) / n
                cv = sum(face[1::2]) / n
                tu, tv = math.floor(cu), math.floor(cv)  # UDIM tile of the face centroid
                pts = [((face[k] - tu) * W, (1.0 - (face[k + 1] - tv)) * H) for k in range(0, len(face), 2)]
                cx = min((cu - tu) * W, W - 1e-6)
                cy = min((1.0 - (cv - tv)) * H, H - 1e-6)
                hit = None
                for mixed in (False, True):  # a flat block wins over the mixed remainder around it
                    for ci, c in enumerate(cells):
                        if (c['kind'] == 'mixed') == mixed and c['x'] <= cx < c['x'] + c['w'] \
                                and c['y'] <= cy < c['y'] + c['h']:
                            hit = ci
                            break
                    if hit is not None:
                        break
                if hit is None:
                    uncovered['faces'] += 1
                    uncovered['mafs'].add(maf)
                    continue
                c, u = cells[hit], use[hit]
                u['faces'] += 1
                u['mafs'].add(maf)
                m = min(min(p[0] - c['x'], c['x'] + c['w'] - p[0], p[1] - c['y'], c['y'] + c['h'] - p[1]) for p in pts)
                u['min_margin_px'] = round(m) if u['min_margin_px'] is None else min(u['min_margin_px'], round(m))
                z = 0.12 * min(c['w'], c['h'])  # bottom-right ID-number zone (Artem 2026-10-21)
                if any(p[0] > c['x'] + c['w'] - z and p[1] > c['y'] + c['h'] - z for p in pts):
                    u['corner_faces'] += 1
    return {'cells': {k: dict(v, mafs=sorted(v['mafs'])) for k, v in use.items()},
            'uncovered': dict(uncovered, mafs=sorted(uncovered['mafs']))}


def match_cells(atlases: list[dict], ids: list[dict]) -> None:
    """Assign every atlas cell to the nearest eligible id within tolerance (in place)."""
    for at in atlases:
        area = at['size'][0] * at['size'][1]
        for ci, c in enumerate(at['cells']):
            if at['role'] == 'opacity mask':
                c['id'], c['reason'] = None, 'opacity mask (alpha of its diffuse map), not a colour cell'
                continue
            if c['kind'] == 'mixed':
                c['id'], c['reason'] = None, 'mixed region around flat blocks (non-rectangular content: decal/pattern)'
                continue
            if c['w'] * c['h'] < MIN_CELL_SHARE * area:
                c['id'], c['reason'] = None, 'fragment below 1/1024 of the atlas (gutter/detail)'
                continue
            col = c['color'] if c['kind'] == 'solid' else c['mean']
            best = None
            for e in ids:
                if e.get('match') is False or c['kind'] not in e['cell_kinds']:
                    continue
                d = min(_dist(col, t) for t in e['targets'])
                if d <= MATCH_TOL[c['kind']] and (best is None or d < best[0]):
                    best = (d, e['id'])
            if best:
                c['id'], c['dist'], c['reason'] = best[1], round(best[0], 1), None
            else:
                c['id'], c['reason'] = None, ('patterned cell matches no id tone: decal or a material '
                                              'not in the list' if c['kind'] == 'patterned'
                                              else 'flat colour matches no id within tolerance')


def spec_requirements(schedule: dict, ids: list[dict]) -> list[dict]:
    out = []
    for r in schedule['rows']:
        text = ' '.join(str(r.get(k) or '') for k in ('name', 'material'))
        hit = [e['id'] for e in ids if e.get('spec') and re.search(e['spec'], text)]
        out.append({'table': r.get('table'), 'row': r.get('row'), 'name': r.get('name'),
                    'ids': hit, 'gap': not hit})
    return out


def check_paths(inputs: list[str], outputs: list[str]) -> None:
    norm = lambda p: os.path.normcase(os.path.realpath(p))  # noqa: E731
    ins = {norm(p) for p in inputs}
    seen = set()
    for o in outputs:
        n = norm(o)
        if n in ins:
            raise InputError(f'output resolves to an input: {o}')
        if n in seen:
            raise InputError(f'two outputs resolve to the same file: {o}')
        seen.add(n)


def build(args) -> dict:
    mats = _load(args.materials)
    uvd = _load(args.uv_dump)
    maxm = _load(args.max_maps)
    sched = _load(args.schedule)
    ral = _load(args.ral)['colors']
    seed = _load(args.seed)
    ids = load_seed(seed, ral)
    refs, empty = texture_refs(mats)
    if not refs and not empty:
        raise InputError('no texture references in --materials')
    hits = find_images(refs, args.maps_dir)

    inventory, missing, atlases = [], [], []
    for name in sorted(refs):
        r = refs[name]
        users = sorted(r['mafs'])
        if not hits.get(name):
            missing.append({'name': name, 'referenced_path': r['raw_path'], 'mafs': users,
                            'materials': sorted(r['materials']),
                            'reason': 'not found in any --maps-dir (searched: %s)' % '; '.join(args.maps_dir)})
            continue
        copies = [{'path': p, 'bytes': os.path.getsize(p), 'sha256': sha256_file(p)} for p in hits[name]]
        inventory.append({'name': name, 'copies': copies, 'mafs': users, 'materials': sorted(r['materials']),
                          'ground_other_site': bool(IMG_GROUND_RE.search(name)),
                          'copies_identical': len({c['sha256'] for c in copies}) == 1})
    for p in args.extra_atlas:
        if not os.path.isfile(p):
            raise InputError(f'extra atlas not found: {p}')
        inventory.append({'name': os.path.basename(p), 'copies': [{'path': p.replace('\\', '/'),
                          'bytes': os.path.getsize(p), 'sha256': sha256_file(p)}], 'mafs': [],
                          'materials': [], 'ground_other_site': False, 'copies_identical': True,
                          'source': 'extra atlas, not bound by a library MAF FBX'})
    for it in inventory:
        if it['ground_other_site']:
            continue
        seg = segment(it['copies'][0]['path'])
        it['size_px'] = seg['size']
        seg['name'] = it['name']
        seg['mafs'] = it['mafs']
        seg['role'] = 'opacity mask' if OPACITY_RE.search(it['name']) else 'atlas' if len([c for c in seg['cells'] if c['kind'] != 'mixed']) >= 3 else 'single-material map'
        atlases.append(seg)
    match_cells(atlases, ids)
    for at in atlases:
        at['uv'] = uv_cells(uvd, at['name'], at) if at['mafs'] else None

    # library materials -> ids / excluded / unmapped
    lib = collections.defaultdict(set)
    for fi in mats['files']:
        for mt in fi['materials']:
            lib[mt['name']].add(_maf(fi['fbx']))
    excluded, unmapped, lib_hits = [], [], collections.defaultdict(list)
    for name in sorted(lib):
        cls, why = classify_material(name)
        hit = [e['id'] for e in ids if e.get('library') and re.search(e['library'], name)]
        if hit:
            for i in hit:
                lib_hits[i].append({'material': name, 'mafs': len(lib[name])})
        elif cls != 'meaningful':
            excluded.append({'material': name, 'mafs': len(lib[name]), 'class': cls, 'reason': why})
        else:
            unmapped.append({'material': name, 'mafs': len(lib[name]),
                             'reason': 'meaningful name, no id pattern matches - needs Artem'})
    reqs = spec_requirements(sched, ids)

    max_files = collections.Counter()
    for m in maxm['materials']:
        for x in m['maps']:
            max_files['empty' if not x['file'] else 'file'] += 1

    rows = []
    for e in ids:
        cells = []
        for at in atlases:
            for ci, c in enumerate(at['cells']):
                if c.get('id') == e['id']:
                    u = (at['uv'] or {}).get('cells', {}).get(ci) if at['uv'] else None
                    cells.append({'atlas': at['name'], 'cell': ci, 'x': c['x'], 'y': c['y'], 'w': c['w'],
                                  'h': c['h'], 'kind': c['kind'], 'color': c['color'], 'dist': c['dist'],
                                  'uv_mafs': (u or {}).get('mafs', []), 'uv_faces': (u or {}).get('faces', 0)})
        spec_rows = [f"{q['table']}#{q['row']}" for q in reqs if e['id'] in q['ids']]
        status = 'proposed'
        if e.get('match') is False:
            status = 'proposed, spec-only: colour/appearance not given by any atlas or spec - needs Artem'
        elif not cells:
            status = 'proposed, gap: no atlas cell' + (' (spec asks for it)' if spec_rows else '')
        rows.append({'id': e['id'], 'key': e['key'], 'name_ru': e['name_ru'], 'kind': e['kind'],
                     'ral': e.get('ral'), 'target': e['target'], 'cells': cells,
                     'library_materials': lib_hits.get(e['id'], []), 'spec_rows': spec_rows,
                     'status': status})
    return {
        'schema': 'library-maf-material-ids', 'version': 'v004', 'status': 'proposed',
        'scope': "first deliverable of #524: ID list for Artem's review; layouts and the assembly "
                 'procedure follow his approval; nothing reassigned in the library',
        'match_method': 'atlas cell -> id by colour distance to the id targets (mean |dRGB| <= %s); the agent '
                        'did not inspect the images visually - Artem verifies on the contact sheet' % MATCH_TOL,
        'generated_by': 'tools/library/maf_atlas_ids.py',
        'inputs': {k: {'path': p, 'sha256': sha256_file(p)} for k, p in (
            ('materials', args.materials), ('uv_dump', args.uv_dump), ('max_maps', args.max_maps),
            ('schedule', args.schedule), ('seed', args.seed), ('ral', args.ral))},
        'maps_dirs': args.maps_dir,
        'ids': rows,
        'inventory': {'found': inventory, 'missing': missing,
                      'empty_bitmap': [{'material': k, 'mafs': len(v)} for k, v in sorted(empty.items())],
                      'empty_bitmap_note': 'FBX texture with an empty file path; the library .max scene keeps '
                                           '%d bitmap maps with no file (max_maps readback), so no image is '
                                           'bound - not guessed' % max_files['empty']},
        'atlases': [{k: v for k, v in at.items() if k != 'path'} | {'path': at['path']} for at in atlases],
        'library_materials': {'excluded': excluded, 'unmapped': unmapped},
        'spec_requirements': reqs,
    }


def _font(size: int):
    from PIL import ImageFont
    for f in ('C:/Windows/Fonts/arial.ttf', 'C:/Windows/Fonts/segoeui.ttf'):
        if os.path.isfile(f):
            return ImageFont.truetype(f, size)
    return ImageFont.load_default(size)


def draw_id(draw, box, text, font):
    """ID number small in the bottom-right corner of the cell (Artem 2026-10-21 atlas rule)."""
    x0, y0, x1, y1 = box
    tb = draw.textbbox((0, 0), text, font=font)
    tw, th = tb[2] - tb[0], tb[3] - tb[1]
    pad = 3
    rx0, ry0 = x1 - tw - 2 * pad, y1 - th - 2 * pad
    draw.rectangle((rx0, ry0, x1, y1), fill=(0, 0, 0))
    draw.text((rx0 + pad - tb[0], ry0 + pad - tb[1]), text, fill=(255, 255, 255), font=font)


def render_png(result: dict, out_dir: str) -> dict:
    from PIL import Image, ImageDraw
    Image.MAX_IMAGE_PIXELS = None
    os.makedirs(out_dir, exist_ok=True)
    written = {}
    paths = {at['name']: at['path'] for at in result['atlases']}
    tile, cols = 220, 6
    n = len(result['ids'])
    sheet = Image.new('RGB', (cols * tile, ((n + cols - 1) // cols) * (tile + 44)), (255, 255, 255))
    d = ImageDraw.Draw(sheet)
    f_id, f_lbl = _font(16), _font(13)
    cache = {}
    for k, e in enumerate(result['ids']):
        x, y = (k % cols) * tile, (k // cols) * (tile + 44)
        box = (x + 6, y + 6, x + tile - 6, y + tile - 6)
        if e['cells']:
            c = max(e['cells'], key=lambda c: c['w'] * c['h'])
            if c['atlas'] not in cache:
                cache[c['atlas']] = Image.open(paths[c['atlas']]).convert('RGB')
            s = min(c['w'], c['h'], 1024)
            cx, cy = c['x'] + c['w'] // 2, c['y'] + c['h'] // 2
            crop = cache[c['atlas']].crop((cx - s // 2, cy - s // 2, cx - s // 2 + s, cy - s // 2 + s))
            sheet.paste(crop.resize((box[2] - box[0], box[3] - box[1]), Image.LANCZOS), box[:2])
            src = '%s cell %d' % (c['atlas'][:18], c['cell'])
        else:
            d.rectangle(box, fill=_rgb(e['target']))
            d.line((box[0], box[1], box[2], box[3]), fill=(255, 0, 0), width=3)
            src = 'GAP: no atlas cell (target colour)'
        draw_id(d, box, str(e['id']), f_id)
        d.text((x + 6, y + tile - 2), e['key'], fill=(0, 0, 0), font=f_lbl)
        d.text((x + 6, y + tile + 16), src, fill=(90, 90, 90), font=f_lbl)
    p = os.path.join(out_dir, 'material_ids_v004_contact_sheet.png')
    sheet.save(p)
    written['contact_sheet'] = p
    for at in result['atlases']:
        if at['role'] != 'atlas':
            continue
        im = cache.get(at['name']) or Image.open(at['path']).convert('RGB')
        sc = 1024 / max(im.size)
        ov = im.resize((round(im.size[0] * sc), round(im.size[1] * sc)), Image.BOX)
        od = ImageDraw.Draw(ov)
        for ci, c in enumerate(at['cells']):
            b = (c['x'] * sc, c['y'] * sc, (c['x'] + c['w']) * sc - 1, (c['y'] + c['h']) * sc - 1)
            col = (255, 0, 255) if c['kind'] == 'mixed' else ((0, 200, 0) if c.get('id') else (255, 140, 0))
            od.rectangle(b, outline=col, width=2)
            if c.get('id') and c['w'] * sc > 24 and c['h'] * sc > 18:
                draw_id(od, tuple(round(v) for v in b), str(c['id']), _font(13))
        q = os.path.join(out_dir, 'overlay_%s.png' % re.sub(r'[^A-Za-z0-9_.-]', '_', os.path.splitext(at['name'])[0]))
        ov.save(q)
        written['overlay ' + at['name']] = q
    return {k: {'path': v.replace('\\', '/'), 'sha256': sha256_file(v)} for k, v in written.items()}


def render_md(r: dict) -> str:
    L = ['# MAF material IDs v004 - proposal (#524)', '',
         f"Status: **{r['status']}**. {r['scope']}. Generated by `{r['generated_by']}`; machine-readable twin "
         '`material_ids_v004.json`. ID number on every tile/cell: small, bottom-right corner (Artem 2026-10-21).', '',
         '## ID list', '',
         '| ID | key | name | kind | target | atlas cells (atlas: cell, px) | spec rows | library materials | status |',
         '|---|---|---|---|---|---|---|---|---|']
    for e in r['ids']:
        cells = '; '.join(f"{c['atlas']}: {c['cell']} ({c['w']}x{c['h']}, {c['color']})" for c in e['cells'][:4])
        if len(e['cells']) > 4:
            cells += f"; +{len(e['cells']) - 4}"
        libm = ', '.join(f"{m['material']} ({m['mafs']})" for m in e['library_materials'])
        L.append(f"| {e['id']} | `{e['key']}` | {e['name_ru']} | {e['kind']} | "
                 f"{('RAL ' + e['ral'] + ' ') if e['ral'] else ''}{e['target']} | {cells or '-'} | "
                 f"{len(e['spec_rows'])} | {libm or '-'} | {e['status']} |")
    L += ['', '## Specification rows without an id (gaps)', '']
    gaps = [q for q in r['spec_requirements'] if q['gap']]
    L += [f"- {q['table']}#{q['row']}: {q['name']}" for q in gaps] or ['- none']
    L += ['', '## Atlases: how they are made', '',
          'Concept (Artem 2026-10-21): MAFs are textured through atlases for both profiles - VPM: a 4K map per '
          'UDIM tile; NPM: 2K maps named GroundEl, laid out the same way; a site set is 512 px (MAF-09). '
          'Cells are found by guillotine cuts + flat-block detection (`tools/library/maf_atlas_cells.py`); '
          'cell -> id is a colour-distance match only (`dist`, mean |dRGB|), not a visual check - '
          'verify on the contact sheet and overlays. Telegram copies are compressed: layout, not exact pixels.', '',
          '| atlas | px | role | cells | largest cell (kind, share, id) | solid cell sides px (min / median / max) | MAFs |',
          '|---|---|---|---|---|---|---|']
    for at in r['atlases']:
        area = at['size'][0] * at['size'][1]
        real = [c for c in at['cells'] if c['kind'] != 'mixed' and c['w'] * c['h'] >= area / 1024]
        if not real:
            continue
        big = max(real, key=lambda c: c['w'] * c['h'])
        sides = sorted(min(c['w'], c['h']) for c in real if c['kind'] == 'solid')
        ss = f"{sides[0]} / {sides[len(sides) // 2]} / {sides[-1]}" if sides else '-'
        L.append(f"| {at['name']} | {at['size'][0]} | {at['role']} | {len(real)} | {big['kind']}, "
                 f"{big['w'] * big['h'] / area:.0%}, {big.get('id') or '-'} | {ss} | {len(at['mafs'])} |")
    L.append('')
    for at in r['atlases']:
        cells = at['cells']
        area = at['size'][0] * at['size'][1]
        sol = sum(c['w'] * c['h'] for c in cells if c['kind'] == 'solid')
        pat = sum(c['w'] * c['h'] for c in cells if c['kind'] == 'patterned')
        uv = at.get('uv')
        L.append(f"### {at['name']} ({at['size'][0]}x{at['size'][1]}, {at['role']}, MAFs: {len(at['mafs'])})")
        L.append(f"- cells: {len([c for c in cells if c['kind'] != 'mixed'])}; solid area {sol / area:.0%}, "
                 f"patterned area {pat / area:.0%}; mixed regions {len([c for c in cells if c['kind'] == 'mixed'])}")
        if uv:
            L.append(f"- UV faces outside every cell: {uv['uncovered']['faces']} "
                     f"(MAFs {len(uv['uncovered']['mafs'])})")
        L.append('')
        L.append('| cell | x,y | w x h px | kind | colour | id | MAFs on it (UV) | faces | min margin px | faces in ID corner |')
        L.append('|---|---|---|---|---|---|---|---|---|---|')
        for ci, c in enumerate(cells):
            u = (uv or {}).get('cells', {}).get(ci, {}) if uv else {}
            L.append(f"| {ci} | {c['x']},{c['y']} | {c['w']}x{c['h']} | {c['kind']} | {c['color']} | "
                     f"{c.get('id') or '- (' + (c.get('reason') or '') + ')'} | {len(u.get('mafs', []))} | "
                     f"{u.get('faces', 0)} | {u.get('min_margin_px', '-')} | {u.get('corner_faces', 0)} |")
        L.append('')
    inv = r['inventory']
    L += ['## Image inventory', '', '| image | px | copies (sha256 12) | MAFs | note |', '|---|---|---|---|---|']
    for it in inv['found']:
        sz = 'x'.join(map(str, it.get('size_px', []))) or '-'
        cp = '<br>'.join(f"`{c['path']}` {c['bytes']} B {c['sha256'][:12]}" for c in it['copies'])
        note = 'Ground texture of another site - excluded' if it['ground_other_site'] else it.get('source', '')
        L.append(f"| {it['name']} | {sz} | {cp} | {len(it['mafs'])} | {note} |")
    L += ['', '### Missing images (referenced, not found)', '']
    L += [f"- `{m['name']}` ({len(m['mafs'])} MAFs) referenced as `{m['referenced_path']}`" for m in inv['missing']]
    L += ['', f"### Empty bitmaps: {sum(x['mafs'] for x in inv['empty_bitmap'])} material uses", '',
          inv['empty_bitmap_note'], '']
    L += ['## Library material names that are not ids', '', '| material | MAFs | class | reason |', '|---|---|---|---|']
    ex = r['library_materials']
    L += [f"| {m['material']} | {m['mafs']} | {m.get('class', 'unmapped')} | {m['reason']} |"
          for m in ex['unmapped'] + ex['excluded']]
    return '\n'.join(L) + '\n'


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    for a in ('materials', 'uv-dump', 'max-maps', 'schedule', 'seed', 'ral', 'out-json', 'out-md'):
        ap.add_argument('--' + a, required=True)
    ap.add_argument('--maps-dir', action='append', required=True)
    ap.add_argument('--extra-atlas', action='append', default=[])
    ap.add_argument('--evidence-dir')
    args = ap.parse_args(argv)
    inputs = [args.materials, args.uv_dump, args.max_maps, args.schedule, args.seed, args.ral, *args.extra_atlas]
    try:
        check_paths(inputs, [args.out_json, args.out_md])
        if args.evidence_dir:
            ev = os.path.normcase(os.path.realpath(args.evidence_dir))
            if any(os.path.normcase(os.path.realpath(d)) == ev for d in args.maps_dir):
                raise InputError('evidence dir is a maps dir')
        result = build(args)
    except (InputError, OSError, KeyError, json.JSONDecodeError) as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 2
    if args.evidence_dir:
        result['evidence'] = render_png(result, args.evidence_dir)
    for path, text in ((args.out_json, json.dumps(result, ensure_ascii=False, indent=1) + '\n'),
                       (args.out_md, render_md(result))):
        tmp = path + '.partial'
        with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
            f.write(text)
        os.replace(tmp, path)
    print(f"ids {len(result['ids'])}; atlases {len(result['atlases'])}; found {len(result['inventory']['found'])}; "
          f"missing {len(result['inventory']['missing'])}; gaps "
          f"{sum(1 for e in result['ids'] if not e['cells'])}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
