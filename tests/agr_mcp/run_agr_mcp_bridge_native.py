"""new-case: #1024 PR A native check of the agr-mcp Max bridge against an installed AGR Tools 0.9.0 in batch Max 2024.

Run via the lab DCC runner (script_in_place) on an EMPTY batch document; AGR_TEST_OUTPUT names a NEW directory,
AGR_TEST_PACKAGE the built 0.9.0 MZP, AGR_BRIDGE_BEFORE the max_bridge.py of main before this PR (optional).
Installs the MZP into OUT/scripts/AGRTools-<version> (no user folder touched), builds a synthetic scene and calls
`max_bridge.call(tool, root_hex, args_hex)` - the exact code the MCP server runs inside Max over the pipe - for
EVERY Max tool of the catalogue (FUNCTIONS, CHECKS_070, EDITS_080, EDITS_090; mode=preview only).
A row passes when the bridge reached the installed runtime: ok, or a refusal raised by the runtime itself
(e.g. a row that needs an input path); never version_mismatch / runtime_missing / unsupported_tool /
handles_required / selection_changed, never `not_implemented`, and the user's selection is the same after.
Also: empty handles -> handles_required; scope=selection; root='' resolves to the loaded runtime; default_root
finds the install. The pipe transport (3dsmax-mcp) is not exercised here: the batch slot has no listener.
With AGR_BRIDGE_BEFORE the same calls go through the old bridge to measure how many tools worked before the PR.
Nothing is saved; the scene is never written. Writes native.json; raises when any row fails.
"""
import hashlib
import importlib.util
import json
import os
import sys
import traceback
from pathlib import Path

from pymxs import runtime as rt

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(os.environ['AGR_TEST_OUTPUT'])
OUT.mkdir(parents=True, exist_ok=False)
PACKAGE = Path(os.environ['AGR_TEST_PACKAGE'])
BEFORE = os.environ.get('AGR_BRIDGE_BEFORE')
os.environ['LOCALAPPDATA'] = str(OUT / 'localappdata')
os.environ['AGR_NO_PROMPT'] = '1'
assert not rt.maxFileName, 'only an empty batch document is allowed'
FATAL = ('version_mismatch', 'runtime_missing', 'unsupported_tool', 'handles_required', 'selection_changed',
         'target_conflict', 'unknown_handle', 'scene_mismatch')


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


bridge = load(ROOT / 'src/agr_mcp/max_side/max_bridge.py', 'max_bridge')
summary = {'max_version': list(rt.maxVersion())[:3],
           'package_sha256': hashlib.sha256(PACKAGE.read_bytes()).hexdigest(),
           'bridge_sha256': hashlib.sha256((ROOT / 'src/agr_mcp/max_side/max_bridge.py').read_bytes()).hexdigest(),
           'rows': [], 'checks': {}, 'errors': {}}


def install():
    rt.execute('global AGRToolsInstallRoot; global AGRToolsStartupRoot')
    scripts = OUT / 'scripts'
    version = PACKAGE.stem.rsplit('-', 1)[1]  # AGR-Tools-<x.y.z>.mzp
    root = scripts / ('AGRTools-' + version)  # the userScripts layout of install.ms
    rt.AGRToolsInstallRoot = str(root) + '/'
    rt.AGRToolsStartupRoot = str(OUT / 'startup') + '/'
    rt.makeDir(rt.AGRToolsStartupRoot, all=True)
    rt.fileIn(str(PACKAGE))
    assert (root / 'runtime.py').is_file(), 'MZP did not install runtime.py into ' + str(root)
    return scripts, root, version


SCRIPTS, INSTALL, VERSION = install()
summary['runtime_version'] = VERSION
sys.modules.pop('runtime', None)

rt.units.SystemType = rt.name('meters')
box = rt.convertToPoly(rt.box(name='SM_Bridge_Main', length=1, width=1, height=1, mapcoords=True))
plane = rt.convertToPoly(rt.plane(name='SM_Bridge_Ground', length=4, width=4, lengthsegs=1, widthsegs=1,
                                  mapcoords=True, pos=rt.point3(3, 0, 0)))
glass = rt.convertToPoly(rt.box(name='SM_Bridge_Main_Glass', length=1, width=1, height=0.1, mapcoords=True,
                                pos=rt.point3(0, 3, 0)))
mat = rt.standardMaterial(name='M_Bridge_Syn')
for n in (box, plane, glass):
    n.material = mat
light = rt.Omnilight(name='L_Bridge_Omni', pos=rt.point3(0, 0, 3))
H = {n.name: int(rt.getHandleByAnim(n)) for n in (box, plane, glass, light)}
summary['handles'] = H
MESH = [H['SM_Bridge_Main'], H['SM_Bridge_Ground'], H['SM_Bridge_Main_Glass']]
USER_SELECTION = [H['SM_Bridge_Ground']]


def select_user():
    rt.clearSelection()
    rt.select([rt.maxOps.getNodeByHandle(h) for h in USER_SELECTION])


def selected():
    return sorted(int(rt.getHandleByAnim(n)) for n in rt.selection)


def hexs(text):
    return text.encode('utf-8').hex()


def call(mod, tool, args, root=None):
    select_user()
    raw = mod.call(tool, hexs(str(INSTALL) if root is None else root), hexs(json.dumps(args)))
    return json.loads(raw), selected()


def targets(tool):
    if tool == 'agr_light_check':
        return [H['L_Bridge_Omni']]
    return MESH


