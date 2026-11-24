"""Reuse the pinned #62 fresh replay and #58 reducer; do not write delivery files."""
import hashlib
import math
from pathlib import Path
import statistics
import subprocess
import sys

R62 = '75257229cb561c64bace8250f632c13bc4d694af'
R62_DIR = 'docs/research/atlas-native-phase-r62'
LOCK_BLOB = '365142f28f01a2f12bd4d83e5bfa8f3853a83c06'
LABELS = ('v007', 'v010')
STATES = ('clean', 'small', 'trigger')


def graft(source, anchor, replacement):
    if source.count(anchor) != 1:
        raise ValueError(f'pinned #62 driver anchor drift: {anchor!r}')
    return source.replace(anchor, replacement)


def grade(rounds):
    fail = {'hypothesis': 'inconclusive', 'clean_label_order': 'not_measured'}
    if len(rounds) != 3:
        return fail
    pairs = []
    for row in rounds:
        if [row[v][s]['JE'] for v, s in (('v007', 'clean'), ('v010', 'clean'),
                                         ('v010', 'small'), ('v010', 'trigger'))] != [202, 0, 0, 320]:
            return fail | {'reason': 'prior JE witness mismatch'}
        pair, baselines = {}, {}
        for label in LABELS:
            clean, small, trigger = (row[label][s]['paired_rgb'] for s in STATES)
            counts = [{v: r['pixels'] for v, r in x['views'].items()} for x in (clean, small, trigger)]
            if not counts[0] or not counts[0] == counts[1] == counts[2]:
                return fail | {'reason': 'mask coverage changed or empty'}
            baseline = clean['mean']
            if not all(math.isfinite(x['mean']) for x in (clean, small, trigger)):
                return fail | {'reason': 'nonfinite score'}
            baselines[label] = baseline
            pair[label] = {'small': small['mean'] - baseline, 'trigger': trigger['mean'] - baseline}
        pair['clean_label_delta'] = baselines['v007'] - baselines['v010']
        pair['minimum_trigger_delta'] = min(pair[v]['trigger'] for v in LABELS)
        pairs.append(pair)
    ds = [p['minimum_trigger_delta'] for p in pairs]
    cs = [p['clean_label_delta'] for p in pairs]
    spread = max(ds) - min(ds)
    passed = all(p[v]['trigger'] >= 0.002 and p[v]['trigger'] > p[v]['small'] and abs(p[v]['small']) <= 0.002
                 for p in pairs for v in LABELS)
    return dict(hypothesis='inconclusive' if spread > 0.0005 else ('confirmed' if passed else 'refuted'),
                median_delta=statistics.median(ds), paired_spread=spread, pairs=pairs,
                clean_label_order=('inconclusive' if max(cs) - min(cs) > 0.0005 else
                                   ('separates_fixture' if min(cs) > 0 and statistics.median(cs) >= 0.002 else 'refuted')))


def run(out):
    # Check the locked scorer environment before any native work.
    if subprocess.check_output(['git', 'hash-object', 'uv.lock']).decode().strip() != LOCK_BLOB:
        raise ValueError('uv.lock drift: use the measured branch checkout')
    if out.exists():
        raise FileExistsError(out)
    driver = out.with_name(out.name + '-driver')
    driver.mkdir(parents=True)
    upstream = {name: subprocess.check_output(['git', 'show', f'{R62}:{R62_DIR}/{name}'])
                for name in ('replay.py', 'phase.py')}
    # #62's camera values are lists; #58's are tuples. Each checks exact equality
    # independently, using the same metadata. Do not mix their reference maps.
    source = graft(upstream['replay.py'], b"        cameras, repeats = {}, {}\n",
                   b"        cameras, repeats, rgb_cameras = {}, {}, {}\n")
    source = graft(source, b"                    case['status'] = 'scored'\n",
                   b"                    rnd[v][name]['paired_rgb'] = r58.score(renders, rgb_cameras)\n"
                   b"                    case['status'] = 'scored'\n")
    source = graft(source, b"        report['cameras'] = cameras\n",
                   b"        report['je_hypothesis_r62'] = report['hypothesis']\n"
                   b"        report['hypothesis'] = 'inconclusive'\n"
                   b"        report['r64'] = grade(report['rounds'])\n"
                   b"        report['cameras'] = cameras\n")
    source = graft(source, b"*layouts.values(), Path(__file__)]",
                   b"*layouts.values(), Path(__file__), wrapper, Path('uv.lock').resolve()]")
    source = graft(source, b"        (out / 'receipt.json').write_text",
                   b"        if report['status'] == 'completed':\n"
                   b"            report['hypothesis'] = report['r64']['hypothesis']\n"
                   b"        (out / 'receipt.json').write_text")
    driver_path = driver / 'replay.py'
    driver_path.write_bytes(source)
    (driver / 'phase.py').write_bytes(upstream['phase.py'])
    wrapper = Path(__file__).resolve()
    namespace: dict = dict(__file__=str(driver_path), __name__='staged_r62', grade=grade, wrapper=wrapper)
    print('wrapper SHA-256:', hashlib.sha256(wrapper.read_bytes()).hexdigest(), flush=True)
    exec(compile(source, str(driver_path), 'exec'), namespace)
    return namespace['run'](out)


if __name__ == '__main__':
    sys.exit(run(Path(sys.argv[1]).resolve()))
