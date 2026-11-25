"""Pattern: new-case — OBSERVE replay of a source-envelope rule, not a delivery builder."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import runpy
import shutil
import statistics
import subprocess
import sys
import time

import ezdxf
from ezdxf import recover

ROOT = Path(__file__).resolve().parents[3]
BASE = 'd9af400c08852308f5f618c9bfc0547e067d82ce'
PRIOR = 'd51167a2acdeda51429a3580eb9dda50cf6990ed'
PREFIX = 'docs/research/trainer_bounds_r101/'
PRIOR_HASHES = {
    'measure.py': '7b49322f2496b4ef4b9ca831e37044856413a83afef8bc9a7e3f7cefa88cd494',
    'manifest.json': '1604102733159f655758099e763aaef624824a0ea4a1b209945f91df51c40595',
}
AC05 = Path('G:/Мой диск/AGR-evidence/tec26-oks/AC05/gate1-v004/AC05-readback-v002.dxf')
AC05_HASH = '84486940c29c1bbb288486f2b62f4fb9d3d7b8addf002e3f1e0b8be846461a73'
BLENDER_HASH = '1e6624af112b3c936f4b038b025ebd2bf00ae72c4b62881a6787166d71c58fa5'
SUFFIXES = ('-IDEN', '-TEXT', '-NOTE', '-DIMS')
INPUTS = ('l03_dxf', 'l01_dxf', 'frame', 'key', 'rejected')
CODE = ('tools/trainer/trainer.py', 'tools/blender/fbx_readback.py',
        'src/dt_ai/core/blender_runner.py', 'pyproject.toml', 'uv.lock')

sys.path.insert(0, str(ROOT))
from tools.trainer import trainer  # noqa: E402


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha_file(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def git_blob(ref, path):
    return subprocess.check_output(['git', 'show', f'{ref}:{path}'], cwd=ROOT)


def freeze_check(fixture, prior_dir, driver_hash):
    if sys.version_info[:3] != (3, 14, 7) or ezdxf.__version__ != '1.4.3':
        raise ValueError('expected Python 3.14.7 and ezdxf 1.4.3')
    files = {str(fixture[name][0]): fixture[name][1] for name in INPUTS}
    files.update({str(AC05): AC05_HASH, trainer._blender(): BLENDER_HASH,
                  str(Path(__file__)): driver_hash})
    files.update({str(prior_dir / name): h for name, h in PRIOR_HASHES.items()})
    for path, expected in files.items():
        if sha_file(path) != expected:
            raise ValueError(f'input SHA-256 mismatch: {path}')
    code = {path: sha_bytes(git_blob(BASE, path)) for path in CODE}
    for path, expected in code.items():
        if sha_bytes((ROOT / path).read_bytes().replace(b'\r\n', b'\n')) != expected:
            raise ValueError(f'code parities no longer match {BASE}: {path}')
    return {'fixture': {name: fixture[name] for name in INPUTS}, 'other': files, 'code_git_lf': code}


def strip_annotations(entities):
    kept = [e for e in entities if not e.dxf.layer.endswith(SUFFIXES)]
    removed = Counter(e.dxf.layer for e in entities if e.dxf.layer.endswith(SUFFIXES))
    return kept, {'removed': sum(removed.values()), 'by_layer': dict(sorted(removed.items())),
                  'coverage': 'exercised' if removed else 'not_exercised'}


def paired_run(m, work, k):
    work.mkdir()
    plan = list(m['read'](k['l03_dxf'][0])[0])
    facade = list(m['read'](k['l01_dxf'][0])[0])
    frame = json.loads(Path(k['frame'][0]).read_text(encoding='utf-8'))
    phys = m['PHYS']

    def envelope(p, f, layers=phys):
        fp, counts = m['plan_footprint'](p, layers)
        z_top = m['facade_top'](f)
        if fp is None or z_top is None:
            raise ValueError('KPP1 physical layout missing')
        return m['envelope'](fp, 0.0, z_top, frame, layers), counts

    p, delta_p = strip_annotations(plan)
    f, delta_f = strip_annotations(facade)
    baseline, base_counts = envelope(plan, facade)
    candidate, candidate_counts = envelope(p, f)
    p_again, delta_p_again = strip_annotations(p)
    f_again, delta_f_again = strip_annotations(f)
    duplicate, _ = envelope(p_again, f_again)
    stairs_off, stairs_counts = envelope(p, f, tuple(label for label in phys if label != 'S-STRS-'))

    # Clone one boxable physical wall entity; never change the original.
    ent, ebox = next((e, b) for e, b in m['boxes'](p)
                     if e.dxf.layer.startswith('A-WALL-') and e.dxftype() == 'LINE')
    injected = ent.copy()
    west = m['box_of'](baseline)[0][0]
    east_of_world_origin = (west - 2.0 - frame['frame_shift_m'][0]) * 1000 + frame['origin_mm'][0]
    injected.translate(east_of_world_origin - ebox[0], 0, 0)
    injected.dxf.layer = 'A-WALL-TEST-IDEN'
    injection_base, _ = envelope([*plan, injected], facade)
    injected_p, injected_delta = strip_annotations([*plan, injected])
    injection_candidate, _ = envelope(injected_p, f)
    injection_dx = m['box_of'](injection_base)[0][0] - west

    # Evaluate only after all source-only candidate envelopes exist.
    boxes = {}
    for name in ('key', 'rejected'):
        source = Path(k[name][0])
        staged = work / f'{name}.fbx'
        shutil.copyfile(source, staged)
        if sha_file(staged) != k[name][1]:
            raise ValueError(f'staged FBX identity mismatch: {name}')
        boxes[name] = trainer.readback(staged, work / f'{name}.json', work)
        if boxes[name] is None:
            raise ValueError(f'fresh trainer readback failed for {name}; see {work}')

    key = boxes['key']
    baseline_step = trainer.bounds_step(baseline, key)
    candidate_step = trainer.bounds_step(candidate, key)
    baseline_faces, candidate_faces = m['faces'](baseline, key), m['faces'](candidate, key)
    west_gain = abs(baseline_faces['x_min']) - abs(candidate_faces['x_min'])
    stair_east = m['faces'](stairs_off, key)['x_max']
    accepted = trainer.bounds_step(key, key)
    rejected = trainer.bounds_step(boxes['rejected'], key)
    return {
        'E1': {'step': baseline_step, 'faces_m': baseline_faces, 'plan_counts': base_counts},
        'E1b': {'step': candidate_step, 'faces_m': candidate_faces, 'plan_counts': candidate_counts,
                'matches': {'L03': delta_p, 'L01': delta_f}, 'west_gain_m': round(west_gain, 4)},
        'calibration': {'accepted_identity': accepted, 'rejected': rejected,
                        'ok': accepted['status'] == 'pass' and rejected['status'] == 'fail' and
                        rejected['max_corner_dev_m'] > accepted['max_corner_dev_m']},
        'clean_reapply': {'parity': duplicate == candidate, 'L03': delta_p_again, 'L01': delta_f_again},
        'injected_plan_iden': {'e1_shift_m': round(injection_dx, 4), 'e1b_parity': injection_candidate == candidate,
                               'L03_incremental_removed': injected_delta['removed'] - delta_p['removed'],
                               'L03_coverage': 'exercised', 'L01_incremental_removed': 0,
                               'L01_coverage': 'not_exercised'},
        'native_stair_ablation': {'east_error_m': stair_east, 'L03_removed_from_envelope':
                                  candidate_counts.get('S-STRS-', 0) - stairs_counts.get('S-STRS-', 0),
                                  'L01_changed': 0, 'L01_coverage': 'not_exercised'},
        'witnesses_ok': (west_gain >= .30 and delta_p['removed'] > 0 and duplicate == candidate and
                         delta_p_again['removed'] == delta_f_again['removed'] == 0 and injection_dx <= -1.9 and
                         injection_candidate == candidate and injected_delta['removed'] == delta_p['removed'] + 1
                         and stair_east <= -3.9),
        'gain_m': round(baseline_step['max_corner_dev_m'] - candidate_step['max_corner_dev_m'], 4),
    }


def eligibility(phys):
    try:
        doc = ezdxf.readfile(AC05)
        strict_error = None
        fixes = errors = 0
    except ezdxf.DXFStructureError as exc:
        strict_error = str(exc)
        doc, audit = recover.readfile(AC05)
        fixes, errors = len(audit.fixes), len(audit.errors)
    census = Counter(e.dxf.layer for e in doc.modelspace())
    matching = {k: v for k, v in census.items() if k.startswith(phys)}
    return {'fixture': 'TEC26 AC05', 'status': 'not_exercised', 'scoring': 'not measured',
            'strict_error': strict_error, 'recovery_fixes': fixes, 'recovery_errors': errors,
            'drawing_units': doc.units, 'physical_prefix_counts': matching,
            'layers_seen': len(census), 'most_common': census.most_common(8)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    started = time.monotonic()
    out = args.out.resolve()
    out.mkdir()
    prior_dir = out / 'replay' / 'r101'
    prior_dir.mkdir(parents=True)
    for name, expected in PRIOR_HASHES.items():
        data = git_blob(PRIOR, PREFIX + name)
        if sha_bytes(data) != expected:
            raise ValueError(f'prior {name} hash mismatch')
        (prior_dir / name).write_bytes(data)
    k = json.loads((prior_dir / 'manifest.json').read_bytes())['kpp1']
    driver = sha_file(__file__)
    manifest = freeze_check(k, prior_dir, driver)
    m = runpy.run_path(str(prior_dir / 'measure.py'))
    held_out = eligibility(m['PHYS'])
    pairs = []
    stop = 'complete'
    for i in range(1, 4):
        if 180 - (time.monotonic() - started) < 35:
            stop = 'budget stop'
            break
        pair_start = time.monotonic()
        row = paired_run(m, out / f'pair{i}', k)
        row['wall_s'] = round(time.monotonic() - pair_start, 3)
        pairs.append(row)
    if freeze_check(k, prior_dir, driver) != manifest:
        raise ValueError('input parity changed')
    wall = round(time.monotonic() - started, 3)
    if wall > 180:
        stop = 'budget exceeded'
    if stop == 'complete' and len(pairs) == 3 and all(r['calibration']['ok'] and r['witnesses_ok'] for r in pairs):
        verdict = 'refuted' if any(r['gain_m'] < .30 or r['E1b']['step']['status'] != 'pass' for r in pairs) else 'inconclusive'
    else:
        verdict = 'inconclusive'
    gains = [r['gain_m'] for r in pairs]
    summary = {'verdict': verdict, 'run_status': stop, 'pairs': len(pairs), 'wall_s': wall,
               'input_parity': True, 'held_out': held_out['status'],
               'paired_gain_m': {'median': statistics.median(gains), 'range': [min(gains), max(gains)]} if gains else None,
               'median_dev_m': {n: statistics.median(r[n]['step']['max_corner_dev_m'] for r in pairs)
                                for n in ('E1', 'E1b')} if pairs else None,
               'native_candidate_passes': sum(r['E1b']['step']['status'] == 'pass' for r in pairs)}
    # Receipt paths for the script and the replayed prior artifacts are portable names.
    manifest['other'] = {'driver': manifest['other'].pop(str(Path(__file__))),
                         'r101': {n: manifest['other'].pop(str(prior_dir / n)) for n in PRIOR_HASHES},
                         **manifest['other']}
    receipt = {'schema': 'r102-receipt/1', 'base': BASE, 'prior': PRIOR,
               'summary': summary, 'held_out': held_out, 'manifest': manifest, 'pairs': pairs}
    (out / 'receipt.json').write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__':
    main()
