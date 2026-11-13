"""new-case: frozen native dimension research scoring and zero-prediction guard."""
from __future__ import annotations

import importlib.util


def test_zero_prediction_guard():
    name = 'tools.research.pdf_album.dimension_autoresearch'
    assert importlib.util.find_spec(name) is not None, 'frozen research guard is missing'
    from tools.research.pdf_album.dimension_autoresearch import precision_guard
    metrics = {'found': 0, 'correct': 0, 'wrong': 0, 'truth': 6,
               'missed': 6, 'precision': None, 'recall': 0.0}
    assert precision_guard(metrics) == 'zero_prediction_pass'
    assert metrics['precision'] is None


def _truth():
    return [{'handle': 'A', 'measurement': 6000, 'raw': '6000',
             'orientation': 'horizontal', 'ends': [10., 100.], 'coord': 50.,
             'bbox': [40., 40., 60., 48.]}]


def _value():
    return {'id': 'd1', 'kind': 'dimension', 'value': 6000, 'raw': '6000',
            'orientation': 'horizontal', 'span': {'p0': [10., 50.], 'p1': [100., 50.]},
            'bbox': [40., 40., 60., 48.], 'binding': {'type': 'axis_pair', 'axes': ['1', '2']}}


def test_score_one_to_one_and_boundaries():
    from copy import deepcopy
    from tools.research.pdf_album.dimension_autoresearch import score
    first = _value()
    duplicate = dict(first, id='d2')
    m = score([first, duplicate], _truth())['metrics']
    assert (m['correct'], m['wrong'], m['missed']) == (1, 1, 0)
    for delta in (.499999, .5, .500001):
        for field in ('value', 'end', 'line'):
            v = deepcopy(first)
            if field == 'value':
                v['value'] += delta
            elif field == 'end':
                v['span']['p0'][0] += delta
            else:
                v['span']['p0'][1] += delta
            assert score([v], _truth())['metrics']['correct'] == (delta < .5)


def test_precision_guard_generated():
    import pytest
    from tools.research.pdf_album.dimension_autoresearch import precision_guard
    for found in range(1, 81):
        for correct in range(found + 1):
            m = dict(found=found, correct=correct, wrong=found-correct, truth=80,
                     missed=80-correct, precision=correct/found, recall=correct/80)
            assert precision_guard(m) == ('pass' if 20*correct >= 19*found else 'fail')
    for bad in (float('nan'), float('inf'), None, -.1, .95):
        with pytest.raises(ValueError):
            precision_guard(dict(found=20, correct=18, wrong=2, truth=20, missed=2,
                                 precision=bad, recall=.9))
    with pytest.raises(ValueError):
        precision_guard(dict(found=0, correct=0, wrong=0, truth=0, missed=0,
                             precision=None, recall=0))


def test_score_invalid_evidence():
    import pytest
    from copy import deepcopy
    from tools.research.pdf_album.dimension_autoresearch import score
    for bad in (float('nan'), float('inf'), -float('inf')):
        for field in ('value', 'span'):
            v = deepcopy(_value())
            if field == 'value':
                v['value'] = bad
            else:
                v['span']['p0'][0] = bad
            assert score([v], _truth())['metrics']['wrong'] == 1
    for span in (None, {}, {'p0': [10, 50]}):
        assert score([dict(_value(), span=span)], _truth())['metrics']['wrong'] == 1
    for kind in ('opening', 'unsupported', 'unknown', 'review', 'not_run', 'fail'):
        v = dict(_value(), binding={'type': kind})
        assert score([v], _truth())['metrics']['wrong'] == 1
    assert score([], _truth())['metrics']['missed'] == 1
    for truth in ([], _truth()*2, [dict(_truth()[0], measurement=float('nan'))]):
        with pytest.raises(ValueError):
            score([], truth)
    with pytest.raises(ValueError, match='duplicate prediction'):
        score([_value(), _value()], _truth())


