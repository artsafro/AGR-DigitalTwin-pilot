"""new-case: native smoke of the AGR Tools 1.1 RELEASE (release branch improve/agr-tools-1-1) in locked batch Max 2024
on DISPOSABLE synthetic scenes.

Run via the lab DCC runner (script_in_place); AGR_TEST_OUTPUT names a NEW directory, AGR_TEST_PACKAGE the built MZP.
Installs the MZP into OUT (no user folders touched), then checks in the real Max Python, through the INSTALLED
runtime (the panel route: runtime.edit_ui with the options of the parameter form):
* version 1.1.0, runtime.EDITS_100 = the 37 stage buttons (33 of 1.0 + 4 handoff rows of 1.1), the installed
  package has handoff_core.py / handoff_max.py / params_core.py and the plan rows of 1.1;
* needs_params: a form row pressed without its required option is refused naming the field, before the glue;
* handoff on a centimetre scene (Multi/Sub + Standard with bitmaps, an instance): export preview -> apply writes a NEW
  bundle; verify of the source scene vs the bundle; import of the bundle FBX into AGENT_<req>; verify of that layer;
  «Восстановить материалы» preview -> apply on the layer; agent.accept preview -> apply of the import request;
* the agr-mcp bridge in this Max: handoff.import preview WITHOUT handles (the bundle is the input), handoff.export
  apply over MCP allowed (new folder), handoff.restore_materials apply over MCP refused (needs_human).
Nothing is saved; the scenes are never written. The Claude dock and the Qt form need the GUI: covered by pytest-qt.
"""
import hashlib
import importlib.util
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
os.environ['LOCALAPPDATA'] = str(OUT / 'localappdata')
os.environ['AGR_JOURNAL_DIR'] = str(OUT / 'journal')
os.environ['AGR_NO_PROMPT'] = '1'
summary = {'max_version': list(rt.maxVersion())[:3], 'package_sha256': hashlib.sha256(PACKAGE.read_bytes()).hexdigest(),
           'checks': {}, 'errors': {}}
assert not rt.maxFileName, 'only an empty batch document is allowed'
HANDOFF = ('handoff.export', 'handoff.import', 'handoff.verify', 'handoff.restore_materials')
JOB = OUT / 'jobs' / 'BH11'


def check(name, fn):
    try:
        summary['checks'][name] = fn()
    except Exception:  # noqa: BLE001 - recorded; the run fails at the end
        summary['errors'][name] = traceback.format_exc()[-2500:]


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def install():
    rt.execute('global AGRToolsInstallRoot; global AGRToolsStartupRoot')
    rt.AGRToolsInstallRoot = str(OUT / 'installed') + '/'
    rt.AGRToolsStartupRoot = str(OUT / 'startup') + '/'
    rt.makeDir(rt.AGRToolsStartupRoot, all=True)
    rt.fileIn(str(PACKAGE))
    assert rt.execute('global AGRToolsRegistered; AGRToolsRegistered == true'), 'MZP macros not registered'
    sys.path.insert(0, str(OUT / 'installed'))
    sys.modules.pop('runtime', None)
    import runtime as agr
    return agr


agr = install()
roadmap = agr._load_core('roadmap.py', 'agr_tools_roadmap')
suite = roadmap.load_file(str(OUT / 'installed' / 'agr-tools-suite.json'))
MODEL = agr._load_core('ui_model.py', 'agr_tools_ui_model')


def registry():
    assert agr.VERSION == MODEL.VERSION == '1.1.0', (agr.VERSION, MODEL.VERSION)
    every = roadmap.stage_buttons(suite, None)
    assert list(agr.EDITS_100) == every and len(every) == 37, every
    assert roadmap.stage_buttons(suite, '1.1') == list(HANDOFF)
    for name in ('handoff_core.py', 'handoff_max.py', 'params_core.py'):
        assert (OUT / 'installed' / name).is_file(), name
    mcr = (OUT / 'installed' / 'agr_tools.mcr').read_text(encoding='utf-8-sig')
    for tool in HANDOFF:
        assert "form_ui('{}')".format(tool) in mcr, tool
    assert 'AGRToolsAgentDock' in mcr and callable(agr.agent_dock) and callable(agr.form_ui)
    return {'version': agr.VERSION, 'stage_buttons': len(every), 'stations': {t: roadmap.stations(suite)[t]
                                                                               for t in HANDOFF}}


