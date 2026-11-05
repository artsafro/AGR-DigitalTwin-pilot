"""new-case: AGR Tools 0.8 (#908) branch C: ucx.rename and qa.names_fix cores (names_core.py), plain pytest.

Every defect named in docs/experiments/ucx.rename.md (L01) and qa.names_fix.md (L03) has a regression test that is
RED on a behaviour model of the source and GREEN on names_core. The source models below are written from the lab
MEASUREMENTS (jobs 20261104-225132-d9e46cca, 20261104-230842-38aeaa99), not from GeoAGR code (#853):
GeoAGR UCX Rename `GeoAGR.ms:62907-62920`, Material Cloner `GeoAGR.ms:55620-55769`.
"""
import importlib.util
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / 'adapters/max/agr_tools'


def _load(name, alias):
    spec = importlib.util.spec_from_file_location(alias, PKG / name)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[alias] = mod
    spec.loader.exec_module(mod)
    return mod


nc = _load('names_core.py', 'agr_tools_names_core_t')
cc = _load('checks_core.py', 'agr_tools_checks_core')
ec = _load('edit_core.py', 'agr_tools_edit_core_names_t')
MASK = re.compile(r'^UCX_SM_[A-Za-z0-9_]+_(Main|Ground)_\d{3}$')


def red_green(prop, source, impl):
    """The property fails on the source model (RED) and holds on the implementation (GREEN)."""
    assert not prop(source()), 'source model already satisfies the property: not a regression'
    assert prop(impl())


# ---- ucx.rename: source model (L01 measurements) ---------------------------------------------------------
def source_ucx_rename(selected, unselected=()):
    """Every selected node: strip leading/trailing digits and `_`, drop every `UCX_`, then `UCX_<rest>_NNN`
    numbered in SELECTION order, skipping numbers of unselected names with the same base."""
    out, taken = {}, {}
    for name in unselected:
        m = re.fullmatch(r'(.*_)(\d+)', name)
        if m:
            taken.setdefault(m.group(1), set()).add(int(m.group(2)))
    for key, name in selected:
        rest = name.strip('0123456789_').replace('UCX_', '').strip('0123456789_')
        base = 'UCX_' + rest + '_'
        n = 1
        while n in taken.setdefault(base, set()):
            n += 1
        taken[base].add(n)
        out[key] = base + '{:03d}'.format(n)
    return out


def impl_ucx_rename(selected, unselected=(), geometry=None):
    items = [{'key': k, 'name': n, 'geometry': True if geometry is None else geometry.get(k, True)} for k, n in selected]
    plan = nc.ucx_plan(items, [n for n in unselected if nc.UCX_MASK.fullmatch(n)])
    out = {k: n for k, n in selected}
    out.update({r['key']: r['new'] for r in plan['rename']})
    return out


def test_u1_only_ucx_pieces_are_renamed():
    sel = [(1, 'SM_Tverskaya12_Main'), (2, 'UCX_SM_Tverskaya12_Main_001'), (3, 'Point001'), (4, 'Camera001')]
    red_green(lambda r: r[1] == 'SM_Tverskaya12_Main' and r[3] == 'Point001' and r[4] == 'Camera001',
              lambda: source_ucx_rename(sel), lambda: impl_ucx_rename(sel))
    plan = nc.ucx_plan([{'key': k, 'name': n, 'geometry': k != 3} for k, n in sel]
                       + [{'key': 5, 'name': 'UCX_helper', 'geometry': False}])
    assert {s['name'] for s in plan['skipped']} == {'SM_Tverskaya12_Main', 'Point001', 'Camera001', 'UCX_helper'}
    assert all(s['reason'] for s in plan['skipped'])


def test_u2_numbers_follow_old_numbers_not_selection_order():
    sel = [(10, 'UCX_SM_A_Main_003'), (11, 'UCX_SM_A_Main_002'), (12, 'UCX_SM_A_Main_001')]
    red_green(lambda r: r == {10: 'UCX_SM_A_Main_003', 11: 'UCX_SM_A_Main_002', 12: 'UCX_SM_A_Main_001'},
              lambda: source_ucx_rename(sel), lambda: impl_ucx_rename(sel))
    gaps = impl_ucx_rename([(1, 'UCX_SM_A_Main_009'), (2, 'UCX_SM_A_Main_004'), (3, 'UCX_SM_A_Main')])
    assert gaps == {2: 'UCX_SM_A_Main_001', 1: 'UCX_SM_A_Main_002', 3: 'UCX_SM_A_Main_003'}  # unnumbered last


