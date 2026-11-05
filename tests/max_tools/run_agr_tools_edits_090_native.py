"""new-case: #979 native smoke of the AGR Tools 0.9 BASE (branch 0) in locked batch Max on DISPOSABLE synthetic scenes.

Run via the lab DCC runner; AGR_TEST_OUTPUT must name a NEW directory, AGR_TEST_PACKAGE the built MZP.
Installs the MZP into OUT (no user folders touched), then checks in the real Max Python:
the package still says 0.8.x (VERSION moves only in the release branch R), data/ is installed, runtime.EDITS_090
has the 19 plan rows and every stub answers `not_implemented` (#979), the dispatcher refusals, all 19 new
macroScripts are registered and run through runtime.ui (report written, nothing changed in the scene), the panel
model greys the 0.9 rows, the 19 icons are installed, `select_offenders` selects light offenders by anim handle,
the cleanup `options` pass (defaults off, unknown key refused, preview/apply carry them), and finally the polygon
builder builds the committed catalog with the bases 0.8 / 0.9: 32 new station captions, 2 base rectangles and
2 top cameras. Nothing is saved; the scenes are never written.
"""
import hashlib
import json
import os
from pathlib import Path
import sys
import traceback

from pymxs import runtime as rt

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(os.environ['AGR_TEST_OUTPUT'])
OUT.mkdir(parents=True, exist_ok=False)
PACKAGE = Path(os.environ['AGR_TEST_PACKAGE'])
os.environ['LOCALAPPDATA'] = str(OUT / 'localappdata')  # report memory of this smoke only
os.environ['AGR_NO_PROMPT'] = '1'
summary = {'max_version': list(rt.maxVersion())[:3], 'package_sha256': hashlib.sha256(PACKAGE.read_bytes()).hexdigest(),
           'checks': {}, 'errors': {}}
assert not rt.maxFileName, 'only an empty batch document is allowed'


def check(name, fn):
    try:
        summary['checks'][name] = fn()
    except Exception:  # noqa: BLE001 - recorded; the run fails at the end
        summary['errors'][name] = traceback.format_exc()[-2000:]


def install():
    rt.execute('global AGRToolsInstallRoot; global AGRToolsStartupRoot')
    rt.AGRToolsInstallRoot = str(OUT / 'installed') + '/'
    rt.AGRToolsStartupRoot = str(OUT / 'startup') + '/'
    rt.makeDir(rt.AGRToolsStartupRoot, all=True)
    rt.fileIn(str(PACKAGE))
    assert rt.execute('global AGRToolsRegistered; AGRToolsRegistered == true'), 'MZP macros not registered'
    sys.path.insert(0, str(OUT / 'installed'))
    import runtime as agr
    startup = sorted(p.name for p in (OUT / 'startup').glob('AGRTools-*.ms'))
    assert startup == ['AGRTools-{}.ms'.format(agr.VERSION)], startup
    return agr


agr = install()
model = agr._load_core('ui_model.py', 'agr_tools_ui_model')
summary['runtime_version'] = agr.VERSION
ACTS = [a for a in model.ACTIONS if a.tool in agr.EDITS_090]


def package():
    assert agr.VERSION.startswith('0.8.') and model.VERSION == agr.VERSION, agr.VERSION
    data = OUT / 'installed' / 'data'
    got = sorted(p.relative_to(data).as_posix() for p in data.rglob('*') if p.is_file())
    assert {'procedural_classes.json', 'streets/PROVENANCE.md'} <= set(got), got
    assert json.loads((data / 'procedural_classes.json').read_text(encoding='utf-8'))['owner'] == 'C'
    return {'version': agr.VERSION, 'data': got}


def registry():
    assert len(agr.EDITS_090) == 19 and len(ACTS) == 19 and {a.tool for a in ACTS} == set(agr.EDITS_090)
    assert len(agr.READ_090) == 10 and agr.SELECT_090 == ('light.check',)
    rt.clearSelection()
    out = {}
    for tool in agr.EDITS_090:
        r = agr.edits_090(tool, 'preview')
        assert agr.parse_report(json.dumps(r)) == r
        assert r['status'] == 'not_implemented' and r['plan']['issue'] == '#979', (tool, r['status'])
        out[tool] = r['status']
    return out


