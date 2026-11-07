"""new-case: AGR Tools 1.1 (release branch improve/agr-tools-1-1): the Max <-> Blender handoff of branch BH
(handoff_core.py / handoff_max.py, docs/experiments/blender-handoff.md) in the panel, the menu and the MCP server.

Defects of 1.0.1 this file pins (RED on origin/main, GREEN here):
H1 the four handoff functions were not plan rows: no button, no macro, no menu entry, no station
   (docs/experiments/blender-handoff.md §5 «Не сделано»);
H2 runtime.EDITS_100 did not route them: edit_ui('handoff.export') was `unsupported edit tool`;
H3 handoff_core.py / handoff_max.py were not in the MZP (build FILES, install.ms required list);
H4 MCP had no agr_handoff_export / agr_handoff_import / agr_handoff_verify (mcp-review 3.2, plan 1.x §3 item 6);
H5 profiles: import must be operator (markup in AGENT_* only), export operator (file: new folder), verify observer
   (read), restore materials only preview over MCP, apply = a person in the panel/dock (modeller with confirmation).
Plain pytest, no pymxs.
"""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / 'adapters/max/agr_tools'
SUITE = ROOT / 'docs/plans/agr-tools-suite.json'
HANDOFF = ('handoff.export', 'handoff.import', 'handoff.verify', 'handoff.restore_materials')


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


rm = _load(PKG / 'roadmap.py', 'agr_tools_roadmap_110h')
ec = _load(PKG / 'edit_core.py', 'agr_tools_edit_core_110h')
suite = rm.load_file(str(SUITE))
ROWS = {r['id']: r for r in suite['rows']}


def runtime():
    return _load(PKG / 'runtime.py', 'agr_runtime_110h')


def model():
    return _load(PKG / 'ui_model.py', 'agr_tools_ui_model_110h')


# ---- H1 plan rows on the agent stage -----------------------------------------------------------------------------
def test_h1_four_handoff_rows_are_1_1_buttons_of_the_agent_stage():
    agent = rm.stage_of(suite, 'agent')
    assert agent['rows'] == ['agent.request', 'agent.accept'] + list(HANDOFF)
    assert agent['big_button'] == 'agent.request'
    modes = {r: ROWS[r]['mode'] for r in HANDOFF}
    assert modes == {'handoff.export': 'file', 'handoff.import': 'undo', 'handoff.verify': 'read',
                     'handoff.restore_materials': 'undo'}
    for r in HANDOFF:
        assert ROWS[r]['version'] == '1.1' and ROWS[r]['fate'] == 'stage' and ROWS[r]['mcp'] == 'yes', r
        assert ROWS[r]['lab_report'] == 'docs/experiments/blender-handoff.md'
    v11 = next(v for v in suite['versions'] if v['version'] == '1.1')
    assert v11['rows'] == list(HANDOFF) and v11['status'] == 'done'
    # stations are numbered per version: the 33 of 1.0 keep their numbers, the handoff rows are 1.1.1..1.1.4
    st = rm.stations(suite)
    assert st['agent.accept'] == '1.0.33' and [st[r] for r in HANDOFF] == ['1.1.1', '1.1.2', '1.1.3', '1.1.4']
    assert len(rm.stage_buttons(suite)) == 33 and rm.stage_buttons(suite, '1.1') == list(HANDOFF)
    assert rm.stage_buttons(suite, None) == rm.stage_buttons(suite) + list(HANDOFF)
    # the passport K1 keeps its 11 stages: the handoff is not a new stage
    assert [s['id'] for s in suite['stages']] == list(range(10)) + ['agent']