@pytest.mark.parametrize('old', ['UCX_SM_Tverskaya_12', '1st_Main', '12_Lenina_Main'])
def test_u3_address_is_never_trimmed(old):
    """Measured: `UCX_SM_Tverskaya_12` -> `UCX_SM_Tverskaya_001`, `1st_Main` -> `UCX_st_Main_001`."""
    red_green(lambda r: r[1] == old, lambda: source_ucx_rename([(1, old)]), lambda: impl_ucx_rename([(1, old)]))


@pytest.mark.parametrize('old,new', [('UCX_SM_Tverskaya_12_Main_4', 'UCX_SM_Tverskaya_12_Main_001'),
                                     ('UCX_SM_1st_Main', 'UCX_SM_1st_Main_001'),
                                     ('UCX_SM_Tverskaya_12_Ground_7', 'UCX_SM_Tverskaya_12_Ground_001')])
def test_u3_address_digits_survive(old, new):
    assert impl_ucx_rename([(1, old)])[1] == new


def test_u3_name_without_kind_is_refused_not_damaged():
    plan = nc.ucx_plan([{'key': 1, 'name': 'UCX_SM_Tverskaya_12', 'geometry': True}])
    assert not plan['rename'] and 'Main/_Ground' in plan['skipped'][0]['reason']
    assert source_ucx_rename([(1, 'UCX_SM_Tverskaya_12')])[1] == 'UCX_SM_Tverskaya_001'  # the measured damage


@pytest.mark.parametrize('old,new', [('ucx_SM_A_Main_7', 'UCX_SM_A_Main_001'),
                                     ('Ucx_ucx_SM_A_Main_02', 'UCX_SM_A_Main_001'),
                                     ('UCX_SM_UCX_Annex_Main_001', 'UCX_SM_UCX_Annex_Main_001'),
                                     ('UCX_sm_A_main_5', 'UCX_SM_A_Main_001'),
                                     ('UCX_A_Ground_3', 'UCX_SM_A_Ground_001')])
def test_u4_prefix_any_case_inner_ucx_kept(old, new):
    red_green(lambda r: r[1] == new, lambda: source_ucx_rename([(1, old)]), lambda: impl_ucx_rename([(1, old)]))


def test_u4_digits_only_name_is_refused():
    red_green(lambda r: r[1] == '123', lambda: source_ucx_rename([(1, '123')]), lambda: impl_ucx_rename([(1, '123')]))
    assert source_ucx_rename([(1, '123')])[1] == 'UCX__001'  # measured
    plan = nc.ucx_plan([{'key': 1, 'name': 'UCX_123', 'geometry': True},
                        {'key': 2, 'name': 'UCX_SM_12_Main_001', 'geometry': True}])
    assert not plan['rename'] and not plan['unchanged'] and len(plan['skipped']) == 2


def test_u5_grammar_width_and_unselected_numbers():
    sel = [(1, 'UCX_SM_A_Main_5'), (2, 'UCX_SM_A_Main_6')]
    unsel = ['UCX_SM_A_Main_01', 'UCX_SM_A_Main_001']
    out = impl_ucx_rename(sel, unsel)
    assert out == {1: 'UCX_SM_A_Main_002', 2: 'UCX_SM_A_Main_003'}  # 001 is held by an unselected node
    assert all(MASK.fullmatch(n) for n in out.values())
    with pytest.raises(ValueError):
        nc.ucx_name('A', 'Main', 1000)
    with pytest.raises(ValueError):
        nc.ucx_name('A', 'Roof', 1)


def test_u5_more_than_999_pieces_is_an_error_and_nothing_renamed():
    items = [{'key': i, 'name': 'UCX_SM_A_Main_{}'.format(i), 'geometry': True} for i in range(1, 1001)]
    items.append({'key': 5000, 'name': 'UCX_SM_A_Ground_9', 'geometry': True})
    plan = nc.ucx_plan(items)
    assert len(plan['errors']) == 1 and plan['errors'][0]['group'] == 'UCX_SM_A_Main' and len(plan['errors'][0]['keys']) == 1000
    assert plan['rename'] == [{'key': 5000, 'old': 'UCX_SM_A_Ground_9', 'new': 'UCX_SM_A_Ground_001'}]