def _units(name):
    rt.units.SystemType = rt.name(name)


def _scene():
    """BODY_Brick_001 (box, Multi/Sub of two Standard with diffuse bitmaps, matIDs 1/2), its instance
    BODY_Brick_002, GLASS_001 (Standard with an opacity bitmap); centimetres, pivot off the geometry."""
    rt.resetMaxFile(rt.name('noPrompt'))
    _units('centimeters')
    maps = OUT / 'maps'
    maps.mkdir(parents=True, exist_ok=True)

    def std(name, colour, mapname, slot='diffuseMap'):
        m = rt.Standardmaterial(name=name)
        m.diffuse = rt.color(*colour)
        bm = rt.Bitmaptexture(name=name + '_map')
        bm.filename = str(maps / mapname)
        setattr(m, slot, bm)
        return m
    multi = rt.Multimaterial(numsubs=2, name='BH11_Multi')
    multi.materialList[0] = std('BH11_Side', (180, 90, 60), 'side.png')
    multi.materialList[1] = std('BH11_Top', (90, 90, 180), 'top.png')
    body = rt.Box(name='BODY_Brick_001', length=300, width=400, height=250, mapcoords=True)
    rt.convertToPoly(body)
    for f in range(1, int(rt.polyop.getNumFaces(body)) + 1):
        rt.polyop.setFaceMatID(body, f, 1 if f > 2 else 2)
    body.material = multi
    body.pos = rt.Point3(120, 40, 0)
    rt.setUserProp(body, 'agr_role', 'body')
    twin = rt.instance(body)
    twin.name = 'BODY_Brick_002'
    twin.pos = rt.Point3(900, 40, 0)
    glass = rt.Plane(name='GLASS_001', length=100, width=150, lengthsegs=1, widthsegs=1)
    rt.convertToPoly(glass)
    glass.material = std('BH11_Glass', (200, 220, 255), 'glass_opacity.png', 'opacityMap')
    glass.pos = rt.Point3(120, -110, 120)
    rt.setUserProp(glass, 'agr_role', 'glass')
    return [body, twin, glass]


def _press(tool, options, nodes=None):
    """Two panel presses through edit_ui (preview, then apply of that preview); a read row presses once."""
    if nodes is not None:
        rt.clearSelection()
        rt.select(nodes)
    else:
        rt.clearSelection()
    agr._edits.pop(tool, None)
    pre = agr.edit_ui(tool, select=False, options=options)
    out = {'preview': pre['status'], 'findings': sum(len(o['findings']) for o in pre['objects'])}
    if tool in agr.READ_100:
        return pre, None, out
    app = agr.edit_ui(tool, select=False, options=options)
    assert app['plan']['mode'] == 'apply', (tool, app['plan']['mode'])
    out['apply'] = app['status']
    return pre, app, out


def needs_params():
    rt.resetMaxFile(rt.name('noPrompt'))
    b = rt.Box(name='SM_Smoke_110_Main_001')
    rt.select(b)
    got = {}
    for tool in ('agent.request', 'handoff.import', 'tex.dilate'):
        try:
            agr.edit_ui(tool)
            raise AssertionError(tool + ': pressed without its parameter')
        except ValueError as exc:
            assert str(exc).startswith('needs_params: ' + tool), exc
            got[tool] = str(exc)[:140]
    return got


STATE = {}


