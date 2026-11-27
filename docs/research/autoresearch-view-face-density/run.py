"""Replay the frozen #146 OBSERVE contract from the repository root."""
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import runpy
from statistics import median
import subprocess
import sys
from time import monotonic
from types import SimpleNamespace

R140 = 'ab33b7e4249f41232501d0c05534bd2793a15358'
FIXTURES = {
    'elv': ('640b3678fb18ac2e5811742116a92e96ef236ab6', 'elv'),
    'kpp': (R140, '2d'),
    'obr': ('de68ef753b3753c82d16d47e2852129f8d64d572', 'raster-2d'),
}
LOCK = 'ba1bb998b19d50e1a066042e6362a9ec581949f0fe928433af2008060df4d5ea'


def blob(job, name, rev=None):
    parent, suffix = FIXTURES[job]
    path = f'docs/research/autoresearch-view-face-{suffix}/{name}'
    return subprocess.check_output(['git', 'show', f'{rev or parent}:{path}'])


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def dump(path, data):
    path.write_bytes((json.dumps(data, ensure_ascii=False, indent=1) + '\n').encode('utf-8'))


def replace_once(text, before, after):
    if text.count(before) != 1:
        raise ValueError(f'Pinned scorer seam mismatch: {before}')
    return text.replace(before, after)


def excess(p, q):
    return max(0.0, (p - q) / (1 - q)) if q < 1 else 0.0


class Ranker:
    """Track A and B at the same offsets, retaining the original A expression."""

    def __init__(self, api):
        self.pending, self.answers = [], []
        self.baseline = api['decide']
        baseline_source = blob('kpp', 'score.py').decode('utf-8')
        source = replace_once(baseline_source, '    rows = np.flatnonzero',
                              '    adjusted = -1.0\n    rows = np.flatnonzero')
        source = replace_once(source, '        return -1.0', '        return -1.0, -1.0')
        source = replace_once(source, '    count_view = np.count_nonzero(view)',
                              '    count_view = np.count_nonzero(view)\n'
                              '    q_view = np.count_nonzero(hits_view) / view.size')
        source = replace_once(source, '            precision = np.count_nonzero(view & nearby(crop)) / count_view',
                              '            hit_crop = nearby(crop)\n'
                              '            precision = np.count_nonzero(view & hit_crop) / count_view')
        source = replace_once(source, '    return best\n',
                              '            p = excess(precision, np.count_nonzero(hit_crop) / view.size)\n'
                              '            r = excess(recall, q_view)\n'
                              '            adjusted = max(adjusted, 2 * p * r / (p + r) if p + r else 0.0)\n'
                              '    return best, adjusted')
        scope = {'excess': excess}
        exec(compile(source, f'{R140}:score.py+chance', 'exec'), scope)
        self.paired = scope['face_score']

    def score(self, *args, **kwargs):
        baseline, adjusted = self.paired(*args, **kwargs)
        self.pending.append(adjusted)
        return baseline

    def decide(self, scores):
        trial = dict(zip(scores, self.pending, strict=True))
        self.pending.clear()
        winner = self.baseline(trial)
        self.answers.append({'pick': winner, 'scores': {k: round(v, 6) for k, v in trial.items()}})
        return self.baseline(scores)


def measure(out, job):
    out.mkdir(parents=True, exist_ok=False)
    upstream = out / 'upstream'
    upstream.mkdir()
    deps = {'run.py', 'receipt.json'} | ({'fixture.json'} if job == 'elv' else {'score.py'} if job == 'kpp' else set())
    for name in sorted(deps):
        (upstream / name).write_bytes(blob(job, name))
    oracle = json.loads((upstream / 'receipt.json').read_bytes())
    if job == 'kpp':
        sys.path.insert(0, str(upstream))
    api = runpy.run_path(str(upstream / 'run.py'))
    state = api['main'].__globals__
    data = out / 'native'
    if job == 'elv':
        fx = json.loads((upstream / 'fixture.json').read_bytes())
        pins = api['stage'](data, fx)
        if pins != oracle['pins']:
            raise ValueError('ELV staged manifest mismatch')
        scorer = runpy.run_path(str(data / 'score.py'))
        rank = Ranker(scorer)
        state['runpy'] = SimpleNamespace(run_path=lambda _: scorer | {'face_score': rank.score, 'decide': rank.decide})
        rows = api['measure'](data, 1, fx)
        truth_key, case_key, pick_key, delta_key = 'gt_az', 'case', 'pick', 'changed_pixels'
        expected = oracle['rows']
        for role, item in fx['inputs'].items():
            api['sha'](item['path']) == item['sha256'] or fail(f'ELV {role} changed')
            api['sha'](data / f'elv.{role}') == item['sha256'] or fail(f'ELV staged {role} changed')
        api['sha'](api['BLENDER']) == oracle['blender_sha256'] or fail('Blender changed')
    elif job == 'kpp':
        rank = Ranker(api)
        manifest = oracle['inputs']
        for item in manifest.values():
            api['check'](Path(item['source']), item['source_sha256'])
        if api['prepare'](data) != manifest:
            raise ValueError('KPP1/AC08 staged manifest mismatch')
        state.update(face_score=rank.score, decide=rank.decide)
        api['measure'](data, 1)
        rows = json.loads((data / 'pair-1.json').read_bytes())
        api['parity'](data, rows)
        truth_key, case_key, pick_key, delta_key = 'gt_az', 'case', 'B', 'changed_pixels'
        expected, pins = oracle['views'], manifest
        for name, item in manifest.items():
            api['check'](Path(item['source']), item['source_sha256'])
            api['check'](data / name, item['sha256'])
        api['check'](api['BLENDER'], oracle['blender_sha256'])
    else:
        scorer = api['upstream_edges']()
        rank = Ranker(vars(scorer))
        scorer.face_score, scorer.decide = rank.score, rank.decide
        state['upstream_edges'] = lambda: scorer
        api['main'](data)
        result = json.loads((data / 'pair.json').read_bytes())
        rows, pins = result['cases'], result['hashes']
        if pins != oracle['paired_result']['hashes']:
            raise ValueError('OBR22 staged manifest mismatch')
        truth_key, case_key, pick_key, delta_key = 'gt', 'kind', 'B', 'changed_edge_px'
        expected = oracle['paired_result']['cases']
    if rows != expected:
        raise ValueError(f'{job}: full historical baseline row parity failed')
    answers = iter(rank.answers)
    for row in rows:
        a = row[pick_key]
        if isinstance(a, dict):
            a = a.get('answer')
        case = row[case_key]
        if job == 'obr' and case == 'mirror' and not row[delta_key]:
            row['adjusted'] = {'pick': None, 'scores': {}}
        else:
            row['adjusted'] = next(answers)
        scope = 'crop' if case.startswith('partial') else case
        fixture = row.get('fixture', job)
        row['group'] = f'{fixture}/{scope}'
        truth = row[truth_key]
        for arm, pick in (('A', a), ('B', row['adjusted']['pick'])):
            row[f'verdict_{arm}'] = ('not_exercised' if scope == 'mirror' and not row[delta_key] else
                                     'abstain' if pick is None else 'correct' if pick == truth else 'wrong')
    if rank.pending or next(answers, None) is not None:
        raise ValueError('Unconsumed candidate scores')
    dump(out / 'paired.json', {'pins': pins, 'rows': rows})


