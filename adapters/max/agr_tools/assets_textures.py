"""new-case: textures of placed library assets (#1024): VPM UDIM tiles and the NPM atlas route.

Owner's rules (Artem 06.11.2026):
* NPM: after placement one button builds one atlas per kind — Flora (D + O) and MAF (D). Solid colours get a tiny
  cell, textured materials (wood, tiles, ...) get room by texel density. That is the existing atlas_core.pack
  (plug cells 16 px for flat Kd, textured cells at the target texel; atlas.flora writes the separate opacity
  plane), so NPM here only routes the asset objects to it.
* VPM: the script knows which UDIMs are taken, takes the next free ones, names the maps by the VPM grammar
  (names_core.texture_stem: T_<Address>_<Diffuse|ERM|Normal>_<Slot>.<UDIM>) and writes them into the project
  folder. Few texture sets (<= `tile_limit`, default 5 as in the owner's example) -> one UDIM per set, the set's
  layout kept and moved by a whole tile. More sets -> 4K tiles packed at one texel density (cut by the UV bounds of
  each set, the FloraAtlas.ms idea, GeoAGR-private sha256 0160f807…1093, nothing copied). Flora keeps its alpha
  in the Diffuse (VPM has no opacity map); its missing ERM/Normal become flat placeholders.

Pure stdlib; the Max side is assets_max.vpm_udims. A101 assets carry their own texture set per asset (measured),
so they need no cutting from a shared atlas; shared-atlas libraries (legacy Union, FLORA_Union) go through the
packed route.
"""
import math
import re

MAX_UDIM = 1100
TILE_PX = 4096
PAD_PX = 16
FLAT = {'erm': (0, 200, 0), 'normal': (128, 128, 255)}  # E=0, roughness 0.78, metal 0; flat tangent normal
_ROLE_TAILS = (('diffuse', r'(_diffuse|_d|_basecolor|_albedo)'), ('normal', r'(_normal|_n)'),
               ('erm', r'(_erm|_m|_r|_e)'), ('opacity', r'(_opacity|_o)'))


def role_of(path):
    """Map role from the file name: A101 MAF `_Diffuse/_ERM/_Normal` (high) and `_d/_n/_m/_r/_o` (low); a Flora
    file `<base>_high.png` / `_low.png` without a role tail is the RGBA diffuse."""
    stem = re.sub(r'\.[^.]+$', '', str(path).replace('\\', '/').rsplit('/', 1)[-1]).lower()
    for role, tail in _ROLE_TAILS:
        if re.search(tail + r'$', stem):
            return role
    return 'diffuse'


def tile_uv(udim):
    """UDIM 1001 + u + 10 v -> (u, v)."""
    if not 1001 <= udim <= MAX_UDIM:
        raise ValueError('UDIM must be 1001..1100: ' + repr(udim))
    n = udim - 1001
    return n % 10, n // 10


def used_tiles(files, address, udim_of):
    """{slot: set(udim)} of VPM maps of this address among file names (udim_of = names_core.udim_of)."""
    pat = re.compile(r'^T_' + re.escape(address) + r'(?:_Ground)?_(?:Diffuse|ERM|Normal)_(?P<slot>[1-7])[._]',
                     re.IGNORECASE)
    out = {}
    for f in files:
        base = str(f).replace('\\', '/').rsplit('/', 1)[-1]
        m = pat.match(base)
        u = udim_of(base)
        if m and u:
            out.setdefault(int(m.group('slot')), set()).add(u)
    return out


def allocate(used, count, slot=1, max_slots=7):
    """`count` free tiles that keep every slot contiguous (udim.slots `udim_gap`): after the highest used tile of
    `slot`; past 1100 the next slots, each starting after its own highest tile. Returns [(slot, udim)]."""
    out = []
    s = slot
    while len(out) < count:
        if s > max_slots:
            raise ValueError('no free UDIM: slots {}..{} full ({} more tiles needed)'.format(
                slot, max_slots, count - len(out)))
        nxt = max(used.get(s, set()) | {1000}) + 1
        while nxt <= MAX_UDIM and len(out) < count:
            out.append((s, nxt))
            nxt += 1
        s += 1
    return out


def texture_sets(rows):
    """rows: [{'asset', 'version', 'material', 'maps': [paths], 'uv_bbox': [[u0, v0], [u1, v1]],
    'area3d_m2', 'tex_px': [w, h]}] -> unique sets by material (instances share one), roles resolved."""
    sets = {}
    for r in rows:
        key = r['material']
        s = sets.setdefault(key, {'material': key, 'assets': [], 'maps': {}, 'uv_bbox': r.get('uv_bbox'),
                                  'area3d_m2': 0.0, 'tex_px': r.get('tex_px')})
        if r['asset'] not in s['assets']:
            s['assets'].append(r['asset'])
            s['area3d_m2'] += float(r.get('area3d_m2') or 0.0)
        for p in r['maps']:
            role = role_of(p)
            if role == 'opacity' and 'diffuse' in s['maps']:
                continue
            s['maps'].setdefault(role, p)
    return [sets[k] for k in sorted(sets)]


def _inside_unit(bb, eps=1e-4):
    return bb is not None and bb[0][0] >= -eps and bb[0][1] >= -eps and bb[1][0] <= 1 + eps and bb[1][1] <= 1 + eps


