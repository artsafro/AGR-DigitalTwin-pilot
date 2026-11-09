"""Copy-only #298 output guards. new-case: job-local immutable input boundary."""
from pathlib import Path


def new_output(source, output):
    source = Path(source).resolve(strict=True)
    output = Path(output).resolve()
    if source.is_dir() and output.is_relative_to(source):
        raise ValueError(f'output is within protected source {source}')
    if output == source or output.exists():
        raise ValueError(f'refusing existing/aliased output {output}')
    return output


def remap_rect(uv, src, dst, eps=1e-6):
    """Affine slot remap (u0, v0, u1, v1) -> (u0', v0', u1', v1'); a UV outside its reviewed slot stops."""
    u, v = uv
    if not (src[0] - eps <= u <= src[2] + eps and src[1] - eps <= v <= src[3] + eps):
        raise ValueError(f'uv {uv} outside its reviewed slot {src}')
    return [dst[0] + (u - src[0]) / (src[2] - src[0]) * (dst[2] - dst[0]),
            dst[1] + (v - src[1]) / (src[3] - src[1]) * (dst[3] - dst[1])]


def _rot(p, deg):
    import math
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return (p[0] * c - p[1] * s, p[0] * s + p[1] * c)


def verona_point(shape, plan_rotation_deg, depth, set_id):
    """DWG insert of a generated «Верона» row -> placement point (bbox centre, ccw rotation).

    The generator (tools/library/maf_gen_bench.py) rotates the block centreline by plan_rotation_deg and centres
    the mesh on the bbox of the offset strip; the engine places the local origin at (x, y) rotated by `rotation`.
    """
    import importlib.util
    spec = importlib.util.spec_from_file_location('maf_gen_bench_r', Path(__file__).parents[2] / 'tools/library/maf_gen_bench.py')
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    pts = [_rot(tuple(p), plan_rotation_deg) for p in shape['centreline_block_m']]
    left, right, _ = gen._offsets(pts, depth / 2)
    xs, ys = [p[0] for p in left + right], [p[1] for p in left + right]
    c = ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2)
    ins = shape['inserts_in_568BF'][0]
    theta = (ins['rotation_deg'] - plan_rotation_deg) % 360.0
    off = _rot(c, theta)
    return {'handle': ins['handle'], 'label': set_id, 'x': ins['insert_m'][0] + off[0],
            'y': ins['insert_m'][1] + off[1], 'z': 0.0, 'rotation': theta, 'inside': True,
            'layer': '!_А101_маф', 'position': None, 'container': None, 'ref': ins['handle']}


def verona_points(shapes, build_report, adapter_maf, depth):
    """Adapter MAF points with every «Верона» row insert (inside 568BF) relabelled to its set id at the
    generator pivot; inserts the adapter lacks are added from the plan shapes. -> (points, log)."""
    rows = {str(r['row']): r for r in build_report['rows']}
    derived, log = {}, []
    for key, shape in shapes['rows'].items():
        if shape.get('status') != 'found':
            raise ValueError(f'row {key}: plan shape not found')
        r = rows[key]
        pt = verona_point(shape, r['plan_rotation_deg'], depth, r['set_id'])
        derived[pt['handle']] = pt
    out, seen = [], set()
    for p in adapter_maf:
        h = p.get('handle')
        if h in derived:
            q = dict(derived[h], z=p.get('z', 0.0))
            out.append(q)
            seen.add(h)
            log.append({'handle': h, 'set_id': q['label'], 'old_label': p.get('label'), 'source': 'adapter insert relabelled',
                        'x': q['x'], 'y': q['y'], 'rotation': q['rotation']})
        else:
            out.append(p)
    for h, q in derived.items():
        if h not in seen:
            out.append(q)
            log.append({'handle': h, 'set_id': q['label'], 'old_label': None, 'source': 'plan-shapes insert added',
                        'x': q['x'], 'y': q['y'], 'rotation': q['rotation']})
    return out, log
