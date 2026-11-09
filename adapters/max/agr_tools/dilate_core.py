"""AGR Tools 1.0 (#1024), owned by branch N (improve/issue-1024-vpm-maps): map padding (tex.dilate, station 1.0.20), stdlib only; no pymxs.

Plan row `tex.dilate`, mode `file`: writes padded PNG copies of texture maps into a NEW folder; the sources are never
touched and an existing file is refused (or versioned), never overwritten.

Source: GeoAGR Fit Mat / dilate chain `GeoAGR.ms:8265-8300` (ImageMagick `-transparent <corner colour>` + uvdilate.exe +
`-background black -alpha remove`) and `GeoAGR.ms:25021`; analysis C6 (alpha-guided RGB dilation, original on top).
Defects of the source that are not repeated (verdict of the plan row and lab L15):
* a map on a solid (white) background WITHOUT alpha gets no padding: nothing is "transparent" for the chain, so the mask
  can be an alpha channel, an explicit background colour (+ fuzz) or a UV coverage mask (`coverage_mask`);
* the output of uvdilate/`-alpha remove` has no alpha although the input had one: `keep_alpha` keeps it, the padded
  pixels get alpha 0 (the colour is only for mips/filtering, as in C6);
* the padding is not limited: a fixed pixel count per map size (VPM-2.5-1.5: 16 px at 2048, 32 px at 4096 -> size/128,
  NPM-2.5-4: 8 px) and pixels beyond it stay as they are;
* the original is not put on top of a recoloured substrate: every pixel INSIDE the mask is bit-identical in the output
  (the source also runs a colour correction, `makeGreener`, over the padded file);
* exit codes of external programs are not checked (L15): there is no external program here; a failure is a `failed`
  row, never a "successful" empty file;
* the output path overwrites silently (L15): `edit_core.new_path`.

Pixels of a mask are "covered" (island content); only uncovered pixels within `padding` of a covered pixel are filled,
ring by ring (4-neighbourhood, nearest covered pixel, mean of the already filled neighbours of the ring), deterministic.
"""
import importlib.util
import os
import sys

DEFAULT_PADDING = {'vpm': None, 'npm': 8}   # vpm: size // 128 (16 px at 2048, 32 px at 4096)
MASKS = ('auto', 'alpha', 'background', 'uv', 'file')
ISSUE = '#1024'