def fail(message):
    raise ValueError(message)


def summarize(rows):
    summary = {}
    for name in sorted({r['group'] for r in rows}):
        for arm in ('A', 'B'):
            counts = Counter(r[f'verdict_{arm}'] for r in rows if r['group'] == name)
            right, wrong, abstain = (counts[k] for k in ('correct', 'wrong', 'abstain'))
            answered, total = right + wrong, right + wrong + abstain
            summary[f'{name}/{arm}'] = dict(correct=right, wrong=wrong, abstain=abstain,
                not_exercised=counts['not_exercised'], accuracy=right / answered if answered else None,
                abstain_rate=abstain / total if total else None)
    return summary


def gate(rows, tally):
    return (all(r['verdict_B'] != 'wrong' for r in rows)
            and tally['elv/crop/B']['correct'] >= 15
            and tally['elv/full/B']['correct'] >= 5
            and any(r.get('view') == 'p23 frag D-G' and r['verdict_B'] == 'correct' for r in rows)
            and tally['kpp1/full/B']['correct'] >= 3
            and tally['kpp1/crop/B']['correct'] >= 22
            and tally['ac08/full/B']['abstain'] == 4 and tally['ac08/crop/B']['abstain'] == 36
            and all(r['verdict_B'] == 'correct' for r in rows
                    if r['group'] in ('obr/full', 'obr/crop') and r['verdict_A'] == 'correct'))


def series(out):
    start = monotonic()
    if digest('uv.lock') != LOCK:
        raise ValueError('uv.lock mismatch')
    out.mkdir(parents=True, exist_ok=False)
    hashes, times, timing_rows = [], [], []
    status = 'finished'
    script = Path(__file__).resolve()
    for i in (1, 2, 3):
        pair_start = monotonic()
        dirs = {job: out / f'{i}-{job}' for job in FIXTURES}
        timing = {}
        for job, target in dirs.items():
            tick = monotonic()
            with target.with_suffix('.log').open('xb') as log:
                subprocess.run([sys.executable, str(script), str(target), job],
                               check=True, timeout=max(1, 840 - (monotonic() - start)),
                               stdout=log, stderr=subprocess.STDOUT)
            timing[job] = round(monotonic() - tick, 3)
            print(f'{i}/{job}: {timing[job]} s', flush=True)
        paths = {j: p / 'paired.json' for j, p in dirs.items()}
        hashes.append({j: digest(p) for j, p in paths.items()})
        rows = [row for p in paths.values() for row in json.loads(p.read_bytes())['rows']]
        times.append(round(monotonic() - pair_start, 3))
        timing_rows.append(timing)
        if monotonic() - start + 1.15 * times[0] * (3 - i) > 840:
            status = 'budget_stop'
            break
    if status == 'finished' and any(h != hashes[0] for h in hashes[1:]):
        status = 'nonidentical_repeats'
    tally = summarize(rows)
    dump(out / 'receipt.json', dict(status=status, hypothesis=('confirmed' if gate(rows, tally) else 'refuted')
         if status == 'finished' else 'inconclusive', revisions=FIXTURES, lock=LOCK, runner=digest(script),
         measured_head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
         pair_hashes=hashes, pair_s=times, fixture_s=timing_rows, median_s=median(times),
         min_s=min(times), max_s=max(times), wall_s=round(monotonic() - start, 3), summary=tally, rows=rows))


if __name__ == '__main__':
    target = Path(sys.argv[1]).resolve()
    if len(sys.argv) == 3:
        measure(target, sys.argv[2])
    else:
        series(target)
