"""new-case: #908 native smoke of the AGR Tools 0.8.0 release in locked batch Max on a DISPOSABLE synthetic scene.

Run via the lab DCC runner; AGR_TEST_OUTPUT must name a NEW directory, AGR_TEST_PACKAGE the built MZP.
Installs the MZP into OUT (no user folders touched), then checks in the real Max Python:
runtime 0.8.0, runtime.EDITS_080 and the dispatcher refusals, none of the 13 tools answers `not_implemented`
any more, every new macroScript runs twice (preview press, apply press) on a synthetic box, the panel model
(0.8 actions shown, not greyed), the shipped icons, and the edit_max helpers on a throwaway box: export copy on
its own layer, one undo record, selection restored, before/after snapshot of the original, and an error inside
the run leaves `edit_max.session` (pymxs.undo swallowed it, #908 branch C). The per-button acceptance is in the
geom/tex/names/package runners. Nothing is saved; the scene is never written.
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
os.environ['AGR_NO_PROMPT'] = '1'  # no ±0.000 prompt in batch Max
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
ACTS = [a for a in model.ACTIONS if a.section == model.SECTIONS.index('Сдача (копии)')]


def registry():
    """Released: every row has its glue function; with nothing selected a preview reports or refuses, never stubs."""
    assert agr.VERSION == '0.8.0' and model.VERSION == '0.8.0'
    assert len(agr.EDITS_080) == 13 and len(ACTS) == 13 and {a.tool for a in ACTS} == set(agr.EDITS_080)
    rt.clearSelection()
    out = {}
    for tool in sorted(agr.EDITS_080):
        try:
            r = agr.edits_080(tool, 'preview')
        except (ValueError, RuntimeError) as exc:
            out[tool] = 'refused: ' + str(exc)[:120]
            continue
        assert r['status'] != 'not_implemented' and agr.parse_report(json.dumps(r)) == r, (tool, r['status'])
        out[tool] = r['status']
    return out


def refusals():
    out = {}
    for args, word in ((('nope', 'preview'), 'unsupported'), (('model.triangulate', 'apply'), 'needs the preview'),
                       (('qa.package', 'apply', {}), 'read-only'), (('model.triangulate', 'run'), 'mode')):
        try:
            agr.edits_080(*args)
        except ValueError as exc:
            assert word in str(exc), (args, exc)
            out[args[0] + ':' + args[1]] = type(exc).__name__
        else:
            raise AssertionError('accepted ' + repr(args))
    return out


def macros():
    """Every new macroScript runs through runtime.ui -> edit_ui -> edits_080 twice on a synthetic box (first press
    preview, second press apply of that preview for editing rows). Options-less runs may refuse (no folder, no
    address): the refusal is recorded; a stub answer is a failure."""
    box = rt.Box(name='SM_Smoke_908_Main_001', length=2, width=2, height=2)
    out = {}
    for a in ACTS:
        res = []
        for press in (1, 2):
            if not rt.isValidNode(box):
                box = rt.Box(name='SM_Smoke_908_Main_001', length=2, width=2, height=2)
            rt.select(box)
            path = Path(agr.reports_dir()) / (a.tool + '.json')
            mtime = path.stat().st_mtime_ns if path.is_file() else None
            try:
                ok = bool(rt.macros.run('AGR Tools', a.macro))
            except Exception as exc:  # noqa: BLE001 - a refusal propagates through the macro seam
                res.append('refused: ' + (str(exc).splitlines() or [type(exc).__name__])[0][:120])
                continue
            if path.is_file() and path.stat().st_mtime_ns != mtime:
                rep = json.loads(path.read_text(encoding='utf-8'))
                assert rep['tool'] == a.tool and rep['status'] != 'not_implemented', (a.macro, rep['status'])
                plan = rep.get('plan') if isinstance(rep.get('plan'), dict) else {}
                res.append('{}:{}'.format(plan.get('mode', '?'), rep['status']))
            else:
                res.append('ran={} no new report'.format(ok))
        out[a.macro] = res
    if rt.isValidNode(box):
        rt.delete(box)
    return out


def panel_model():
    roadmap = agr._load_core('roadmap.py', 'agr_tools_roadmap')
    suite = roadmap.load_file(agr.suite_path())
    rail = model.rail(suite['blocks'], suite['rows'])
    done = {model.row_of(a.id) for _, d, _ in rail for a in d}
    planned = {r['id'] for _, _, p in rail for r in p}
    assert set(agr.EDITS_080) <= done and not planned & set(agr.EDITS_080)  # released: shown, not greyed
    rows = model.rows(agr._edit_core().not_implemented('export.zip', 'preview'))
    assert [(r.ok, r.code) for r in rows] == [(False, 'not_implemented')]
    return {'shown_08': len(set(agr.EDITS_080) & done), 'done_rows': len(done), 'planned_rows': len(planned)}


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


def edit_max_helpers():
    import pymxs
    emax = agr._load_core('edit_max.py', 'agr_tools_edit_max')
    edit = agr._edit_core()
    with pymxs.undo(True, 'smoke 908 setup'):  # its own record, so the run's record is the only one above it
        work = rt.Box(name='SM_Smoke_908_Work', length=3, width=4, height=5, pos=rt.Point3(1, 2, 3))
        work.material = rt.Standardmaterial(name='M_Smoke_908')
        other = rt.Sphere(name='Smoke_908_Selected', radius=1)
    rt.select(other)
    before = emax.snapshot([work])
    with emax.session('smoke 908') as was_selected:
        holding = bool(rt.theHold.Holding())  # the run records undo
        pairs = emax.export_copies([work], layer='AGR_export_smoke')
        rt.select([c for _, c in pairs])  # the run changes selection; session restores it
    copy = pairs[0][1]
    after = emax.snapshot([work])
    assert after == before and edit.fingerprint(after) == edit.fingerprint(before), 'original changed'
    assert [str(n.name) for n in rt.selection] == ['Smoke_908_Selected'], [str(n.name) for n in rt.selection]
    assert [str(n.name) for n in was_selected] == ['Smoke_908_Selected']
    assert '_AGR_export_' in str(copy.name) and str(copy.layer.name) == 'AGR_export_smoke'
    assert copy.material is not None and copy.material != work.material
    copy_snap = emax.snapshot([copy])[0]
    assert copy_snap['mesh'] == before[0]['mesh'] and copy_snap['transform'] == before[0]['transform']
    copy_name = str(copy.name)

    def alive():
        return {'copy': rt.getNodeByName(copy_name) is not None, 'work': bool(rt.isValidNode(work)),
                'other': bool(rt.isValidNode(other))}
    steps = {'before_undo': alive()}
    rt.execute('max undo')  # a single undo removes the whole run (copy, name, material, layer membership)
    steps['undo_1'] = alive()
    summary['undo_steps'] = steps
    # Measured (job 20261105-003249-e0800495): in 3dsmaxbatch every pymxs undo record of ONE python.ExecuteFile
    # collapses into one step, so the same undo also removes the setup record. Isolation from earlier user
    # actions can only be shown in interactive Max (release smoke R); here: undo active, run fully undone.
    assert holding, 'no undo record during the run'
    assert not steps['undo_1']['copy'], steps
    return {'copy': copy_name, 'undo_active_in_run': holding, 'one_undo_removes_run': True,
            'batch_undo_merges_setup': steps['undo_1']['work'] is False, 'mesh_hash': before[0]['mesh'][:16]}


def session_reraises():
    """#908 branch C, job 20261105-011438-a488a8fd: pymxs.undo swallowed an error raised inside edit_max.session,
    so a failed apply carried on. Released edit_max re-raises it after the undo record; selection still restored."""
    emax = agr._load_core('edit_max.py', 'agr_tools_edit_max')
    sel = rt.Sphere(name='Smoke_908_Reraise_Selected', radius=1)
    rt.select(sel)
    after = []
    caught = None
    try:
        with emax.session('smoke 908 reraise'):
            rt.Box(name='Smoke_908_Reraise_Tmp')
            rt.clearSelection()
            raise ValueError('smoke 908: apply failed on purpose')
        after.append('carried on')  # the defect
    except ValueError as exc:
        caught = str(exc)
    names = [str(n.name) for n in rt.selection]
    assert caught == 'smoke 908: apply failed on purpose' and after == [], (caught, after)
    assert names == ['Smoke_908_Reraise_Selected'], names
    rt.delete([o for o in rt.objects if str(o.name).startswith('Smoke_908_Reraise')])
    return {'reraised': caught, 'selection_restored': names}


for name, fn in (('registry', registry), ('refusals', refusals), ('macros', macros), ('panel_model', panel_model),
                 ('icons', icons), ('edit_max', edit_max_helpers), ('session_reraises', session_reraises)):
    check(name, fn)
summary['scene_saved'] = bool(str(rt.maxFileName))
(OUT / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding='utf-8')
print('AGR_908_SUMMARY ' + json.dumps(summary, ensure_ascii=True)[:3000])
assert not summary['errors'] and not summary['scene_saved'], sorted(summary['errors'])