def test_ucx_acceptance_scene_and_idempotence():
    """L01 minimal acceptance on the core: model + helper skipped, stable order, mask, second run unchanged."""
    sel = [(1, 'SM_Addr_Main'), (2, 'UCX_SM_Addr_Main_003'), (3, 'UCX_SM_Addr_Main_001'), (4, 'ucx_SM_Addr_Main_7'),
           (5, 'UCX_SM_Addr_Ground_01'), (6, 'Point001')]
    geo = {6: False}
    first = impl_ucx_rename(sel, geometry=geo)
    assert first == {1: 'SM_Addr_Main', 2: 'UCX_SM_Addr_Main_002', 3: 'UCX_SM_Addr_Main_001',
                     4: 'UCX_SM_Addr_Main_003', 5: 'UCX_SM_Addr_Ground_001', 6: 'Point001'}
    assert all(MASK.fullmatch(first[k]) for k in (2, 3, 4, 5))
    again = nc.ucx_plan([{'key': k, 'name': n, 'geometry': geo.get(k, True)} for k, n in first.items()])
    assert again['rename'] == [] and len(again['unchanged']) == 4
    assert source_ucx_rename(sel)[1] != 'SM_Addr_Main'  # the source renames the render model (RED)


def test_ucx_mask_is_the_names_check_mask():
    """One grammar: every produced name passes checks_core (the 0.5.0 names check) for VPM."""
    for n in ('UCX_SM_A_Main_001', 'UCX_SM_Tverskaya_12_Ground_999'):
        assert nc.UCX_MASK.fullmatch(n)
        assert [c for c, _ in cc.name_findings(n, 'SM', 'vpm') if c not in ('name_case', 'name_digits')] == []


# ---- qa.names_fix: masks --------------------------------------------------------------------------------
@pytest.mark.parametrize('raw,model,name', [
    ('SM_Test_001_Main', 'npm', 'SM_Test_001_Main'),
    ('sm_Test_1_main', 'npm', 'SM_Test_001_Main'),
    ('Test_02_MainGlass', 'npm', 'SM_Test_002_MainGlass'),
    (' SM_Test Street_Ground ', 'npm', 'SM_Test_Street_Ground'),
    ('SM_Тverskaya_Main', 'vpm', 'SM_Tverskaya_Main'),        # Cyrillic Т homoglyph in a Latin word
    ('SM_Тверская_Main', 'vpm', 'SM_Tverskaya_Main'),          # Russian word transliterated
    ('SM_Test\u200b_Ground', 'vpm', 'SM_Test_Ground'),
])
def test_parse_object_repairs_only_unambiguous_parts(raw, model, name):
    got = nc.parse_object(raw, model)
    assert isinstance(got, dict) and got['name'] == name, got


@pytest.mark.parametrize('raw,model,word', [('Box001', 'npm', 'geometry type'), ('SM_Test_Main', 'npm', 'OKS'),
                                            ('SM_Test_021_Main', 'npm', '001..020'),
                                            ('SM_Test_GroundEl', 'vpm', 'VPM has no'), ('SM_007_Main', 'npm', 'Address'),
                                            ('UCX_SM_A_Main_001', 'vpm', 'not an SM')])
def test_parse_object_refuses_with_a_reason(raw, model, word):
    got = nc.parse_object(raw, model)
    assert isinstance(got, str) and word in got, got


