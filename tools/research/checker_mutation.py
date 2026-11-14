"""new-case: frozen real-etalon scene mutation benchmark and exact oracle (#1261).

Mutation score is incremental correct-code detection, never unrelated/pre-existing fails.
Freeze runs Blender on copies; measure only re-evaluates immutable measured scene facts.
No live Max, no repair of etalons, no change to the generator after its freeze receipt.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'src'), str(Path(__file__).parent)]
from checker_mutation_guard import caught, guard, read, sha256, verify_files
from twinqa.fbx_header import fbx_application, fbx_units
from twinqa.profiles import load_profiles
from twinqa.scene import scene_findings

GENERATOR = ROOT / 'tools/research/checker_mutation_blender.py'
GUARD = ROOT / 'tools/research/checker_mutation_guard.py'


def mutate_units(data, scale_cm):
    """Change only GlobalSettings/Properties70/UnitScaleFactor's binary double on a copy."""
    import struct
    from twinqa.fbx_header import _iter_nodes, _parse_props, fbx_header
    encoding, version = fbx_header(data)
    if encoding != 'binary' or version is None:
        raise ValueError('unsupported FBX for units mutation')
    for root in _iter_nodes(data, 27, len(data), version):
        if root['name'] != 'GlobalSettings':
            continue
        for properties in _iter_nodes(data, root['props_end'], root['end_offset'], version):
            if properties['name'] != 'Properties70':
                continue
            for node in _iter_nodes(data, properties['props_end'], properties['end_offset'], version):
                props = _parse_props(data, node['props_at'], node['props_end'], node['num_props'])
                if props and props[0] == ('S', 'UnitScaleFactor') and props[-1][0] == 'D':
                    at = node['props_end'] - 8
                    return data[:at] + struct.pack('<d', scale_cm) + data[at+8:]
    raise ValueError('UnitScaleFactor double missing')


def findings(rb, config, profiles):
    groups = scene_findings(rb, config['kind'], config['role'], profiles.profile(config['kind']),
                            **config.get('operands', {}))
    result = []
    for stage, values in sorted(groups.items()):
        for value in values:
            # Finding identity is the production stage + finding name, not a research-only alarm.
            result.append({'code': f'{stage}/{value.name}', 'status': value.status, 'observed': value.observed})
    return result


def evaluate(root, manifest):
    verify_files(root, manifest['files'])
    profiles = load_profiles()
    clean, rows = {}, []
    for config in manifest['etalons']:
        name = config['id']
        folder = root / name
        source = folder / config['source_name']
        data = source.read_bytes()
        units, app = fbx_units(data), fbx_application(data)
        def load_rb(path, unit_source=None):
            rb = read(path)
            rb['fbx_units'], rb['fbx_application'] = (fbx_units(unit_source.read_bytes()) if unit_source else units), app
            return rb
        baseline = findings(load_rb(folder / 'scenes/clean.json'), config, profiles)
        clean[name] = baseline
        operations = read(folder / 'scenes/operations.json')['operations']
        for op in operations:
            if op['status'] != 'generated':
                rows.append({'etalon': name, **op})
                continue
            if op.get('adapter') == 'fbx_units_only':
                from twinqa.scene import _v002_findings
                mutant = [{'code': 'V002/'+f.name, 'status': f.status, 'observed': f.observed}
                          for f in _v002_findings({'fbx_units': fbx_units((folder/op['fbx']).read_bytes())}, [], op['fbx'])
                          if f.name == 'system units']
            else:
                mutant = findings(load_rb(folder / f"scenes/{op['class']}.json"), config, profiles)
            hit = caught(baseline, mutant, op['expected'])
            detected = [f['code'] for f in mutant if f['code'] in op['expected'] and f['status'] in {'fail','review'}]
            rows.append({'etalon': name, **op, 'caught': hit, 'checks': detected, 'findings': mutant})
    sys.path.insert(0, str(ROOT / 'tools/qa'))
    import validate_package as vp
    for config in manifest.get('packages', []):
        folder = root / config['id']
        def package_findings(path):
            report = vp.validate(path, config['kind'], profiles, scene=False)
            found = []
            occurrences = {}
            for stage in report.stages:
                for f in stage.findings:
                    key = f'{stage.id}/{f.name}/{f.evidence}'
                    occurrence = occurrences.get(key, 0)
                    occurrences[key] = occurrence + 1
                    found.append({'code': f'{key}/{occurrence}', 'status': f.status, 'observed': f.observed})
            return found
        baseline = package_findings(folder / config['source_name'])
        clean[config['id']] = baseline
        for case, names in [('missing_texture', ['map set', 'PNG count']), ('oversized_texture', ['map size'])]:
            mutant = package_findings(folder / case / config['source_name'])
            expected = [f['code'] for f in mutant if any('/'+n+'/' in f['code'] for n in names)]
            hit = caught(baseline, mutant, expected) if expected else False
            rows.append({'etalon': config['id'], 'class': case, 'status': 'generated', 'expected': expected,
                         'caught': hit, 'checks': [f['code'] for f in mutant if f['code'] in expected and f['status'] in {'fail','review'}], 'findings': mutant})
    verify_files(root, manifest['files'])
    generated = [r for r in rows if r['status'] == 'generated']
    if not generated:
        raise ValueError('empty mutant corpus')
    per_class = {}
    for row in rows:
        stats = per_class.setdefault(row['class'], {'caught': 0, 'missed': 0, 'not_applicable': 0, 'checks': []})
        if row['status'] != 'generated':
            stats['not_applicable'] += 1
        else:
            stats['caught' if row['caught'] else 'missed'] += 1
            if row['caught']:
                stats['checks'] = sorted(set(stats['checks']) | set(row['checks']))
    return {'score': sum(r['caught'] for r in generated) / len(generated), 'total': len(generated),
            'caught': sum(r['caught'] for r in generated), 'per_class': per_class, 'rows': rows, 'clean': clean}


