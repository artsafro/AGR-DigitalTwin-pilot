"""new-case: synthetic source/model mode-A discrepancy and evidence contracts."""
import copy
import json
import math
import subprocess
import sys

import pytest


def synthetic_bundle():
    """Entirely synthetic, not KPP1 evidence."""
    return {
        "schema": "album-model-audit-input/1",
        "trust_rule": "D271",
        "frame": {"name": "synthetic-local-m", "placement": "synthetic identity"},
        "pdf": [{"id": "level-1", "category": "level", "mark": "roof", "facade": "F1",
                 "position_m": [0, 8], "value": 8.0, "unit": "m", "tolerance": 0.01,
                 "verified": True, "calibrated": False,
                 "evidence": {"path": "synthetic.pdf", "sha256": "a" * 64,
                              "page": 1, "sheet": "synthetic facade", "bbox": [1, 2, 3, 4],
                              "method": "synthetic vector text"}}],
        "models": [{"id": "source", "observations": [
            {"id": "roof-face", "category": "level", "mark": "roof", "facade": "F1",
             "position_m": [0, 8], "value": 8.005, "unit": "m", "verified": True,
             "object_id": "42", "object_name": "synthetic roof",
             "evidence": {"path": "synthetic.fbx", "sha256": "b" * 64,
                          "method": "synthetic measured face", "locator": "face 3"}}]}],
        "match_tolerance_m": 0.1,
    }


def test_synthetic_level_comparison_retains_both_evidences():
    from dt_ai.album.compare import compare
    bundle = synthetic_bundle()
    original = copy.deepcopy(bundle)
    result = compare(bundle)
    assert result["rows"][0]["status"] == "match"
    assert abs(result["rows"][0]["difference"] - 0.005) < 1e-12
    assert result["rows"][0]["pdf"] == bundle["pdf"][0]
    assert result["rows"][0]["model"] == bundle["models"][0]["observations"][0]
    assert result["counts"] == {"match": 1, "mismatch": 0, "needs manual check": 0}
    assert result["passed"] is False  # diagnostic, never delivery approval
    assert bundle == original


def test_all_comparison_kinds_and_two_models():
    from dt_ai.album.compare import compare
    b = synthetic_bundle()
    template, obs = b['pdf'][0], b['models'][0]['observations'][0]
    cases = [('level', 8.0, 8.2, 'm', .01, 'mismatch'),
             ('axis', 0.0, 0.0, 'm', .01, 'match'),
             ('opening_count', 4, 3, 'count', 0, 'mismatch'),
             ('finish', 'RAL 5015', 'RAL 5015', 'text', 0, 'match'),
             ('mark', 'OK-14', 'OK-15', 'text', 0, 'mismatch'),
             ('opening_size', 1.8, 1.75, 'm', .01, 'needs manual check')]
    b['pdf'], b['models'][0]['observations'] = [], []
    for category, a, value, unit, tol, status in cases:
        f = dict(copy.deepcopy(template), id=category, category=category, value=a, unit=unit, tolerance=tol)
        o = dict(copy.deepcopy(obs), id=category, category=category, value=value, unit=unit)
        b['pdf'].append(f)
        b['models'][0]['observations'].append(o)
    b['models'].append(dict(id='r1', observations=copy.deepcopy(b['models'][0]['observations'])))
    r = compare(b)
    assert [x['status'] for x in r['rows']] == [x[-1] for x in cases] * 2
    assert r['counts'] == {'match': 4, 'mismatch': 6, 'needs manual check': 2}
    assert r['rows'][-1]['reason'] == 'opening size pending calibrated album extraction (#1302)'


def test_unknown_and_ambiguous_geometry_never_choose_first():
    from dt_ai.album.compare import compare
    b = synthetic_bundle()
    o = b['models'][0]['observations'][0]
    b['models'][0]['observations'].append(dict(copy.deepcopy(o), id='duplicate-location'))
    r = compare(b)
    assert r['rows'][0]['status'] == 'needs manual check'
    assert r['rows'][0]['model'] is None
    assert len(r['rows'][0]['candidates']) == 2
    assert len(r['unmatched_model_observations']) == 2
    b['models'][0]['observations'].pop()
    o['position_m'] = [1, 8]  # same mark, wrong geometry
    assert compare(b)['rows'][0]['status'] == 'needs manual check'
    o['position_m'] = [0, 8]
    o['verified'] = False
    assert compare(b)['rows'][0]['status'] == 'needs manual check'
    o['verified'] = True
    o['value'] = None
    assert compare(b)['rows'][0]['status'] == 'needs manual check'


