"""OBSERVE-only vector partial-view scope experiment #158."""

import argparse
import hashlib
import json
import math
import subprocess
from pathlib import Path
from statistics import median
from time import monotonic

import pymupdf

BASE = 'e49d791c3a52203cbf88d7bc0305ec619bf95575'
FIXTURE_SHA = 'b1b892b914d034beda0b28c00da733403af2c5c516410bf4745062cf60f75940'
PDF = Path('G:/Мой диск/AGR-evidence/145-view-face-elv/run1/elv.pdf')
GLYPHS = {20: (5, 6, 606, 607, 608, 11, 12, 601, 602, 603, 8, 9, 596, 597, 598),
          23: (534, 535, 9094, 9095, 9096, 531, 532, 9089, 9090, 9091),
          24: (97, 98, 2176, 2177, 2178, 100, 101, 2181, 2182, 2183)}


def break_marks(drawings, box):
    """Return boundary glyphs in page space, not a full-scope assertion."""
    x0, y0, x1, y1 = box
    halo = pymupdf.Rect(x0 - 10, y0 - 10, x1 + 10, y1 + 10)
    strokes, fills = [], []
    for path in drawings:
        if 'rect' in path and not path['rect'].intersects(halo):
            continue
        for item in path['items']:
            if item[0] == 'l' and path['type'] == 's' and path['color'] == (0, 0, 0):
                if halo.contains(item[1]) and halo.contains(item[2]):
                    strokes.append((tuple(item[1]), tuple(item[2])))
            elif (item[0] == 're' and path['type'] == 'f' and min(path['fill']) >= .98
                  and path['fill_opacity'] >= .98 and item[1].intersects(halo)):
                fills.append(tuple(item[1]))
    result = set()
    for cross in (0, 1):
        along = 1 - cross
        shorts, longs = [], []
        for p, q in strokes:
            left, right = sorted((p, q), key=lambda t: t[cross])
            dx, dy = right[cross] - left[cross], right[along] - left[along]
            if not .5 <= abs(dy) <= 4.5:
                continue
            if 3 <= dx <= 8:
                shorts.append((left, right, dy))
            if 8 <= dx <= 15:
                longs.append((left, right, dy))
        for p, q, dy in longs:
            c = tuple((a + b) * .5 for a, b in zip(p, q))
            if not box[along] + 9 <= c[along] <= box[along + 2] - 9:
                continue
            edges = ('left', 'right') if cross == 0 else ('top', 'bottom')
            edge, delta = min(zip(edges, (abs(c[cross] - box[cross]), abs(c[cross] - box[cross + 2]))),
                              key=lambda pair: pair[1])
            if delta > 6:
                continue
            if not any(s * dy < 0 and math.dist(a, p) <= .18 for a, _, s in shorts):
                continue
            if not any(s * dy < 0 and math.dist(b, q) <= .18 for _, b, s in shorts):
                continue
            supports = {r for r in fills if 8 <= r[cross + 2] - r[cross] <= 15
                        and 2.5 <= r[along + 2] - r[along] <= 7
                        and all(r[i] - 1 <= c[i] <= r[i + 2] + 1
                                and abs((r[i] + r[i + 2]) * .5 - c[i]) <= 3 for i in (0, 1))}
            if len(supports) >= 2:
                result.add((edge, round(c[0], 3), round(c[1], 3)))
    return sorted(result)


def shifted(paths, dx, dy):
    delta = pymupdf.Point(dx, dy)
    rd = (dx, dy, dx, dy)
    return [dict(d, rect=d['rect'] + rd, items=[
        (tag, a + delta, b + delta) if tag == 'l' else (tag, a + rd, b) for tag, a, b in d['items']])
        for d in paths]


