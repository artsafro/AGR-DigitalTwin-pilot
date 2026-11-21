"""new-case: bring A101 MAF archives to the library contract where the geometry/material side is off (#1024).

AGR Lab runner, Max 2024, on archive COPIES (job inputs); the Drive originals are never written.
  AGR_OUT   output folder: fixed/<name>/ (all archive members, .max and FBX replaced) + fixes.json
  AGR_ZIPS  ';' list of runner copies of the archives to fix
Rules (owner 07.11 "bring every MAF to one template"; assets_library.MAF_CONTRACT):
  * pivot XY more than 50 mm off the bbox centre -> bbox centre (Z kept);
  * pivot more than 400 mm above the base AND above mid-height (not ground level) -> base + 200 mm (usual footing);
  * material not named M_<name>_<version> while its maps belong to this asset -> renamed.
The pivot moves without moving the geometry, then the node moves back so the pivot keeps its old place in the file
layout. The .max is saved as 3ds Max 2022 (the sources' version); <name>_high/_low.fbx are exported like the
sources (m, Y up, FBX 2014, triangulated, media embedded) with the pivot at the origin. Read back: the saved .max
is reopened and measured, each FBX is imported into an empty scene and measured.
"""
import json
import os
from pathlib import Path
import sys
import traceback
import zipfile

from pymxs import runtime as rt

OUT = Path(os.environ['AGR_OUT'])
OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'adapters/max/agr_tools'))
import assets_max as amx  # noqa: E402

XY_TOL_MM, FOOTING_MM = 50.0, 200.0


def mm_per_unit():
    return amx.m_per_unit() * 1000.0


def measure(node, k):
    lo, hi, piv = amx._box([node], k)
    return {'tris': int(rt.snapshotAsMesh(node).numfaces),
            'bbox_mm': [round(hi[i] - lo[i], 1) for i in range(3)],
            'above_base_mm': round(piv[2] - lo[2], 1),
            'offset_xy_mm': [round(piv[0] - (lo[0] + hi[0]) / 2, 1), round(piv[1] - (lo[1] + hi[1]) / 2, 1)],
            'material': None if node.material is None else str(node.material.name),
            'pivot_mm': [round(p, 1) for p in piv]}


def fbx_params():
    rt.pluginManager.loadClass(rt.FBXEXP)
    for key, val in (('Animation', False), ('Cameras', False), ('Lights', False), ('Triangulate', True),
                     ('SmoothingGroups', True), ('EmbedTextures', True), ('ConvertUnit', 'm'), ('UpAxis', 'Y'),
                     ('FileVersion', 'FBX201400'), ('GenerateLog', False)):
        rt.FBXExporterSetParam(key, val)


def fix_archive(zpath):
    name = Path(zpath).stem
    dest = OUT / 'fixed' / name
    dest.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(zpath) as zf:
        zf.extractall(dest)
    max_path = dest / (name + '.max')
    rt.resetMaxFile(rt.Name('noPrompt'))
    rt.loadMaxFile(str(max_path), quiet=True, useFileUnits=True)
    k = mm_per_unit()
    rec = {'name': name, 'units_mm_per_unit': k, 'before': {}, 'after': {}, 'fixes': [], 'fbx': {}}
    nodes = {v: rt.getNodeByName(name + '_' + v) for v in ('high', 'low')}
    for v, n in nodes.items():
        if n is None:
            raise ValueError('no object ' + name + '_' + v)
        b = rec['before'][v] = measure(n, k)
        lo, hi, piv = amx._box([n], 1.0)  # file units
        new = list(piv)
        cx, cy = (lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2
        if max(abs(x) for x in b['offset_xy_mm']) > XY_TOL_MM:
            new[0], new[1] = cx, cy
            rec['fixes'].append('{}: pivot XY -> bbox centre (was {} mm)'.format(v, b['offset_xy_mm']))
        if b['above_base_mm'] > 400.0 and b['above_base_mm'] > 0.5 * b['bbox_mm'][2]:
            new[2] = lo[2] + FOOTING_MM / k
            rec['fixes'].append('{}: pivot Z -> base + {:.0f} mm (was {} mm above the base)'.format(
                v, FOOTING_MM, b['above_base_mm']))
        if new != list(piv):
            old = rt.Point3(*piv)
            target = rt.Point3(*new)
            n.pivot = target                 # geometry stays where it is
            n.pos = n.pos - (target - old)   # pivot back to its old place in the file layout
        want = 'M_{}_{}'.format(name, v)
        if n.material is not None and str(n.material.name).lower() != want.lower():
            maps = [str(m.filename) for m in amx.node_bitmaps([n])]
            if all(name.lower() in os.path.basename(p).lower() for p in maps):
                rec['fixes'].append('{}: material {} -> {}'.format(v, n.material.name, want))
                n.material.name = want
            else:
                rec['fixes'].append('{}: material {} kept (shared maps of another asset)'.format(v, n.material.name))
    if not rec['fixes']:
        return rec
    rt.saveMaxFile(str(max_path), saveAsVersion=2022, quiet=True)
    fbx_params()
    for v, n in nodes.items():
        keep = rt.Point3(n.pos.x, n.pos.y, n.pos.z)
        n.pos = rt.Point3(0, 0, 0)
        rt.select(n)
        out = dest / '{}_{}.fbx'.format(name, v)
        ok = rt.exportFile(str(out), rt.Name('noPrompt'), selectedOnly=True, using=rt.FBXEXP)
        n.pos = keep
        rec['fbx'][v] = {'exported': bool(ok), 'bytes': out.stat().st_size if out.exists() else 0}
    # read back: the saved .max ...
    rt.resetMaxFile(rt.Name('noPrompt'))
    rt.loadMaxFile(str(max_path), quiet=True, useFileUnits=True)
    k2 = mm_per_unit()
    for v in ('high', 'low'):
        rec['after'][v] = measure(rt.getNodeByName(name + '_' + v), k2)
    # ... and each FBX in an empty millimetre scene
    for v in ('high', 'low'):
        rt.resetMaxFile(rt.Name('noPrompt'))
        rt.units.SystemType = rt.Name('millimeters')
        rt.units.SystemScale = 1.0
        nodes_f = amx._import_fbx(str(dest / '{}_{}.fbx'.format(name, v)))
        geo = [g for g in nodes_f if rt.superclassof(g) == rt.GeometryClass]
        rec['fbx'][v]['readback'] = measure(geo[0], mm_per_unit()) if geo else None
        rec['fbx'][v]['objects'] = [str(g.name) for g in geo]
    return rec


results, errors = [], {}
for z in [p for p in os.environ['AGR_ZIPS'].split(';') if p]:
    try:
        results.append(fix_archive(z))
    except Exception:  # noqa: BLE001 - one archive must not stop the others
        errors[Path(z).stem] = traceback.format_exc()[-1500:]
(OUT / 'fixes.json').write_text(json.dumps({'results': results, 'errors': errors}, ensure_ascii=False, indent=1),
                                encoding='utf-8')
if errors:
    raise RuntimeError('fix errors: ' + ', '.join(errors))
