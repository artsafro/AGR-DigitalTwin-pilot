"""Replay unchanged #17 R3 on frozen #18 accepted controls, with no production writes."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import statistics
import subprocess
import sys
from typing import Any

from dt_ai.core.blender_runner import run_blender

ROOT = Path(__file__).resolve().parents[3]
REV = '6ae13568ca85bb3880e84f4f1a30f22f6c23a96d'
HARNESS = 'docs/research/autoresearch-body-mesh-neighbours-harness/'
DUMP = 'tools/blender/mesh_quality_dump.py'
INPUTS = {
    '63A-v005': ('G:/Мой диск/AGR-evidence/1619-body-training/tower-A/v005/63A_Stage1_v005.fbx',
                 'f3769c62a7e9fdbfcf7a59624269bcd0374ca494f593e2e85c08474a0007798a'),
    'G22-k2-v002r1': ('C:/x/ev_1619/r7/k2_v002r1.mq.json',
                     '2e922754e8b77f854627267fc75b1ba9c22c41a7c4713333fc34ba0ffaff431b'),
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def git_blob(rev, path):
    return subprocess.check_output(['git', 'show', f'{rev}:{path}'], cwd=ROOT)


def main(out):
    old: dict[str, Any] = {'__name__': 'ar18_pinned', '__file__': str(ROOT / HARNESS / 'neighbours.py')}
    exec(compile(git_blob(REV, HARNESS + 'neighbours.py'), old['__file__'], 'exec'), old)
    pinned = old['pinned']
    g = pinned(old['GRID_REV'], 'docs/research/autoresearch-body-mesh-grid-harness/grid.py')
    witness = pinned(g['AR14'], g['LOCAL'] + 'witness.py')
    historical_bytes = git_blob(REV, HARNESS + 'r3.json')
    historical = json.loads(historical_bytes)
    core = g['CORE']
    code = (ROOT / core).read_text(encoding='utf-8')
    new = old['candidate'](code, g['splice'])
    if (sha(code.encode()) != historical['source_core_sha256']
            or sha(new.encode()) != historical['candidate_core_sha256']
            or historical['worst_min_margin'] < 0.5
            or not historical['translation_invariant']):
        raise ValueError('pinned calibration or variant mismatch')
    if (ROOT / DUMP).read_text(encoding='utf-8') != git_blob(g['FROZEN'], DUMP).decode('utf-8'):
        raise ValueError('native dump owner differs from pinned calibration')
    base, variant = {}, {}
    exec(compile(code, core, 'exec'), base)
    exec(compile(new, core, 'exec'), variant)
    witness['witness'](base['score'], variant['score'])
    canon = witness['canonical']
    out.mkdir(parents=True, exist_ok=False)
    tmp = out / 'temp'
    tmp.mkdir()
    os.environ.update(dict.fromkeys(('TEMP', 'TMP', 'TMPDIR'), str(tmp)))
    rows = {}
    for name, (path, expected) in INPUTS.items():
        source = Path(path)
        if sha(source.read_bytes()) != expected:
            raise ValueError(f'source hash drift: {name}')
        if source.suffix == '.fbx':
            copy = out / source.name
            shutil.copyfile(source, copy)
            if sha(copy.read_bytes()) != expected:
                raise ValueError('private FBX copy hash drift')
            dump_path = out / '63A.dump.json'
            run_blender(ROOT / DUMP, [copy, dump_path], output_json=dump_path,
                        log_path=out / 'blender.log', cwd=out, timeout=90)
            if sha(copy.read_bytes()) != expected:
                raise ValueError('private FBX changed during import')
        else:
            dump_path = source
        raw = dump_path.read_bytes()
        dump = json.loads(raw)
        a, b = [], []
        for _ in range(3):
            a.append(base['score'](dump['objects']))
            b.append(variant['score'](dump['objects']))
        if a != [a[0]] * 3 or b != [b[0]] * 3 or canon(a[0]) != canon(b[0]):
            raise ValueError(f'nonrepeatable result or report parity failure: {name}')
        diffs = [round(x['score'] - y['score'], 3) for x, y in zip(a, b, strict=True)]
        if sha(source.read_bytes()) != expected or sha(dump_path.read_bytes()) != sha(raw):
            raise ValueError(f'input changed while scoring: {name}')
        rows[name] = {'source_sha256': expected, 'dump_sha256': sha(raw), 'blender': dump.get('blender'),
                      'dump_dropped': dump.get('dropped', []), 'totals': a[0]['totals'],
                      'R0': [r['score'] for r in a], 'R3': [r['score'] for r in b],
                      'local': b[0]['local_irregular_area_share'],
                      'median_drop': statistics.median(diffs), 'paired_spread': max(diffs) - min(diffs)}
    maximum = max(r['median_drop'] for r in rows.values())
    receipt = {'prior_revision': REV, 'prior_receipt_sha256': sha(historical_bytes),
               'prior_worst_margin': historical['worst_min_margin'],
               'R0_sha256': sha(code.encode()), 'R3_sha256': sha(new.encode()), 'rows': rows,
               'max_median_drop': maximum, 'threshold': 0.5, 'passed': maximum <= 0.5,
               'clean_checks': ['synthetic clean and reset', 'canonical report parity', 'input checksums'],
               'injected_checks': ['pinned synthetic skew witness'],
               'not_measured': ['held-out rejected pair', 'verified clean rounded/oblique envelope',
                                'fresh G22 k2 native readback', 'body-core candidate', 'delivery QA']}
    with (out / 'holdout.json').open('x', encoding='utf-8', newline='\n') as f:
        f.write(json.dumps(receipt, indent=2, ensure_ascii=False) + '\n')
    print(f'{maximum:.3f}')


if __name__ == '__main__':
    main(Path(sys.argv[1]).resolve())
