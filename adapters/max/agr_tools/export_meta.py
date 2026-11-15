"""new-case: dependency-free export metadata contract for shared DCC exporters (#1361).

Schema: schemas/ExportMeta.schema.json. Historical three-field metadata remains readable;
new producers add profile, exported_files and per-field provenance. Unknown is explicit,
not an inferred zero, thumbnail or legal address. Packaging does not certify delivery QA.
"""
import argparse
import json
import math
import re
from pathlib import Path

REQUIRED = {'address', 'h_otn_model_max_z_m', 'thumbnail'}
OPTIONAL = {'profile', 'exported_files', 'provenance', 'fbx', 'pivot_revit_internal_m',
            'bbox_after_pivot', 'main_tris', 'glass_tris', 'ucx', 'ucx_tris'}


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'duplicate JSON key {key!r}')
        result[key] = value
    return result


def validate_meta(meta):
    if not isinstance(meta, dict):
        raise ValueError('export_meta must be an object')
    missing = REQUIRED - meta.keys()
    if missing:
        raise ValueError(f'export_meta missing fields: {sorted(missing)}')
    extra = meta.keys() - REQUIRED - OPTIONAL
    if extra:
        raise ValueError(f'export_meta unknown keys: {sorted(extra)}')
    address = meta['address']
    if not isinstance(address, str) or re.fullmatch(r'[A-Za-z0-9]+(?:_[A-Za-z0-9]+)*', address) is None:
        raise ValueError('export_meta address must be a Latin/digit/underscore token or unknown')
    top = meta['h_otn_model_max_z_m']
    if top != 'unknown' and (type(top) not in (int, float) or not math.isfinite(top)):
        raise ValueError('export_meta h_otn_model_max_z_m must be finite or unknown')
    if not isinstance(meta['thumbnail'], str) or not meta['thumbnail'].strip():
        raise ValueError('export_meta thumbnail must be a path or unknown')
    if 'profile' in meta and meta['profile'] not in ('npm', 'vpm', 'unknown'):
        raise ValueError(f"export_meta unsupported profile {meta['profile']!r}")
    if 'exported_files' in meta:
        files = meta['exported_files']
        if not isinstance(files, list) or not files:
            raise ValueError('export_meta exported_files must be nonempty')
        for name in files:
            if not isinstance(name, str) or re.fullmatch(r'[A-Za-z0-9_]+\.fbx', name) is None:
                raise ValueError(f'export_meta unsupported exported_files member {name!r}')
        if len(set(n.casefold() for n in files)) != len(files):
            raise ValueError('export_meta duplicated exported_files')
    if 'fbx' in meta and (not isinstance(meta['fbx'], str) or not meta['fbx'].strip()):
        raise ValueError('export_meta fbx must be a nonempty path')
    for key in ('main_tris', 'glass_tris', 'ucx', 'ucx_tris'):
        if key in meta and (type(meta[key]) is not int or meta[key] < 0):
            raise ValueError(f'export_meta {key} must be a nonnegative integer')
    for key in ('pivot_revit_internal_m', 'bbox_after_pivot'):
        if key not in meta:
            continue
        vectors = [meta[key]] if key == 'pivot_revit_internal_m' else meta[key]
        if not isinstance(vectors, list) or len(vectors) != (1 if key == 'pivot_revit_internal_m' else 2):
            raise ValueError(f'export_meta {key} has invalid dimensions')
        for vector in vectors:
            if not isinstance(vector, list) or len(vector) != 3 or any(type(x) not in (int, float) or not math.isfinite(x) for x in vector):
                raise ValueError(f'export_meta {key} requires finite xyz vectors')
        if key == 'bbox_after_pivot' and any(vectors[0][i] > vectors[1][i] for i in range(3)):
            raise ValueError('export_meta bbox_after_pivot is reversed')
    if 'provenance' in meta:
        prov = meta['provenance']
        fields = set(meta) - {'provenance'}
        if not isinstance(prov, dict) or set(prov) != fields:
            raise ValueError(f'export_meta provenance must name exactly {sorted(fields)}')
        for key, source in prov.items():
            if not isinstance(source, str) or not source.strip():
                raise ValueError(f'export_meta provenance.{key} must name its source/question')
    return meta


def load_meta(path):
    try:
        return validate_meta(json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=unique_object))
    except (ValueError, OSError) as exc:
        raise ValueError(f'export_meta {path}: {exc}') from exc


def load_package_meta(package_dir, explicit=None):
    """Nearest canonical record, unique non-light FBX sidecar, then historical parent.

    Multiple independent sidecars require explicit selection; never choose the first entry.
    Metadata identifies an exporter/naming token, not whole-package QA or a survey datum.
    """
    import os
    pkg = Path(package_dir)
    if explicit is not None:
        return load_meta(explicit)
    adjacent = pkg / 'export_meta.json'
    if os.path.lexists(adjacent):
        return load_meta(adjacent)
    candidates = sorted(p for p in pkg.glob('*.fbx.export_meta.json') if not p.name.endswith('_Light.fbx.export_meta.json'))
    if len(candidates) == 1:
        return load_meta(candidates[0])
    if len(candidates) > 1:
        raise ValueError(f'ambiguous export metadata {candidates}; choose --meta explicitly')
    return load_meta(pkg.parent / 'export_meta.json')


