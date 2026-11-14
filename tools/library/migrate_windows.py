"""new-case: windows library migration plan using the existing D204 generator, not source-scene edits."""
import argparse
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def min_spacing(vertices):
    """Minimum per-part vertex spacing after Blender float32 storage, in metres."""
    import numpy as np
    points = np.asarray(vertices, dtype=np.float32).astype(np.float64)
    if len(points) < 2:
        return 0.0
    return min(float(np.linalg.norm(points[i+1:] - points[i], axis=1).min()) for i in range(len(points)-1))


def prepare(repo, types_doc=None):
    repo = Path(repo)
    wg = load_module(repo/'adapters/max/agr_tools/windowgen_core.py', 'migration_windowgen')
    sash = load_module(repo/'tools/library/window_sashes.py', 'migration_sashes')
    base = repo/'library/windows'
    doc = copy.deepcopy(types_doc) if types_doc is not None else json.loads((base/'window_types.json').read_text(encoding='utf-8'))
    sash_path = 'library/windows/sources/win-typical-max-sashes-v001.json'
    sash.apply_sashes(doc, [(sash_path, json.loads((repo/sash_path).read_text(encoding='utf-8')))])
    standard = wg.load_standard(json.loads((base/'standard.json').read_text(encoding='utf-8')))
    ids = [t['id'].casefold() for t in doc['types']]
    if len(ids) != len(set(ids)):
        raise ValueError('duplicate type id')
    for t in doc['types']:
        if t['role'] not in standard['role_family']:
            raise ValueError('unmapped role: ' + str(t['role']))
    report = wg.library_report(doc['types'], standard)
    assets = []
    for cell, (t, quality) in enumerate(zip(doc['types'], report['types']), 1):
        ready = quality['verdict'] == 'pass'
        meshes = {profile: wg.build_type(t, standard, {'variant': profile}) for profile in ('npm', 'vpm')} if ready else {}
        reasons = [] if ready else quality['why']
        if ready and any(min_spacing(wg.part_mesh(mesh, part)['verts']) <= 0.002
                         for mesh in meshes.values() for part in ('frame', 'glass') if mesh['parts'][part]):
            ready, meshes = False, {}
            reasons = ['native float32 vertex spacing <= 2 mm (D152 xView); retain source, no guessed weld/shape change']
        assets.append({'id': t['id'], 'name': t['name'] or f'{t["id"]} (source name unspecified)', 'confirmation': t['status'],
                       'status': 'ready' if ready else 'quarantine',
                       'reason': reasons, 'preview_cell': cell,
                       'source': {'record': t['id'], 'original_name': t['name'], 'provenance': t['source'],
                                  'unconfirmed': t['unconfirmed'], 'family': quality['family'],
                                  'geometry': 'D204 standard-generated; not original customer mesh'},
                       'meshes': meshes})
    return {'assets': assets}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='new version directory, outside the repository')
    parser.add_argument('--blender', default='C:/Program Files/Blender Foundation/Blender 5.1/blender.exe')
    args = parser.parse_args(argv)
    repo = Path(__file__).resolve().parents[2]
    output = args.output.resolve()
    if output.exists() or output.is_relative_to(repo) or repo.is_relative_to(output):
        parser.error('output must be a new external version directory, never an input/repository ancestor')
    result = subprocess.run([args.blender, '-b', '--factory-startup', '--disable-autoexec', '--python-exit-code', '3',
                             '--python', str(Path(__file__).with_name('build_windows_blender.py')), '--', str(repo), str(output)])
    return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())
