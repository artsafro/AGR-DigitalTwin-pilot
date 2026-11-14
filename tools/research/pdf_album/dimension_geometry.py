"""new-case: vector dimension reconstruction, independently supported scale (#1335).

Research only. A supported paper scale is NOT semantic endpoint identity or a
production calibration. No oracle, model value or nominal printed scale is used.
"""
from __future__ import annotations

import math
from statistics import median


def consensus_scale(seeds):
    """Require three graph-independent source dimensions and strict residuals."""
    parent, selected, ratios = {}, [], []

    def root(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            x = parent[x]
        return x

    for seed in seeds:
        pair = seed['pair']
        if len(pair) != 2 or any(not isinstance(x, str) or not x for x in pair):
            raise ValueError('invalid endpoint pair')
        length, value = seed['length'], seed['value']
        if any(type(x) not in (int, float) or not math.isfinite(x) or x <= 0
               for x in (length, value)):
            raise ValueError('invalid scale evidence')
        ratio = value / length
        if not math.isfinite(ratio) or ratio <= 0:
            raise ValueError('unmeasurable ratio')
        ratios.append(ratio)
        a, b = map(root, pair)
        if a != b:
            parent[a] = b
            selected.append(seed)
    result = dict(status='unknown', mm_per_pt=None, independent=len(selected))
    if len(selected) < 3:
        return dict(result, reason='fewer than three independent dimensions')
    scale = median(ratios)
    if any(not math.isfinite(scale * s['length']) or
           abs(scale * s['length'] - s['value']) >= max(10., .005 * s['value'])
           for s in seeds):
        return dict(result, reason='conflicting dimension scale evidence')
    return dict(result, status='supported', mm_per_pt=scale,
                reason='three or more independent dimensions agree; diagnostic only')


def reconstruct(segments, runs, seeds):
    """Join line/ticks/extensions before value-compatible one-to-one label search.

    Cardinal slash ticks only; unsupported arrows/rotation stay unbound. A
    displaced label additionally needs an actual continuation stroke (leader).
    Source path indices are retained; no wall/axis identity is inferred.
    """
    from dt_ai.album import binding as B, reader as R
    for s in segments:
        if not all(math.isfinite(x) for x in (*s.p0, *s.p1)):
            raise ValueError('non-finite vector geometry')
    for r in runs:
        if not all(math.isfinite(x) for x in (*r.bbox, *r.dir, r.size)) or r.size <= 0:
            raise ValueError('invalid text geometry')
    scale = consensus_scale(seeds)
    spans = []
    for chain in B._chains(segments, runs):
        axis = 0 if chain['orientation'] == 'horizontal' else 1
        c = chain['coord']
        for a, b in zip(chain['ticks'], chain['ticks'][1:]):
            extensions = []
            for end in (a, b):
                hits = [s for s in segments
                        if (B._vert(s) if axis == 0 else B._horiz(s))
                        and max(abs(s.p0[axis]-end), abs(s.p1[axis]-end)) < .5
                        and min(s.p0[1-axis], s.p1[1-axis]) < c
                        < max(s.p0[1-axis], s.p1[1-axis])
                        and abs(s.p1[1-axis]-s.p0[1-axis]) > 2.]
                extensions.append(sorted({s.path for s in hits}))
            if all(extensions):
                p0, p1 = ([a, c], [b, c]) if axis == 0 else ([c, a], [c, b])
                spans.append(dict(axis=axis, a=a, b=b, coord=c,
                                  span=dict(p0=p0, p1=p1), extensions=extensions))
    labels, candidates = [], {}
    for i, run in enumerate(runs):
        value = R.check_dimension_text(run.text)
        if value is None:
            continue
        row = dict(run=i, raw=run.text, bbox=list(run.bbox), value=value,
                   status='unbound', semantic_binding='unbound', credited=False,
                   reason='no unique complete compatible geometry', span=None)
        hits = []
        if scale['status'] == 'supported':
            for k, sp in enumerate(spans):
                axis, c = sp['axis'], sp['coord']
                if abs(run.dir[1-axis]) > 1e-6 or abs(run.dir[axis]) < .99:
                    continue
                u = (run.bbox[axis]+run.bbox[axis+2])/2
                v = (run.bbox[1-axis]+run.bbox[3-axis])/2
                lo, hi = sorted((u, (sp['a']+sp['b'])/2))
                inside = sp['a'] <= u <= sp['b']
                leader = any((B._horiz(s) if axis == 0 else B._vert(s))
                             and max(abs(s.p0[1-axis]-c), abs(s.p1[1-axis]-c)) < .5
                             and min(s.p0[axis], s.p1[axis]) <= lo
                             and max(s.p0[axis], s.p1[axis]) >= hi for s in segments)
                residual = abs((sp['b']-sp['a'])*scale['mm_per_pt']-value)
                if (inside or leader) and abs(v-c) < 4*run.size and residual < max(10., .005*value):
                    distance = math.hypot(max(sp['a']-u, 0, u-sp['b']), v-c)
                    hits.append((distance, k, leader))
        hits.sort()
        # Equal-nearest candidates and two labels claiming one span both refuse.
        if hits and (len(hits) == 1 or hits[1][0]-hits[0][0] > .5):
            candidates[i] = hits[0]
        labels.append(row)
    for row in labels:
        hit = candidates.get(row['run'])
        if hit and sum(h[1] == hit[1] for h in candidates.values()) == 1:
            sp = spans[hit[1]]
            row.update(status='geometry_bound', span=sp['span'],
                       extensions=sp['extensions'], leader=hit[2],
                       reason='paper geometry only; semantic endpoints remain unverified')
    return dict(scale=scale, spans=spans, labels=labels,
                dropped_runs=[dict(run=i, text=r.text, reason='not a positive numeric dimension token')
                              for i, r in enumerate(runs) if R.check_dimension_text(r.text) is None],
                passed=False)


def main(argv=None):
    """Replay frozen inputs; stdout only, no output/temp/report path API."""
    import argparse
    import json
    from copy import deepcopy
    from pathlib import Path
    import pymupdf
    from dt_ai.album import reader as R
    from dt_ai.album.binding import bind_album
    from dt_ai.album.compare import compare, validate
    from tools.research.pdf_album import dimension_autoresearch as E

    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    frozen = {p: p.read_bytes() for p in (E.CORPUS, E.BASELINE)}
    corpus = E.load_corpus(E.CORPUS)
    baseline = json.loads(frozen[E.BASELINE])
    if E.digest(E.canonical(corpus)) != baseline['corpus_sha256']:
        raise ValueError('stale frozen corpus')
    model_path = E.ROOT / 'jobs/KPP1/audit-1304/input-final.json'
    model_bytes = model_path.read_bytes()
    model_bundle = json.loads(model_bytes)
    validate(model_bundle)
    evidence = {}
    for model in model_bundle['models']:
        for observation in model['observations']:
            item = observation['evidence']
            p = Path(item['path'])
            if E.digest(p.read_bytes()) != item['sha256']:
                raise ValueError(f'stale model evidence: {p}')
            evidence[p] = item['sha256']
    sheets = []
    guard = True
    for sheet in corpus['sheets']:
        pdf = sheet['files']['pdf']
        doc = bind_album(pdf['path'], pages=[1])
        before = E.score(doc['values'], sheet['truth'])
        after_doc = deepcopy(doc)
        with pymupdf.open(pdf['path']) as source:
            _, segments, _ = R._primitives(source[0])
            runs = R._text_runs(pymupdf, source[0])
        geometries = []
        for view in doc['views']:
            seeds = []
            for v in doc['values']:
                if v['view'] != view['id'] or v['kind'] != 'dimension':
                    continue
                binding = v['binding']
                if binding['type'] not in ('axis_pair', 'level_pair'):
                    continue
                pair = binding.get('axes', binding.get('levels'))
                seeds.append(dict(pair=[binding['type']+':'+x for x in pair],
                                  length=v['span']['length_pt'], value=v['value']))
            # Partition before scale fitting: no scale shared across viewports.
            box = view['bbox']
            selected = [(i, r) for i, r in enumerate(runs)
                        if box[0] <= (r.bbox[0]+r.bbox[2])/2 <= box[2]
                        and box[1] <= (r.bbox[1]+r.bbox[3])/2 <= box[3]]
            g = reconstruct(segments, [r for _, r in selected], seeds)
            g['scale_evidence'] = seeds
            for row in g['labels']:
                row['run'] = selected[row['run']][0]
            for row in g['dropped_runs']:
                row['run'] = selected[row['run']][0]
            g['view'] = view['id']
            geometries.append(g)
            for row in g['labels']:
                if row['status'] != 'geometry_bound':
                    continue
                matches = [v for v in after_doc['values'] if v['kind'] == 'dimension'
                           and v['bbox'] == row['bbox'] and v['view'] == view['id']]
                if len(matches) != 1 or matches[0]['binding']['type'] != 'unbound':
                    continue
                v = matches[0]
                axis = next(sp['axis'] for sp in g['spans'] if sp['span'] == row['span'])
                want = 'vertical' if axis == 0 else 'horizontal'
                ends = []
                for point in row['span'].values():
                    hits = [a['label'] for a in view['axes'] if a['orientation'] == want
                            and abs(a['position']-point[axis]) < .5]
                    ends.append(hits[0] if len(hits) == 1 else None)
                v['span'] = dict(row['span'], length_pt=abs(row['span']['p1'][axis]-row['span']['p0'][axis]))
                v['orientation'] = 'horizontal' if axis == 0 else 'vertical'
                if all(ends) and ends[0] != ends[1]:
                    v['binding'] = dict(type='axis_pair', axes=ends)
        after = E.score(after_doc['values'], sheet['truth'])
        stable = E.guard_document(after_doc, baseline['signatures'][sheet['name']])
        guard &= stable and E.precision_guard(after['metrics']) != 'fail'
        manual = None
        if sheet['name'] == 'L03':
            unresolved = [v for v in after_doc['values'] if v['kind'] == 'dimension'
                          and v['binding']['type'] == 'unbound' and v['bbox'] is not None
                          and v['value'] is not None and v['value'] > 0]
            bundle = deepcopy(model_bundle)
            bundle['pdf'] = [dict(id=v['id'], category='axis', mark=v['id'],
                facade='L03-plan-unregistered', position_m=None, value=v['value']/1000,
                unit='m', tolerance=.0005, verified=False, calibrated=False,
                evidence=dict(path=pdf['path'], sha256=pdf['sha256'], page=1,
                              sheet='L03', bbox=v['bbox'], method='vector dimension; no model counterpart identity'),
                note='No registered L03 plan endpoint pair in #1304 facade observations; value is not a correspondence key.')
                for v in unresolved]
            if bundle['pdf']:
                manual = compare(bundle)
        sheets.append(dict(sheet=sheet['name'], split=sheet['split'], before=before,
                           after=after, geometry=geometries, model_cross_check=manual,
                           document_guard=stable, precision_guard=E.precision_guard(after['metrics'])))
    E.load_corpus(E.CORPUS)
    if any(p.read_bytes() != data for p, data in frozen.items()) or model_path.read_bytes() != model_bytes:
        raise ValueError('research inputs changed during replay')
    for p, sha in evidence.items():
        if E.digest(p.read_bytes()) != sha:
            raise ValueError(f'model evidence changed during replay: {p}')
    print(json.dumps(dict(schema='dimension-geometry-research/1',
                         corpus_sha256=baseline['corpus_sha256'],
                         model_input_sha256=E.digest(model_bytes), guard=bool(guard),
                         sheets=sheets, passed=False), ensure_ascii=False, allow_nan=False))
    return 0 if guard else 1


if __name__ == '__main__':
    raise SystemExit(main())
