"""new-case: native 07/08 regression against hash-pinned Codex scene copies (#2051)."""
import hashlib
import json
import math
import sys
from itertools import combinations
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/blender'))
from ucx_cut_passage import bodies, body_digest, core, read_mesh  # noqa: E402 - Blender path bootstrap

sys.path.insert(0, str(ROOT / 'src'))
from twinqa.geometry import ucx_audit as audit  # noqa: E402 - Blender path bootstrap

# Source vertex / polygon indices, not dimensions inferred from Codex hulls.
CASES = {
    '07': {
        'sha256': 'f253c4c76e0c20103c0bb664e513cd416e51aaad91b0754a06e3fbc806ddb995',
        'frozen': '__UCX_MAIN_OKS', 'walls': [(13, 12), (16, 17)], 'soffit': [6],
        'feet': [(10, 11, 13, 12), (14, 15, 17, 16)], 'top': [10],
        'below_top': {0: 0, 1: 1, 2: 2, 3: 3, 8: 8},
    },
    '08': {
        'sha256': '25e172a63f5e23e6ecbddcf2b3f9b66d05f79a8585f3f0b339e30f11684cedab',
        'frozen': '__UCX_MAIN_OKS_v1', 'walls': [(56, 51), (57, 52)], 'soffit': list(range(27, 32)) + [34],
        'feet': [(48, 49, 50, 51, 56), (52, 53, 54, 55, 57)], 'top': list(range(8)),
        'below_top': dict(enumerate([18, 19, 21, 20, 42, 29, 43, 44, 27, 28, 45, 47, 46, 26, 25, 22, 24, 23])),
    },
}


def derive(obj, case):
    verts, _ = read_mesh(obj)
    faces = [tuple(p.vertices) for p in obj.data.polygons]
    walls = case['walls']
    directions = [core._unit((verts[j][0] - verts[i][0], verts[j][1] - verts[i][1], 0)) for i, j in walls]
    axis = core._unit(tuple(a + b for a, b in zip(*directions)))
    anchor = verts[walls[0][0]][:2] + [0.0]
    depth = [core._dot(axis, core._sub(v, anchor)) for v in verts]
    bounds = [min(depth), max(depth)]
    floor = min(v[2] for v in verts)
    roof_z = [verts[i][2] for f in case['soffit'] for i in faces[f]]
    assert max(roof_z) - min(roof_z) < 0.0001, roof_z
    roof = min(roof_z)
    section = []
    for d in bounds:
        ends = []
        for i, j in walls:
            t = (d - depth[i]) / (depth[j] - depth[i])
            xy = [verts[i][k] + t * (verts[j][k] - verts[i][k]) for k in (0, 1)]
            ends.extend([xy + [floor], xy + [roof]])
        section.append(ends)
    cutter = dict(axis=axis, anchor_m=anchor, depth_m=bounds, floor_m=floor, soffit_m=roof,
                  wall_vertex_ids=walls, sections_m=section)
    cells = []
    # On working arrays only, the bottom circuits supply the floor caps of the two jamb hulls.
    for loop in case['feet']:
        cells.append([verts[i] for i in loop] + [verts[i][:2] + [roof] for i in loop])
    for f in case['top']:
        top = faces[f]
        bottom = [verts[case['below_top'][i]][:2] + [roof] for i in top]
        cells.append([verts[i] for i in top] + bottom)
    assert all(math.isfinite(v) for section_end in section for p in section_end for v in p)
    return cutter, cells


def mesh(handle, points):
    verts, tris = core._hull_core()._convex_hull(points)
    return dict(handle=handle, verts=verts, tris=tris)