def test_guard_refuses_drift():
    from copy import deepcopy
    from tools.research.pdf_album.dimension_autoresearch import guard_document, verdict_signature
    doc = {'passed': False, 'values': [dict(_value(), measured_mm=None)],
           'views': [{'id': 'v1', 'axes': [], 'scale': {'status': 'unknown'}}], 'findings': []}
    signature = verdict_signature(doc)
    assert guard_document(doc, signature)
    dimension_only = deepcopy(doc)
    dimension_only['findings'] = [{'code': 'dimension_text_invalid', 'id': 'd99', 'text': 'note'}]
    assert guard_document(dimension_only, signature), 'dimension IDs are not axis/level verdicts'
    for kind in ('scale', 'measured', 'passed', 'axes', 'level'):
        v = deepcopy(doc)
        if kind == 'scale': v['views'][0]['scale']['status'] = 'guessed'
        if kind == 'measured': v['values'][0]['measured_mm'] = 6000
        if kind == 'passed': v['passed'] = True
        if kind == 'axes': v['views'][0]['axes'] = [{'label': 'X'}]
        if kind == 'level': v['values'].append({'kind': 'level', 'value': 1, 'binding': {'type': 'unbound'}})
        assert not guard_document(v, signature)


def test_frozen_corpus(tmp_path):
    import json
    import pytest
    from tools.research.pdf_album.dimension_autoresearch import digest, load_corpus
    sheets = []
    for i, split in enumerate(('TUNE', 'HOLD-OUT')):
        p = tmp_path / f'{i}.pdf'
        p.write_bytes(b'synthetic, not a PDF')
        sheets.append(dict(name=str(i), split=split, truth=_truth(),
                           files={'pdf': {'path': str(p), 'sha256': digest(p.read_bytes())}}))
    manifest = tmp_path / 'corpus.json'
    manifest.write_text(json.dumps({'sheets': sheets}))
    assert len(load_corpus(manifest)['sheets']) == 2
    (tmp_path / '0.pdf').write_bytes(b'changed')
    with pytest.raises(ValueError, match='hash mismatch'):
        load_corpus(manifest)
    sheets[0]['files']['pdf'] = sheets[1]['files']['pdf']
    manifest.write_text(json.dumps({'sheets': sheets}))
    with pytest.raises(ValueError, match='aliased input'):
        load_corpus(manifest)
    sheets[1]['name'] = sheets[0]['name']
    manifest.write_text(json.dumps({'sheets': sheets}))
    with pytest.raises(ValueError, match='duplicate sheet'):
        load_corpus(manifest)


def test_committed_corpus_portable():
    import json
    from tools.research.pdf_album.dimension_autoresearch import BASELINE, CORPUS, canonical, digest
    # Git normalizes CRLF to LF. Bind the semantic manifest, not checkout newline policy.
    corpus = json.loads(CORPUS.read_text(encoding='utf8'))
    receipt = json.loads(BASELINE.read_text(encoding='utf8'))
    assert receipt['corpus_sha256'] == digest(canonical(corpus))
    assert digest(canonical(json.loads(CORPUS.read_bytes().replace(b'\r\n', b'\n')))) == receipt['corpus_sha256']


