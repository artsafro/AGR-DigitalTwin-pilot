"""Standing #43 driver: plant -> export -> frozen extract -> frozen score (baseline) + C1 (in-memory patched copy).
Writes result43.json. Observe-only; the frozen detector/key/controls in C:/x/t_563a40f7 are read, never written."""
import hashlib, json, subprocess, sys, types
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

R43 = Path(__file__).resolve().parent
HO = Path('C:/x/t_563a40f7')
WT = Path(sys.argv[1])  # worktree root (tools/blender/verifier_views.py)
BL = 'C:/Program Files/Blender Foundation/Blender 5.1/blender.exe'
A = Path('C:/x/review-k2/k2_v002r1_body_quad.fbx')
R = Path('C:/x/autoresearch-body-form-r41/inputs/R.fbx')
KEY, SUMS = HO / 'key/heldout-key-v001.json', HO / 'key/SHA256SUMS.txt'
ZS = '16.85,17.8,18.2,19.8'
FB, EX, SC = R43 / 'fbx', R43 / 'extract', R43 / 'score'
for d in (FB, EX, SC):
    d.mkdir(exist_ok=True)

PLANTS = [('A_rt', 'A', 0.0), ('P_fill', 'P_fill', 0.0)] + \
         [(f'P_recess_{d:.2f}', 'P_recess', d) for d in (0.03, 0.06, 0.11, 0.13, 0.20)] + \
         [(f'P_corner_{l:.2f}', 'P_corner', l) for l in (0.05, 0.10, 0.20, 0.40, 0.80)]
NEG = ['R', 'P_fill'] + [p[0] for p in PLANTS if p[1] in ('P_recess', 'P_corner')]
ACC = ['A', 'A_rt', 'C_none']
INJ = ['C_shift_opening', 'C_shift_wall']
FROZEN = ['J1_missing_4259581', 'J2_extra_endwall', 'J3_stair_cut_basket']


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def run(cmd, log):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    Path(log).write_text(r.stdout[-4000:] + '\n--- stderr\n' + r.stderr[-4000:], encoding='utf-8')
    if r.returncode:
        raise SystemExit(f'FAILED {cmd[-3:]} rc={r.returncode}, see {log}')


def plant(job):
    name, var, p = job
    out = FB / f'{name}.fbx'
    if not out.exists():
        run([BL, '-b', '--factory-startup', '--python', str(R43 / 'plant43.py'), '--', str(WT), str(A), var, str(p),
             str(out)], R43 / 'logs' / f'plant_{name}.log')
    return name, out


def extract(job):
    name, fbx = job
    out = EX / f'{name}.extract.json'
    if not out.exists():
        run([BL, '-b', '--factory-startup', '--python', str(HO / 'detector/extract.py'), '--', str(fbx), str(out), ZS],
            R43 / 'logs' / f'extract_{name}.log')
    return name, out


def scorer(cz=None):
    src = (HO / 'detector/score_heldout.py').read_text(encoding='utf-8')
    if cz:
        old = 'CONTOUR_Z = ["16.85", "19.8"]'
        assert src.count(old) == 1
        src = src.replace(old, f'CONTOUR_Z = {json.dumps(cz)}')
    m = types.ModuleType('sh')
    m.__dict__['__name__'] = 'sh'
    exec(compile(src, 'score_heldout.py', 'exec'), m.__dict__)
    return m


def score(m, name, ex, tag):
    out = SC / f'{name}.{tag}.json'
    import contextlib, io
    with contextlib.redirect_stdout(io.StringIO()):
        m.main(str(KEY), str(SUMS), str(ex), str(out))
    return json.loads(out.read_text(encoding='utf-8'))


def detected(r):
    o = r['openings']
    fp = o.get('FP_extra', 0) if isinstance(o, dict) else 0
    return r['summary_groupA']['fail'] > 0 or r['summary_groupB']['fail'] > 0 or fp > 0


def main():
    (R43 / 'logs').mkdir(exist_ok=True)
    with ThreadPoolExecutor(4) as ex:
        fbx = dict(ex.map(plant, PLANTS))
    fbx.update({'A': A, 'R': R, **{c: HO / 'controls' / f'{c}.fbx' for c in ['C_none'] + INJ}})
    jobs = list(fbx.items()) + [('A_rep2', A), ('A_rep3', A)]
    with ThreadPoolExecutor(4) as ex:
        exs = dict(ex.map(extract, jobs))
    for f in FROZEN:
        exs[f] = HO / 'controls' / f'{f}.extract.json'
    det_hashes = sorted({sha(exs[k]) for k in ('A', 'A_rep2', 'A_rep3')})
    base, c1 = scorer(), scorer(['16.85', '17.8', '18.2', '19.8'])
    res = {'inputs': {k: {'path': str(v), 'sha256': sha(v)} for k, v in fbx.items()},
           'extract_sha256': {k: sha(v) for k, v in exs.items()}, 'A_extract_distinct_hashes': len(det_hashes),
           'variants': {}}
    for name in ACC + NEG + INJ + FROZEN:
        b, c = score(base, name, exs[name], 'base'), score(c1, name, exs[name], 'c1')
        changed = [k for k in b['items'] if b['items'][k]['status'] != c['items'][k]['status']]
        new = {k: c['items'][k] for k in c['items'] if k not in b['items']}
        res['variants'][name] = {
            'class': 'accepted' if name in ACC else 'negative' if name in NEG else 'injected' if name in INJ else 'frozen_dump',
            'base': {'detected': detected(b), 'A': b['summary_groupA'], 'B': b['summary_groupB'], 'openings': b['openings'],
                     'non_pass': {k: v['status'] + ': ' + v['basis'][:120] for k, v in b['items'].items() if v['status'] != 'pass'}},
            'c1': {'detected': detected(c), 'A': c['summary_groupA'],
                   'new_items': {k: v['status'] + ': ' + v['basis'][:120] for k, v in new.items()} or 'not_exercised',
                   'preexisting_items_changed': len(changed)}}
    v = res['variants']
    res['M43'] = {t: {'detected': sum(v[n][t]['detected'] for n in NEG), 'of': len(NEG),
                      'accepted_false_fails': sum(v[n][t]['detected'] for n in ACC),
                      'missed': [n for n in NEG if not v[n][t]['detected']]} for t in ('base', 'c1')}
    (R43 / 'result43.json').write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(res['M43'], indent=1), 'A distinct extract hashes', len(det_hashes))
    for n in ACC + NEG + INJ + FROZEN:
        print(f"{n:22s} base={v[n]['base']['detected']!s:5s} c1={v[n]['c1']['detected']!s:5s} "
              f"A={v[n]['base']['A']} chg={v[n]['c1']['preexisting_items_changed']} new={v[n]['c1']['new_items']}"[:330])


if __name__ == '__main__':
    main()
