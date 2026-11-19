"""Pattern: n/a | new-case: 63C additive stage 2 on the accepted v002 cut lips.

Run with the POLY63-A stage2 helpers from main, accepted body dump, Revit crop,
opening-types.csv, floor.json, standard.json, output.json (in that order).
"""
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

import numpy as np


def registry_types(names):
    """Validate the matched openings against the 63C AR export's name format."""
    types, unresolved = {}, []
    for opening, name in names.items():
        label, _, suffix = (name or '').rpartition(' [')
        instance = re.fullmatch(r'([0-9]+)\]', suffix)
        if not instance or not re.fullmatch(r'Окн_\S+ .+ Комфорт ОК-[0-9]+-[0-9]+', label):
            unresolved.append(f'opening {opening}, instance {instance[1] if instance else "unknown"}')
        else:
            types[opening] = label
    if unresolved:
        raise ValueError('Unresolved Revit family/type: ' + '; '.join(unresolved))
    return types


def build(helper, dump, crop, registry, floor, standard, output):
    sys.path.insert(0, str(Path(helper).resolve()))
    import stage2_plan as a
    reg = list(csv.DictReader(Path(registry).open(encoding='utf-8-sig')))
    fl = json.loads(Path(floor).read_text(encoding='utf8'))
    std = a.windowgen_core.load_standard(json.loads(Path(standard).read_text(encoding='utf8')))
    v, f = a.body_mesh(dump)
    ops = a.openings_core.find_openings_report({'verts': v, 'faces': f, 'ref': {'name': 'SM_Body_Main'}})['openings']
    if len(reg) != len(ops) or len(ops) != 363 or any(o['status'] != 'ok' for o in ops):
        raise ValueError('unexpected opening census')
    d = np.load(crop); names = list(d['names']); ix = d['obj']; tris = d['tri']
    modules = []
    for name in fl['opening_sources']:
        tri = tris[ix == names.index(name)]
        w = a.revit_window(tri)
        # The sill flashing projects past the frame. Measure the continuous outer
        # jamb, not the overall depth of the window assembly.
        from collections import defaultdict
        adjacency = defaultdict(set)
        for vertices in np.round(tri.astype(float), 5):
            pts = list(map(tuple, vertices))
            for point in pts:
                adjacency[point].update(pts)
        groups = []
        while adjacency:
            todo = [next(iter(adjacency))]; group = set()
            while todo:
                point = todo.pop()
                if point in group: continue
                group.add(point); todo.extend(adjacency.pop(point))
            groups.append(group)
        jamb = np.array(list(max(groups, key=len)))
        n = np.array([-w['u'][1], w['u'][0]])
        w['depth'] = round(float(np.ptp(jamb[:, :2] @ n)), 3)
        if not 0.02 < w['depth'] < 0.4: raise ValueError(('frame depth', name, w['depth']))
        modules.append(w)
    prof = a.measure_profile(modules); els = []; rows = []; caps = []
    matched = []
    for i, o in enumerate(sorted(ops, key=lambda o: (round(o['frame']['origin'][2], 2), o['id'])), 1):
        bd = np.asarray(o['border']); sill = bd[:, 2].min(); c = bd.mean(0)
        # Match only on this sill; prove along-wall fit separately from reveal displacement.
        candidates = []
        for row in reg:
            if abs(float(row['sill_m']) - sill) > .002: continue
            w = modules[int(row['module_opening_1based'])-1]
            delta = w['centre'][:2] - c[:2]
            if np.linalg.norm(delta) < .8 and abs(w['W']-o['w']) < .002 and abs(w['H']-o['h']) < .002:
                candidates.append((row, w))
        if len(candidates) != 1: raise ValueError(('unresolved opening', i, candidates))
        row, w = candidates[0]; key = row.get('fbx_model')
        if np.linalg.norm(w['centre'][:2]-[float(row['ref_centroid_x']),float(row['ref_centroid_y'])]) > .002:
            raise ValueError(('registry mismatch', key))
        matched.append((i, o, bd, sill, w, key))
    names = {i: key for i, _, _, _, _, key in matched}
    types = registry_types(names)
    if len(set(names.values())) != len(names):
        raise ValueError('duplicate registry name')
    for i, o, bd, sill, w, key in matched:
        u = np.array(o['frame']['x'])[:2]
        typ = types[i]; fd = w['depth']; W,H = o['w'],o['h']
        fields,_ = a.frame_grid(w,prof['transom_m'],prof['face_top_m']); fields = a.scale_fields(fields,w['W'],W,prof['face_m'])
        if np.dot(w['u'],u)<0: fields = [[W-r,z,W-l,h] for l,z,r,h in fields]
        entry = dict(id=typ,role='window',width_m=W,height_m=H,panes_m=fields,source={'occurrences':1},frame_profile_m={k:prof[k] for k in ('face_m','face_top_m','face_bottom_m','impost_m')} | {'depth_m':fd})
        mesh = a.windowgen_core.build_type(entry,std)
        tr = a.winplace_core.placement_rows(o['frame'],mesh['size_m'],mesh['face_axis'],recess_m=fd/2)  # [D354]
        for part,col in [('frame','Windows'),('glass','Glass')]:
            m = a.windowgen_core.part_mesh(mesh,part); verts = [a.winplace_core.apply_rows(tr,p) for p in m['verts']]
            els.append(dict(name=f'SM_Win_{i:03}_{part.capitalize()}',opening=i,collection='Stage2_'+col,verts=verts,faces=m['faces'],mats=[a.MAT_NAMES[j] for j in m['mat_ids']]))
        cap = a.quad_back(a.capsule_core.planar_capsule(dict(o,border=(bd-np.array(o['frame']['z'])*fd).tolist(),depth=o['depth']+fd),a.capsule_core.options(dict(frame_depth_m=fd))))
        chk=a.capsule_core.check_capsule(cap)
        if chk['bad_edges'] or chk['open_off_rim'] or not chk['inward']: raise ValueError(('invalid capsule', key))
        for prev, z, other in caps:
            if abs(sill-z)<.01 and (a.capsule_core.mesh_hits(prev,cap,1e-4) or a.capsule_core.same_wall_overlap(prev,cap)):
                raise ValueError(('capsules overlap',key,other))
        caps.append((cap,sill,key)); els.append(dict(name=f'CAPSULE_63C_{i:03}',opening=i,collection='Stage2_Capsules',verts=cap['verts'],faces=cap['faces'],mats=[a.capsule_core.MATERIAL]*len(cap['faces'])))
        rows.append(dict(opening=i,type=typ,source=key,w=W,h=H,reveal_m=o['depth'],frame_depth_m=fd))
    report=dict(rows=rows,openings={'ok':len(rows)},capsules={'made':len(caps)},baskets={'count':0,'decision':'[D353]'}, types=dict(Counter(r['type'] for r in rows)))
    Path(output).write_text(json.dumps(dict(report=report,elements=els),ensure_ascii=False),encoding='utf8')
    print(len(els),report['types'],Counter(r['frame_depth_m'] for r in rows))


if __name__ == '__main__':
    build(*sys.argv[1:])
