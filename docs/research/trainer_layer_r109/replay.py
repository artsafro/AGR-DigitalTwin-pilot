"""R109 observation only: wall-layer evidence census of the pinned site-63 Revit FBX (no key is read)."""
from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
import hashlib
import json
import re
import shutil
import statistics
import struct
import subprocess
import sys
import time
import zlib

ROOT = Path(__file__).resolve().parents[3]
R105 = '95ae5adb1bf907e927b994296c51ad321edd18b7'
MANIFEST = 'docs/research/autoresearch-trainer-storey-band-r105.md'
EV = Path('G:/Мой диск/AGR-evidence')
SOURCE = '1855-trainer-v0/bank/63a-stage1/STLB-04_RR_AR.fbx'
BLENDER = 'C:/Program Files/Blender Foundation/Blender 4.4/blender.exe'
DUMP = 'docs/research/trainer_layer_r109/layer_dump_blender.py'
FAMILY = 'Базовая стена Вентфасад 250 250 '
WALL = 'Базовая стена '
BOXES = {'63A': ([79.0, 61.8, -2], [121.6, 97.6, 79.2]), '63B': ([53.3, -1.4, -2], [98.4, 36.0, 62.4])}
SCOPE = {'63A': (10.15, 47.95), '63B': (4.65, 51.90)}  # stated bands, same as #107/#108
PARITY_63B_FAMILY_ROWS = 907
MIN_FAMILY_GEOMETRIES = 907  # frozen: N >= 907 (superset of the 63B in-band rows)
BUDGET_S = 600.0  # frozen: <= 10 min wall, end to end


# ---- minimal FBX 7.x binary reader -------------------------------------------------------------------------
def read_fbx(data: bytes):
    if not data.startswith(b'Kaydara FBX Binary  \x00'):
        raise ValueError('not a binary FBX')
    ver = struct.unpack('<I', data[23:27])[0]
    w, h = (8, '<QQQ') if ver >= 7500 else (4, '<III')

    def prop(o):
        t = chr(data[o]); o += 1
        fixed = {'Y': '<h', 'C': '<?', 'I': '<i', 'L': '<q', 'F': '<f', 'D': '<d'}
        if t in fixed:
            n = struct.calcsize(fixed[t])
            return struct.unpack(fixed[t], data[o:o + n])[0], o + n
        if t in 'fdlib':
            ln, enc, cl = struct.unpack('<III', data[o:o + 12]); o += 12
            raw = data[o:o + cl]; o += cl
            if t == 'b':
                return None, o
            body = zlib.decompress(raw) if enc else raw
            return struct.unpack(f'<{ln}{t}', body), o
        if t in 'SR':
            ln = struct.unpack('<I', data[o:o + 4])[0]; o += 4
            return data[o:o + ln], o + ln
        raise ValueError(f'unknown FBX property type {t!r}')

    def node(o):
        end, n_props, _ = struct.unpack(h, data[o:o + 3 * w]); o += 3 * w
        nl = data[o]; o += 1
        name = data[o:o + nl].decode(); o += nl
        if end == 0:
            return None, o
        props = []
        for _ in range(n_props):
            v, o = prop(o)
            props.append(v)
        kids = []
        while o < end:
            k, o = node(o)
            if k is None:
                break
            kids.append(k)
        return (name, props, kids), end

    top, o = {}, 27
    while o < len(data) - 160:
        n, o = node(o)
        if n is None:
            break
        top[n[0]] = n
    return top


def wall_geometries(top):
    """{geometry id: (model names, polygons, per-polygon material index list)}"""
    models = {p[0]: p[1].split(b'\x00\x01')[0].decode('utf-8') for n, p, _ in top['Objects'][2] if n == 'Model'}
    geos = {p[0]: k for n, p, k in top['Objects'][2] if n == 'Geometry'}
    users = defaultdict(list)
    for _, p, _ in top['Connections'][2]:
        if p[0] == b'OO' and p[1] in geos and p[2] in models:
            users[p[1]].append(models[p[2]])
    out = {}
    for g, names in users.items():
        if not any(nm.startswith(WALL) for nm in names):
            continue
        kid = {k[0]: k for k in geos[g]}
        polys, cur = [], []
        for i in kid['PolygonVertexIndex'][1][0]:
            if i < 0:
                cur.append(~i); polys.append(cur); cur = []
            else:
                cur.append(i)
        mats = [0] * len(polys)
        lem = kid.get('LayerElementMaterial')
        if lem:
            arr = [k for k in lem[2] if k[0] == 'Materials'][0][1][0]
            mats = list(arr) if len(arr) == len(polys) else [arr[0]] * len(polys)
        out[g] = (names, polys, mats)
    return out