def handoff():
    nodes = _scene()
    res = {}
    pre, app, res['export'] = _press('handoff.export', {'job_dir': str(JOB)}, nodes)
    bundle = JOB / 'handoff' / pre['plan']['seq']
    files = sorted(p.name for p in bundle.iterdir())
    for f in ('model.fbx', 'manifest.json', 'sidecar.json', 'materials.json', 'readback_max.json'):
        assert f in files, (f, files)
    res['bundle_files'] = files
    STATE['bundle'] = str(bundle)
    _p, _a, res['verify_source'] = _press('handoff.verify', {'bundle': str(bundle)}, nodes)
    pre, app, res['import'] = _press('handoff.import', {'bundle': str(bundle)})
    layer = app['plan'].get('layer') or pre['plan'].get('layer')
    req = app['plan'].get('request')
    assert layer and layer.startswith('AGENT_') and req and os.path.isfile(req), (layer, req)
    imported = sorted(str(n.name) for n in rt.objects if str(n.layer.name) == layer)
    res['layer'], res['imported'] = layer, imported
    _p, _a, res['verify_layer'] = _press('handoff.verify', {'bundle': str(bundle), 'layer': layer})
    _p, _a, res['restore'] = _press('handoff.restore_materials', {'bundle': str(bundle), 'layer': layer})
    pre, app, res['accept'] = _press('agent.accept', {'request': req})
    res['after_accept_layers'] = sorted({str(n.layer.name) for n in rt.objects})
    lines = (OUT / 'journal').glob('*.jsonl')
    res['journal_lines'] = sum(len(p.read_text(encoding='utf-8').splitlines()) for p in lines)
    return res


def mcp_bridge():
    bridge = load(ROOT / 'src/agr_mcp/max_side/max_bridge.py', 'max_bridge')
    assert bridge.ROUTES['handoff.export'][2] == '1.1.0'
    root = str(OUT / 'installed').encode().hex()
    nodes = _scene()
    rt.clearSelection()

    def call(tool, args):
        return json.loads(bridge.call(tool, root, json.dumps(args).encode().hex()))
    out = {}
    imp = call('agr_op_preview', {'scene': 'live', 'op': 'handoff.import', 'options': {'bundle': STATE['bundle'],
                                                                                         'request_id': 'mcp11'}})
    assert imp['ok'] and imp['result']['plan']['mode'] == 'preview', imp
    out['import_preview_without_handles'] = imp['result']['status']
    h = [int(n.inode.handle) for n in nodes]
    exp = call('agr_op_preview', {'scene': 'live', 'handles': h, 'op': 'handoff.export',
                                  'options': {'job_dir': str(JOB)}})
    assert exp['ok'], exp
    app = call('agr_op_apply', {'scene': 'live', 'handles': h, 'op': 'handoff.export', 'preview': exp['result'],
                                'expect': {'doc': exp['doc'], 'runtime_version': exp['runtime_version']}})
    assert app['ok'] and app['result']['plan']['mode'] == 'apply', app
    out['export_apply_over_mcp'] = app['result']['status']
    res = call('agr_op_preview', {'scene': 'live', 'handles': h, 'op': 'handoff.restore_materials',
                                  'options': {'bundle': STATE['bundle']}})
    assert res['ok'], res
    bad = call('agr_op_apply', {'scene': 'live', 'handles': h, 'op': 'handoff.restore_materials',
                                'preview': res['result']})
    assert not bad['ok'] and 'needs_human' in bad['error'], bad
    out['restore_apply_over_mcp'] = bad['error'][:120]
    return out


check('registry_110', registry)
check('needs_params', needs_params)
check('handoff_panel_route', handoff)
if 'bundle' in STATE:
    check('mcp_bridge_110', mcp_bridge)
_units('meters')
(OUT / 'summary.json').write_text(json.dumps(summary, indent=1, ensure_ascii=False, default=str), encoding='utf-8')
print('AGR_TOOLS_110_NATIVE checks', sorted(summary['checks']), 'errors', sorted(summary['errors']))
assert not summary['errors'], 'native 1.1.0 release smoke failed: see summary.json'