@pytest.mark.parametrize('mutation', [
    lambda b: b.update(pdf=[]),
    lambda b: b.update(models=[]),
    lambda b: b['pdf'].append(copy.deepcopy(b['pdf'][0])),
    lambda b: b['models'].append(copy.deepcopy(b['models'][0])),
    lambda b: b['models'][0]['observations'].append(copy.deepcopy(b['models'][0]['observations'][0])),
    lambda b: b['pdf'][0].update(category='unmapped-material-slot'),
    lambda b: b['pdf'][0]['evidence'].pop('bbox'),
    lambda b: b['models'][0]['observations'][0].pop('object_id'),
    lambda b: b.update(match_tolerance_m=0),
    lambda b: b['pdf'][0].update(verified='true'),
    lambda b: b['pdf'][0].update(extra_default_material='forbidden'),
])
def test_invalid_partial_duplicate_and_unmapped_inputs_fail_closed(mutation):
    from dt_ai.album.compare import compare
    b = synthetic_bundle()
    mutation(b)
    with pytest.raises(ValueError):
        compare(b)


@pytest.mark.parametrize('field', ['value', 'tolerance', 'position_m'])
@pytest.mark.parametrize('number', [math.nan, math.inf, -math.inf])
@pytest.mark.parametrize('side', ['pdf', 'model'])
def test_nonfinite_values_never_pass(field, number, side):
    from dt_ai.album.compare import compare
    b = synthetic_bundle()
    record = b['pdf'][0] if side == 'pdf' else b['models'][0]['observations'][0]
    if side == 'model' and field == 'tolerance':
        record = b  # model uses shared matching tolerance
        field = 'match_tolerance_m'
    record[field] = [number, 8] if field == 'position_m' else number
    with pytest.raises(ValueError):
        compare(b)


def test_exact_boundaries_and_missing_values():
    from dt_ai.album.compare import compare
    b = synthetic_bundle()
    f, o = b['pdf'][0], b['models'][0]['observations'][0]
    f['value'], f['tolerance'], o['value'] = 0., .125, .125
    assert compare(b)['rows'][0]['status'] == 'mismatch'
    b['match_tolerance_m'] = .125
    o['position_m'] = [.125, 8]
    assert compare(b)['rows'][0]['status'] == 'needs manual check'
    o['position_m'] = [0, 8]
    f['value'] = None
    assert compare(b)['rows'][0]['status'] == 'needs manual check'


def write_cli_input(tmp_path, bundle=None):
    b = synthetic_bundle() if bundle is None else bundle
    import hashlib
    for records, name in [(b['pdf'], 'synthetic.pdf'), (b['models'][0]['observations'], 'synthetic.fbx')]:
        p = tmp_path / name
        p.write_bytes(b'synthetic evidence')
        for r in records:
            r['evidence']['path'] = str(p)
            r['evidence']['sha256'] = hashlib.sha256(p.read_bytes()).hexdigest()
    p = tmp_path / 'input.json'
    p.write_text(json.dumps(b), encoding='utf-8')
    return p


def cli(input_path, output_dir):
    return subprocess.run([sys.executable, '-m', 'dt_ai.album.compare', '--input', str(input_path),
                           '--output-dir', str(output_dir)], capture_output=True, text=True)


def test_fresh_cli_reports_both_formats_and_refuses_stale_output(tmp_path):
    p = write_cli_input(tmp_path)
    out = tmp_path / 'report'
    r = cli(p, out)
    assert r.returncode == 0, r.stderr
    report = json.loads((out / 'report.json').read_text(encoding='utf-8'))
    assert report['counts']['match'] == 1
    assert 'synthetic facade' in (out / 'report.md').read_text(encoding='utf-8')
    before = {x: x.read_bytes() for x in out.iterdir()}
    assert cli(p, out).returncode != 0
    assert before == {x: x.read_bytes() for x in out.iterdir()}


def test_cli_fail_statuses_and_aliases_write_nothing(tmp_path):
    b = synthetic_bundle()
    b['models'][0]['observations'][0]['value'] = 9
    p = write_cli_input(tmp_path, b)
    assert cli(p, tmp_path / 'mismatch').returncode == 1
    b['pdf'][0]['value'] = None
    p = write_cli_input(tmp_path, b)
    assert cli(p, tmp_path / 'manual').returncode == 2
    before = p.read_bytes()
    assert cli(p, p).returncode != 0
    assert p.read_bytes() == before
    assert cli(p, p.parent / '.' / p.name).returncode != 0
    assert p.read_bytes() == before
    b['pdf'][0]['evidence']['sha256'] = 'f' * 64
    p.write_text(json.dumps(b), encoding='utf-8')
    out = tmp_path / 'stale'
    assert cli(p, out).returncode != 0
    assert not out.exists()


