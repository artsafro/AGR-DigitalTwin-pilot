"""new-case: #1729 Max 2026 batch probe of the FBX channel each metallic slot is exported to, and the maps a Max FBX
import connects (3dsmaxbatch only; DISPOSABLE synthetic scene, nothing is saved).

Run: `3dsmaxbatch.exe <wrapper.ms>` where the wrapper is `python.ExecuteFile @"<this file>"`, with
AGR_PROBE_OUTPUT = a NEW folder and optionally AGR_PROBE_IMPORT = FBX files to import (`;`-separated, read only).

Export cases (one plane, a Standard or Physical material, diffuse + roughness + the metallic map on one slot):
    std_specularLevel  Standardmaterial.specularLevelMap   (SLOT_TABLE before #1729)
    std_reflection     Standardmaterial.reflectionMap      (SLOT_TABLE after #1729)
    phys_metalness     PhysicalMaterial.metalness_map
Each FBX is <OUT>/<case>/0001_Probe1729_<case>_Ground.fbx (binary FBX 2014, embedded media). The FBX channels are
read back on the host by agr_tools/fbxmaps_core.py, not here. For every AGR_PROBE_IMPORT file the script resets the
scene, imports it and writes <OUT>/import_<n>.json: every bitmap connected to a scene material (fbxmaps_max) and the
fbxmaps_core readback; for AGR_PROBE_IMPORT files it also applies the reconnect plan, reads back again and
re-exports the scene to <OUT>/reconnected_<n>/. The probe textures are synthetic 4x4 PNGs written under OUT.
"""
import importlib.util
import json
import os
import struct
import zlib
from pathlib import Path

from pymxs import runtime as rt

AGR = Path(__file__).resolve().parents[2] / 'adapters' / 'max' / 'agr_tools'
OUT = Path(os.environ['AGR_PROBE_OUTPUT'])
OUT.mkdir(parents=True, exist_ok=False)
IMPORTS = [p for p in os.environ.get('AGR_PROBE_IMPORT', '').split(';') if p]


def png(path, rgb):
    row = b'\x00' + bytes(rgb) * 4
    raw = zlib.compress(row * 4)

    def chunk(tag, data):
        return struct.pack('>I', len(data)) + tag + data + struct.pack('>I', zlib.crc32(tag + data) & 0xffffffff)
    path.write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 4, 4, 8, 2, 0, 0, 0))
                     + chunk(b'IDAT', raw) + chunk(b'IEND', b''))
    return str(path)


def bitmap(path):
    return rt.Bitmaptexture(fileName=path)


def export_case(case):
    rt.resetMaxFile(rt.Name('noPrompt'))
    folder = OUT / case
    folder.mkdir()
    base = '0001_Probe1729_{}'.format(case.replace('_', ''))
    t = 'T_Probe1729_{}_Ground'.format(case.replace('_', ''))
    d = png(folder / (t + '_d_1.png'), (120, 110, 90))
    r = png(folder / (t + '_r_1.png'), (200, 200, 200))
    m = png(folder / (t + '_m_1.png'), (0, 0, 0))
    plane = rt.Plane(length=1, width=1, lengthsegs=1, widthsegs=1)
    plane.name = 'SM_Probe1729_{}_Ground'.format(case.replace('_', ''))
    rt.convertToPoly(plane)
    name = 'M_Probe1729_{}_Ground_1'.format(case.replace('_', ''))
    if case.startswith('std_'):
        mat = rt.Standardmaterial(name=name)
        mat.diffuseMap = bitmap(d)
        mat.glossinessMap = bitmap(r)
        setattr(mat, 'specularLevelMap' if case == 'std_specularLevel' else 'reflectionMap', bitmap(m))
    else:
        mat = rt.PhysicalMaterial(name=name)
        mat.base_color_map = bitmap(d)
        mat.roughness_map = bitmap(r)
        mat.metalness_map = bitmap(m)
    plane.material = mat
    rt.pluginManager.loadClass(rt.FbxExporter)
    for key, val in (('FileVersion', 'FBX201400'), ('ASCII', False), ('EmbedTextures', True),
                     ('Animation', False), ('Cameras', False), ('Lights', False)):
        rt.FBXExporterSetParam(key, val)
    fbx = str(folder / (base + '_Ground.fbx'))
    rt.select(plane)
    ok = rt.exportFile(fbx, rt.Name('noPrompt'), selectedOnly=True, using=rt.FBXEXP)
    return {'case': case, 'fbx': fbx, 'ok': bool(ok) and os.path.isfile(fbx), 'material_class': str(rt.classOf(mat))}