def test_replay_rejects_mutation_during_run(tmp_path, monkeypatch):
    import json
    import pytest
    from dt_ai.album import binding
    from tools.research.pdf_album import dimension_autoresearch as A
    sheets = []
    for i, split in enumerate(('TUNE', 'HOLD-OUT')):
        p = tmp_path / f'{i}.pdf'
        p.write_bytes(b'synthetic boundary injection, not a PDF')
        sheets.append(dict(name=str(i), split=split, truth=_truth(),
                           files={'pdf': {'path': str(p), 'sha256': A.digest(p.read_bytes())}}))
    corpus = tmp_path / 'corpus.json'
    raw = json.dumps({'sheets': sheets})
    corpus.write_text(raw)
    doc = {'passed': False, 'values': [], 'views': [], 'findings': []}
    baseline = tmp_path / 'baseline.json'
    receipt = {'corpus_sha256': A.digest(A.canonical(json.loads(raw))),
               'signatures': {s['name']: A.verdict_signature(doc) for s in sheets}}
    baseline.write_text(json.dumps(receipt))
    monkeypatch.setattr(A, 'CORPUS', corpus)
    monkeypatch.setattr(A, 'BASELINE', baseline)
    monkeypatch.setattr(binding, 'bind_album', lambda *a, **k: doc)
    assert A.evaluate()['guard'] is True
    for target in (tmp_path / '0.pdf', corpus, baseline):
        original = target.read_bytes()
        def rewrite(*args, **kwargs):
            target.write_bytes(original + b' ')
            return doc
        monkeypatch.setattr(binding, 'bind_album', rewrite)
        with pytest.raises(ValueError, match='hash mismatch|changed during replay'):
            A.evaluate()
        target.write_bytes(original)
    receipt['corpus_sha256'] = '0'*64
    baseline.write_text(json.dumps(receipt))
    with pytest.raises(ValueError, match='stale baseline'):
        A.evaluate()


def test_real_native_replay_and_repeat():
    import json
    import subprocess
    import sys
    import pytest
    from tools.research.pdf_album import dimension_autoresearch as A
    sheets = json.loads(A.CORPUS.read_text(encoding='utf8'))['sheets']
    from pathlib import Path
    if not all(Path(f['path']).exists() for s in sheets for f in s['files'].values()):
        pytest.skip('optional frozen native copies absent; never synthesize native evidence')
    first = A.evaluate()
    result = subprocess.run([sys.executable, '-m', 'tools.research.pdf_album.dimension_autoresearch'],
                            cwd=A.ROOT, capture_output=True, text=True, encoding='utf8', check=True)
    second = json.loads(result.stdout.splitlines()[0])
    assert first == second
    assert first['guard'] is True
    assert [(s['metrics']['found'], s['metrics']['correct'], s['metrics']['wrong'], s['metrics']['missed'])
            for s in first['sheets']] == [(7, 7, 0, 75), (10, 10, 0, 2), (0, 0, 0, 6)]
    baseline = json.loads(A.CORPUS.with_name('baseline-results.json').read_text(encoding='utf8'))
    for current, previous in zip(first['sheets'], baseline['sheets']):
        old = {r['handle'] for r in previous['handles'] if r['class'] == 'correct_semantic_binding'}
        new = {r['handle'] for r in current['handles'] if r['class'] == 'correct_semantic_binding'}
        assert old <= new, 'R1 must preserve every earlier native identity'
        assert new - old == ({'341A', '341C'} if current['sheet'] == 'KNS' else set())
    assert first['tune_recall'] == 17 / 94
    assert first['sheets'][2]['precision_guard'] == 'zero_prediction_pass'


def test_fresh_cli_read_only(tmp_path):
    import os
    import subprocess
    import sys
    from tools.research.pdf_album.dimension_autoresearch import ROOT
    # No output API exists: an attempted input alias is rejected by argparse
    # before corpus/source access. Even predictable .partial files stay untouched.
    source = tmp_path / 'source.pdf'
    source.write_bytes(b'synthetic input')
    alias = tmp_path / 'alias.pdf'
    os.link(source, alias)
    partial = tmp_path / 'alias.pdf.partial'
    partial.write_bytes(b'foreign partial')
    for spelling in (str(source), str(alias), str(alias).replace('alias.pdf', './alias.pdf')):
        result = subprocess.run([sys.executable, '-m', 'tools.research.pdf_album.dimension_autoresearch',
                                 '--output', spelling], cwd=ROOT, capture_output=True)
        assert result.returncode != 0
        assert source.read_bytes() == alias.read_bytes() == b'synthetic input'
        assert partial.read_bytes() == b'foreign partial'