def refusals():
    out = {}
    for args, word in ((('nope', 'preview'), 'unsupported'), (('place.replace', 'apply'), 'needs the preview'),
                       (('light.check', 'apply', {}), 'read-only'), (('place.replace', 'run'), 'mode'),
                       (('model.triangulate', 'preview'), 'unsupported')):
        try:
            agr.edits_090(*args)
        except ValueError as exc:
            assert word in str(exc), (args, exc)
            out[args[0] + ':' + args[1]] = type(exc).__name__
        else:
            raise AssertionError('accepted ' + repr(args))
    return out


def _macro_module():
    import __main__
    mod = getattr(__main__, 'agr_tools_runtime', None)
    summary['macro_runtime'] = 'bootstrap' if mod is not None else 'fallback: this script import'
    return mod if mod is not None else agr


def macros():
    """Every new macroScript is registered and routes to runtime.ui -> edit_ui -> edits_090: the stub answer is
    written to the report memory, nothing in the scene changes (same nodes, same selection)."""
    mod = _macro_module()
    box = rt.Box(name='SM_Smoke_979_Main_001', length=2, width=2, height=2)
    out = {}
    for a in ACTS:
        rt.select(box)
        before = sorted(str(n.name) for n in rt.objects)
        path = Path(agr.reports_dir()) / (a.tool + '.json')
        mtime = path.stat().st_mtime_ns if path.is_file() else None
        ran = bool(rt.macros.run('AGR Tools', a.macro))
        written = path.is_file() and path.stat().st_mtime_ns != mtime
        rep = mod.ui(a.tool)  # the same press through the runtime object the macros use
        assert ran and written, (a.macro, ran, written)
        assert rep['tool'] == a.tool and rep['status'] == 'not_implemented', (a.macro, rep['status'])
        assert sorted(str(n.name) for n in rt.objects) == before and [str(n.name) for n in rt.selection] == [
            'SM_Smoke_979_Main_001'], a.macro
        assert a.tool not in mod._edits
        out[a.macro] = 'ran, report written, not_implemented'
    rt.delete(box)
    return out


def panel_model():
    roadmap = agr._load_core('roadmap.py', 'agr_tools_roadmap')
    suite = roadmap.load_file(agr.suite_path())  # the strict load() passes on the shipped plan
    rail = model.rail(suite['blocks'], suite['rows'])
    done = {model.row_of(a.id) for _, d, _ in rail for a in d}
    planned = {r['id'] for _, _, p in rail for r in p}
    assert set(agr.EDITS_090) <= planned and not done & set(agr.EDITS_090)  # greyed «в версии 0.9»
    assert set(agr.EDITS_080) <= done
    rows = model.rows(agr.edits_090('qa.normals', 'preview'))
    assert [(r.ok, r.code, r.detail) for r in rows] == [(False, 'not_implemented', 'в работе (#979): модуль ещё пуст')]
    return {'greyed_09': len(set(agr.EDITS_090) & planned), 'sections': list(model.SECTIONS[6:])}


def icons():
    missing = []
    for theme in ('Dark', 'Light'):
        for a in ACTS:
            for size in (24, 30, 36, 48):
                p = OUT / 'installed' / 'icons' / theme / 'AgrIcons' / 'agr_{}_{}.png'.format(a.icon, size)
                if not p.is_file() or not p.read_bytes().startswith(b'\x89PNG'):
                    missing.append(str(p))
    assert not missing, missing[:5]
    return {'icons': len(ACTS), 'pngs_per_theme': 4 * len(ACTS)}


def select_offenders():
    """light.check is a `select` row: the UI glue selects the offenders named by anim handle (the core never does)."""
    far = rt.Omnilight(name='Smoke_979_Omni_far', pos=rt.Point3(0, 0, 3))
    ok = rt.Omnilight(name='Smoke_979_Omni_ok', pos=rt.Point3(9, 0, 3))
    keep = rt.Box(name='Smoke_979_Selected')
    rt.select(keep)
    edit = agr._edit_core()
    report = edit.report('light.check', 'preview', state_hash='smoke', objects=[
        edit.entry(int(rt.getHandleByAnim(far)), 'Smoke_979_Omni_far', [edit.finding('omni_distance', detail='syn')]),
        edit.entry(int(rt.getHandleByAnim(ok)), 'Smoke_979_Omni_ok')])
    n = agr.select_offenders(report)
    picked = [str(x.name) for x in rt.selection]
    assert n == 1 and picked == ['Smoke_979_Omni_far'], picked
    rt.select(keep)
    clean = edit.report('light.check', 'preview', state_hash='smoke', objects=[
        edit.entry(int(rt.getHandleByAnim(ok)), 'Smoke_979_Omni_ok')])
    assert agr.select_offenders(clean) == 0 and [str(x.name) for x in rt.selection] == ['Smoke_979_Selected']
    rt.delete([far, ok, keep])
    return {'selected': picked, 'no_offender_keeps_selection': True}