TOOLS = ([(t, 'functions') for t in bridge.FUNCTIONS] + [(t, 'checks_070') for t in bridge.CHECKS_070]
         + [(t, 'edits_080') for t in bridge.EDITS_080] + [(t, 'edits_090') for t in bridge.EDITS_090])
summary['tools_total'] = len(TOOLS)


def verdict(out, after):
    if not out.get('ok'):
        err = str(out.get('error'))
        code = err.split(':', 2)[1].strip() if err.count(':') >= 2 else ''
        fatal = any(err.startswith(c) or (': ' + c + ':') in err or code == c for c in FATAL)
        return {'reached_runtime': not fatal, 'status': 'refused', 'error': err[:300]}
    res = out.get('result') or {}
    status = res.get('status') if isinstance(res, dict) else None
    return {'reached_runtime': status != 'not_implemented', 'status': status,
            'runtime_version': out.get('runtime_version'), 'selection': out.get('selection')}


for tool, group in TOOLS:
    args = {'scene': 'live', 'handles': targets(tool)}
    if group in ('edits_080', 'edits_090'):
        args['mode'] = 'preview'
    try:
        out, after = call(bridge, tool, args)
        row = dict(verdict(out, after), tool=tool, group=group, selection_after=after,
                   selection_kept=after == sorted(USER_SELECTION))
        row['pass'] = row['reached_runtime'] and row['selection_kept']
    except Exception:  # noqa: BLE001 - a crash of call() itself is a failed row
        row = {'tool': tool, 'group': group, 'pass': False, 'error': traceback.format_exc()[-1500:]}
    summary['rows'].append(row)
    print('ROW', tool, row.get('status'), 'pass=' + str(row['pass']), (row.get('error') or '')[:160])


def check(name, fn):
    try:
        summary['checks'][name] = fn()
    except Exception:  # noqa: BLE001
        summary['errors'][name] = traceback.format_exc()[-2000:]


def empty_handles():
    out = {}
    for tool in ('agr_xview_check', 'agr_scene_census', 'agr_qa_package', 'agr_udim_slots'):
        got, after = call(bridge, tool, {'scene': 'live', 'handles': []})
        assert not got['ok'] and got['error'].startswith('BridgeError: handles_required'), got
        assert after == sorted(USER_SELECTION), after
        out[tool] = got['error'][:80]
    return out


def scope_selection():
    got, after = call(bridge, 'agr_scene_census', {'scene': 'live', 'scope': 'selection'})
    assert got['ok'] and got['selection']['scope'] == 'selection', got
    names = sorted(o.get('name') for o in got['result'].get('objects', []) if isinstance(o, dict))
    assert after == sorted(USER_SELECTION), after
    bad, _ = call(bridge, 'agr_scene_census', {'scene': 'live', 'scope': 'selection', 'handles': MESH})
    assert not bad['ok'] and 'target_conflict' in bad['error'], bad
    return {'objects': names}


def checks_070_select_false():
    got, after = call(bridge, 'agr_qa_zero_area', {'scene': 'live', 'handles': MESH})
    assert got['ok'] and got['selection']['restored'] is False, got['selection']
    return {'status': got['result'].get('status'), 'selection_after': after}


def root_resolution():
    got, _ = call(bridge, 'agr_scene_units', {'scene': 'live', 'handles': MESH}, root='')
    assert got['ok'] and os.path.normcase(got['runtime_file']) == os.path.normcase(str(INSTALL / 'runtime.py')), got
    found = bridge.default_root(str(SCRIPTS), '0.5.0')
    assert found and os.path.normcase(found) == os.path.normcase(str(INSTALL)), found
    return {'runtime_file': got['runtime_file'], 'default_root': found}


check('empty_handles_required', empty_handles)
check('scope_selection', scope_selection)
check('checks_070_select_false', checks_070_select_false)
check('root_resolution', root_resolution)

if BEFORE:
    def before_pr():
        old = load(BEFORE, 'max_bridge_before')
        rows = {}
        for tool, group in TOOLS:
            args = {'scene': 'live', 'handles': targets(tool)}
            if group in ('edits_080', 'edits_090'):
                args['mode'] = 'preview'
            out, _ = call(old, tool, args)
            err = str(out.get('error') or '')
            rows[tool] = 'ok' if out.get('ok') else ('version' if ('!=' in err or 'another module' in err)
                                                     else 'refused: ' + err[:100])
        working = sorted(t for t, v in rows.items() if v != 'version')
        return {'bridge_sha256': hashlib.sha256(Path(BEFORE).read_bytes()).hexdigest(),
                'working': len(working), 'blocked_by_pin': len(rows) - len(working), 'rows': rows}
    check('before_pr_old_bridge', before_pr)

passed = sum(r['pass'] for r in summary['rows'])
summary['passed'] = passed
summary['scene_after'] = {'file': str(rt.maxFileName), 'objects': len(list(rt.objects))}
(OUT / 'native.json').write_text(json.dumps(summary, indent=1, default=str), encoding='utf-8')
print('BRIDGE_NATIVE', passed, '/', len(TOOLS), 'checks', sorted(summary['checks']), 'errors', sorted(summary['errors']))
if summary.get('checks', {}).get('before_pr_old_bridge'):
    b = summary['checks']['before_pr_old_bridge']
    print('BEFORE_PR working', b['working'], 'blocked_by_pin', b['blocked_by_pin'])
assert passed == len(TOOLS) and not summary['errors'], 'bridge native failed: see native.json'
