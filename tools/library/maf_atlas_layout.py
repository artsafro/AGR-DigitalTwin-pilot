"""Lay the v005 MAF material IDs out on atlases: library VPM 4K / NPM 2K and a 512 site set (issue #524).

Pattern: verify actual artifacts, not exporter return codes (docs/domain/patterns/INDEX.md).
new-case: library-wide ID atlas layout (4K UDIM tile, 2K GroundEl, 512 site set) with the ID number in the
bottom-right corner of every cell and a UV corner keep-out zone (#524, Artem 2026-10-21).

Inputs (read-only): --ids library/maf/material_ids_v005.json (its evidence.tiles name the swatch tiles and
their SHA256), --tiles-dir <evidence dir of the ids run>, --spec library/maf/atlas_layout_v005_spec.json,
--site-set <jobs/.../site-maf-set.json> (optional; one per spec site set, name=path).
Outputs: --out-json (small text, committed) and --evidence-dir (PNG layouts, never committed; rule 57).
Fail closed (exit 2, nothing written): a tile missing or with another SHA256 than the ids JSON records, an
id without a tile, a site material without an id mapping, an id key unknown to the ids JSON, a layout
that does not fit, an output resolving to an input.

Packing: tools/materials/atlas_maf.py buddy allocator (power-of-two squares, largest first). The library
layout uses fixed slot sides per layout class (L/M/S) plus a decal reserve; the 512 site set uses the
regulated atlas_maf contract (flat 64/128, patterned >= 128, padding 8, patterned growth).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / 'materials'))
import atlas_maf  # noqa: E402
from maf_atlas_ids import (CORNER_MIN_PX, CORNER_SHARE, InputError, _font, _load, check_paths,  # noqa: E402,F401
                           draw_id, id_corner, save_png, sha256_file, write_atomic)


def fit_font(text: str, side: int):
    """Largest font (>= 5 px) whose draw_id box fits a side x side corner; None if none fits."""
    from PIL import Image, ImageDraw
    d = ImageDraw.Draw(Image.new('RGB', (1, 1)))
    for px in range(max(5, round(side * 0.6)), 4, -1):
        f = _font(px)
        tb = d.textbbox((0, 0), text, font=f)
        if tb[2] - tb[0] + 7 <= side and tb[3] - tb[1] + 7 <= side:  # draw_id: 3 px pad per side, inclusive box
            return f
    return None


def _uv(box: list[int], size: int) -> list[float]:
    x, y, w, h = box
    return [round(x / size, 6), round(1 - (y + h) / size, 6), round((x + w) / size, 6), round(1 - y / size, 6)]


def load_tiles(ids: dict, tiles_dir: str) -> dict:
    """key -> tile path, verified against the SHA256 the ids run recorded (no stale or swapped tile)."""
    rec = {t['key']: t for t in (ids.get('evidence') or {}).get('tiles', [])}
    out = {}
    for e in ids['ids']:
        if not e.get('atlas', True):
            continue
        t = rec.get(e['key'])
        if not t:
            raise InputError(f"id {e['id']} {e['key']}: no tile recorded in the ids JSON")
        p = os.path.join(tiles_dir, t['file'])
        if not os.path.isfile(p):
            raise InputError(f"id {e['id']} {e['key']}: tile not found: {p}")
        if sha256_file(p) != t['sha256']:
            raise InputError(f"id {e['id']} {e['key']}: tile SHA256 differs from the ids JSON (stale tile): {p}")
        out[e['key']] = p
    return out


def _is_flat(path: str) -> tuple[bool, tuple[int, int, int]]:
    from PIL import Image
    with Image.open(path) as im:
        lo, hi = zip(*im.convert('RGB').getextrema())
    return lo == hi, tuple(lo)


def plan_library(ids: dict, spec: dict) -> dict:
    lib = spec['library']
    size, pad, slot = lib['size'], lib['padding_px'], lib['slot_px']
    for k in ('L', 'M', 'S'):
        if not atlas_maf._is_pow2(slot.get(k, 0)) or slot[k] <= pad + 2 * CORNER_MIN_PX:
            raise InputError(f'library slot {k}: {slot.get(k)} is not a power of two above the padding')
    items, excluded = [], []
    for e in ids['ids']:
        if not e.get('atlas', True):
            excluded.append({'id': e['id'], 'key': e['key'], 'reason': e['status']})
            continue
        if e.get('size') not in slot:
            raise InputError(f"id {e['id']} {e['key']}: no layout class (size) {e.get('size')!r}")
        items.append((e['id'], slot[e['size']]))
    if not items:
        raise InputError('no ids to lay out')
    reserve = lib.get('decal_reserve_px') or 0
    placed_items = items + ([(10 ** 6, reserve)] if reserve else [])
    if sum(s * s for _, s in placed_items) > size * size:
        raise InputError(f'library layout does not fit {size}x{size}')
    placed = atlas_maf._place(placed_items, size)
    if placed is None:
        raise InputError(f'library layout does not fit {size}x{size} (packer)')
    by = {e['id']: e for e in ids['ids']}
    cells = []
    for i, s in items:
        x, y = placed[i]
        content = [x + pad // 2, y + pad // 2, s - pad, s - pad]
        cells.append({'id': i, 'key': by[i]['key'], 'size_class': by[i]['size'], 'slot_px': [x, y, s, s],
                      'content_px': content, 'id_corner_px': id_corner(content)})
    used = sum(s * s for _, s in placed_items)
    out = {'size': size, 'padding_px': pad, 'cells': cells, 'excluded': excluded,
           'free_share': round(1 - used / (size * size), 3)}
    if reserve:
        x, y = placed[10 ** 6]
        out['decal_reserve_px'] = [x, y, reserve, reserve]
    return out


def scale_layout(base: dict, size: int) -> dict:
    """Same layout at another power-of-two resolution (NPM 2K = VPM 4K x 0.5); padding stays >= 8 px."""
    k = size / base['size']
    if not atlas_maf._is_pow2(size) or k > 1:
        raise InputError(f'profile size {size} must be a power of two <= {base["size"]}')
    pad = round(base['padding_px'] * k)
    if pad < atlas_maf.MIN_PADDING:
        raise InputError(f'profile {size}: padding {pad} px < {atlas_maf.MIN_PADDING} px (reg p.9 §5.4)')
    cells = []
    for c in base['cells']:
        x, y, s, _ = (round(v * k) for v in c['slot_px'])
        content = [x + pad // 2, y + pad // 2, s - pad, s - pad]
        cells.append(dict(c, slot_px=[x, y, s, s], content_px=content, id_corner_px=id_corner(content)))
    out = dict(base, size=size, padding_px=pad, cells=cells)
    if 'decal_reserve_px' in base:
        out['decal_reserve_px'] = [round(v * k) for v in base['decal_reserve_px']]
    return out


def plan_site(ids: dict, site: dict, positions: list[dict], tiles: dict, size: int = 512) -> dict:
    """512 site set with only the ids the site uses (atlas_maf contract) + per-position material -> id."""
    keys = {e['key']: e for e in ids['ids']}
    m2i = site['material_to_id']
    for mat, key in m2i.items():
        if key not in keys:
            raise InputError(f'site material {mat!r} maps to unknown id key {key!r}')
        if not keys[key].get('atlas', True):
            raise InputError(f'site material {mat!r} maps to {key!r}, which has no atlas cell by rule')
    rows, used = [], []
    for p in positions:
        for slot, mat in sorted(p['material_map'].items()):
            if mat not in m2i:
                raise InputError(f"{p['set_id']}: material {mat!r} has no id mapping in the spec")
            rows.append({'set_id': p['set_id'], 'catalogue_id': p.get('catalogue_id'), 'slot': slot,
                         'material': mat, 'id': keys[m2i[mat]]['id'], 'key': m2i[mat]})
            if m2i[mat] not in used:
                used.append(m2i[mat])
    if not rows:
        raise InputError('site set has no position materials')
    mats = []
    for n, key in enumerate(sorted(used, key=lambda k: keys[k]['id'])):
        flat, col = _is_flat(tiles[key])
        mats.append(atlas_maf.Material(name=key, kind='solid' if flat else 'patterned', size=64 if flat else 128,
                                       index=n, color=col if flat else None,
                                       texture=None if flat else Path(tiles[key])))
    try:
        slots = atlas_maf.plan_atlas(mats, size, atlas_maf.MIN_PADDING)
    except atlas_maf.AtlasError as exc:
        raise InputError(f'site set: {exc}') from exc
    cells = []
    for s in slots:
        content = list(atlas_maf._content_box(s.x, s.y, s.size, atlas_maf.MIN_PADDING))
        cells.append({'id': keys[s.name]['id'], 'key': s.name, 'kind': s.kind, 'slot_px': [s.x, s.y, s.size, s.size],
                      'content_px': content, 'id_corner_px': id_corner(content)})
    cells.sort(key=lambda c: c['id'])
    return {'size': size, 'padding_px': atlas_maf.MIN_PADDING, 'cells': cells, 'positions': rows,
            '_materials': mats, '_slots': slots}


def render(layout: dict, tiles: dict, path: str) -> dict:
    from PIL import Image, ImageDraw
    size = layout['size']
    if '_slots' in layout:
        im = atlas_maf.render_atlas(layout['_slots'], layout['_materials'], size, layout['padding_px'])
    else:
        im = Image.new('RGB', (size, size), atlas_maf.NEUTRAL)
        for c in layout['cells']:
            x, y, _, _ = c['slot_px']
            cx, _, cw, _ = c['content_px']
            # content + edge-repeated gutter (bleed), the same as the 512 atlas_maf renderer
            block = atlas_maf._pattern_block(Path(tiles[c['key']]), cw, cx - x)
            im.paste(Image.fromarray(block, 'RGB'), (x, y))
    d = ImageDraw.Draw(im)
    for c in layout['cells']:
        zx, zy, zs, _ = c['id_corner_px']
        draw_id(d, (zx, zy, zx + zs - 1, zy + zs - 1), str(c['id']), fit_font(str(c['id']), zs))
    save_png(im, path)
    return {'path': path.replace('\\', '/'), 'sha256': sha256_file(path), 'size': [size, size]}


def corner_fits(layout: dict) -> list[str]:
    """IDs whose number box would spill out of its keep-out corner (must be empty)."""
    from PIL import Image, ImageDraw
    bad = []
    for c in layout['cells']:
        zs = c['id_corner_px'][2]
        f = fit_font(str(c['id']), zs)
        if f is None:
            bad.append(f"{c['id']} {c['key']}")
            continue
        im = Image.new('RGB', (zs * 3, zs * 3), (255, 255, 255))
        d = ImageDraw.Draw(im)
        draw_id(d, (zs * 2, zs * 2, zs * 3 - 1, zs * 3 - 1), str(c['id']), f)
        bb = Image.eval(im.convert('L'), lambda v: 255 - v).getbbox()
        if bb and (bb[0] < zs * 2 or bb[1] < zs * 2):
            bad.append(f"{c['id']} {c['key']}")
    return bad


def build(args) -> dict:
    ids = _load(args.ids)
    spec = _load(args.spec)
    if spec.get('version') != ids.get('version'):
        raise InputError(f"spec version {spec.get('version')} != ids version {ids.get('version')}")
    tiles = load_tiles(ids, args.tiles_dir)
    base = plan_library(ids, spec)
    profiles = {}
    for name, pr in spec['library']['profiles'].items():
        profiles[name] = dict(scale_layout(base, pr['size']), file=pr['file'], udim=pr.get('udim'))
    sites = {}
    given = dict(s.split('=', 1) for s in (args.site_set or []))
    for name, site in (spec.get('site_sets') or {}).items():
        if name not in given:
            continue
        positions = _load(given[name])['positions']
        lay = plan_site(ids, site, positions, tiles)
        proof = [r for r in lay['positions'] if r['set_id'] in site.get('proof_positions', [])]
        missing = sorted(set(site.get('proof_positions', [])) - {r['set_id'] for r in proof})
        if missing:
            raise InputError(f'site {name}: proof positions not in the set: {missing}')
        cell = {c['key']: c for c in lay['cells']}
        for r in proof:
            r['uv_safe'] = _uv(cell[r['key']]['content_px'], lay['size'])
            r['id_corner_uv'] = _uv(cell[r['key']]['id_corner_px'], lay['size'])
        lay.update(file=site['file'], proof=proof, source={'path': given[name], 'sha256': sha256_file(given[name])})
        sites[name] = lay
    unknown = sorted(set(given) - set(spec.get('site_sets') or {}))
    if unknown:
        raise InputError(f'--site-set names not in the spec: {unknown}')
    bad = [n + ': ' + ', '.join(b) for n, lay in [*profiles.items(), *sites.items()] if (b := corner_fits(lay))]
    if bad:
        raise InputError(f'ID number does not fit its corner: {bad}')
    return {'schema': 'library-maf-atlas-layout', 'version': ids['version'], 'status': 'proposed',
            'generated_by': 'tools/library/maf_atlas_layout.py',
            'inputs': {'ids': {'path': args.ids, 'sha256': sha256_file(args.ids)},
                       'spec': {'path': args.spec, 'sha256': sha256_file(args.spec)}},
            'rule_id_corner': 'ID number small in the bottom-right corner of every cell (id_corner_px); UV '
                              'islands stay inside content_px and outside id_corner_px (Artem 2026-10-21)',
            'profiles': profiles, 'site_sets': sites, '_tiles': tiles}


def render_md(r: dict) -> str:
    L = [f"# MAF atlas layouts {r['version']} - proposal (#524)", '',
         f"Status: **{r['status']}** (Artem approves the ID list and the layouts once [D168]; nothing in the "
         f"library is reassigned before that). Generated by `{r['generated_by']}` from `{r['inputs']['ids']['path']}` "
         f"and `{r['inputs']['spec']['path']}`; machine-readable twin `atlas_layout_{r['version']}.json`. "
         'PNGs are evidence on Drive (rule 57), not committed.', '',
         f"Rule: {r['rule_id_corner']}.", '', '## Profiles', '',
         '| profile | file | px | padding px | cells | slot px L / M / S | decal reserve px | free share |',
         '|---|---|---|---|---|---|---|---|']
    for name, p in [*r['profiles'].items(), *r['site_sets'].items()]:
        sides = {}
        for c in p['cells']:
            sides.setdefault(c.get('size_class') or c.get('kind'), set()).add(c['slot_px'][2])
        ss = ' / '.join(','.join(map(str, sorted(sides.get(k, [])))) or '-' for k in ('L', 'M', 'S')) \
            if 'size_class' in p['cells'][0] else '; '.join(f"{k} {sorted(v)}" for k, v in sides.items())
        L.append(f"| {name} | `{p['file']}` | {p['size']} | {p['padding_px']} | {len(p['cells'])} | {ss} | "
                 f"{p.get('decal_reserve_px', '-')} | {p.get('free_share', '-')} |")
    v = next(iter(r['profiles'].values()))
    L += ['', f"## Cells ({v['size']} px; other library profiles are the same layout scaled)", '',
          '| ID | key | class | slot x,y,side | content x,y,w,h | ID corner x,y,side |', '|---|---|---|---|---|---|']
    L += [f"| {c['id']} | `{c['key']}` | {c['size_class']} | {c['slot_px'][:3]} | {c['content_px']} | "
          f"{c['id_corner_px'][:3]} |" for c in sorted(v['cells'], key=lambda c: c['id'])]
    if v.get('excluded'):
        L += ['', 'Not in the atlas: ' + '; '.join(f"{e['id']} `{e['key']}` ({e['reason']})" for e in v['excluded'])]
    for name, s in r['site_sets'].items():
        L += ['', f"## Site set `{name}` ({s['size']} px, only the IDs the site uses)", '',
              '| ID | key | kind | slot | content |', '|---|---|---|---|---|']
        L += [f"| {c['id']} | `{c['key']}` | {c['kind']} | {c['slot_px']} | {c['content_px']} |" for c in s['cells']]
        L += ['', '### Proof: library MAF material -> ID -> cell (dry run, no UV moved)', '',
              '| position | MAF | slot | site material | ID | UV safe rect (u0,v0,u1,v1) | keep-out corner UV |',
              '|---|---|---|---|---|---|---|']
        L += [f"| {p['set_id']} | {p['catalogue_id']} | {p['slot']} | {p['material']} | {p['id']} `{p['key']}` | "
              f"{p['uv_safe']} | {p['id_corner_uv']} |" for p in s['proof']]
    L += ['', '## Procedure: library MAF -> IDs -> atlas', '',
          '1. Read the MAF material slots (`library/maf/fbx_materials.json`, or the site set `material_map`).',
          '2. Map every slot to one v005 ID (`material_ids_v005.json`: `library` / `spec` patterns, merges). '
          'An unmapped slot is an error naming it - never a default; a new ID needs Artem.',
          '3. Pick the layout: VPM = the 4K UDIM tile, NPM = the same layout at 2K (GroundEl naming), a site '
          'set = 512 px built from only the IDs the site uses (`maf_atlas_layout.py --site-set`).',
          "4. Lay the UV islands of each slot inside its ID cell's `content_px` (UV safe rect), scaled to fit; "
          'flat cells may take islands of any scale; keep the bottom-right `id_corner_px` free.',
          '5. Read back: every face inside its cell, none overlapping a corner (`maf_atlas_ids.py '
          '--require-keepout`: polygon/`id_corner_px` overlap, exit 1 names the cells; a failed or incomplete '
          'UV dump exits 2), then the regular MAF checks (`validate-delivery`).', '']
    return '\n'.join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    for a in ('ids', 'spec', 'tiles-dir', 'out-json'):
        ap.add_argument('--' + a, required=True)
    ap.add_argument('--site-set', action='append', help='name=path of a site-maf-set.json')
    ap.add_argument('--out-md')
    ap.add_argument('--evidence-dir')
    args = ap.parse_args(argv)
    inputs = [args.ids, args.spec] + [s.split('=', 1)[-1] for s in (args.site_set or [])]
    try:
        check_paths(inputs, [args.out_json] + ([args.out_md] if args.out_md else []))
        if args.evidence_dir and os.path.normcase(os.path.realpath(args.evidence_dir)) == \
                os.path.normcase(os.path.realpath(args.tiles_dir)):
            raise InputError('evidence dir is the tiles dir')
        r = build(args)
        layouts = [*r['profiles'].values(), *r['site_sets'].values()]
        for lay in layouts:
            f = lay['file']
            if not isinstance(f, str) or not f or f != os.path.basename(f) or f in ('.', '..') or '/' in f:
                raise InputError(f'layout file name must be a plain file name, got {f!r}')
        # preflight every actual target (JSON, MD, each layout PNG) against every actual source (ids, spec,
        # site sets, tiles) and against each other, before anything is written
        pngs = [os.path.join(args.evidence_dir, lay['file']) for lay in layouts] if args.evidence_dir else []
        check_paths(inputs + list(r['_tiles'].values()),
                    [args.out_json] + ([args.out_md] if args.out_md else []) + pngs)
        for lay, p in zip(layouts, pngs):
            lay['png'] = render(lay, r['_tiles'], p)
    except (InputError, OSError, KeyError, json.JSONDecodeError) as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 2
    for lay in r['site_sets'].values():
        lay.pop('_materials', None)
        lay.pop('_slots', None)
    r.pop('_tiles')
    outs = [(args.out_json, json.dumps(r, ensure_ascii=False, indent=1) + '\n')]
    if args.out_md:
        outs.append((args.out_md, render_md(r)))
    for path, text in outs:
        write_atomic(path, text.encode('utf-8'))
    print('; '.join(f"{n}: {len(v['cells'])} cells {v['size']}px" for n, v in
                    [*r['profiles'].items(), *r['site_sets'].items()]))
    return 0


if __name__ == '__main__':
    sys.exit(main())