def vpm_plan(sets, used, address, texture_stem, kind, slot=1, tile_limit=5, obj_type='Main', texel=None):
    """Plan of the VPM textures of one kind ('flora' / 'maf').

    tile_per_set: one free UDIM per set, UVs moved by the whole tile (the set's UVs must lie in 0..1), maps copied
    under the VPM names, missing ERM/Normal as flat placeholders. packed_4k: sets cut by their UV bounds and laid
    on 4096 px tiles at one texel density (`texel` px/m, default the lowest source texel so nothing is upscaled);
    the pixel step of this route is planned, not executed (report says so)."""
    obj = {'address': address, 'oks': None, 'type': obj_type}
    if not sets:
        return {'kind': kind, 'mode': 'empty', 'rows': [], 'tiles': []}
    if len(sets) <= tile_limit:
        tiles = allocate(used, len(sets), slot)
        rows = []
        for s, (sl, udim) in zip(sets, tiles):
            row = {'material': s['material'], 'assets': s['assets'], 'slot': sl, 'udim': udim,
                   'uv_offset': list(tile_uv(udim)), 'copy': [], 'placeholders': [], 'findings': []}
            if not _inside_unit(s.get('uv_bbox')):
                row['findings'].append('uv_outside_0_1')
            if 'diffuse' not in s['maps']:
                row['findings'].append('no_diffuse')
            for role, vrole in (('diffuse', 'diffuse'), ('erm', 'metalness'), ('normal', 'normal')):
                stem = texture_stem(obj, 'vpm', vrole, sl, udim)
                if role in s['maps']:
                    row['copy'].append({'role': role, 'src': s['maps'][role], 'stem': stem})
                else:
                    row['placeholders'].append({'role': role, 'stem': stem, 'rgb': list(FLAT[role])})
            rows.append(row)
        return {'kind': kind, 'mode': 'tile_per_set', 'rows': rows, 'tiles': tiles,
                'blocking': sorted({f for r in rows for f in r['findings']})}
    return packed_plan(sets, used, kind, slot, texel)


def packed_plan(sets, used, kind, slot=1, texel=None, tile_px=TILE_PX, pad=PAD_PX):
    """Cells = UV bounds of each set at one texel density; shelf-packed into tile_px tiles (largest first)."""
    cells = []
    for s in sets:
        bb, px = s.get('uv_bbox'), s.get('tex_px')
        if not bb or not px or not s.get('area3d_m2'):
            raise ValueError('set {!r}: uv_bbox, tex_px and area3d_m2 are needed for packing'.format(s['material']))
        cells.append(dict(material=s['material'], src_w=(bb[1][0] - bb[0][0]) * px[0],
                          src_h=(bb[1][1] - bb[0][1]) * px[1],
                          src_texel=math.sqrt((bb[1][0] - bb[0][0]) * (bb[1][1] - bb[0][1]) * px[0] * px[1] /
                                              s['area3d_m2'])))
    target = texel or min(c['src_texel'] for c in cells)
    for c in cells:
        k = target / c['src_texel']
        c['w'], c['h'] = max(1, int(math.ceil(c['src_w'] * k))), max(1, int(math.ceil(c['src_h'] * k)))
        if c['w'] + 2 * pad > tile_px or c['h'] + 2 * pad > tile_px:
            raise ValueError('set {!r} does not fit one {} px tile at {:.1f} px/m'.format(c['material'], tile_px,
                                                                                         target))
    tiles, shelves = [], []  # shelves: [tile index, y, height, x]
    for c in sorted(cells, key=lambda c: (-c['h'], -c['w'], c['material'])):
        w, h = c['w'] + 2 * pad, c['h'] + 2 * pad
        for sh in shelves:
            if sh[3] + w <= tile_px and h <= sh[2]:
                c['tile'], c['x'], c['y'] = sh[0], sh[3] + pad, sh[1] + pad
                sh[3] += w
                break
        else:
            t = len(tiles) - 1
            top = max([sh[1] + sh[2] for sh in shelves if sh[0] == t], default=None) if tiles else None
            if top is None or top + h > tile_px:
                tiles.append(len(tiles))
                t, top = len(tiles) - 1, 0
            shelves.append([t, top, h, w])
            c['tile'], c['x'], c['y'] = t, pad, top + pad
    alloc = allocate(used, len(tiles), slot)
    for c in cells:
        c['slot'], c['udim'] = alloc[c['tile']]
    fill = sum(c['w'] * c['h'] for c in cells) / float(len(tiles) * tile_px * tile_px)
    return {'kind': kind, 'mode': 'packed_4k', 'texel_px_per_m': round(target, 2), 'tiles': alloc,
            'fill': round(fill, 3), 'rows': sorted(cells, key=lambda c: c['material']),
            'blocking': [], 'note': 'pixel cut/resample of the packed route is the next step'}


def npm_route(objects):
    """objects: [{'name', 'kind', 'version'}] -> which existing atlas button takes which low objects."""
    flora = sorted(o['name'] for o in objects if o['kind'] == 'flora' and o['version'] == 'low')
    maf = sorted(o['name'] for o in objects if o['kind'] == 'maf' and o['version'] == 'low')
    return {'atlas.flora': flora, 'atlas.npm': maf}
