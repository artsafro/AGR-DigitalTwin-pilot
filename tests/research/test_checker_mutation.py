"""new-case: fail-closed exact-oracle mutation research contract (#1261)."""
import copy
import importlib.util
from pathlib import Path

import pytest

PATH = Path(__file__).resolve().parents[2] / 'tools/research/checker_mutation_guard.py'


def load():
    spec = importlib.util.spec_from_file_location('checker_mutation_guard', PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def finding(status='pass', code='V004/topology defects'):
    return {'code': code, 'status': status, 'observed': '0 defects'}


def test_exact_oracle():
    g = load()
    oracle = {'etalon': [finding()]}
    assert g.guard(oracle, copy.deepcopy(oracle)) is True


@pytest.mark.parametrize('changed', [[], [finding('review')], [finding('fail')], [finding('not_run')],
                                      [finding(code='V003/object types')]])
def test_guard_rejects_changes(changed):
    g = load()
    with pytest.raises(ValueError):
        g.guard({'etalon': [finding()]}, {'etalon': changed})
    with pytest.raises(ValueError):
        g.guard({'etalon': [finding('fail')]}, {'etalon': [finding()]})


def test_score_requires_expected_new_finding():
    g = load()
    clean = [finding()]
    assert g.caught(clean, [finding('fail')], ['V004/topology defects'])
    assert not g.caught(clean, [finding('fail')], ['V012/mesh names'])
    assert not g.caught([finding('fail')], [finding('fail')], ['V004/topology defects'])
    assert not g.caught(clean, [finding('not_run')], ['V004/topology defects'])


@pytest.mark.parametrize('bad', [[], {}, [finding('unknown')], [dict(finding(), observed=float('nan'))],
                               [{'code': 'V004/x', 'status': 'pass'}], [finding(), finding()]])
def test_invalid_findings(bad):
    with pytest.raises(ValueError):
        load().validate(bad)


def test_identity_and_repeats():
    g = load()
    a = finding()
    b = finding(code='V002/units')
    assert g.guard({'e': [a, b]}, {'e': [b, a]})
    for _ in range(10):
        assert g.caught([a], [finding('review')], [a['code']])


def test_hash_drift(tmp_path):
    g = load()
    p = tmp_path / 'scene.json'
    p.write_text('first')
    expected = g.sha256(p)
    g.verify_files(tmp_path, {'scene.json': expected})
    p.write_text('second')
    with pytest.raises(ValueError, match='hash'):
        g.verify_files(tmp_path, {'scene.json': expected})


def test_cli_aliases(tmp_path):
    import subprocess
    import sys
    p = tmp_path / 'oracle.json'
    p.write_text('{"e": [{"code": "V004/x", "status": "pass", "observed": "ok"}]}')
    before = p.read_bytes()
    result = subprocess.run([sys.executable, str(PATH), str(p), str(p), '--output', str(p)], capture_output=True)
    assert result.returncode != 0
    assert p.read_bytes() == before


def test_new_check_must_pass_every_etalon():
    g = load()
    before = {'e': [finding()]}
    new = finding(code='V005/new rule')
    assert g.guard(before, {'e': [finding(), new]})
    for status in ['review', 'fail', 'not_run']:
        with pytest.raises(ValueError):
            g.guard(before, {'e': [finding(), dict(new, status=status)]})


@pytest.mark.parametrize('value', ['NaN', 'Infinity', '-Infinity'])
def test_nonfinite_json_is_rejected(tmp_path, value):
    p = tmp_path / 'oracle.json'
    p.write_text('{"x": '+value+'}')
    with pytest.raises(ValueError):
        load().read(p)


def test_duplicate_json_key_is_rejected(tmp_path):
    p = tmp_path / 'oracle.json'
    p.write_text('{"e": [], "e": []}')
    with pytest.raises(ValueError, match='duplicate key'):
        load().read(p)


def test_manifest_escape_and_aliases(tmp_path):
    g = load()
    p = tmp_path / 'scene.json'
    p.write_text('source')
    digest = g.sha256(p)
    with pytest.raises(ValueError):
        g.verify_files(tmp_path, {'scene.json': digest, './scene.json': digest})
    with pytest.raises(ValueError):
        g.verify_files(tmp_path, {'../scene.json': digest})


def test_fresh_process_cli_and_existing_output(tmp_path):
    import json
    import subprocess
    import sys
    a, b, out = [tmp_path / n for n in ['a.json', 'b.json', 'result.json']]
    a.write_text(json.dumps({'e': [finding()]}))
    b.write_bytes(a.read_bytes())
    cmd = [sys.executable, str(PATH), str(a), str(b), '--output', str(out)]
    first = subprocess.run(cmd, capture_output=True)
    assert first.returncode == 0, first.stderr
    assert json.loads(out.read_text()) == {'guard': 'PASS', 'new_false_alarms': 0}
    before = out.read_bytes()
    assert subprocess.run(cmd, capture_output=True).returncode != 0
    assert out.read_bytes() == before
    assert a.read_bytes() == b.read_bytes()


def test_generated_status_transition_probe():
    g = load()
    statuses = ['pass', 'fail', 'review', 'not_run']
    for old in statuses:
        for new in statuses:
            before, after = {'e': [finding(old)]}, {'e': [finding(new)]}
            if old == new:
                assert g.guard(before, after)
            else:
                with pytest.raises(ValueError):
                    g.guard(before, after)

