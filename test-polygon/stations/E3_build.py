"""new-case: polygon station builder of branch E3 (#979): export.zip, qa.package, export.geojson_write stations.

`make(obj, rt) -> node` (build/build_scene.py): a small marker box named after the archive/report object; a marker
with `extra.writes` ({folder: kind}) also writes the synthetic delivery files of those folders
(C:/x/test-polygon/e3/..., outside the repository, like FBX_DIR). Everything is synthetic and stdlib only;
`delivery_files(kind)` is pure, so the unit tests check the same bytes the live run uses.
"""
import base64
import json
import os
import struct
import zipfile
import zlib
from io import BytesIO
from pathlib import Path

POLY = Path(__file__).resolve().parents[1]
FBX = b'Kaydara FBX Binary  \x00\x1a\x00' + struct.pack('<I', 7400) + b'\x00' * 64
MAPS = {'Diffuse': (120, 110, 100), 'ERM': (0, 170, 0), 'Normal': (128, 128, 255)}
# 256x256 flat JPEG (quality 60), the GeoJSON preview picture (reg p.54); made once with Pillow, embedded here.
JPEG_256 = base64.b64decode(
    '/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAA0JCgsKCA0LCgsODg0PEyAVExISEyccHhcgLikxMC4pLSwzOko+MzZGNywtQFdBRkxO'
    'UlNSMj5aYVpQYEpRUk//2wBDAQ4ODhMREyYVFSZPNS01T09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09P'
    'T09PT09PT0//wAARCAEAAQADASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUF'
    'BAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVW'
    'V1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi'
    '4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAEC'
    'AxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVm'
    'Z2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq'
    '8vP09fb3+Pn6/9oADAMBAAIRAxEAPwCzRRRWZYUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRR'
    'QAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUU'
    'UUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAF'
    'FFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFA'
    'BRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRR'
    'QAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUU'
    'UUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAF'
    'FFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFA'
    'BRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRR'
    'QAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUU'
    'UUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAF'
    'FFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFA'
    'BRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRR'
    'QAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQB//'
    '2Q=='
)


def png_flat(colour, size=256):
    """8-bit RGB PNG of one colour (stdlib zlib)."""
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff)
    row = b'\x00' + bytes(colour) * size
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', size, size, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(row * size)) + chunk(b'IEND', b''))


def _geojson():
    return (POLY / 'geojson' / 'valid_oks.geojson').read_bytes()


def _vpm_set(stem):
    files = {stem + '.fbx': FBX, stem + '.geojson': _geojson()}
    for kind, colour in MAPS.items():
        files['T_{}_{}_1.1001.png'.format(stem[3:], kind)] = png_flat(colour)
    return files


def _zip(files):
    b = BytesIO()
    with zipfile.ZipFile(b, 'w', zipfile.ZIP_DEFLATED) as z:
        for name, data in files.items():
            z.writestr(name, data)
    return b.getvalue()


def delivery_files(kind):
    """{file name: bytes} of one station folder.

    zip: address ZipOk, NPM `0813_ZipOk_01` + `_Ground` (a complete archive) and a VPM OKS set without GeoJSON and
    PNG (its archive has findings), plus a decoy. pkg: `SM_PkgOk.zip` (complete VPM set) and `SM_PkgBad.zip`
    (a `../` member: V001 zip_traversal). geojson: the 256x256 preview JPG."""
    if kind == 'zip':
        return {'0813_ZipOk_01.fbx': FBX, '0813_ZipOk_Ground.fbx': FBX, 'SM_ZipOk.fbx': FBX, 'notes.txt': b'decoy'}
    if kind == 'pkg':
        good = _vpm_set('SM_PkgOk')
        bad = _vpm_set('SM_PkgBad')
        bad['../SM_PkgBad_Light.fbx'] = FBX
        return {'SM_PkgOk.zip': _zip(good), 'SM_PkgBad.zip': _zip(bad)}
    if kind == 'geojson':
        return {'preview.jpg': JPEG_256}
    raise ValueError('unknown E3 station kind: ' + repr(kind))


def write_files(folder, files):
    """Write the synthetic files; a file with other bytes is replaced (this folder is the polygon's own)."""
    os.makedirs(folder, exist_ok=True)
    for name, data in files.items():
        path = os.path.join(folder, name)
        if os.path.isfile(path):
            with open(path, 'rb') as fh:
                if fh.read() == data:
                    continue
        with open(path, 'wb') as fh:
            fh.write(data)


def make(obj, rt):
    for folder, kind in sorted(((obj.get('extra') or {}).get('writes') or {}).items()):
        write_files(folder, delivery_files(kind))
    node = rt.Box(name=obj['name'], length=1.0, width=1.0, height=0.5)
    node.pos = rt.Point3(*[float(v) for v in obj['pos']])
    return node


if __name__ == '__main__':  # print the station folders for a dry look
    print(json.dumps({k: sorted(delivery_files(k)) for k in ('zip', 'pkg', 'geojson')}, indent=1))
