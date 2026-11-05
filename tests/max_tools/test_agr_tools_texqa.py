"""new-case: AGR Tools 0.9 (#979) branch B: tex.erm_normal_check core (texqa_core.py), plain pytest.

Defects named in #979 §1 are RED on a behaviour model of the GeoAGR normal-map decision (`GeoAGR.ms:1685`
`-threshold 50%`, `render_map_bump` `GeoAGR.ms:2188-2216`, runtime finding R02: 128 -> 255, a 32-colour palette
decision, the extension trusted, no DirectX and no ERM check). The model is written from the measurements, no
GeoAGR code (#853). GREEN on texqa_core. Acceptance set of #979 §1 is generated here (stdlib PNG).
"""
import hashlib
import importlib.util
import math
import struct
import sys
import zlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / 'adapters/max/agr_tools'


def _load(name, alias):
    spec = importlib.util.spec_from_file_location(alias, PKG / name)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[alias] = mod
    spec.loader.exec_module(mod)
    return mod


tq = _load('texqa_core.py', 'agr_tools_texqa_core_t')


def red_green(prop, source, impl):
    assert not prop(source()), 'source model already satisfies the property: not a regression'
    assert prop(impl())


# ---- synthetic pictures ---------------------------------------------------------------------------------
def png(w, h, px, channels, depth=8):
    if depth == 8:
        return tq.write_png(w, h, px, channels)
    ctype = {1: 0, 3: 2, 4: 6}[channels]
    stride = w * channels
    raw = b''
    for y in range(h):
        row = px[y * stride:(y + 1) * stride]
        raw += b'\x00' + b''.join(struct.pack('>H', v * 257) for v in row)

    def chunk(k, b):
        return struct.pack('>I', len(b)) + k + b + struct.pack('>I', zlib.crc32(k + b) & 0xffffffff)
    return (tq.PNG_SIG + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 16, ctype, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b''))


def flat_normal(size=64, alpha=None):
    n = 3 if alpha is None else 4
    px = bytes((128, 128, 255) + (() if alpha is None else (alpha,))) * (size * size)
    return png(size, size, px, n)


def dome(size=96, directx=True, radius=0.42):
    """Hemispherical bump in the middle; OpenGL encodes G = +dh/dy_img, DirectX inverts G."""
    px = bytearray()
    c = (size - 1) / 2.0
    R = radius * size
    for y in range(size):
        for x in range(size):
            dx, dy = (x - c) / R, (y - c) / R
            r2 = dx * dx + dy * dy
            if r2 < 0.98:
                hz = math.sqrt(1.0 - r2)
                # h = sqrt(1 - r^2): dh/dx = -dx/hz, dh/dy_img = -dy/hz; OpenGL n = (-dh/dx, -dh/dv, 1) with
                # v = -y_img, so -dh/dv = dh/dy_img = -dy/hz
                nx, gl_g = dx / hz, -dy / hz
                ln = math.sqrt(nx * nx + gl_g * gl_g + 1.0)
                nx, gl_g, nz = nx / ln, gl_g / ln, 1.0 / ln
            else:
                nx, gl_g, nz = 0.0, 0.0, 1.0
            g = -gl_g if directx else gl_g
            px += bytes((int(round((nx + 1) * 127.5)), int(round((g + 1) * 127.5)), int(round((nz + 1) * 127.5))))
    return png(size, size, bytes(px), 3)


def erm(r, g, b, size=32, glow_box=None):
    px = bytearray()
    for y in range(size):
        for x in range(size):
            rr = r
            if glow_box and glow_box[0] <= x < glow_box[2] and glow_box[1] <= y < glow_box[3]:
                rr = 200
            px += bytes((rr, g, b))
    return png(size, size, bytes(px), 3)


def jpeg_named_png():
    # minimal JPEG header with SOF0 64x64 (enough for the signature and size)
    sof = b'\xff\xc0' + struct.pack('>HBHHB', 11, 8, 64, 64, 1) + b'\x01\x11\x00'
    return b'\xff\xd8\xff\xe0' + struct.pack('>H', 16) + b'JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00' + sof + b'\xff\xd9'


def codes(res):
    return sorted({c for c, _ in res['findings']})


# ---- source behaviour model (GeoAGR, measured R02) ------------------------------------------------------
def geoagr_model(name, data):
    """Normal-map decision as measured: trust the extension, binarise every channel at 50 % (128 -> 255),
    look the binarised picture up in a 32-colour palette; a normal map must be mostly (0..127 R, 0..127 G, 255 B)
    after binarising. No DirectX check, no ERM check."""
    if not name.lower().endswith('.png'):
        return {'normal': False, 'findings': ['not png']}
    try:
        pic = tq.read_png(data)
    except ValueError:
        return {'normal': False, 'findings': []}  # JPEG named .png: identify reads it, no format finding
    bins = {}
    for i in range(0, len(pic.px), pic.n):
        key = tuple(255 if v >= 128 else 0 for v in pic.px[i:i + 3])
        bins[key] = bins.get(key, 0) + 1
    dominant = max(bins, key=bins.get)
    return {'normal': dominant == (0, 0, 255), 'findings': []}


def impl(name, data, role='normal', emissive=False):
    return tq.check_file(name, data, role, emissive)


