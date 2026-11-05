"""D193 texel exception: frozen, master-bound list; every other texel failure stays a failure (#371)."""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'jobs/VATUTINO-SITE/texel_exception_v015.py'
spec = importlib.util.spec_from_file_location('texel_exception_v015', SCRIPT)
tx = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tx)


def master(tmp_path, name='m.json', thin=2, verts=None, mat=None, faces=None):
    """Slot A: `thin` sliver quads (aspect 20) + one square; slot B: one square."""
    v, f, m = [], [], []
    for i in range(thin):
        o = len(v); y = 2.0 * i
        v += [[0, y, 0], [2, y, 0], [2, y + .1, 0], [0, y + .1, 0]]; f.append([o, o + 1, o + 2, o + 3]); m.append(0)
    for slot, x in ((0, 10), (1, 20)):
        o = len(v); v += [[x, 0, 0], [x + 1, 0, 0], [x + 1, 1, 0], [x, 1, 0]]; f.append([o, o + 1, o + 2, o + 3]); m.append(slot)
    d = {'verts': verts if verts is not None else v, 'faces': faces if faces is not None else f,
         'mat': mat if mat is not None else m, 'slots': ['A', 'B']}
    p = tmp_path / name
    p.write_text(json.dumps(d), encoding='utf-8')
    return p


def test_freeze_then_check_passes_and_counts(tmp_path):
    p = master(tmp_path)
    rec = tx.freeze(p, 'npm', tmp_path / 'f.json')
    assert rec['total'] == 2 and rec['slots']['A']['offenders'] == [0, 1] and rec['slots']['B']['cap'] == 0
    r = tx.check(p, 'npm', tmp_path / 'f.json')
    assert r['passed'] and r['offenders'] == 2


def test_unlisted_offender_and_cap_fail(tmp_path):
    p = master(tmp_path)
    tx.freeze(p, 'npm', tmp_path / 'f.json')
    f = json.loads((tmp_path / 'f.json').read_text())
    f['slots']['A']['offenders'] = [0]; f['slots']['A']['cap'] = 1; f['total'] = 1
    (tmp_path / 'g.json').write_text(json.dumps(f))
    r = tx.check(p, 'npm', tmp_path / 'g.json')
    assert not r['passed'] and r['unlisted'] == {'A': [1]} and r['over_cap'] == {'A': [2, 1]}
    # list kept but cap lowered: still a failure (cap must equal the list length)
    f['slots']['A']['offenders'] = [0, 1]; f['total'] = 2
    (tmp_path / 'h.json').write_text(json.dumps(f))
    assert not tx.check(p, 'npm', tmp_path / 'h.json')['passed']


@pytest.mark.parametrize('thin', [0, 1, 3, 5])
def test_generated_lists_exact_at_threshold(tmp_path, thin):
    """Probe: for N slivers the frozen total is N; dropping any one listed face fails."""
    p = master(tmp_path, thin=thin)
    rec = tx.freeze(p, 'vpm', tmp_path / 'f.json')
    assert rec['total'] == thin and tx.check(p, 'vpm', tmp_path / 'f.json')['passed']
    for k in range(thin):
        f = json.loads((tmp_path / 'f.json').read_text())
        f['slots']['A']['offenders'].pop(k); f['slots']['A']['cap'] -= 1; f['total'] -= 1
        (tmp_path / 'g.json').write_text(json.dumps(f))
        assert not tx.check(p, 'vpm', tmp_path / 'g.json')['passed']


def test_other_master_profile_or_slot_is_an_error(tmp_path):
    p = master(tmp_path)
    tx.freeze(p, 'npm', tmp_path / 'f.json')
    with pytest.raises(tx.TexelExceptionError, match='not .vpm'):
        tx.check(p, 'vpm', tmp_path / 'f.json')
    q = master(tmp_path, name='q.json', thin=1)
    with pytest.raises(tx.TexelExceptionError, match='master differs'):
        tx.check(q, 'npm', tmp_path / 'f.json')
    f = json.loads((tmp_path / 'f.json').read_text())
    f['decision'] = 'D157'
    (tmp_path / 'g.json').write_text(json.dumps(f))
    with pytest.raises(tx.TexelExceptionError, match='not a D193'):
        tx.check(p, 'npm', tmp_path / 'g.json')
    with pytest.raises(tx.TexelExceptionError, match='unsupported profile'):
        tx.offenders(p, 'NPM-Ground')


@pytest.mark.parametrize('kw,match', [
    ({'faces': [], 'mat': []}, 'no faces'),
    ({'verts': [[float('nan'), 0, 0]] * 12}, 'finite'),
    ({'verts': [[float('inf'), 0, 0]] * 12}, 'finite'),
    ({'mat': [0, 0, 0, 7]}, 'names no slot'),
    ({'mat': [0, 0, 0, True]}, 'names no slot'),
    ({'mat': [0, 0, 0]}, 'length mismatch'),
    ({'mat': [0, 0, 0, 0]}, "slot 'B' has 0 faces"),
])
def test_fail_closed_inputs(tmp_path, kw, match):
    p = master(tmp_path, **kw)
    with pytest.raises(tx.TexelExceptionError, match=match):
        tx.offenders(p, 'npm')


def test_freeze_refuses_existing_or_aliased_output(tmp_path):
    p = master(tmp_path)
    before = p.read_bytes()
    with pytest.raises(tx.TexelExceptionError):
        tx.freeze(p, 'npm', p)
    (tmp_path / 'f.json').write_text('keep')
    with pytest.raises(tx.TexelExceptionError, match='overwrite'):
        tx.freeze(p, 'npm', tmp_path / 'f.json')
    assert p.read_bytes() == before and (tmp_path / 'f.json').read_text() == 'keep'


def test_cli_fresh_process_exit_codes(tmp_path):
    p = master(tmp_path)
    run = lambda *a: subprocess.run([sys.executable, str(SCRIPT), *map(str, a)], capture_output=True, text=True)
    assert run('freeze', p, 'npm', tmp_path / 'f.json').returncode == 0
    assert run('check', p, 'npm', tmp_path / 'f.json').returncode == 0
    f = json.loads((tmp_path / 'f.json').read_text())
    f['slots']['A']['offenders'] = [0]; f['slots']['A']['cap'] = 1; f['total'] = 1
    (tmp_path / 'g.json').write_text(json.dumps(f))
    assert run('check', p, 'npm', tmp_path / 'g.json').returncode == 1
    assert run('check', p, 'vpm', tmp_path / 'f.json').returncode == 2
    assert run('check', tmp_path / 'missing.json', 'npm', tmp_path / 'f.json').returncode == 2


@pytest.mark.parametrize('profile,total', [('npm', 8511), ('vpm', 11430)])
def test_committed_lists_match_decision_caps(profile, total):
    rec = json.loads((ROOT / f'jobs/VATUTINO-SITE/ground-texel-exception-v015-{profile}.json').read_text())
    assert rec['decision'] == 'D193' and rec['profile'] == profile and rec['total'] == total
    assert sum(len(s['offenders']) for s in rec['slots'].values()) == total
    assert all(s['cap'] == len(s['offenders']) == len(set(s['offenders'])) for s in rec['slots'].values())
    assert all(0 <= i < s['faces'] for s in rec['slots'].values() for i in s['offenders'])
    row = next(r for r in (ROOT / 'docs/decisions.md').read_text(encoding='utf-8').splitlines()
               if r.startswith('| D193 |'))
    assert f'{total:,}' in row and 'texel_ready' in row and 'by construction' in row
