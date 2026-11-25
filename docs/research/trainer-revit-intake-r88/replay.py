"""OBSERVE #88: reproduce the source-only Revit-to-BodyPlan handoff."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

import jsonschema
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
HEAD = '08015022acc2a140994eeb188444f68a4388c15c'
HOOKS = Path('jobs/garibaldi22/body-training-1619/hooks')
CORE = Path('tools/methods/body/body_lattice.py')
SCHEMA = Path('schemas/BodyPlan.schema.json')
BLENDER = Path('C:/Program Files/Blender Foundation/Blender 5.1/blender.exe')
RUNS = Path('C:/x/trainer/runs')
INPUTS = {
    Path('C:/x/body-training/a101-63/source/STLB-04_RR_AR.fbx'):
        '2b4d0201d3d2454344bba263500363fcc528a322bd2702ece0fac38e39a158d7',
    Path('G:/Мой диск/AGR-evidence/1619-body-training/gate1/boxes63.json'):
        'e8a41981ecaa7603ec4c8ef28098388ee2fcbf7cc8e341eaf5d08ed4f5d987e7',
}


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
            proc = subprocess.run([str(x) for x in argv], stdout=fh, stderr=subprocess.STDOUT,
                                  env=env, timeout=timeout, cwd=log.parent)
            rc = proc.returncode
        except subprocess.TimeoutExpired:
            rc = None
    return {'exit': rc, 'wall_s': round(time.perf_counter() - t, 3),
            'log_tail': log.read_text(encoding='utf-8', errors='replace').splitlines()[-8:],
            'log_sha256': sha(log)}


def main(out, blender, native):
    out.mkdir()
    scratch = out / 'temp'
    scratch.mkdir()
    env = {**os.environ, 'TEMP': str(scratch), 'TMP': str(scratch), 'TMPDIR': str(scratch),
           'PYTHONUTF8': '1', 'PYTHONDONTWRITEBYTECODE': '1'}
    pinned = out / 'code'
    code = [CORE, SCHEMA, *(HOOKS / f'{x}.py' for x in ('floor_from_dump', 'revit_floor_dump', 'module_build'))]
    fingerprints = {}
    for rel in code:
        p = pinned / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(subprocess.check_output(['git', 'show', f'{HEAD}:{rel.as_posix()}'], cwd=ROOT))
        fingerprints[rel.as_posix()] = sha(p)
    for original, expected in INPUTS.items():
        check(original, expected)
        shutil.copyfile(original, out / original.name)
        check(out / original.name, expected)
    source, tower_map = [out / p.name for p in INPUTS]
    boxes = {row['id']: row for row in json.loads(tower_map.read_text(encoding='utf-8'))}
    sys.path.insert(0, str((pinned / CORE).parent))
    from body_lattice import build_module, validate_plan  # pyright: ignore[reportMissingImports]

    schema = json.loads((pinned / SCHEMA).read_text(encoding='utf-8'))
    adapter = pinned / HOOKS / 'floor_from_dump.py'
    cropper = pinned / HOOKS / 'revit_floor_dump.py'
    rows = []
    receipt = {'revision': HEAD, 'code_sha256': fingerprints,
               'inputs_sha256': {p.name: h for p, h in INPUTS.items()}, 'rows': rows,
               'python': sys.version, 'numpy': np.__version__}
    if native:
        code_bytes = cropper.read_bytes()
        old = b'bpy.ops.import_scene.fbx(filepath=src)'
        if code_bytes.count(old) != 1:
            raise RuntimeError('expected exactly one pinned legacy FBX import call')
        cropper.write_bytes(code_bytes.replace(old, b'bpy.ops.wm.fbx_import(filepath=src)'))
        receipt['native_cropper_sha256'] = sha(cropper)

    def save():
        (out / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')

    receipt['blender'] = invoke([blender, '--version'], out / 'blender.log', 20, env)
    receipt['blender']['log_tail'] = (out / 'blender.log').read_text(encoding='utf-8').splitlines()[:4]
    receipt['blender_sha256'] = sha(blender)
    empty = out / 'synthetic_empty.npz'
    np.savez_compressed(empty, tri=np.empty((0, 3, 3)), obj=np.array([], dtype=np.int32),
                        names=np.array([], dtype='U1'), mat=np.array([], dtype=np.int32),
                        mats=np.array([], dtype='U1'))
    rejected_plan = out / 'synthetic_empty.json'
    receipt['synthetic_empty'] = invoke([sys.executable, adapter, empty, rejected_plan, '--openings'],
                                        out / 'synthetic_empty.log', 20, env)
    receipt['synthetic_empty'].update(crop_sha256=sha(empty), emitted=rejected_plan.exists())
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
            snapshot = RUNS / f'{tower.lower()}-stage1-codex-r87-{iteration}'
            wt = snapshot / 'wt'
            row = {'fixture': tower, 'iteration': iteration, 'baseline': None, 'candidate': None}
            run_metadata = json.loads((snapshot / 'run.json').read_text(encoding='utf-8-sig'))
            git_head = subprocess.check_output(['git', '-C', str(wt), 'rev-parse', 'HEAD'], text=True).strip()
            existing = (wt / HOOKS / adapter.name).is_file()
            row.update(baseline_snapshot=git_head, baseline_origin=run_metadata['origin_main'],
                       baseline_run_sha256=sha(snapshot / 'run.json'), baseline_adapter_exists=existing)
            if not existing:
                row['baseline'] = 0
            rows.append(row)
            box = boxes[tower]
            xy = ','.join(str(v) for v in [*box['min'][:2], *box['max'][:2]])
            check(source, INPUTS[next(iter(INPUTS))])
            crop, plan = d / 'crop.npz', d / 'floor.json'
            row['xy_m'] = xy
            row['crop'] = invoke([blender, '--background', '--factory-startup', '--disable-autoexec',
                                  '--threads', '1', '--python-exit-code', '1', '--python', cropper,
                                  '--', source, crop, xy], d / 'crop.log',
                                 max(0.1, min(60, deadline - time.perf_counter())), env)
            if row['crop']['exit'] == 0 and crop.is_file():
                with np.load(crop, allow_pickle=False) as data:
                    tri = data['tri']
                    row['arrays'] = {k: {'shape': list(data[k].shape), 'dtype': str(data[k].dtype),
                                         'sha256': hashlib.sha256(data[k].tobytes()).hexdigest()} for k in data.files}
                    if len(tri):
                        row['bbox_m'] = [tri.min(axis=(0, 1)).tolist(), tri.max(axis=(0, 1)).tolist()]
                row['crop_sha256'] = sha(crop)
                row['adapter'] = invoke([sys.executable, adapter, crop, plan, '--openings'], d / 'adapter.log',
                                        max(0.1, min(30, deadline - time.perf_counter())), env)
                if row['adapter']['exit'] == 0 and plan.is_file():
                    row['plan_sha256'] = sha(plan)
                    doc = json.loads(plan.read_text(encoding='utf-8'))
                    row['plan_counts'] = doc.get('counts')
                    row['dropped'] = len(doc.get('dropped', []))
                    try:
                        jsonschema.validate(doc, schema)
                        validate_plan(doc)
                        build_module(doc)
                        row['candidate'] = int(bool(len(tri) and any(len(w) > 5 and w[5] > 0
                                                                    for w in doc.get('windows', []))))
                    except (ValueError, jsonschema.ValidationError) as exc:
                        row['candidate'] = 0
                        row['validation_error'] = str(exc)
                elif row['adapter']['exit'] == 1:
                    last = row['adapter']['log_tail'][-1:]
                    if last and last[0].startswith(('refused:', 'no window objects', 'reveal ', 'no typical',
                                                   'no wall', 'no contour', 'no typical-floor')):
                        row['candidate'] = 0
            print(tower, iteration, row['baseline'], row['candidate'], row.get('adapter', {}).get('log_tail'), flush=True)
            save()
        if iteration == 1:
            first = time.perf_counter() - started
            receipt['first_pair_wall_s'] = round(first, 3)
            deadline = min(deadline, started + 5 * first)
    for original, expected in INPUTS.items():
        check(original, expected)
        check(out / original.name, expected)
    receipt['source_parity'] = True
    receipt['status'] = 'finished'
    receipt['series_wall_s'] = round(time.perf_counter() - started, 3)
    save()


if __name__ == '__main__':
    blender = BLENDER.parent.with_name('Blender 4.4') / BLENDER.name if '--blender44' in sys.argv else BLENDER
    main(Path(sys.argv[1]).resolve(), blender, '--blender51-native' in sys.argv)