def test_h1_roadmap_still_rejects_a_1_1_row_missing_from_its_version_list():
    broken = json.loads(SUITE.read_text(encoding='utf-8'))
    next(v for v in broken['versions'] if v['version'] == '1.1')['rows'].reverse()
    with pytest.raises(ValueError, match=r'versions\[1.1\]'):
        rm.load(json.dumps(broken, ensure_ascii=False))
    broken = json.loads(SUITE.read_text(encoding='utf-8'))
    next(r for r in broken['rows'] if r['id'] == 'handoff.verify')['version'] = '0.9'
    with pytest.raises(ValueError, match='needs version'):
        rm.load(json.dumps(broken, ensure_ascii=False))


def test_h1_buttons_macros_menu_and_icons():
    m = model()
    icons = _load(ROOT / 'tools/max/agr_icons.py', 'agr_icons_110h')
    for r in HANDOFF:
        a = m.BY_TOOL[r]
        assert a in m.ACTIONS_100 and not a.wip
        assert (a.icon, a.label) == (ROWS[r]['icon'], ROWS[r]['label_ru'])
        assert a.tip == '1.1, этап «Агент»' and m.stage_tip(r) == a.tip
        assert a.icon in icons.names()
        mcr = m.macros_ms()
        assert 'macroScript {} '.format(a.macro) in mcr and "form_ui('{}')".format(r) in mcr
        assert m.stable_id(a.macro) in m.menu_ms()
    assert m.BY_TOOL['handoff.restore_materials'].label == 'Восстановить материалы'
    assert m.stage_tip('agent.accept') == '1.0, этап «Агент»'
    rail = {st.id: st for st in m.stage_rail(suite)}
    assert [a.tool for a in rail['agent'].small] == ['agent.accept'] + list(HANDOFF)
    for name in ('agr_tools.mcr', 'menu.ms'):
        text = getattr(m, 'macros_ms' if name.endswith('.mcr') else 'menu_ms')()
        assert (PKG / name).read_bytes().replace(b'\r\n', b'\n') == b'\xef\xbb\xbf' + text.encode('utf-8')


# ---- H2 runtime registry -----------------------------------------------------------------------------------------
def test_h2_runtime_routes_the_handoff_rows_to_handoff_max():
    rt = runtime()
    for r in HANDOFF:
        assert rt.EDITS_100[r] == ('handoff_core.py', r.replace('.', '_'))
        assert rt.glue_file('handoff_core.py', rt.GLUE_100) == 'handoff_max.py'
    assert 'handoff.verify' in rt.READ_100 and not set(HANDOFF) - {'handoff.verify'} & set(rt.READ_100)
    glue = (PKG / 'handoff_max.py').read_text(encoding='utf-8')
    for r in HANDOFF:
        assert 'def {}(ctx, mode, nodes, preview)'.format(r.replace('.', '_')) in glue
    assert rt.VERSION == '1.1.0'


def test_h2_verify_has_no_apply_and_mcp_may_apply_only_export_and_import(monkeypatch):
    rt = runtime()
    p = ec.report('handoff.restore_materials', 'preview', objects=[ec.entry(5, 'Box')], done=['Box'],
                  state_hash=ec.fingerprint((1,)))
    with pytest.raises(ValueError, match='^needs_human'):
        rt.edits_100('handoff.restore_materials', 'apply', p, actor='mcp')
    with pytest.raises(ValueError, match='read-only'):
        rt.edits_100('handoff.verify', 'apply', p)
    assert set(rt.MCP_APPLY_100) == {'handoff.export', 'handoff.import'}
    seen = []
    monkeypatch.setattr(rt, '_dispatch_edit', lambda table, read, glue, issue, tool, mode, *a: seen.append(
        (tool, mode)) or ec.not_implemented(tool, mode, issue))
    for tool in rt.MCP_APPLY_100:
        rt.edits_100(tool, 'apply', p, actor='mcp')  # not refused before the glue (the glue checks the preview)
    with pytest.raises(ValueError, match='^needs_human'):
        rt.edits_100('handoff.export', 'apply', p, actor='agent')  # only the MCP client of the operator profile
    assert seen == [(t, 'apply') for t in rt.MCP_APPLY_100]


