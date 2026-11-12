"""new-case: fail-closed library catalogue and native Blender cleanliness, not delivery QA."""
import argparse
import json
from pathlib import Path


def load_json(path):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('duplicate key: ' + key)
            result[key] = value
        return result
    def constant(value):
        raise ValueError('non-finite JSON: ' + value)
    doc = json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=pairs, parse_constant=constant)
    json.dumps(doc, allow_nan=False)  # also reject exponent overflow (1e999)
    return doc


def validate_catalogue(doc):
    from jsonschema import Draft202012Validator
    schema = load_json(Path(__file__).resolve().parents[2] / 'schemas/library_catalogue.schema.json')
    json.dumps(doc, allow_nan=False)
    errors = list(Draft202012Validator(schema).iter_errors(doc))
    if errors:
        raise ValueError('; '.join(str(list(e.path)) + ': ' + e.message for e in errors))
    if (doc['library'] == 'flora') != (doc['pivot'] == 'flora-bbox-plus-0.1'):
        raise ValueError('D100: Flora requires flora-bbox-plus-0.1; other libraries must not use it')
    ids, cells = set(), set()
    for asset in doc['assets']:
        if asset['id'].casefold() in ids:
            raise ValueError('duplicate id: ' + asset['id'])
        ids.add(asset['id'].casefold())
        if asset['preview_cell'] in cells:
            raise ValueError('duplicate preview_cell: ' + str(asset['preview_cell']))
        cells.add(asset['preview_cell'])
        for profile, v in asset['variants'].items():
            if v['path'] != f'assets/{asset["id"]}/{profile}.blend':
                raise ValueError('variant path disagrees with asset/profile: ' + v['path'])
            if any(not name.startswith(f'{asset["id"]}_{profile}_') for name in v['objects']):
                raise ValueError('object name disagrees with asset/profile: ' + asset['id'])
            mats = v['materials']
            if len({m['id'] for m in mats}) != len(mats) or any(m['name'] != f'matid_{m["id"]}' for m in mats):
                raise ValueError('unmapped/conflicting material: ' + asset['id'])
    if not any(a['status'] == 'ready' for a in doc['assets']):
        raise ValueError('assets: no ready assets to inspect')


def scene_errors(scene, expected, pivot):
    """Compare raw native inventory with a variant. No stored verdicts are consumed."""
    import math
    errors = []
    try:
        if scene['units'] != 'METRIC' or scene['scale_length'] != 1:
            errors.append('scene: expected metres, scale_length=1')
        if scene['orphans'] or scene['unsupported']:
            errors.append('scene extras: ' + str(scene['orphans'] + scene['unsupported']))
        objects = scene['objects']
        names = [o['name'] for o in objects]
        if sorted(names) != sorted(expected['objects']) or len(set(names)) != len(names):
            errors.append('objects: expected ' + str(expected['objects']) + ', got ' + str(names))
        total, materials, bounds = 0, {}, []
        for obj in objects:
            name = obj['name']
            try:
                for key, value in [('type', 'MESH'), ('location', [0, 0, 0]), ('rotation', [0, 0, 0]),
                                   ('scale', [1, 1, 1]), ('hidden', False), ('parent', None),
                                   ('modifiers', []), ('constraints', []), ('unused_slots', []),
                                   ('uv_layers', 1), ('uv_finite', True), ('degenerate_faces', 0),
                                   ('loose_vertices', 0), ('duplicate_faces', 0)]:
                    if obj[key] != value:
                        errors.append(f'{name}: {key}={obj[key]!r}')
                count = obj['triangles']
                spacing = obj['min_vertex_distance_m']
                if type(spacing) not in (int, float) or not math.isfinite(spacing) or spacing <= 0.002:
                    errors.append(f'{name}: vertex spacing <= 2 mm or unmeasured: {spacing}')
                if type(count) is not int or count <= 0:
                    errors.append(f'{name}: invalid triangles {count}')
                total += count
                b = obj['bounds']
                if len(b) != 2 or any(len(v) != 3 for v in b) or not all(
                        type(c) in (int, float) and math.isfinite(c) for v in b for c in v):
                    errors.append(f'{name}: invalid bounds')
                elif any(b[1][i] < b[0][i] for i in range(3)):
                    errors.append(f'{name}: inverted bounds')
                else:
                    bounds.append(b)
                if not obj['materials']:
                    errors.append(f'{name}: missing materials')
                for material in obj['materials']:
                    mid, mname = material['id'], material['name']
                    if type(mid) is not int or {'id': mid, 'name': mname} not in expected['materials']:
                        errors.append(f'{name}: unmapped material {mid} {mname}')
                    if mid in materials and materials[mid] != mname:
                        errors.append(f'{name}: conflicting material {mid}')
                    materials[mid] = mname
            except (KeyError, TypeError, ValueError) as exc:
                errors.append(f'{name}: incomplete native inventory: {exc}')
        if total != expected['triangles']:
            errors.append(f'{names}: triangles expected {expected["triangles"]}, got {total}')
        if sorted(materials.items()) != sorted((m['id'], m['name']) for m in expected['materials']):
            errors.append(f'{names}: material inventory mismatch')
        if bounds:
            lo = [min(b[0][i] for b in bounds) for i in range(3)]
            hi = [max(b[1][i] for b in bounds) for i in range(3)]
            size = expected['size_m']
            origin = [0, 0, 0] if pivot == 'bottom-left' else [-size[0]/2, -size[1]/2, 0]
            if pivot == 'flora-bbox-plus-0.1':
                origin[2] = -0.1  # D100: place pivot on Ground, do not sink another 10 cm.
            if pivot not in ('bottom-left', 'bottom-center', 'flora-bbox-plus-0.1') or any(
                    abs(hi[i]-lo[i]-size[i]) > 1e-5 or abs(lo[i]-origin[i]) > 1e-5 for i in range(3)):
                errors.append(f'{names}: size/pivot mismatch: {lo}, {hi}')
    except (KeyError, TypeError, ValueError) as exc:
        errors.append('incomplete scene inventory: ' + str(exc))
    return errors