def _agr(name):
    spec = importlib.util.spec_from_file_location('agr_tools_' + name[:-3] + '_probe1729', AGR / name)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


FC, FM = _agr('fbxmaps_core.py'), _agr('fbxmaps_max.py')


def _export_all(fbx):
    rt.pluginManager.loadClass(rt.FbxExporter)
    for key, val in (('FileVersion', 'FBX201400'), ('ASCII', False), ('EmbedTextures', True),
                     ('Animation', False), ('Cameras', False), ('Lights', False)):
        rt.FBXExporterSetParam(key, val)
    return bool(rt.exportFile(fbx, rt.Name('noPrompt'), using=rt.FBXEXP)) and os.path.isfile(fbx)


def import_case(n, fbx, reconnect):
    """Import -> connected maps -> readback (fbxmaps_core); with `reconnect` also apply the reconnect plan, read the
    scene again and export it to <OUT>/reconnected_<n>/<same name>.fbx (embedded media) for the SINTEZ run."""
    rt.resetMaxFile(rt.Name('noPrompt'))
    rt.pluginManager.loadClass(rt.FbxImporter)
    rt.FBXImporterSetParam('Mode', rt.Name('create'))
    ok = rt.importFile(fbx, rt.Name('noPrompt'), using=rt.FBXIMP)
    doc = {'fbx': fbx, 'ok': bool(ok), 'max': str(rt.maxVersion()), 'connected': FM.connected_maps(rt),
           'material_classes': sorted({str(rt.classOf(m)) for m in rt.sceneMaterials})}
    maps = FC.read_fbx(fbx)
    doc['readback'] = FC.import_readback(maps, doc['connected'])
    if reconnect:
        plan = FC.reconnect_plan(doc['readback']['unconnected'], FM.scene_materials(rt, FC.RECONNECT_SLOT))
        doc['reconnect'] = FM.apply_reconnect(rt, plan, os.path.splitext(fbx)[0] + '.fbm')
        doc['connected_after'] = FM.connected_maps(rt)
        doc['readback_after'] = FC.import_readback(maps, doc['connected_after'])
        out = OUT / 'reconnected_{}'.format(n)
        out.mkdir()
        doc['reexport'] = str(out / os.path.basename(fbx))
        doc['reexport_ok'] = _export_all(doc['reexport'])
    (OUT / 'import_{}.json'.format(n)).write_text(json.dumps(doc, indent=1), encoding='utf-8')
    return {'fbx': fbx, 'ok': doc['ok'], 'connected': len(doc['connected']), 'status': doc['readback']['status'],
            'status_after': doc.get('readback_after', {}).get('status')}


report = {'max': str(rt.maxVersion()), 'exports': [], 'imports': []}
try:
    for c in ('std_specularLevel', 'std_reflection', 'phys_metalness'):
        report['exports'].append(export_case(c))
    # the exported probes are imported back too (Max -> FBX -> Max round trip), then the given files
    probes = [e['fbx'] for e in report['exports'] if e['ok']]
    for i, f in enumerate(probes + IMPORTS):
        report['imports'].append(import_case(i, f, reconnect=f in IMPORTS))
except Exception as exc:  # the report names the failure; batch Max has no Listener
    import traceback
    report['error'] = traceback.format_exc()
(OUT / 'probe.json').write_text(json.dumps(report, indent=1), encoding='utf-8')
