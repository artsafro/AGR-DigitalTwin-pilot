"""new-case: #1024 branch 0 native smoke of the AGR Tools 1.0 BASE in locked batch Max 2024 on DISPOSABLE scenes.

Run via the lab DCC runner (script_in_place); AGR_TEST_OUTPUT names a NEW directory, AGR_TEST_PACKAGE the built MZP.
Installs the MZP into OUT (no user folders touched), then checks in the real Max Python:
runtime.EDITS_100 = the 33 plan buttons in station order and every stub answers `not_implemented` (preview, and apply
of a synthetic preview for editing rows); actor mcp/agent cannot apply; every call journals one line (journal under
OUT); host_max.MaxHost on a centimetre scene: ObjRef, mesh in metres, role prop round trip, one undo record;
the 33 macroScripts are registered and wip (no edit runs); the panel model has the stage rail; the agr-mcp bridge
routes a 1.0 big button (preview only) and refuses apply; the polygon builder builds base 1.0 (33 stations).
Nothing is saved; the scenes are never written.
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


def check(name, fn):
    try:
        summary['checks'][name] = fn()
    except Exception:  # noqa: BLE001 - recorded; the run fails at the end
        summary['errors'][name] = traceback.format_exc()[-2000:]


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
ORDER = roadmap.stage_buttons(suite)
summary['runtime_version'] = agr.VERSION


def journal_lines():
    p = OUT / 'journal' / 'untitled.jsonl'
    return [json.loads(x) for x in p.read_text(encoding='utf-8').splitlines()] if p.is_file() else []


def registry():
    assert list(agr.EDITS_100) == ORDER and len(ORDER) == 33, ORDER
    ec = agr._edit_core()
    out, before = {}, len(journal_lines())
    rt.clearSelection()
    box = rt.Box(name='SM_Smoke_1024_Main_001', length=2, width=2, height=2)
    rt.select(box)
    for tool in ORDER:
        r = agr.edits_100(tool, 'preview')
        assert r['status'] == 'not_implemented' and r['plan']['issue'] == '#1024', (tool, r['status'])
        agr.parse_report(json.dumps(r))
        if tool not in agr.READ_100:
            p = ec.report(tool, 'preview', objects=[ec.entry(5, 'Box')], done=['Box'], state_hash=ec.fingerprint((1,)))
            assert agr.edits_100(tool, 'apply', p)['status'] == 'not_implemented', tool
            for actor in ('mcp', 'agent'):
                try:
                    agr.edits_100(tool, 'apply', p, actor=actor)
                    raise AssertionError(tool + ': apply by ' + actor + ' was not refused')
                except ValueError as exc:
                    assert str(exc).startswith('needs_human'), exc
        out[tool] = r['status']
    rt.delete(box)
    lines = journal_lines()[before:]
    calls = len(ORDER) + 3 * sum(t not in agr.READ_100 for t in ORDER)
    assert len(lines) == calls, (len(lines), calls)  # every call, refused ones too, is one line
    assert {x['actor'] for x in lines} == {'panel', 'mcp', 'agent'}
    return {'stubs': len(out), 'journal_lines': len(lines), 'journal_file': 'journal/untitled.jsonl'}


def host_adapter():
    host = agr._load_core('host_max.py', 'agr_tools_host_max').MaxHost()
    old = (str(rt.units.SystemType), float(rt.units.SystemScale))
    rt.units.SystemType = rt.name('centimeters')
    try:
        b = rt.Box(name='BODY_Brick_001', length=100, width=200, height=300)  # 1 x 2 x 3 m in cm units
        ref, = host.refs([b])
        assert ref['host'] == 'max' and ref['name'] == 'BODY_Brick_001' and ref['doc'] == 'untitled', ref
        assert host.resolve([ref])[0] == b
        mesh = host.mesh(ref)
        xs = [v[0] for v in mesh['verts']]
        zs = [v[2] for v in mesh['verts']]
        size = (round(max(xs) - min(xs), 6), round(max(zs) - min(zs), 6))
        assert size == (2.0, 3.0), size
        assert abs(host.m_per_unit() - 0.01) < 1e-12
        with host.undo('AGR Tools 1.0 smoke: role'):
            host.set_role(ref, 'body')
        assert host.role(ref) == 'body'
        try:
            host.set_role(ref, 'wall')
            raise AssertionError('unknown role accepted')
        except ValueError:
            pass
        rt.delete(b)
        return {'ref': ref, 'size_m': size, 'faces': len(mesh['faces'])}
    finally:
        rt.units.SystemType = rt.name(old[0].lstrip('#'))
        rt.units.SystemScale = old[1]


check('registry_stubs_journal', registry)
check('host_adapter_cm', host_adapter)


def polygon():
    """The builder builds the committed catalog with base 1.0: 33 stations 1.0.1..1.0.33, its base and camera."""
    sys.path.insert(0, str(ROOT / 'test-polygon' / 'build'))
    sys.path.insert(0, str(ROOT / 'test-polygon'))
    import polygon_core as core
    import build_scene
    rt.resetMaxFile(rt.name('noPrompt'))
    rt.units.SystemType = rt.name('meters')
    catalog = build_scene.catalog_objects()
    made = build_scene.build('polygon_all', texture_dir=str(OUT / 'textures'))
    names = {str(n.name) for n in rt.objects}
    want = [o['name'] for o in catalog if o['scene'] == 'polygon_all']
    missing = sorted(set(want) - names)
    assert not missing, missing[:10]
    new = [s for s in core.stations() if s['version'] == '1.0']
    assert [s['button'] for s in new] == ORDER, [s['button'] for s in new][:5]
    labels = ['_label_' + s['id'].replace('.', '_') for s in new]
    absent = [x for x in labels if rt.getNodeByName(x) is None]
    assert len(new) == 33 and not absent, absent
    for x in ('_base_1_0', '_cam_База 1.0'):
        assert rt.getNodeByName(x) is not None, x
    assert core.TOUR_LAST == '1.0'
    text = str(rt.getNodeByName('_label_1_0_1').text)
    return {'stations_1_0': len(new), 'nodes_built': len(made), 'catalog_polygon_all': len(want),
            'label_1_0_1': text.replace('\r\n', ' | ')[:160]}


def macros_and_rail():
    """33 wip macroScripts are registered, disabled and run no edit; the panel model gives the stage rail."""
    model = agr._load_core('ui_model.py', 'agr_tools_ui_model')
    acts = model.ACTIONS_100
    assert [a.tool for a in acts] == ORDER and all(a.wip for a in acts)
    before = len(journal_lines())
    out = {}
    for a in acts:
        ran = bool(rt.macros.run('AGR Tools', a.macro))
        out[a.macro] = ran
    assert len(journal_lines()) == before, 'a wip macro reached the runtime'
    rail = model.stage_rail(suite, None)
    assert len(rail) == 11, rail
    icons = sorted(p.name for p in (OUT / 'installed').rglob('agr_passport*.png'))
    return {'macros': len(out), 'ran_flags': sorted(set(out.values())), 'stages': len(rail),
            'passport_icons': len(icons)}


def mcp_bridge():
    """agr-mcp bridge inside this Max: a 1.0 big button previews (stub -> not_implemented), apply is refused."""
    bridge = load(ROOT / 'src/agr_mcp/max_side/max_bridge.py', 'max_bridge')
    rt.resetMaxFile(rt.name('noPrompt'))
    b = rt.Box(name='BODY_Brick_001')
    h = int(b.inode.handle)
    root = (str(OUT / 'installed')).encode().hex()
    assert 'body.roof' in bridge.ROWS_100 and 'body.roof' in bridge.EDIT_ROWS
    args = {'scene': 'live', 'handles': [h], 'op': 'body.roof'}
    got = json.loads(bridge.call('agr_op_preview', root, json.dumps(args).encode().hex()))
    assert got['ok'] and got['result']['status'] == 'not_implemented', got
    bad = json.loads(bridge.call('agr_op_apply', root, json.dumps(dict(args, preview=got['result'])).encode().hex()))
    assert not bad['ok'] and 'needs_human' in bad['error'], bad
    empty = json.loads(bridge.call('agr_op_preview', root, json.dumps({'scene': 'live', 'op': 'body.roof'})
                                   .encode().hex()))
    assert not empty['ok'] and 'handles_required' in empty['error'], empty
    tool, names = 'agr_op_preview(body.roof)', bridge.ROWS_100
    return {'tool': tool, 'preview': got['result']['status'], 'apply_refused': bad['error'][:120],
            'bridge_tools_100': len(names)}


check('macros_and_rail', macros_and_rail)
check('mcp_bridge_100', mcp_bridge)
check('polygon_base_1_0', polygon)
(OUT / 'summary.json').write_text(json.dumps(summary, indent=1, ensure_ascii=False, default=str), encoding='utf-8')
print('EDITS_100_NATIVE checks', sorted(summary['checks']), 'errors', sorted(summary['errors']))
assert not summary['errors'], 'native 1.0 base failed: see summary.json'
