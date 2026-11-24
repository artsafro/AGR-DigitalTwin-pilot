"""OBSERVE only. See ../autoresearch-body-form-r54.md for the frozen contract."""
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import statistics as stats
import subprocess as sp
import sys
import time

REV = 'ad00bbb325f2a8f99f4e71c8697f365ce4410a0b'
PRIOR = 'docs/research/autoresearch-body-form-r53'
P = Path('C:/x/t_563a40f7')
K63 = Path('C:/x/t_fb3a0b98-r51/key')
H40 = Path('C:/x/autoresearch-body-form-r40/evidence')
H53 = Path('C:/x/t_1276e6bc-r53/run01')
CAP = min(180, int(os.environ.get('R54_CAP_S', '180')))


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def dump(path, val):
    path.write_text(json.dumps(val, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def sha(path):
    return hashlib.file_digest(path.open('rb'), 'sha256').hexdigest()


def run(cmd, **kwargs):
    return sp.run(cmd, check=True, capture_output=True, **kwargs).stdout


def check_manifest(root):
    for line in (root/'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines():
        digest, name = line.split(maxsplit=1)
        assert sha(root/name.removeprefix('*')) == digest, f'manifest mismatch: {name}'


def normalized(report):
    report = copy.deepcopy(report)
    report['provenance'].pop('candidate_fbx')
    return report


def supports(S, sections, box, ring, opening):
    a, u, _ = S.frame(ring, *opening['contour_segment'])
    lo, hi = opening['edge_s_m']
    mid = (lo + hi) / 2
    edge, band = S.TOL['opening_edge_m'], S.TOL['wall_line_search_m']
    sets = {}
    for z in S.OPENING_Z:
        ix = [i for i, (p, q) in enumerate(sections[z]) if S.inbox(p, box, .5) or S.inbox(q, box, .5)]
        gaps = S.gaps(S.wall_intervals([sections[z][i] for i in ix], a, u), lo - .6, hi + .6)
        g = next((g for g in gaps if g[0] < mid < g[1]), None)
        sides = ([], [])
        for i in ix if g else []:
            p, q = sections[z][i]
            (t0, d0), (t1, d1) = sorted((S.local(p, a, u), S.local(q, a, u)))
            length = math.dist(p, q)
            if length < 1e-6 or (t1-t0)/length < S.TOL['parallel_cos'] or max(abs(d0), abs(d1)) >= band:
                continue
            if t0 < g[0]-edge and abs(t1-g[0]) <= edge:
                sides[0].append((i, d0, d1))
            if t1 > g[1]+edge and abs(t0-g[1]) <= edge:
                sides[1].append((i, d0, d1))
        sets[z] = sides
    return a, u, sets


def describe(S, key, ex, overlay, reference):
    ring = {v['ring_index']: v['xy'] for v in key['contour_vertices_in_box']}
    result = {}
    for o in key['openings']:
        pid = 'opening:' + o['id']
        a, u, sides = supports(S, ex['sections'], key['box_xy_m'], ring, o)
        ds = [d for pair in sides.values() for side in pair for _, d0, d1 in side for d in (d0, d1)]
        rim = overlay['openings'][pid]['rim']
        old = overlay['openings'][pid]['depth_rim']
        tol = S.TOL['reveal_depth_m']
        spread = max(ds) - min(ds) if ds else None
        d = stats.median(ds) if all(side for pair in sides.values() for side in pair) else None
        status = ('no_rim' if rim is None else 'flank_missing' if d is None else
                  'noncoplanar' if spread > tol else 'measured')
        depth = abs(S.local(rim['c'], a, u)[1] - d) if status == 'measured' else None
        result[pid] = dict(depth=depth, old=old, status=status, line=d, flank_spread=spread,
                           counts={z: list(map(len, pair)) for z, pair in sides.items()},
                           key_fail=None if depth is None else abs(depth - o['reveal_depth_m']) > tol,
                           wall_fail=None if depth is None or not reference else abs(depth-reference[o['id']]) > tol)
    return result


def perturb(S, key, ex, overlay, target, mode, clean):
    trial = copy.deepcopy(ex)
    ov = copy.deepcopy(overlay)
    o, = [o for o in key['openings'] if o['id'].endswith(target)]
    pid = 'opening:' + o['id']
    ring = {v['ring_index']: v['xy'] for v in key['contour_vertices_in_box']}
    a, u, sides = supports(S, ex['sections'], key['box_xy_m'], ring, o)
    rim = ov['openings'][pid]['rim']
    if clean[pid]['depth'] is None:
        return {'status': 'not_exercised', 'target': pid}
    delta = -math.copysign(.10, S.local(rim['c'], a, u)[1] - clean[pid]['line'])

    def move(point):
        return [point[0] + delta*u[1], point[1] - delta*u[0]]

    changed = {}
    for z, pair in sides.items():
        ids = {i for side in pair for i, _, _ in side} if mode != 'lower' or z == S.OPENING_Z[0] else set()
        changed[z] = len(ids)
        for i in ids:
            trial['sections'][z][i] = [move(p) for p in trial['sections'][z][i]]
    if mode == 'rigid':
        rim['c'] = move(rim['c'])
    out = describe(S, key, trial, ov, None)
    v = out[pid]
    diff = None if v['depth'] is None else v['depth'] - clean[pid]['depth']
    off = [p for p in out if p != pid and (out[p]['status'] != clean[p]['status'] or
           (out[p]['depth'] is not None and abs(out[p]['depth'] - clean[p]['depth']) > .001))]
    return dict(target=pid, status=v['status'], depth=v['depth'], original_depth=clean[pid]['depth'],
                delta=diff, error=None if diff is None else abs(diff-.10), old_delta=(
                    abs(S.local(rim['c'], a, u)[1])-abs(S.local(overlay['openings'][pid]['rim']['c'], a, u)[1])),
                changed_segments=changed, off_target=off, flank_counts=v['counts'], line=v['line'])


def main(out):
    out.mkdir(parents=True)
    start = time.monotonic()
    result = {'status': 'preflight', 'hypothesis': 'inconclusive', 'runs': {}, 'base_prior': REV, 'cap_s': CAP}
    try:
        # Reuse the original fixture list, not a copied fork of the previous experiment.
        for name in ('run53.py', 'score53.py'):
            (out / name).write_bytes(run(['git', 'show', f'{REV}:{PRIOR}/{name}']))
        sys.path.insert(0, str(out))
        sys.dont_write_bytecode = True
        pins = read(Path(__file__).with_name('pins.json'))
        assert all(sha(Path(p)) == h for p, h in pins.items()), 'absolute-path pin mismatch'
        for root in (P, P/'key', K63):
            check_manifest(root)
        import run53 as prior
        S = prior.score53.S
        fbxset = {k: (Path(p), h) for k, (_, p, h) in (prior.F63 | prior.FG22).items() if k != 'G22_C_shift_opening'}
        fbxset |= {k: (H40/f'{k}.fbx', h) for k, h in {
            'A': '5b1e8d76c81de07dd62a94a1419a1f0bb6f5c82bd069592c2453f21b94f0f200',
            'R': '8e97a80af2de0a22fae5d689a193762fe5ff2d90eb4b83106e35d5c78a5eb519'}.items()}
        pins |= {p: h for h, p in prior.PINS.values()}
        pins |= {str(p): h for p, h in fbxset.values()}
        assert all(sha(Path(p)) == h for p, h in pins.items()), 'fixture pin mismatch'
        result['input_pins'] = pins
        result['scripts'] = {p.name: sha(p) for p in (Path(__file__), out/'run53.py', out/'score53.py')}
        keys = {r: read(r/'heldout-key-v001.json') for r in (K63, P/'key')}
        rf = prior.rface(keys[K63])
        assert set(rf.values()) == {.50}
        dump(out/'rface.json', rf)
        env = dict(os.environ, TMP=str(out), TEMP=str(out), TMPDIR=str(out))
        orig = {}
        for k, (source, h) in fbxset.items():
            dst = out / f'{k}.fbx'
            shutil.copyfile(source, dst)
            assert sha(dst) == h
            orig[k] = H40/f'{k}-1.score.json' if k in ('A', 'R') else H53/k/'rep1'/'vs_key.json'
        pairs = [(k, rep) for rep in range(1, 4) for k in fbxset]
        measured = time.monotonic()
        result['status'] = 'running'
        for j, (k, rep) in enumerate(pairs, 1):
            remain = CAP - (time.monotonic()-start)
            if remain <= 0 or j == 3 and (time.monotonic()-measured) * ((len(pairs)-2)/2) * 1.25 > remain:
                result['status'] = 'budget_stop'
                break
            d = out / k / str(rep)
            d.mkdir(parents=True)
            is63 = k in prior.F63
            root = K63 if is63 else P/'key'
            key = keys[root]
            z = {s: str(round(float(s)-key['z_shift_m'],2)) if is63 else s for s in prior.ZL}
            raw = d/'raw.json'
            log = run([prior.BLENDER, '-b', '--factory-startup', '--disable-autoexec', '--threads', '1',
                       '--python-exit-code', '1', '--python', prior.DET+'/extract.py', '--',
                       (out/f'{k}.fbx').as_posix(), str(raw), ','.join(z.values())], env=env, timeout=remain)
            (d/'extract.log').write_bytes(log)
            assert b'EXTRACT' in log
            ex = read(raw)
            if is63:
                ex['sections'] = {s: ex['sections'][t] for s,t in z.items()}
                ex['loops'] = [dict(lp, z=[round(x+key['z_shift_m'], 4) for x in lp['z']]) for lp in ex['loops']]
            cp, fp = d/'extract.json', d/'score.json'
            dump(cp, ex)
            run([sys.executable, prior.DET+'/score_heldout.py', root/'heldout-key-v001.json', root/'SHA256SUMS.txt', cp, fp], timeout=max(1, CAP-(time.monotonic()-start)))
            report = read(fp)
            ov = prior.score53.overlay(root/'heldout-key-v001.json', cp, fp, d/'overlay.json', out/'rface.json' if is63 else None)
            rel = describe(S, key, ex, ov, rf if is63 else None)
            summary = dict(parity=normalized(report) == normalized(read(orig[k])),
                           openings=report['openings'], groupA=report['summary_groupA'], relative=rel)
            if k in ('G22_C_none', 'v007'):
                target = '194b464' if is63 else '4259581'
                summary['injected'] = {mode: perturb(S, key, ex, ov, target, mode, rel)
                                       for mode in ('face', 'rigid', 'lower')}
            result['runs'].setdefault(k, []).append(summary)
            if j == 2:
                result['timed_pair_s'] = round(time.monotonic()-measured, 3)
        result['postflight'] = all(sha(Path(p)) == h for p, h in pins.items()) and all(
            sha(out/f'{k}.fbx') == h for k, (_, h) in fbxset.items())
        for root in (P, P/'key', K63):
            check_manifest(root)
        if result['status'] == 'running':
            result['status'] = 'complete'
            aggregate(result, S.TOL['reveal_depth_m'], prior.F63)
    except (AssertionError, KeyError, ValueError, OSError, sp.SubprocessError) as exc:
        result['status'] = 'budget_stop' if isinstance(exc, sp.TimeoutExpired) else 'error'
        result['error'] = str(exc)
        if isinstance(exc, sp.CalledProcessError):
            result['stderr'] = exc.stderr.decode('utf8', errors='replace')
            result['stdout'] = exc.stdout.decode('utf8', errors='replace')
        raise
    finally:
        result['wall_s'] = round(time.monotonic() - start, 3)
        dump(out/'receipt.json', result)
        print({k: v for k, v in result.items() if k not in ('runs', 'input_pins')})


def aggregate(res, tol, f63):
    runs = res['runs']
    calibration = {}
    exercised, errors, guard = [], [], []
    native_counts = []
    for rep in range(3):
        per = []
        for k, rr in runs.items():
            row = rr[rep]
            rel = row['relative']
            comparable = [v for v in rel.values() if v['old'] is not None]
            preserved = all(v['depth'] is not None and abs(v['depth']-v['old']) <= tol for v in comparable)
            cnt = {name: sum(v[name] is True for v in rel.values()) for name in ('wall_fail','key_fail')}
            nm = sum(v['depth'] is None for v in rel.values())
            calibration.setdefault(k, []).append(dict(**cnt, nm=nm, old_measured=len(comparable),
                                                        preserved=preserved, parity=row['parity']))
            ok = row['parity'] and (preserved or k == 'G22_C_shift_wall')
            if k in f63:
                ok &= nm == 0 and cnt['wall_fail'] == (0 if k == 'v007' else 5)
            if k in ('A', 'G22_C_none'):
                ok &= nm == 0 and cnt['key_fail'] == 0
            if k == 'A':
                ok &= row['openings']['TP'] == 6
            if k == 'R':
                ok &= row['openings']['FN'] == 6 and nm == 6
            guard.append(ok)
            if 'injected' not in row:
                continue
            x = row['injected']
            measured = all(v['status'] != 'not_exercised' and any(v['changed_segments'].values()) for v in x.values())
            exercised.append(measured)
            if measured:
                f, r, l = (x[n] for n in ('face', 'rigid', 'lower'))
                per.append(f['error'])
                guard.append(all(not v['off_target'] for v in x.values()) and f['error'] is not None and
                             abs(f['old_delta']) <= .001 and r['delta'] is not None and abs(r['delta']) <= .001 and
                             l['status'] == 'noncoplanar' and l['depth'] is None)
        c, w = (runs[k][rep]['relative'] for k in ('G22_C_none','G22_C_shift_wall'))
        native_counts.append(dict(unmeasured=sum(v['depth'] is None for v in w.values()),
                                  changed=sum(c[p]['depth'] is not None and w[p]['depth'] is not None and
                                              abs(c[p]['depth']-w[p]['depth']) > .001 for p in c)))
        a, r = (runs[k][rep]['groupA'] for k in ('A','R'))
        guard.append(a['pass'] > r['pass'])
        errors.append(per)
    primary = spread = None
    if all(exercised) and all(len(row) == 2 and all(x is not None for x in row) for row in errors):
        primary = max(map(stats.median, zip(*errors)))
        spread = max(max(v)-min(v) for v in zip(*errors))
        guard.append(primary <= .001 and spread <= .001)
    res.update(calibration=calibration, native_shift=native_counts, paired_errors=errors, primary_m=primary,
               spread_m=spread, exercised=exercised, all_guards=all(guard))
    if res['postflight']:
        res['hypothesis'] = ('refuted' if not all(guard) else 'confirmed' if primary is not None else 'inconclusive')


if __name__ == '__main__':
    main(Path(sys.argv[1]).resolve())