def test_masks_pass_the_names_check():
    npm = nc.parse_object('SM_Test_001_Main', 'npm')
    vg = nc.parse_object('SM_Test_Ground', 'vpm')
    vm = nc.parse_object('SM_Test_Main', 'vpm')
    names = [(nc.material_name(npm, 2), 'M', 'npm'), (nc.texture_stem(npm, 'npm', 'diffuse', 2) + '.png', 'T', 'npm'),
             (nc.texture_stem(vg, 'vpm', 'roughness', 1, 1003) + '.png', 'T', 'vpm'),
             (nc.texture_stem(vm, 'vpm', 'normal', 3) + '.png', 'T', 'vpm'), (nc.material_name(vg, 1), 'M', 'vpm')]
    assert names[1][0] == 'T_Test_001_Main_d_2.png' and names[2][0] == 'T_Test_Ground_ERM_1.1003.png'
    assert names[3][0] == 'T_Test_Normal_3.1001.png' and names[0][0] == 'M_Test_001_Main_2'
    for n, role, model in names:
        assert cc.name_findings(n, role, model) == [], (n, cc.name_findings(n, role, model))
    assert nc.texture_stem(vm, 'vpm', 'opacity', 1) is None  # VPM has no opacity map mask


# ---- qa.names_fix: source model (L03 measurements) --------------------------------------------------------
def source_cloner(state, donor):
    """Material Cloner: object names unchanged; each target with `_NNN_` gets the donor material (its own
    replaced), the index replaced in the WHOLE path, file copied if it exists and the destination does not,
    map repointed regardless; Listener-only reporting (no result)."""
    files = {p: dict(i) for p, i in state['files'].items()}
    d = next(o for o in state['objects'] if o['name'] == donor)
    di = re.search(r'_(\d{3})_', d['name']).group(1)
    out = {'objects': {}, 'maps': {}, 'materials': {}, 'files': files, 'report': None}
    for o in state['objects']:
        out['objects'][o['key']] = o['name']
        m = re.search(r'_(\d{3})_', o['name'])
        if o is d or not m:
            continue
        out['materials'][o['key']] = 'donor'
        for mp in d['material']['maps']:
            new = mp['path'].replace('_' + di + '_', '_' + m.group(1) + '_')
            if files.get(mp['path'], {}).get('exists') and not files.get(new, {}).get('exists'):
                if Path(new).parent == Path(mp['path']).parent:
                    files[new] = dict(files[mp['path']])
            out['maps'][(o['key'], mp['role'])] = new
    return out


def _mat(name, maps):
    return {'name': name, 'class': 'PhysicalMaterial', 'subs': None,
            'maps': [{'key': k, 'role': r, 'path': p, 'name': 'map'} for k, r, p in maps]}


def _scene(tmp='C:/proj/tex'):
    """L03 acceptance scene: donor with D/ERM(N in folder _001_)/missing, targets _002_/_003_, no-index, own."""
    donor = _mat('Donor', [('base_color_map', 'diffuse', tmp + '/T_Test_001_Main_d_1.png'),
                           ('bump_map.normal_map', 'normal', tmp + '/_001_/T_Test_001_Main_n_1.png'),
                           ('roughness_map', 'roughness', tmp + '/T_Test_001_Main_r_1.png')])
    objects = [{'key': 1, 'name': 'SM_Test_001_Main', 'geometry': True, 'ucx': False, 'model': None, 'material': donor},
               {'key': 2, 'name': 'SM_Test_002_Main', 'geometry': True, 'ucx': False, 'model': None, 'material': None},
               {'key': 3, 'name': 'SM_Test_003_Main', 'geometry': True, 'ucx': False, 'model': None, 'material': None},
               {'key': 4, 'name': 'Box001', 'geometry': True, 'ucx': False, 'model': None, 'material': None},
               {'key': 5, 'name': 'SM_Test_004_Main', 'geometry': True, 'ucx': False, 'model': None,
                'material': _mat('Own', [('base_color_map', 'diffuse', tmp + '/own.png')])}]
    files = {tmp + '/T_Test_001_Main_d_1.png': {'exists': True, 'sha256': 'd' * 64},
             tmp + '/_001_/T_Test_001_Main_n_1.png': {'exists': True, 'sha256': 'n' * 64},
             tmp + '/T_Test_001_Main_r_1.png': {'exists': False, 'sha256': None},
             tmp + '/own.png': {'exists': True, 'sha256': 'o' * 64},
             tmp + '/T_Test_003_Main_d_1.png': {'exists': True, 'sha256': '3' * 64}}
    return {'objects': objects, 'files': files, 'export_names': []}


def _plan(state=None, **opts):
    opts.setdefault('donor', 'SM_Test_001_Main')
    return nc.names_fix_plan(state or _scene(), opts)


