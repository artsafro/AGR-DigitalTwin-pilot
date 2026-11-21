"""new-case: D288 attribute-only KPP1 VPM package v008 from the delivered customer GeoJSON.

Usage: uv run python jobs/KPP1/delivered-1371/build_v008.py BASE_VPM_ZIP DELIVERED_002_ZIP NEW_OUTPUT_DIR

BASE_VPM_ZIP is package-v006 `SM_Kpp_1.zip` (#1278, sha256 pinned); DELIVERED_002_ZIP is the
read-only customer archive `SM_77_05_0009005_117_002.zip` (sha256 pinned). Per [D288] only
FNO_code, FNO_name, s_obsh, s_naz and spp_gns are copied from the delivered `_002` GeoJSON;
s_podz stays empty (unknown), heights stay R1 171.05 / 8.65 / 179.70 [D262]/[D279]. Every other
ZIP member is copied byte-identical. The NPM ZIP and the delivered Ground are NOT touched here:
the Ground is not ready [D288]. Assembly is not validation or delivery acceptance.
"""
import argparse
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[3]
BASE_SHA256 = '6c6b03b4e12c942eda4bbae4d2a543efc6319f6af770da5a9854ac56e2a0947d'
DELIVERED_SHA256 = 'caef3a21acdb8aee1fee9e496e26bd9f9adaeef2a17272e8189bb634aee13ecf'
DELIVERED_MEMBER = 'SM_77_05_0009005_117_002.geojson'
MEMBER = 'SM_Kpp_1.geojson'
TEXT_FIELDS = ('FNO_code', 'FNO_name')
AREA_FIELDS = ('s_obsh', 's_naz', 'spp_gns')
R1_HEIGHTS = {'h_relief': 171.05, 'h_otn': 8.65, 'h_abs': 179.7}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _props(data: bytes, label: str) -> dict:
    doc = json.loads(data.decode('utf-8-sig'))
    features = doc.get('features') if isinstance(doc, dict) else None
    if not isinstance(features, list) or len(features) != 1:
        raise ValueError(f'{label}: expected exactly one feature')
    props = features[0].get('properties')
    if not isinstance(props, dict):
        raise ValueError(f'{label}: properties missing')
    return props


def _decimals(value: float) -> int:
    text = repr(float(value))
    return len(text.split('.')[1].rstrip('0')) if '.' in text and 'e' not in text else 99


def delivered_values(data: bytes) -> dict:
    """Return the five D288 fields from the delivered `_002` GeoJSON; fail closed on anything odd."""
    props = _props(data, DELIVERED_MEMBER)
    out = {}
    for key in TEXT_FIELDS + AREA_FIELDS + ('s_podz',):
        if key not in props:
            raise ValueError(f'delivered {key} missing')
    for key in TEXT_FIELDS:
        value = props[key]
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f'delivered {key} empty or not text: {value!r}')
        out[key] = value
    for key in AREA_FIELDS:
        value = props[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f'delivered {key} not a number: {value!r}')
        if not math.isfinite(value) or value <= 0 or _decimals(value) > 2:
            raise ValueError(f'delivered {key} not a finite positive area with <= 2 decimals: {value!r}')
        out[key] = value
    if props['s_podz'] != '':
        raise ValueError(f'delivered s_podz {props["s_podz"]!r}: D288 expects it unknown; new data needs a decision')
    sys.path.insert(0, str(ROOT / 'src'))
    from twinqa import fno
    problems = fno.check(out['FNO_code'], out['FNO_name'])
    if problems:
        raise ValueError(f'delivered FNO not in classifier: {problems}')
    return out


