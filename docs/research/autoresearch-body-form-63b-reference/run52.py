"""Local source-reference probe on the standing #51 harness; no geometry writes."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import statistics
import subprocess
import sys
import time
import types

PREV = '95dcfb93ea60f9f72713ae9804a8926d46034b34'
PREFIX = 'docs/research/autoresearch-body-form-r51/'
OLD = Path('C:/x/t_fb3a0b98-r51/run1')
LEVELS = {'16.85': '8.03', '17.8': '8.98', '18.2': '9.38', '19.8': '10.98'}
LO, HI = 2.8, 5.4


def old(name):
    return subprocess.check_output(['git', 'show', f'{PREV}:{PREFIX}{name}'])


def load(p):
    return json.loads(Path(p).read_bytes())


def module(name):
    mod = types.ModuleType(name)
    mod.__file__ = name
    exec(compile(old(name), name, 'exec'), mod.__dict__)
    return mod


def clip(iv):
    return [(max(a, LO), min(b, HI)) for a, b in iv if max(a, LO) < min(b, HI)]


def diff(a, b):
    intersection = sum(max(0, min(j, l) - max(i, k)) for i, j in a for k, l in b)
    return max(0, sum(j-i for i,j in a+b) - 2*intersection)


def save(path, data):
    path.write_bytes((json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))


def main(out):
    out.mkdir(parents=True)
    temp = out / 'native-temp'
    temp.mkdir()
    env = os.environ | {key: str(temp) for key in ('TEMP', 'TMP', 'TMPDIR')}
    start = time.monotonic()
    cap = 150
    r = {'status': 'running', 'hypothesis': 'inconclusive', 'cap_s': cap, 'runs': {}, 'margins': []}
    result = out / 'receipt.json'
    try:
        base = module('run51.py')
        det = Path(base.DET)
        key = Path(base.KEY)
        hist = json.loads(old('receipt.json'))
        paths = {Path(p): h for h,p in base.PINS.values()}
        paths.update({Path(p): h for _,p,h in base.VARIANTS.values()})
        w = OLD / 'fixtures/W_shift_opening.fbx'
        paths.update({w: '489d1c0e2fd7330db85d35c5e6d5b4253a2140a44f052bf8d812bdd9ec76aca9',
                      key/'SHA256SUMS.txt': '2b060600347e4203b70bc23561963a5b2bacd96c8412416084345df816cb0eff',
                      det/'extract.py': 'ee50925b8a45d6b55d4409cc21893d7932ae7b76d66c3a7c7c4b6b4bb51875af',
                      det/'score_heldout.py': 'e9d6f65b6373a4fc95c91a3ea202d29cfb2f052a2aee4bfe0eb1ee1fb3d9b942',
                      Path(base.BLENDER): '1e6624af112b3c936f4b038b025ebd2bf00ae72c4b62881a6787166d71c58fa5'})
        variants = {k: Path(p) for k,(_,p,_) in base.VARIANTS.items()} | {'W_shift_opening': w}
        for name in variants:
            for rep in range(1,4):
                paths[OLD/name/f'rep{rep}'/'vs_key.json'] = hist['runs'][name][rep-1]['vs_key_sha256']
        def verify():
            bad = [str(p) for p,h in paths.items() if base.sha(p) != h]
            if bad:
                raise ValueError(f'hash mismatch {bad}')
        r['manifest'] = {p.as_posix(): h for p,h in paths.items()}
        verify()
        r['preflight'] = 'ok'
        sys.dont_write_bytecode = True
        spec = importlib.util.spec_from_file_location('score_heldout', det/'score_heldout.py')
        score = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(score)
        contour_key = load(key/'heldout-key-v001.json')
        ring = {x['ring_index']: x['xy'] for x in contour_key['contour_vertices_in_box']}
        a,u,_ = score.frame(ring,18,19)
        posthoc = old('posthoc51.py').decode('utf-8')
        assert 'A, B = (85.519, 16.334), (95.936, 27.133)' in posthoc
        assert (a, ring[19]) == ([85.519,16.334], [95.936,27.133])
        raw_ref = load(base.SRC)['modules']['A']['reference']
        source = [(name, (p,q)) for name,(p,q) in raw_ref if all(abs(score.local(x,a,u)[1]) <= .03 for x in (p,q))]
        intervals = lambda segs: clip(score.wall_intervals(segs,a,u))
        b = intervals([(a, ring[19])])
        c = intervals([seg for _,seg in source])
        assert b == [(LO,HI)] and len(c) == 2 and c[0][0] == LO and c[1][1] == HI
        left,right = c[0][1],c[1][0]
        assert right-left >= 1.0
        chord = [[a[0]+s*u[0],a[1]+s*u[1]] for s in (left,right)]
        r['reference'] = {'B': b, 'C': c, 'source_lines': [[name, seg] for name,seg in source if intervals([seg])]}
        copies = {}
        for name,p in variants.items():
            fbx = out/f'{name}.fbx'
            shutil.copyfile(p,fbx)
            if base.sha(fbx) != paths[p]:
                raise ValueError('bad staged copy')
            copies[name] = fbx
        def one(name, rep):
            d = out/name/f'rep{rep}'
            d.mkdir(parents=True)
            raw = d/'raw.extract.json'
            remaining = cap - (time.monotonic()-start)
            if remaining <= 0:
                raise TimeoutError('wall cap')
            with (d/'extract.log').open('wb') as log:
                subprocess.run([base.BLENDER, '--background', '--factory-startup', '--disable-autoexec', '--threads', '1',
                                '--python-exit-code', '1', '--python', str(det/'extract.py'), '--', str(copies[name]),
                                str(raw), ','.join(LEVELS.values())], check=True, timeout=remaining, env=env, stdout=log,
                               stderr=subprocess.STDOUT)
            ex = load(raw)
            sections = {z: ex['sections'][real] for z,real in LEVELS.items()}
            lab = ex | {'sections': sections, 'loops': [lp | {'z': [round(z+8.82,4) for z in lp['z']]} for lp in ex['loops']]}
            cand = d/'candidate.extract.json'
            save(cand,lab)
            dest = d/'vs_key.json'
            score.main(str(key/'heldout-key-v001.json'), str(key/'SHA256SUMS.txt'), str(cand), str(dest))
            current, past = load(dest), load(OLD/name/f'rep{rep}'/'vs_key.json')
            def normalized(report):
                return report | {'provenance': {k:v for k,v in report['provenance'].items() if k != 'candidate_fbx'}}
            row = {'B': [], 'C': [], 'changed_sections': 0, 'status': 'scored', 'intervals': {},
                   'legacy_equal': normalized(current) == normalized(past), 'legacy_openings': current['openings'],
                   'legacy_extras': current['extra_openings'], 'legacy_non_pass': {k:v for k,v in current['items'].items() if v['status'] != 'pass'},
                   'extract_sha256': base.sha(raw), 'legacy_sha256': base.sha(dest)}
            if name == 'v007':
                row['fill_C'] = []
                row['fill_changed_segments'] = {}
            for z in score.CONTOUR_Z:
                segs = sections[z]
                iv = intervals(segs)
                if not iv:
                    row['status'] = 'not_exercised'
                    continue
                row['intervals'][z] = iv
                eb,ec = diff(iv,b),diff(iv,c)
                row['B'].append(eb)
                row['C'].append(ec)
                row['changed_sections'] += abs(eb-ec) > 1e-9
                if name == 'v007':
                    row['fill_C'].append(diff(intervals([*segs,chord]),c))
                    row['fill_changed_segments'][z] = 1
            return row
        ready, meets = True, True
        names = list(variants)
        for rep in range(1,4):
            pair_start = time.monotonic()
            rows = r['runs'][str(rep)] = {}
            for name in names:
                rows[name] = one(name,rep)
                if rep == 1 and name == 'v002':
                    elapsed = time.monotonic()-pair_start
                    r['timing_pair_s'] = elapsed
                    if elapsed*10+15 > cap-(time.monotonic()-start):
                        raise TimeoutError('timing pair exceeds remaining budget')
            arow,wrow = rows['v007'],rows['W_shift_opening']
            if not all(row['legacy_equal'] and row['status'] == 'scored' and row['changed_sections'] == 2 for row in rows.values()):
                ready = False
            if not all(row['status'] == 'scored' for row in rows.values()):
                continue
            for row in rows.values():
                row['B_max'],row['C_max'] = max(row['B']),max(row['C'])
            r['margins'].append({k:min(rows[n][k+'_max'] for n in names[1:-1])-arow[k+'_max'] for k in ('B','C')})
            last = r['margins'][-1]
            ready &= (max(arow['fill_C']) >= 1 and max(arow['fill_C'])-arow['C_max'] >= 1
                      and max(abs(x-y) for x,y in zip(wrow['C'],arow['C'],strict=True)) <= .001
                      and wrow['legacy_non_pass'].get('opening:6189f94:edges', {}).get('status') == 'fail')
            meets &= (last['B'] < 0 and last['C'] >= .20 and arow['C_max'] <= .12
                      and all(rows[n]['C_max'] >= 1 for n in names[1:-1]))
        verify()
        if any(base.sha(fbx) != paths[variants[name]] for name,fbx in copies.items()):
            raise ValueError('staged copy changed')
        r['postflight'] = 'ok'
        if len(r['margins']) == 3:
            r['margin_summary'] = {k: {'median': statistics.median(x[k] for x in r['margins']),
                                      'spread': max(x[k] for x in r['margins'])-min(x[k] for x in r['margins'])} for k in ('B','C')}
        r.update(status='complete', hypothesis=('confirmed' if meets else 'refuted') if ready else 'inconclusive')
    except (TimeoutError, subprocess.TimeoutExpired) as exc:
        r.update(status='budget_stop', error=str(exc))
    except Exception as exc:
        r.update(status='error', error=repr(exc))
        raise
    finally:
        r['wall_s'] = time.monotonic()-start
        save(result,r)
        print(r['status'], r['hypothesis'], r.get('margin_summary'), r['wall_s'])


if __name__ == '__main__':
    main(Path(sys.argv[1]).resolve())
