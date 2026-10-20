"""Reproduce #359: freeze, tests A/B, semantics, timing, verify. No production writes."""
import argparse
import copy
import hashlib
import importlib.util
import inspect
import json
import math
import os
from pathlib import Path
import platform
import random
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
from candidate import BASELINE, CANDIDATE, SELECTION, START, END, install

TESTS = ['tests/test_mesh_audit_generated_crossings.py',
         'tests/test_mesh_audit_planar_polygons.py', 'tests/test_shared_library.py']
SOURCES = ['technical_library/mesh_audit/core.py',
           'technical_library/mesh_audit/README.md', 'src/twinqa/geometry/winding.py'] + TESTS
PLANES = ['XY', 'XZ', 'YZ', 'oblique']
spec = importlib.util.spec_from_file_location('oracle359', ROOT / TESTS[0])
oracle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(oracle)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def filehash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(name, value):
    path = HERE / name
    # Evidence is append-only by filename; reruns require a fresh worktree.
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def load(name):
    return json.loads((HERE / name).read_text(encoding='utf-8'))


def expand(poly, factor):
    return [[a[0] + (b[0]-a[0])*j/factor, a[1] + (b[1]-a[1])*j/factor]
            for a, b in zip(poly, poly[1:] + poly[:1]) for j in range(factor)]


def embed(poly, plane):
    functions = {'XY': lambda x,y: (float(x),float(y),0.0),
                 'XZ': lambda x,y: (float(x),0.0,float(y)),
                 'YZ': lambda x,y: (0.0,float(x),float(y)),
                 'oblique': lambda x,y: (float(x),float(y),float(x+2*y))}
    if plane not in functions:
        raise ValueError(f'Unknown embedding: {plane}')
    return [functions[plane](x,y) for x,y in poly]


def pytest_run(mode, name, collect=False, regression=False):
    env = dict(os.environ, HYP359_MODE=mode, HYP359_REPORT=str(HERE / (name+'.json')))
    env['PYTHONPATH'] = os.pathsep.join([str(HERE), str(ROOT), str(ROOT/'src'), env.get('PYTHONPATH','')])
    cmd = ['env', '-u', 'MSYS_NO_PATHCONV', '-u', 'MSYS2_ARG_CONV_EXCL',
           'uv', 'run', 'pytest', '-q', '-p', 'no:cacheprovider',
           '--basetemp=C:/x/pi-t_c80d2ee7', '-p', 'evidence_plugin']
    if collect:
        cmd += ['--collect-only']
    cmd += ['experiments/hyp-359/test_projection_work.py'] if regression else TESTS
    result = subprocess.run(cmd, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=400)
    with (HERE / (name+'.log')).open('x', encoding='utf-8') as f:
        f.write(result.stdout)
    print(result.stdout.splitlines()[-1], flush=True)
    return result.returncode


def freeze():
    rng = random.Random(105)
    grid = [(x,y) for x in range(-15,16) for y in range(-15,16)]
    population = []
    attempts = 0
    while len(population) < 200:
        attempts += 1
        poly = rng.sample(grid, rng.randint(4,9))
        if not oracle._has_collinear_triple(poly):
            population.append(poly)
    labels = [oracle._count_proper_crossing_pairs(p) for p in population]
    counts = [sum(c == 0 for c in labels), sum(c > 0 for c in labels), sum(c > 1 for c in labels)]
    assert counts == [27,173,117] and attempts == 245
    selected = [next(i for i,c in enumerate(labels) if c == 0), next(i for i,c in enumerate(labels) if c >= 2)]
    # Store all originals and all prescribed derivatives, not only seeds.
    inputs = {'population': population, 'pair_counts': labels, 'selected': selected,
              'derivatives': {str(f): [expand(p,f) for p in population] for f in (2,4)},
              'long': {str(i): expand(population[i],16) for i in selected}}
    save('inputs.json', inputs)
    assert pytest_run('A', 'inventory', collect=True) == 0
    inventory = load('inventory.json')['nodes']
    prediction = {
        'prior': 'Medium rejection chance; cubic selection may not dominate whole-call work; projection ties may differ.',
        'long': [{'polygon':i, 'plane':p, 'max_B_over_A':0.60,
                  'prediction':'likely pass; not measured'} for i in selected for p in PLANES],
        'short': {'max_B_over_A':1.10, 'prediction':'uncertain; overhead can reject'},
        'confirmation': 'independent three pairs per long case, same <=0.60',
        'semantics': 'zero full-dictionary/oracle/mutation differences; three identical runs',
        'tests': 'unchanged focused inventory and outcomes; no failures',
        'sampling': 'one warmup per implementation; seven alternating AB/BA pairs; exactly three calls/batches per sample',
        'timing_cap_seconds':900, 'task_cap_seconds':2700,
        'delivery_passed':False,
    }
    save('frozen.json', {'head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
         'main':subprocess.check_output(['git','rev-parse','main'],text=True).strip(),
         'python':sys.version, 'platform':platform.platform(), 'counts':counts, 'attempts':attempts,
         'input_sha256':filehash(HERE/'inputs.json'),
         'population_sha256':digest(inputs['population']),
         'derivative_sha256':{f:digest(p) for f,p in inputs['derivatives'].items()},
         'long_sha256':{i:digest(p) for i,p in inputs['long'].items()}, 'inventory':inventory,
         'inventory_sha256':digest(inventory), 'predictions':prediction,
         'hashes':{p:filehash(ROOT/p) for p in SOURCES},
         'experiment_hashes':{p.name:filehash(p) for p in HERE.glob('*.py')},
         'issue_sha256':filehash(HERE/'issue.json'),
         'frozen_at_unix':time.time()})
    print('Frozen', counts, 'selected', selected, 'nodes', len(inventory), flush=True)


