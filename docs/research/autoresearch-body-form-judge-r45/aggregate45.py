"""Aggregate standing #45 judge calls -> result45.json (rules frozen in autoresearch-body-form-judge-r45.md)."""
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
W = {'Q1': 3, 'Q2': 3, 'Q3': 3, 'Q4': 3, 'Q5': 2}
FAM = {'recess': ('Q1', 'W_recess', [0.20, 0.11, 0.06, 0.03]), 'corner': ('Q4', 'W_corner', [0.40, 0.20, 0.10, 0.05])}
T_C1 = {'recess': 0.06, 'corner': 0.10}          # #43 receipt M43.c1 (scene readback)
VARS = ['A', 'W_recess', 'W_corner'] + [f'P_{f}_{s:.2f}' for f, (_, _, L) in FAM.items() for s in L]
calls = [json.loads(p.read_text(encoding='utf-8')) for p in sorted((ROOT / 'calls').glob('*.json'))]
out = {'n_calls': len(calls), 'wall_s_sum': round(sum(c['wall_s'] for c in calls), 1),
       'unparsed': [c['id'] for c in calls if not c['parsed']], 'judges': {}}


def maj(vals):
    v, k = Counter(vals).most_common(1)[0]
    return v if k >= 2 else 'Unsure'


for j in ('claude', 'codex'):
    rub = [c for c in calls if c['judge'] == j and c['kind'] == 'rubric']
    cells, flips = {}, 0
    for v in VARS:
        for q in W:
            vals = [c['parsed'].get(q, 'Unsure') if c['parsed'] else 'Unsure' for c in rub if c['imgs'] == [v]]
            cells[f'{v}.{q}'] = {'calls': vals, 'majority': maj(vals) if vals else 'not_measured'}
            flips += len(set(vals)) > 1
    S = {v: sum(W[q] for q in W if cells[f'{v}.{q}']['majority'] == 'Yes') for v in VARS}
    fam = {}
    false_yes, ladder_cells = [], 0
    for f, (q, wit, L) in FAM.items():
        ladder = {s: cells[f'P_{f}_{s:.2f}.{q}']['majority'] for s in L}
        ladder_cells += len(L)
        false_yes += [f'P_{f}_{s:.2f}.{q}' for s, m in ladder.items() if m == 'Yes']
        a_ok = cells[f'A.{q}']['majority'] == 'Yes'
        w_ok = cells[f'{wit}.{q}']['majority'] == 'No'
        T = None   # inf
        for s in L:            # descending sizes; threshold = smallest s with s and all larger correct No
            if ladder[s] == 'No':
                T = s
            else:
                break
        qual = a_ok and w_ok
        fam[f] = {'cell': q, 'A': cells[f'A.{q}']['majority'], 'witness': cells[f'{wit}.{q}']['majority'],
                  'ladder': {f'{s:.2f}': m for s, m in ladder.items()}, 'qualified': qual,
                  'T': (T if T is not None else 'inf') if qual else 'not measured', 'T_C1': T_C1[f],
                  'less_sensitive_than_C1': ((T is None) or T > T_C1[f]) if qual else None}
    pairs = {}
    for c in calls:
        if c['judge'] == j and c['kind'] == 'pair':
            other = c['imgs'][1] if c['imgs'][0] == 'A' else c['imgs'][0]
            b = (c['parsed'] or {}).get('better', 'Unsure')
            pairs.setdefault(other, {})[c['order']] = {'X': c['imgs'][0], 'Y': c['imgs'][1]}.get(b, 'Unsure')
    kept = {o: d['AB'] for o, d in pairs.items() if d.get('AB') == d.get('BA') and d['AB'] != 'Unsure'}
    out['judges'][j] = {'cells': cells, 'families': fam, 'yes_bias_ladder': f'{len(false_yes)}/{ladder_cells}',
                        'false_yes_cells': false_yes, 'flip_cells': f'{flips}/{len(VARS) * len(W)}', 'S': S,
                        'S_ladder_lt_S_A': {v: S[v] < S['A'] for v in VARS[3:]},
                        'pairs_raw': pairs, 'pairs_order_consistent': kept,
                        'pair_coverage': f'{len(kept)}/{len(pairs)}',
                        'pair_A_wins_kept': f"{sum(w == 'A' for w in kept.values())}/{len(kept)}"}

c1, c2 = (out['judges'][j]['pairs_order_consistent'] for j in ('claude', 'codex'))
common = sorted(set(c1) & set(c2))
agree = sum(c1[k] == c2[k] for k in common)
labels = {c1[k] for k in common} | {c2[k] for k in common}
if common:
    po = agree / len(common)
    pe = sum((sum(c1[k] == l for k in common) / len(common)) * (sum(c2[k] == l for k in common) / len(common))
             for l in labels)
    kappa = None if pe == 1 else round((po - pe) / (1 - pe), 3)
else:
    kappa = None
out['pairwise'] = {'common_pairs': common, 'raw_agreement': f'{agree}/{len(common)}', 'kappa': kappa,
                   'kappa_note': 'undefined (single label or no common pairs)' if kappa is None else ''}
out['proxy'] = {'planted': 'not measured'}
qual = [(j, f, r) for j in out['judges'] for f, r in out['judges'][j]['families'].items() if r['qualified']]
per_judge = all(any(jj == j for jj, _, _ in qual) for j in ('claude', 'codex'))
if qual and per_judge and all(r['less_sensitive_than_C1'] for _, _, r in qual):
    h = 'confirmed'
elif qual and all(not r['less_sensitive_than_C1'] for _, _, r in qual):
    h = 'refuted'
else:
    h = 'inconclusive'
out['H45'] = h
(ROOT / 'result45.json').write_text(json.dumps(out, indent=1), encoding='utf-8')
for j in ('claude', 'codex'):
    r = out['judges'][j]
    print(j, json.dumps({k: r[k] for k in ('families', 'yes_bias_ladder', 'false_yes_cells', 'flip_cells', 'S',
                                         'pair_coverage', 'pair_A_wins_kept')}))
print('pairwise', out['pairwise'], 'H45', h, 'calls', out['n_calls'], 'unparsed', out['unparsed'])
