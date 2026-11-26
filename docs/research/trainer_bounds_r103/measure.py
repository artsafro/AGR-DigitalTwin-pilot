"""Pattern: new-case — OBSERVE per-face source reachability of the KPP1 trainer key, not a builder.

For each key face, the smallest distance to a bbox edge of any source entity on the three
bank DWG sheets (L03 plan, L01/L02 facades registered by grid axes). If that distance exceeds
the native 0.10 m bound, no union/selection-of-entities envelope can pass `bounds` on it.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import statistics
import subprocess
import sys
import time

import ezdxf
from ezdxf import bbox

ROOT = Path(__file__).resolve().parents[3]
BASE = 'd9af400c08852308f5f618c9bfc0547e067d82ce'
PRIOR = 'd51167a2acdeda51429a3580eb9dda50cf6990ed'
PRIOR_MANIFEST = 'docs/research/trainer_bounds_r101/manifest.json'
PRIOR_MANIFEST_HASH = '1604102733159f655758099e763aaef624824a0ea4a1b209945f91df51c40595'
L02 = ('G:/Мой диск/AGR-evidence/1855-r103-bounds-reach/l02.dxf',
       'c0176ba9faed16ea30af6f6c08cbd1db003db5a5545eb0913257938da1adbcd3')
BLENDER_HASH = '1e6624af112b3c936f4b038b025ebd2bf00ae72c4b62881a6787166d71c58fa5'
CODE = ('tools/trainer/trainer.py', 'tools/blender/fbx_readback.py')
PHYS = ('A-WALL-', 'A-GLAZ-', 'S-STRS-')            # frozen r101 layer set
SUFFIXES = ('-IDEN', '-TEXT', '-NOTE', '-DIMS')      # frozen r102 E1b filter
FACES = ('x_min', 'y_min', 'z_min', 'x_max', 'y_max', 'z_max')
SPAN = {'X': 27000.0, 'Y': 11000.0}                  # axes 1-4 and А-В (mm)
VIEW_REACH = 5000.0                                 # facade entity centre to its view's axes (mm)
TOL = 0.10
# Review round 1 counterexample (dt-reviewer, comment 10617): registered bboxes of these entities, door leaf included.
SELECTION_S = {'L03': ('1195', '1562', '15E8'), 'L01': ('ADC', '1832'), 'L02': ('13C2',)}
BUDGET_S, MIN_LEFT_S = 300, 60

sys.path.insert(0, str(ROOT))
from tools.trainer import trainer  # noqa: E402


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha_file(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def layer_sets():
    def p(layer):
        return layer.startswith(PHYS) and not layer.endswith(SUFFIXES)

    def a(layer):
        return not layer.endswith(SUFFIXES) and not layer.startswith(('G-', 'S-GRID-'))

    return {'P': p, 'A': a, 'A-door': lambda layer: a(layer) and not layer.startswith('A-DOOR-')}


UNREAD = ('missing_def', 'bbox_error', 'no_extent')  # geometry the DXF could not give us -> inconclusive


def classify(e):
    """('ok', bbox) or (status, None); status in empty_def (inventoried) or UNREAD (blocks a verdict)."""
    block = None
    if e.dxftype() == 'INSERT':  # check the definition first: ezdxf raises on a missing one
        block = e.doc.blocks.get(e.dxf.name) if e.doc is not None else None
        if block is None:
            return 'missing_def', None
    try:
        b = bbox.extents([e], fast=True)
    except Exception:  # noqa: BLE001 - recorded as bbox_error, never silently skipped
        return 'bbox_error', None
    if b.has_data:
        return 'ok', (b.extmin.x, b.extmin.y, b.extmax.x, b.extmax.y)
    if block is not None and len(block) == 0:
        return 'empty_def', None
    return 'no_extent', None


def boxes(entities):
    for e in entities:
        status, b = classify(e)
        if status == 'ok' and b is not None:
            yield e, b


def inventory(entities, keep):
    """Per-status counts on the kept layers; empty definitions listed by block name."""
    counts, empty, unread = {}, {}, []
    for e in entities:
        if not keep(e.dxf.layer):
            continue
        status, _ = classify(e)
        counts[status] = counts.get(status, 0) + 1
        if status == 'empty_def':
            empty[e.dxf.name] = empty.get(e.dxf.name, 0) + 1
        elif status in UNREAD:
            unread.append({'status': status, 'layer': e.dxf.layer, 'type': e.dxftype(),
                           'handle': e.dxf.handle, 'block': getattr(e.dxf, 'name', '')})
    return {'counts': dict(sorted(counts.items())), 'empty_def_blocks': dict(sorted(empty.items())),
            'unread': unread[:20], 'complete': not unread}


def label(text):
    text = re.sub(r'\\U\+([0-9A-Fa-f]{4})', lambda m: chr(int(m.group(1), 16)), text).strip()
    return {'А': 'A', 'В': 'V'}.get(text, text)


def axes(entities, plan):
    """Grid axes as (label, coordinate mm, family) from S-GRID lines and their label MTEXT."""
    lines = [(e, b) for e, b in boxes(entities) if e.dxf.layer.startswith('S-GRID-') and e.dxftype() == 'LINE']
    texts = [(label(e.plain_text()), ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2))
             for e, b in boxes(entities) if e.dxf.layer.startswith('S-GRID-') and e.dxftype() == 'MTEXT']
    out = []
    for e, b in lines:
        vertical = abs(b[2] - b[0]) < 1.0
        ends = [(e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y)]
        name, dist = min(((t, min(((c[0] - x) ** 2 + (c[1] - y) ** 2) ** .5 for x, y in ends)) for t, c in texts),
                         key=lambda r: r[1])
        if dist > 1500:
            continue
        coord = b[0] if vertical else b[1]
        if not plan and not vertical:
            continue
        out.append((name, coord, 'X' if name in ('1', '4') else 'Y', vertical))
    return out


def plan_axes(ax):
    got = {name: coord for name, coord, fam, vertical in ax if name in ('1', '4', 'A', 'V')
           and vertical == (fam == 'X')}
    checks = {'X': round(got['4'] - got['1'], 1), 'Y': round(got['V'] - got['A'], 1)}
    return got, checks


def facade_views(ax):
    """Consecutive axis pairs along the sheet form the four elevations."""
    pts = sorted((c, n, f) for n, c, f, _ in ax if n in ('1', '4', 'A', 'V'))
    views = []
    for i in range(0, len(pts) - 1, 2):
        (c0, n0, f0), (c1, n1, f1) = pts[i], pts[i + 1]
        views.append({'family': f0, 'axes': {n0: c0, n1: c1}, 'span_ok': f0 == f1 and n0 != n1 and
                      abs(abs(c1 - c0) - SPAN[f0]) <= 5.0, 'lo': min(c0, c1), 'hi': max(c0, c1)})
    return views


def world(frame, axis, mm):
    i = 0 if axis == 'x' else 1
    return (mm - frame['origin_mm'][i]) / 1000.0 + frame['frame_shift_m'][i]


def edges(sheet, entities, frame, plan_ax, crop=None, views=None):
    """Yield (entity, {face: world edge}) for every entity that maps onto the key frame."""
    if sheet == 'L03':
        for e, b in boxes(entities):
            if crop and not (b[0] >= crop[0] and b[1] >= crop[1] and b[2] <= crop[2] and b[3] <= crop[3]):
                continue
            yield e, 'plan', {'x_min': world(frame, 'x', b[0]), 'x_max': world(frame, 'x', b[2]),
                              'y_min': world(frame, 'y', b[1]), 'y_max': world(frame, 'y', b[3])}
        return
    views = views or []
    for e, b in boxes(entities):
        mid = (b[0] + b[2]) / 2
        dist, v = min(((max(v['lo'] - mid, mid - v['hi'], 0.0), v) for v in views), key=lambda r: r[0])
        if dist > VIEW_REACH:
            continue
        fam = v['family']
        names = ('1', '4') if fam == 'X' else ('A', 'V')
        f0, f1 = v['axes'][names[0]], v['axes'][names[1]]
        p0, p1 = plan_ax[names[0]], plan_ax[names[1]]
        s = (p1 - p0) / (f1 - f0)
        lo, hi = sorted((p0 + (b[0] - f0) * s, p0 + (b[2] - f0) * s))
        ax = 'x' if fam == 'X' else 'y'
        yield e, f'view-{fam}{"+" if s > 0 else "-"}', {
            f'{ax}_min': world(frame, ax, lo), f'{ax}_max': world(frame, ax, hi),
            'z_min': b[1] / 1000.0, 'z_max': b[3] / 1000.0}


def reach(rows, key, keep):
    best = {}
    for sheet, e, view, ed in rows:
        if not keep(e.dxf.layer):
            continue
        for face, value in ed.items():
            d = value - key[face]  # raw; rounding is for display only, never before a comparison
            if face not in best or abs(d) < best[face]['abs_raw_m']:
                best[face] = {'abs_raw_m': abs(d), 'abs_m': round(abs(d), 4), 'signed_m': round(d, 4),
                              'sheet': sheet, 'view': view, 'layer': e.dxf.layer, 'type': e.dxftype(),
                              'handle': e.dxf.handle, 'block': getattr(e.dxf, 'name', '')[:60]}
    return {f: best.get(f, {'abs_raw_m': None, 'abs_m': None, 'status': 'not_measured'}) for f in FACES}


def decide(union_raw, valid, complete):
    """H103 verdict from raw per-face distances (lists over repeats). 0.10000 reachable, 0.10004 not."""
    if not (valid and complete):
        return 'inconclusive', []
    unreachable = [f for f, v in union_raw.items() if v and all(x is not None and x > TOL for x in v)]
    if unreachable:
        return 'refuted', unreachable
    if all(v and all(x is not None and x <= TOL for x in v) for v in union_raw.values()):
        return 'confirmed (reachable only; no rule, no transfer)', []
    return 'inconclusive', []


def selection_envelope(rows, handles):
    """Envelope of a named selection {sheet: [handle]} as a synthetic readback for trainer.bounds_step."""
    lo, hi, found = {}, {}, set()
    for sheet, e, _view, ed in rows:
        if e.dxf.handle not in handles.get(sheet, ()):
            continue
        found.add((sheet, e.dxf.handle))
        for face, v in ed.items():
            side, store = (min, lo) if face.endswith('_min') else (max, hi)
            store[face] = side(store.get(face, v), v)
    missing = sorted(f'{s}:{h}' for s, hs in handles.items() for h in hs if (s, h) not in found)
    if missing or len(lo) + len(hi) != 6:
        return None, missing
    return {'meshes': [{'bounds_m': [[lo['x_min'], lo['y_min'], lo['z_min']],
                                     [hi['x_max'], hi['y_max'], hi['z_max']]]}]}, missing


def review_checks():
    """Synthetic, source-free rows for review round 1 inputs 2 and 3 (re-run in every repeat)."""
    doc = ezdxf.new()
    msp = doc.modelspace()
    gone = doc.blocks.new('R103_GONE')
    gone.add_line((0, 0), (1000, 0))
    doc.blocks.new('R103_EMPTY')
    msp.add_blockref('R103_GONE', (0, 0), dxfattribs={'layer': 'A-WALL-____-MCUT'})
    msp.add_blockref('R103_EMPTY', (0, 0), dxfattribs={'layer': 'A-WALL-____-MCUT'})
    wall = msp.add_line((0, 0), (1000, 0), dxfattribs={'layer': 'A-WALL-____-MCUT'})
    doc.blocks.delete_block('R103_GONE', safe=False)
    inv = inventory(msp, layer_sets()['P'])
    missing = {'counts': inv['counts'], 'complete': inv['complete'],
               'verdict': decide({f: [0.0] * 3 for f in FACES}, True, inv['complete'])[0]}
    missing['ok'] = (inv['counts'] == {'empty_def': 1, 'missing_def': 1, 'ok': 1} and not inv['complete']
                     and missing['verdict'] == 'inconclusive')
    key = dict.fromkeys(FACES, 0.0)
    boundary = {}
    for dist in (0.10004, 0.10000):
        got = reach([('L03', wall, 'plan', {**key, 'x_min': dist})], key, lambda layer: True)
        raw = {f: [got[f]['abs_raw_m']] * 3 for f in FACES}
        native = trainer.bounds_step({'meshes': [{'bounds_m': [[dist, 0.0, 0.0], [0.0, 0.0, 0.0]]}]},
                                     {'meshes': [{'bounds_m': [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]}]})['status']
        boundary[f'{dist:.5f}'] = {'oracle': decide(raw, True, True)[0], 'native_bounds': native}
    boundary['ok'] = (boundary['0.10004'] == {'oracle': 'refuted', 'native_bounds': 'fail'}
                      and boundary['0.10000']['oracle'].startswith('confirmed')
                      and boundary['0.10000']['native_bounds'] == 'pass')
    return {'missing_def_inconclusive': missing, 'tolerance_boundary_raw': boundary,
            'ok': missing['ok'] and boundary['ok']}


def key_faces(rb):
    lo = [min(m['bounds_m'][0][i] for m in rb['meshes']) for i in range(3)]
    hi = [max(m['bounds_m'][1][i] for m in rb['meshes']) for i in range(3)]
    return dict(zip(FACES, lo + hi))


def load(path):
    return list(ezdxf.readfile(path).modelspace())


def one_repeat(k, out, sheets_src):
    out.mkdir()
    frame = json.loads(Path(k['frame'][0]).read_text(encoding='utf-8'))
    sheets = {name: load(path) for name, path in sheets_src.items()}
    plan_ax, plan_span = plan_axes(axes(sheets['L03'], plan=True))
    reg = {'plan_spans_mm': plan_span, 'plan_ok': all(abs(plan_span[f] - SPAN[f]) <= 5.0 for f in SPAN)}
    for name in ('L01', 'L02'):
        views = facade_views(axes(sheets[name], plan=False))
        reg[name] = [{'family': v['family'], 'axes': v['axes'], 'span_ok': v['span_ok']} for v in views]
    reg['ok'] = reg['plan_ok'] and all(len(reg[n]) == 4 and all(v['span_ok'] for v in reg[n]) for n in ('L01', 'L02'))

    walls = [b for e, b in boxes(sheets['L03']) if e.dxf.layer.startswith('A-WALL-') and not e.dxf.layer.endswith(SUFFIXES)]
    crop = (min(b[0] for b in walls) - 5000, min(b[1] for b in walls) - 5000,
            max(b[2] for b in walls) + 5000, max(b[3] for b in walls) + 5000)

    views = {name: facade_views(axes(sheets[name], plan=False)) for name in ('L01', 'L02')}

    def rows_of(src):
        return [(name, e, view, ed) for name, ents in src.items()
                for e, view, ed in edges(name, ents, frame, plan_ax, crop if name == 'L03' else None,
                                         views.get(name))]

    rows = rows_of(sheets)  # every source edge exists before any key readback

    rb = {}
    for name in ('key', 'rejected'):
        staged = out / f'{name}.fbx'
        shutil.copyfile(k[name][0], staged)
        if sha_file(staged) != k[name][1]:
            raise ValueError(f'staged FBX identity mismatch: {name}')
        rb[name] = trainer.readback(staged, out / f'{name}.json', out)
        if rb[name] is None:
            raise ValueError(f'fresh readback failed: {name}')
    key = key_faces(rb['key'])
    accepted, rejected = trainer.bounds_step(rb['key'], rb['key']), trainer.bounds_step(rb['rejected'], rb['key'])
    calibration = {'accepted_identity': accepted, 'rejected': rejected,
                   'ok': accepted['status'] == 'pass' and rejected['status'] == 'fail'
                   and rejected['max_corner_dev_m'] > accepted['max_corner_dev_m']}

    sets = layer_sets()
    result = {}
    for set_name, keep in sets.items():
        result[set_name] = {sheet: reach([r for r in rows if r[0] == sheet], key, keep) for sheet in sheets}
        result[set_name]['union'] = reach(rows, key, keep)

    # Witnesses: synthetic copies only; the source entities are never modified.
    p = sets['P']
    plan_wall = next(e for e, b in boxes(sheets['L03']) if e.dxftype() == 'LINE' and p(e.dxf.layer)
                     and e.dxf.layer.startswith('A-WALL-'))
    wb = next(b for _, b in boxes([plan_wall]))
    target_mm = (key['x_min'] - frame['frame_shift_m'][0]) * 1000 + frame['origin_mm'][0]
    inj = plan_wall.copy()
    inj.translate(target_mm - wb[0], 0, 0)
    inj_iden = inj.copy()
    inj_iden.dxf.layer = 'A-WALL-TEST-IDEN'
    w_phys = reach(rows + rows_of({'L03': [inj]}), key, p)['x_min']
    w_iden = reach(rows + rows_of({'L03': [inj_iden]}), key, p)['x_min']
    # Facade witness: an L01 glazing entity in an X view, moved so its registered west edge hits the key face.
    l01_rows = [r for r in rows if r[0] == 'L01' and r[2].startswith('view-X') and r[1].dxf.layer.startswith('A-GLAZ-')
                and p(r[1].dxf.layer)]
    _, fe, fview, fed = l01_rows[0]
    s = 1.0 if fview.endswith('+') else -1.0
    fb = next(b for _, b in boxes([fe]))
    finj = fe.copy()
    shift_mm = (key['x_min'] - fed['x_min']) * 1000.0 * s
    finj.translate(shift_mm, 0, 0)
    w_fac = reach([r for r in rows if r[0] == 'L01'] + rows_of({'L01': [finj]}), key, p)['x_min']
    clean = reach([r for r in rows if p(r[1].dxf.layer)], key, p) == result['P']['union']
    witnesses = {'plan_injected_wall': w_phys, 'plan_injected_iden': w_iden, 'facade_injected_glaz': w_fac,
                 'facade_injected_source': {'layer': fe.dxf.layer, 'type': fe.dxftype(), 'view': fview,
                                            'bbox_mm': [round(v, 1) for v in fb]},
                 'clean_refilter_parity': clean,
                 'ok': (w_phys['abs_m'] == 0.0 and w_iden == result['P']['union']['x_min']
                        and w_fac['abs_m'] == 0.0 and clean)}
    sel_rb, sel_missing = selection_envelope(rows, SELECTION_S)
    selection = {'handles': {s: list(h) for s, h in SELECTION_S.items()}, 'missing': sel_missing,
                 'bounds_step': trainer.bounds_step(sel_rb, rb['key']) if sel_rb else
                 {'status': 'not_measured', 'reason': 'selection incomplete'},
                 'envelope_m': sel_rb['meshes'][0]['bounds_m'] if sel_rb else None,
                 'note': 'numerical counterexample to a general no-selection claim; includes the open door leaf'}
    inv = {set_name: {sheet: inventory(ents, keep) for sheet, ents in sheets.items()} for set_name, keep in sets.items()}
    complete = {set_name: all(v['complete'] for v in per.values()) for set_name, per in inv.items()}
    return {'registration': reg, 'calibration': calibration, 'key_faces_m': {f: round(v, 4) for f, v in key.items()},
            'reach': result, 'witnesses': witnesses, 'counts': {s: len(v) for s, v in sheets.items()},
            'inventory': inv, 'complete': complete, 'selection_S': selection, 'review_checks': review_checks()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    started = time.monotonic()
    out = args.out.resolve()
    out.mkdir()
    blob = subprocess.check_output(['git', 'show', f'{PRIOR}:{PRIOR_MANIFEST}'], cwd=ROOT)
    if sha_bytes(blob) != PRIOR_MANIFEST_HASH:
        raise ValueError('r101 manifest hash mismatch')
    k = json.loads(blob)['kpp1']
    pinned = {**{n: k[n] for n in ('l03_dxf', 'l01_dxf', 'frame', 'key', 'rejected')}, 'l02_dxf': list(L02),
              'blender': [trainer._blender(), BLENDER_HASH], 'driver': [str(Path(__file__)), None]}

    def check():
        got = {}
        for name, (path, expected) in pinned.items():
            h = sha_file(path)
            if expected and h != expected:
                raise ValueError(f'input SHA-256 mismatch: {name}')
            got[name] = [Path(path).name if name == 'driver' else path, h]
        code = {}
        for path in CODE:
            ref = sha_bytes(subprocess.check_output(['git', 'show', f'{BASE}:{path}'], cwd=ROOT))
            if sha_bytes((ROOT / path).read_bytes().replace(b'\r\n', b'\n')) != ref:
                raise ValueError(f'code parity broken vs {BASE}: {path}')
            code[path] = ref
        return {'inputs': got, 'code_git_lf': code}

    manifest = check()
    src = {'L03': k['l03_dxf'][0], 'L01': k['l01_dxf'][0], 'L02': L02[0]}
    reps, stop = [], 'complete'
    for i in range(1, 4):
        if BUDGET_S - (time.monotonic() - started) < MIN_LEFT_S:
            stop = 'budget stop'
            break
        t0 = time.monotonic()
        row = one_repeat(k, out / f'rep{i}', src)
        row['wall_s'] = round(time.monotonic() - t0, 3)
        reps.append(row)
    if check() != manifest:
        raise ValueError('input parity changed during the series')
    wall = round(time.monotonic() - started, 3)
    if wall > BUDGET_S:
        stop = 'budget exceeded'
    union = {f: [r['reach']['P']['union'][f]['abs_raw_m'] for r in reps] for f in FACES}
    valid = stop == 'complete' and len(reps) == 3 and all(
        r['registration']['ok'] and r['calibration']['ok'] and r['witnesses']['ok'] and r['review_checks']['ok']
        for r in reps)
    complete_p = bool(reps) and all(r['complete']['P'] for r in reps)
    verdict, unreachable = decide(union, valid, complete_p)
    a_door = {f: [r['reach']['A-door']['union'][f]['abs_raw_m'] for r in reps] for f in FACES}
    summary = {'verdict': verdict, 'scope': 'H103 on frozen layer set P only (union of three DXF sheets)',
               'run_status': stop, 'repeats': len(reps), 'wall_s': wall, 'input_parity': True,
               'P_complete': complete_p,
               'P_union_median_abs_m': {f: round(statistics.median(v), 5) if v and None not in v else None
                                        for f, v in union.items()},
               'unreachable_faces_P': unreachable,
               'A_minus_door_union_median_abs_m': {f: round(statistics.median(v), 5) if v and None not in v else None
                                                   for f, v in a_door.items()},
               'selection_S_bounds': [r['selection_S']['bounds_step'] for r in reps],
               'empty_def_inserts_P': {s: v['counts'].get('empty_def', 0) for s, v in reps[0]['inventory']['P'].items()}
               if reps else None,
               'held_out': 'not measured (no eligible independent etalon)'}
    receipt = {'schema': 'r103-receipt/2', 'base': BASE, 'prior': PRIOR, 'summary': summary,
               'manifest': manifest, 'repeats': reps}
    (out / 'receipt.json').write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + '\n',
                                      encoding='utf-8', newline='\n')
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__':
    main()
