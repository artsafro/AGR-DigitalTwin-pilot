"""new-case: OBSERVE loop for the master mesh quality score (#1616) - proposes and logs, never retains.

  uv run python tools/qa/mesh_quality_observe.py SRC.blend RUN_DIR [--angles 80,60,45,30]

Round 0 measures the source; each next round runs the candidate hook
``tools/blender/split_welded_parts_candidate.py`` with one parameter on a copy, measures it with
tools/qa/mesh_quality_score.py (same zones) and KEEPS it as the incumbent only if the score
improves. Every round is appended to RUN_DIR/observe-log.jsonl with what it WOULD change in the
skeleton (a body-stage ``after`` hook, docs/agents/SKELETONS.md); nothing is written to the
skeleton, the job or the source. Retaining a change is a normal PR + review (OBSERVE rule).

Skeleton stage ``mesh-quality`` (#1739, end of ``body`` in oks-vpm / oks-npm, observe week):

  uv run python tools/qa/mesh_quality_observe.py stage MASTER.(blend|fbx|obj|json) --out NEW/mesh_quality.json
         [--cell-m 3.0] [--param key=value ...] [--blender EXE]

writes ONE report: the unchanged #1616 score (tools/qa/mesh_quality_score.py defaults) plus the local
per-facade-cell defect signal that #1724 (standing #13) listed as "would change": irregular / sliver / n-gon faces
(and triangles in a quad master) counted per facade cell (side by the dominant horizontal normal, cell_m x cell_m
along the facade and in height), so a corner defect is not averaged away by the whole-body area share. It only
RECORDS: there is no threshold, no return and no refusal path (``returns_work`` is always false; a ``fail`` status
still exits 0). Turning on return mode is Artem's decision after the observe week (#1739, out of scope).
Errors (unreadable or non-finite geometry, an output that aliases the input or exists) exit 2 and write nothing.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'tools' / 'qa'))
import mesh_quality_score as mqs  # noqa: E402  (report: docs/research/mesh-quality-1616/REPORT.md)

CORNERS = [[-17.5, -8.2, -12.5, -3.2], [-17.5, 3.5, -12.5, 8.5]]   # KPP1 SW / NW corner posts (#1563 sheet)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# ---------------------------------------------------------------- skeleton stage `mesh-quality` (#1739)

STAGE_SCHEMA = 'agr.mesh_quality_stage/1'
STAGE_KEYS = ('schema', 'stage', 'mode', 'returns_work', 'input', 'score', 'status', 'components', 'dropped',
              'cells', 'signal')
CELL_KEYS = ('cell_m', 'triangulated_input', 'measured_faces', 'facade_faces', 'non_facade_faces',
             'degenerate_faces', 'defect_faces', 'facade_defect_faces', 'non_facade_defect_faces',
             'max_cell_defect_faces', 'max_cell_defect_area_m2', 'cells_with_defects', 'worst', 'dropped',
             'thresholds')
FACADE_MAX_NZ = 0.5      # |n_z| below this: a facade face (wall); above: roof / floor / soffit
WORST_N = 10


def _finite_pos(v, what):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0:
        raise ValueError(f'{what} must be a finite positive number, got {v!r}')
    return float(v)


def _faces_of(obj):
    name = obj.get('name') if isinstance(obj, dict) else None
    if not isinstance(name, str) or not isinstance(obj.get('verts'), list) or not isinstance(obj.get('faces'), list):
        raise ValueError(f'object {name!r}: needs name, verts and faces lists')
    verts = obj['verts']
    for v in verts:
        if not (isinstance(v, (list, tuple)) and len(v) == 3 and all(
                isinstance(c, (int, float)) and not isinstance(c, bool) for c in v)):
            raise ValueError(f'object {name}: bad vertex {v!r}')
        if not all(math.isfinite(c) for c in v):
            raise ValueError(f'object {name}: non-finite vertex coordinate {v!r}')
    out = []
    for fi, f in enumerate(obj['faces']):
        if not isinstance(f, (list, tuple)) or len(f) < 3:
            raise ValueError(f'object {name}: face {fi} has fewer than 3 corners')
        for i in f:
            if isinstance(i, bool) or not isinstance(i, int) or not 0 <= i < len(verts):
                raise ValueError(f'object {name}: face {fi} vertex index {i!r} out of range')
        out.append([verts[i] for i in f])
    return name, out


def cell_defects(objects, params=None, cell_m=3.0):
    """Per-facade-cell defect counts (pure). Thresholds are the #1616 core defaults (``irregular_deg``,
    ``tri_min_angle_deg``, ``quad_min_angle_deg``); every measured face ends in a facade cell, the non-facade
    bucket or the degenerate (zero-area) bucket; collision hulls are dropped with the reason."""
    core = mqs.load_core()
    cell = _finite_pos(cell_m, 'cell_m')
    p = core._params(params)
    eps = core.ANGLE_EPS_DEG
    if not isinstance(objects, list):
        raise ValueError('objects must be a list')
    rows, dropped = [], []
    for obj in objects:
        name, faces = _faces_of(obj)
        if name.startswith(p['collision_prefix']):
            dropped.append({'name': name, 'reason': 'collision hull (' + p['collision_prefix'] + ')'})
            continue
        rows.extend(faces)
    if not rows:
        raise ValueError('no measured faces (empty master or collision hulls only)')
    triangulated = sum(1 for f in rows if len(f) == 3) > 0.5 * len(rows)
    cells = {}
    acc = {'facade_faces': 0, 'non_facade_faces': 0, 'degenerate_faces': 0, 'facade_defect_faces': 0,
           'non_facade_defect_faces': 0, 'degenerate_defect_faces': 0}
    for fp in rows:
        k = len(fp)
        n = core._newell(fp)
        ln = core._norm(n)
        ang = core._angles(fp)
        if ln == 0:
            acc['degenerate_faces'] += 1
            acc['degenerate_defect_faces'] += 1          # a zero-area face is always a defect
            continue
        irregular = max(abs(x - 90.0) for x in ang) > p['irregular_deg'] + eps
        if k == 3:
            defect = min(ang) < p['tri_min_angle_deg'] - eps or (irregular and not triangulated)
        elif k == 4:
            defect = irregular or min(ang) < p['quad_min_angle_deg'] - eps
        else:
            defect = True                                # n-gon: an error in the score too
        c = [sum(q[i] for q in fp) / k for i in range(3)]
        if abs(n[2]) / ln >= FACADE_MAX_NZ:
            acc['non_facade_faces'] += 1
            acc['non_facade_defect_faces'] += defect
            continue
        acc['facade_faces'] += 1
        acc['facade_defect_faces'] += defect
        if abs(n[0]) >= abs(n[1]):
            side, u = ('+X' if n[0] > 0 else '-X'), c[1]
        else:
            side, u = ('+Y' if n[1] > 0 else '-Y'), c[0]
        key = (side, math.floor(u / cell), math.floor(c[2] / cell))
        row = cells.setdefault(key, {'side': key[0], 'u': key[1], 'z': key[2], 'faces': 0, 'defect_faces': 0,
                                     'defect_area_m2': 0.0})
        row['faces'] += 1
        if defect:
            row['defect_faces'] += 1
            row['defect_area_m2'] += ln / 2.0
    for row in cells.values():
        row['defect_area_m2'] = round(row['defect_area_m2'], 6)
    bad = sorted((r for r in cells.values() if r['defect_faces']),
                 key=lambda r: (-r['defect_faces'], -r['defect_area_m2'], r['side'], r['u'], r['z']))
    measured = acc['facade_faces'] + acc['non_facade_faces'] + acc['degenerate_faces']
    if measured != len(rows):
        raise ValueError(f'face accounting broken: {measured} != {len(rows)}')
    return {'cell_m': cell, 'triangulated_input': triangulated, 'measured_faces': measured,
            'facade_faces': acc['facade_faces'], 'non_facade_faces': acc['non_facade_faces'],
            'degenerate_faces': acc['degenerate_faces'],
            'defect_faces': acc['facade_defect_faces'] + acc['non_facade_defect_faces'] + acc['degenerate_defect_faces'],
            'facade_defect_faces': acc['facade_defect_faces'], 'non_facade_defect_faces': acc['non_facade_defect_faces'],
            'max_cell_defect_faces': bad[0]['defect_faces'] if bad else 0,
            'max_cell_defect_area_m2': max((r['defect_area_m2'] for r in bad), default=0.0),
            'cells_with_defects': len(bad), 'worst': [dict(r) for r in bad[:WORST_N]], 'dropped': dropped,
            'thresholds': {'irregular_deg': p['irregular_deg'], 'tri_min_angle_deg': p['tri_min_angle_deg'],
                           'quad_min_angle_deg': p['quad_min_angle_deg'], 'facade_max_nz': FACADE_MAX_NZ},
            'cells_all': sorted(cells.values(), key=lambda r: (r['side'], r['u'], r['z']))}


def cell_label(row):
    return f"{row['side']} u{row['u']} z{row['z']}"


def signal_line(score, status, cells):
    w = cells['worst'][0] if cells['worst'] else None
    worst = (f"worst cell {cell_label(w)}: {w['defect_faces']} defect faces of {w['faces']} "
             f"({w['defect_area_m2']:.2f} m2)") if w else 'worst cell none'
    return (f"score {score:.2f} ({status}); {worst}; {cells['cells_with_defects']} cells with defects, "
            f"{cells['defect_faces']}/{cells['measured_faces']} defect faces")


def validate_stage_report(doc):
    """Fail-closed check of mesh_quality.json: observe only, never returns work."""
    if not isinstance(doc, dict) or set(doc) != set(STAGE_KEYS):
        raise ValueError(f'mesh_quality report keys {sorted(doc) if isinstance(doc, dict) else doc!r} '
                         f'!= {sorted(STAGE_KEYS)}')
    if doc['schema'] != STAGE_SCHEMA or doc['stage'] != 'mesh-quality':
        raise ValueError(f"mesh_quality report schema {doc['schema']!r} / stage {doc['stage']!r}")
    if doc['mode'] != 'observe' or doc['returns_work'] is not False:
        raise ValueError('mesh_quality is observe only: mode must be observe and returns_work false (#1739)')
    s = doc['score']
    if isinstance(s, bool) or not isinstance(s, (int, float)) or not math.isfinite(s) or not 0 <= s <= 100:
        raise ValueError(f'mesh_quality score must be a finite number 0-100, got {s!r}')
    if doc['status'] not in ('measured', 'fail'):
        raise ValueError(f"mesh_quality status {doc['status']!r}")
    cells = doc['cells']
    if not isinstance(cells, dict) or set(cells) != set(CELL_KEYS) or not isinstance(cells['worst'], list):
        raise ValueError('mesh_quality cells block is incomplete')
    if not isinstance(doc['input'], dict) or not doc['input'].get('sha256'):
        raise ValueError('mesh_quality input provenance missing')
    return doc


def stage(source, out, cell_m=3.0, params=None, blender=None):
    src, out = Path(source).resolve(), Path(out).resolve()
    if src == out or (out.exists() and src.exists() and src.samefile(out)):
        raise ValueError('report aliases input')
    if out.exists() or Path(str(out) + '.partial').exists():
        raise ValueError(f'report {out} exists; use a new versioned path')
    if not out.parent.is_dir():
        raise ValueError(f'output folder {out.parent} does not exist')
    _finite_pos(cell_m, 'cell_m')
    got = {}
    with tempfile.TemporaryDirectory(prefix='mq-stage-', dir=out.parent) as td:
        rep = mqs.run(src, Path(td) / 'score.json', params=params, blender=blender,
                      on_dump=lambda objs: got.__setitem__('cells', cell_defects(objs, params, cell_m)))
    cells = got['cells']
    cells.pop('cells_all')
    doc = {'schema': STAGE_SCHEMA, 'stage': 'mesh-quality', 'mode': 'observe', 'returns_work': False,
           'input': rep['input'], 'score': rep['score'], 'status': rep['status'], 'components': rep['components'],
           'dropped': rep['dropped'], 'cells': cells, 'signal': signal_line(rep['score'], rep['status'], cells)}
    validate_stage_report(doc)
    if out.exists() or Path(str(out) + '.partial').exists():         # state may have changed during the measure
        raise ValueError(f'report {out} appeared during the measure; not overwritten')
    tmp = Path(str(out) + '.partial')
    try:
        with open(tmp, 'x', encoding='utf-8') as fh:
            fh.write(json.dumps(doc, ensure_ascii=False, allow_nan=False, indent=1))
        os.replace(tmp, out)
    finally:
        if tmp.exists():
            tmp.unlink()
    return doc


def stage_main(argv):
    ap = argparse.ArgumentParser(prog='mesh_quality_observe.py stage',
                                 description='skeleton stage mesh-quality (#1739): record only, never returns work')
    ap.add_argument('master')
    ap.add_argument('--out', required=True)
    ap.add_argument('--cell-m', type=float, default=3.0)
    ap.add_argument('--param', action='append', default=[], help='key=value core parameter')
    ap.add_argument('--blender', default=None)
    a = ap.parse_args(argv)
    try:
        doc = stage(a.master, a.out, a.cell_m, dict(mqs.parse_param(x) for x in a.param) or None, a.blender)
    except (ValueError, OSError, RuntimeError) as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 2
    print('Mesh quality (observe): ' + doc['signal'])
    return 0


def main(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    if argv[:1] == ['stage']:
        return stage_main(argv[1:])
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('src')
    ap.add_argument('run_dir')
    ap.add_argument('--angles', default='80,60,45,30')
    ap.add_argument('--blender', default=None)
    a = ap.parse_args(argv)
    src, run = Path(a.src).resolve(), Path(a.run_dir).resolve()
    if run.exists():
        raise SystemExit('run dir exists; use a new one: ' + str(run))
    if run == src.parent or src.parent in run.parents:
        raise SystemExit('run dir inside the source directory')
    run.mkdir(parents=True)
    before = sha(src)
    from dt_ai.core.blender_runner import blender_command
    log = run / 'observe-log.jsonl'
    base = mqs.run(src, run / 'round-00-score.json', zones=CORNERS, blender=a.blender)
    best = {'round': 0, 'score': base['score'], 'master': str(src)}
    rows = [{'round': 0, 'candidate': 'baseline (no hook)', 'score': base['score'], 'components': base['components'],
             'kept': True, 'master': str(src), 'master_sha256': before}]
    for i, angle in enumerate([float(x) for x in a.angles.split(',')], start=1):
        out = run / f'round-{i:02d}'
        cmd = blender_command(ROOT / 'tools' / 'blender' / 'split_welded_parts_candidate.py',
                              (src, out, repr(angle)), executable=a.blender)
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
        fbx = out / 'master.fbx'
        if proc.returncode != 0 or not fbx.is_file():
            rows.append({'round': i, 'candidate': f'split_welded_parts angle={angle}', 'error': proc.stderr[-400:],
                         'kept': False})
            continue
        rep = mqs.run(fbx, run / f'round-{i:02d}-score.json', zones=CORNERS, blender=a.blender)
        kept = rep['score'] > best['score']
        if kept:
            best = {'round': i, 'score': rep['score'], 'master': str(fbx)}
        rows.append({'round': i, 'candidate': f'split_welded_parts angle={angle}', 'score': rep['score'],
                     'delta_vs_baseline': round(rep['score'] - base['score'], 3), 'components': rep['components'],
                     'hook': json.loads((out / 'hook.json').read_text(encoding='utf-8'))['split_edges'],
                     'kept': kept, 'master': str(fbx), 'master_sha256': sha(fbx),
                     'would_change': ('skeletons.json jobs/KPP1 hooks += {"script": "hooks/split_welded_parts.py", '
                                      f'"stage": "body", "point": "after"}} with angle_deg={angle}')})
    if sha(src) != before:
        raise SystemExit('source changed during the loop')
    with log.open('x', encoding='utf-8') as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + '\n')
    (run / 'incumbent.json').write_text(json.dumps(best, indent=2), encoding='utf-8')
    for r in rows:
        print(r['round'], r['candidate'], r.get('score'), 'KEEP' if r['kept'] else 'discard')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
