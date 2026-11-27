"""Pattern: n/a | new-case: the ONE POLY63 stage-2 command: windows + capsules on an accepted body (#1963).

uv run python tools/windows/stage2.py 63A BODY_DUMP.npz CROP.npz STAGE2.json [--keys keys.json] [--band LO HI]
uv run python tools/windows/stage2.py 63B BODY_DUMP.npz CROP.npz STAGE2.json [--band LO HI] [--standard standard.json]
uv run python tools/windows/stage2.py 63C BODY_DUMP.npz CROP.npz opening-types.csv floor.json STAGE2.json
                                      [--standard standard.json]

The body is only read. Shared steps are the 63A stage-2 helpers (jobs/POLY63-A/stage2-1619/hooks/stage2_plan.py:
claim_openings #1714, revit_window, frame_grid, measure_profile, scale_fields, quad_back) and the owner cores
(openings_core, windowgen_core, winplace_core, capsule_core). Tower recognisers are object rules and stay per tower
(hygiene a05: do not glue them by stage name): 63A and 63B keep their job modules, this command routes argv to their
`main`; the 63C route (registry pick from opening-types.csv, outer-jamb frame depth) lives here, moved verbatim from
jobs/POLY63-C/hooks/stage2_63c.py so the accepted 63C v001 plan replays byte-identical.
"""
import csv
import importlib.util
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
HELPERS = ROOT / 'jobs' / 'POLY63-A' / 'stage2-1619' / 'hooks'
TOWERS = {'63A': HELPERS / 'stage2_plan.py', '63B': ROOT / 'jobs' / 'POLY63-B' / 'stage2' / 'hooks' / 'stage2_63b.py'}
STANDARD = ROOT / 'library' / 'windows' / 'standard.json'

OPENINGS = 363  # 63C tower census of the accepted v002 body (tower-specific parameter)


def helpers():
    """The shared 63A stage-2 helpers, imported once as `stage2_plan` (the name 63B imports them by)."""
    if str(HELPERS) not in sys.path:
        sys.path.insert(0, str(HELPERS))
    import stage2_plan
    return stage2_plan


def tower_module(tower):
    """The kept job module of tower 63A or 63B."""
    if tower == '63A':
        return helpers()
    name = Path(TOWERS[tower]).stem
    if name not in sys.modules:
        helpers()
        spec = importlib.util.spec_from_file_location(name, TOWERS[tower])
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
    return sys.modules[name]


def revit_type(name):
    """63C AR export name format: the type label, or None when the Revit family/type is unresolved."""
    label, _, suffix = (name or '').rpartition(' [')
    if re.fullmatch(r'[0-9]+\]', suffix) and re.fullmatch(r'Окн_\S+ .+ Комфорт ОК-[0-9]+-[0-9]+', label):
        return label
    return None


def match_registry(a, ops, reg, modules):
    """63C pick for the shared POLY63 matcher (stage2_plan.claim_openings, #1714): only rows on this sill,
    with the module centre < 0.8 m along the wall and W/H within 2 mm; exactly one row; registry centroid within 2 mm.
    A claimed row must carry a resolved Revit family/type name. Stops before writing on any problem."""
    def pick(o, centre):
        sill = np.asarray(o['border'])[:, 2].min()
        candidates = []
        for k, row in enumerate(reg):
            if abs(float(row['sill_m']) - sill) > .002:
                continue
            w = modules[int(row['module_opening_1based']) - 1]
            delta = w['centre'][:2] - centre[:2]
            if np.linalg.norm(delta) < .8 and abs(w['W'] - o['w']) < .002 and abs(w['H'] - o['h']) < .002:
                candidates.append(k)
        if len(candidates) != 1:
            return None, 'no registry row' if not candidates else 'several registry rows: ' + ', '.join(
                repr(reg[k].get('fbx_model')) for k in candidates)
        k = candidates[0]
        row = reg[k]
        w = modules[int(row['module_opening_1based']) - 1]
        if np.linalg.norm(w['centre'][:2] - [float(row['ref_centroid_x']), float(row['ref_centroid_y'])]) > .002:
            return None, 'registry mismatch {!r}'.format(row.get('fbx_model'))
        return k, (w, row.get('fbx_model'))

    def label(k):
        return 'registry row {} {!r}'.format(k + 1, reg[k].get('fbx_model'))

    def unresolved(k, owners):
        name = reg[k].get('fbx_model')
        if revit_type(name) is None:
            instance = re.fullmatch(r'.* \[([0-9]+)\]', name or '')
            return 'Unresolved Revit family/type: {}, instance {}'.format(
                '; '.join(owners), instance[1] if instance else 'unknown')
        return None
    return a.claim_openings(ops, len(reg), pick, label, unresolved)


def jamb_depth(tri, w):
    """63C frame depth: the continuous outer jamb of the Revit window (the sill flashing projects past the
    frame, so not the overall depth of the window assembly)."""
    adjacency = defaultdict(set)
    for vertices in np.round(tri.astype(float), 5):
        pts = list(map(tuple, vertices))
        for point in pts:
            adjacency[point].update(pts)
    groups = []
    while adjacency:
        todo = [next(iter(adjacency))]
        group = set()
        while todo:
            point = todo.pop()
            if point in group:
                continue
            group.add(point)
            todo.extend(adjacency.pop(point))
        groups.append(group)
    jamb = np.array(list(max(groups, key=len)))
    n = np.array([-w['u'][1], w['u'][0]])
    return round(float(np.ptp(jamb[:, :2] @ n)), 3)


