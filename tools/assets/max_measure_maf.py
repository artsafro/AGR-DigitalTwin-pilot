"""new-case: measure MAF archives that ship without a sidecar (#1024), AGR Lab runner, Max 2024, archive COPIES.

  AGR_OUT    output folder (measured.json + the throwaway project/cache);
  AGR_ZIPS   ';' list of runner copies of the archives.
Each archive is imported with assets_max.run_import into a fresh metre scene (both versions) and measured in the
shape of the A101 sidecar (schema 3 subset) with `measured: true`: geometry per version (object names/count, tris,
bbox mm, pivot above base / XY offset / inside, transform), materials, textures (file, slot by name, resolution).
Nothing is written into the archives; assets_library.audit_maf reads the result like a sidecar.
"""
import json
import os
from pathlib import Path
import shutil
import sys

from pymxs import runtime as rt

OUT = Path(os.environ['AGR_OUT'])
OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'adapters/max/agr_tools'))
import assets_max as amx  # noqa: E402

core = amx.core
tex = amx._sibling('assets_textures')
SLOT = {'diffuse': 'base_color', 'normal': 'bump', 'erm': 'metalness', 'opacity': 'opacity'}
lib = OUT / 'lib'
lib.mkdir(exist_ok=True)
for z in [p for p in os.environ['AGR_ZIPS'].split(';') if p]:
    shutil.copyfile(z, lib / Path(z).name)
idx = core.scan_maf(str(lib), str(OUT / 'cache'), lib='maf')
result, errors = {}, {}
for a in idx['assets']:
    rt.resetMaxFile(rt.Name('noPrompt'))
    rt.units.SystemType = rt.Name('meters')
    rt.units.SystemScale = 1.0
    try:
        rep = amx.run_import(idx, [a['id']], {'project_dir': str(OUT / 'project'), 'cache_dir': str(OUT / 'cache'),
                                             'row_limit_m': 1000.0}, str(OUT / 'cache'), scene_label='measure')
        if rep['status'] != 'done':
            raise RuntimeError(rep['errors'])
        meta = {'schema': 'measured-1', 'measured': True, 'name': a['name'], 'units': 'mm', 'up_axis': 'Z',
                'versions': {}, 'geometry': {}, 'materials': {}, 'textures': {}, 'polycount': {}}
        for v in ('high', 'low'):
            nodes = [o for o in rt.objects if str(rt.getUserProp(o, core.PROP_VER)) == v]
            meta['versions'][v] = bool(nodes)
            if not nodes:
                continue
            tris = sum(int(rt.snapshotAsMesh(n).numfaces) for n in nodes)
            lo, hi, piv = amx._box(nodes, 1000.0 * amx.m_per_unit())  # millimetres
            n0 = nodes[0]
            sc = [float(n0.scale.x), float(n0.scale.y), float(n0.scale.z)]
            q = n0.rotation
            meta['geometry'][v] = {
                'object_names': [str(n.name) for n in nodes], 'object_count': len(nodes), 'tris': tris,
                'bbox': {'x': round(hi[0] - lo[0], 1), 'y': round(hi[1] - lo[1], 1), 'z': round(hi[2] - lo[2], 1)},
                'pivot': {'above_bbox_base_mm': round(piv[2] - lo[2], 1),
                          'offset_x_mm': round(piv[0] - (lo[0] + hi[0]) / 2, 1),
                          'offset_y_mm': round(piv[1] - (lo[1] + hi[1]) / 2, 1),
                          'inside_bbox': all(lo[i] - 0.5 <= piv[i] <= hi[i] + 0.5 for i in range(3))},
                'transform': {'scale': [round(s, 4) for s in sc], 'has_negative_scale': sc[0] * sc[1] * sc[2] < 0,
                              'rotation_deg': [0.0, 0.0, 0.0] if abs(abs(float(q.w)) - 1) < 1e-6 else
                              ['non-identity', round(float(q.w), 6)]}}
            meta['polycount'][v] = tris
            mats = {}
            for n in nodes:
                if n.material is not None:
                    mats[str(n.material.name)] = str(rt.classof(n.material))
            meta['materials'][v] = [{'name': k, 'class': c} for k, c in sorted(mats.items())]
            files = sorted({str(m.filename) for m in amx.node_bitmaps(nodes)})
            meta['textures'][v] = [{'file': os.path.basename(f), 'slot': SLOT.get(tex.role_of(f), 'other'),
                                    'resolution': amx.png_size(f)} for f in files]
        result[a['name']] = meta
    except Exception as exc:  # noqa: BLE001 - one archive must not stop the others
        errors[a['name']] = '{}: {}'.format(type(exc).__name__, exc)[:800]
(OUT / 'measured.json').write_text(json.dumps({'measured': result, 'errors': errors}, ensure_ascii=False, indent=1),
                                   encoding='utf-8')
if errors:
    raise RuntimeError('measure errors: ' + ', '.join(errors))
