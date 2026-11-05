"""new-case: AGR Tools 0.8.1 owner decisions (#908) native check in locked batch Max on DISPOSABLE synthetic scenes.

1. qa.scene_hygiene `hyg_layer` through the installed MZP (runtime.checks_070): a box on the default layer "0"
   passes, a box on an extra layer fails with the reg p.28 §3.2 text; the scene is not changed by the check.
2. V004 reference FBX written by this Max (FBX exporter, Y-up, FBX 2014): identity box, box turned +90 deg X,
   box turned -28 deg Z. The files are read back outside Max (twinqa.scene.readback + scene_findings, Blender)
   to show which import mode gives the object's own transform on a real Max FBX.

AGR_TEST_OUTPUT must name a NEW directory, AGR_TEST_PACKAGE the built MZP. Files are written only below OUT; the
scene is never saved.
"""
import hashlib
import json
import os
import sys
import traceback
from pathlib import Path

from pymxs import runtime as rt

OUT = Path(os.environ['AGR_TEST_OUTPUT'])
OUT.mkdir(parents=True, exist_ok=False)
PACKAGE = Path(os.environ['AGR_TEST_PACKAGE'])
os.environ['LOCALAPPDATA'] = str(OUT / 'localappdata')
summary = {'max_version': list(rt.maxVersion())[:3], 'package_sha256': hashlib.sha256(PACKAGE.read_bytes()).hexdigest(),
           'checks': {}, 'errors': {}}
assert not rt.maxFileName, 'only an empty batch document is allowed'


def check(name, fn):
    try:
        summary['checks'][name] = fn()
    except Exception:  # noqa: BLE001 - recorded; the run fails at the end
        summary['errors'][name] = traceback.format_exc()[-3000:]


def install():
    rt.execute('global AGRToolsInstallRoot; global AGRToolsStartupRoot')
    rt.AGRToolsInstallRoot = str(OUT / 'installed') + '/'
    rt.AGRToolsStartupRoot = str(OUT / 'startup') + '/'
    rt.makeDir(rt.AGRToolsStartupRoot, all=True)
    rt.fileIn(str(PACKAGE))
    assert rt.execute('global AGRToolsRegistered; AGRToolsRegistered == true'), 'MZP macros not registered'
    sys.path.insert(0, str(OUT / 'installed'))
    import runtime as agr
    return agr


def fresh():
    rt.resetMaxFile(rt.name('noPrompt'))
    rt.units.SystemType = rt.name('meters')
    rt.units.SystemScale = 1.0


def box(name, pos):
    b = rt.Box(name=name, length=2, width=2, height=2, pos=rt.Point3(*pos))
    b.material = rt.Standardmaterial(name='M_X_001_Main_1')
    rt.convertToPoly(b)
    return b


def hygiene_layer():
    fresh()
    box('SM_X_001_Main', (0, 0, 0))
    extra = rt.LayerManager.newLayerFromName('Extra_Layer')
    other = box('SM_X_002_Main', (5, 0, 0))
    extra.addNode(other)
    before = sorted((str(n.name), str(n.layer.name)) for n in rt.objects)
    rt.select(rt.objects)
    rep = agr.checks_070('scene_hygiene', None, False)
    agr.parse_report(json.dumps(rep, allow_nan=False))
    (OUT / 'scene_hygiene.json').write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding='utf-8')
    after = sorted((str(n.name), str(n.layer.name)) for n in rt.objects)
    by_name = {o['name']: o for o in rep['objects']}
    good, bad = by_name['SM_X_001_Main'], by_name['SM_X_002_Main']
    bad_codes = [f['code'] for f in bad['findings']]
    text = next(f.get('detail') or f.get('message') or json.dumps(f, ensure_ascii=False)
                for f in bad['findings'] if f['code'] == 'hyg_layer')
    assert good['findings'] == [], good
    assert bad_codes == ['hyg_layer'], bad_codes
    assert 'Extra_Layer' in json.dumps(bad, ensure_ascii=False) and 'p.28' in json.dumps(bad, ensure_ascii=False)
    assert before == after, 'the check changed the scene'
    return {'status': rep['status'], 'good': [], 'bad': bad_codes, 'text': text}


def export_v004():
    files = {}
    for label, rot in (('identity', None), ('rot_x_plus90', ('x', 90.0)), ('rot_z_minus28', ('z', -28.0))):
        fresh()
        b = box('SM_X_001_Main', (0, 0, 0))
        if rot:
            axis = {'x': rt.Point3(1, 0, 0), 'z': rt.Point3(0, 0, 1)}[rot[0]]
            rt.rotate(b, rt.AngleAxis(rot[1], axis))
        rt.select(b)
        rt.FBXExporterSetParam('ResetExport')
        rt.FBXExporterSetParam('ASCII', False)
        rt.FBXExporterSetParam('FileVersion', 'FBX201400')
        rt.FBXExporterSetParam('UpAxis', 'Y')
        rt.FBXExporterSetParam('Animation', False)
        rt.FBXExporterSetParam('Cameras', False)
        rt.FBXExporterSetParam('Lights', False)
        path = OUT / 'fbx' / ('0101_X_{}.fbx'.format(label))
        path.parent.mkdir(exist_ok=True)
        ok = rt.exportFile(str(path), rt.name('noPrompt'), selectedOnly=True, using=rt.FBXEXP)
        assert ok and path.is_file(), label
        q = b.rotation
        files[label] = {'file': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                        'max_rotation_quat': [q.x, q.y, q.z, q.w]}
    return files


agr = install()
summary['runtime_version'] = agr.VERSION
check('hyg_layer', hygiene_layer)
check('v004_fbx', export_v004)
(OUT / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding='utf-8')
print('AGR_OWNER_NATIVE', json.dumps(summary, ensure_ascii=False)[:4000])
if summary['errors']:
    raise SystemExit(1)