def check_frozen():
    f = load('frozen.json')
    assert filehash(HERE/'inputs.json') == f['input_sha256']
    assert all(filehash(ROOT/p) == h for p,h in f['hashes'].items())
    assert all(filehash(HERE/p) == h for p,h in f['experiment_hashes'].items())
    return f


def variants(inputs):
    for i, poly in enumerate(inputs['population']):
        for plane in PLANES:
            for reverse in (False,True):
                base = poly[::-1] if reverse else poly
                for shift in range(len(base)):
                    yield ['original',i,1,plane,reverse,shift], embed(base[shift:]+base[:shift],plane)
    for factor in (2,4):
        for i,poly in enumerate(inputs['derivatives'][str(factor)]):
            for plane in PLANES:
                for reverse in (False,True):
                    base = poly[::-1] if reverse else poly
                    for shift in (0,len(base)//2):
                        yield ['derivative',i,factor,plane,reverse,shift], embed(base[shift:]+base[:shift],plane)
    for i in inputs['selected']:
        for plane in PLANES:
            yield ['long',i,16,plane,False,0], embed(inputs['long'][str(i)],plane)


def semantics():
    check_frozen()
    inputs = load('inputs.json')
    counts = {'original':0,'derivative':0,'long':0}
    failures = []
    hashes = {mode:[] for mode in ('A','B')}
    for rep in range(3):
        records = {mode:[] for mode in ('A','B')}
        for key,vertices in variants(inputs):
            faces = [tuple(range(len(vertices)))]
            before = copy.deepcopy((vertices,faces))
            result = {}
            for mode in ('A','B'):
                result[mode] = install(mode)(vertices,faces)
                records[mode].append([key,result[mode]])
            expected = int(inputs['pair_counts'][key[1]] > 0)
            ok = (result['A'] == result['B'] and (vertices,faces) == before and
                  all(r['self_intersecting_polygons'] == expected and
                      r['delivery_passed'] is False and r['intersection_test_performed'] is False
                      for r in result.values()))
            if not ok:
                failures.append({'key':key,'results':result,'expected':expected})
            if rep == 0:
                counts[key[0]] += 1
        for mode in records:
            hashes[mode].append(digest(records[mode]))
        print('semantic repetition',rep+1,counts, 'failures',len(failures),flush=True)
    save('semantics.json', {'counts_per_repetition':counts,'repetitions':3,'hashes':hashes,
         'repeat_identical':len(set(hashes['A']+hashes['B'])) == 1,
         'failures':failures[:10], 'failure_count':len(failures),
         'delivery_passed':False})


def timing():
    check_frozen()
    inputs = load('inputs.json')
    started = time.perf_counter()
    rows = []
    def sample(mode, workload):
        if time.perf_counter()-started >= 900:
            raise TimeoutError('15-minute timing cap')
        call = install(mode)
        t = time.perf_counter()
        for _ in range(3):
            for vertices,faces in workload:
                call(vertices,faces)
        return (time.perf_counter()-t)/3
    def block(name, workload, pairs):
        # Each implementation gets exactly one untimed warmup whole workload.
        for mode in ('A','B'):
            call = install(mode)
            for v,f in workload:
                call(v,f)
        raw = {'A':[],'B':[]}
        orders = []
        for pair in range(pairs):
            order = 'AB' if pair%2 == 0 else 'BA'
            orders.append(order)
            for mode in order:
                raw[mode].append(sample(mode,workload))
        medians = {m:statistics.median(s) for m,s in raw.items()}
        row = {'name':name,'pairs':pairs,'orders':orders,'seconds_per_call_or_batch':raw,
               'median':medians,'ratio':medians['B']/medians['A']}
        rows.append(row)
        print(name, 'B/A',row['ratio'],flush=True)
    try:
        for i in inputs['selected']:
            for plane in PLANES:
                v = embed(inputs['long'][str(i)],plane)
                block(f'long-{i}-{plane}',[(v,[tuple(range(len(v)))])],7)
        batch = [(embed(p,'XY'),[tuple(range(len(p)))]) for p in inputs['population']]
        block('short-200-XY',batch,7)
        # Separate confirmation block after all initial workloads, reversed case order.
        for i in reversed(inputs['selected']):
            for plane in reversed(PLANES):
                v = embed(inputs['long'][str(i)],plane)
                block(f'confirmation-{i}-{plane}',[(v,[tuple(range(len(v)))])],3)
        error = None
    except Exception as exc:
        error = repr(exc)
    save('timing.json', {'rows':rows,'elapsed_seconds':time.perf_counter()-started,
                         'error':error,'delivery_passed':False})


def probes():
    """Bounded fail-closed/report-only probes; no new acceptance policy for inspect_mesh."""
    rows = []
    cases = [('empty',[],[]), ('partial',[(0,0,0)],[(0,1,2)]),
             ('nonplanar',[(0,0,0),(1,1,1),(0,1,0),(1,0,0)],[(0,1,2,3)])]
    for c in (float('nan'),float('inf'),-float('inf')):
        cases.append((repr(c),[(c,0,0)],[]))
    for h in (0.5e-10,1e-10,2e-10):
        cases.append((f'threshold-{h}',[(0,0,0),(1,h,0),(0,h,0),(1,0,0)],[(0,1,2,3)]))
    for mode in ('A','B'):
        for name,v,f in cases:
            try:
                r = install(mode)(v,f)
                assert r['delivery_passed'] is False and r['intersection_test_performed'] is False
                if name == 'threshold-1e-10':
                    assert r['self_intersecting_polygons'] == 0
                rows.append({'mode':mode,'case':name,'outcome':'report-only; delivery failed','result':r})
            except ValueError as exc:
                rows.append({'mode':mode,'case':name,'outcome':'error','error':str(exc)})
    errors = []
    for func,arg in ((install,'missing-key'),(lambda p:embed([],p),'missing-plane')):
        try:
            func(arg)
        except ValueError as exc:
            assert arg in str(exc)
            errors.append(str(exc))
        else:
            raise AssertionError('Unmapped key silently accepted')
    # First-on-ties selector checked by independent brute force on every frozen original.
    inputs = load('inputs.json')
    selector_source = 'def select(poly):\n' + SELECTION + '    return best_cross, best_mag2\n'
    ns = {}
    exec(selector_source,ns)
    tie_checks = 0
    tie_population = inputs['population'] + [[[-1,-1],[1,-1],[1,1],[-1,1]],[[0,0],[0,0],[0,0],[0,0]]]
    for poly in tie_population:
        for plane in PLANES:
            p = embed(poly,plane)
            p0 = p[0]
            distances = [sum((q[k]-p0[k])**2 for k in range(3)) for q in p]
            p1 = p[distances.index(max(distances))]
            u = [p1[k]-p0[k] for k in range(3)]
            crosses = []
            for q in p:
                v = [q[k]-p0[k] for k in range(3)]
                crosses.append((u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]))
            magnitudes = [sum(c*c for c in cross) for cross in crosses]
            mag = max(magnitudes)
            expected = crosses[magnitudes.index(mag)] if mag > 0 else None
            assert ns['select'](p) == (expected,mag)
            tie_checks += 1
    save('probes.json',{'fail_closed_reports':rows,'unknown_key_errors':errors,
         'selector_bruteforce_checks':tie_checks,'delivery_passed':False})


