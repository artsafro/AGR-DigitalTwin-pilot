"""new-case: AGR Tools 0.5.0 read-only diagnostics (names, triangle limits per FBX, textures, pivot, GeoJSON).

Stdlib only, no pymxs: the Max glue (checks_max.py) reads the scene and passes plain rows here.
Base: GeoAGR 13.64 (author Artem), recovered GeoAGR.ms (GeoAGR-private@31c723e); every adapted
function names its source line and its changes. Only the logic used is adapted, not GeoAGR.ms.
Thresholds are the locked standards (standards/NPM_STANDARD.yaml, VPM_STANDARD.yaml); a test pins
them to the YAML so they cannot drift.
"""
import json
import math
import re
import struct

# --- thresholds (pinned to standards/*.yaml by tests/max_tools/test_agr_tools_checks.py) -------------
NAME_MAX = 254                                   # NPM/VPM naming.max_characters
NPM_OKS_TRI_MAX = 150000                         # NPM geometry.oks_triangles_per_fbx_max
NPM_GROUND_TRI_MAX = 180000                      # NPM geometry.ground_triangles_total_max
VPM_OKS_TRI_MAX = 1000000                        # VPM geometry.oks_triangles_per_fbx_max_excluding_collision
VPM_GROUND_TRI_BY_AREA = ((0.05, 300000), (0.1, 705000), (0.25, 1125000), (0.5, 1650000),
                          (0.75, 1950000), (1.0, 2625000), (1.5, 3150000), (None, 4500000))
NPM_TEX_SIZES = (256, 512, 1024, 2048)           # NPM textures.allowed_square_sizes_px
NPM_TEX_PLACEHOLDER = 128                        # conflict #5 decided: 128x128 m/r placeholders
NPM_GROUND_EL_MAX = 512                          # NPM textures.ground_elements_set_size_px_max
NPM_FLORA_MAX = 2048                             # NPM textures.vegetation_set_size_px_max
NPM_TEX_BYTES_MAX = 3145728                      # NPM textures.max_file_bytes
NPM_PADDING_PX = 8                               # NPM textures.island_padding_px_min
VPM_TEX_SIZES = (2048, 4096)                     # VPM textures.allowed_square_sizes_px
VPM_TEX_PLACEHOLDER = 256                        # VPM textures.flat_placeholder.size_px
VPM_PADDING_PX = {2048: 16, 4096: 32}            # VPM textures.padding_px_min
VPM_BITS = 8                                     # VPM textures.bits_per_channel
PIVOT_TOL_M = 0.001                              # conflict #19 decided: meshes share the origin within 1 mm
PADDING_PAIR_BUDGET = 2000000                    # edge pairs per object before `tex_unmeasurable`

NPM_TYPES = ('Main', 'MainGlass', 'Ground', 'GroundGlass', 'GroundEl', 'GroundElGlass', 'Flora')
VPM_TYPES = ('Main', 'MainGlass', 'Ground', 'GroundGlass')
FBX_TYPES = {('npm', 'oks'): ('Main', 'MainGlass'),
             ('npm', 'ground'): ('Ground', 'GroundGlass', 'GroundEl', 'GroundElGlass', 'Flora'),
             ('vpm', 'oks'): ('Main', 'MainGlass'), ('vpm', 'ground'): ('Ground', 'GroundGlass')}
NPM_MAPS = ('d', 'n', 'o', 'm', 'r')
VPM_MAPS = ('Diffuse', 'ERM', 'Normal')
SLOTS = ('1', '2', '3', '4', '5', '6', '7')
OKS_NUMBER = re.compile(r'(?:00[1-9]|01[0-9]|020)')
UCX_INDEX = re.compile(r'(?:00[1-9]|0[1-9][0-9]|[1-9][0-9]{2})')
NAME_CHARS = re.compile(r'[A-Za-z0-9_]+')

CODES = {
    'names': {'name_empty', 'name_length', 'name_symbols', 'name_separator', 'name_prefix', 'name_suffix',
              'name_type', 'name_case', 'name_digits', 'name_conflict', 'fbx_unmapped'},
    'tris': {'tri_limit', 'tri_at_limit', 'tri_unmeasurable', 'ucx_tri_limit', 'fbx_unmapped'},
    'textures': {'tex_missing', 'tex_unreadable', 'tex_format', 'tex_size', 'tex_alpha', 'tex_bit_depth',
                 'tex_file_size', 'tex_udim', 'tex_set', 'tex_padding', 'tex_overlap_review', 'tex_matid_wrapped',
                 'tex_unmeasurable', 'at_threshold', 'fbx_unmapped'},
    'pivot': {'pivot_z', 'pivot_mismatch', 'pivot_reference_ambiguous', 'pivot_unmeasurable', 'at_threshold',
              'fbx_unmapped'},
    'geojson': set(),
}
FBX_ROW = {'fbx', 'model', 'role', 'objects', 'render_triangles', 'ucx_triangles', 'limit', 'ucx_limit'}


# --- FBX model kind ---------------------------------------------------------------------------------
def fbx_kind(path):
    """(model, role) from the FBX file stem, as twinqa.naming.address_from_fbx; None when unmapped.
    NPM: NNNN_{Address}_NN | NNNN_{Address}_Ground; VPM: SM_{Address} | SM_{Address}_Ground."""
    if not isinstance(path, str) or not path.strip():
        return None
    stem = re.split(r'[\\/]', path.strip())[-1]
    if not stem.lower().endswith('.fbx'):
        return None
    stem = stem[:-4]
    if re.fullmatch(r'SM_[A-Za-z0-9_]+?_Ground', stem):
        return ('vpm', 'ground')
    if re.fullmatch(r'SM_[A-Za-z0-9_]+', stem):
        return ('vpm', 'oks')
    if re.fullmatch(r'[0-9]{4}_[A-Za-z0-9_]+?_Ground', stem):
        return ('npm', 'ground')
    if re.fullmatch(r'[0-9]{4}_[A-Za-z0-9_]+?_(?:0[1-9]|1[0-9]|20)', stem):
        return ('npm', 'oks')
    return None


def is_ucx(name):
    return isinstance(name, str) and name.upper().startswith('UCX_')


def mesh_kind(name):
    """Geometry suffix of a mesh by EXACT last token.

    adapted from GeoAGR 13.64 (author Artem), GeoAGR.ms:65326 (btn_check_npm `case of findstring`) and
    GeoAGR.ms:65740 (btn_check_vpm), changes: exact token instead of a substring `case`, so MainGlass is
    never taken for Main and UCX_*_Ground never for Ground (defect D2); UCX is tested first.
    """
    if not isinstance(name, str) or not name:
        return None
    if is_ucx(name):
        return 'UCX'
    last = name.split('_')[-1]
    return last if last in NPM_TYPES else None


