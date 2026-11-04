"""Build the MAF material ID list (v004, v005, ...) from the atlases the library MAFs use (issue #524).

Pattern: verify actual artifacts, not exporter return codes (docs/domain/patterns/INDEX.md).
new-case: material ID list derived from atlas cells + MAF specification rows (#524).

Inputs (all read-only):
  --materials   library/maf/fbx_materials.json   (Blender readback of the library FBX: material -> images)
  --uv-dump     <uv_dump.json>                   (tools/library/maf_uv_dump.py: per-material UV faces)
  --max-maps    <max_maps.json>                  (tools/library/maf_max_maps_job.py: scene bitmap files)
  --maps-dir    <dir> (repeatable)               (where the referenced images are looked up, by file name)
  --extra-atlas <png> (repeatable)               (Artem's concept atlases; no library MAF binds them)
  --layout-example <png> (repeatable)            (layout examples: inventoried and segmented, never a
                                                  colour/texture source - Artem 2026-10-21)
  --prev-seed   <seed.json>                      (previous version: every old id must be kept or merged)
  --schedule    jobs/VATUTINO-SITE/maf/site-schedule.json (MAF specification rows, material column)
  --seed        library/maf/material_ids_v005_seed.json   (the ID list: id, key, kind, target, status)
  --ral         tools/materials/ral_classic.json
Outputs: --out-json, --out-md (small text, committed) and --evidence-dir (PNG contact sheet + atlas
overlays, never committed; rule 57). No output may resolve to an input; on any input error nothing
is written and the exit code is 2.

Every input element ends in the output or in a reported list with its reason: texture refs ->
found / missing / empty-bitmap; library material names -> id / excluded / unmapped; atlas cells
-> id / unmapped; specification rows -> ids / gap. The list status is the seed status
(``proposed``, or ``approved-v1`` once accepted [D181]). Every entry status uses that same prefix.
An id with ``swatch: "target"`` keeps its gap and uses the flat target colour; no patch is picked.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import io
import json
import math
import ntpath
import os
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from maf_atlas_cells import segment  # noqa: E402

KIND_CELLS = {  # which cell kinds an id kind may take
    'paint': {'solid'}, 'plastic': {'solid', 'patterned'}, 'rubber': {'solid'},
    'translucent': {'solid'}, 'metal': {'solid', 'patterned'}, 'wood': {'patterned'},
    'mineral': {'patterned'}, 'opacity': {'patterned'}, 'sheet': {'patterned', 'solid'},
}
SIZES = ('S', 'M', 'L')  # layout class: S flat cell, M patterned cell, L dominant wood
PATCH_TOL = 24.0  # picked clean patch for a gap id: mean |dRGB| to the target
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


CORNER_SHARE = 0.15  # side of the bottom-right ID zone, share of the cell content side (layout contract)
CORNER_MIN_PX = 16


def id_corner(content: list[int]) -> list[int]:
    """Bottom-right keep-out square [x, y, w, h] inside a content box: the ID number lives here."""
    x, y, w, h = content
    s = min(max(CORNER_MIN_PX, math.ceil(CORNER_SHARE * min(w, h))), min(w, h))
    return [x + w - s, y + h - s, s, s]


def clip_area(pts: list[tuple[float, float]], rect: list[float]) -> float:
    """Area of a polygon clipped to an axis-aligned rect [x, y, w, h] (Sutherland-Hodgman, any simple polygon).

    Positive area = the face really overlaps the rect; touching an edge or a corner point gives 0.
    """
    x0, y0 = rect[0], rect[1]
    x1, y1 = x0 + rect[2], y0 + rect[3]
    planes = ((0, x0, True), (0, x1, False), (1, y0, True), (1, y1, False))
    poly = list(pts)
    for axis, val, keep_ge in planes:
        if not poly:
            break
        inside = (lambda p: p[axis] >= val) if keep_ge else (lambda p: p[axis] <= val)
        out = []
        for i, cur in enumerate(poly):
            prev = poly[i - 1]
            if inside(cur):
                if not inside(prev):
                    out.append(_cut(prev, cur, axis, val))
                out.append(cur)
            elif inside(prev):
                out.append(_cut(prev, cur, axis, val))
        poly = out
    if len(poly) < 3:
        return 0.0
    return abs(sum(poly[i - 1][0] * p[1] - p[0] * poly[i - 1][1] for i, p in enumerate(poly))) / 2.0


def _cut(a, b, axis, val):
    t = (val - a[axis]) / (b[axis] - a[axis])
    return (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))


def write_atomic(path: str, data: bytes) -> None:
    """Write via an exclusively created, uniquely named temp next to ``path`` (never clobbers another file)."""
    d = os.path.dirname(os.path.abspath(path))
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.' + os.path.basename(path) + '.', suffix='.tmp', dir=d)
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(data)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def save_png(img, path: str) -> None:
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    write_atomic(path, buf.getvalue())


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
        own_n = len(targets)  # own tones; merged_also = tones of ids merged into this one
        targets += list(e.get('merged_also', []))
        for t in targets:
            _rgb(t)
        cells = set(e.get('cells') or KIND_CELLS[kind])
        if not cells <= {'solid', 'patterned'}:
            raise InputError(f'seed id {i}: bad cells {sorted(cells)}')
        size = e.get('size', 'S' if cells & {'solid'} else 'M')
        if size not in SIZES:
            raise InputError(f'seed id {i}: bad size {size!r} (one of {SIZES})')
        if not isinstance(e.get('atlas', True), bool):
            raise InputError(f'seed id {i}: atlas must be true/false')
        seen_id.add(i)
        seen_key.add(key)
        out.append(dict(e, target=target.upper(), targets=[t.upper() for t in targets],
                        own_targets=[t.upper() for t in targets[:own_n]], cell_kinds=sorted(cells),
                        size=size, atlas=e.get('atlas', True), review=list(e.get('review', []))))
    return out


def check_merges(seed: dict, ids: list[dict], prev: dict | None) -> list[dict]:
    """Every merge names a previous id and a kept id; every previous id is kept or merged (never lost)."""
    keys = {e['key'] for e in ids}
    merges = seed.get('merges', [])
    if not isinstance(merges, list):
        raise InputError('seed merges must be a list')
    seen = set()
    for m in merges:
        f, into = m.get('from_key'), m.get('into')
        if not f or f in seen:
            raise InputError(f'merge from_key missing or duplicated: {f!r}')
        if f in keys:
            raise InputError(f'merge {f!r}: merged key is still an id')
        if into not in keys:
            raise InputError(f'merge {f!r}: into {into!r} is not an id of this seed')
        if not m.get('reason'):
            raise InputError(f'merge {f!r}: no reason')
        seen.add(f)
    if prev is not None:
        old = {e['key'] for e in prev.get('ids', [])}
        if not old:
            raise InputError('prev seed has no ids')
        lost = sorted(old - keys - seen)
        if lost:
            raise InputError(f'previous ids neither kept nor merged: {lost}')
        ghost = sorted(seen - old)
        if ghost:
            raise InputError(f'merges name keys that are not in the previous seed: {ghost}')
    return merges


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
        for mname, mat in fi['materials'].items():
            if not any(ntpath.basename(im.get('filepath') or '') == image_name for im in mat.get('images', [])):
                continue
            if not mat.get('uv_layer'):
                raise InputError(f"{fi['fbx']}: material {mname} uses {image_name} but has no UV layer")
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
                # bottom-right ID-number keep-out (Artem 2026-10-21): the same id_corner contract as the
                # layouts, checked on EVERY cell independently of the centroid cell - a face whose centroid
                # lies in a neighbour cell (or in no cell) still violates the corner it overlaps
                for ci, c in enumerate(cells):
                    if clip_area(pts, id_corner([c['x'], c['y'], c['w'], c['h']])) > 1e-9:
                        use[ci]['corner_faces'] += 1
                        use[ci].setdefault('corner_mafs', set()).add(maf)
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
    return {'cells': {k: dict(v, mafs=sorted(v['mafs']), corner_mafs=sorted(v.get('corner_mafs', ())))
                      for k, v in use.items()},
            'uncovered': dict(uncovered, mafs=sorted(uncovered['mafs']))}


def match_cells(atlases: list[dict], ids: list[dict]) -> None:
    """Assign every atlas cell to the nearest eligible id within tolerance (in place)."""
    for at in atlases:
        area = at['size'][0] * at['size'][1]
        for ci, c in enumerate(at['cells']):
            if at['role'] == 'layout example':
                c['id'], c['reason'] = None, 'layout example only (Artem 2026-10-21): not a colour/texture source'
                continue
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


_ARR: dict = {}  # atlas path -> float pixel array (one decode per run)


def pick_patch(atlases: list[dict], e: dict, block: int = 32, k: int = 4) -> dict | None:
    """Clean textured patch for a gap id: a k x k window of blocks inside one non-mixed real-atlas cell...

    ...whose mean is nearest the id target (<= PATCH_TOL), homogeneous (block means vary little - no decal
    edge) and textured (pixel std > 4). Returns None when nothing qualifies; never a default.
    """
    import numpy as np
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    best = None
    for at in atlases:
        if at['role'] != 'atlas':
            continue
        im = _ARR.get(at['path'])
        for c in at['cells']:
            if c['kind'] != 'patterned' or c.get('id') is not None and c['id'] != e['id']:
                continue
            if im is None:
                im = _ARR[at['path']] = np.asarray(Image.open(at['path']).convert('RGB'), dtype=np.float32)
            sub = im[c['y']:c['y'] + c['h'], c['x']:c['x'] + c['w']]
            ny, nx = sub.shape[0] // block, sub.shape[1] // block
            if ny < k + 2 or nx < k + 2:
                continue
            g = sub[:ny * block, :nx * block].reshape(ny, block, nx, block, 3)
            means, stds = g.mean((1, 3)), g.std((1, 3)).mean(-1)
            for by in range(1, ny - k):  # skip the border ring of blocks (gutters, cut lines)
                for bx in range(1, nx - k):
                    m = means[by:by + k, bx:bx + k].reshape(-1, 3)
                    mu = m.mean(0)
                    if m.std(0).mean() > 6 or stds[by:by + k, bx:bx + k].mean() <= 4:
                        continue
                    hexc = '#%02X%02X%02X' % tuple(int(round(v)) for v in mu)
                    d = min(_dist(hexc, t) for t in e['targets'])
                    if d <= PATCH_TOL and (best is None or d < best['dist']):
                        best = {'atlas': at['name'], 'x': c['x'] + bx * block, 'y': c['y'] + by * block,
                                'w': k * block, 'h': k * block, 'mean': hexc, 'dist': round(d, 1),
                                'note': 'picked clean patch by colour search inside an unassigned patterned '
                                        'cell - на проверку'}
    return best


def list_status(seed: dict) -> str:
    """``proposed`` until Artem accepts the list; ``approved-v1`` is the first working version [D181]."""
    status = seed.get('status') or 'proposed'
    if status not in ('proposed', 'approved-v1'):
        raise InputError(f'seed status must be proposed or approved-v1, got {status!r}')
    if status == 'approved-v1':
        approval = seed.get('approval') or {}
        if not isinstance(approval, dict) or not str(approval.get('date') or '') or not str(approval.get('quote') or ''):
            raise InputError('approved-v1 seed needs approval.date and approval.quote')
    return status


def spec_requirements(schedule: dict, ids: list[dict]) -> list[dict]:
    out = []
    for r in schedule['rows']:
        text = ' '.join(str(r.get(k) or '') for k in ('name', 'material'))
        hit = [e['id'] for e in ids if e.get('spec') and re.search(e['spec'], text)]
        out.append({'table': r.get('table'), 'row': r.get('row'), 'name': r.get('name'),
                    'ids': hit, 'gap': not hit})
    return out


def check_uv_dump(uv_dump: dict, required: dict) -> dict:
    """Fail closed on a failed or incomplete UV readback before any analysis.

    ``required``: image name -> MAFs whose FBX binds it. Every dump row must be a successful import with
    materials; every required MAF must have exactly one row; a material bound to the image without a UV
    layer is an error. A required (MAF, image) pair with no face is not counted as zero measured faces: it is
    returned as ``{image: [{maf, fbx, reason}]}`` (the FBX lists the material but no polygon uses it - the
    dump only holds materials that polygons use - or Blender did not read the binding back).
    """
    files = uv_dump.get('files') if isinstance(uv_dump, dict) else None
    if not isinstance(files, list) or not files:
        raise InputError('uv dump: no files')
    rows = {}
    for fi in files:
        if not isinstance(fi, dict) or not fi.get('fbx'):
            raise InputError(f'uv dump: row without fbx: {str(fi)[:80]}')
        if 'error' in fi:
            raise InputError(f"uv dump: {fi['fbx']}: {fi['error']}")
        if not isinstance(fi.get('materials'), dict) or not fi['materials']:
            raise InputError(f"uv dump: {fi['fbx']}: no materials")
        maf = _maf(fi['fbx'])
        if maf in rows:
            raise InputError(f'uv dump: {maf} given twice ({rows[maf]["fbx"]}, {fi["fbx"]})')
        rows[maf] = fi
    unmeasured = collections.defaultdict(list)
    for image, mafs in sorted(required.items()):
        for maf in sorted(mafs):
            fi = rows.get(maf)
            if fi is None:
                raise InputError(f'uv dump: no row for {maf} (its FBX uses {image})')
            bound = {k: m for k, m in fi['materials'].items()
                     if any(ntpath.basename(im.get('filepath') or '') == image for im in m.get('images', []))}
            for k, m in bound.items():
                if not m.get('uv_layer'):
                    raise InputError(f"uv dump: {fi['fbx']}: material {k} uses {image} but has no UV layer")
            if not sum(len(m.get('faces') or []) for m in bound.values()):
                unmeasured[image].append({'maf': maf, 'fbx': fi['fbx'], 'reason': (
                    f'no polygon of the imported FBX uses a material bound to {image} (unused material slot, '
                    'or the binding was not read back): not measured, not counted as 0 faces')})
    return dict(unmeasured)


def check_paths(inputs: list[str], outputs: list[str]) -> None:
    norm = lambda p: os.path.normcase(os.path.realpath(p))  # noqa: E731
    ins = {norm(p) for p in inputs}
    seen = set()
    for o in outputs:
        n = norm(o)
        if n in ins:
            raise InputError(f'output resolves to an input: {o}')
        if os.path.isdir(o):
            raise InputError(f'output is a directory: {o}')
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
    version = seed.get('version')
    if not isinstance(version, str) or not re.fullmatch(r'v\d{3}', version):
        raise InputError(f'seed version must look like v005, got {version!r}')
    merges = check_merges(seed, ids, _load(args.prev_seed) if getattr(args, 'prev_seed', None) else None)
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
    examples = list(getattr(args, 'layout_example', None) or [])
    for p, src in [(p, 'extra atlas, not bound by a library MAF FBX') for p in args.extra_atlas] + \
            [(p, 'layout example only, never a colour/texture source') for p in examples]:
        if not os.path.isfile(p):
            raise InputError(f'extra atlas not found: {p}')
        if any(it['name'] == os.path.basename(p) for it in inventory):
            raise InputError(f'image name given twice: {os.path.basename(p)}')
        inventory.append({'name': os.path.basename(p), 'copies': [{'path': p.replace('\\', '/'),
                          'bytes': os.path.getsize(p), 'sha256': sha256_file(p)}], 'mafs': [],
                          'materials': [], 'ground_other_site': False, 'copies_identical': True,
                          'source': src})
    example_names = {os.path.basename(p) for p in examples}
    for it in inventory:
        if it['ground_other_site']:
            continue
        seg = segment(it['copies'][0]['path'])
        it['size_px'] = seg['size']
        seg['name'] = it['name']
        seg['mafs'] = it['mafs']
        seg['role'] = 'layout example' if it['name'] in example_names else \
            'opacity mask' if OPACITY_RE.search(it['name']) else 'atlas' if len([c for c in seg['cells'] if c['kind'] != 'mixed']) >= 3 else 'single-material map'
        atlases.append(seg)
    unmeasured = check_uv_dump(uvd, {at['name']: at['mafs'] for at in atlases if at['mafs']})
    match_cells(atlases, ids)
    for at in atlases:
        at['uv'] = uv_cells(uvd, at['name'], at) if at['mafs'] else None
        if at['uv'] is not None:
            at['uv']['unmeasured'] = unmeasured.get(at['name'], [])

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

    prefix = list_status(seed)
    rows = []
    for e in ids:
        cells = []
        for at in atlases:
            for ci, c in enumerate(at['cells']):
                if c.get('id') == e['id']:
                    u = (at['uv'] or {}).get('cells', {}).get(ci) if at['uv'] else None
                    cells.append({'atlas': at['name'], 'cell': ci, 'x': c['x'], 'y': c['y'], 'w': c['w'],
                                  'h': c['h'], 'kind': c['kind'], 'color': c['color'], 'dist': c['dist'],
                                  'dist_own': round(min(_dist(c['color'] if c['kind'] == 'solid' else c['mean'],
                                                                  t) for t in e['own_targets']), 1),
                                  'uv_mafs': (u or {}).get('mafs', []), 'uv_faces': (u or {}).get('faces', 0)})
        spec_rows = [f"{q['table']}#{q['row']}" for q in reqs if e['id'] in q['ids']]
        status = prefix
        patch_ = None
        # swatch "target": the gap stays, and the contact sheet is the flat target colour (no picked crop).
        if not cells and e['atlas'] and 'patterned' in e['cell_kinds'] and e.get('swatch') != 'target':
            patch_ = pick_patch(atlases, e)
        if not e['atlas']:
            status = prefix + ', not in the atlas: ' + str((seed.get('kinds') or {}).get(e['kind'], e['kind']))
        elif e.get('match') is False:
            status = prefix + ', spec-only: colour/appearance not given by any atlas or spec - needs Artem'
        elif not cells:
            status = prefix + ', gap: no atlas cell' + (' (spec asks for it)' if spec_rows else '')
        elif not any(c['dist_own'] <= MATCH_TOL[c['kind']] for c in cells):
            status = prefix + ', gap: atlas cells only of merged shades, none of the own tones'
        rows.append({'id': e['id'], 'key': e['key'], 'name_ru': e['name_ru'], 'kind': e['kind'],
                     'ral': e.get('ral'), 'target': e['target'], 'cells': cells,
                     'library_materials': lib_hits.get(e['id'], []), 'spec_rows': spec_rows,
                     'size': e['size'], 'atlas': e['atlas'], 'review': e['review'],
                     'prev_id': e.get('v004_id'), 'picked_patch': patch_, 'status': status})
    result = {
        'schema': 'library-maf-material-ids', 'version': version, 'status': prefix,
    }
    if prefix == 'approved-v1':
        approval = seed['approval']
        result['approval'] = {'date': approval['date'], 'quote': approval['quote'],
                              'by': approval.get('by') or 'Artem'}
    result.update({
        'scope': seed.get('scope') or ("ID list of #524 for Artem's review; nothing reassigned in the library"),
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
        'merges': merges,
        'decals': seed.get('decals'),
    })
    return result


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


def swatch(result: dict, e: dict, size: int, cache: dict):
    """(image, source label) for an id: real crop of its largest atlas cell (patterned), the measured cell
    colour (solid), a picked clean patch, or the target colour for a gap. Never a layout example."""
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    paths = {at['name']: at['path'] for at in result['atlases']}
    roles = {at['name']: at['role'] for at in result['atlases']}

    def crop(name, x, y, w, h):
        if roles.get(name) == 'layout example':
            raise InputError(f"id {e['id']}: swatch from a layout example {name}")
        if name not in cache:
            cache[name] = Image.open(paths[name]).convert('RGB')
        ins = round(0.06 * min(w, h))  # stay clear of cell borders, gutters and corner numbers
        s = min(w, h) - 2 * ins
        cx, cy = x + w // 2, y + h // 2
        return cache[name].crop((cx - s // 2, cy - s // 2, cx - s // 2 + s, cy - s // 2 + s)).resize(
            (size, size), Image.LANCZOS)
    own = [c for c in e['cells'] if c['dist_own'] <= MATCH_TOL[c['kind']]]  # not only merged-in shades
    if own:
        best = min(c['dist_own'] for c in own)
        near = [c for c in own if c['dist_own'] <= best + 4]  # nearest tone; largest of those
        c = max(near, key=lambda c: c['w'] * c['h'])
        if c['kind'] == 'solid':
            return Image.new('RGB', (size, size), _rgb(c['color'])), '%s cell %d (flat %s)' % (
                c['atlas'][:18], c['cell'], c['color'])
        return crop(c['atlas'], c['x'], c['y'], c['w'], c['h']), '%s cell %d' % (c['atlas'][:18], c['cell'])
    p = e.get('picked_patch')
    if p:
        return crop(p['atlas'], p['x'], p['y'], p['w'], p['h']), 'GAP: patch %s (на проверку)' % p['atlas'][:14]
    why = ' (cells only of merged shades)' if e['cells'] else ''
    return Image.new('RGB', (size, size), _rgb(e['target'])), 'GAP: target colour %s%s' % (e['target'], why)


def _tile_path(out_dir: str, e: dict) -> str:
    return os.path.join(out_dir, 'tiles', 'ID_%02d_%s.png' % (e['id'], e['key']))


def _sheet_path(out_dir: str, result: dict) -> str:
    return os.path.join(out_dir, 'material_ids_%s_contact_sheet.png' % result['version'])


def _overlay_path(out_dir: str, at: dict) -> str:
    return os.path.join(out_dir, 'overlay_%s.png' % re.sub(r'[^A-Za-z0-9_.-]', '_', os.path.splitext(at['name'])[0]))


def evidence_targets(result: dict, out_dir: str) -> list[str]:
    """Every file ``render_png`` writes (preflighted against all inputs before anything is written)."""
    return [_sheet_path(out_dir, result)] + [_tile_path(out_dir, e) for e in result['ids']] + \
        [_overlay_path(out_dir, at) for at in result['atlases'] if at['role'] in ('atlas', 'layout example')]


def render_png(result: dict, out_dir: str) -> dict:
    from PIL import Image, ImageDraw
    Image.MAX_IMAGE_PIXELS = None
    written, tiles = {}, []
    tile, cols = 220, 6
    n = len(result['ids'])
    sheet = Image.new('RGB', (cols * tile, ((n + cols - 1) // cols) * (tile + 44)), (255, 255, 255))
    d = ImageDraw.Draw(sheet)
    f_id, f_lbl = _font(16), _font(13)
    cache = {}
    for k, e in enumerate(result['ids']):
        x, y = (k % cols) * tile, (k // cols) * (tile + 44)
        box = (x + 6, y + 6, x + tile - 6, y + tile - 6)
        img, src = swatch(result, e, 512, cache)
        sheet.paste(img.resize((box[2] - box[0], box[3] - box[1]), Image.LANCZOS), box[:2])
        tp = _tile_path(out_dir, e)
        save_png(img, tp)  # clean tile: no number baked in (the number is drawn by the layout, bottom-right)
        tiles.append({'id': e['id'], 'key': e['key'], 'file': 'tiles/' + os.path.basename(tp),
                      'sha256': sha256_file(tp), 'source': src})
        draw_id(d, box, str(e['id']), f_id)
        d.text((x + 6, y + tile - 2), e['key'], fill=(0, 0, 0), font=f_lbl)
        d.text((x + 6, y + tile + 16), src, fill=(200, 0, 0) if src.startswith('GAP') else (90, 90, 90),
               font=f_lbl)
    p = _sheet_path(out_dir, result)
    save_png(sheet, p)
    written['contact_sheet'] = p
    for at in result['atlases']:
        if at['role'] not in ('atlas', 'layout example'):
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
        q = _overlay_path(out_dir, at)
        save_png(ov, q)
        written['overlay ' + at['name']] = q
    out = {k: {'path': v.replace('\\', '/'), 'sha256': sha256_file(v)} for k, v in written.items()}
    out['tiles'] = tiles
    return out


def _uv_cell(uv: dict | None, index: int) -> dict:
    """Cell UV record. JSON object keys are strings; a fresh build keeps int keys."""
    if not uv:
        return {}
    cells = uv.get('cells') or {}
    found = cells.get(index)
    if found is None:
        found = cells.get(str(index))
    return found or {}


def render_md(r: dict) -> str:
    v = r['version']
    title = 'approved-v1' if r['status'] == 'approved-v1' else 'proposal'
    approved = ''
    if r.get('approval'):
        approved = f" Approved {r['approval']['date']} [D181]: «{r['approval']['quote']}»."
    scope = str(r['scope']).rstrip().rstrip('.')
    L = [f'# MAF material IDs {v} - {title} (#524)', '',
         f"Status: **{r['status']}**.{approved} {scope}. Generated by `{r['generated_by']}`; machine-readable twin "
         f'`material_ids_{v}.json`. ID number on every tile/cell: small, bottom-right corner (Artem 2026-10-21); '
         'swatch tiles carry no number inside the texture.', '',
         '## ID list', '',
         '| ID | prev | key | name | kind | size | target | atlas cells (atlas: cell, px) | spec rows | '
         'library materials | status |',
         '|---|---|---|---|---|---|---|---|---|---|---|']
    for e in r['ids']:
        cells = '; '.join(f"{c['atlas']}: {c['cell']} ({c['w']}x{c['h']}, {c['color']})" for c in e['cells'][:4])
        if len(e['cells']) > 4:
            cells += f"; +{len(e['cells']) - 4}"
        libm = ', '.join(f"{m['material']} ({m['mafs']})" for m in e['library_materials'])
        pp = e.get('picked_patch')
        if not cells and pp:
            cells = f"GAP; picked patch {pp['atlas']} {pp['x']},{pp['y']} {pp['w']}x{pp['h']} {pp['mean']} (на проверку)"
        st = e['status'] + ''.join('; на проверку: ' + x for x in e.get('review', []))
        L.append(f"| {e['id']} | {e.get('prev_id') or '-'} | `{e['key']}` | {e['name_ru']} | {e['kind']} | "
                 f"{e.get('size', '-')} | {('RAL ' + e['ral'] + ' ') if e['ral'] else ''}{e['target']} | "
                 f"{cells or '-'} | {len(e['spec_rows'])} | {libm or '-'} | {st} |")
    if r.get('merges'):
        keyid = {e['key']: e['id'] for e in r['ids']}
        L += ['', '## Merged (previous id -> kept id)', '', '| previous | into | reason |', '|---|---|---|']
        L += [f"| {m.get('from_v004_id', '-')} `{m['from_key']}` | {keyid[m['into']]} `{m['into']}` | "
              f"{m['reason']} |" for m in r['merges']]
    if r.get('decals'):
        L += ['', '## Per-MAF decals (not material IDs)', '', r['decals']['rule'] + ':', '']
        L += [f'- {x}' for x in r['decals'].get('examples', [])]
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
            um = uv.get('unmeasured') or []
            L.append(f"- MAFs binding this image with no UV face read back (not measured, not 0): {len(um)}"
                     + (' - ' + ', '.join(u['maf'] for u in um) if um else ''))
        L.append('')
        L.append('| cell | x,y | w x h px | kind | colour | id | MAFs on it (UV) | faces | min margin px | faces in ID corner |')
        L.append('|---|---|---|---|---|---|---|---|---|---|')
        for ci, c in enumerate(cells):
            u = _uv_cell(uv, ci)
            L.append(f"| {ci} | {c['x']},{c['y']} | {c['w']}x{c['h']} | {c['kind']} | {c['color']} | "
                     f"{c.get('id') or '- (' + (c.get('reason') or '') + ')'} | {len(u.get('mafs', []))} | "
                     f"{u.get('faces', 0)} | {'-' if u.get('min_margin_px') is None else u['min_margin_px']} | {u.get('corner_faces', 0)} |")
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


def keepout_violations(result: dict) -> list[str]:
    """'<atlas> cell <n>: <faces> faces (<MAFs>)' for every cell whose ID corner a UV face overlaps."""
    out = []
    for at in result['atlases']:
        for k, u in sorted(((at.get('uv') or {}).get('cells') or {}).items(), key=lambda kv: int(kv[0])):
            if u.get('corner_faces'):
                out.append(f"{at['name']} cell {k}: {u['corner_faces']} faces "
                           f"({', '.join(u.get('corner_mafs') or u['mafs'])})")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    for a in ('materials', 'uv-dump', 'max-maps', 'schedule', 'seed', 'ral', 'out-json', 'out-md'):
        ap.add_argument('--' + a, required=True)
    ap.add_argument('--maps-dir', action='append', required=True)
    ap.add_argument('--extra-atlas', action='append', default=[])
    ap.add_argument('--layout-example', action='append', default=[])
    ap.add_argument('--prev-seed')
    ap.add_argument('--evidence-dir')
    ap.add_argument('--require-keepout', action='store_true',
                    help='exit 1 (nothing written) when any UV face overlaps the bottom-right ID corner of a cell')
    args = ap.parse_args(argv)
    inputs = [args.materials, args.uv_dump, args.max_maps, args.schedule, args.seed, args.ral, *args.extra_atlas,
              *args.layout_example] + ([args.prev_seed] if args.prev_seed else [])
    try:
        check_paths(inputs, [args.out_json, args.out_md])
        if args.evidence_dir:
            ev = os.path.normcase(os.path.realpath(args.evidence_dir))
            if any(os.path.normcase(os.path.realpath(d)) == ev for d in args.maps_dir):
                raise InputError('evidence dir is a maps dir')
        result = build(args)
        # preflight every actual target against every actual source (CLI inputs + found images) and each other
        found = [c['path'] for it in result['inventory']['found'] for c in it['copies']]
        targets = [args.out_json, args.out_md] + (evidence_targets(result, args.evidence_dir)
                                                  if args.evidence_dir else [])
        check_paths(inputs + found, targets)
    except (InputError, OSError, KeyError, json.JSONDecodeError) as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 2
    if args.require_keepout:
        bad = keepout_violations(result)
        if bad:
            print('error: UV faces in the ID-number keep-out corner: ' + '; '.join(bad), file=sys.stderr)
            return 1
    if args.evidence_dir:
        result['evidence'] = render_png(result, args.evidence_dir)
    for path, text in ((args.out_json, json.dumps(result, ensure_ascii=False, indent=1) + '\n'),
                       (args.out_md, render_md(result))):
        write_atomic(path, text.encode('utf-8'))
    print(f"ids {len(result['ids'])}; atlases {len(result['atlases'])}; found {len(result['inventory']['found'])}; "
          f"missing {len(result['inventory']['missing'])}; gaps "
          f"{sum(1 for e in result['ids'] if not e['cells'])}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