def _sibling(module_name, filename):
    mod = sys.modules.get(module_name)
    if mod is not None:
        return mod
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
    spec = importlib.util.spec_from_file_location(module_name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


def tex():
    return _sibling('agr_tools_tex_core', 'tex_core.py')


def edit_core():
    return _sibling('agr_tools_edit_core', 'edit_core.py')


# ---- padding amount ------------------------------------------------------------------------------------
def padding_px(profile, size):
    """Padding in px by profile and the longer side: vpm size // 128 (VPM-2.5-1.5), npm 8 (NPM-2.5-4)."""
    if profile not in DEFAULT_PADDING:
        raise ValueError('profile must be vpm or npm: ' + repr(profile))
    if DEFAULT_PADDING[profile] is not None:
        return DEFAULT_PADDING[profile]
    return max(1, int(size) // 128)


def dilate_options(options):
    """Validated options of tex.dilate (all parameters, no hidden defaults)."""
    o = dict(options or {})
    known = {'files', 'folder', 'out', 'profile', 'mask', 'background', 'fuzz', 'padding', 'keep_alpha',
             'on_exists', 'uv_faces', 'mask_files', 'owners'}
    extra = sorted(set(o) - known)
    if extra:
        raise ValueError('unknown options: ' + ', '.join(extra))
    files = o.get('files')
    if files is None and o.get('folder') is not None:
        files = tex().list_sources(o['folder'])
    if not files:
        raise ValueError('nothing to pad: give options.files or options.folder with PNG maps (empty input is an error)')
    if isinstance(files, str):
        files = [files]
    profile = o.get('profile', 'vpm')
    if profile not in DEFAULT_PADDING:
        raise ValueError('profile must be vpm or npm')
    mask = o.get('mask', 'auto')
    if mask not in MASKS:
        raise ValueError('mask must be one of ' + ', '.join(MASKS))
    if mask == 'background' and o.get('background') is None:
        raise ValueError('mask=background needs options.background [r,g,b]')
    padding = o.get('padding')
    if padding is not None and (type(padding) is not int or padding < 1):
        raise ValueError('padding must be a positive integer (pixels)')
    fuzz = o.get('fuzz', 0)
    if type(fuzz) is not int or not 0 <= fuzz <= 255:
        raise ValueError('fuzz must be 0..255')
    if o.get('on_exists', 'refuse') not in ('refuse', 'version'):
        raise ValueError('on_exists must be refuse or version')
    bg = None if o.get('background') is None else [int(v) for v in tex()._colour(o['background'])]
    return {'files': [str(f) for f in files], 'out': o.get('out'), 'profile': profile, 'mask': mask,
            'background': bg, 'fuzz': fuzz, 'padding': padding, 'keep_alpha': bool(o.get('keep_alpha', False)),
            'on_exists': o.get('on_exists', 'refuse'), 'uv_faces': o.get('uv_faces') or {},
            'mask_files': o.get('mask_files') or {}, 'owners': o.get('owners') or {}}


# ---- masks ---------------------------------------------------------------------------------------------
def mask_from_alpha(img, threshold=0):
    """1 where alpha > threshold. An image without alpha has no alpha mask (None)."""
    if img.n != 4:
        return None
    return bytearray(1 if a > threshold else 0 for a in img.px[3::4])


def mask_from_background(img, background, fuzz=0):
    """1 where the pixel differs from `background` by more than `fuzz` in any channel (maps on a solid background
    without alpha: the white-background case that the source chain leaves unpadded)."""
    br, bg, bb = background
    px, n = img.px, img.n
    out = bytearray(img.w * img.h)
    for i in range(img.w * img.h):
        o = i * n
        if n == 4 and px[o + 3] == 0:
            continue
        if abs(px[o] - br) > fuzz or abs(px[o + 1] - bg) > fuzz or abs(px[o + 2] - bb) > fuzz:
            out[i] = 1
    return out


def coverage_mask(w, h, faces, samples=3):
    """UV coverage of triangles/polygons of ONE tile (u, v in 0..1; v up) -> mask w*h, row 0 at the TOP.

    A pixel is covered when any of samples x samples points of it lies inside a face (conservative at island edges,
    deterministic). Faces with more than 3 vertices are fanned. Degenerate faces cover nothing."""
    mask = bytearray(w * h)
    step = [(k + 0.5) / samples for k in range(samples)]
    for face in faces:
        pts = [(float(u) * w, (1.0 - float(v)) * h) for u, v in face]
        for k in range(1, len(pts) - 1):
            _fill_triangle(mask, w, h, pts[0], pts[k], pts[k + 1], step)
    return mask


def _fill_triangle(mask, w, h, a, b, c, step):
    area = (b[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (b[1] - a[1])
    if abs(area) < 1e-12:
        return
    x0, x1 = max(0, int(min(a[0], b[0], c[0]) - 1)), min(w - 1, int(max(a[0], b[0], c[0]) + 1))
    y0, y1 = max(0, int(min(a[1], b[1], c[1]) - 1)), min(h - 1, int(max(a[1], b[1], c[1]) + 1))
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            if mask[y * w + x]:
                continue
            for sy in step:
                hit = False
                for sx in step:
                    px, py = x + sx, y + sy
                    w0 = ((b[0] - a[0]) * (py - a[1]) - (px - a[0]) * (b[1] - a[1])) / area
                    w1 = ((px - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (py - a[1])) / area
                    if w0 >= -1e-9 and w1 >= -1e-9 and w0 + w1 <= 1 + 1e-9:
                        hit = True
                        break
                if hit:
                    mask[y * w + x] = 1
                    break


def choose_mask(img, opts, name, decode=None):
    """(mask, source) for one map. `auto`: UV faces of the file, else alpha, else the explicit background; a map with
    none of them is refused by the caller (never guessed from a corner pixel)."""
    kind = opts['mask']
    if kind in ('auto', 'uv') and name in opts['uv_faces']:
        return coverage_mask(img.w, img.h, opts['uv_faces'][name]), 'uv'
    if kind == 'uv':
        return None, 'uv'
    if kind in ('auto', 'alpha'):
        m = mask_from_alpha(img)
        if m is not None and (kind == 'alpha' or not all(m)):
            return m, 'alpha'
        if kind == 'alpha':
            return None, 'alpha'
    if kind in ('auto', 'background') and opts['background'] is not None:
        return mask_from_background(img, opts['background'], opts['fuzz']), 'background'
    return None, kind


# ---- dilation ------------------------------------------------------------------------------------------
def dilate_masked(img, mask, radius, keep_alpha=False):
    """Fill uncovered pixels within `radius` rings (4-neighbourhood) of covered ones with the nearest covered colour.

    Covered pixels are never changed. Returns (Image, filled count). With keep_alpha the output has alpha: covered
    pixels keep theirs, padded pixels get alpha 0 (an RGB input gets alpha 255 on covered pixels)."""
    tc = tex()
    w, h, n, px = img.w, img.h, img.n, img.px
    if len(mask) != w * h:
        raise ValueError('mask size {} does not match the image {}x{}'.format(len(mask), w, h))
    if not any(mask):
        raise ValueError('mask covers nothing: the map has no island content to pad')
    rgb = bytearray(w * h * 3)
    for i in range(w * h):
        rgb[3 * i:3 * i + 3] = px[i * n:i * n + 3]
    filled = bytearray(mask)
    front = [i for i in range(w * h) if not mask[i]]
    count = 0
    for _ in range(radius):
        newly, rest = [], []
        for i in front:
            x, y = i % w, i // w
            acc, k = [0, 0, 0], 0
            for j in ((i - 1) if x > 0 else -1, (i + 1) if x < w - 1 else -1, (i - w) if y > 0 else -1,
                      (i + w) if y < h - 1 else -1):
                if j >= 0 and filled[j]:
                    acc[0] += rgb[3 * j]
                    acc[1] += rgb[3 * j + 1]
                    acc[2] += rgb[3 * j + 2]
                    k += 1
            if k:
                newly.append((i, [(c + k // 2) // k for c in acc]))
            else:
                rest.append(i)
        if not newly:
            break
        for i, c in newly:
            rgb[3 * i:3 * i + 3] = bytes(c)
            filled[i] = 1
        count += len(newly)
        front = rest
    if not keep_alpha:
        return tc.Image(w, h, 3, rgb), count
    out = bytearray(w * h * 4)
    for i in range(w * h):
        out[4 * i:4 * i + 3] = rgb[3 * i:3 * i + 3]
        if mask[i]:
            out[4 * i + 3] = px[i * n + 3] if n == 4 else 255
    return tc.Image(w, h, 4, out), count


def covered_identical(before, after, mask):
    """True when every covered pixel's RGB is bit-identical (the "original on top" rule)."""
    nb, na = before.n, after.n
    for i in range(before.w * before.h):
        if mask[i] and before.px[i * nb:i * nb + 3] != after.px[i * na:i * na + 3]:
            return False
    return True


# ---- plan / report -------------------------------------------------------------------------------------
def output_name(path):
    """`<stem>.<ext>` is kept: padding changes pixels, not the name (names_core grammar of the source file)."""
    return os.path.basename(str(path))


def dilate_plan(opts, read, exists=os.path.exists):
    """Rows [{path, name, target, size, padding, mask, filled, data|reason, code}] for every source file.

    `read(path)` -> bytes or None. Nothing is written here. A source that cannot be padded is a row with `code`
    and `reason` (`dilate_not_png`, `dilate_unreadable`, `dilate_no_mask`, `dilate_exists`...), never a copy."""
    tc, edit = tex(), edit_core()
    rows, planned = [], set()
    out_dir = opts['out']
    for path in opts['files']:
        name = os.path.basename(path)
        row = {'path': path, 'name': name, 'owners': [list(x) for x in opts['owners'].get(name, ())]}
        data = read(path)
        if data is None:
            row.update(code='dilate_unreadable', reason='file not found or unreadable: ' + path)
            rows.append(row)
            continue
        if data[:8] != tc.PNG_SIG:
            row.update(code='dilate_not_png', reason='only PNG maps are padded in the core (convert with tex.format_fix)')
            rows.append(row)
            continue
        try:
            img = tc.decode_png(data)[0]
            mask, source = choose_mask(img, opts, name)
        except Exception as exc:  # noqa: BLE001 - a bad file is a row, the batch goes on
            row.update(code='dilate_unreadable', reason='cannot decode: {}'.format(exc))
            rows.append(row)
            continue
        if mask is None:
            row.update(code='dilate_no_mask', reason='no alpha, no UV faces and no background colour for this map '
                       '(mask={}): nothing is guessed from a corner pixel'.format(opts['mask']))
            rows.append(row)
            continue
        side = max(img.w, img.h)
        pad = opts['padding'] or padding_px(opts['profile'], side)
        row.update(size=[img.w, img.h], padding=pad, mask=source, covered=sum(mask))
        if not any(mask):
            row.update(code='dilate_empty_mask', reason='mask covers nothing')
            rows.append(row)
            continue
        if all(mask):
            row.update(code='dilate_nothing_to_pad', reason='the map is fully covered, no free pixels', filled=0)
            rows.append(row)
            continue
        target = os.path.join(out_dir if out_dir else os.path.join(os.path.dirname(path), 'padded'), output_name(path))
        key = os.path.normcase(os.path.abspath(target))
        if key in planned:
            row.update(code='dilate_duplicate', reason='same target requested twice: second refused', target=target)
            rows.append(row)
            continue
        planned.add(key)
        try:
            row['target'] = edit.new_path(target, version=opts['on_exists'] == 'version', exists=exists)
        except FileExistsError:
            row.update(code='dilate_exists', reason='exists, not overwritten (on_exists=refuse): ' + target, target=target)
            rows.append(row)
            continue
        try:
            out, filled = dilate_masked(img, mask, pad, keep_alpha=opts['keep_alpha'])
            row['filled'] = filled
            row['data'] = tc.encode_png(out)
            row['channels'] = out.n
        except Exception as exc:  # noqa: BLE001
            row.update(code='dilate_failed', reason='padding failed: {}'.format(exc))
        rows.append(row)
    return rows


def dilate_state(rows, opts):
    """JSON-ready state for the preview hash: options, sources (size) and targets (existence)."""
    return {'tool': 'tex.dilate', 'options': opts,
            'rows': [{'path': r['path'], 'target': r.get('target'), 'code': r.get('code'),
                      'size': r.get('size'), 'padding': r.get('padding'), 'filled': r.get('filled')} for r in rows]}


def dilate_report(edit, mode, opts, rows, state_hash=None, written=()):
    done = [{'path': r['path'], 'target': r['target'], 'padding': r['padding'], 'filled': r['filled'],
             'mask': r['mask']} for r in rows if 'code' not in r]
    skipped = [edit.skipped(r['path'], r['reason']) for r in rows if 'code' in r]
    objects, seen = [], set()
    for i, r in enumerate(rows):
        finding = [edit.finding(r['code'], (), '{}: {}'.format(r['name'], r['reason']))] if 'code' in r else []
        for h, node in r.get('owners') or [[i + 1, r['name']]]:     # the owner nodes; a file without one is its own entry
            if int(h) in seen:
                prev = next(o for o in objects if o['handle'] == int(h))
                prev['findings'] += [f for f in finding if f not in prev['findings']]
                continue
            seen.add(int(h))
            objects.append(edit.entry(h, node, finding))
    plan_rows = [{k: v for k, v in r.items() if k != 'data'} for r in rows]
    extra = {'options': opts, 'files': plan_rows}
    if mode == 'apply':
        extra['written'] = list(written)
    return edit.report('tex.dilate', mode, objects, done, skipped, [],
                       state_hash=state_hash if mode == 'preview' else None, extra=extra)


def write_padded(edit, rows):
    """Write the planned PNG files as NEW files (edit.write_new refuses an existing path)."""
    written = []
    for r in rows:
        if 'code' in r:
            continue
        os.makedirs(os.path.dirname(r['target']), exist_ok=True)
        edit.write_new(r['target'], r['data'])
        written.append(r['target'])
    return written
