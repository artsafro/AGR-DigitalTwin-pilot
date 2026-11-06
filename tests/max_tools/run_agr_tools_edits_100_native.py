"""new-case: #1024 native smoke of the AGR Tools 1.0.0 RELEASE (branch R; was the branch 0 base smoke) in locked batch
Max 2024 on DISPOSABLE scenes.

Run via the lab DCC runner (script_in_place); AGR_TEST_OUTPUT names a NEW directory, AGR_TEST_PACKAGE the built MZP.
Installs the MZP into OUT (no user folders touched), then checks in the real Max Python:
runtime and panel model say 1.0.0; runtime.EDITS_100 = the 33 plan buttons in station order; 31 have their glue and
only branch Q (npm.to_vpm, udim.udims_to_ids, deferred to 1.1) still answers `not_implemented` (preview, and apply of
a synthetic preview); actor mcp/agent cannot apply; every call journals one line (journal under OUT);
host_max.MaxHost on a centimetre scene: ObjRef, mesh in metres, role prop round trip, one undo record;
the 33 macroScripts are registered: the 2 wip ones run no edit, each of the 31 released ones reaches runtime.edit_ui
(one macro press + two panel presses on a synthetic box; refusals without options are recorded, a stub answer
fails); the panel model has the stage rail (only stage 8 wip); the agr-mcp bridge previews a released 1.0 big button
and a Q stub, apply is refused; the polygon builder builds base 1.0 (33 stations).
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
MODEL = agr._load_core('ui_model.py', 'agr_tools_ui_model')
assert agr.VERSION == MODEL.VERSION == '1.0.0', (agr.VERSION, MODEL.VERSION)  # release 1.0.0 (#1024 R)
WIP = set(MODEL.WIP_100)


def journal_lines():
    p = OUT / 'journal' / 'untitled.jsonl'
    return [json.loads(x) for x in p.read_text(encoding='utf-8').splitlines()] if p.is_file() else []


def implemented(tool):
    import ast
    core, fn = agr.EDITS_100[tool]
    glue = OUT / 'installed' / agr.glue_file(core, agr.GLUE_100)
    return fn in {n.name for n in ast.parse(glue.read_text(encoding='utf-8')).body if isinstance(n, ast.FunctionDef)}


def registry():
    assert list(agr.EDITS_100) == ORDER and len(ORDER) == 33, ORDER
    ec = agr._edit_core()
    out, before = {}, len(journal_lines())
    rt.clearSelection()
    box = rt.Box(name='SM_Smoke_1024_Main_001', length=2, width=2, height=2)
    rt.select(box)
    stubs = [t for t in ORDER if not implemented(t)]  # release 1.0.0: only branch Q is still a stub (1.1)
    assert set(stubs) == WIP == {'npm.to_vpm', 'udim.udims_to_ids'}, stubs
    for tool in stubs:
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
    calls = len(stubs) + 3 * sum(t not in agr.READ_100 for t in stubs)
    assert len(lines) == calls, (len(lines), calls)  # every call, refused ones too, is one line
    assert {x['actor'] for x in lines} == {'panel', 'mcp', 'agent'}
    return {'implemented': len(ORDER) - len(out), 'stubs': sorted(out), 'journal_lines': len(lines),
            'journal_file': 'journal/untitled.jsonl'}


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


def _macro_module():
    import __main__
    mod = getattr(__main__, 'agr_tools_runtime', None)
    summary['macro_runtime'] = 'bootstrap' if mod is not None else 'fallback: this script import'
    return mod if mod is not None else agr


def _box():
    rt.clearSelection()
    b = rt.Box(name='SM_Smoke_1024_Main_001', length=2, width=2, height=2)
    rt.select(b)
    return b


def macros_and_rail():
    """The 2 wip macroScripts run no edit; each of the 31 released ones reaches runtime.edit_ui: a macro press, then
    two panel presses through the SAME runtime object the macros use (preview, then apply of that preview for an
    editing row). Options-less presses may refuse (no passport, no library, no folder): recorded. A stub answer
    fails. The panel model gives the stage rail with only stage 8 wip."""
    model = MODEL
    acts = model.ACTIONS_100
    assert [a.tool for a in acts] == ORDER and {a.tool for a in acts if a.wip} == WIP
    mod = _macro_module()
    wip, released = {}, {}
    for a in acts:
        rt.resetMaxFile(rt.name('noPrompt'))
        box = _box()
        before = len(journal_lines())
        ran = bool(rt.macros.run('AGR Tools', a.macro))
        grew = len(journal_lines()) - before
        if a.wip:
            assert grew == 0, a.macro + ': a wip macro reached the runtime'
            wip[a.macro] = 'ran={} journal+0'.format(ran)
            continue
        res = ['macro ran={} journal+{}'.format(ran, grew)]
        mod._edits.pop(a.tool, None)  # the presses below start from a fresh preview
        for press in (1, 2):
            if not rt.isValidNode(box):
                box = _box()
            rt.select(box)
            before = len(journal_lines())
            try:
                rep = mod.edit_ui(a.tool)
            except Exception as exc:  # noqa: BLE001 - the refusal text is the evidence
                res.append('press{} refused: {}'.format(press, (str(exc).splitlines() or [type(exc).__name__])[0][:160]))
                continue
            assert rep['tool'] == a.tool and rep['status'] != 'not_implemented', (a.macro, rep['status'])
            plan = rep.get('plan') if isinstance(rep.get('plan'), dict) else {}
            res.append('press{} {}:{} journal+{}'.format(press, plan.get('mode', '?'), rep['status'],
                                                         len(journal_lines()) - before))
        released[a.macro] = res
    assert len(released) == 31 and len(wip) == 2
    rail = model.stage_rail(suite, None)
    assert len(rail) == 11, rail
    assert [st.id for st in rail if st.big.wip] == [8], [st.id for st in rail if st.big.wip]
    done = {model.row_of(a.id) for _, d, _ in model.rail(suite['blocks'], suite['rows']) for a in d}
    old_10 = {a.tool for a in acts if a.tool.partition('.')[0] == roadmap.row(suite, a.tool)['block']}
    assert old_10 - WIP <= done and not WIP & done, sorted(old_10 - done)
    icons = sorted(p.name for p in (OUT / 'installed').rglob('agr_passport*.png'))
    return {'wip': wip, 'released': released, 'stages': len(rail), 'old_rows_done_on_pages': len(old_10 - WIP),
            'passport_icons': len(icons)}


def mcp_bridge():
    """agr-mcp bridge inside this Max: a released 1.0 big button (body.roof) and a Q stub (npm.to_vpm) preview;
    apply over MCP is refused (needs_human); an empty handles list is refused."""
    bridge = load(ROOT / 'src/agr_mcp/max_side/max_bridge.py', 'max_bridge')
    rt.resetMaxFile(rt.name('noPrompt'))
    b = rt.Box(name='BODY_Brick_001')
    h = int(b.inode.handle)
    root = (str(OUT / 'installed')).encode().hex()
    assert 'body.roof' in bridge.ROWS_100 and 'body.roof' in bridge.EDIT_ROWS
    args = {'scene': 'live', 'handles': [h], 'op': 'body.roof'}
    got = json.loads(bridge.call('agr_op_preview', root, json.dumps(args).encode().hex()))
    assert got['ok'] and got['result']['status'] != 'not_implemented', got
    assert bridge.RUNTIME_100 == '1.0.0'
    bad = json.loads(bridge.call('agr_op_apply', root, json.dumps(dict(args, preview=got['result'])).encode().hex()))
    assert not bad['ok'] and 'needs_human' in bad['error'], bad
    stub = json.loads(bridge.call('agr_op_preview', root, json.dumps(dict(args, op='npm.to_vpm')).encode().hex()))
    assert stub['ok'] and stub['result']['status'] == 'not_implemented', stub
    empty = json.loads(bridge.call('agr_op_preview', root, json.dumps({'scene': 'live', 'op': 'body.roof'})
                                   .encode().hex()))
    assert not empty['ok'] and 'handles_required' in empty['error'], empty
    tool, names = 'agr_op_preview(body.roof)', bridge.ROWS_100
    return {'tool': tool, 'preview': got['result']['status'], 'apply_refused': bad['error'][:120],
            'q_stub': stub['result']['status'],
            'bridge_tools_100': len(names)}


check('macros_and_rail', macros_and_rail)
check('mcp_bridge_100', mcp_bridge)
check('polygon_base_1_0', polygon)
(OUT / 'summary.json').write_text(json.dumps(summary, indent=1, ensure_ascii=False, default=str), encoding='utf-8')
print('EDITS_100_NATIVE checks', sorted(summary['checks']), 'errors', sorted(summary['errors']))
assert not summary['errors'], 'native 1.0.0 release smoke failed: see summary.json'