# --- names ------------------------------------------------------------------------------------------
def _symbols(text, allow_udim_dot=False):
    """adapted from GeoAGR 13.64 (author Artem), GeoAGR.ms:4089 (parse_error_symbols) and :7056-7057
    (translit, space), changes: one regex; the dot of `{SlotNumber}.{UDIM}` is legal only in VPM textures."""
    body = text
    if allow_udim_dot and body.count('.') == 1:
        body = body.replace('.', '_')
    if NAME_CHARS.fullmatch(body):
        return None
    bad = sorted(set(c for c in body if not re.fullmatch(r'[A-Za-z0-9_]', c)))
    if '.' in bad:
        return 'dot "." is not allowed'
    if ' ' in bad:
        return 'space is not allowed'
    if any(ord(c) > 127 for c in bad):
        return 'non-Latin characters (transliterate): ' + ''.join(bad)
    return 'characters other than A-Z a-z 0-9 _: ' + ''.join(bad)


def _address_tokens(tokens):
    """adapted from GeoAGR 13.64 (author Artem), GeoAGR.ms:7217-7251 (capital letter, digits apart),
    changes: structural tokens are removed by exact match before the checks; the abbreviation/street
    dictionaries (abbr3/abbr4/ul4/ul5.csv) are not shipped and are not checked."""
    out = []
    for tok in tokens:
        if not tok:
            continue
        if tok[0].isalpha() and not tok[0].isupper():
            out.append(('name_case', 'each word starts with a capital letter: ' + tok))
        letters = re.sub(r'[0-9]', '', tok)
        if letters and letters != tok:
            out.append(('name_digits', 'digits are separated from letters by "_": ' + tok))
    return out


def name_findings(name, role, model, fbx_role=None):
    """Findings [(code, detail)] for one object (SM), material (M) or texture file (T) name.

    adapted from GeoAGR 13.64 (author Artem), GeoAGR.ms:6907 (check_names_all, NPM) and GeoAGR.ms:7331
    (check_names_all_vpm, VPM), changes: SlotNumber 1..7 instead of exactly "1" (defect D4); exact
    tokens for Main/MainGlass/Ground/GroundEl/UCX instead of substrings (D2); NPM OKS number 001..020
    (NPM_STANDARD oks_001_to_020, as twinqa.naming) instead of 001..100; the geometry suffix of an
    object is bound to its FBX role (oks: Main/MainGlass, ground: Ground...; as twinqa.naming);
    VPM textures follow T_{Address}[_Ground]_{Diffuse|ERM|Normal}_{SlotNumber}.{UDIM}; NPM
    M_Glass_01..07 is reported as conflict #17 instead of silently exempted; "Ul"/"Ulitsa" substring
    tests dropped (they flag Ulyanovskaya); address dictionaries not checked.
    """
    if role not in ('SM', 'M', 'T') or model not in ('npm', 'vpm') or fbx_role not in (None, 'oks', 'ground'):
        raise ValueError(f'unsupported name role/model: {role}/{model}/{fbx_role}')
    if not isinstance(name, str) or not name.strip():
        return [('name_empty', f'no {dict(SM="object", M="material", T="texture")[role]} name')]
    out = []
    if len(name) > NAME_MAX:
        out.append(('name_length', f'{len(name)} characters > {NAME_MAX}'))
    stem = name
    if role == 'T':
        stem = re.split(r'[\\/]', stem)[-1]
        if stem.lower().endswith('.png'):
            stem = stem[:-4]
    vpm_tex = role == 'T' and model == 'vpm'
    bad = _symbols(stem, allow_udim_dot=vpm_tex)
    if bad:
        out.append(('name_symbols', bad))
    if '_' not in stem:
        out.append(('name_separator', 'no "_" separator'))
        return out
    tt = stem.split('_')
    if any(t == '' for t in tt):
        out.append(('name_separator', 'empty element between "_"'))
        return out
    ucx = role == 'SM' and tt[0] == 'UCX'
    prefix = {'SM': 'SM', 'M': 'M', 'T': 'T'}[role]
    if ucx:
        if model == 'npm':
            out.append(('name_prefix', 'UCX is not specified for NPM'))
            return out
        if len(tt) < 4 or tt[1] != 'SM':
            out.append(('name_prefix', 'collision must be UCX_SM_...'))
            return out
        if tt[-2] not in ('Main', 'Ground') or not UCX_INDEX.fullmatch(tt[-1]):
            out.append(('name_type', 'UCX_SM_{Address}_Main|Ground_001..999'))
        elif fbx_role and tt[-2] != ('Ground' if fbx_role == 'ground' else 'Main'):
            out.append(('name_type', f'UCX in a {fbx_role} FBX must be UCX_SM_..._{"Ground" if fbx_role == "ground" else "Main"}_NNN'))
        return out + _address_tokens(tt[2:-2])
    if tt[0] != prefix:
        out.append(('name_prefix', f'first element must be "{prefix}"'))
        return out
    types = NPM_TYPES if model == 'npm' else VPM_TYPES
    if role == 'SM' and fbx_role:
        types = FBX_TYPES[(model, fbx_role)]
    if role == 'SM':
        if tt[-1] == '1':
            out.append(('name_suffix', 'an object name cannot end with "_1"'))
        if len(tt) > 2 and tt[-2] in NPM_MAPS:
            out.append(('name_suffix', 'map suffix _d_/_n_/_o_/_m_/_r_ is for textures, not objects'))
        type_at, tail = len(tt) - 1, 1
    elif role == 'M':
        if model == 'npm' and len(tt) == 3 and tt[1] == 'Glass':
            ok = re.fullmatch(r'0[1-7]', tt[2]) is not None
            return out + [('name_conflict', 'M_Glass_01..07 is not in the regulation (conflict #17, review)'
                           + ('' if ok else '; and not 01..07'))]
        if tt[-1] not in SLOTS:
            out.append(('name_suffix', 'last element must be SlotNumber 1..7: ' + tt[-1]))
        if len(tt) > 2 and tt[-2] in NPM_MAPS:
            out.append(('name_suffix', 'map suffix _d_/_n_/_o_/_m_/_r_ is for textures, not materials'))
        type_at, tail = len(tt) - 2, 2
    elif model == 'npm':
        if tt[-1] not in SLOTS:
            out.append(('name_suffix', 'last element must be SlotNumber 1..7: ' + tt[-1]))
        if len(tt) < 3 or tt[-2] not in NPM_MAPS:
            out.append(('name_suffix', 'map element must be d, n, o, m or r'))
        type_at, tail = len(tt) - 3, 3
    else:
        last = tt[-1].split('.')
        if len(last) != 2 or last[0] not in SLOTS:
            out.append(('name_suffix', 'last element must be {SlotNumber 1..7}.{UDIM}: ' + tt[-1]))
        elif not re.fullmatch(r'1(?:0[0-9][1-9]|0[1-9]0|100)', last[1]):
            out.append(('name_suffix', 'UDIM must be 1001..1100: ' + last[1]))
        if len(tt) < 3 or tt[-2] not in VPM_MAPS:
            out.append(('name_suffix', 'map element must be Diffuse, ERM or Normal'))
        address = tt[1:-2]
        if address and address[-1] == 'Ground':
            address = address[:-1]
        if not address:
            out.append(('name_type', 'no Address element'))
        return out + _address_tokens(address)
    if type_at < 1 or tt[type_at] not in types:
        out.append(('name_type', 'geometry element must be one of ' + ', '.join(types)))
        return out + _address_tokens(tt[1:max(type_at, 1)])
    address_end = type_at
    if model == 'npm' and tt[type_at] in ('Main', 'MainGlass'):
        if type_at < 2 or not OKS_NUMBER.fullmatch(tt[type_at - 1]):
            out.append(('name_type', 'OKS number 001..020 must precede ' + tt[type_at]))
        else:
            address_end = type_at - 1
    if address_end <= 1:
        out.append(('name_type', 'no Address element'))
    del tail
    return out + _address_tokens(tt[1:address_end])