def patch_geojson(data: bytes, values: dict) -> bytes:
    """Replace the five empty `"key": ""` lines once each; keep every other byte."""
    before = _props(data, MEMBER)
    for key, expected in R1_HEIGHTS.items():
        if before.get(key) != expected:
            raise ValueError(f'base {key} {before.get(key)!r} != R1 {expected} [D262]')
    if before.get('s_podz') != '':
        raise ValueError('base s_podz is not empty')
    text = data.decode('utf-8')
    for key, value in values.items():
        if before.get(key) != '':
            raise ValueError(f'base {key} already set: {before.get(key)!r}')
        pattern = re.compile(r'^(\s*)"' + re.escape(key) + r'": "",(\r?)$', re.M)
        if len(pattern.findall(text)) != 1:
            raise ValueError(f'base {key}: expected exactly one empty line')
        literal = json.dumps(value, ensure_ascii=False)
        text = pattern.sub(lambda m: f'{m.group(1)}"{key}": {literal},{m.group(2)}', text)
    result = text.encode('utf-8')
    after = _props(result, MEMBER)
    if list(after) != list(before):
        raise ValueError('property order changed')
    changed = {k for k in before if before[k] != after[k]}
    if changed != set(values) or any(after[k] != v for k, v in values.items()):
        raise ValueError(f'unexpected property changes: {sorted(changed)}')
    return result


def build(base: Path, delivered: Path, output: Path, base_sha: str = BASE_SHA256,
          delivered_sha: str = DELIVERED_SHA256) -> dict:
    base, delivered, output = Path(base), Path(delivered), Path(output)
    out_r = output.resolve()
    for src in (base, delivered):
        src_r = src.resolve()
        if out_r == src_r or out_r in src_r.parents:
            raise ValueError(f'output {output} aliases or contains input {src}')
    if output.exists():
        raise ValueError(f'output exists: {output}')
    partial = Path(str(output) + '.partial')
    if partial.exists():
        raise ValueError(f'partial exists: {partial}')
    base_bytes, delivered_bytes = base.read_bytes(), delivered.read_bytes()
    if sha256(base_bytes) != base_sha:
        raise ValueError(f'base sha256 {sha256(base_bytes)} != pinned {base_sha}')
    if sha256(delivered_bytes) != delivered_sha:
        raise ValueError(f'delivered sha256 {sha256(delivered_bytes)} != pinned {delivered_sha}')
    with zipfile.ZipFile(io.BytesIO(delivered_bytes)) as archive:
        values = delivered_values(archive.read(DELIVERED_MEMBER))
    stream = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(base_bytes)) as src, zipfile.ZipFile(stream, 'w') as dst:
        names = src.namelist()
        if names.count(MEMBER) != 1 or len(set(names)) != len(names):
            raise ValueError(f'base members: expected one {MEMBER} and no duplicates')
        geojson = patch_geojson(src.read(MEMBER), values)
        for info in src.infolist():
            data = geojson if info.filename == MEMBER else src.read(info.filename)
            copy = zipfile.ZipInfo(info.filename, info.date_time)
            copy.compress_type, copy.external_attr = info.compress_type, info.external_attr
            dst.writestr(copy, data)
    package = stream.getvalue()
    with zipfile.ZipFile(io.BytesIO(package)) as check:
        if check.namelist() != names or check.read(MEMBER) != geojson or check.testzip() is not None:
            raise ValueError('readback of new package failed')
    partial.mkdir(parents=True)
    (partial / 'SM_Kpp_1.zip').write_bytes(package)
    (partial / MEMBER).write_bytes(geojson)
    record = {'decision': 'D288', 'base': {'path': str(base), 'sha256': base_sha},
              'delivered': {'path': str(delivered), 'member': DELIVERED_MEMBER, 'sha256': delivered_sha},
              'applied': values, 'kept': {**R1_HEIGHTS, 's_podz': ''},
              'npm': 'not built: delivered Ground not ready [D288]; NPM stays package-v006'}
    (partial / 'assembly.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
    sums = ''.join(f'{sha256((partial / n).read_bytes())}  {n}\n'
                   for n in ('SM_Kpp_1.zip', MEMBER, 'assembly.json'))
    (partial / 'SHA256SUMS.txt').write_text(sums, encoding='utf-8')
    os.replace(partial, output)
    return record


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('base', type=Path)
    parser.add_argument('delivered', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--base-sha', default=BASE_SHA256)
    parser.add_argument('--delivered-sha', default=DELIVERED_SHA256)
    args = parser.parse_args(argv)
    try:
        record = build(args.base, args.delivered, args.output, args.base_sha, args.delivered_sha)
    except (ValueError, OSError, KeyError, zipfile.BadZipFile) as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 1
    print(json.dumps(record['applied'], ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