# ---- layer evidence (criteria a/b/c of the frozen contract) -------------------------------------------------
def edges(poly):
    return [tuple(sorted((poly[i], poly[(i + 1) % len(poly)]))) for i in range(len(poly))]


def components(polys):
    parent = {}

    def find(x):
        while parent.setdefault(x, x) != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for poly in polys:
        r = find(poly[0])
        for v in poly[1:]:
            parent[find(v)] = r
    return len({find(v) for poly in polys for v in poly})


def evidence(polys, mats):
    use = Counter(e for p in polys for e in edges(p))
    a = components(polys) >= 2
    b = any(c > 2 for c in use.values())
    c = False
    for m in set(mats):
        part = [p for p, k in zip(polys, mats) if k == m]
        if len(part) == len(polys):
            continue
        pu = Counter(e for p in part for e in edges(p))
        if pu and all(n >= 2 and n % 2 == 0 for n in pu.values()):
            c = True
    return {'a_components': a, 'b_nonmanifold': b, 'c_closed_partition': c, 'any': a or b or c}


def family(names):
    head = [nm for nm in names if nm.startswith(WALL)][0]
    return FAMILY.strip() if head.startswith(FAMILY) else ' '.join(head.split(' ')[:4])


def census(data: bytes):
    table = defaultdict(Counter)
    for names, polys, mats in wall_geometries(read_fbx(data)).values():
        ev = evidence(polys, mats)
        row = table[family(names)]
        row['geometries'] += 1
        row['multi_material'] += len(set(mats)) > 1
        for k, v in ev.items():
            row[k] += v
    return {k: dict(v) for k, v in sorted(table.items())}


# ---- Blender secondary (M109-B) ------------------------------------------------------------------------------
def blender_rows(doc):
    out = {}
    for tag, (lo_b, hi_b) in BOXES.items():
        lo_s, hi_s = SCOPE[tag]
        rows = Counter()
        for o in doc['objects']:
            if not o['verts'] or not o['name'].startswith(WALL):
                continue
            x, y = zip(*o['hull'])
            lo, hi = [min(x), min(y), o['z'][0]], [max(x), max(y), o['z'][1]]
            if not all(a <= b <= c <= d for a, b, c, d in zip(lo_b, lo, hi, hi_b)):
                continue
            if not lo_s - 1e-6 <= lo[2] < hi_s - 1e-6:
                continue
            fam = 'family' if o['name'].startswith(FAMILY) else 'other'
            rows[fam + '_rows'] += 1
            rows[fam + '_multi_part'] += len(o['parts']) >= 2
        out[tag] = dict(rows)
    return out


# ---- frozen controls, run inside every replay (r2: review r1 P1.1/P1.2) -------------------------------------
def _box(o):
    f = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    return [[o + i for i in q] for q in f]


def _layered():
    m = {0: 1, 2: 3, 4: 5, 6: 7, 1: 8, 3: 9, 5: 10, 7: 11}
    return _box(0) + [[m[i] for i in q] for q in _box(0)]