def digest(path):
    import hashlib
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def check(catalogue, root, repo, inspect):
    """Read-only check; hash inputs before/after native readback, reject physical aliases."""
    catalogue, root, repo = Path(catalogue).resolve(), Path(root).resolve(), Path(repo).resolve()
    before = {catalogue: digest(catalogue)}
    doc = load_json(catalogue)
    validate_catalogue(doc)
    variants = [(a, profile, v) for a in doc['assets'] for profile, v in a['variants'].items()]
    files = [(repo, row) for row in doc['inputs']] + [(root, doc['showcase'])] + [(root, v) for _, _, v in variants]
    paths = []
    for base, row in files:
        rel = Path(row['path'])
        if rel.is_absolute() or '..' in rel.parts or '\\' in row['path'] or ':' in row['path']:
            raise ValueError('unsafe relative path: ' + row['path'])
        path = (base / rel).resolve()
        if not path.is_relative_to(base) or not path.is_file():
            raise ValueError('missing/escaping file: ' + str(path))
        if any(path.samefile(other) for other in before):
            raise ValueError('aliased/duplicated input: ' + str(path))
        value = digest(path)
        if value != row['sha256']:
            raise ValueError('stale sha256: ' + str(path))
        before[path] = value
        paths.append(path)
    native_paths = paths[ len(doc['inputs']) + 1: ]
    actual = {p.resolve() for p in (root/'assets').rglob('*') if p.is_file()}
    if actual != set(native_paths):
        raise ValueError('assets folder has missing/extra files: ' + str(sorted(map(str, actual ^ set(native_paths)))))
    raw = inspect(native_paths)
    if set(raw) != {str(p) for p in native_paths}:
        raise ValueError('partial/duplicated native readback')
    errors = []
    for (asset, profile, v), path in zip(variants, native_paths):
        errors += [asset['id'] + '/' + profile + ': ' + e for e in scene_errors(raw[str(path)], v, doc['pivot'])]
    after_files = {p.resolve() for p in (root/'assets').rglob('*') if p.is_file()}
    if actual != after_files:
        raise ValueError('assets inventory changed during run')
    for path, sha in before.items():
        if not path.is_file() or digest(path) != sha:
            raise ValueError('input changed during run: ' + str(path))
    return {'cleanliness': 'fail' if errors else 'pass', 'errors': errors, 'variants_checked': len(variants),
            'ready': sum(a['status'] == 'ready' for a in doc['assets']),
            'quarantine': [{'id': a['id'], 'reason': a['reason']} for a in doc['assets'] if a['status'] == 'quarantine'],
            'delivery_certificate': False}


def native_inspect(paths, blender):
    import subprocess
    script = Path(__file__).with_name('inspect_library_blender.py')
    command = [str(blender), '-b', '--factory-startup', '--disable-autoexec', '--python-exit-code', '3',
               '--python', str(script), '--', *map(str, paths)]
    result = subprocess.run(command, capture_output=True, encoding='utf-8', errors='replace', timeout=1200)
    if result.returncode:
        raise ValueError('Blender readback exit ' + str(result.returncode) + ': ' + result.stdout[-1500:] + result.stderr[-1000:])
    rows = [json.loads(line.removeprefix('AGR_LIBRARY_SCENE ')) for line in result.stdout.splitlines()
            if line.startswith('AGR_LIBRARY_SCENE ')]
    if len(rows) != len(paths) or len({r['path'] for r in rows}) != len(rows):
        raise ValueError('partial/duplicate Blender result')
    return {r['path']: r['scene'] for r in rows}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('catalogue', type=Path)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--blender', type=Path, default=Path('C:/Program Files/Blender Foundation/Blender 5.1/blender.exe'))
    args = parser.parse_args(argv)
    try:
        result = check(args.catalogue, args.root, args.repo, lambda paths: native_inspect(paths, args.blender))
    except (ValueError, OSError, KeyError, TypeError) as exc:
        result = {'cleanliness': 'fail', 'errors': [str(exc)], 'delivery_certificate': False}
    print(json.dumps(result, ensure_ascii=True, allow_nan=False))
    return 0 if result['cleanliness'] == 'pass' else 1


if __name__ == '__main__':
    raise SystemExit(main())