def names_scene(rows):
    """rows: [{'key', 'name', 'fbx', 'materials': [names], 'maps': [file paths]}] -> findings by key.
    Every object, its (sub-)materials and every map file name are checked (GeoAGR passed the three
    lists separately, GeoAGR.ms:65278 btn_check_npm -> check_names_all "SM"/"M"/"T")."""
    found = {}
    for r in rows:
        f = found.setdefault(r['key'], [])
        kind = fbx_kind(r.get('fbx'))
        if kind is None:
            f.append(('fbx_unmapped', f'AGR_EXPORT_PATH {r.get("fbx")!r} is not an NPM/VPM FBX name'))
            continue
        model, fbx_role = kind
        f.extend((c, f'object {r["name"]}: {d}') for c, d in name_findings(r['name'], 'SM', model, fbx_role))
        if is_ucx(r['name']):
            continue
        for m in r.get('materials', []):
            f.extend((c, f'material {m}: {d}') for c, d in name_findings(m, 'M', model))
        for path in r.get('maps', []):
            stem = re.split(r'[\\/]', path)[-1]
            f.extend((c, f'texture {stem}: {d}') for c, d in name_findings(stem, 'T', model))
    return found


# --- triangle limits per FBX -------------------------------------------------------------------------
def vpm_ground_limit(area_ha):
    """VPM Ground triangle limit from the site-area table (territory minus footprint, ha)."""
    if isinstance(area_ha, bool) or not isinstance(area_ha, (int, float)) or not math.isfinite(area_ha) or area_ha <= 0:
        return None
    for top, limit in VPM_GROUND_TRI_BY_AREA:
        if top is None or area_ha <= top:
            return limit
    return None


def vpm_ucx_limit(render):
    """VPM collision.triangle_limit (conflict #3 decided, SINTEZ AGR Checker formula)."""
    return 15000 if render < 50000 else min(math.ceil(render * 0.05), 100000)


def triangle_limits(rows):
    """Per-FBX triangle budgets. rows: [{'key', 'name', 'fbx', 'triangles', 'site_area_ha'}].

    adapted from GeoAGR 13.64 (author Artem), GeoAGR.ms:65601-65625 (btn_check_npm) and :65970-65992
    (btn_check_vpm), changes: summed per exported FBX (AGR_EXPORT_PATH) and per model kind instead of
    over the whole selection (defect D8); NPM OKS FBX <= 150 000, NPM Ground FBX <= 180 000 (Ground,
    GroundEl and Flora, separately from Main); VPM OKS <= 1 000 000 without UCX instead of the stale
    2 000 000; VPM Ground by the site-area table; UCX budget by the decided formula; triangles are
    counted on a read-only TriMesh snapshot (no copy/convert/ConnectVertices); a count equal to the
    limit is `tri_at_limit` (no silent pass at the boundary).
    Returns (findings by key, fbx rows).
    """
    found = {r['key']: [] for r in rows}
    groups = {}
    for r in rows:
        tri = r.get('triangles')
        if isinstance(tri, bool) or not isinstance(tri, int) or tri < 0:
            found[r['key']].append(('tri_unmeasurable', f'triangle count {tri!r}'))
            continue
        kind = fbx_kind(r.get('fbx'))
        if kind is None:
            found[r['key']].append(('fbx_unmapped', f'AGR_EXPORT_PATH {r.get("fbx")!r} is not an NPM/VPM FBX name'))
            continue
        groups.setdefault(r['fbx'], []).append(r)
    table = []
    for fbx, members in sorted(groups.items()):
        model, role = fbx_kind(fbx)
        render = sum(r['triangles'] for r in members if not is_ucx(r['name']))
        ucx = sum(r['triangles'] for r in members if is_ucx(r['name']))
        limit = ucx_limit = None
        detail = None
        if model == 'npm':
            limit = NPM_OKS_TRI_MAX if role == 'oks' else NPM_GROUND_TRI_MAX
        elif role == 'oks':
            limit = VPM_OKS_TRI_MAX
        else:
            areas = {r.get('site_area_ha') for r in members}
            area = areas.pop() if len(areas) == 1 else None
            limit = vpm_ground_limit(area)
            if limit is None:
                detail = f'unmapped key AGR_SITE_AREA_HA (one positive value per Ground FBX), got {sorted(map(repr, areas | {area}))}'
        if model == 'vpm':
            ucx_limit = vpm_ucx_limit(render)
        table.append({'fbx': fbx, 'model': model, 'role': role, 'objects': len(members),
                      'render_triangles': render, 'ucx_triangles': ucx, 'limit': limit, 'ucx_limit': ucx_limit})
        for r in members:
            f = found[r['key']]
            if is_ucx(r['name']):
                if ucx_limit is not None and ucx > ucx_limit:
                    f.append(('ucx_tri_limit', f'{fbx}: UCX {ucx} > {ucx_limit}'))
                elif ucx_limit is not None and ucx == ucx_limit:
                    f.append(('tri_at_limit', f'{fbx}: UCX {ucx} == {ucx_limit}'))
                continue
            if detail:
                f.append(('tri_unmeasurable', f'{fbx}: {detail}'))
            elif render > limit:
                f.append(('tri_limit', f'{fbx}: {render} > {limit} ({model} {role}, per FBX)'))
            elif render == limit:
                f.append(('tri_at_limit', f'{fbx}: {render} == {limit} ({model} {role}); at the limit'))
    return found, table


