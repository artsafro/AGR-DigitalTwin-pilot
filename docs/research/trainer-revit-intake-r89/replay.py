"""OBSERVE #89: Revit-to-BodyPlan handoff with a source-naming window keys file (one variant, frozen)."""
import collections
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import jsonschema
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
HEAD = '08015022acc2a140994eeb188444f68a4388c15c'
HOOKS = Path('jobs/garibaldi22/body-training-1619/hooks')
CORE = Path('tools/methods/body/body_lattice.py')
SCHEMA = Path('schemas/BodyPlan.schema.json')
BLENDER = Path('C:/Program Files/Blender Foundation/Blender 5.1/blender.exe')
KEYS = HERE / 'keys63.json'
INPUTS = {
    Path('C:/x/body-training/a101-63/source/STLB-04_RR_AR.fbx'):
        '2b4d0201d3d2454344bba263500363fcc528a322bd2702ece0fac38e39a158d7',
    Path('G:/Мой диск/AGR-evidence/1619-body-training/gate1/boxes63.json'):
        'e8a41981ecaa7603ec4c8ef28098388ee2fcbf7cc8e341eaf5d08ed4f5d987e7',
}
STOPS = ('refused:', 'no window objects', 'reveal ', 'no typical', 'no wall', 'no contour', 'no typical-floor')


def sha(path):
    with path.open('rb') as fh:
        return hashlib.file_digest(fh, 'sha256').hexdigest()


def check(path, expected):
    if sha(path) != expected:
        raise RuntimeError(f'SHA-256 mismatch: {path}')


def invoke(argv, log, timeout, env):
    t = time.perf_counter()
    with log.open('wb') as fh:
        try:
            rc = subprocess.run([str(x) for x in argv], stdout=fh, stderr=subprocess.STDOUT,
                                env=env, timeout=timeout, cwd=log.parent).returncode
        except subprocess.TimeoutExpired:
            rc = None
    return {'exit': rc, 'wall_s': round(time.perf_counter() - t, 3),
            'log_tail': log.read_text(encoding='utf-8', errors='replace').splitlines()[-6:],
            'log_sha256': sha(log)}


def score(run, plan, tri, schema, validate_plan, build_module):
    """M89/M88 handoff: 1, 0 on a witnessed deterministic rejection, None when not measured."""
    if run['exit'] == 0 and plan.is_file():
        doc = json.loads(plan.read_text(encoding='utf-8'))
        run.update(plan_sha256=sha(plan), plan_counts=doc.get('counts'),
                   windows=len(doc.get('windows', [])),
                   reveal_pos=sum(1 for w in doc.get('windows', []) if len(w) > 5 and w[5] > 0),
                   dropped=len(doc.get('dropped', [])),
                   dropped_reasons=collections.Counter(str(d.get('reason', d) if isinstance(d, dict) else d)[:60]
                                                       for d in doc.get('dropped', [])).most_common(8))
        try:
            jsonschema.validate(doc, schema)
            validate_plan(doc)
            build_module(doc)
            return int(bool(len(tri) and run['reveal_pos']))
        except (ValueError, jsonschema.ValidationError) as exc:
            run['validation_error'] = str(exc)[:300]
            return 0
    if run['exit'] == 1 and run['log_tail'] and run['log_tail'][-1].startswith(STOPS):
        return 0
    return None