def freeze(config_path, output, blender):
    config_bytes = config_path.read_bytes()
    config = read(config_path)
    if output.exists() or not config.get('etalons'):
        raise ValueError('existing output or empty corpus')
    ids = [c['id'] for c in config['etalons']]
    if len(ids) != len(set(ids)) or any(not n.replace('_','').isalnum() for n in ids):
        raise ValueError('duplicate or unsafe etalon IDs')
    sources = [Path(c['source']).resolve() for c in config['etalons']]
    if len(set(sources)) != len(sources) or any(p.is_relative_to(output.resolve()) for p in sources):
        raise ValueError('duplicate source or source/output alias')
    for p in sources:
        if not p.is_file() or p.suffix.lower() != '.fbx':
            raise ValueError(f'missing/unsupported source: {p}')
    output.mkdir(parents=True)
    for c, source in zip(config['etalons'], sources):
        folder = output / c['id']
        folder.mkdir()
        c['source_name'] = source.name
        copied = folder / source.name
        before = sha256(source)
        shutil.copyfile(source, copied)
        if sha256(copied) != before:
            raise ValueError(f'copy hash mismatch: {source}')
        with (folder / 'blender.log').open('w', encoding='utf-8') as log:
            cmd = [blender, '--background', '--factory-startup', '--python-exit-code', '1',
                   '--python', str(GENERATOR), '--', str(copied.resolve()), str((folder/'scenes').resolve()), '--cases', *c['cases']]
            result = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT, timeout=1800)
        if result.returncode:
            raise RuntimeError(f'Blender exit {result.returncode}: {folder}/blender.log')
        unit_source = folder / 'wrong_units.fbx'
        unit_source.write_bytes(mutate_units(copied.read_bytes(), 1.0))
        op_path = folder/'scenes/operations.json'
        ops = read(op_path)
        ops['operations'].append({'class': 'wrong_units', 'status': 'generated', 'expected': ['V002/system units'], 'fbx': unit_source.name,
                                  'adapter': 'fbx_units_only', 'witness': 'UnitScaleFactor 1 cm, actual binary FBX metadata checker only; no scene facts claimed'})
        op_path.write_text(json.dumps(ops, indent=2), encoding='utf-8')
        if sha256(source) != before or sha256(copied) != before:
            raise ValueError(f'source changed: {source}')
    import io
    import zipfile
    from PIL import Image
    for c in config.get('packages', []):
        source = Path(c['source'])
        folder = output / c['id']
        folder.mkdir()
        c['source_name'] = source.name
        original = source.read_bytes()
        (folder/source.name).write_bytes(original)
        with zipfile.ZipFile(io.BytesIO(original)) as z:
            files = {i.filename: z.read(i) for i in z.infolist()}
        png = next((n for n in sorted(files) if n.lower().endswith('.png')), None)
        if not png:
            raise ValueError(f'package has no texture to mutate: {source}')
        for case in ['missing_texture', 'oversized_texture']:
            target = folder / case / source.name
            target.parent.mkdir()
            modified = dict(files)
            if case == 'missing_texture':
                del modified[png]
            else:
                buf = io.BytesIO()
                with Image.open(io.BytesIO(modified[png])) as image:
                    image.resize((8192,8192)).save(buf, format='PNG')
                modified[png] = buf.getvalue()
            with zipfile.ZipFile(target, 'x', compression=zipfile.ZIP_DEFLATED) as z:
                for name, data in sorted(modified.items()):
                    z.writestr(name, data)
        if source.read_bytes() != original:
            raise ValueError('package source changed during freeze')
    if config_path.read_bytes() != config_bytes:
        raise ValueError('configuration changed during freeze')
    files = {p.relative_to(output).as_posix(): sha256(p) for p in output.rglob('*') if p.is_file() and p.suffix != '.log'}
    manifest = {'schema': 1, 'seed': 1261, 'base_commit': subprocess.check_output(['git','rev-parse','HEAD'], text=True).strip(),
                'generator_sha256': sha256(GENERATOR), 'guard_sha256': sha256(GUARD),
                'config_sha256': __import__('hashlib').sha256(config_bytes).hexdigest(), 'files': files, **config}
    (output/'manifest.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding='utf-8')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    f = sub.add_parser('freeze')
    f.add_argument('config', type=Path)
    f.add_argument('output', type=Path)
    f.add_argument('--blender', default='C:/Program Files/Blender Foundation/Blender 5.1/blender.exe')
    seal = sub.add_parser('seal', help='seal preparation once, before any baseline measurement')
    seal.add_argument('corpus', type=Path)
    for name in ['baseline', 'measure']:
        m = sub.add_parser(name)
        m.add_argument('corpus', type=Path)
        m.add_argument('--output', type=Path, required=True)
        m.add_argument('--manifest-sha256', required=True)
        if name == 'measure':
            m.add_argument('--oracle-sha256', required=True)
    args = p.parse_args()
    if args.command == 'freeze':
        freeze(args.config, args.output, args.blender)
        return
    root = args.corpus.resolve()
    if args.command == 'seal':
        if (root.parent/'baseline.json').exists():
            raise ValueError('cannot reseal a measured corpus')
        manifest = read(root/'manifest.json')
        if manifest.get('sealed'):
            raise ValueError('corpus already sealed')
        for c in manifest['etalons']:
            folder = root/c['id']
            source = folder/c['source_name']
            original = source.read_bytes()
            old = fbx_units(original)['unit_scale_factor']
            mutated = mutate_units(original, old*.5)
            if original == mutated:
                raise ValueError('no-op unit mutant')
            (folder/'wrong_units.fbx').write_bytes(mutated)
            ops_path = folder/'scenes/operations.json'
            ops = read(ops_path)
            for op in ops['operations']:
                if op['class'] == 'wrong_units':
                    op['witness'] = f'UnitScaleFactor {old} -> {old*.5} cm; binary metadata checker only'
            ops_path.write_text(json.dumps(ops, indent=2), encoding='utf-8')
        manifest.update(sealed=True, runner_sha256=sha256(Path(__file__)), guard_sha256=sha256(GUARD), generator_sha256=sha256(GENERATOR))
        manifest['files'] = {p.relative_to(root).as_posix(): sha256(p) for p in root.rglob('*')
                             if p.is_file() and p.name != 'manifest.json' and p.suffix != '.log'}
        (root/'manifest.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding='utf-8')
        print(json.dumps({'manifest_sha256': sha256(root/'manifest.json'), 'files': len(manifest['files'])}))
        return
    output = args.output.resolve()
    if output.exists() or output.is_relative_to(root):
        p.error('existing output or corpus alias; nothing written')
    manifest = read(root / 'manifest.json')
    if sha256(root/'manifest.json') != args.manifest_sha256 or not manifest.get('sealed'):
        raise ValueError('unsealed corpus or manifest hash drift')
    if manifest['runner_sha256'] != sha256(Path(__file__)):
        raise ValueError('measurement runner drift since seal')
    if manifest['generator_sha256'] != sha256(GENERATOR) or manifest['guard_sha256'] != sha256(GUARD):
        raise ValueError('generator/guard drift since freeze')
    result = evaluate(root, manifest)
    if args.command == 'baseline':
        result['guard'] = 'baseline oracle; not a delivery pass'
    else:
        if sha256(root.parent/'baseline.json') != args.oracle_sha256:
            raise ValueError('oracle hash drift')
        baseline = read(root.parent / 'baseline.json')
        guard(baseline['clean'], result['clean'])
        result['guard'] = 'PASS'
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2, ensure_ascii=False, allow_nan=False)
    print(json.dumps({k: result[k] for k in ['score','caught','total','guard']}))


if __name__ == '__main__':
    main()
