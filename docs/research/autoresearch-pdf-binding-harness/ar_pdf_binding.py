"""Pattern: n/a | new-case: docs/research/autoresearch-pdf-binding-harness/ar_pdf_binding.py - standing #4/#5 bind_album timing driver (OBSERVE)

OBSERVE only: time the public binder in the unchanged #1321 evaluator.

Standing #4 driver (R1 = `_chains`), extended in standing #5 with `--round R2|R3`
(R2 = indexed `_span_gap` search in `_bind_page`; R3 = R2 + R1). Run from the ignored `tmp/`.
"""
import argparse
from contextlib import contextmanager
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import statistics
import subprocess
import sys
import time
from unittest.mock import patch

from dt_ai.album import binding
from tools.research.pdf_album import dimension_autoresearch as oracle

ROOT = Path(__file__).resolve().parents[1]
TRIAL = Path('C:/x/ar_t_c528b5b4/ar_candidate_binding.py')  # archived #4 R1 candidate
TRIAL_R2 = Path(__file__).with_name('ar_candidate_r2.py')
ROUND = 'R1'
BASE = binding.bind_album


@contextmanager
def candidate():
    trial = None
    if ROUND in ('R1', 'R3'):
        spec = importlib.util.spec_from_file_location('dt_ai.album._ar_candidate', TRIAL)
        trial = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(trial)
    if ROUND == 'R1':
        with patch.object(binding, '_chains', trial._chains):
            yield
        return
    spec = importlib.util.spec_from_file_location('_ar_candidate_r2_builder', TRIAL_R2)
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    r2 = builder.build()
    if ROUND == 'R3':
        r2._chains = trial._chains
    with patch.object(binding, '_bind_page', r2._bind_page):
        yield


def replay(mutate=False):
    seconds, docs = [], []

    def timed(*args, **kwargs):
        start = time.perf_counter()
        doc = BASE(*args, **kwargs)
        seconds.append(time.perf_counter() - start)
        if mutate:
            doc['note'] = 'deliberate parity probe outside the historical score'
        docs.append(oracle.canonical(doc))
        return doc

    with patch.object(binding, 'bind_album', timed):
        result = oracle.evaluate()
    if len(docs) != 3 or not result['guard']:
        raise RuntimeError('wrong sheet count or historical guard failed')
    return sum(seconds), docs, oracle.canonical(result)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path)
    p.add_argument('--probe', action='store_true')
    p.add_argument('--round', choices=('R1', 'R2', 'R3'), default='R1')
    a = p.parse_args()
    global ROUND
    ROUND = a.round
    if a.probe:
        _, docs, result = replay()
        _, changed, unchanged = replay(mutate=True)
        if unchanged != result or changed == docs:
            raise RuntimeError('mutation did not isolate the full-document guard')
        print('Mutation: historical evaluation unchanged, exact document parity rejected')
        return 0
    if not a.out or a.out.resolve().is_relative_to(ROOT) or a.out.exists():
        p.error('--out must be a new path outside the worktree')
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    inputs = [Path(binding.__file__), TRIAL, TRIAL_R2, Path(__file__)]
    before = [sha256(f.read_bytes()).hexdigest() for f in inputs]
    start = time.perf_counter()
    _, docs, result = replay()
    runs = []
    try:
        for pair, order in enumerate(('BC', 'CB', 'BC'), 1):
            for variant in order:
                if time.perf_counter() - start >= 480:
                    raise TimeoutError('measurement limit exceeded')
                if variant == 'C':
                    with candidate():
                        seconds, observed, score = replay()
                else:
                    seconds, observed, score = replay()
                row = dict(pair=pair, variant=variant, seconds=seconds,
                           exact_docs=observed == docs, exact_score=score == result)
                runs.append(row)
                print(row, flush=True)
                if not (row['exact_docs'] and row['exact_score']):
                    raise RuntimeError('parity failed')
        if time.perf_counter() - start >= 480:
            raise TimeoutError('measurement limit exceeded')
        if before != [sha256(f.read_bytes()).hexdigest() for f in inputs]:
            raise RuntimeError('binder, candidate, or driver changed during measurement')
        med = {v: statistics.median(r['seconds'] for r in runs if r['variant'] == v) for v in 'BC'}
        pair_faster = all({r['variant']: r['seconds'] for r in runs if r['pair'] == pair}['C']
                          < {r['variant']: r['seconds'] for r in runs if r['pair'] == pair}['B']
                          for pair in (1, 2, 3))
        extra = dict(median=med, ratio=med['C'] / med['B'], all_pairs_faster=pair_faster,
                     timing_gate=pair_faster and med['C'] <= 0.80 * med['B'])
        rc = 0
    except (RuntimeError, TimeoutError, ValueError) as exc:
        extra = dict(error=str(exc), timing_gate=False)
        rc = 1
    receipt = dict(round=ROUND, head=head, python=sys.version.split()[0], runs=runs,
                   source_sha256=dict(zip([f.name for f in inputs], before)),
                   doc_sha256=[sha256(doc).hexdigest() for doc in docs],
                   result_sha256=sha256(result).hexdigest(), **extra)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    with a.out.open('x', encoding='utf-8') as f:
        json.dump(receipt, f, indent=2, allow_nan=False)
    print(extra)
    return rc


if __name__ == '__main__':
    raise SystemExit(main())