def build_spec(tag, path):
    case = CASES[tag]
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    assert digest == case['sha256'], 'UCX_ADD indices refer to a different source revision'
    bpy.ops.wm.open_mainfile(filepath=str(path.resolve()), load_ui=False, use_scripts=False)
    assert bpy.context.scene.unit_settings.scale_length == 1.0
    objects = bpy.context.scene.objects
    cutter, cells = derive(objects['UCX_ADD'], case)
    partitions = {}
    if tag == '07':
        # Same triangulated boundary; split the concave slab along its existing top diagonal (1, 3).
        handle = f'{case["frozen"]}/2480'
        slab = next(r for r in bodies(objects[case['frozen']]) if r['handle'] == handle)
        split = [(1, 3, 7), (1, 7, 5)]
        partitions[handle] = [[slab['tris'][i] for i in (2, 3, 4, 5, 8, 11)] + split,
                              [slab['tris'][i] for i in (0, 1, 6, 7, 9, 10)] + [t[::-1] for t in split]]
    return dict(source_sha256=digest, frozen_objects=[case['frozen']], name_prefix='UCX_SM_Geo_004_Main_',
                exclude_objects=[o.name for o in objects if o.name != case['frozen']], partitions=partitions,
                clearance=mesh('clearance', sum(cutter['sections_m'], [])), derivation=cutter,
                fill=[mesh(f'frame-{i + 1}', points) for i, points in enumerate(cells)])


def geometry(row):
    return row['verts'], row['tris']


def proxy(row):
    try:
        core.piece(*geometry(row))
    except ValueError:
        return dict(row, **{k: v for k, v in core._passage_envelope(row['verts']).items() if k in ('verts', 'tris')})
    return row


def census(frozen, added, clearance):
    """Alternate full-axis SAT on newly loaded geometry; uncertainty uses outer frozen bounds."""
    best, intersections, closest = math.inf, [], None
    indexed = [(row, audit.bounds(row['verts'])) for row in [*frozen, *added]]
    for i, (a, ab) in enumerate(indexed[len(frozen):], len(frozen)):
        for b, bb in indexed[:i]:
            if audit.bbox_gap(ab, bb) > max(0.0, best):
                continue
            gap = audit.sat_separation(geometry(a), geometry(b))
            if gap < best:
                best, closest = gap, [a['handle'], b['handle']]
            if gap < -1e-8:
                intersections.append([a['handle'], b['handle'], gap])
    cb = audit.bounds(clearance['verts'])
    blockers = [row['handle'] for row, bounds in indexed if audit.bbox_gap(cb, bounds) == 0
                and audit.sat_separation(geometry(row), geometry(clearance)) < -1e-8]
    names = {row['handle'] for row in added}
    return dict(bodies=len(indexed), changed_bodies=len(added), min_gap_m=best if math.isfinite(best) else None,
                closest=closest, intersections=intersections, passage_blockers=blockers,
                new_obstructions=[n for n in blockers if n in names])


def display_section(rows, profile):
    """Display-only mid-depth mesh cuts. Acceptance uses the whole 3D clearance instead."""
    axis, origin = profile['axis'], profile['anchor_m']
    lateral = [-axis[1], axis[0], 0.0]
    depth = sum(profile['depth_m']) / 2
    limits = [core._dot(lateral, core._sub(section[i], origin))
              for section in profile['sections_m'] for i in (0, 2)]
    lo, hi = min(limits) - 1.0, max(limits) + 1.0
    zlo, zhi = profile['floor_m'] - 1.0, profile['soffit_m'] + 1.0
    segments = []
    for row in rows:
        points = [core._sub(v, origin) for v in row['verts']]
        distances = [core._dot(axis, p) - depth for p in points]
        if min(distances) >= 0 or max(distances) <= 0:
            continue
        for a, b, c in row['tris']:
            hits = []
            for i, j in ((a, b), (b, c), (c, a)):
                di, dj = distances[i], distances[j]
                if (di < 0) != (dj < 0):
                    t = di / (di - dj)
                    p = [points[i][k] + t * (points[j][k] - points[i][k]) for k in range(3)]
                    hits.append([core._dot(lateral, p), p[2]])
            if (len(hits) == 2 and max(p[0] for p in hits) >= lo and min(p[0] for p in hits) <= hi
                    and max(p[1] for p in hits) >= zlo and min(p[1] for p in hits) <= zhi):
                segments.append(hits)
    return segments


