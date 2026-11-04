"""new-case: AGR Tools 0.8 branch B (#908): tex.format_fix, tex.placeholders, scene.missing_maps.

Every defect named in docs/experiments/{tex.format_fix,tex.placeholders,scene.missing_maps}.md is a regression
test run against two implementations:
* `source` - a behaviour model of the GeoAGR 13.64 source AS MEASURED in lab L02/L03 (no GeoAGR code, #853):
  it must FAIL (strict xfail = RED);
* `agr` - tex_core.py / tex_max.py of this branch: it must PASS (GREEN).
Plus the "minimal acceptance" of each lab report on synthetic files, and the glue preview -> apply through
a fake pymxs (the real Max run is tests/max_tools/run_agr_tools_tex_native.py).
"""
import hashlib
import importlib.util
import os
import random
import struct
import sys
import types
import zlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / 'adapters/max/agr_tools'


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


ec = sys.modules.get('agr_tools_edit_core') or _load(PKG / 'edit_core.py', 'agr_tools_edit_core')
cc = sys.modules.get('agr_tools_checks_core') or _load(PKG / 'checks_core.py', 'agr_tools_checks_core')
tc = _load(PKG / 'tex_core.py', 'agr_tools_tex_core_t')
tm = _load(PKG / 'tex_max.py', 'agr_tools_tex_max_t')


# ---- synthetic PNG writer (test side, independent of tex_core's encoder) ------------------------------
def _chunk(kind, body):
    return struct.pack('>I', len(body)) + kind + body + struct.pack('>I', zlib.crc32(kind + body) & 0xffffffff)


def _pack(samples, depth):
    if depth == 8:
        return bytes(samples)
    if depth == 16:
        return struct.pack('>{}H'.format(len(samples)), *samples)
    out, per = bytearray(), 8 // depth
    for i in range(0, len(samples), per):
        b = 0
        for k, s in enumerate(samples[i:i + per]):
            b |= s << (8 - depth * (k + 1))
        out.append(b)
    return bytes(out)


ADAM7 = ((0, 0, 8, 8), (4, 0, 8, 8), (0, 4, 4, 8), (2, 0, 4, 4), (0, 2, 2, 4), (1, 0, 2, 2), (0, 1, 1, 2))


def png(w, h, ctype, depth, pixel, plte=None, trns=None, interlace=0):
    """pixel(x, y) -> tuple of samples for the colour type."""
    nch = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[ctype]
    raw = bytearray()
    passes = [(0, 0, 1, 1)] if not interlace else ADAM7
    for x0, y0, dx, dy in passes:
        xs = range(x0, w, dx)
        for y in range(y0, h, dy):
            if not len(xs):
                continue
            samples = [s for x in xs for s in pixel(x, y)]
            assert len(samples) == len(xs) * nch
            raw += b'\x00' + _pack(samples, depth)
    out = b'\x89PNG\r\n\x1a\n' + _chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, depth, ctype, 0, 0, interlace))
    if plte is not None:
        out += _chunk(b'PLTE', bytes(c for rgb in plte for c in rgb))
    if trns is not None:
        out += _chunk(b'tRNS', trns)
    return out + _chunk(b'IDAT', zlib.compress(bytes(raw))) + _chunk(b'IEND', b'')


def rgb8(w, h, f=lambda x, y: (x % 256, y % 256, (x + y) % 256)):
    return png(w, h, 2, 8, f)