def cleanup_options():
    box = rt.Box(name='SM_Smoke_979_Clean_Main', length=2, width=2, height=2)
    box.mapcoords = True
    rt.convertToPoly(box)
    rt.setUserPropBuffer(box, 'MapChannel:1 = UV\r\n')
    p = agr.cleanup_preview([box])
    assert p['options'] == {'channels': False, 'keys': False} and len(p['channels']) == 1, p['options']
    on = agr.cleanup_preview([box], {'channels': True})
    assert on['options'] == {'channels': True, 'keys': False} and on['report'] == p['report']
    try:
        agr.cleanup_preview([box], {'delete_everything': True})
    except ValueError as exc:
        refused = str(exc)
    else:
        raise AssertionError('unknown cleanup option accepted')
    before = sorted(str(n.name) for n in rt.objects)
    tampered = dict(on, channels=[[7]])
    try:
        agr.cleanup_apply([box], tampered)
    except ValueError as exc:
        stale = 'stale' in str(exc)
    else:
        raise AssertionError('tampered preview accepted')
    copies, after = agr.cleanup_apply([box], on)  # apply re-plans with the options recorded in the preview
    assert after['status'] == 'pass' and all('_AGR_export_' in str(c.name) for c in copies)
    rt.delete(list(copies) + [box])
    return {'default': p['options'], 'refused': refused[:80], 'apply_copies': len(copies), 'tampered_stale': stale,
            'objects_before_apply': len(before)}


def polygon():
    """The builder builds the committed catalog (bases 0.1-0.9; branch 0 has no fragment yet): 32 new stations."""
    sys.path.insert(0, str(ROOT / 'test-polygon' / 'build'))
    sys.path.insert(0, str(ROOT / 'test-polygon'))
    import polygon_core as core
    import build_scene
    catalog = build_scene.catalog_objects()
    made = build_scene.build('polygon_all', texture_dir=str(OUT / 'textures'))
    names = {str(n.name) for n in rt.objects}
    want = [o['name'] for o in catalog if o['scene'] == 'polygon_all']
    missing = sorted(set(want) - names)
    assert not missing, missing[:10]
    new = [s for s in core.stations() if s['version'] in ('0.8', '0.9')]
    labels = ['_label_' + s['id'].replace('.', '_') for s in new]
    assert len(new) == 32 and all(rt.getNodeByName(x) is not None for x in labels), labels
    for x in ('_base_0_8', '_base_0_9', '_cam_База 0.8', '_cam_База 0.9'):
        assert rt.getNodeByName(x) is not None, x
    text = str(rt.getNodeByName('_label_0_9_9').text)
    assert 'Станция 0.9.9' in text and 'причина в README' in text, text
    layer = rt.LayerManager.getLayerFromName('_labels')
    return {'stations_new': len(new), 'nodes_built': len(made), 'catalog_polygon_all': len(want),
            'label_0_9_9': text.replace('\r\n', ' | ')[:160], 'labels_layer': layer is not None}


for name, fn in (('package', package), ('registry', registry), ('refusals', refusals), ('macros', macros),
                 ('panel_model', panel_model), ('icons', icons), ('select_offenders', select_offenders),
                 ('cleanup_options', cleanup_options), ('polygon', polygon)):
    check(name, fn)
summary['scene_saved'] = bool(str(rt.maxFileName))
(OUT / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding='utf-8')
print('AGR_979_SUMMARY ' + json.dumps(summary, ensure_ascii=True)[:3000])
assert not summary['errors'] and not summary['scene_saved'], sorted(summary['errors'])
