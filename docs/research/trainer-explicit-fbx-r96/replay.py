"""Offline R96 replay; reuse the trainer's selection and native bounds checks."""

import hashlib
import json
import shutil
import sys
import time
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
from tools.trainer import trainer  # noqa: E402


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def require_hash(path, digest):
    if sha(path) != digest:
        raise ValueError(f'fixture hash mismatch: {path}')


def pick(path, etalon):
    try:
        selected, _ = trainer.pick_built(path, etalon)
        return selected, 'selected' if selected is not None else 'missing'
    except trainer.TrainerError as exc:
        if not str(exc).startswith('several FBX in '):
            raise
        return None, 'ambiguous'


def bounds(row):
    return [[func(m['bounds_m'][side][axis] for m in row['meshes']) for axis in range(3)]
            for side, func in enumerate((min, max))]


def geom(src, work, label, deadline):
    if time.monotonic() >= deadline:
        raise TimeoutError('R96 wall budget exhausted')
    row = trainer.readback(src, work / f'{label}.json', work)
    if row is None:
        raise RuntimeError(f'native readback failed: {work / (label + ".log")}')
    return row


def specimen(src, work, label, key, deadline):
    row = geom(src, work, label, deadline)
    return row, {'bounds_m': bounds(row), 'verdict': trainer.bounds_step(row, key)}


def trial(work, kpp, tower, entries, kpp_key, deadline):
    work.mkdir()
    k_etalon, tower_etalon = entries
    key = geom(kpp_key, work, 'kpp-key', deadline)
    result = {'kpp1': {}, '63b': {}}
    for run, files in kpp.items():
        stage = work / run
        copied = []
        for src in files:
            path = stage / src.parent.name / src.name
            path.parent.mkdir(parents=True)
            shutil.copyfile(src, path)
            require_hash(path, sha(src))
            copied.append(path)
        by_dir, outcome = pick(stage, k_etalon)
        records, meshes = {}, []
        for i, path in enumerate(copied):
            selected, status = pick(path, k_etalon)
            if status != 'selected' or selected != path:
                raise RuntimeError(f'failed explicit selection: {path}')
            rb, record = specimen(selected, work, f'{run}-C-{i}', key, deadline)
            records[path.relative_to(stage).as_posix()] = record
            meshes.extend(rb['meshes'])
        baseline = None
        if by_dir is not None:
            _, baseline = specimen(by_dir, work, f'{run}-B', key, deadline)
        union = {'meshes': meshes}
        result['kpp1'][run] = {'B': outcome, 'B_native': baseline, 'C': records,
                              'union_bounds_m': bounds(union),
                              'union_diagnostic': trainer.bounds_step(union, key),
                              'B_selected_same_as_C': by_dir == copied[0] if len(copied) == 1 else None}
    result['kpp1_key_bounds_m'] = bounds(key)
    key = geom(tower['v007'], work, '63b-key', deadline)
    for ver, src in tower.items():
        stage = work / ('63b-' + ver)
        stage.mkdir()
        path = stage / 'deliverable.fbx'
        shutil.copyfile(src, path)
        require_hash(path, sha(src))
        selected, clean = pick(stage, tower_etalon)
        if clean != 'selected' or selected != path:
            raise RuntimeError(f'failed clean selection: {path}')
        _, b = specimen(selected, work, f'63b-{ver}-B', key, deadline)
        before = set(stage.rglob('*.fbx'))
        decoy = stage / 'scratch' / 'body.fbx'
        decoy.parent.mkdir()
        src_decoy = tower['v004' if ver == 'v007' else 'v007']
        shutil.copyfile(src_decoy, decoy)
        require_hash(decoy, sha(src_decoy))
        _, injected = pick(stage, tower_etalon)
        selected, explicit = pick(path, tower_etalon)
        if explicit != 'selected' or selected != path:
            raise RuntimeError(f'failed explicit selection: {path}')
        _, c = specimen(selected, work, f'63b-{ver}-C', key, deadline)
        result['63b'][ver] = {'B': clean, 'I': injected, 'C': explicit, 'B_native': b, 'C_native': c,
                              'added_paths': sorted(p.relative_to(stage).as_posix()
                                                    for p in set(stage.rglob('*.fbx')) - before)}
    return result


def main(out):
    m = json.loads((HERE / 'inputs.json').read_text(encoding='utf-8'))
    for path, digest in m['sha256'].items():
        require_hash(path, digest)
    if Path(trainer._blender()).resolve() != Path(m['blender']).resolve():
        raise ValueError('trainer resolved a different Blender executable')
    bank = trainer.load_bank(m['bank'])
    entries = [trainer.etalon(bank, eid) for eid in ('kpp1-v004', '63b-stage1')]
    kpp = {}
    for run, folder in m['kpp_dirs'].items():
        files = sorted(Path(folder).rglob('*.fbx'))
        if {p.resolve() for p in files} != {Path(p).resolve() for p in m['kpp_files'][run]}:
            raise ValueError(f'FBX inventory changed: {run}')
        kpp[run] = files
    tower = {v: Path(p) for v, p in m['tower'].items()}
    out.mkdir(parents=True, exist_ok=False)
    start = time.monotonic()
    deadline = start + 240
    result = {'status': 'running', 'repeats': []}
    try:
        for i in range(1, 4):
            begin = time.monotonic()
            row = trial(out / f'repeat-{i}', kpp, tower, entries, Path(m['kpp_key']), deadline)
            row['wall_s'] = round(time.monotonic() - begin, 3)
            result['repeats'].append(row)
            if i == 1 and deadline - time.monotonic() < 2 * row['wall_s'] + 30:
                raise TimeoutError('two further pairs do not fit after the pilot')
            if time.monotonic() >= deadline:
                raise TimeoutError('R96 wall budget exhausted')
        result['status'] = 'complete'
    except (RuntimeError, TimeoutError) as exc:
        result.update(status='inconclusive', reason=str(exc))
    finally:
        result['wall_s'] = round(time.monotonic() - start, 3)
        (out / 'receipt.json').write_bytes((json.dumps(result, indent=2) + '\n').encode('utf-8'))
    print(result['status'], 'repeats:', len(result['repeats']), 'wall s:', result['wall_s'])
    return 0 if result['status'] == 'complete' else 1


if __name__ == '__main__':
    raise SystemExit(main(Path(sys.argv[1]).resolve()))