# --- textures -----------------------------------------------------------------------------------------
def png_info(data):
    """(width, height, bit_depth, color_type, has_alpha) from PNG bytes; ValueError when not a PNG.
    Replaces GeoAGR's openBitmap/.hasAlpha and ImageMagick `identify` (GeoAGR.ms:65857-65885)."""
    if not isinstance(data, (bytes, bytearray)) or data[:8] != b'\x89PNG\r\n\x1a\n':
        raise ValueError('not a PNG file')
    pos, ihdr, trns = 8, None, False
    while pos + 8 <= len(data):
        length, kind = struct.unpack('>I4s', data[pos:pos + 8])
        chunk = data[pos + 8:pos + 8 + length]
        if len(chunk) != length:
            raise ValueError('truncated PNG chunk')
        if kind == b'IHDR':
            if length != 13:
                raise ValueError('bad IHDR')
            ihdr = struct.unpack('>IIBB', chunk[:10])
        elif kind == b'tRNS':
            trns = True
        elif kind in (b'IDAT', b'IEND'):
            break
        pos += 12 + length
    if ihdr is None:
        raise ValueError('PNG without IHDR')
    w, h, depth, ctype = ihdr
    if w == 0 or h == 0 or ctype not in (0, 2, 3, 4, 6):
        raise ValueError('invalid PNG header')
    return w, h, depth, ctype, ctype in (4, 6) or trns


def _map_of(stem, model):
    tt = stem.split('_')
    if len(tt) < 2:
        return None
    m = tt[-2]
    return m if m in (NPM_MAPS if model == 'npm' else VPM_MAPS) else None


def texture_file_findings(path, data, model, kind):
    """Findings for one texture file. data: bytes or None when the file is missing.

    adapted from GeoAGR 13.64 (author Artem), GeoAGR.ms:65400-65470 (btn_check_npm) and :65850-65888
    (btn_check_vpm), changes: runs for EVERY map of EVERY object (defect D1, GeoAGR kept only the last
    object's paths); sizes from the locked standards: NPM 256..2048 square (128 only for m/r
    placeholders, conflict #5), GroundEl <= 512, Flora <= 2048, <= 3 MiB; VPM 2048/4096 square or the
    256 placeholder; alpha: NPM never, VPM only in Diffuse (never in ERM/Normal/placeholders);
    VPM 8 bits per channel read from the PNG header instead of ImageMagick `identify`.
    Returns (findings, info) where info is (w, h, map) or None.
    """
    stem = re.split(r'[\\/]', path)[-1]
    if not stem.lower().endswith('.png'):
        return [('tex_format', f'{stem}: textures are PNG')], None
    stem = stem[:-4]
    if data is None:
        return [('tex_missing', f'{stem}: file not found')], None
    try:
        w, h, depth, ctype, alpha = png_info(data)
    except ValueError as exc:
        return [('tex_unreadable', f'{stem}: {exc}')], None
    out = []
    mp = _map_of(stem.split('.')[0], model)
    if w != h:
        out.append(('tex_size', f'{stem}: {w}x{h} is not square'))
    if model == 'npm':
        allowed = set(NPM_TEX_SIZES) | ({NPM_TEX_PLACEHOLDER} if mp in ('m', 'r') else set())
        cap = NPM_GROUND_EL_MAX if kind == 'GroundEl' else NPM_FLORA_MAX if kind == 'Flora' else max(NPM_TEX_SIZES)
        if w not in allowed or h not in allowed or max(w, h) > cap:
            out.append(('tex_size', f'{stem}: {w}x{h} not in {sorted(a for a in allowed if a <= cap)}'))
        if alpha:
            out.append(('tex_alpha', f'{stem}: alpha channel is forbidden in NPM'))
        if len(data) > NPM_TEX_BYTES_MAX:
            out.append(('tex_file_size', f'{stem}: {len(data)} bytes > {NPM_TEX_BYTES_MAX}'))
        elif len(data) == NPM_TEX_BYTES_MAX:
            out.append(('at_threshold', f'{stem}: {len(data)} bytes == {NPM_TEX_BYTES_MAX}'))
    else:
        placeholder = w == h == VPM_TEX_PLACEHOLDER
        if not placeholder and (w not in VPM_TEX_SIZES or h not in VPM_TEX_SIZES):
            out.append(('tex_size', f'{stem}: {w}x{h} not in {list(VPM_TEX_SIZES)} or {VPM_TEX_PLACEHOLDER} placeholder'))
        if alpha and (placeholder or mp != 'Diffuse'):
            out.append(('tex_alpha', f'{stem}: alpha only in Diffuse, never in {mp or "unnamed map"}{" placeholder" if placeholder else ""}'))
        channel_bits = 8 if ctype == 3 else depth
        if channel_bits != VPM_BITS:
            out.append(('tex_bit_depth', f'{stem}: {channel_bits} bits per channel, expected {VPM_BITS}'))
    return out, (w, h, mp)


def udim_set_findings(stems):
    """VPM UDIM tiles of one object: from 1001, without gaps, Diffuse+ERM+Normal per tile.
    adapted from GeoAGR 13.64 (author Artem), GeoAGR.ms:65825-65830 (btn_check_vpm), changes: tiles and
    maps parsed from {map}_{SlotNumber}.{UDIM} names per object, not from the last object's paths."""
    tiles = {}
    out = []
    for stem in stems:
        tt = stem.split('_')
        last = tt[-1].split('.')
        if len(tt) < 3 or len(last) != 2 or not last[1].isdigit():
            out.append(('tex_udim', f'{stem}: no {{SlotNumber}}.{{UDIM}}'))
            continue
        tiles.setdefault((last[0], int(last[1])), set()).add(tt[-2])
    for slot in sorted({s for s, _ in tiles}):
        nums = sorted(u for s, u in tiles if s == slot)
        if nums and (nums[0] != 1001 or nums != list(range(1001, 1001 + len(nums)))):
            out.append(('tex_udim', f'slot {slot}: UDIM {nums} must run 1001.. without gaps'))
        for u in nums:
            missing = sorted(set(VPM_MAPS) - tiles[(slot, u)])
            if missing:
                out.append(('tex_set', f'slot {slot} UDIM {u}: missing {missing}'))
    return out