def verify(path, spec_path, out, comparison):
    spec = json.loads(spec_path.read_text(encoding='utf-8'))
    assert spec['source_sha256'] == hashlib.sha256(path.read_bytes()).hexdigest()
    receipt = json.loads(out.with_suffix('.passage.json').read_text(encoding='utf-8')) if out != path else None
    bpy.ops.wm.open_mainfile(filepath=str(path.resolve()), load_ui=False, use_scripts=False)
    source = list(bodies(bpy.context.scene.objects[spec['frozen_objects'][0]]))
    codex = [row for o in bpy.context.scene.objects if o.name.startswith(('UCX_PILOT_', 'UCX_V4_')) for row in bodies(o)]
    frozen = [proxy(row) for row in source]
    for r in source:
        if r['handle'] in spec['partitions']:
            parts = core._passage_partition(dict(r, partition=spec['partitions'][r['handle']]))
            frozen = [p for p in frozen if p['handle'] != r['handle']] + [dict(p, handle=r['handle']) for p in parts]
    clearance = spec['clearance']
    before = census(frozen, codex, clearance)
    before.update(bodies=len(source) + len(codex), tris=sum(len(r['tris']) for r in [*source, *codex]),
                  added_tris=sum(len(r['tris']) for r in codex))
    if receipt is None:
        assert not before['passage_blockers'], f"unchanged Codex set blocks full passage: {before['passage_blockers']}"
        return
    assert receipt['output_sha256'] == hashlib.sha256(out.read_bytes()).hexdigest()
    assert receipt['spec_sha256'] == hashlib.sha256(spec_path.read_bytes()).hexdigest()
    assert sorted(set(before['passage_blockers']) - set(before['new_obstructions'])) == sorted(receipt['replaced'])

    bpy.ops.wm.open_mainfile(filepath=str(out.resolve()), load_ui=False, use_scripts=False)
    objects = bpy.context.scene.objects
    assert not set(spec['exclude_objects']) & set(objects.keys())
    retained = [r for name in spec['frozen_objects'] if name in objects for r in bodies(objects[name])]
    retained_refs = [r for r in source if r['handle'] not in receipt['replaced']]
    assert sorted(map(body_digest, retained)) == sorted(map(body_digest, retained_refs))
    assert receipt['unchanged_sha256'] == {r['handle']: body_digest(r) for r in retained_refs}
    created = []
    for item in receipt['created']:
        row, = bodies(objects[item['name']])
        assert body_digest(row) == item['sha256']
        core.piece(*geometry(row))
        created.append(row)
    after = census([proxy(r) for r in retained], created, clearance)
    after.update(tris=sum(len(r['tris']) for r in [*retained, *created]), added_tris=sum(len(r['tris']) for r in created))
    assert after['tris'] == receipt['tris_after']
    assert not after['passage_blockers'] and not after['new_obstructions'], after
    assert not after['intersections'] and after['min_gap_m'] >= 0.002, after

    good = [r for r in retained_refs if r['handle'] not in receipt['conservative_frozen']]
    bounded = [(r, audit.bounds(r['verts'])) for r in good]
    legacy = [[a['handle'], b['handle'], gap] for (a, ab), (b, bb) in combinations(bounded, 2)
              if audit.bbox_gap(ab, bb) == 0 and (gap := audit.sat_separation(geometry(a), geometry(b))) < -core.TOL_M]
    result = dict(reference=before, candidate=after, inherited_convex_intersections=legacy,
                  inherited_uncertified=receipt['conservative_frozen'], replaced=receipt['replaced'],
                  candidate_sha256=receipt['output_sha256'], source_sha256=receipt['source_sha256'],
                  display_section={label: display_section(rows, spec['derivation']) for label, rows in
                                   [('reference_base', source), ('reference_added', codex),
                                    ('candidate_base', retained), ('candidate_added', created)]})
    with comparison.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
    print(f"PASSAGE_COMPARE {path.name}: {before['bodies']} -> {after['bodies']} bodies, "
          f"{before['tris']} -> {after['tris']} tris, {after['min_gap_m'] * 1000:.3f} mm, "
          f"legacy intersections {len(legacy)}")


def main():
    tag, infile, report, *verification = sys.argv[sys.argv.index('--') + 1:]
    if verification:
        out, comparison = map(Path, verification)
        verify(Path(infile), Path(report), out, comparison)
        return
    spec = build_spec(tag, Path(infile))
    with Path(report).open('x', encoding='utf-8') as f:
        json.dump(spec, f, indent=2)


if __name__ == '__main__':
    main()