def verify():
    frozen = check_frozen()
    a,b = load('affected-A.json'),load('affected-B.json')
    inventory_ok = a['nodes'] == b['nodes'] == frozen['inventory']
    tests_ok = a['outcomes'] == b['outcomes'] and a['exitstatus'] == b['exitstatus'] == 0
    s,t = load('semantics.json'),load('timing.json')
    violations = [r['name'] for r in t['rows'] if r['ratio'] > (1.10 if r['name'].startswith('short') else 0.60)]
    if s['failure_count'] or not s['repeat_identical'] or not inventory_ok or not tests_ok or violations:
        verdict = 'REJECTED'
    elif len(t['rows']) != 17 or t['error']:
        verdict = 'INCONCLUSIVE'
    else:
        verdict = 'CONFIRMED'
    save('verdict.json',{'verdict':verdict,'delivery_passed':False,'timing_violations':violations,
         'inventory_unchanged':inventory_ok,'focused_results_identical':tests_ok,
         'source_test_input_experiment_hashes_unchanged':True})
    print(verdict,violations)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', choices=['freeze','A','B','semantics','timing','probes','verify'])
    args = parser.parse_args()
    if args.stage == 'freeze': freeze()
    elif args.stage in ('A','B'):
        check_frozen()
        assert pytest_run(args.stage,'affected-'+args.stage) == 0
        status = pytest_run(args.stage,'regression-'+args.stage,regression=True)
        assert status == (1 if args.stage == 'A' else 0)
    else:
        globals()[args.stage]()