def build_63c(dump, crop, registry, floor, standard, output):
    """63C additive stage 2 on the accepted v002 cut lips (accepted body dump, Revit crop, opening-types.csv,
    floor.json, standard.json, output.json)."""
    a = helpers()
    reg = list(csv.DictReader(Path(registry).open(encoding='utf-8-sig')))
    fl = json.loads(Path(floor).read_text(encoding='utf8'))
    std = a.windowgen_core.load_standard(json.loads(Path(standard).read_text(encoding='utf8')))
    v, f = a.body_mesh(dump)
    ops = a.openings_core.find_openings_report({'verts': v, 'faces': f, 'ref': {'name': 'SM_Body_Main'}})['openings']
    if len(reg) != len(ops) or len(ops) != OPENINGS or any(o['status'] != 'ok' for o in ops):
        raise ValueError('unexpected opening census')
    d = np.load(crop)
    names, ix, tris = list(d['names']), d['obj'], d['tri']
    modules = []
    for name in fl['opening_sources']:
        tri = tris[ix == names.index(name)]
        w = a.revit_window(tri)
        w['depth'] = jamb_depth(tri, w)
        if not 0.02 < w['depth'] < 0.4:
            raise ValueError(('frame depth', name, w['depth']))
        modules.append(w)
    prof = a.measure_profile(modules)
    els, rows, caps = [], [], []
    ordered = sorted(ops, key=lambda o: (round(o['frame']['origin'][2], 2), o['id']))
    matched = []
    for i, (o, _, (w, key)) in enumerate(match_registry(a, ordered, reg, modules), 1):
        bd = np.asarray(o['border'])
        matched.append((i, o, bd, bd[:, 2].min(), w, key))
    names = {i: key for i, _, _, _, _, key in matched}
    types = {i: revit_type(key) for i, key in names.items()}
    if len(set(names.values())) != len(names):
        a.stop(['duplicate registry name'])
    face_keys = ('face_m', 'face_top_m', 'face_bottom_m', 'impost_m')
    for i, o, bd, sill, w, key in matched:
        u = np.array(o['frame']['x'])[:2]
        typ, fd, W, H = types[i], w['depth'], o['w'], o['h']
        fields, _ = a.frame_grid(w, prof['transom_m'], prof['face_top_m'])
        fields = a.scale_fields(fields, w['W'], W, prof['face_m'])
        if np.dot(w['u'], u) < 0:
            fields = [[W - right, z, W - left, h] for left, z, right, h in fields]
        entry = dict(id=typ, role='window', width_m=W, height_m=H, panes_m=fields, source={'occurrences': 1},
                     frame_profile_m={k: prof[k] for k in face_keys} | {'depth_m': fd})
        mesh = a.windowgen_core.build_type(entry, std)
        tr = a.winplace_core.placement_rows(o['frame'], mesh['size_m'], mesh['face_axis'], recess_m=fd / 2)  # [D356]
        for part, col in [('frame', 'Windows'), ('glass', 'Glass')]:
            m = a.windowgen_core.part_mesh(mesh, part)
            verts = [a.winplace_core.apply_rows(tr, p) for p in m['verts']]
            els.append(dict(name=f'SM_Win_{i:03}_{part.capitalize()}', opening=i, collection='Stage2_' + col,
                            verts=verts, faces=m['faces'], mats=[a.MAT_NAMES[j] for j in m['mat_ids']]))
        rim = dict(o, border=(bd - np.array(o['frame']['z']) * fd).tolist(), depth=o['depth'] + fd)
        cap = a.quad_back(a.capsule_core.planar_capsule(rim, a.capsule_core.options(dict(frame_depth_m=fd))))
        chk = a.capsule_core.check_capsule(cap)
        if chk['bad_edges'] or chk['open_off_rim'] or not chk['inward']:
            raise ValueError(('invalid capsule', key))
        for prev, z, other in caps:
            if abs(sill - z) < .01 and (a.capsule_core.mesh_hits(prev, cap, 1e-4)
                                        or a.capsule_core.same_wall_overlap(prev, cap)):
                raise ValueError(('capsules overlap', key, other))
        caps.append((cap, sill, key))
        els.append(dict(name=f'CAPSULE_63C_{i:03}', opening=i, collection='Stage2_Capsules', verts=cap['verts'],
                        faces=cap['faces'], mats=[a.capsule_core.MATERIAL] * len(cap['faces'])))
        rows.append(dict(opening=i, type=typ, source=key, w=W, h=H, reveal_m=o['depth'], frame_depth_m=fd))
    # [D355]: keep the historical v001 report label below for byte-exact replay.
    report = dict(rows=rows, openings={'ok': len(rows)}, capsules={'made': len(caps)},
                  baskets={'count': 0, 'decision': '[D353]'}, types=dict(Counter(r['type'] for r in rows)))
    write_plan(output, report, els)
    print(len(els), report['types'], Counter(r['frame_depth_m'] for r in rows))


def write_plan(output, report, elements):
    """The 63C plan writer: a new path only (open 'x'), {report, elements} as UTF-8 JSON."""
    payload = json.dumps(dict(report=report, elements=elements), ensure_ascii=False)
    with Path(output).open('x', encoding='utf8') as stream:
        stream.write(payload)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] not in ('63A', '63B', '63C'):
        sys.stderr.write(__doc__.split('\n\n')[1] + '\n')
        sys.exit('unknown tower {!r}; expected 63A, 63B or 63C'.format(argv[0] if argv else None))
    tower, rest = argv[0], argv[1:]
    if tower != '63C':
        return tower_module(tower).main(rest)
    import argparse
    ap = argparse.ArgumentParser(prog='stage2.py 63C', description='63C stage 2 on the accepted v002 body')
    for name in ('dump', 'crop', 'registry', 'floor', 'out'):
        ap.add_argument(name)
    ap.add_argument('--standard', default=str(STANDARD))
    args = ap.parse_args(rest)
    build_63c(args.dump, args.crop, args.registry, args.floor, args.standard, args.out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
