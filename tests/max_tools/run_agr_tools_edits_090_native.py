"""new-case: #979 native smoke of the AGR Tools 0.9.0 RELEASE (branch R) in locked batch Max on DISPOSABLE scenes.

Run via the lab DCC runner; AGR_TEST_OUTPUT must name a NEW directory, AGR_TEST_PACKAGE the built MZP.
Installs the MZP into OUT (no user folders touched), then checks in the real Max Python:
runtime and panel model say 0.9.0, data/ is installed, runtime.EDITS_090 has the 19 plan rows and none answers
`not_implemented` (with nothing selected a preview reports or refuses), the dispatcher refusals, all 19 macroScripts
are registered and run through runtime.ui, then two panel presses (preview, then apply of that preview for an
editing row) go through the same runtime object; refusal texts are recorded, a stub answer fails. The panel model
shows the 0.9 rows (not greyed), the 19 icons are installed, `select_offenders` selects light offenders by anim
handle, the cleanup `options` pass, and the polygon builder builds the committed catalog (bases 0.1-0.9 from the
station fragments). Nothing is saved; the scenes are never written.
(Base-branch version of this smoke: job 20261105-125103-6dc1d28d.)
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
    assert agr.VERSION == '0.9.0' and model.VERSION == agr.VERSION, agr.VERSION
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
        try:
            r = agr.edits_090(tool, 'preview')
        except (ValueError, RuntimeError) as exc:  # nothing selected / no input file: a named refusal
            out[tool] = 'refused: ' + str(exc)[:120]
            continue
        assert agr.parse_report(json.dumps(r)) == r
        assert r['status'] != 'not_implemented', (tool, r['status'])
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
    """Every macroScript is registered and routes to runtime.ui (one press on a synthetic box); then two panel presses
    (preview, then apply of that preview for an editing row) through the SAME runtime object the macros use, so a
    refusal keeps its text. Options-less presses may refuse (no schedule, no legend, no ground): recorded; a stub
    answer fails. A read row never changes the scene."""
    mod = _macro_module()
    box = rt.Box(name='SM_Smoke_979_Main_001', length=2, width=2, height=2)
    out = {}
    for a in ACTS:
        res = []
        rt.select(box)
        path = Path(agr.reports_dir()) / (a.tool + '.json')
        mtime = path.stat().st_mtime_ns if path.is_file() else None
        ran = bool(rt.macros.run('AGR Tools', a.macro))
        # macros.run is false when the press refuses (no legend, no schedule ...): recorded, the presses below show why
        res.append('macro ran={} report={}'.format(ran, path.is_file() and path.stat().st_mtime_ns != mtime))
        mod._edits.pop(a.tool, None)  # the presses below start from a fresh preview
        for press in (1, 2):
            if not rt.isValidNode(box):
                box = rt.Box(name='SM_Smoke_979_Main_001', length=2, width=2, height=2)
            rt.select(box)
            before = sorted(str(n.name) for n in rt.objects)
            try:
                rep = mod.ui(a.tool)
            except Exception as exc:  # noqa: BLE001 - the refusal text is the evidence
                res.append('press{} refused: {}'.format(press, (str(exc).splitlines() or [type(exc).__name__])[0][:160]))
                continue
            assert rep['tool'] == a.tool and rep['status'] != 'not_implemented', (a.macro, rep['status'])
            if a.tool in agr.READ_090:
                assert sorted(str(n.name) for n in rt.objects) == before, a.macro  # read rows change nothing
            plan = rep.get('plan') if isinstance(rep.get('plan'), dict) else {}
            res.append('press{} {}:{}'.format(press, plan.get('mode', '?'), rep['status']))
        out[a.macro] = res
    if rt.isValidNode(box):
        rt.delete(box)
    return out


def panel_model():
    roadmap = agr._load_core('roadmap.py', 'agr_tools_roadmap')
    suite = roadmap.load_file(agr.suite_path())  # the strict load() passes on the shipped plan
    rail = model.rail(suite['blocks'], suite['rows'])
    done = {model.row_of(a.id) for _, d, _ in rail for a in d}
    planned = {r['id'] for _, _, p in rail for r in p}
    assert set(agr.EDITS_090) <= done and not planned & set(agr.EDITS_090)  # released: shown, not greyed
    assert set(agr.EDITS_080) <= done
    assert all(roadmap.vkey(r['version']) > roadmap.vkey('0.9') for _, _, p in rail for r in p)  # 1.0 and 1.x only
    return {'shown_09': len(set(agr.EDITS_090) & done), 'done_rows': len(done), 'planned_rows': len(planned),
            'sections': list(model.SECTIONS[6:])}


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
    """The builder builds the committed catalog of R (bases 0.1-0.9 with the station fragments): 32 new stations."""
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
    assert 'Станция 0.9.9' in text and 'в работе' not in text, text
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
