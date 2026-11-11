"""new-case: reproducible real-corpus intake benchmark against frozen kind candidates.

No geometry/semantic precision is inferred from heuristic-label agreement.
Run with pdf-review; --evidence and --receipts must both be NEW directories.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import time

from dt_ai.album.intake import index_album


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sources', type=Path, required=True)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--receipts', type=Path, required=True)
    args = parser.parse_args()
    if args.evidence.exists() or args.receipts.exists():
        parser.error('evidence and receipts must be fresh directories')
    args.evidence.mkdir(parents=True, exist_ok=False)
    args.receipts.mkdir(parents=True, exist_ok=False)
    refs = Path(__file__).with_name('results')
    summaries = []
    for album in ('elv', 'cod20207', 'tec26'):
        reference = json.loads((refs / f'{album}.json').read_text('utf8'))
        source = args.sources / f'{album}.pdf'
        if hashlib.sha256(source.read_bytes()).hexdigest() != reference['sha256']:
            raise ValueError(f'{album}: source hash differs from frozen research')
        timings = []
        for run in ('first', 'repeat'):
            started = time.perf_counter()
            index_album(source, args.evidence / album / run, page_budget_s=10)
            timings.append(time.perf_counter() - started)
        first, repeat = [args.evidence / album / run for run in ('first', 'repeat')]
        for name in ('album_index.json', 'manifest.json'):
            if (first / name).read_bytes() != (repeat / name).read_bytes():
                raise ValueError(f'{album}/{name}: nondeterministic')
        index = json.loads((first / 'album_index.json').read_bytes())
        if [p['pdf_page'] for p in index['pages']] != list(range(1, reference['pages'] + 1)):
            raise ValueError(f'{album}: incomplete physical page accounting')
        rows = []
        pairs = []
        for page, ref in zip(index['pages'], reference['index'], strict=True):
            expected = ref['kind_candidate'].replace('3D view', '3D')
            pairs.append((expected, page['kind']))
            rows.append(dict(pdf_page=page['pdf_page'], kind=page['kind'], expected_kind=expected,
                             status=page['status'], reason=page['reason'],
                             printed_sheet=page['printed_sheet'], title=page['title'],
                             routes=dict(Counter(r['route'] for r in page['regions'])),
                             indicators=dict(Counter(r['indicator'] for r in page['regions']))))
        scores = {}
        for kind in ('plan', 'facade', 'section', 'schedule', '3D', 'unknown'):
            tp = sum(a == b == kind for a, b in pairs)
            predicted = sum(b == kind for a, b in pairs)
            actual = sum(a == kind for a, b in pairs)
            scores[kind] = dict(correct=tp, predicted=predicted, reference=actual,
                                precision=tp / predicted if predicted else None,
                                recall=tp / actual if actual else None)
        summary = dict(album=album, source_sha256=reference['sha256'], pages=rows,
                       accounted=len(rows), reference_pages=reference['pages'],
                       kind_agreement=sum(a == b for a, b in pairs), scores=scores,
                       scope='agreement with frozen text heuristics; NOT semantic ground truth',
                       seconds=timings, deterministic=True, passed=False,
                       evidence=str(first.resolve()),
                       hashes={name: hashlib.sha256((first / name).read_bytes()).hexdigest()
                               for name in ('album_index.json', 'manifest.json')})
        (args.receipts / f'{album}.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf8', newline='\n')
        summaries.append({k: summary[k] for k in ('album', 'accounted', 'kind_agreement', 'seconds')})
    members = sorted(p for p in args.evidence.rglob('*') if p.is_file())
    seal = '\n'.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(args.evidence).as_posix()}' for p in members) + '\n'
    (args.evidence / 'SHA256SUMS.txt').write_text(seal, encoding='utf8', newline='\n')
    # Read back every member after sealing, not just the write's exit code.
    for line in seal.splitlines():
        digest, name = line.split('  ', 1)
        if hashlib.sha256((args.evidence / name).read_bytes()).hexdigest() != digest:
            raise ValueError(f'evidence readback mismatch: {name}')
    print(json.dumps(summaries))


if __name__ == '__main__':
    main()