def _seg_dist(p, q, r, s):
    def d_ps(a, b, c):
        bx, by = c[0] - b[0], c[1] - b[1]
        L = bx * bx + by * by
        t = 0.0 if L == 0 else max(0.0, min(1.0, ((a[0] - b[0]) * bx + (a[1] - b[1]) * by) / L))
        return math.hypot(a[0] - b[0] - t * bx, a[1] - b[1] - t * by)

    def orient(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    o1, o2, o3, o4 = orient(p, q, r), orient(p, q, s), orient(r, s, p), orient(r, s, q)
    if o1 * o2 < 0 and o3 * o4 < 0:
        return 0.0
    return min(d_ps(p, r, s), d_ps(q, r, s), d_ps(r, p, q), d_ps(s, p, q))


def _inside(pt, tri):
    a, b, c = tri
    d1 = (pt[0] - b[0]) * (a[1] - b[1]) - (a[0] - b[0]) * (pt[1] - b[1])
    d2 = (pt[0] - c[0]) * (b[1] - c[1]) - (b[0] - c[0]) * (pt[1] - c[1])
    d3 = (pt[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (pt[1] - a[1])
    neg, pos = d1 < 0 or d2 < 0 or d3 < 0, d1 > 0 or d2 > 0 or d3 > 0
    return not (neg and pos)


def padding_findings(uvs, faces, size_px, required_px, owner=None, overlap_review=False):
    """Minimum gap between UV islands of one tile, in pixels of a size_px texture.

    uvs: [(u, v)]; faces: [(face_id, [uv vertex indices])] (polygons are fanned).
    adapted from GeoAGR 13.64 (author Artem), GeoAGR.ms:17010-17277 (UDIMs.btn_Udim_check: renderUV mask
    dilated by the padding), changes: exact segment distances between island boundaries instead of a
    raster dilation; the regulation's 16/32 px for VPM 2048/4096 (the commented-out branch, matrix
    gap 3) instead of the live 8 px; NPM keeps 8 px; a gap equal to the minimum is `at_threshold`;
    touching or overlapping islands have gap 0 and are `tex_padding` by default; with overlap_review
    (VPM: regulation 2.5.1.5 applies padding only to islands with unique images; VPM_STANDARD
    uv.repeating_islands_may_overlap, glass.overlap_allowed) a gap 0 is the review-level
    `tex_overlap_review` instead, kept apart from the gaps so it never hides a gap > 0 below the minimum;
    work above PADDING_PAIR_BUDGET edge pairs is `tex_unmeasurable`, never a pass.
    owner: face id -> owner (an object of a pooled atlas); the worst pair is reported PER OWNER and
    each finding carries its owner as a 4th element. Without owner one worst pair for the whole set.
    """
    one = owner is None
    owner = owner or (lambda _fid: None)
    if not faces:
        return [('tex_unmeasurable', 'no UV faces')]
    for u, v in uvs:
        if not (math.isfinite(u) and math.isfinite(v)):
            return [('tex_unmeasurable', 'non-finite UV')]
    parent = list(range(len(uvs)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for _, idx in faces:
        for j in idx[1:]:
            a, b = find(idx[0]), find(j)
            if a != b:
                parent[a] = b
    islands = {}
    for fid, idx in faces:
        islands.setdefault(find(idx[0]), []).append((fid, idx))
    data = []
    for root, fs in islands.items():
        edges, tris, ids = {}, [], []
        for fid, idx in fs:
            ids.append(fid)
            for k in range(len(idx)):
                e = tuple(sorted((idx[k], idx[(k + 1) % len(idx)])))
                edges[e] = edges.get(e, 0) + 1
            for k in range(1, len(idx) - 1):
                tris.append((uvs[idx[0]], uvs[idx[k]], uvs[idx[k + 1]]))
        boundary = [(uvs[a], uvs[b]) for (a, b), c in edges.items() if c == 1]
        pts = [uvs[i] for _, idx in fs for i in idx]
        cu = sum(p[0] for p in pts) / len(pts)
        cv = sum(p[1] for p in pts) / len(pts)
        box = (min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts))
        data.append({'tile': (math.floor(cu), math.floor(cv)), 'boundary': boundary, 'tris': tris,
                     'pts': pts, 'box': box, 'ids': ids})
    need = required_px / float(size_px)
    worst, overlaps = {}, {}
    work = 0
    for i in range(len(data)):
        for j in range(i + 1, len(data)):
            A, B = data[i], data[j]
            if A['tile'] != B['tile']:
                continue
            gx = max(A['box'][0] - B['box'][2], B['box'][0] - A['box'][2], 0.0)
            gy = max(A['box'][1] - B['box'][3], B['box'][1] - A['box'][3], 0.0)
            if math.hypot(gx, gy) > need:
                continue
            work += len(A['boundary']) * len(B['boundary'])
            if work > PADDING_PAIR_BUDGET:
                return [('tex_unmeasurable', f'UV padding needs more than {PADDING_PAIR_BUDGET} edge pairs')]
            d = min((_seg_dist(p, q, r, s) for p, q in A['boundary'] for r, s in B['boundary']), default=math.inf)
            if d > 0 and (any(_inside(A['pts'][0], t) for t in B['tris']) or any(_inside(B['pts'][0], t) for t in A['tris'])):
                d = 0.0
            # worst pair PER OWNER (review r1): a pooled atlas must not hide one object's violation
            # behind another pair's smaller gap
            for o in {owner(A['ids'][0]), owner(B['ids'][0])}:
                if overlap_review and d == 0:
                    overlaps.setdefault(o, A['ids'] + B['ids'])
                elif o not in worst or d < worst[o][0]:
                    worst[o] = (d, A['ids'] + B['ids'])
    out = []
    for o in sorted(overlaps, key=repr):
        out.append(('tex_overlap_review', f'UV islands touch or overlap at {size_px} px: allowed only for '
                    'repeating islands (VPM 2.5.1.5), review', overlaps[o], o))
    for o in sorted(worst, key=repr):
        d, ids = worst[o]
        px = d * size_px
        if math.isclose(px, required_px, rel_tol=0.0, abs_tol=1e-9):
            out.append(('at_threshold', f'UV island gap {px:.3f} px == {required_px} px', ids, o))
        elif px < required_px:
            detail = 'islands touch or overlap' if d == 0 else f'UV island gap {px:.3f} px'
            out.append(('tex_padding', f'{detail} < {required_px} px at {size_px} px', ids, o))
    return [i[:3] for i in out] if one else out


def required_padding(model, size):
    if model == 'npm':
        return NPM_PADDING_PX
    return VPM_PADDING_PX.get(size)


def atlas_id(paths, model):
    """Identity of the texture atlas a slot maps to: its base-colour maps (NPM `d`, VPM `Diffuse`; the
    VPM `.UDIM` suffix stripped so all tiles of one set are one atlas), else every map of the slot.
    Objects of one FBX whose slots share this id share the atlas; their islands are measured together."""
    base, every = set(), set()
    for path in paths:
        name = re.split(r'[\\/]', str(path))[-1]
        stem = name[:-4] if name.lower().endswith('.png') else name
        folder = re.sub(r'[\\/]+', '/', str(path)[:len(str(path)) - len(name)]).lower()
        if model == 'vpm':
            stem = re.sub(r'\.\d{4}$', '', stem)
        n = folder + stem.lower()
        every.add(n)
        if _map_of(stem.split('.')[0], model) in ('d', 'Diffuse'):
            base.add(n)
    return tuple(sorted(base or every))


def _no_submaterial_reason(mid, ids, slots):
    """Why `max_submaterial_index` found no sub-material: a duplicated target is ambiguous, not missing."""
    if type(mid) is int and mid >= 1 and ids and None not in slots and max(int(i) for i in ids) >= 1:
        w = (mid - 1) % max(int(i) for i in ids) + 1
        if sum(1 for v in ids if int(v) == w) > 1:
            return (f'face matID {mid} wraps to matID {w}, which is duplicated in materialIDList {list(ids)}: '
                    'the target sub-material is ambiguous')
    return f'face matID {mid} has no sub-material in the Multimaterial'


def max_submaterial_index(mid, ids):
    """Index into a Multimaterial's materialIDList for face matID `mid`, as the 3ds Max 2026 FBX export
    resolves it; None = no sub-material (the export writes an empty placeholder slot).
    Measured (3dsmaxbatch 2026.3, FBX export + re-import, PR for #827): the ID wraps by the HIGHEST
    listed ID n, w = (mid - 1) mod n + 1, then w must be in the list: #(1,2): 3->1, 4->2; #(1,5): 6->1,
    10->5, 2/3/4/7->none; #(2,3): 1/4->none, 5->2. Fail-closed: no IDs, a non-int or < 1 matID, or a
    duplicated resolved ID (ambiguous) give None, never the first entry."""
    if type(mid) is not int or mid < 1 or not ids:
        return None
    ids = [int(i) for i in ids]
    if max(ids) < 1:
        return None
    w = (mid - 1) % max(ids) + 1
    hits = [i for i, v in enumerate(ids) if v == w]
    return hits[0] if len(hits) == 1 else None


def listed_submaterial_index(mid, ids):
    """Index of face matID `mid` in materialIDList WITHOUT the FBX wrap; None when `mid` is not listed
    exactly once. The MatID check and the export `empty_slot` use it: a matID outside the list is a
    blocking finding even though the export wraps it onto another sub-material (#844, [D196]
    2026-11-04: the face gets another material in the delivery). Fail-closed like max_submaterial_index."""
    if type(mid) is not int or not ids or [int(i) for i in ids].count(mid) != 1:
        return None
    return max_submaterial_index(mid, ids)


def textures_scene(rows):
    """rows: [{'key', 'name', 'fbx', 'maps': [(path, bytes|None)], 'slots': {matID: [path]} (optional: a
    Multimaterial; absent = one material for every face), 'uv': callable -> (uvs, faces)}], faces are
    (face_id, [uv indices]) or (face_id, [uv indices], matID). 'id_list' (optional): the Multimaterial's
    materialIDList as given, duplicates kept; a face matID outside `slots` wraps by the highest listed ID
    (`max_submaterial_index`); a wrap target that is duplicated (ambiguous) or absent from `slots` is
    `tex_unmeasurable`, never measured.
    EVERY object's maps are read (defect D1: GeoAGR kept `texes_paths = texs` of the last object only,
    GeoAGR.ms:65313/65709). A map list is a list: empty means "no maps" (defect D3: GeoAGR.ms:65715
    tested the usedMaps array against undefined). UV padding is measured per ATLAS (review r1): every
    face goes to its matID's slot maps; the faces of all objects of one FBX whose slots share an atlas
    (`atlas_id`) are pooled, measured at that atlas size (per UDIM tile inside padding_findings) and the
    finding is split back per object with its own face ids. An unmapped matID is `tex_unmeasurable`
    naming it; a slot without maps is `tex_missing` + a dropped entry. Returns (findings by key, dropped)."""
    found, dropped = {}, []
    infos = {}
    atlases = {}  # (fbx, atlas id) -> {'size', 'need', 'uvs', 'faces', 'keys'}
    for r in rows:
        f = found.setdefault(r['key'], [])
        kind = fbx_kind(r.get('fbx'))
        if kind is None:
            f.append(('fbx_unmapped', f'AGR_EXPORT_PATH {r.get("fbx")!r} is not an NPM/VPM FBX name'))
            continue
        model = kind[0]
        mk = mesh_kind(r['name'])
        if mk == 'UCX':
            dropped.append({'name': r['name'], 'reason': 'UCX carries no textures'})
            continue
        maps = r['maps']
        if not isinstance(maps, list):
            raise ValueError('map list required for ' + r['name'])
        glass = mk in ('MainGlass', 'GroundGlass', 'GroundElGlass')
        if not maps:
            if glass:
                dropped.append({'name': r['name'], 'reason': 'glass without maps: nothing to measure'})
            else:
                f.append(('tex_missing', 'material has no texture maps'))
            continue
        if glass:
            f.append(('tex_format', 'glass materials carry no texture maps'))
        stems = []
        for path, data in maps:
            fs, info = texture_file_findings(path, data, model, mk)
            f.extend(fs)
            infos[path] = info
            stem = re.split(r'[\\/]', path)[-1]
            stems.append(stem[:-4] if stem.lower().endswith('.png') else stem)
        if model == 'vpm':
            f.extend(udim_set_findings(stems))
        slots = r.get('slots')
        if slots is None:
            slots = {None: [p for p, _ in maps]}
        elif not isinstance(slots, dict):
            raise ValueError('slot map required for ' + r['name'])
        elif not slots:
            f.append(('tex_unmeasurable', 'the Multimaterial has no sub-materials: no slot for any face'))
            continue
        known = {p for p, _ in maps}
        slot_atlas = {}
        for mid, paths in slots.items():
            if paths is None:  # materialIDList repeats this ID: which sub-material is meant is unknown
                f.append(('tex_unmeasurable', f'matID {mid} is repeated in materialIDList: '
                          'the sub-material for it is ambiguous, its faces are not measured'))
                continue
            missing = [p for p in paths if p not in known]
            if missing:
                raise ValueError(f'{r["name"]} matID {mid}: slot maps {missing} are not in the map list')
            where = '' if mid is None else f' on matID {mid}'
            if not paths:
                if not glass:
                    f.append(('tex_missing', f'matID {mid}: sub-material has no texture maps'))
                dropped.append({'name': r['name'], 'reason': f'UV padding not measured{where}: no maps'})
                continue
            sizes = [i[0] for i in (infos.get(p) for p in paths)
                     if i and i[0] == i[1] and (model == 'npm' or i[2] == 'Diffuse')]
            size = max(sizes) if sizes else None
            need = required_padding(model, size) if size else None
            if need is None:
                dropped.append({'name': r['name'],
                                'reason': f'UV padding not measured{where}: no {model} map size with a padding rule'})
                continue
            a = atlases.setdefault((r['fbx'], atlas_id(paths, model)),
                                   {'size': size, 'need': need, 'uvs': [], 'faces': [], 'keys': [],
                                    'model': model})
            if size > a['size']:
                a['size'], a['need'] = size, need
            slot_atlas[mid] = a
        if not slot_atlas:
            continue
        uvs, faces = r['uv']()
        if not faces:
            f.append(('tex_unmeasurable', 'no UV faces'))
            continue
        offsets, unmapped, wrapped = {}, {}, {}
        ids = r.get('id_list')  # the materialIDList as given (duplicates kept), like the FBX export sees it
        ids = [k for k in slots if k is not None] if ids is None else list(ids)
        for face in faces:
            fid, idx = face[0], face[1]
            mid = None if None in slots else (face[2] if len(face) > 2 else None)
            if mid not in slots:
                i = None if None in slots else max_submaterial_index(mid, ids)
                if i is None:
                    unmapped.setdefault(mid, _no_submaterial_reason(mid, ids, slots))
                    continue
                if ids[i] not in slots:  # in id_list but without a slot: nothing to measure on
                    unmapped.setdefault(mid, f'face matID {mid} wraps to matID {ids[i]} (sub {i + 1}), which is '
                                             'in materialIDList but has no slot in the Multimaterial')
                    continue
                wrapped.setdefault(mid, (i, []))[1].append(fid)
                mid = ids[i]
            a = slot_atlas.get(mid)
            if a is None:  # slot already reported (no maps / no padding rule)
                continue
            if id(a) not in offsets:
                offsets[id(a)] = len(a['uvs'])
                a['uvs'].extend(uvs)
                if r['key'] not in a['keys']:
                    a['keys'].append(r['key'])
            off = offsets[id(a)]
            a['faces'].append(((r['key'], fid), [i + off for i in idx]))
        for mid in sorted(unmapped, key=repr):
            f.append(('tex_unmeasurable', unmapped[mid]))
        for mid, (i, fids) in sorted(wrapped.items()):
            f.append(('tex_matid_wrapped', f'face matID {mid} -> sub {i + 1} (matID {ids[i]}): not in '
                      f'materialIDList {ids}; 3ds Max FBX export wraps it by the highest ID {max(ids)}, '
                      'padding measured on that sub-material', fids))
    for a in atlases.values():
        if not a['faces']:
            continue
        for item in padding_findings(a['uvs'], a['faces'], a['size'], a['need'], owner=lambda fid: fid[0],
                                     overlap_review=a['model'] == 'vpm'):
            if len(item) < 4:  # whole-atlas finding (unmeasurable): every object of the atlas
                for k in a['keys']:
                    found[k].append(item)
                continue
            k = item[3]
            others = sorted({kk for kk, _ in item[2] if kk != k}, key=repr)
            detail = item[1] + (f' (shared atlas with object keys {others})' if others else '')
            found[k].append((item[0], detail, [fid for kk, fid in item[2] if kk == k]))
    return found, dropped


# --- pivot --------------------------------------------------------------------------------------------
def pivot_findings(rows):
    """VPM-2.9-4.b (pivot Z at the project zero) and VPM-2.9-5 (all pivots of one FBX coincide).
    rows: [{'key', 'name', 'fbx', 'pivot': (x, y, z) metres}]. UCX pivots are free (VPM-2.9-4.c).
    adapted from GeoAGR 13.64 (author Artem), GeoAGR.ms:65915-65926 (btn_check_vpm pivot/bbox test),
    changes: no bbox-centre rule for glass (it contradicts VPM-2.9-5, matrix note); Z must be 0 within
    1 mm (conflict #19 decided); pivots compared per FBX within 1 mm; exactly 1 mm is `at_threshold`.
    Main/Ground names are the references (#832): a reference is not mismatched against another mesh;
    when references disagree, one `pivot_reference_ambiguous` is attached to the alphabetically first
    and that FBX gets no `pivot_mismatch`.
    Returns (findings by key, dropped [{'name', 'reason'}])."""
    found = {r['key']: [] for r in rows}
    dropped = []
    groups = {}
    for r in rows:
        kind = fbx_kind(r.get('fbx'))
        if kind is None:
            found[r['key']].append(('fbx_unmapped', f'AGR_EXPORT_PATH {r.get("fbx")!r} is not an NPM/VPM FBX name'))
            continue
        if kind[0] != 'vpm':
            dropped.append({'name': r['name'], 'reason': 'NPM FBX: VPM-2.9 pivot rules do not apply'})
            continue
        if is_ucx(r['name']):
            dropped.append({'name': r['name'], 'reason': 'UCX pivot is unconstrained (VPM-2.9-4.c)'})
            continue
        p = r.get('pivot')
        if not isinstance(p, (list, tuple)) or len(p) != 3 or not all(
                isinstance(c, (int, float)) and not isinstance(c, bool) and math.isfinite(c) for c in p):
            found[r['key']].append(('pivot_unmeasurable', f'pivot {p!r}'))
            continue
        z = abs(float(p[2]))
        if math.isclose(z, PIVOT_TOL_M, rel_tol=1e-9, abs_tol=0.0):
            found[r['key']].append(('at_threshold', f'pivot Z {p[2]:.6f} m: |Z| == {PIVOT_TOL_M} m'))
        elif z > PIVOT_TOL_M:
            found[r['key']].append(('pivot_z', f'pivot Z {p[2]:.6f} m, project zero is 0 (VPM-2.9-4.b)'))
        groups.setdefault(r['fbx'], []).append(r)

    def edge(a, b, distance):
        found[a['key']].append(('at_threshold', f'pivot {distance:.6f} m from {b["name"]}: == {PIVOT_TOL_M} m'))

    def mismatch(member, fbx, others):
        others = sorted((name, dist if math.isfinite(dist) else float('inf')) for name, dist in others)
        if others:
            txt = ', '.join(f'{name} ({dist:.6f} m)' for name, dist in others)
            found[member['key']].append(('pivot_mismatch', f'pivot differs from {txt} in {fbx} (VPM-2.9-5)'))

    for fbx, members in groups.items():
        # Order independent (#821, #832): Main/Ground objects are the references. A reference is never
        # mismatched against a non-reference. Disagreeing references are one finding on the alphabetically
        # first name, and that FBX then has no pivot_mismatch. Without a reference, every pair more than
        # 1 mm apart is reported (never "the first member").
        refs = [m for m in members if m['name'].split('_')[-1] in ('Main', 'Ground')]
        if refs:
            ambiguous = False
            ordered = sorted(refs, key=lambda m: m['name'])
            for i, left in enumerate(ordered):
                for right in ordered[i + 1:]:
                    kind, distance = _pivot_sep(left['pivot'], right['pivot'])
                    if kind == 'edge':
                        edge(left, right, distance)
                        edge(right, left, distance)
                    elif kind == 'bad':
                        ambiguous = True
            if ambiguous:
                shown = ', '.join(f'{m["name"]} {_pivot_xyz(m["pivot"])}' for m in ordered)
                found[ordered[0]['key']].append((
                    'pivot_reference_ambiguous',
                    f'Main/Ground references disagree in {fbx}: {shown} (VPM-2.9-5)'))
                continue
            ref_ids = {id(m) for m in refs}
            for member in members:
                if id(member) in ref_ids:
                    continue
                others = []
                for ref in refs:
                    kind, distance = _pivot_sep(member['pivot'], ref['pivot'])
                    if kind == 'edge':
                        edge(member, ref, distance)
                    elif kind == 'bad':
                        others.append((ref['name'], distance))
                mismatch(member, fbx, others)
            continue
        bad = {id(m): [] for m in members}
        for i, left in enumerate(members):
            for right in members[i + 1:]:
                kind, distance = _pivot_sep(left['pivot'], right['pivot'])
                if kind == 'edge':
                    edge(left, right, distance)
                    edge(right, left, distance)
                elif kind == 'bad':
                    bad[id(left)].append((right['name'], distance))
                    bad[id(right)].append((left['name'], distance))
        for member in members:
            mismatch(member, fbx, bad[id(member)])
    return found, dropped


def _pivot_xyz(pivot):
    parts = []
    for value in pivot:
        number = float(value)
        parts.append(str(int(number)) if number.is_integer() else format(number, 'g'))
    return '(' + ','.join(parts) + ')'


def _pivot_sep(left, right):
    """'edge' at exactly 1 mm, 'bad' when farther or not a finite distance, else 'ok'."""
    distance = math.dist(left, right)
    if not math.isfinite(distance):
        return 'bad', distance
    if math.isclose(distance, PIVOT_TOL_M, rel_tol=1e-9, abs_tol=0.0):
        return 'edge', distance
    if distance > PIVOT_TOL_M:
        return 'bad', distance
    return 'ok', distance


# --- GeoJSON ------------------------------------------------------------------------------------------
GEOJSON_CODE = (
    'import json, sys\n'
    'from pathlib import Path\n'
    'root = Path(sys.argv[1])\n'
    'sys.path[:0] = [str(root / "src")]\n'
    'from twinqa.geojson import geojson_findings\n'
    'from twinqa.profiles import load_profiles\n'
    'path = Path(sys.argv[2])\n'
    'out = geojson_findings(path.read_bytes(), load_profiles(root / "standards").vpm,\n'
    '                       path.stem.endswith("_Ground"), source_name=path.name)\n'
    'sys.stdout.write(json.dumps([{"name": f.name, "status": f.status, "observed": str(f.observed),\n'
    '                              "expected": str(f.expected)} for f in out], allow_nan=False))\n'
)


def geojson_report(path, runner):
    """Run the pilot twinqa GeoJSON checker through ``runner(path) -> list[dict]``.
    Every failure (missing file, wrong extension, crashing checker, bad output) is a finding, never a raise."""
    findings = []
    if not isinstance(path, str) or not path.strip():
        findings = [{'name': 'file', 'status': 'fail', 'observed': repr(path), 'expected': 'a .geojson file'}]
    elif not path.lower().endswith('.geojson'):
        findings = [{'name': 'file', 'status': 'fail', 'observed': path, 'expected': '*.geojson'}]
    else:
        try:
            got = runner(path)
            if not isinstance(got, list) or not got or any(
                    not isinstance(f, dict) or set(f) != {'name', 'status', 'observed', 'expected'} for f in got):
                raise ValueError('checker returned no findings')
            findings = got
        except Exception as exc:  # noqa: BLE001 - every failure must surface as a finding
            findings = [{'name': 'checker', 'status': 'fail', 'observed': str(exc)[-400:] or type(exc).__name__,
                         'expected': 'twinqa GeoJSON checker ran'}]
    status = 'pass' if all(f['status'] == 'pass' for f in findings) else 'fail'
    report = {'schema': 1, 'tool': 'geojson', 'status': status, 'objects': [],
              'plan': {'path': path if isinstance(path, str) else '', 'findings': findings}}
    validate_report(report)
    return report


# --- report contract ----------------------------------------------------------------------------------
def validate_plan(tool, plan):
    """Plan schema of the 0.5.0 tools (the 0.4.0 contract adds `plan` per tool)."""
    if tool == 'geojson':
        if not isinstance(plan, dict) or set(plan) != {'path', 'findings'} or not isinstance(plan['path'], str):
            raise ValueError('incomplete plan')
        if not isinstance(plan['findings'], list) or not plan['findings']:
            raise ValueError('incomplete plan')
        for f in plan['findings']:
            if not isinstance(f, dict) or set(f) != {'name', 'status', 'observed', 'expected'}:
                raise ValueError('incomplete finding')
            if f['status'] not in ('pass', 'fail', 'review', 'not_run'):
                raise ValueError('unmapped GeoJSON status ' + str(f['status']))
        return
    if not isinstance(plan, dict) or set(plan) != {'fbx', 'dropped'}:
        raise ValueError('incomplete plan')
    if not isinstance(plan['fbx'], list) or not isinstance(plan['dropped'], list):
        raise ValueError('incomplete plan')
    for row in plan['fbx']:
        if not isinstance(row, dict) or set(row) != FBX_ROW:
            raise ValueError('incomplete FBX row')
        if row['model'] not in ('npm', 'vpm') or row['role'] not in ('oks', 'ground'):
            raise ValueError('unmapped FBX kind')
    for item in plan['dropped']:
        if not isinstance(item, dict) or set(item) != {'name', 'reason'} or not item['reason']:
            raise ValueError('drop without a reason')


def validate_report(report):
    """GeoJSON report: no scene objects; status derived from the checker findings."""
    if report.get('tool') != 'geojson' or set(report) != {'schema', 'tool', 'status', 'objects', 'plan'}:
        raise ValueError('incomplete report')
    if report['schema'] != 1 or report['objects'] != []:
        raise ValueError('incomplete report')
    validate_plan('geojson', report['plan'])
    expected = 'pass' if all(f['status'] == 'pass' for f in report['plan']['findings']) else 'fail'
    if report['status'] != expected:
        raise ValueError('inconsistent status')
    json.dumps(report, allow_nan=False)
    return report
