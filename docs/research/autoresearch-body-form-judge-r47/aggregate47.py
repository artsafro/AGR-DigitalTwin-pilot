"""Standing #47 aggregation: rubric flips vs A and pairwise false preferences (FD47). Usage: python aggregate47.py"""
import json
from collections import Counter
from pathlib import Path

D = Path(__file__).resolve().parent
NV = ['N_tri', 'N_sub', 'N_jit_0.005', 'N_jit_0.020']
SCORED = ['Q1', 'Q2', 'Q3', 'Q5']
calls = [json.loads(p.read_text(encoding='utf-8')) for p in sorted((D / 'calls').glob('*.json'))]
failed = [c['id'] for c in calls if c['rc'] != 0 or not c['parsed']]


def maj(vals):
    v, k = Counter(vals).most_common(1)[0]
    return v if k >= 2 else 'Unsure'


res = {'calls': len(calls), 'failed': failed, 'judges': {}}
fd = 0
for j in ('claude', 'codex'):
    R = {}
    for v in ['A'] + NV:
        cs = [c['parsed'] or {} for c in calls if c['judge'] == j and c['kind'] == 'rubric' and c['imgs'] == [v]]
        R[v] = {q: maj([c.get(q, 'Unsure') for c in cs]) for q in SCORED + ['Q4']}
        R[v]['n'] = len(cs)
        R[v]['raw'] = {q: [c.get(q) for c in cs] for q in SCORED + ['Q4']}
    flips = {}
    for v in NV:
        f = [q for q in SCORED if R[v][q] != R['A'][q] and 'Unsure' not in (R[v][q], R['A'][q])]
        nm = [q for q in SCORED if 'Unsure' in (R[v][q], R['A'][q])]
        flips[v] = {'flips': f, 'not_measured': nm, 'q4_noise': [R['A']['Q4'], R[v]['Q4']]}
        fd += len(f)
    P = {}
    for v in NV + ['A']:
        ab = [c for c in calls if c['judge'] == j and c['kind'] == 'pair' and c['imgs'] == ['A', v] and c['order'] == 'AB']
        ba = [c for c in calls if c['judge'] == j and c['kind'] == 'pair' and c['imgs'] == [v, 'A'] and c['order'] == 'BA']
        a1 = (ab[0]['parsed'] or {}).get('better', 'missing')
        a2 = (ba[0]['parsed'] or {}).get('better', 'missing')
        # side picked in each order: AB: X=A(first copy), BA: X=v
        s1 = {'X': 'A', 'Y': v + '*' if v == 'A' else v}.get(a1, 'Unsure')
        s2 = {'X': v + '*' if v == 'A' else v, 'Y': 'A'}.get(a2, 'Unsure')
        consistent = s1 == s2 and s1 != 'Unsure'
        P[v if v != 'A' else 'AA'] = {'AB': a1, 'BA': a2, 'picked': s1 if consistent else None}
        if v != 'A' and consistent:
            fd += 1
    res['judges'][j] = {'rubric_majority': {v: {q: R[v][q] for q in SCORED + ['Q4', 'n']} for v in R},
                        'rubric_raw': {v: R[v]['raw'] for v in R}, 'flips': flips, 'pairs': P}
res['FD47'] = fd
fd_core = sum(len(res['judges'][j]['flips'][v]['flips']) + (res['judges'][j]['pairs'][v]['picked'] is not None)
              for j in res['judges'] for v in NV[:3])
res['FD47_core_tri_sub_jit005'] = fd_core
res['FD47_stress_jit020'] = fd - fd_core
(D / 'result47.json').write_text(json.dumps(res, indent=1), encoding='utf-8')
print(json.dumps({k: res[k] for k in ('calls', 'failed', 'FD47', 'FD47_core_tri_sub_jit005', 'FD47_stress_jit020')}))
for j in res['judges']:
    print(j, 'A', res['judges'][j]['rubric_majority']['A'])
    for v in NV:
        print(' ', v, res['judges'][j]['flips'][v], 'pair', res['judges'][j]['pairs'][v])
    print('  AA', res['judges'][j]['pairs']['AA'])
