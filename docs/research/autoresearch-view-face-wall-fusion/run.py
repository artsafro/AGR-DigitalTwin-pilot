"""H168, an OBSERVE-only paired native readback of two elevation cues.

new-case: docs/research/autoresearch-view-face-wall-fusion/run.py - H168 wall-ID fusion experiment
"""

import hashlib
import importlib.metadata
import json
import statistics
import subprocess
import sys
import time
import types
from pathlib import Path
from typing import Any

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
R167 = 'b59d6e2213fff0d6f89f97e9140dd2965019f4ee'
R149 = 'ef84ca410559a5bf7417d7e8803a841e022c5b98'
PINS = {
    '167/run.py': 'ee621f3d5c4835914343b06c2c87aa2891dde6b0b3d6e31c594fcdc07692d124',
    '167/params.json': 'dc8ab77bb8feef9cb0476df66d33dea631042808c4a40db667ae6d743aeaa85a',
    '167/blender_elv.py': '1fed14287f753b3441aff4afa49ba421f546978358432f95d7efc19135057fce',
    '149/run.py': 'a6ac3463f33b3daaaed7ad259994ddbc13be3b7d8dad130d616f0eec45de60dd',
    '149/score.py': '4a125268b8c495f15680efe9e8ecf34ae1733de1354403f32f5887d140e2ed24',
    '149/rays_type.py': 'c24e6d0abd84f0d5bf707831739ee4da259bc4f4acdeb4e5a791464c983ce422',
}
BASELINE = '04f67ea689a0cb763bd9df3b01e7b38cd1b9dd65b4555ff1441e072db7948921'
BUDGET_S = 2100


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False).encode('utf-8')


def git(*args):
    return subprocess.check_output(['git', *args], cwd=REPO)


def pin(key):
    rev, folder = (R167, 'elvwall') if key.startswith('167/') else (R149, 'material')
    data = git('show', f'{rev}:docs/research/autoresearch-view-face-{folder}/{key.split("/")[1]}')
    if sha(data) != PINS[key]:
        raise ValueError(f'Wrong bytes: {key}')
    return data


def module(name, file, source) -> Any:
    mod = types.ModuleType(name)
    mod.__file__ = str(file)
    exec(compile(source, name, 'exec'), mod.__dict__)
    return mod


def stage(out):
    staged = out / 'stage'
    staged.mkdir(parents=True)
    m167 = module('r167', HERE / 'r167.py', pin('167/run.py'))
    m167.HERE = staged
    (staged / 'params.json').write_bytes(pin('167/params.json'))
    ray_source = pin('149/rays_type.py')
    type_source = ray_source[ray_source.index(b'SUFFIX ='):ray_source.index(b'verts, tris, tri_lab, types =')]
    tail = (HERE / 'label_tail.py').read_bytes()
    call = b'\nwall_type_maps(sc, dg, walls, hidden, P, type_name, outdir)\n'
    (staged / 'blender_elv.py').write_bytes(pin('167/blender_elv.py') + b'\n\n' + type_source + tail + call)
    score = module('score', HERE / 'r149_score.py', pin('149/score.py'))
    source = pin('149/run.py').replace(b'import score as S  # noqa: E402', b'')
    fill = module('r149', HERE / 'r149.py', source)
    fill.S = score
    return m167, m167.load(), fill, score


def fuse(glass, finish):
    if glass is None:
        return finish, 'finish_only' if finish is not None else 'neither'
    if finish is None:
        return glass, 'glass_only'
    return (glass, 'agree') if glass == finish else (None, 'conflict')


def inject(state, glass, finish):
    if state == 'blank':
        g, d = np.zeros_like(glass), np.zeros_like(finish)
    elif state == 'mirror':
        g, d = glass[:, ::-1], finish[:, ::-1]
    elif state == 'clean':
        g, d = glass, finish
    else:
        raise ValueError(state)
    return g, d, {'glass': int(np.count_nonzero(g != glass)), 'finish': int(np.count_nonzero(d != finish))}


def compact(labels):
    keys = np.unique(np.append(labels, 0))
    return np.searchsorted(keys, labels).astype(np.int32)