def main(out, blender):
    out.mkdir()
    scratch = out / 'temp'
    scratch.mkdir()
    env = {**os.environ, 'TEMP': str(scratch), 'TMP': str(scratch), 'TMPDIR': str(scratch),
           'PYTHONUTF8': '1', 'PYTHONDONTWRITEBYTECODE': '1'}
    pinned = out / 'code'
    fingerprints = {}
    for rel in [CORE, SCHEMA, *(HOOKS / f'{x}.py' for x in ('floor_from_dump', 'revit_floor_dump', 'module_build'))]:
        p = pinned / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(subprocess.check_output(['git', 'show', f'{HEAD}:{rel.as_posix()}'], cwd=ROOT))
        fingerprints[rel.as_posix()] = sha(p)
    for original, expected in INPUTS.items():
        check(original, expected)
    source, tower_map = INPUTS
    boxes = {row['id']: row for row in json.loads(tower_map.read_text(encoding='utf-8'))}
    sys.path.insert(0, str((pinned / CORE).parent))
    sys.path.insert(0, str((pinned / HOOKS)))
    from body_lattice import build_module, validate_plan  # pyright: ignore[reportMissingImports]
    from floor_from_dump import KEYS as DEFAULT_KEYS, classify  # pyright: ignore[reportMissingImports]

    schema = json.loads((pinned / SCHEMA).read_text(encoding='utf-8'))
    adapter = pinned / HOOKS / 'floor_from_dump.py'
    cropper = pinned / HOOKS / 'revit_floor_dump.py'
    code_bytes = cropper.read_bytes()
    old = b'bpy.ops.import_scene.fbx(filepath=src)'
    if code_bytes.count(old) != 1:
        raise RuntimeError('expected exactly one pinned legacy FBX import call')
    cropper.write_bytes(code_bytes.replace(old, b'bpy.ops.wm.fbx_import(filepath=src)'))
    keys = json.loads(KEYS.read_text(encoding='utf-8'))
    rows = []
    receipt = {'revision': HEAD, 'code_sha256': fingerprints, 'native_cropper_sha256': sha(cropper),
               'keys_sha256': sha(KEYS), 'keys': keys,
               'inputs_sha256': {p.name: h for p, h in INPUTS.items()}, 'rows': rows,
               'python': sys.version, 'numpy': np.__version__}

    def save():
        (out / 'receipt.json').write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')

    receipt['blender'] = invoke([blender, '--version'], out / 'blender.log', 20, env)
    receipt['blender_sha256'] = sha(blender)
    empty = out / 'synthetic_empty.npz'
    np.savez_compressed(empty, tri=np.empty((0, 3, 3)), obj=np.array([], dtype=np.int32),
                        names=np.array([], dtype='U1'), mat=np.array([], dtype=np.int32),
                        mats=np.array([], dtype='U1'))
    rejected = out / 'synthetic_empty.json'
    receipt['synthetic_empty'] = invoke([sys.executable, adapter, empty, rejected, '--openings', '--keys', KEYS],
                                        out / 'synthetic_empty.log', 20, env)
    receipt['synthetic_empty'].update(crop_sha256=sha(empty), emitted=rejected.exists())
    save()

    started = time.perf_counter()
    deadline = started + 480
    for iteration in range(1, 4):
        for tower in ('63A', '63B'):
            if time.perf_counter() >= deadline:
                receipt['status'] = 'budget_stop'
                save()
                return
            d = out / f'{tower}-{iteration}'
            d.mkdir()
            box = boxes[tower]
            xy = ','.join(str(v) for v in [*box['min'][:2], *box['max'][:2]])
            check(source, INPUTS[source])
            crop = d / 'crop.npz'
            row = {'fixture': tower, 'iteration': iteration, 'xy_m': xy, 'baseline': None, 'candidate': None}
            rows.append(row)
            row['crop'] = invoke([blender, '--background', '--factory-startup', '--disable-autoexec',
                                  '--threads', '1', '--python-exit-code', '1', '--python', cropper,
                                  '--', source, crop, xy], d / 'crop.log',
                                 max(0.1, min(60, deadline - time.perf_counter())), env)
            if row['crop']['exit'] == 0 and crop.is_file():
                with np.load(crop, allow_pickle=False) as data:
                    tri, names = data['tri'], [str(n) for n in data['names']]
                row.update(crop_sha256=sha(crop), triangles=len(tri), objects=len(names),
                           classes_default=collections.Counter(map(str, classify(names, DEFAULT_KEYS))),
                           classes_candidate=collections.Counter(map(str, classify(names, keys))))
                for arm, extra in (('baseline', []), ('candidate', ['--keys', KEYS])):
                    plan = d / f'{arm}.json'
                    run = invoke([sys.executable, adapter, crop, plan, '--openings', *extra], d / f'{arm}.log',
                                 max(0.1, min(30, deadline - time.perf_counter())), env)
                    row[arm] = score(run, plan, tri, schema, validate_plan, build_module)
                    row[f'{arm}_run'] = run
            print(tower, iteration, row['baseline'], row['candidate'],
                  row.get('candidate_run', {}).get('log_tail', [])[-1:], flush=True)
            save()
        if iteration == 1:
            receipt['first_pair_wall_s'] = round(time.perf_counter() - started, 3)
            deadline = min(deadline, started + 5 * receipt['first_pair_wall_s'])
    for original, expected in INPUTS.items():
        check(original, expected)
    receipt.update(source_parity=True, status='finished', series_wall_s=round(time.perf_counter() - started, 3))
    save()


if __name__ == '__main__':
    main(Path(sys.argv[1]).resolve(), BLENDER)
