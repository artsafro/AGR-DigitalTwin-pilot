"""Standing #49 aggregate (evidence-only): equivalence cells, E49, H49, comparison with the 'better' question."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
X = Path('C:/x')
CORE_SAME = ['A', 'N_tri', 'N_sub', 'N_jit_0.005']          # 'A' = AA control
STRESS_SAME = ['N_jit_0.020']
CORE_DIFF = ['R', 'W_recess', 'W_corner', 'P_recess_0.20', 'P_recess_0.11', 'P_recess_0.06',
             'P_corner_0.40', 'P_corner_0.20', 'P_corner_0.10']
BOUNDARY = ['P_recess_0.03', 'P_corner_0.05']
TRUTH = {**{v: 'Same' for v in CORE_SAME + STRESS_SAME + BOUNDARY}, **{v: 'Different' for v in CORE_DIFF}}


def label(rec):
    p = rec.get('parsed') or {}
    v = str(p.get('form', '')).strip().capitalize()
    return v if v in ('Same', 'Different', 'Unsure') else None


def kappa(a, b):
    labs = sorted(set(a) | set(b))
    n = len(a)
    if n == 0:
        return None
    po = sum(x == y for x, y in zip(a, b)) / n
    pe = sum((a.count(lb) / n) * (b.count(lb) / n) for lb in labs)
    return None if pe == 1 else round((po - pe) / (1 - pe), 3)


def better_baseline():
    """'better' question (#41/#45/#47): order-consistent pick of A -> Different, else no decision."""
    out = {'claude': {}, 'codex': {}}
    r41 = json.loads((X / 'autoresearch-body-form-r41/result41.json').read_text(encoding='utf-8'))
    r45 = json.loads((X / 'autoresearch-body-form-r45/result45.json').read_text(encoding='utf-8'))
    r47 = json.loads((X / 'autoresearch-body-form-r47/result47.json').read_text(encoding='utf-8'))
    for j in out:
        oc41 = r41['judges'][j].get('pairs_order_consistent', {})
        if 'R' in oc41 or 'R' in r41['judges'][j].get('pairs_raw', {}):
            out[j]['R'] = 'Different' if oc41.get('R') == 'A' else 'no decision'
        oc45 = r45['judges'][j]['pairs_order_consistent']
        for v in r45['judges'][j]['pairs_raw']:
            out[j][v] = 'Different' if oc45.get(v) == 'A' else 'no decision'
        out[j]['_r47_raw'] = r47['judges'][j].get('pairs') or r47['judges'][j].get('pair_raw') or \
            {k: v for k, v in r47['judges'][j].items() if 'pair' in k}
    return out


def main():
    jobs = json.loads((ROOT / 'jobs-pair.json').read_text(encoding='utf-8'))
    recs = [json.loads((ROOT / 'calls' / f"{j['id']}.json").read_text(encoding='utf-8')) for j in jobs]
    res = {'n_calls': len(recs), 'failed': sum(1 for r in recs if label(r) is None),
           'wall_s_sum': round(sum(r['wall_s'] for r in recs), 1), 'wall_s_max': max(r['wall_s'] for r in recs),
           'judges': {}}
    cells = {}
    for judge in ('claude', 'codex'):
        raw, cell = {}, {}
        for r in recs:
            if r['judge'] != judge:
                continue
            v = r['imgs'][1] if r['order'] == 'AB' else r['imgs'][0]
            raw.setdefault(v, {})[r['order']] = label(r)
        for v, o in raw.items():
            ab, ba = o.get('AB'), o.get('BA')
            if ab is None or ba is None:
                cell[v] = 'not_measured'
            elif ab == ba and ab in ('Same', 'Different'):
                cell[v] = ab
            else:
                cell[v] = 'no decision'
        scored = CORE_SAME + STRESS_SAME + CORE_DIFF
        errors = [v for v in scored if cell.get(v) in ('Same', 'Different') and cell[v] != TRUTH[v]]
        decided = [v for v in scored if cell.get(v) in ('Same', 'Different')]
        det = [v for v in CORE_DIFF if cell.get(v) == 'Different']
        res['judges'][judge] = {
            'raw': raw, 'cell': cell, 'errors': errors, 'E': len(errors),
            'decided': f'{len(decided)}/{len(scored)}', 'detection': f'{len(det)}/{len(CORE_DIFF)}',
            'same_correct': [v for v in CORE_SAME + STRESS_SAME if cell.get(v) == 'Same'],
            'boundary': {v: cell.get(v) for v in BOUNDARY}}
        cells[judge] = cell
    E = sum(j['E'] for j in res['judges'].values())
    common = [v for v in TRUTH if cells['claude'].get(v) in ('Same', 'Different')
              and cells['codex'].get(v) in ('Same', 'Different')]
    a = [cells['claude'][v] for v in common]
    b = [cells['codex'][v] for v in common]
    res['judge_agreement'] = {'common_decided': len(common), 'raw': f'{sum(x == y for x, y in zip(a, b))}/{len(common)}',
                              'kappa': kappa(a, b)}
    res['E49'] = E
    refute = any(cells[j].get(v) == 'Different' for j in cells for v in CORE_SAME) or \
        any(cells[j].get('R') == 'Same' for j in cells)
    confirm = E == 0 and all(cells[j].get('R') == 'Different' and cells[j].get('A') == 'Same' and
                             int(res['judges'][j]['detection'].split('/')[0]) >= 6 for j in cells)
    if res['failed'] > 0.2 * len(recs):
        h = 'inconclusive (failed calls > 20%)'
    else:
        h = 'refuted' if refute else ('confirmed' if confirm else 'inconclusive')
    res['H49'] = h
    res['better_baseline'] = better_baseline()
    (ROOT / 'result49.json').write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding='utf-8')
    for j, d in res['judges'].items():
        print(j, 'E', d['E'], d['errors'], 'decided', d['decided'], 'det', d['detection'], 'boundary', d['boundary'])
        print('  cells', d['cell'])
    print('E49', E, 'H49', h, 'agreement', res['judge_agreement'], 'failed', res['failed'], 'wall_sum', res['wall_s_sum'])


if __name__ == '__main__':
    main()
