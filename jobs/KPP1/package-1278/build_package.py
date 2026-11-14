"""new-case: publish immutable KPP1 R1 placed-package copies under decision D285.

Usage: uv run python jobs/KPP1/package-1278/build_package.py SOURCE NEW_OUTPUT
SOURCE is #1271's approved transform applied to latest rerun-1230 R1 v003;
source copies and hashes are recorded in source-r1-v003-SHA256SUMS.txt.
Successful assembly is NOT validation, SINTEZ certification or delivery acceptance.
"""
import argparse
import hashlib
import json
from pathlib import Path

EXPECTED = {
    '0000_Kpp_1.zip': 'cd90142217ae4cf38f0330262c7daf5daae9e5ca19960511d6d98d9aeb0480b0',
    'SM_Kpp_1.zip': '40d0615b2e4390175efa7903d6793ae0514998bacb506c327a3753d1686f597c',
    'SM_Kpp_1.geojson': '4dffaca25627b281395d5ffb82c3065dd58356ea052db03b4a2c55600bcea96d',
}
PLACEMENT = ('approximate, ±0.1 m, fitted to customer NPM 0607_77_05_0009005_117_02; '
             'entrance orientation not independently confirmed')


def digest(data):
    return hashlib.sha256(data).hexdigest()


import re
import struct
import io
import zipfile


def fix_geojson(data):
    """Keep semantic values; repair only the pinned coordinate's literal precision."""
    text = data.decode('utf-8')
    before = json.loads(text)
    point = before['features'][0]['geometry']['coordinates']
    if point != [8056.144, -9581.270]:
        raise ValueError('unsupported GeoJSON insertion point')
    text, count = re.subn(r'"coordinates"\s*:\s*\[\s*8056\.144\s*,\s*-9581\.270?\s*\]',
                         '"coordinates": [8056.144, -9581.270]', text)
    if count != 1 or json.loads(text) != before:
        raise ValueError('unsupported/duplicate GeoJSON coordinates')
    return text.encode('utf-8')


def fix_npm_glass(data):
    """Rewrite just three FBX 7400 material properties, preserving raw mesh bytes.

    FBX element end offsets are absolute, so shortening the material name also
    requires updating ancestor/following element headers. Property payloads,
    including compressed geometry/UV arrays and embedded images, are untouched
    except the named material and its Opacity/TransparencyFactor double values.
    This narrow job-local codec is not a general FBX exporter.
    """
    if data[:23] != b'Kaydara FBX Binary  \x00\x1a\x00' or data[23:27] != struct.pack('<I', 7400):
        raise ValueError('unsupported FBX: binary 7400 required')
    old = b'M_Kpp_1_MainGlass_1\x00\x01Material'
    new = b'M_Glass_01\x00\x01Material'
    counts = [0, 0, 0]

    def string(value):
        return b'S' + struct.pack('<I', len(value)) + value

    def rewrite(pos, newpos, glass=False):
        if pos + 13 > len(data):
            raise ValueError('partial FBX header')
        end, count, size, namelen = struct.unpack_from('<IIIB', data, pos)
        first = pos + 13 + namelen
        childpos = first + size
        if not pos < childpos <= end <= len(data):
            raise ValueError('partial FBX element')
        name = data[pos+13:first]
        props = data[first:childpos]
        if name == b'Material' and string(old) in props:
            if props.count(string(old)) != 1:
                raise ValueError('duplicate glass material name')
            props = props.replace(string(old), string(new))
            counts[0] += 1
            glass = True
        if glass and name == b'P':
            for idx, key in enumerate((b'Opacity', b'TransparencyFactor'), 1):
                if props.startswith(string(key)):
                    if props[-9:-8] != b'D':
                        raise ValueError('unsupported glass property: ' + key.decode())
                    value = struct.unpack('<d', props[-8:])[0]
                    if not 0 <= value <= 1:
                        raise ValueError('invalid glass property: ' + key.decode())
                    props = props[:-8] + struct.pack('<d', .5)
                    counts[idx] += 1
        body = name + props
        while childpos < end:
            if data[childpos:childpos+13] == bytes(13):
                if childpos + 13 != end:
                    raise ValueError('unsupported FBX sentinel')
                body += bytes(13)
                childpos += 13
            else:
                chunk, childpos = rewrite(childpos, newpos + 13 + len(body), glass)
                body += chunk
        return struct.pack('<IIIB', newpos + 13 + len(body), count, len(props), namelen) + body, end

    pos = 27
    output = data[:27]
    while pos + 13 <= len(data) and data[pos:pos+13] != bytes(13):
        chunk, pos = rewrite(pos, len(output))
        output += chunk
    if data[pos:pos+13] != bytes(13) or counts != [1, 1, 1]:
        raise ValueError('unmapped/duplicate glass properties: ' + repr(counts))
    return output + data[pos:]