def test_repeated_pdf_schedule_pages_share_one_physical_model_observation():
    from dt_ai.album.compare import compare
    b = synthetic_bundle()
    repeated = copy.deepcopy(b['pdf'][0])
    repeated['id'] = 'repeat-on-page2'
    repeated['evidence']['page'] = 2
    b['pdf'].append(repeated)
    r = compare(b)
    assert r['counts']['match'] == 2
    assert not r['unmatched_model_observations']


def test_input_state_change_before_publication_is_refused(tmp_path, monkeypatch):
    from dt_ai.album import compare as module
    p = write_cli_input(tmp_path)
    real = module.compare
    def changed(bundle):
        r = real(bundle)
        (tmp_path / 'synthetic.fbx').write_bytes(b'changed during comparison')
        return r
    monkeypatch.setattr(module, 'compare', changed)
    out = tmp_path / 'changed'
    with pytest.raises(ValueError, match='changed/stale'):
        module.run(p, out)
    assert not out.exists()


def test_hardlinks_partial_names_and_competing_writer_do_not_clobber_inputs(tmp_path, monkeypatch):
    from dt_ai.album.compare import run
    from pathlib import Path
    p = write_cli_input(tmp_path)
    before = p.read_bytes()
    alias = tmp_path / 'alias'
    alias.hardlink_to(p)
    assert cli(p, alias).returncode != 0
    partial = tmp_path / 'report.json.partial'
    partial.hardlink_to(p)
    out = tmp_path / 'raced'
    real_mkdir = Path.mkdir
    def raced(self, *args, **kwargs):
        if self == out:
            real_mkdir(self)
            (self / 'report.json').hardlink_to(p)
        return real_mkdir(self, *args, **kwargs)
    monkeypatch.setattr(Path, 'mkdir', raced)
    with pytest.raises(FileExistsError):
        run(p, out)
    assert p.read_bytes() == before == partial.read_bytes() == (out / 'report.json').read_bytes()


def test_duplicate_json_keys_rejected_fresh_process(tmp_path):
    p = write_cli_input(tmp_path)
    text = p.read_text(encoding='utf-8')
    p.write_text(text.replace('"verified": true', '"verified": false, "verified": true', 1), encoding='utf-8')
    out = tmp_path / 'duplicate'
    r = cli(p, out)
    assert r.returncode == 3
    assert 'duplicate JSON key verified' in r.stderr
    assert not out.exists()


def test_generated_numeric_boundary_matrix():
    from dt_ai.album.compare import compare
    # Binary-exact values: independent literal integer oracle, no display rounding.
    for category in ('level', 'axis', 'opening_size'):
        for step in range(-32, 33):
            b = synthetic_bundle()
            f, o = b['pdf'][0], b['models'][0]['observations'][0]
            f.update(category=category, value=8.0, tolerance=.125, calibrated=True)
            o.update(category=category, value=8.0 + step / 128)
            row = compare(b)['rows'][0]
            assert row['status'] == ('match' if -16 < step < 16 else 'mismatch')
            assert row['difference'] == step / 128


def test_real_kpp1_receipt_keeps_manual_gates_and_evidence():
    from pathlib import Path
    from dt_ai.album.compare import compare
    root = Path(__file__).resolve().parents[1] / 'jobs/KPP1/audit-1304'
    bundle = json.loads((root / 'input-final.json').read_text(encoding='utf-8'))
    saved = json.loads((root / 'report-final/report.json').read_text(encoding='utf-8'))
    actual = compare(bundle)
    for key in ('rows', 'counts', 'unmatched_model_observations', 'frame', 'trust_rule', 'passed'):
        assert actual[key] == saved[key]
    assert len(actual['rows']) == 2 * len(bundle['pdf'])
    assert sum(actual['counts'].values()) == len(actual['rows'])
    assert actual['passed'] is False
    assert {r['pdf']['category'] for r in actual['rows']} == {
        'level', 'axis', 'finish', 'opening_count', 'mark', 'opening_size'}
    assert all(r['status'] == 'needs manual check' for r in actual['rows']
               if r['pdf']['category'] in ('opening_size', 'mark', 'axis'))