def test_n2_objects_and_materials_get_mask_names():
    plan = _plan()
    red_green(lambda names: names.get(4) is None and names.get(2) == 'SM_Test_002_Main' and 'M_Test_002_Main_1' in names.values(),
              lambda: {**source_cloner(_scene(), 'SM_Test_001_Main')['objects'], 4: 'Box001'},
              lambda: {**{o['key']: o['new'] for o in plan['objects']},
                       **{100 + i: m['new'] for i, m in enumerate(plan['materials']) if m.get('new')}})
    assert {o['new'] for o in plan['objects']} == {'SM_Test_001_Main', 'SM_Test_002_Main', 'SM_Test_003_Main',
                                                   'SM_Test_004_Main'}
    assert nc.check_names(plan, cc) == []


def test_n3_mask_only_in_the_file_name_never_in_folders():
    src = source_cloner(_scene(), 'SM_Test_001_Main')['maps']
    impl = {(f['key'], f['role']): f['target'] for f in _plan()['files']}
    red_green(lambda maps: all('/_001_/' in p for (k, role), p in maps.items() if role == 'normal'),
              lambda: src, lambda: impl)
    assert impl[(2, 'normal')] == 'C:/proj/tex/_001_/T_Test_002_Main_n_1.png'


def test_n4_never_repointed_to_a_missing_file():
    state = _scene()
    src = source_cloner(state, 'SM_Test_001_Main')

    def ok(result):
        files, maps = result
        return all(files.get(p, {}).get('exists') for p in maps.values() if p is not None)
    plan = _plan(state)
    after = dict(state['files'])
    impl_maps = {}
    for f in plan['files']:
        if f['action'] == 'copy':
            after[f['target']] = {'exists': True}
        impl_maps[(f['key'], f['role'])] = None if f['action'].startswith('clear') else f['target']
    red_green(ok, lambda: (src['files'], src['maps']), lambda: (after, impl_maps))
    missing = [x for x in plan['failures'] if 'source file missing' in x['reason']]
    assert {x['key'] for x in missing} == {1, 2, 3}  # the donor's own copy too


def test_n5_existing_destination_is_reused_not_overwritten():
    rows = {(f['key'], f['role']): f for f in _plan()['files']}
    r = rows[(3, 'diffuse')]
    assert r['action'] == 'reuse existing file (not overwritten)' and r['same_content'] is False
    assert r['target_sha256'] == '3' * 64
    # the lab did not reproduce "Cloner overwrites": the source also keeps it (no RED here, invariant only)
    assert source_cloner(_scene(), 'SM_Test_001_Main')['files']['C:/proj/tex/T_Test_003_Main_d_1.png']['sha256'] == '3' * 64


def test_n6_own_material_is_not_replaced_silently():
    src = source_cloner(_scene(), 'SM_Test_001_Main')
    kept = _plan()
    red_green(lambda r: r.get(5) != 'donor', lambda: src['materials'],
              lambda: {o['key']: o['material_source'] for o in kept['objects']})
    assert {'key': 5, 'material': 'Own', 'action': 'kept (own material)', 'donor': 'SM_Test_001_Main'} in kept['materials']
    replaced = _plan(replace_material=True)
    assert [m for m in replaced['materials'] if m.get('action') == 'replaced by donor'][0]['key'] == 5


def test_n7_every_failure_and_skip_is_in_the_result():
    assert source_cloner(_scene(), 'SM_Test_001_Main')['report'] is None
    plan = _plan()
    assert [s['item'] for s in plan['skipped']] == ['Box001'] and plan['skipped'][0]['reason']
    reasons = ' | '.join(f['reason'] for f in plan['failures'])
    assert 'T_Test_001_Main_r_1.png' in reasons


def test_names_fix_report_fits_the_edit_contract():
    plan = _plan()
    rep = ec.report('qa.names_fix', 'preview', [ec.entry(o['key'], o['old']) for o in plan['objects']],
                    done=plan['objects'], skipped_=[ec.skipped(s['item'], s['reason']) for s in plan['skipped']],
                    ambiguous=plan['ambiguous'], state_hash=ec.fingerprint(_scene()), extra={'files': plan['files']})
    assert ec.check_preview('qa.names_fix', rep) is rep