# ---- regressions ----------------------------------------------------------------------------------------
def test_flat_normal_is_recognised_not_binarised():
    """R02: `-threshold 50%` turns 128 into 255, the flat #8080FF is not a normal map for GeoAGR."""
    data = flat_normal()
    red_green(lambda r: r is True,
              lambda: geoagr_model('T_A_Normal_1.1001.png', data)['normal'],
              lambda: codes(impl('T_A_Normal_1.1001.png', data)) == [])


def test_opengl_dome_fails_directx_dome_passes():
    gl, dx = dome(directx=False), dome(directx=True)
    red_green(lambda r: r == ['normal_opengl'],
              lambda: geoagr_model('a.png', gl)['findings'],
              lambda: codes(impl('a.png', gl)))
    res = impl('b.png', dx)
    assert codes(res) == [] and res['orientation'] == 'directx', res


def test_jpeg_named_png_is_a_format_failure():
    data = jpeg_named_png()
    red_green(lambda r: r == ['format_mismatch'],
              lambda: geoagr_model('T_A_Normal_1.1001.png', data)['findings'],
              lambda: codes(impl('T_A_Normal_1.1001.png', data)))
    assert tq.jpeg_size(data) == (64, 64)


def test_erm_false_emission_and_grey_erm_fail_clean_erm_passes():
    clean, glow, grey = erm(0, 140, 0), erm(0, 140, 0, glow_box=(4, 4, 12, 12)), erm(120, 120, 120)
    red_green(lambda r: r == ['erm_false_emission'],
              lambda: geoagr_model('T_A_ERM_1.1001.png', glow)['findings'],
              lambda: codes(impl('T_A_ERM_1.1001.png', glow, 'erm')))
    assert codes(impl('x.png', grey, 'erm')) == ['erm_grey']
    assert codes(impl('x.png', clean, 'erm')) == []
    # declared emission in the material: R is allowed
    assert codes(impl('x.png', glow, 'erm', emissive=True)) == []


def test_normal_with_alpha_and_16_bit_are_reported():
    assert codes(impl('n.png', flat_normal(alpha=255))) == ['alpha_channel']
    px16 = bytes((128, 128, 255)) * (16 * 16)
    assert 'bit_depth' in codes(impl('n.png', png(16, 16, px16, 3, depth=16)))


def test_grey_or_offset_flat_is_not_a_normal_map():
    grey = png(32, 32, bytes((128, 128, 128)) * 1024, 3)
    assert 'normal_not_unit' in codes(impl('n.png', grey))
    off = png(32, 32, bytes((140, 128, 250)) * 1024, 3)
    assert 'normal_flat_offset' in codes(impl('n.png', off))


def test_ridge_without_curl_signal_is_ambiguous_not_pass():
    """A 1-D ramp (gradient only along x) has zero curl in both conventions: ambiguous, never a pass."""
    size = 48
    px = bytearray()
    for y in range(size):
        for x in range(size):
            nx = math.sin(x / 3.0) * 0.5
            nz = math.sqrt(1 - nx * nx)
            px += bytes((int(round((nx + 1) * 127.5)), 128, int(round((nz + 1) * 127.5))))
    res = impl('n.png', png(size, size, bytes(px), 3))
    assert codes(res) == ['normal_orientation_unknown'], res
    assert 'normal_orientation_unknown' in tq.AMBIGUOUS


def test_missing_and_unreadable():
    assert codes(impl('gone.png', None)) == ['missing_file']
    assert codes(impl('bad.png', tq.PNG_SIG + b'garbage')) == ['unreadable']


def test_sources_are_not_changed(tmp_path):
    files = {'flat.png': flat_normal(), 'gl.png': dome(directx=False), 'erm.png': erm(0, 100, 0),
             'jpg.png': jpeg_named_png()}
    before = {}
    for name, data in files.items():
        (tmp_path / name).write_bytes(data)
        before[name] = hashlib.md5(data).hexdigest()
    for name in files:
        role = 'erm' if name == 'erm.png' else 'normal'
        tq.check_file(str(tmp_path / name), (tmp_path / name).read_bytes(), role)
    assert {n: hashlib.md5((tmp_path / n).read_bytes()).hexdigest() for n in files} == before


def test_png_roundtrip_reader_writer():
    px = bytes(range(0, 48)) * 4
    for ch in (1, 3, 4):
        w = 8
        h = len(px) // (w * ch)
        data = tq.write_png(w, h, px[:w * h * ch], ch)
        pic = tq.read_png(data)
        assert (pic.w, pic.h, pic.n, pic.px) == (w, h, ch, px[:w * h * ch])
    assert tq.write_png(2, 1, b'\x01\x02\x03\x04\x05\x06', 3) == tq.write_png(2, 1, b'\x01\x02\x03\x04\x05\x06', 3)


def test_role_of_names():
    assert tq.role_of('T_Addr_Normal_1.1001.png') == 'normal'
    assert tq.role_of('T_Addr_ERM_2.1003.png') == 'erm'
    assert tq.role_of('T_Addr_001_Main_n_1.png') == 'normal'
    assert tq.role_of('T_Addr_Diffuse_1.1001.png') is None
    assert tq.role_of('whatever.png', 'bumpMap') == 'normal'


@pytest.mark.parametrize('fmt,data', [('tga', b'\x00\x00\x02' + b'\x00' * 13 + b'\x18\x00'), ('bmp', b'BM' + b'\x00' * 20)])
def test_sniff(fmt, data):
    assert tq.sniff(data) == fmt