# ---- H3 package ---------------------------------------------------------------------------------------------------
def test_h3_handoff_and_params_modules_ship_in_the_mzp():
    builder = _load(ROOT / 'tools/max/build_agr_tools.py', 'agr_builder_110h')
    install = (PKG / 'install.ms').read_text(encoding='utf-8-sig')
    for name in ('handoff_core.py', 'handoff_max.py', 'params_core.py'):
        assert name in builder.FILES and '"{}"'.format(name) in install, name


# ---- H4/H5 MCP -------------------------------------------------------------------------------------------------
def test_h4_mcp_handoff_tools_and_routes():
    from agr_mcp import catalog, tools
    from agr_mcp.max_side import max_bridge
    cat = tools.catalog()
    for name in ('agr_handoff_export', 'agr_handoff_import', 'agr_handoff_verify'):
        assert name in cat and cat[name].schema == 2, name
        assert name in tools.v2_names()
    assert cat['agr_handoff_verify'].read_only and not cat['agr_handoff_import'].read_only
    props = cat['agr_handoff_import'].input['properties']
    assert {'bundle', 'request_id', 'fbx', 'preview_id', 'scene'} <= set(props)
    assert 'preview_id' not in cat['agr_handoff_verify'].input['properties']
    for r in HANDOFF:
        assert max_bridge.ROUTES[r] == ('e100', r, '1.1.0', 'edits_100'), r
    assert list(max_bridge.ROWS_100) == list(runtime().EDITS_100)
    assert 'handoff.verify' in max_bridge.READ_ROWS and 'handoff.verify' in catalog.check_ids(catalog.load_plan())
    plan = catalog.load_plan()
    assert 'handoff.restore_materials' in catalog.op_ids(plan)
    assert {'handoff.export', 'handoff.import'} <= set(catalog.apply_ids(plan))
    assert 'handoff.restore_materials' not in max_bridge.APPLY_OVER_MCP
    assert {'handoff.export', 'handoff.import'} <= max_bridge.APPLY_OVER_MCP
    assert len(catalog.stage_rows(plan)) == 15  # the 1.0 stage tools are unchanged


@pytest.mark.parametrize('profile,expected', [
    ('observer', {'agr_handoff_verify'}),
    ('operator', {'agr_handoff_verify', 'agr_handoff_export', 'agr_handoff_import'}),
    ('modeller', {'agr_handoff_verify', 'agr_handoff_export', 'agr_handoff_import'})])
def test_h5_profiles(profile, expected):
    from agr_mcp import tools
    from agr_mcp.max_side import agr_profiles as pr
    cat = tools.catalog()
    got = {n for n in ('agr_handoff_export', 'agr_handoff_import', 'agr_handoff_verify') if pr.allowed(cat[n], profile)}
    assert got == expected
    assert pr.tool_class(cat['agr_handoff_export']) == 'file' and pr.tool_class(cat['agr_handoff_import']) == 'markup'
    assert pr.tool_class(cat['agr_handoff_verify']) == 'read'
    assert not pr.allowed(cat['agr_op_apply'], 'operator')  # restore apply: never operator


def test_h5_bridge_takes_the_bundle_rows_without_a_selection():
    from agr_mcp.max_side import max_bridge

    class Rt:
        selection = []
    assert max_bridge._targets(Rt(), {'scene': 'live'}, ['handoff.import']) == []
    assert max_bridge._targets(Rt(), {'scene': 'live'}, ['handoff.verify']) == []
    with pytest.raises(max_bridge.BridgeError, match='handles_required'):
        max_bridge._targets(Rt(), {'scene': 'live'}, ['handoff.export'])
    with pytest.raises(max_bridge.BridgeError, match='handles_required'):
        max_bridge._targets(Rt(), {'scene': 'live'}, ['handoff.verify', 'qa.xview'])
