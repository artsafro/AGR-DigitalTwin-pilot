"""Synthetic issue #386 regression; new-case, explicitly selected, never a delivery gate."""
import copy
import hashlib
import json
import math
import os
import shutil
import subprocess
from pathlib import Path
import sys

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / 'src'))
import driver
import compatibility as guard


def frozen():
    return json.loads((HERE / 'results.json').read_text(encoding='utf-8'))


def test_frozen_results():
    assert guard.validate_results(frozen(), driver.P)


def test_frozen_evidence_bytes():
    files = [HERE / 'predictions.json', HERE / 'results.json', *sorted((HERE / 'raw').glob('*.json'))]
    assert len(files) == 56
    digest = hashlib.sha256()
    for path in files:
        digest.update(path.relative_to(HERE).as_posix().encode())
        digest.update(path.read_bytes())
    assert digest.hexdigest() == 'f335613b2590ba71ce6a8ca83098217d4afb83294df5709367c0c1d21401f70d'


@pytest.mark.parametrize('filename', sorted(p.name for p in (HERE / 'raw').glob('*.json')))
def test_frozen_raw_receipt(filename):
    """Exhaustive 54 receipts; recompute every raw vertex transform and pair."""
    data = json.loads((HERE / 'raw' / filename).read_text(encoding='utf-8'))
    objs = data['objects']
    guard.inventory(objs, driver.local_scene())
    for obj in objs:
        m = obj['matrix_world']
        world = [[sum(m[r][c] * v[c] for c in range(3)) + m[r][3] for r in range(3)] for v in obj['raw']]
        assert world == obj['world']
    stem = filename.replace('_readback.json', '').replace('_prefbx.json', '')
    result = frozen()
    row = next(r for r in result['rows'] if stem == f"{r['arm']}_r{r['rep']}_a{r['angle']}_t{r['t'][0]}_{r['t'][1]}")
    oracle = {n: driver.xform(v, row['angle'], row['t']) for n, v in driver.local_scene().items()}
    failures = []
    boxes, meta = driver.structure([dict(o, tris=o.get('tris', driver.BOX_TRIS)) for o in objs], oracle, failures, filename)
    assert not failures
    gaps = [driver.measure(boxes, g, k) for k, g in enumerate(driver.P['gaps_m'])]
    pre = '_prefbx' in filename
    assert gaps == (row['prefbx']['gaps'] if pre else row['imported'])
    assert meta == (row['prefbx']['meta'] if pre else row['meta'])
    if row['arm'] == 'B_local':
        assert all(o['matrix_world'] == objs[0]['matrix_world'] for o in objs)


LIMITS = [driver.T[k] for k in ('analytic_abs_error_m_max', 'local_prefbx_gap_error_m_max',
          'local_imported_gap_error_m_max', 'local_corner_distance_m_max', 'repeat_gap_diff_m_max')]
LIMITS.append(driver.T['baked_control']['tolerance_mm'])


@pytest.mark.parametrize('limit', LIMITS)
@pytest.mark.parametrize('kind', ['below', 'equal', 'above', 'nan', 'inf', 'negative', 'none'])
def test_strict_boundaries(limit, kind):
    value = {'below': math.nextafter(limit, 0), 'equal': limit, 'above': math.nextafter(limit, math.inf),
             'nan': math.nan, 'inf': math.inf, 'negative': -1, 'none': None}[kind]
    if kind == 'below':
        guard.below(value, limit, 'synthetic')
    else:
        with pytest.raises(ValueError):
            guard.below(value, limit, 'synthetic')


@pytest.mark.parametrize('index', range(36))
def test_every_scene_is_mandatory(index):
    result = frozen()
    result['rows'].pop(index)
    with pytest.raises(ValueError, match='scene matrix'):
        guard.validate_results(result, driver.P)


@pytest.mark.parametrize('index', range(18))
def test_each_local_scene_is_checked(index):
    result = frozen()
    row = [r for r in result['rows'] if r['arm'] == 'B_local'][index]
    row['meta']['P0_A']['corner_dist_m'] = driver.T['local_corner_distance_m_max']
    with pytest.raises(ValueError, match='corner'):
        guard.validate_results(result, driver.P)


@pytest.mark.parametrize('kind', ['empty', 'unsupported', 'nan', 'inf', 'native', 'matrix', 'delivery', 'duplicate', 'pair'])
def test_corrupt_result(kind):
    result = frozen()
    if kind == 'empty':
        result['rows'] = []
    elif kind == 'unsupported':
        result['rows'][0]['arm'] = 'UNMAPPED'
    elif kind in ('nan', 'inf'):
        result['rows'][0]['imported'][0]['gap_m'] = float(kind)
    elif kind == 'native':
        result['rows'][0]['export_rc'] = 1
    elif kind == 'matrix':
        next(r for r in result['rows'] if r['arm'] == 'B_local')['imported_matrices']['P0_A'][0][0] += 1
    elif kind == 'delivery':
        result['delivery_passed'] = True
    elif kind == 'duplicate':
        result['rows'][0] = copy.deepcopy(result['rows'][1])
    else:
        result['rows'][0]['imported'].pop()
    with pytest.raises((ValueError, KeyError, TypeError)):
        guard.validate_results(result, driver.P)