def fix_placeholder_png(name, data):
    """Reduce only proven single-colour R1 tiles; never resample texture detail."""
    from PIL import Image
    if not re.fullmatch(r'T_Kpp_1_(Diffuse|ERM|Normal)_1\.100[4-7]\.png', name):
        raise ValueError('unmapped placeholder: ' + name)
    try:
        with Image.open(io.BytesIO(data)) as image:
            if image.format != 'PNG' or image.mode != 'RGB' or image.size not in ((2048, 2048), (256, 256)):
                raise ValueError('unsupported placeholder: ' + name)
            if any(lo != hi for lo, hi in image.getextrema()):
                raise ValueError('nonflat texture cannot be replaced: ' + name)
            result = io.BytesIO()
            Image.new('RGB', (256, 256), image.getpixel((0, 0))).save(result, format='PNG')
            return result.getvalue()
    except OSError as exc:
        raise ValueError('invalid PNG input: ' + name) from exc


def repair_artifacts(blobs):
    """Repair copied archives deterministically, retaining every original member."""
    fixed_geojson = fix_geojson(blobs['SM_Kpp_1.geojson'])
    result = {'SM_Kpp_1.geojson': fixed_geojson}
    for name in ('0000_Kpp_1.zip', 'SM_Kpp_1.zip'):
        stream = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(blobs[name])) as source:
            names = source.namelist()
            required = ['0000_Kpp_1_01.fbx'] if name.startswith('0000') else ['SM_Kpp_1.geojson']
            if len(names) != len(set(names)) or any(n not in names for n in required):
                raise ValueError('duplicate/missing package input members: ' + name)
            with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as dest:
                for info in source.infolist():
                    payload = source.read(info)
                    if info.filename == '0000_Kpp_1_01.fbx':
                        payload = fix_npm_glass(payload)
                    elif info.filename == 'SM_Kpp_1.geojson':
                        if payload != blobs['SM_Kpp_1.geojson']:
                            raise ValueError('conflicting GeoJSON inputs')
                        payload = fixed_geojson
                    elif re.fullmatch(r'T_Kpp_1_(Diffuse|ERM|Normal)_1\.100[4-7]\.png', info.filename):
                        payload = fix_placeholder_png(info.filename, payload)
                    dest.writestr(info, payload)
        result[name] = stream.getvalue()
    return result


def build(source, output):
    """Snapshot all pinned inputs before exclusive output creation; never overwrite.

    ZIP member inventory and all geometry payloads remain unchanged. Only NPM
    glass material name/alpha and VPM coordinate literal precision are repaired.
    Ancillary source diagnostics are not package inputs. Reports and hashes live
    inside the newly reserved directory, with no shared temp names. A failed
    write leaves incomplete evidence, never a pass receipt.
    """
    source, output = Path(source).resolve(), Path(output).resolve()
    if output.is_relative_to(source) or source.is_relative_to(output):
        raise ValueError('output aliases source or its directory tree')
    if output.exists():
        raise ValueError('output already exists: ' + str(output))
    blobs = {}
    for name, expected in EXPECTED.items():
        path = source / name
        if not path.is_file():
            raise ValueError('missing input: ' + name)
        data = path.read_bytes()
        if digest(data) != expected:
            raise ValueError('input hash mismatch: ' + name)
        blobs[name] = data
    # Detect a second writer before any output. The bytes we publish are the
    # validated snapshot, not a later reread/copyfile of a mutable input.
    for name, expected in EXPECTED.items():
        if digest((source / name).read_bytes()) != expected:
            raise ValueError('input changed during snapshot: ' + name)
    repaired = repair_artifacts(blobs)
    output.mkdir()  # atomic exclusive directory claim; no exist_ok, no cleanup
    for name, data in repaired.items():
        with (output / name).open('xb') as stream:
            stream.write(data)
    receipt = {
        'decision': 'D285', 'source_decision': 'D262',
        'source_sha256': EXPECTED, 'placement': PLACEMENT,
        'zero_abs_m': 171.050, 'point_msk77': [8056.144, -9581.270],
        'ground': 'missing; Ground author',
        'areas': 'missing KPP1-specific schedule; Artem',
        'fno': 'empty pending SINTEZ',
        'passed': False,
        'note': 'assembly only; run validate_package --scene on both ZIPs',
    }
    with (output / 'assembly.json').open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(receipt, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    hashes = {name: digest(data) for name, data in repaired.items()}
    hashes['assembly.json'] = digest((output / 'assembly.json').read_bytes())
    with (output / 'SHA256SUMS.txt').open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(''.join(f'{sha}  {name}\n' for name, sha in sorted(hashes.items())))
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    build(args.source, args.output)
    print('assembled 3 immutable artifacts; delivery passed=false')