def drawing_labels(page, view, fixture, m145, fill):
    scale = m145.scale_pt_per_m(page, view)
    segments = m145.segments(page, view['box_pt'], scale)
    grid = fixture['res_m']
    image = m145.raster_view(segments, grid)
    occupied = np.where(image.any(0), image.argmax(0), image.shape[0])
    span = np.flatnonzero((image.shape[0] - occupied) * grid >= fixture['decision']['tall_m'])
    x0, x1 = (int(span[0]), int(span[-1]) + 1) if len(span) else (0, image.shape[1])
    xs, ys = segments[:, [0, 2]], segments[:, [1, 3]]
    hn = int(np.ceil(np.ptp(ys) / fill.RES)) + 1
    wn = int(np.ceil(np.ptp(xs) / fill.RES)) + 1
    labels, _ = fill.view_labels(page, view['box_pt'], scale, xs.min(), -ys.max(), wn, hn)
    first = round(x0 * grid / fill.RES)
    width = max(1, round((x1 - x0) * grid / fill.RES))
    rows = np.flatnonzero(image[:, x0:x1].any(axis=1))
    top = round(int(rows[0]) * grid / fill.RES) if len(rows) else 0
    return labels[top:, first:first + width]


def outcome(answer, sides, truth):
    return 'abstain' if answer is None else 'correct' if sides[answer] == truth else 'wrong'


def compare(out, base, ctx, fill, score):
    import pymupdf

    m145, fx = ctx[5:7]
    sides = {row['id']: row['az'] for row in base['walls']}
    rows = []
    with np.load(out / 'wall_types.npz', allow_pickle=False) as archive:
        if set(archive.files) != sides.keys():
            raise ValueError('Wall-ID mismatch between the two native channels')
        maps = {wall: compact(archive[wall]) for wall in sorted(sides)}
    slack = round(fx['decision']['width_slack_m'] / fill.RES)
    with pymupdf.open(fx['inputs']['pdf']['path']) as doc:
        for prior in base['rows']:
            name = prior['view']
            view = fx['views'][name]
            truth = prior['gt_az']
            clean = drawing_labels(doc[view['page'] - 1], view, fx, m145, fill)
            row: dict[str, Any] = dict(name=name, kind=view['kind'], truth=truth,
                                       filled_cells=int(np.count_nonzero(clean)))
            for state in ('clean', 'blank', 'mirror'):
                old = prior['states'][state]
                _, labels, changed = inject(state, np.empty((0, 0)), clean)
                changed['glass'] = old['changed_cells']
                scores = {wall: round(float(score.face_score(labels, arr, slack)), 9)
                          for wall, arr in maps.items()}
                a = old['answers']['C166']
                d = score.decide(scores)
                f, route = fuse(a, d)
                if score.decide(dict(reversed(list(scores.items())))) != d:
                    raise ValueError(f'Finish candidate-order parity: {name} {state}')
                row[state] = dict(a=a, d=d, f=f, route=route, changed=changed,
                                  a_outcome=outcome(a, sides, truth), d_outcome=outcome(d, sides, truth),
                                  f_outcome=outcome(f, sides, truth), scores=scores,
                                  exercised=state == 'clean' or any(changed.values()))
            rows.append(row)
    return {'rows': rows, 'map_hits': {key: int(np.count_nonzero(val)) for key, val in maps.items()}}


def verdict(rows):
    by_name = {row['name']: row for row in rows}
    clean = [row['clean'] for row in rows]
    opaque = by_name['p19 A-I']['clean']
    control = by_name['p18 I-A']['clean']
    negative = by_name['p19 10-1']['mirror']
    return {
        'full_coverage': sum(row['kind'] == 'full' and row['clean']['f_outcome'] == 'correct' for row in rows) >= 4,
        'retained': all(c['a'] == c['f'] for c in clean if c['a_outcome'] == 'correct'),
        'clean_safety': all(c['f_outcome'] != 'wrong' for c in clean),
        'blanks': all(row['blank']['f'] is None for row in rows),
        'mirror_safety': all(m['f_outcome'] != 'wrong' for row in rows if any((m := row['mirror'])['changed'].values())),
        'positive_witness': opaque['route'] == 'finish_only' and opaque['f_outcome'] == 'correct',
        'retention_control': control['a_outcome'] == 'correct' and control['f'] == control['a'],
        'negative_witness': any(negative['changed'].values()) and negative['f_outcome'] != 'wrong',
    }


