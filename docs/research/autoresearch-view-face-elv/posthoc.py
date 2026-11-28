"""#145 POST-HOC diagnostic (not a keep, not stability evidence): sheet-level candidate-prior normalisation.

Rescores the frozen receipt: each candidate's score minus that candidate's median score over the OTHER views of the
same booklet (no GT used), then answers only with margin >= tau. Mirrors excluded.
    python docs/research/autoresearch-view-face-elv/posthoc.py docs/research/autoresearch-view-face-elv/receipt.json
"""
import json
import statistics
import sys
from collections import Counter


def group(row):
    return 'synthetic_crop' if row['case'].startswith('partial') else row['case']


def main(path):
    rows = [r for r in json.load(open(path, encoding='utf-8'))['rows'] if r['case'] != 'mirror']
    for tau in (0.05, 0.10):
        count = Counter()
        for row in rows:
            others = [o for o in rows if o['view'] != row['view']]
            adj = {k: v - statistics.median(o['scores'][k] for o in others) for k, v in row['scores'].items()}
            (best, b), (_, second) = sorted(adj.items(), key=lambda kv: -kv[1])[:2]
            pick = int(best) if b - second >= tau else None
            count[(group(row), 'abstain' if pick is None else 'correct' if pick == row['gt_az'] else 'wrong')] += 1
        print(tau, json.dumps(sorted((f'{g}.{o}', n) for (g, o), n in count.items())))


if __name__ == '__main__':
    main(sys.argv[1])