def test_names_fix_vpm_ground_udim_and_multimaterial_slots():
    def sub(sid, name, path, used=True):
        return {'id': sid, 'used': used, 'name': name, 'class': 'PhysicalMaterial',
                'maps': [{'key': 'base_color_map', 'role': 'diffuse', 'path': path, 'name': 'x'},
                         {'key': 'roughness_map', 'role': 'roughness', 'path': path[:-4] + 'r.png', 'name': 'y'}]}
    mat = {'name': 'Multi', 'class': 'MultiMaterial', 'maps': None,
           'subs': [sub(9, 'b', 'D:/t/grass.1002.png'), sub(3, 'a', 'D:/t/road.png'), sub(4, 'unused', 'D:/t/u.png', False)]}
    state = {'objects': [{'key': 7, 'name': 'SM_Lenina_5_Ground', 'geometry': True, 'ucx': False, 'model': 'vpm',
                          'material': mat}],
             'files': {p: {'exists': True, 'sha256': 'a' * 64} for p in ('D:/t/grass.1002.png', 'D:/t/road.png',
                                                                        'D:/t/grass.1002r.png', 'D:/t/roadr.png')},
             'export_names': []}
    plan = nc.names_fix_plan(state, {})
    mats = {m['old']: m['new'] for m in plan['materials']}
    assert mats == {'Multi': 'M_Lenina_5_Ground', 'a': 'M_Lenina_5_Ground_1', 'b': 'M_Lenina_5_Ground_2'}
    targets = sorted(f['target'] for f in plan['files'])
    assert targets == ['D:/t/T_Lenina_5_Ground_Diffuse_1.1001.png', 'D:/t/T_Lenina_5_Ground_Diffuse_2.1002.png',
                       'D:/t/T_Lenina_5_Ground_ERM_1.1001.png', 'D:/t/T_Lenina_5_Ground_ERM_2.1001.png']
    assert nc.check_names(plan, cc) == []


def test_names_fix_repeat_run_and_duplicate_targets_are_ambiguous():
    state = _scene()
    state['export_names'] = ['SM_Test_002_Main']
    state['objects'].append(dict(state['objects'][1], key=9, name='sm_Test_2_main'))
    plan = _plan(state)
    items = {a['item']: a for a in plan['ambiguous']}
    assert 'SM_Test_002_Main' in items and 'repeat run' in items['SM_Test_002_Main']['reason']
    assert all(o['new'] != 'SM_Test_002_Main' for o in plan['objects'])


def test_names_fix_ucx_shares_the_ucx_grammar():
    state = {'objects': [{'key': 1, 'name': 'ucx_SM_A_Main_7', 'geometry': True, 'ucx': True, 'model': None, 'material': None},
                         {'key': 2, 'name': 'UCX_box', 'geometry': True, 'ucx': True, 'model': None, 'material': None}],
             'files': {}, 'export_names': []}
    plan = nc.names_fix_plan(state, {'model': 'vpm'})
    assert plan['objects'] == [{'key': 1, 'old': 'ucx_SM_A_Main_7', 'new': 'UCX_SM_A_Main_001', 'kind': 'ucx'}]
    assert plan['skipped'][0]['item'] == 'UCX_box'


def test_names_fix_options_are_checked():
    with pytest.raises(ValueError):
        nc.names_fix_plan(_scene(), {'model': 'abc'})
    with pytest.raises(ValueError):
        nc.names_fix_plan(_scene(), {'donor': 'Nope'})
    with pytest.raises(ValueError):
        nc.names_fix_plan(_scene(), {'replace_material': 'yes'})


def test_target_path_keeps_folder_and_separator():
    assert nc.target_path('C:\\p\\_001_\\a.PNG', 'T_X_001_Main_d_1') == 'C:\\p\\_001_\\T_X_001_Main_d_1.png'
    assert nc.udim_of('x/T_A_Diffuse_1.1007.png') == 1007 and nc.udim_of('x/a_1101.png') is None


def test_glue_modules_load_without_pymxs():
    nm = _load('names_max.py', 'agr_tools_names_max_t')
    assert callable(nm.ucx_rename) and callable(nm.qa_names_fix)