def rgba_half(w=64, h=64, colour=(200, 40, 40)):
    """Left half opaque colour, right half fully transparent (hidden colour bright green)."""
    return png(w, h, 6, 8, lambda x, y: colour + (255,) if x < w // 2 else (0, 255, 0, 0))


def pixels(data):
    img, info = tc.decode_png(data)
    return img, info


def md5(p):
    return hashlib.md5(Path(p).read_bytes()).hexdigest()


def noise_png(side, seed=7):
    rnd = random.Random(seed)
    raw = bytearray()
    for _ in range(side):
        raw += b'\x00' + bytes(rnd.getrandbits(8) for _ in range(side * 3))
    return (b'\x89PNG\r\n\x1a\n' + _chunk(b'IHDR', struct.pack('>IIBBBBB', side, side, 8, 2, 0, 0, 0))
            + _chunk(b'IDAT', zlib.compress(bytes(raw), 1)) + _chunk(b'IEND', b''))


# ---- PNG reader/writer -------------------------------------------------------------------------------
@pytest.mark.parametrize('ctype,depth', [(0, 1), (0, 2), (0, 4), (0, 8), (0, 16), (2, 8), (2, 16), (3, 1), (3, 2),
                                         (3, 4), (3, 8), (4, 8), (4, 16), (6, 8), (6, 16)])
@pytest.mark.parametrize('interlace', [0, 1])
def test_decode_every_colour_type_and_depth(ctype, depth, interlace):
    w, h = 13, 9
    top = (1 << depth) - 1
    nch = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[ctype]
    pal = [(i * 7 % 256, i * 13 % 256, i * 29 % 256) for i in range(min(256, top + 1))] if ctype == 3 else None

    def pix(x, y):
        return tuple((x * 3 + y * 5 + c * 11) % (top + 1) for c in range(nch))
    data = png(w, h, ctype, depth, pix, plte=pal, interlace=interlace)
    img, info = tc.decode_png(data)
    assert (img.w, img.h, info['depth'], info['color_type'], info['interlace']) == (w, h, depth, ctype, interlace)
    assert img.n == (4 if ctype in (4, 6) else 3)
    for x, y in ((0, 0), (12, 8), (5, 3), (7, 6)):
        s = pix(x, y)
        got = img.px[(y * w + x) * img.n:(y * w + x + 1) * img.n]
        if ctype == 3:
            exp = pal[s[0]]
        else:
            to8 = [round(v * 255 / top) for v in s]
            exp = [to8[0]] * 3 if ctype in (0, 4) else to8[:3]
            if ctype == 4:
                exp = exp + [to8[1]]
            elif ctype == 6:
                exp = exp + [to8[3]]
        assert list(got) == list(exp), (x, y, list(got), list(exp))


def test_decode_trns_and_crc():
    data = png(4, 1, 3, 8, lambda x, y: (x,), plte=[(1, 2, 3)] * 4, trns=bytes([0, 128]))
    img, info = tc.decode_png(data)
    assert img.n == 4 and list(img.alpha()) == [0, 128, 255, 255] and info['trns']
    gray = png(2, 1, 0, 8, lambda x, y: (x * 9,), trns=struct.pack('>H', 9))
    assert list(tc.decode_png(gray)[0].alpha()) == [255, 0]
    bad = bytearray(rgb8(4, 4))
    bad[-20] ^= 0xFF
    with pytest.raises(ValueError, match='CRC'):
        tc.decode_png(bytes(bad))


def test_encode_roundtrip_and_png_info():
    for n in (3, 4):
        px = bytes((i * 37) % 256 for i in range(17 * 5 * n))
        data = tc.encode_png(tc.Image(17, 5, n, px))
        assert cc.png_info(data)[:4] == (17, 5, 8, 2 if n == 3 else 6)
        assert tc.decode_png(data)[0].px == px
    solid = tc.solid_png(128, [101, 117, 92])
    img, _ = tc.decode_png(solid)
    assert cc.png_info(solid)[:5] == (128, 128, 8, 2, False) and set(zip(*[iter(img.px)] * 3)) == {(101, 117, 92)}


# ---- source behaviour models (measured GeoAGR 13.64, lab L03 / L02) ---------------------------------
class SourceFormat:
    """GeoAGR Format & Alpha Tex as measured (GeoAGR.ms:40195-41094, compress_file GeoAGR.ms:7971-8073)."""

    @staticmethod
    def detect(data):  # identify.exe on PATH: RGBA, palette and 24-bit all "8-bit sRGB"; .NET: RGB16 -> 32-bit Argb
        w, h, depth, ctype, alpha = cc.png_info(data)
        return {'bit_depth': 8, 'color_type': 2} if depth == 8 else {'bit_depth': 8, 'color_type': 6}

    @staticmethod
    def run(sources, out, background=None, max_bytes=None, max_side=None, decode=None):
        done = {}
        for p in sources:  # in place, no backup; a JPG writes a PNG beside it and stops the loop
            if not p.lower().endswith('.png'):
                img = decode(p)
                Path(p).with_suffix('.png').write_bytes(tc.encode_png(img))
                done[p] = str(Path(p).with_suffix('.png'))
                break
            img, _ = tc.decode_png(Path(p).read_bytes())
            if img.n == 4:
                img, _ = tc.flatten(img, [255, 255, 255])  # Remove alpha flattens on white
            if max_side and max(img.w, img.h) > max_side:  # Resize forces a square
                img = tc.Image(max_side, max_side, 3, bytes(max_side * max_side * 3))
            data = tc.encode_png(img)
            if len(data) > 3 * 1000 * 1000:  # compress only > 3.0 MB and always to 3.0 MB, target ignored
                data = tc.encode_png(tc.Image(img.w, img.h, 3, tc.posterize(img.px, 6)))
            Path(p).write_bytes(data)
            done[p] = p
        return done

    @staticmethod
    def dilate_default():
        return True


class AgrFormat:
    detect = staticmethod(lambda data: {k: v for k, v in zip(('bit_depth', 'color_type'), cc.png_info(data)[2:4])})

    @staticmethod
    def run(sources, out, background=None, max_bytes=None, max_side=None, decode=None):
        opts = tc.format_options({'files': list(sources), 'out': str(out), 'background': background,
                                  **({'max_bytes': max_bytes} if max_bytes else {}),
                                  **({'max_side': max_side} if max_side else {})})
        folder, rows = tc.format_fix(list(sources), opts, lambda p: Path(p).read_bytes() if Path(p).is_file() else None,
                                     decode)
        tc.write_outputs(ec, folder, rows)
        return {r['source']: r['out'] for r in rows if 'out' in r}

    @staticmethod
    def dilate_default():
        return tc.format_options({})['dilate']


IMPLS = [pytest.param('source', marks=pytest.mark.xfail(strict=True, reason='GeoAGR 13.64 as measured (RED)')),
         'agr']


def impl(name):
    return {'source': SourceFormat, 'agr': AgrFormat}[name]


def fake_jpg(tmp_path, name='photo.jpg', colour=(10, 120, 30)):
    p = tmp_path / name
    p.write_bytes(b'\xff\xd8FAKEJPEG' + bytes(colour))
    return p


def fake_decode(path):
    data = Path(path).read_bytes()
    return tc.Image(8, 8, 3, data[-3:] * 64)


@pytest.mark.parametrize('name', IMPLS)
def test_F1_never_in_place_new_folder(tmp_path, name):
    src = tmp_path / 'src'
    src.mkdir()
    a = src / 'T_a_d_1.png'
    a.write_bytes(png(8, 8, 3, 8, lambda x, y: (x % 2,), plte=[(1, 2, 3), (4, 5, 6)]))
    before = md5(a)
    outs = impl(name).run([str(a)], tmp_path / 'out')
    assert md5(a) == before
    assert outs and all(Path(o).parent == tmp_path / 'out' for o in outs.values())


@pytest.mark.parametrize('name', IMPLS)
def test_F2_format_from_ihdr_palette_and_16bit_visible(name):
    pal = png(4, 4, 3, 8, lambda x, y: (0,), plte=[(9, 9, 9)])
    rgb16 = png(4, 4, 2, 16, lambda x, y: (1000, 2000, 3000))
    assert impl(name).detect(pal) == {'bit_depth': 8, 'color_type': 3}
    assert impl(name).detect(rgb16) == {'bit_depth': 16, 'color_type': 2}


@pytest.mark.parametrize('name', IMPLS)
def test_F3_alpha_flattened_on_chosen_background_not_white(tmp_path, name):
    p = tmp_path / 'T_a_Diffuse_1.1001.png'
    p.write_bytes(rgba_half())
    outs = impl(name).run([str(p)], tmp_path / 'out', background=[10, 20, 30])
    img, info = pixels(Path(outs[str(p)]).read_bytes())
    assert info['color_type'] == 2
    assert img.px[(5 * 64 + 60) * 3:(5 * 64 + 61) * 3] == bytes((10, 20, 30))
    assert img.px[(5 * 64 + 2) * 3:(5 * 64 + 3) * 3] == bytes((200, 40, 40))


@pytest.mark.parametrize('name', IMPLS)
def test_F4_jpg_does_not_stop_the_batch(tmp_path, name):
    a = tmp_path / 'a.png'
    a.write_bytes(rgb8(8, 8))
    j = fake_jpg(tmp_path)
    b = tmp_path / 'b.png'
    b.write_bytes(png(8, 8, 0, 8, lambda x, y: (x * 9,)))
    outs = impl(name).run([str(a), str(j), str(b)], tmp_path / 'out', decode=fake_decode)
    assert set(outs) == {str(a), str(j), str(b)}
    assert cc.png_info(Path(outs[str(j)]).read_bytes())[2:4] == (8, 2)


@pytest.mark.parametrize('name', IMPLS)
def test_F5_resize_keeps_aspect(tmp_path, name):
    p = tmp_path / 'wide.png'
    p.write_bytes(rgb8(512, 256))
    outs = impl(name).run([str(p)], tmp_path / 'out', max_side=256)
    assert cc.png_info(Path(outs[str(p)]).read_bytes())[:2] == (256, 128)


@pytest.mark.parametrize('name', IMPLS)
def test_F6_size_limit_is_a_parameter_and_honoured(tmp_path, name):
    p = tmp_path / 'noise.png'
    p.write_bytes(noise_png(160))  # ~77 kB of incompressible RGB
    limit = 64 * 1024
    outs = impl(name).run([str(p)], tmp_path / 'out', max_bytes=limit)
    assert Path(outs[str(p)]).stat().st_size <= limit


@pytest.mark.parametrize('name', IMPLS)
def test_F8_no_dilate_by_default(name):
    assert impl(name).dilate_default() is False


def test_F7_compress_never_silent(tmp_path):
    """IM "Matrix" wrote nothing without a word; here an unreachable limit is a skipped row with a reason."""
    p = tmp_path / 'noise.png'
    p.write_bytes(noise_png(96))
    opts = tc.format_options({'files': [str(p)], 'out': str(tmp_path / 'o'), 'max_bytes': 1024,
                              'max_posterize_bits': 1})
    out, rows = tc.format_fix([str(p)], opts, lambda q: Path(q).read_bytes())
    rep = tc.format_report(ec, 'preview', out, rows, 'x' * 64, opts)
    assert rep['plan']['done'] == [] and 'still >' in rep['plan']['skipped'][0]['reason']


def _fit_one(tmp_path, data, name='T_a_d_1.png', **opts):
    tmp_path.mkdir(parents=True, exist_ok=True)
    p = tmp_path / name
    p.write_bytes(data)
    o = tc.format_options(dict({'out': str(tmp_path / 'o')}, **opts))
    return tc.format_fix([str(p)], o, lambda q: Path(q).read_bytes())[1][0]


def test_palette_order_exact_then_quantized_then_posterize(tmp_path):
    """Decision of Artem 05.11.2026 (team audit T01): over the limit, lossless RGB -> palette -> quantised
    palette; posterize only when palette is off or does not fit. The choice is reported."""
    rnd = random.Random(5)
    cols = [(rnd.randrange(256), rnd.randrange(256), rnd.randrange(256)) for _ in range(16)]
    grid = [[rnd.choice(cols) for _ in range(256)] for _ in range(256)]
    few = png(256, 256, 2, 8, lambda x, y: grid[y][x])  # 16 random colours: RGB deflates worse than indices
    r = _fit_one(tmp_path / 'a', few, max_bytes=40 * 1024)  # source 45.6 kB, RGB 45.2 kB, palette 38.6 kB  # <= 256 colours: exact palette, lossless
    assert r['encoding'] == 'palette_exact' and r['rmse'] == 0.0 and r['max_channel_error'] == 0
    img, info = tc.decode_png(r['png'])
    assert info['color_type'] == 3 and img.px == tc.decode_png(few)[0].px
    r = _fit_one(tmp_path / 'b', noise_png(128), max_bytes=24 * 1024)
    assert r['encoding'] == 'palette_quantized' and r['colours'] <= 256 and r['bytes_out'] <= 24 * 1024
    out = tc.decode_png(r['png'])[0].px
    assert r['rmse'] == tc.rmse(tc.decode_png(noise_png(128))[0].px, out) > 0
    assert r['max_channel_error'] == tc.max_channel_error(tc.decode_png(noise_png(128))[0].px, out)
    r = _fit_one(tmp_path / 'c', noise_png(128), max_bytes=24 * 1024, palette=False)
    assert r['encoding'] == 'rgb_posterize' and cc.png_info(r['png'])[3] == 2


def test_palette_input_is_valid_and_rgba_never_palettized(tmp_path):
    pal = png(16, 16, 3, 8, lambda x, y: (x % 2,), plte=[(1, 2, 3), (4, 5, 6)])
    r = _fit_one(tmp_path / 'a', pal)
    assert r['actions'] == ['copied_unchanged'] and r['png'] == pal
    rnd = random.Random(6)
    keep = png(128, 128, 6, 8, lambda x, y: (rnd.randrange(256), rnd.randrange(256), rnd.randrange(256), 128))
    r = _fit_one(tmp_path / 'b', keep, name='T_a_Diffuse_1.1001.png', profile='vpm', max_bytes=24 * 1024)
    assert cc.png_info(r['png'])[3] == 6 and r['encoding'] == 'rgb_posterize'


def test_alpha_refused_without_background_and_kept_where_allowed(tmp_path):
    p = tmp_path / 'T_a_ERM_1.1001.png'
    p.write_bytes(rgba_half())
    d = tmp_path / 'T_a_Diffuse_1.1001.png'
    d.write_bytes(rgba_half())
    opaque = tmp_path / 'T_a_Normal_1.1001.png'
    opaque.write_bytes(png(4, 4, 6, 8, lambda x, y: (128, 128, 255, 255)))
    opts = tc.format_options({'profile': 'vpm', 'out': str(tmp_path / 'o')})
    _, rows = tc.format_fix([str(p), str(d), str(opaque)], opts, lambda q: Path(q).read_bytes())
    by = {Path(r['source']).name: r for r in rows}
    assert 'forbidden' in by[p.name]['reason'] and 'png' not in by[p.name]
    assert cc.png_info(by[d.name]['png'])[3] == 6 and 'alpha kept' in by[d.name]['notes'][0]
    assert by[opaque.name]['actions'][:1] == ['alpha_dropped_opaque'] and cc.png_info(by[opaque.name]['png'])[3] == 2


def test_dilate_on_request_uses_edge_colour(tmp_path):
    p = tmp_path / 'T_a_d_1.png'
    p.write_bytes(rgba_half(colour=(50, 60, 70)))
    opts = tc.format_options({'dilate': True, 'out': str(tmp_path / 'o')})
    _, rows = tc.format_fix([str(p)], opts, lambda q: Path(q).read_bytes())
    img, _ = pixels(rows[0]['png'])
    assert set(zip(*[iter(img.px)] * 3)) == {(50, 60, 70)} and rows[0]['actions'][-2] == 'alpha_flattened_dilate'


def test_out_folder_rules(tmp_path):
    p = tmp_path / 'a.png'
    p.write_bytes(rgb8(4, 4))
    with pytest.raises(ValueError, match='never in place'):
        tc.output_folder([str(p)], str(tmp_path))
    busy = tmp_path / 'busy'
    busy.mkdir()
    (busy / 'x.txt').write_text('x')
    with pytest.raises(FileExistsError):
        tc.output_folder([str(p)], str(busy))
    (tmp_path / 'AGR_format_fix').mkdir()
    assert tc.output_folder([str(p)]).endswith('AGR_format_fix_v002')


def test_output_name_collision_is_ambiguous(tmp_path):
    a = tmp_path / 'tex.png'
    a.write_bytes(rgb8(4, 4))
    j = fake_jpg(tmp_path, 'tex.jpg')
    opts = tc.format_options({'out': str(tmp_path / 'o')})
    out, rows = tc.format_fix([str(a), str(j)], opts, lambda q: Path(q).read_bytes(), fake_decode)
    rep = tc.format_report(ec, 'preview', out, rows, 'h', opts)
    assert rep['status'] == 'fail' and rep['plan']['ambiguous'][0]['item'] == str(j)


def test_acceptance_format_fix(tmp_path):
    """Lab L03 minimal acceptance (JPG through an injected decoder; the real one runs in Max)."""
    src = tmp_path / 'src'
    src.mkdir()
    files = {
        'rgba_half.png': rgba_half(),
        'palette.png': png(32, 32, 3, 8, lambda x, y: ((x + y) % 3,), plte=[(255, 0, 0), (0, 255, 0), (0, 0, 255)]),
        'gray8.png': png(32, 32, 0, 8, lambda x, y: ((x * 8) % 256,)),
        'rgb16.png': png(32, 32, 2, 16, lambda x, y: (x * 2000, y * 2000, 65535)),
        'control.png': rgb8(32, 32),
        'wide.png': rgb8(512, 256),
        'noise.png': noise_png(1024),
    }
    for k, v in files.items():
        (src / k).write_bytes(v)
    fake_jpg(src, 'photo.jpg')
    order = ['rgba_half.png', 'palette.png', 'gray8.png', 'photo.jpg', 'rgb16.png', 'control.png', 'wide.png',
             'noise.png']
    sources = [str(src / n) for n in order]
    before = {p: md5(p) for p in sources}
    limit = 2 * tc.MIB  # 1024^2 noise is ~3 MiB raw; the limit stays a parameter
    opts = tc.format_options({'files': sources, 'out': str(tmp_path / 'out'), 'background': [0, 0, 0],
                              'max_bytes': limit})
    out, rows = tc.format_fix(sources, opts, lambda q: Path(q).read_bytes(), fake_decode)
    written = tc.write_outputs(ec, out, rows)
    rep = tc.format_report(ec, 'apply', out, rows, None, opts, written)
    assert {p: md5(p) for p in sources} == before
    assert len(written) == 8 and rep['plan']['skipped'] == []
    by = {Path(r['source']).name: r for r in rows}
    for w in written:  # 8 bits per channel, no alpha; palette (type 3) allowed: decision of Artem 05.11.2026
        info = cc.png_info(Path(w).read_bytes())
        assert info[2] == 8 and info[4] is False and info[3] in (2, 3), w
    assert cc.png_info(Path(by['palette.png']['out']).read_bytes())[3] == 3
    assert Path(by['palette.png']['out']).read_bytes() == files['palette.png']  # valid palette: unchanged
    img, _ = pixels(Path(by['rgba_half.png']['out']).read_bytes())
    assert img.px[(10 * 64 + 63) * 3:(10 * 64 + 64) * 3] == b'\x00\x00\x00'
    assert by['wide.png']['size_px'] == [512, 256] and 'not square 512x256' in by['wide.png']['notes'][0]
    noise = by['noise.png']
    assert noise['bytes_out'] <= limit and noise['rmse'] > 0 and noise['encoding'] == 'palette_quantized'
    assert noise['colours'] == 256 and noise['max_channel_error'] > 0
    assert Path(by['control.png']['out']).read_bytes() == files['control.png']
    assert by['photo.jpg']['out'].endswith('photo.png')
    ec.validate_report(rep)


# ---- tex.placeholders ---------------------------------------------------------------------------------
class SourcePlaceholders:
    """GeoAGR Make Diffuse/Normal/ERM as measured (GeoAGR.ms:42227/42308/42384, sizes GeoAGR.ms:14441)."""
    sizes = (256, 512, 1024, 2048, 4096)
    default = 4096

    @staticmethod
    def make(folder, name, size, colour):
        if size not in SourcePlaceholders.sizes:
            raise ValueError('size not offered')
        os.makedirs(folder, exist_ok=True)  # the typed folder is created...
        path = folder + name  # ...but the path is folder text + name without separator
        Path(path).write_bytes(tc.solid_png(size, colour))  # existing file overwritten silently
        return [path]


class AgrPlaceholders:
    default = tc.placeholder_options({})['sizes'][0]

    @staticmethod
    def make(folder, name, size, colour, on_exists='refuse'):
        opts = tc.placeholder_options({'folder': folder, 'address': 'Addr', 'sizes': [size],
                                       'colours': {'Diffuse': list(colour)}, 'on_exists': on_exists})
        rows = tc.placeholder_plan(opts)
        return tc.write_placeholders(ec, rows)


PIMPLS = [pytest.param('source', marks=pytest.mark.xfail(strict=True, reason='GeoAGR 13.64 as measured (RED)')),
          'agr']


def pimpl(name):
    return {'source': SourcePlaceholders, 'agr': AgrPlaceholders}[name]


@pytest.mark.parametrize('name', PIMPLS)
def test_P1_128_available_and_default_is_rule_value(tmp_path, name):
    assert pimpl(name).default == 256
    written = pimpl(name).make(str(tmp_path / 'maps') + os.sep, 'T_Addr_Diffuse_1.1001.png', 128, (1, 2, 3))
    assert cc.png_info(Path(written[0]).read_bytes())[:2] == (128, 128)


@pytest.mark.parametrize('name', PIMPLS)
def test_P2_existing_file_never_overwritten(tmp_path, name):
    folder = tmp_path / 'maps'
    folder.mkdir()
    old = folder / 'T_Addr_Diffuse_1.1001.png'
    old.write_bytes(b'old texture')
    pimpl(name).make(str(folder) + os.sep, old.name, 256, (9, 9, 9))
    assert old.read_bytes() == b'old texture'


@pytest.mark.parametrize('name', PIMPLS)
def test_P3_folder_without_trailing_separator_writes_inside(tmp_path, name):
    folder = tmp_path / 'maps'
    written = pimpl(name).make(str(folder), 'T_Addr_Diffuse_1.1001.png', 256, (9, 9, 9))
    assert all(Path(w).parent == folder for w in written)
    assert not list(tmp_path.glob('maps*.png'))


def test_P4_one_call_full_set_with_vpm_names(tmp_path):
    opts = tc.placeholder_options({'folder': str(tmp_path), 'address': 'Lenina_1', 'slots': [1, 2]})
    rows = tc.placeholder_plan(opts)
    assert [Path(r['path']).name for r in rows] == [
        'T_Lenina_1_Diffuse_1.1001.png', 'T_Lenina_1_ERM_1.1001.png', 'T_Lenina_1_Normal_1.1001.png',
        'T_Lenina_1_Diffuse_2.1001.png', 'T_Lenina_1_ERM_2.1001.png', 'T_Lenina_1_Normal_2.1001.png']
    g = tc.placeholder_options({'folder': str(tmp_path), 'address': 'X', 'ground': True})
    assert Path(tc.placeholder_plan(g)[0]['path']).name == 'T_X_Ground_Diffuse_1.1001.png'
    for k in ('X-1', 'Х'):
        with pytest.raises(ValueError):
            tc.placeholder_options({'address': k})


def test_placeholder_version_mode_and_average_colour(tmp_path):
    opts = tc.placeholder_options({'folder': str(tmp_path), 'address': 'A', 'on_exists': 'version'})
    first = tc.write_placeholders(ec, tc.placeholder_plan(opts))
    keep = {p: md5(p) for p in first}
    second = tc.write_placeholders(ec, tc.placeholder_plan(opts))
    assert [Path(p).name for p in second] == ['T_A_Diffuse_1.1001_v002.png', 'T_A_ERM_1.1001_v002.png',
                                              'T_A_Normal_1.1001_v002.png']
    assert {p: md5(p) for p in first} == keep
    img, _ = tc.decode_png(png(2, 2, 6, 8, lambda x, y: (100, 0, 0, 255) if x else (0, 0, 200, 0)))
    assert tc.average_colour(img) == [100, 0, 0]


def test_acceptance_placeholders(tmp_path):
    """Lab L03 minimal acceptance: slot 1, UDIM 1001, sizes 128 + 256, D [101,117,92], ERM [0,200,0], N default."""
    folder = str(tmp_path / 'maps')  # no trailing separator
    opts = tc.placeholder_options({'folder': folder, 'address': 'Addr', 'slots': [1], 'udim': 1001,
                                   'sizes': [128, 256], 'colours': {'Diffuse': [101, 117, 92], 'ERM': [0, 200, 0]}})
    rows = tc.placeholder_plan(opts)
    written = tc.write_placeholders(ec, rows)
    assert len(written) == 6
    want = {'Diffuse': (101, 117, 92), 'ERM': (0, 200, 0), 'Normal': (128, 128, 255)}
    for w in written:
        data = Path(w).read_bytes()
        assert Path(w).is_relative_to(tmp_path / 'maps')
        side = int(Path(w).parent.name)
        assert cc.png_info(data)[:5] == (side, side, 8, 2, False)
        img, _ = tc.decode_png(data)
        assert set(zip(*[iter(img.px)] * 3)) == {want[Path(w).name.split('_')[2]]}
    keep = {w: md5(w) for w in written}
    again = tc.placeholder_plan(opts)
    assert all('not overwritten' in r['reason'] for r in again) and tc.write_placeholders(ec, again) == []
    assert {w: md5(w) for w in written} == keep
    rep = tc.placeholder_report(ec, 'preview', opts, again, 'h')
    assert len(rep['plan']['skipped']) == 6 and rep['plan']['done'] == []


# ---- scene.missing_maps -------------------------------------------------------------------------------
def scene_tree(tmp_path):
    """Synthetic scene of the lab acceptance: maps + owners as the glue gives them."""
    f = tmp_path / 'proj'
    other, third = f / 'other', f / 'third'
    for d in (f, other, third):
        d.mkdir(parents=True, exist_ok=True)
    (f / 'T_ok_d_1.png').write_bytes(rgb8(64, 32))
    (other / 'T_one_d_1.png').write_bytes(rgb8(4, 4))
    (other / 'T_two_d_1.png').write_bytes(rgb8(4, 4))
    (third / 'T_two_d_1.tga').write_bytes(bytes([0, 0, 2]) + bytes(9) + struct.pack('<HH', 4, 4) + b'\x18\x00')
    (f / 'T_u_Diffuse_1.1001.png').write_bytes(rgb8(4, 4))
    (f / 'T_u_Diffuse_1.1003.png').write_bytes(rgb8(4, 4))

    def own(h, node, mat, hidden=False, ucx=False):
        return {'handle': h, 'node': node, 'material': mat, 'map': 'Map', 'hidden': hidden, 'ucx': ucx}
    maps = [
        {'path': str(f / 'T_ok_d_1.png'), 'owners': [own(1, 'SM_ok', 'M_ok')]},
        {'path': str(f / 'gone' / 'T_none_d_1.png'), 'owners': [own(2, 'SM_none', 'M_none')]},
        {'path': str(f / 'gone' / 'T_one_d_1.png'), 'owners': [own(3, 'SM_one', 'M_one')]},
        {'path': str(f / 'gone' / 'T_two_d_1.png'), 'owners': [own(4, 'SM_two', 'M_two')]},
        {'path': str(f / 'gone' / 'T_hid_d_1.png'), 'owners': [own(5, 'SM_hid', 'M_hid', hidden=True)]},
        {'path': str(f / 'gone' / 'T_ucx_d_1.png'), 'owners': [own(6, 'UCX_SM_x_Main_001', 'M_ucx', ucx=True)]},
        {'path': str(f / 'gone' / 'T_none_d_1.png'), 'owners': [own(7, 'SM_none2', 'M_none')]},
        {'path': str(f / 'T_u_Diffuse_1.<UDIM>.png'), 'owners': [own(8, 'SM_udim', 'M_udim')],
         'uv_tiles': [1001, 1002, 1003]},
    ]
    index = tc.candidate_index([str(f), str(other), str(third)])
    return f, maps, index


class SourceMissing:
    """GeoAGR Project Map as measured: rows from usedMaps (missing files are absent), hidden excluded, UCX
    dropped by Refresh, first existing candidate taken silently (GeoAGR.ms:1383)."""

    @staticmethod
    def rows(maps, index):
        out = []
        for m in maps:
            owners = [o for o in m['owners'] if not o['hidden'] and not o['ucx']]
            if not owners or '<UDIM>' in m['path'] or not os.path.isfile(m['path']):
                continue
            out.append({'path': m['path'], 'exists': True, 'owners': owners, 'candidates': [], 'ambiguous': False,
                        'hidden': False, 'ucx': False})
        return out


class AgrMissing:
    @staticmethod
    def rows(maps, index):
        return tc.missing_maps(maps, os.path.isfile, lambda p: Path(p).read_bytes()[:4096], index)


MIMPLS = [pytest.param('source', marks=pytest.mark.xfail(strict=True, reason='GeoAGR 13.64 as measured (RED)')),
          'agr']


def mimpl(name):
    return {'source': SourceMissing, 'agr': AgrMissing}[name]


@pytest.mark.parametrize('name', MIMPLS)
def test_M1_missing_maps_are_listed(tmp_path, name):
    f, maps, index = scene_tree(tmp_path)
    rows = mimpl(name).rows(maps, index)
    missing = {r['path'] for r in rows if not r['exists']}
    assert str(f / 'gone' / 'T_none_d_1.png') in missing and str(f / 'gone' / 'T_one_d_1.png') in missing


@pytest.mark.parametrize('name', MIMPLS)
def test_M2_hidden_and_ucx_included_with_flag(tmp_path, name):
    f, maps, index = scene_tree(tmp_path)
    rows = {Path(r['path']).name: r for r in mimpl(name).rows(maps, index)}
    assert rows['T_hid_d_1.png']['hidden'] and not rows['T_hid_d_1.png']['exists']
    assert rows['T_ucx_d_1.png']['ucx'] and not rows['T_ucx_d_1.png']['exists']


@pytest.mark.parametrize('name', MIMPLS)
def test_M3_two_candidates_ranked_and_ambiguous(tmp_path, name):
    f, maps, index = scene_tree(tmp_path)
    rows = {Path(r['path']).name: r for r in mimpl(name).rows(maps, index)}
    two = rows['T_two_d_1.png']
    assert two['ambiguous'] and [Path(c['path']).suffix for c in two['candidates']] == ['.png', '.tga']
    assert [c['rank'] for c in two['candidates']] == [0, 1]
    assert not rows['T_one_d_1.png']['ambiguous'] and len(rows['T_one_d_1.png']['candidates']) == 1


@pytest.mark.parametrize('name', MIMPLS)
def test_M5_udim_tiles_expanded_and_missing_tile_reported(tmp_path, name):
    f, maps, index = scene_tree(tmp_path)
    rows = [r for r in mimpl(name).rows(maps, index) if 'T_u_Diffuse' in r['path']]
    assert [(r['tile'], r['exists']) for r in rows] == [(1001, True), (1002, False), (1003, True)]


def test_M4_read_only_nothing_written_and_no_apply(tmp_path):
    f, maps, index = scene_tree(tmp_path)

    def tree():
        return sorted((str(p), p.stat().st_size, md5(p)) for p in tmp_path.rglob('*') if p.is_file())
    before = tree()
    rows = AgrMissing.rows(maps, index)
    rep = tc.missing_report(ec, rows, ec.fingerprint(rows), [])
    assert tree() == before and rep['plan']['read_only'] and rep['plan']['done'] == []
    rt_mod = _load(PKG / 'runtime.py', 'agr_tools_runtime_tex_t')
    with pytest.raises(ValueError, match='read-only'):
        rt_mod.edits_080('scene.missing_maps', 'apply', rep)


def test_acceptance_missing_maps(tmp_path):
    f, maps, index = scene_tree(tmp_path)
    rows = AgrMissing.rows(maps, index)
    rep = tc.missing_report(ec, rows, ec.fingerprint(rows), [(9, 'SM_nomaps')])
    paths = [r['path'] for r in rows]
    assert len(paths) == len(set(paths))  # each map once per path
    none = [r for r in rows if r['path'].endswith('T_none_d_1.png')][0]
    assert {o['node'] for o in none['owners']} == {'SM_none', 'SM_none2'} and none['candidates'] == []
    ok = [r for r in rows if r['path'].endswith('T_ok_d_1.png')][0]
    assert ok['exists'] and ok['size_px'] == [64, 32]
    tga = tc.image_size((f.parent / 'proj' / 'third' / 'T_two_d_1.tga').read_bytes())
    assert tga == [4, 4]
    objs = {o['name']: o for o in rep['objects']}
    assert objs['SM_nomaps']['findings'] == [] and objs['SM_ok']['findings'] == []
    assert all(objs[n]['findings'] for n in ('SM_none', 'SM_one', 'SM_two', 'SM_hid', 'UCX_SM_x_Main_001', 'SM_udim'))
    assert '[hidden]' in objs['SM_hid']['findings'][0]['detail'] and '[UCX]' in objs['UCX_SM_x_Main_001']['findings'][0]['detail']
    s = rep['plan']['summary']
    assert (s['missing'], s['ambiguous'], s['with_candidate']) == (6, 1, 2)
    assert rep['status'] == 'fail' and rep['plan']['table'][0].startswith('exists |')
    assert len(rep['plan']['table']) == 2 + len(rows)
    ec.validate_report(rep)


def test_uv_tiles_and_tile_paths():
    assert tc.uv_tiles([[(0.1, 0.1), (0.9, 0.1), (0.5, 0.9)], [(1.2, 0.2), (1.8, 0.2), (1.5, 0.8)],
                        [(0.2, 1.2), (0.8, 1.2), (0.5, 1.9)]]) == {1001, 1002, 1011}
    assert tc.tile_path(os.path.join('d', 'T_<UDIM>.png'), 1012) == os.path.join('d', 'T_1012.png')
    assert tc.tile_path(os.path.join('d', 'T_<UVTILE>.png'), 1012) == os.path.join('d', 'T_u2_v2.png')


# ---- glue through a fake pymxs (preview -> apply contract) -------------------------------------------
class _FakeRT:
    undefined = object()
    maxFilePath = ''
    selection = []

    @staticmethod
    def doesFileExist(p):
        return os.path.exists(p)


@pytest.fixture
def fake_pymxs(monkeypatch):
    mod = types.ModuleType('pymxs')
    mod.runtime = _FakeRT()
    monkeypatch.setitem(sys.modules, 'pymxs', mod)
    return mod.runtime


def _ctx(options):
    return types.SimpleNamespace(agr=None, core=tc, edit=ec, emax=None, options=options)


def test_glue_format_fix_preview_apply(tmp_path, fake_pymxs):
    src = tmp_path / 'src'
    src.mkdir()
    (src / 'T_a_d_1.png').write_bytes(rgba_half())
    (src / 'T_b_d_1.png').write_bytes(png(8, 8, 0, 16, lambda x, y: (x * 4000,)))
    prev = tm.tex_format_fix(_ctx({'folder': str(src), 'background': [1, 2, 3]}), 'preview', None, None)
    ec.check_preview('tex.format_fix', prev)
    out = Path(prev['plan']['out'])
    assert not out.exists() and out.name == 'AGR_format_fix' and len(prev['plan']['done']) == 2
    applied = tm.tex_format_fix(_ctx({}), 'apply', None, prev)
    assert sorted(Path(p).name for p in applied['plan']['written']) == ['T_a_d_1.png', 'T_b_d_1.png']
    assert all(cc.png_info(Path(p).read_bytes())[2:4] == (8, 2) for p in applied['plan']['written'])
    with pytest.raises(ec.StalePreview):  # second apply of the same preview: outputs now exist -> state differs
        tm.tex_format_fix(_ctx({}), 'apply', None, prev)
    prev2 = tm.tex_format_fix(_ctx({'folder': str(src), 'background': [1, 2, 3]}), 'preview', None, None)
    assert Path(prev2['plan']['out']).name == 'AGR_format_fix_v002'
    (src / 'T_a_d_1.png').write_bytes(rgb8(4, 4))  # source changed after the preview
    with pytest.raises(ec.StalePreview, match='changed'):
        tm.tex_format_fix(_ctx({}), 'apply', None, prev2)


def test_glue_placeholders_preview_apply(tmp_path, fake_pymxs):
    folder = tmp_path / 'Maps'
    prev = tm.tex_placeholders(_ctx({'folder': str(folder), 'address': 'Addr', 'sizes': [128]}), 'preview', None, None)
    assert not folder.exists() and len(prev['plan']['done']) == 3
    applied = tm.tex_placeholders(_ctx({}), 'apply', None, prev)
    assert len(applied['plan']['written']) == 3 and all(Path(p).parent == folder for p in applied['plan']['written'])
    with pytest.raises(ec.StalePreview):
        tm.tex_placeholders(_ctx({}), 'apply', None, prev)
    with pytest.raises(ValueError, match='not saved'):
        tm.tex_placeholders(_ctx({'address': 'Addr'}), 'preview', None, None)
    with pytest.raises(ValueError, match='address unknown'):
        tm.tex_placeholders(_ctx({'folder': str(folder)}), 'preview', [], None)


def test_options_validation():
    for bad in ({'max_bytes': 10}, {'profile': 'x'}, {'background': [1, 2]}, {'nope': 1}, {'max_side': 0}):
        with pytest.raises(ValueError):
            tc.format_options(bad)
    for bad in ({'sizes': [100]}, {'udim': 999}, {'slots': [0]}, {'on_exists': 'overwrite'}, {'colours': {'X': [1, 1, 1]}}):
        with pytest.raises(ValueError):
            tc.placeholder_options(bad)
    assert tc.format_options({})['max_bytes'] == 3 * 1024 * 1024