def measure(pdf, views):
    with pymupdf.open(pdf) as doc:
        pages = {n: doc[n - 1].get_drawings() for n in sorted({v['page'] for v in views.values()})}
    payload = [d for d in pages[24] if d['seqno'] in GLYPHS[24][-5:]]
    if len(payload) != 5:
        raise ValueError('Native payload paths missing')
    src = next(d['rect'] for d in payload if d['seqno'] == 2183)

    def probe(drawings, box, changed):
        marks = break_marks(drawings, box)
        return {'verdict': 'visible_break' if marks else 'unverified', 'marks': marks,
                'changed_paths': changed, 'injection': 'exercised' if changed else 'not_exercised',
                'reverse_changed_positions': len(drawings) - len(drawings) % 2,
                'reverse_equal': marks == break_marks(drawings[::-1], box)}

    rows, injected = {}, {}
    for name, v in views.items():
        page, box = v['page'], v['box_pt']
        drawings, ids = pages[page], set(GLYPHS.get(page, ()))
        scope = 'visible_break' if v['kind'].startswith('fragment') else 'unverified'
        rows[name] = {'truth': None if name == 'p19 6-1' else scope,
                      'A': 'unverified', 'B': probe(drawings, box, 0)}
        stripped = [d for d in drawings if d['seqno'] not in ids]
        removed = len(drawings) - len(stripped)
        if removed != len(ids):
            raise ValueError(f'Native glyph inventory mismatch at p{page}')
        injected[f'{name}:remove'] = probe(stripped, box, removed)
        if name == 'p18 1-10':
            x0, y0, x1, y1 = box
            for state, x, paths in [('interior', (x0 + x1) / 2, payload), ('boundary', x0, payload),
                                    ('outline_only', x0, [d for d in payload if d['type'] == 's'])]:
                graft = shifted(paths, x - (src.x0 + src.x1) / 2, (y0 + y1 - src.y0 - src.y1) / 2)
                injected[state] = probe(drawings + graft, box, len(graft))
    counts = {}
    for arm in ('A', 'B'):
        labelled = [r for r in rows.values() if r['truth'] is not None]
        choices = [r[arm] if arm == 'A' else r[arm]['verdict'] for r in labelled]
        counts[arm] = {'n': len(labelled), 'correct': sum(a == r['truth'] for a, r in zip(choices, labelled)),
                       'unverified': choices.count('unverified')}
    checks = {
        'clean': counts['B']['correct'] == 9,
        'removed_native': all(injected[f'{n}:remove']['verdict'] == 'unverified'
                              for n, v in views.items() if v['page'] in GLYPHS),
        'untouched_parity': all(injected[f'{n}:remove'] == rows[n]['B']
                                for n, v in views.items() if v['page'] not in GLYPHS),
        'graft': all(injected[s]['verdict'] == expected for s, expected in (
            ('interior', 'unverified'), ('boundary', 'visible_break'), ('outline_only', 'unverified'))),
        'triggers_exercised': all(injected[s]['changed_paths'] for s in ('interior', 'boundary', 'outline_only'))
        and all(injected[f'{n}:remove']['changed_paths'] for n, v in views.items() if v['page'] in GLYPHS),
        'invariance': all(p['reverse_equal'] for p in [*(r['B'] for r in rows.values()), *injected.values()]),
    }
    return {'counts': counts, 'views': rows, 'injections': injected, 'checks': checks}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write(path, value):
    data = (json.dumps(value, indent=2, sort_keys=True) + '\n').encode()
    path.write_bytes(data)
    return sha(data)


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('out', type=Path)
    cli.add_argument('--pdf', type=Path, default=PDF)
    args = cli.parse_args()
    started = monotonic()
    fixture = subprocess.check_output(['git', 'show', f'{BASE}:docs/research/autoresearch-view-face-elv/fixture.json'])
    if sha(fixture) != FIXTURE_SHA or pymupdf.VersionBind != '1.28.2':
        raise ValueError('Fixture hash or reader version mismatch')
    fx = json.loads(fixture)
    pdf_sha = fx['inputs']['pdf']['sha256']
    if sha(args.pdf.read_bytes()) != pdf_sha:
        raise ValueError('PDF hash mismatch')
    args.out.mkdir(parents=True, exist_ok=False)
    timings, pairs = [], []
    pair = None
    for n in range(1, 4):
        t0 = monotonic()
        pair = measure(args.pdf, fx['views'])
        timings.append(monotonic() - t0)
        pairs.append(write(args.out / f'pair-{n}.json', pair))
        if n == 1 and monotonic() - started + 2 * timings[0] > 120:
            break
    if sha(args.pdf.read_bytes()) != pdf_sha:
        raise ValueError('PDF changed during run')
    coherent = len(pairs) == 3 and len(set(pairs)) == 1
    assert pair is not None
    checks = pair['checks']
    verdict = ('inconclusive' if not coherent or not checks['triggers_exercised'] else
               'confirmed' if all(checks.values()) else 'refuted')
    receipt = {'hypothesis': verdict, 'counts': pair['counts'], 'checks': checks,
               'run_status': 'finished' if len(pairs) == 3 else 'budget_stop', 'parity': coherent,
               'pair_sha256': pairs, 'pair_wall_s': timings, 'median_s': median(timings),
               'spread_s': max(timings) - min(timings), 'fixture_sha256': FIXTURE_SHA,
               'pdf_sha256': pdf_sha, 'runner_sha256': sha(Path(__file__).read_bytes()),
               'lock_sha256': sha(Path('uv.lock').read_bytes()), 'reader': pymupdf.VersionBind}
    print('receipt_sha256', write(args.out / 'receipt.json', receipt), flush=True)
    print(json.dumps(receipt, sort_keys=True))


if __name__ == '__main__':
    main()