def write_meta(path, meta):
    """Exclusive creation: validate all data before any write; never replace a source/delivery."""
    validate_meta(meta)
    text = json.dumps(meta, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    with open(path, 'x', encoding='utf-8') as fh:
        fh.write(text)


def record_export(fbx, *, source, top: float | str = 'unknown', thumbnail='unknown', metadata_path=None, address=None, profile=None):
    """Record only caller measurements and filename facts; never infer a legal address/datum.

    Per-FBX sidecars allow several exports in one directory without overwriting metadata.
    A command producing a single package can explicitly request canonical export_meta.json.
    """
    fbx = Path(fbx)
    if not fbx.is_file():
        raise ValueError(f'exported FBX missing: {fbx}')
    match_vpm = re.fullmatch(r'SM_([A-Za-z0-9_]+)\.fbx', fbx.name)
    match_npm = re.fullmatch(r'[0-9]{4}_([A-Za-z0-9_]+)_(?:0[1-9]|1[0-9]|20|Ground)\.fbx', fbx.name)
    match = match_vpm or match_npm
    record = {'address': address if address is not None else match.group(1) if match else 'unknown',
              'h_otn_model_max_z_m': top, 'thumbnail': str(thumbnail),
              'profile': profile if profile is not None else 'vpm' if match_vpm else 'npm' if match_npm else 'unknown',
              'exported_files': [fbx.name]}
    record['provenance'] = {
        'address': f'{fbx.name}: naming token only, not a certified legal address; question: confirm address token' if match else 'unknown; question: provide sourced address token',
        'h_otn_model_max_z_m': f'{source}: export-frame render-geometry top' if top != 'unknown' else 'unknown; question: supply measured export-frame render top',
        'thumbnail': str(thumbnail) if str(thumbnail) != 'unknown' else 'unknown; question: supply a sourced 256x256 JPEG',
        'profile': f'{fbx.name}: filename grammar (not delivery QA)',
        'exported_files': f'{source}: completed exporter output'}
    if address is not None:
        record['provenance']['address'] = f'{source}: explicit exporter address argument (naming token, not legal-address approval)'
    if profile is not None:
        record['provenance']['profile'] = f'{source}: explicit exporter profile argument'
    path = Path(metadata_path) if metadata_path is not None else fbx.with_suffix(fbx.suffix + '.export_meta.json')
    write_meta(path, record)
    return path


def parse_top(raw):
    """CLI --top: 'unknown' or a finite float; NaN/inf/overflow/garbage are refused, never recorded."""
    if raw == 'unknown':
        return raw
    try:
        value = float(raw)
    except ValueError:
        raise ValueError(f'--top must be a finite number or unknown, got {raw!r}') from None
    if not math.isfinite(value):
        raise ValueError(f'--top must be a finite number or unknown, got {raw!r}')
    return value


def main(argv=None):
    """`check PATH` (also the legacy bare `PATH`) validates; `record FBX --source S` writes a new sidecar.

    Called by `agr export-meta` (src/dt_ai/cli/agr.py) and importable inside 3ds Max (AGR Tools, no deps).
    """
    import os
    import sys
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ['record']:
        ap = argparse.ArgumentParser(prog='agr export-meta record', description='Write a NEW export_meta sidecar.')
        ap.add_argument('fbx')
        ap.add_argument('--source', required=True, help='what produced the FBX (provenance)')
        ap.add_argument('--top', default='unknown', help='measured export-frame render top, m, or unknown')
        ap.add_argument('--thumbnail', default='unknown')
        ap.add_argument('--address')
        ap.add_argument('--profile', choices=('npm', 'vpm', 'unknown'))
        ap.add_argument('--out', help='default: <FBX>.export_meta.json; never replaced')
        args = ap.parse_args(argv[1:])
        top = parse_top(args.top)
        if args.out is not None:
            fbx, out = Path(args.fbx), Path(args.out)
            if out.suffix.lower() != '.json':
                raise ValueError(f'--out must be a .json file, got {out}')
            if os.path.abspath(out) == os.path.abspath(fbx) or (out.exists() and fbx.exists() and os.path.samefile(out, fbx)):
                raise ValueError(f'--out {out} resolves to the input FBX')
        path = record_export(args.fbx, source=args.source, top=top, thumbnail=args.thumbnail,
                             metadata_path=args.out, address=args.address, profile=args.profile)
        print(f'export_meta written: {path}')
        return 0
    if argv[:1] == ['check']:
        argv = argv[1:]
    ap = argparse.ArgumentParser(prog='agr export-meta check', description=__doc__)
    ap.add_argument('path')
    args = ap.parse_args(argv)
    load_meta(args.path)
    print(f'export_meta valid: {args.path}')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError) as exc:
        raise SystemExit(f'refused: {exc}')