# name: (polys, mats, expected raw evidence subset). 'b_dup_face' is the r1 counterexample: one closed cube with one
# outer face duplicated fires raw (b) without any second solid or interface, so (b) is NOT specific to layers.
CONTROLS = {
    'pos_a_disjoint': (lambda: _box(0) + _box(8), lambda: [0] * 12, {'a_components': True, 'any': True}),
    'pos_b_interface': (_layered, lambda: [0] * 12, {'b_nonmanifold': True, 'a_components': False, 'any': True}),
    'pos_c_partition': (_layered, lambda: [0] * 6 + [1] * 6, {'c_closed_partition': True, 'any': True}),
    'neg_painted_face': (lambda: _box(0), lambda: [1, 0, 0, 0, 0, 0],
                         {'a_components': False, 'b_nonmanifold': False, 'c_closed_partition': False, 'any': False}),
    'neg_clean_cube': (lambda: _box(0), lambda: [0] * 6,
                       {'a_components': False, 'b_nonmanifold': False, 'c_closed_partition': False, 'any': False}),
    'b_dup_face': (lambda: _box(0) + [list(_box(0)[0])], lambda: [0] * 7,
                   {'a_components': False, 'b_nonmanifold': True, 'c_closed_partition': False, 'any': True}),
}
# What a raw criterion proves. A fired feature is a layer CANDIDATE, never proof of a layer or of a reachable selector.
CRITERIA = {'a_components': 'candidate (separate solids)',
            'b_nonmanifold': 'unvalidated (fires on a duplicated outer face, control b_dup_face)',
            'c_closed_partition': 'candidate (closed material sub-solid)'}


def run_controls():
    out = {}
    for name, (polys, mats, want) in CONTROLS.items():
        try:
            got = evidence(polys(), mats())
            out[name] = {'pass': all(got.get(k) == v for k, v in want.items()), 'got': got}
        except Exception as exc:  # a crashing detector is a failed control, not a skipped one
            out[name] = {'pass': False, 'error': f'{type(exc).__name__}: {exc}'}
    return out


def decide(runs, family_geometries, family_rows_63b, controls, wall_s):
    """Frozen verdict rule -> (hypothesis, status, reasons). Pure; tested through main()."""
    if wall_s is None or wall_s > BUDGET_S:
        return 'inconclusive', 'budget_stop', [f'wall {wall_s} s > {BUDGET_S:.0f} s']
    reasons = []
    failed = sorted(k for k in CONTROLS if not controls.get(k, {}).get('pass'))
    if failed:
        reasons.append('frozen controls failed or missing: ' + ','.join(failed))
    if len(runs) != 3 or len({r['result_sha256'] for r in runs}) != 1:
        reasons.append('census runs disagree or != 3')
    if (family_geometries or 0) < MIN_FAMILY_GEOMETRIES:
        reasons.append(f'N={family_geometries} < {MIN_FAMILY_GEOMETRIES}')
    if family_rows_63b != PARITY_63B_FAMILY_ROWS:
        reasons.append(f'63B family rows {family_rows_63b} != {PARITY_63B_FAMILY_ROWS}')
    if reasons:
        return 'inconclusive', 'invalid', reasons
    m109 = [r['census'].get(FAMILY.strip(), {}).get('any', 0) for r in runs]
    if all(m == 0 for m in m109):
        return 'confirmed', 'complete', []
    if all(m > 0 for m in m109):
        return 'refuted', 'complete', []
    return 'inconclusive', 'complete', ['M109 differs between runs']


# ---- replay -------------------------------------------------------------------------------------------------
def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def blob(rev, path):
    return subprocess.check_output(['git', 'show', f'{rev}:{path}'], cwd=ROOT)


def check_frozen(commit, work):
    script = Path(__file__).resolve()
    if len(commit) != 40 or blob(commit, script.relative_to(ROOT).as_posix()) != script.read_bytes().replace(
            b'\r\n', b'\n') or blob(commit, DUMP) != (ROOT / DUMP).read_bytes().replace(b'\r\n', b'\n'):
        raise ValueError('use the full frozen variant commit with exact replay/dump blobs')
    if not work.is_relative_to(ROOT):
        raise ValueError('output must be inside this worktree')


def verify_pins(pins, msg='pinned input changed'):
    for p, h in pins.items():
        if sha(p) != h:
            raise ValueError(f'{msg}: {p}')


def pinned_inputs():
    manifest = dict(re.findall(r'^\| `([^`]+)` \| `([0-9a-f]{64})` \|$', blob(R105, MANIFEST).decode('utf-8'), re.M))
    pins = {EV / SOURCE: manifest[SOURCE], Path(BLENDER): manifest[BLENDER]}
    verify_pins(pins, 'pinned input mismatch')
    return pins