def tally(rows):
    return {state: {group: {arm: {result: sum((row['kind'] == 'full') == (group == 'full')
                                               and row[state]['exercised'] and row[state][f'{arm}_outcome'] == result
                                               for row in rows)
                                  for result in ('correct', 'wrong', 'abstain')} for arm in ('a', 'd', 'f')}
                    for group in ('full', 'fragments')} for state in ('clean', 'blank', 'mirror')}


def main(out):
    lock = (REPO / 'uv.lock').read_bytes()
    components = {p.resolve().relative_to(REPO).as_posix(): sha(p.read_bytes())
                  for p in (Path(__file__), HERE / 'label_tail.py')}
    if sha(lock) != sha(git('show', f'{R149}:uv.lock')) or any(sha(git('show', f'HEAD:{p}')) != h
                                                              for p, h in components.items()):
        raise ValueError('Lock or measured script bytes differ from the pinned Git revision')
    out.mkdir(parents=True, exist_ok=False)
    start = time.monotonic()
    m167, ctx, fill, score = stage(out)
    fx = ctx[6]
    native = dict((role, m167.sha_file(row['path'])) for role, row in fx['inputs'].items())
    native['blender'] = m167.sha_file(ctx[1].BLENDER)
    expected = {key: row['sha256'] for key, row in fx['inputs'].items()} | {'blender': m167.BLENDER_SHA}
    if native != expected:
        raise ValueError('Pinned native inputs mismatch')
    receipt: dict[str, Any] = dict(schema='wall-fusion/1', measured_head=git('rev-parse', 'HEAD').decode().strip(),
                   pins=PINS, nested_pins={key: val[2] for key, val in m167.BLOBS.items()}, scripts=components,
                   lock_sha256=sha(lock), native=native,
                   runtime={'python': sys.version.split()[0], **{p: importlib.metadata.version(p)
                              for p in ('numpy', 'pymupdf', 'Pillow')}}, pairs=[], status='running')
    status = 'finished'
    for i in range(3):
        pair = out / f'pair-{i + 1}'
        begin = time.monotonic()
        base, timing = m167.one_run(ctx, pair)
        digest_a = sha(canonical(base))
        if digest_a != BASELINE:
            (pair / 'unexpected_a.json').write_bytes(canonical(base))
            raise ValueError(f'Baseline parity failure: {digest_a}')
        body = compare(pair, base, ctx, fill, score)
        payload = canonical(body)
        (pair / 'body.json').write_bytes(payload)
        wall = time.monotonic() - begin
        receipt['pairs'].append(dict(a_sha256=digest_a, fusion_sha256=sha(payload), baseline_stage_s=timing, wall_s=wall))
        print(f'pair {i + 1}: {wall:.3f} s, baseline parity OK, fusion {sha(payload)}', flush=True)
        remaining = 2 - i
        elapsed = time.monotonic() - start
        if elapsed + receipt['pairs'][0]['wall_s'] * 1.15 * remaining > BUDGET_S:
            status = 'budget_stop'
            break
    head_after = git('rev-parse', 'HEAD').decode().strip()
    if head_after != receipt['measured_head'] or any(m167.sha_file(row['path']) != native[role]
                                                     for role, row in fx['inputs'].items()) or (
            m167.sha_file(ctx[1].BLENDER) != native['blender']):
        raise ValueError('Postflight provenance drift')
    elapsed = time.monotonic() - start
    if elapsed > BUDGET_S:
        status = 'budget_stop'
    if len({p['fusion_sha256'] for p in receipt['pairs']}) != 1:
        status = 'parity_failure'
    body = json.loads((out / 'pair-1' / 'body.json').read_bytes())
    checks = verdict(body['rows'])
    walls = [pair['wall_s'] for pair in receipt['pairs']]
    receipt.update(status=status, result=('confirmed' if all(checks.values()) else 'refuted')
                   if status == 'finished' else 'inconclusive',
                   med_s=statistics.median(walls), spread_s=max(walls) - min(walls), elapsed_s=elapsed,
                   native_unchanged=True, counts=tally(body['rows']), checks=checks, **body)
    (out / 'receipt.json').write_bytes(canonical(receipt))
    print(json.dumps({key: receipt[key] for key in ('status', 'result', 'med_s', 'spread_s', 'checks', 'counts')}, indent=1))


if __name__ == '__main__':
    main(Path(sys.argv[1]).resolve())