def dump():
    return {'meshes': [dict(name=n, vertices=v, triangles=driver.BOX_TRIS, material_ids=[1]*12,
                            matrix_world=driver.matrix(37, [-1170, -14200, 0]))
                       for n, v in driver.local_scene().items()]}


@pytest.mark.parametrize('kind', ['valid', 'empty', 'partial', 'unknown', 'duplicate', 'key', 'material', 'slot', 'nan', 'inf'])
def test_synthetic_dump(kind):
    data = dump()
    if kind == 'empty':
        data['meshes'] = []
    elif kind == 'partial':
        data['meshes'].pop()
    elif kind == 'unknown':
        data['meshes'][0]['name'] = 'UNMAPPED'
    elif kind == 'duplicate':
        data['meshes'].append(data['meshes'][0])
    elif kind == 'key':
        data['meshes'][0]['UNMAPPED'] = 1
    elif kind == 'material':
        data['meshes'][0]['material_ids'][0] = 73
    elif kind == 'slot':
        data['meshes'][0]['slot'] = 'UNMAPPED'
    elif kind in ('nan', 'inf'):
        data['meshes'][0]['matrix_world'][0][0] = float(kind)
    if kind == 'valid':
        guard.synthetic_dump(data)
    else:
        with pytest.raises(ValueError):
            guard.synthetic_dump(data)


@pytest.mark.parametrize('a,b', [(a,b) for a in range(4) for b in range(a+1,4)])
def test_all_path_aliases(tmp_path, a, b):
    paths = [tmp_path / str(i) for i in range(4)]
    paths[b] = paths[a]
    paths[0].write_text('synthetic source')
    with pytest.raises(ValueError):
        guard.paths(paths[0], *paths[1:])
    assert paths[0].read_text() == 'synthetic source'


def test_sidecar_and_hardlink_aliases(tmp_path):
    source = tmp_path / 'source'
    source.write_text('synthetic source')
    out = tmp_path / 'out'
    guard.paths(source, out)
    with pytest.raises(ValueError):
        guard.paths(source, out, Path(str(out) + '.partial'))
    os.link(source, out)
    with pytest.raises(ValueError):
        guard.paths(source, out)
    assert source.read_text() == 'synthetic source'


def test_native_opt_in():
    if os.environ.get('RUN_HYP_386') != '1':
        pytest.skip('explicit opt-in RUN_HYP_386=1; no DCC run by default')
    exe = shutil.which(driver.BLENDER)
    if not exe:
        pytest.skip('Blender 5.1.x not available')
    version = subprocess.run([exe, '--version'], capture_output=True, text=True, check=True).stdout
    if not driver.re.match(r'^Blender 5\.1\.\d+\b', version):
        pytest.skip('requires Blender 5.1.x')
    # New directory inside this worktree; never overwrite frozen evidence or use external temp.
    import uuid
    work = HERE / 'runs' / uuid.uuid4().hex
    driver.main(work, work / 'results.json')
    assert guard.validate_results(json.loads((work / 'results.json').read_text()), driver.P)


@pytest.mark.parametrize('status', ['REJECTED', 'INCONCLUSIVE', 'fail', 'review', 'not_run', 'unknown'])
def test_hostile_status_and_stale_results(status):
    result = frozen()
    assert guard.validate_results(result, driver.P)
    result['verdict'] = status
    with pytest.raises(ValueError, match='non-confirmed'):
        guard.validate_results(result, driver.P)


def test_second_writer_and_temp_clobber(tmp_path):
    source, out = tmp_path / 'source', tmp_path / 'out'
    source.write_text('synthetic source')
    guard.paths(source, out)
    # A second writer changes the filesystem after the first validation.
    partial = Path(str(out) + '.partial')
    partial.write_text('other writer')
    with pytest.raises(ValueError, match='output exists'):
        guard.paths(source, out)
    assert partial.read_text() == 'other writer'
    assert source.read_text() == 'synthetic source'
    assert not out.exists()


def test_fresh_process_cli_refuses_existing_work(tmp_path):
    # Refusal happens before Blender version probing; no DCC process is launched.
    env = dict(os.environ, PYTHONPATH=str(HERE.parents[1] / 'src'), DT_BLENDER='MUST_NOT_RUN')
    result = subprocess.run([sys.executable, str(HERE / 'driver.py'), str(HERE),
                             str(HERE / 'results.json')], env=env, capture_output=True, text=True)
    assert result.returncode != 0
    assert 'work must be a new directory' in result.stderr
    assert 'MUST_NOT_RUN' not in result.stderr


@pytest.mark.parametrize('case', ['empty', 'partial', 'unknown', 'duplicate'])
def test_structure_rejects_incomplete_inventory(case):
    oracle = driver.local_scene()
    objects = [dict(name=n, raw=v, world=v, tris=driver.BOX_TRIS) for n, v in oracle.items()]
    if case == 'empty':
        objects = []
    elif case == 'partial':
        objects.pop()
    elif case == 'unknown':
        objects[0]['name'] = 'UNMAPPED'
    else:
        objects.append(objects[0])
    failures = []
    driver.structure(objects, oracle, failures, 'synthetic')
    assert failures, f'{case} inventory must fail closed'