def read_source(pins):
    data = (EV / SOURCE).read_bytes()
    if hashlib.sha256(data).hexdigest() != pins[EV / SOURCE]:
        raise ValueError('source changed while reading')
    return data


def blender_secondary(work, pins, timeout):
    """-> (M109-B rows, blender wall s, dump sha); (None, None, None) when the remaining budget runs out."""
    staged = work / 'source.fbx'
    shutil.copyfile(EV / SOURCE, staged)
    out = work / 'layer_dump.json'
    s = time.monotonic()
    try:
        proc = subprocess.run([BLENDER, '-b', '--factory-startup', '--python', str(ROOT / DUMP), '--', str(staged),
                               str(out)], capture_output=True, text=True, encoding='utf-8', errors='replace',
                              timeout=max(1.0, timeout))
    except subprocess.TimeoutExpired:
        return None, None, None
    finally:
        staged.unlink()
    blender_s = time.monotonic() - s
    doc = json.loads(out.read_text(encoding='utf-8')) if out.exists() else None
    if proc.returncode or doc is None or doc['sha256'] != pins[EV / SOURCE]:
        raise RuntimeError(f'blender dump failed rc={proc.returncode}: {proc.stderr[-400:]}')
    return blender_rows(doc), blender_s, sha(out)


def main():
    work, commit = Path(sys.argv[1]).resolve(), sys.argv[2]
    check_frozen(commit, work)
    work.mkdir()
    t0 = time.monotonic()
    pins = pinned_inputs()
    controls = run_controls()
    data = read_source(pins)
    runs = []
    for i in range(3):
        s = time.monotonic()
        res = census(data)
        runs.append({'run': i + 1, 'wall_s': time.monotonic() - s, 'result_sha256': hashlib.sha256(
            json.dumps(res, sort_keys=True, ensure_ascii=False).encode()).hexdigest(), 'census': res})
    brows, blender_s, dump_sha = blender_secondary(work, pins, BUDGET_S - (time.monotonic() - t0))
    verify_pins(pins)
    wall = time.monotonic() - t0
    fam = runs[0]['census'].get(FAMILY.strip(), {})
    hypothesis, status, reasons = decide(runs, fam.get('geometries'), (brows or {}).get('63B', {}).get('family_rows'),
                                         controls, wall if brows is not None else None)
    m109 = [r['census'].get(FAMILY.strip(), {}).get('any', 0) for r in runs]
    real_positive = sorted(k for k, v in runs[0]['census'].items() if v.get('any'))
    receipt = {'hypothesis': hypothesis, 'status': status, 'reasons': reasons, 'variant_commit': commit,
               'claim_scope': 'absence/presence of the three measured raw features only; a fired feature is a '
                              'layer candidate, never proof of a layer; selector reachability is not measured',
               'selector_reachable': 'not_measured', 'criteria': CRITERIA, 'controls': controls,
               'wall_s': wall, 'budget_s': BUDGET_S, 'blender_wall_s': blender_s,
               'M109_family_layer_evidence': {'median': statistics.median(m109), 'runs': m109,
                                              'family_geometries': fam.get('geometries'), 'family': fam},
               'M109B_blender_rows': brows, 'real_source_positive_families': real_positive or 'not_exercised',
               'census_runs': [{k: v for k, v in r.items() if k != 'census'} for r in runs],
               'census': runs[0]['census'], 'inputs': {p.as_posix(): h for p, h in pins.items()},
               'r105_manifest': f'{R105}:{MANIFEST}', 'layer_dump_sha256': dump_sha,
               'replay_sha256_git_lf': hashlib.sha256(
                   Path(__file__).resolve().read_bytes().replace(b'\r\n', b'\n')).hexdigest()}
    (work / 'receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n', encoding='utf-8',
                                       newline='\n')
    print(json.dumps({k: receipt[k] for k in ('hypothesis', 'status', 'reasons', 'wall_s',
                                              'M109_family_layer_evidence', 'M109B_blender_rows',
                                              'real_source_positive_families')}, ensure_ascii=True))
    return receipt


if __name__ == '__main__':
    main()
