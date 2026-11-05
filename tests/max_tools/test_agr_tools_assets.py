"""new-case: AGR Tools `assets` module core (#1024): Flora/MAF source adapters, index cache, browser model,
import plan, layout, helper matching, journal (assets_core.py).

Plain pytest, no pymxs, synthetic names and files only (no A101 customer data in this repository). The Max side
(merge from the library copy, layers, materials, textures, undo) is proven by run_agr_tools_assets_native.py
through the AGR Lab runner on a copy of the library file.
Idea source (no code copied, #853): AlexYo Asset Importer 1.0.2, SHA256 4c910813...1db28a9d.
"""
import importlib.util
import json
import os
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / 'adapters/max/agr_tools'


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


core = _load(PKG / 'assets_core.py', 'agr_tools_assets_core_test')

# A synthetic Flora library laid out like the measured A101 file (job 20261106-015800-209bc0a3): per species a
# Text_ label, IMG_ preview planes, <base>_high / <base>_low meshes; one VIZ + third-party proxy; label-only rows.
FLORA_NAMES = [
    'Text_alpha_tree_t1_h500', 'IMG_alpha_tree_t1_h500_high', 'IMG_alpha_tree_t1_h500_low',
    'alpha_tree_t1_h500_high', 'alpha_tree_t1_h500_low',
    'Text_beta_bush_t2_h80', 'IMG_beta_bush_t2_h80_high', 'IMG_beta_bush_t2_h80_low',
    'beta_bush_t2_h80_high', 'beta_bush_t2_h80_low',
    'Text_gamma_vine_t1_h140', 'gamma_vine_t1_h140_high', 'gamma_vine_t1_h140_low', 'gamma_vine_t1_h140_VIZ',
    'CRP_gamma_vine_t1_h140_VIZ_PROXY',
    'Text_delta_flower_t1_h50',  # label without a model yet
    'zeta_shrub_t3_h40_high',   # high only
    'READY', 'P100',
]
PREVIEWS = ['alpha_tree_t1_h500', 'beta_bush_t2_h80', 'gamma_vine_t1_h140',
            'zeta_zeta_shrub_t3_h40',  # duplicated token, same tail -> fuzzy
            'omega_t9_h10']             # no model


def make_flora(tmp_path, names=FLORA_NAMES):
    root = tmp_path / 'flora'
    (root / 'PreviewFlora').mkdir(parents=True)
    (root / 'TextureFlora').mkdir()
    (root / 'LIB_TEST.max').write_bytes(b'synthetic max ' * 10)
    for p in PREVIEWS:
        (root / 'PreviewFlora' / (p + '_PREVIEW.png')).write_bytes(b'\x89PNG synthetic')
    return root


def make_maf_zip(path, base, with_json=True, versions=('high', 'low'), preview=True, maxfile=True):
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, 'w') as z:
        if maxfile:
            z.writestr(base + '.max', b'max')
        if preview:
            z.writestr(base + '.png', b'\x89PNG preview ' + base.encode())
        for v in versions:
            z.writestr(base + '_' + v + '.fbx', b'fbx')
            z.writestr('T_' + base + '_' + v + '_Diffuse.png', b'tex')
        if with_json:
            m, o, a = base.split('_', 2)
            z.writestr(base + '.json', json.dumps({
                'schema': 3, 'name': base, 'identity': {'manufacturer': m, 'object_name': o, 'article': a},
                'units': 'mm', 'versions': {v: True for v in versions},
                'geometry': {v: {'object_names': [base + '_' + v]} for v in versions}}))


# ---- names ----------------------------------------------------------------------------------------------------
def test_parse_flora_and_versions():
    p = core.parse_flora('alpha_tree_t1_h500_high')
    assert (p['base'], p['species'], p['variant'], p['height_cm'], p['ver']) == (
        'alpha_tree_t1_h500', 'alpha_tree', 1, 500, 'high')
    assert core.parse_flora('IMG_beta_bush_t2_h80_low')['prefix'] == 'IMG'
    assert core.parse_flora('CRP_gamma_vine_t1_h140_VIZ_PROXY')['ver'] == 'viz_proxy'
    assert core.parse_flora('READY') is None
    assert core.version_of('alpha_tree_t1_h500_high001') == 'high'
    assert core.version_of('Some_Thing_low') == 'low' and core.version_of('Plain') is None


def test_parse_maf_q28():
    p = core.parse_maf('Adx_StolLidiya_13001-1_high')
    assert (p['manufacturer'], p['title'], p['article'], p['base']) == ('Adx', 'StolLidiya', '13001-1',
                                                                        'Adx_StolLidiya_13001-1')
    assert core.parse_maf('Adx_Naves_40184.1')['article'] == '40184.1'
    assert core.parse_maf('OnlyTwo_Parts') is None


# ---- Flora adapter -----------------------------------------------------------------------------------------------
def test_flora_records_groups_helpers_proxies_and_previews(tmp_path):
    root = make_flora(tmp_path)
    previews = core._preview_names(str(root), 'PreviewFlora')
    recs, rep = core.flora_records('flora_t', FLORA_NAMES, previews)
    by = {r['name']: r for r in recs}
    assert sorted(by) == ['alpha_tree_t1_h500', 'beta_bush_t2_h80', 'gamma_vine_t1_h140', 'zeta_shrub_t3_h40']
    # helpers (Text_/IMG_) are never import objects
    assert by['alpha_tree_t1_h500']['versions'] == {'high': {'objects': ['alpha_tree_t1_h500_high']},
                                                    'low': {'objects': ['alpha_tree_t1_h500_low']}}
    assert by['gamma_vine_t1_h140']['extra_versions'] == {'viz': ['gamma_vine_t1_h140_VIZ']}
    assert list(by['zeta_shrub_t3_h40']['versions']) == ['high']
    assert core.badge(by['zeta_shrub_t3_h40']) == '[H]' and core.badge(by['beta_bush_t2_h80']) == '[H][L]'
    assert by['zeta_shrub_t3_h40']['preview_match'] == 'fuzzy'
    assert rep['labels_without_model'] == ['delta_flower_t1_h50']
    assert rep['third_party_proxies'] == ['CRP_gamma_vine_t1_h140_VIZ_PROXY']
    assert rep['foreign_objects'] == ['P100', 'READY']
    assert rep['previews_unused'] == ['omega_t9_h10']
    assert rep['preview_match'] == {'exact': 3, 'fuzzy': 1, 'none': 0}


def test_fuzzy_preview_needs_the_same_type_and_height(tmp_path):
    recs, _ = core.flora_records('f', ['zeta_shrub_t3_h40_high'], {'zeta_zeta_shrub_t2_h40': 'p.png'})
    assert recs[0]['preview'] is None and recs[0]['preview_match'] == 'none'


def test_scan_flora_index_roundtrip_and_cached_names(tmp_path):
    root = make_flora(tmp_path)
    cache = tmp_path / 'cache'
    idx = core.scan_flora(str(root), FLORA_NAMES, lib='flora_t')
    src = idx['sources']['LIB_TEST.max']
    assert src['sha256'] == core.sha256_file(str(root / 'LIB_TEST.max'))
    assert all(r['source'] == {'path': 'LIB_TEST.max', 'sha256': src['sha256']} for r in idx['assets'])
    core.save_index(str(cache), idx)
    back = core.load_index(str(cache), 'flora_t')
    assert back['assets'] == idx['assets'] and back['schema'] == core.INDEX_SCHEMA
    assert core.flora_needs_names(str(root), back) is False
    # same size, new mtime -> names must be read again
    os.utime(root / 'LIB_TEST.max', (1, 1))
    assert core.flora_needs_names(str(root), back) is True
    assert core.preview_abspath(back, back['assets'][0], str(cache)).endswith('_PREVIEW.png')


def test_flora_layout_rejects_two_max_files(tmp_path):
    root = make_flora(tmp_path)
    (root / 'second.max').write_bytes(b'x')
    with pytest.raises(ValueError, match='exactly one .max'):
        core.flora_layout(str(root))


def test_load_index_rejects_foreign_schema(tmp_path):
    core.write_json_atomic(core.index_path(str(tmp_path), 'x'), {'schema': 'other/9'})
    with pytest.raises(ValueError, match='unsupported index schema'):
        core.load_index(str(tmp_path), 'x')


# ---- MAF adapter ---------------------------------------------------------------------------------------------------
def test_scan_maf_recursive_sidecar_preview_and_broken_zip(tmp_path):
    lib = tmp_path / 'maf'
    make_maf_zip(lib / 'Adx_Stol_13001-1.zip', 'Adx_Stol_13001-1')
    # subfolder: the AlexYo 1.0.2 scan (os.listdir of the root) does not see these
    make_maf_zip(lib / 'sub' / 'Mst_Kachalka_161100.zip', 'Mst_Kachalka_161100', with_json=False,
                 versions=('high',))
    (lib / 'Bad_Zip_1.zip').write_bytes(b'not a zip, still syncing')
    make_maf_zip(lib / 'NoName.zip', 'NoName', with_json=False, preview=False, maxfile=False)
    cache = tmp_path / 'cache'
    idx = core.scan_maf(str(lib), str(cache), lib='maf_t')
    by = {r['name']: r for r in idx['assets']}
    assert sorted(by) == ['Adx_Stol_13001-1', 'Mst_Kachalka_161100', 'NoName']
    a = by['Adx_Stol_13001-1']
    assert (a['manufacturer'], a['title'], a['article']) == ('Adx', 'Stol', '13001-1')
    assert a['meta']['units'] == 'mm' and set(a['versions']) == {'high', 'low'}
    assert (cache / a['preview']).read_bytes().endswith(b'Adx_Stol_13001-1')
    k = by['Mst_Kachalka_161100']
    assert k['source']['path'] == 'sub/Mst_Kachalka_161100.zip' and list(k['versions']) == ['high']
    assert 'name is not Manufacturer_Object_Article (Q28)' in by['NoName']['warnings']
    assert 'no .max in the archive (FBX only)' in by['NoName']['warnings']
    assert [p['path'] for p in idx['report']['problems']] == ['Bad_Zip_1.zip']
    assert idx['report']['with_sidecar'] == 1
    assert a['source']['sha256'] is None  # MAF: hashed at import, not at scan (GB of zips on a streamed Drive)


def test_scan_maf_reuses_unchanged_archives(tmp_path, monkeypatch):
    lib, cache = tmp_path / 'maf', tmp_path / 'cache'
    make_maf_zip(lib / 'Adx_Stol_1.zip', 'Adx_Stol_1')
    first = core.scan_maf(str(lib), str(cache), lib='m')
    calls = []
    real = core.inspect_maf_zip
    monkeypatch.setattr(core, 'inspect_maf_zip', lambda *a: calls.append(a) or real(*a))
    again = core.scan_maf(str(lib), str(cache), lib='m', old_index=first)
    assert calls == [] and again['assets'] == first['assets']
    make_maf_zip(lib / 'Adx_Stol_2.zip', 'Adx_Stol_2')
    third = core.scan_maf(str(lib), str(cache), lib='m', old_index=again)
    assert len(calls) == 1 and len(third['assets']) == 2


def test_maf_sidecar_identity_mismatch_is_reported(tmp_path):
    lib = tmp_path / 'maf'
    lib.mkdir()
    with zipfile.ZipFile(lib / 'Adx_Stol_1.zip', 'w') as z:
        z.writestr('Adx_Stol_1.json', json.dumps({'identity': {'manufacturer': 'Adx', 'object_name': 'Stul',
                                                                'article': '1'}}))
        z.writestr('Adx_Stol_1_high.fbx', b'f')
    idx = core.scan_maf(str(lib), str(tmp_path / 'c'), lib='m')
    assert 'sidecar identity differs from the file name' in idx['assets'][0]['warnings']


# ---- browser model -------------------------------------------------------------------------------------------------
def test_search_tokens_fields_and_yo(tmp_path):
    recs = [core.make_record('m', 'maf', 'Adx_Stol_13001-1', manufacturer='Adx', title='Stol', article='13001-1'),
            core.make_record('m', 'maf', 'Mst_Kachalka_161100', manufacturer='Mst', title='Kachalka',
                             article='161100', meta={'title': 'Качалка зелёная'}),
            core.make_record('f', 'flora', 'alpha_tree_t1_h500', species='alpha_tree', variant=1, height_cm=500)]
    names = lambda q: [r['name'] for r in core.search(recs, q)]  # noqa: E731
    assert names('') == [r['name'] for r in recs]
    assert names('adx 13001') == ['Adx_Stol_13001-1']
    assert names('13001-1') == ['Adx_Stol_13001-1']
    assert names('зеленая') == ['Mst_Kachalka_161100']
    assert names('alpha h500') == ['alpha_tree_t1_h500']
    assert names('alpha h80') == []


def test_selection_toggle_order_and_prune():
    s = core.Selection(['a', 'b', 'a'])
    assert s.ids == ['a', 'b']
    assert s.toggle('c') is True and s.toggle('a') is False and s.ids == ['b', 'c']
    s.keep_only({'c'})
    assert s.ids == ['c']
    s.clear()
    assert s.ids == []


def test_settings_defaults_and_validation():
    s = core.merge_settings({'materials': 'copy', 'unknown': 1})
    assert s['materials'] == 'copy' and 'unknown' not in s and s['versions'] == ['high', 'low']
    for bad in ({'materials': 'x'}, {'textures': 'x'}, {'versions': []}, {'versions': ['mid']},
                {'fbx_scale': 0}):
        with pytest.raises(ValueError):
            core.merge_settings(bad)


# ---- import plan -------------------------------------------------------------------------------------------------
def test_import_plan_skips_scene_duplicates_and_missing_versions(tmp_path):
    idx = core.scan_flora(str(make_flora(tmp_path)), FLORA_NAMES, lib='flora_t')
    ids = ['flora_t:alpha_tree_t1_h500', 'flora_t:zeta_shrub_t3_h40', 'flora_t:nope']
    plan = core.import_plan(idx, ids, in_scene={('flora_t:alpha_tree_t1_h500', 'low')})
    st = [(r['id'].split(':')[1], r.get('version'), r['status']) for r in plan]
    assert st == [('alpha_tree_t1_h500', 'high', 'merge'), ('alpha_tree_t1_h500', 'low', 'already_in_scene'),
                  ('zeta_shrub_t3_h40', 'high', 'merge'), ('zeta_shrub_t3_h40', 'low', 'no_version'),
                  ('nope', None, 'not_in_index')]
    m = plan[0]
    assert m['objects'] == ['alpha_tree_t1_h500_high'] and m['layer'] == 'ASSET_flora_t_high'
    assert m['props'][core.PROP_ID] == 'flora_t:alpha_tree_t1_h500' and m['props'][core.PROP_SHA]
    assert core.plan_hash(plan) == core.plan_hash(json.loads(json.dumps(plan)))


def test_texture_plan_project_copy_library_and_conflicts(tmp_path):
    lib = tmp_path / 'TextureFlora'
    lib.mkdir()
    (lib / 'Alpha_high.png').write_bytes(b'1234')
    (lib / 'beta_low.png').write_bytes(b'12')
    proj = tmp_path / 'proj'
    proj.mkdir()
    (proj / 'beta_low.png').write_bytes(b'different size')
    old = ['G:\\OLD\\FLORA\\TextureFlora\\alpha_high.png', 'D:\\x\\beta_low.png', 'D:\\x\\gone.png', '']
    tp = core.texture_plan(old, [str(lib)], str(proj))
    assert tp['map'] == {old[0]: str(proj / 'Alpha_high.png')}
    assert tp['copy'] == [(str(lib / 'Alpha_high.png'), str(proj / 'Alpha_high.png'))]
    assert tp['missing'] == [old[2]] and tp['conflicts'] == [str(proj / 'beta_low.png')]
    lib_only = core.texture_plan(old, [str(lib)])
    assert lib_only['map'][old[1]] == str(lib / 'beta_low.png') and lib_only['copy'] == []


def _overlap(a, b):
    return all(a[0][i] < b[1][i] and b[0][i] < a[1][i] for i in (0, 1))


def test_layout_rows_from_origin_no_overlap_and_wrap():
    def box(x, y, w, d, piv_z=0.0, zmin=-0.1):
        return ([x, y, zmin], [x + w, y + d, 3.0], [x + w / 2, y + d / 2, piv_z])
    groups = [{'id': 'a', 'boxes': {'high': box(24, -24, 5, 4, 0.0), 'low': box(48, -24, 5, 4, 0.0)}},
              {'id': 'b', 'boxes': {'high': box(24, -100, 1, 1, 0.2)}},
              {'id': 'c', 'boxes': {'high': box(24, -8, 3, 2), 'low': box(48, -8, 3, 2)}}]
    mv = core.layout_rows(groups, gap_m=1.0, row_limit_m=8.0)
    placed = []
    for g in groups:
        for v, (lo, hi, piv) in g['boxes'].items():
            dx, dy, dz = mv[g['id']][v]
            placed.append(([lo[0] + dx, lo[1] + dy], [hi[0] + dx, hi[1] + dy]))
            assert abs(piv[2] + dz) < 1e-12  # pivot on z = 0
    assert placed[0][0] == [0.0, 0.0]          # first High at the origin
    assert placed[1][0] == [0.0, 5.0]          # its Low behind it (+Y, gap 1)
    assert placed[2][0] == [6.0, 0.0]          # next column
    assert placed[3][0] == [0.0, 10.0]         # wrapped: 6 + 1 + 3 > 8 -> new band after depth 9 + gap
    for i in range(len(placed)):
        for j in range(i + 1, len(placed)):
            assert not _overlap(placed[i], placed[j])


# ---- matching helpers ("Сопоставить") ---------------------------------------------------------------------------------
def _two_indexes(tmp_path):
    flora = core.scan_flora(str(make_flora(tmp_path)), FLORA_NAMES + ['alpha_tree_t2_h300_high'], lib='flora_t')
    maf = core.new_index('maf_t', 'maf_zip', '/x', [
        core.make_record('maf_t', 'maf', 'Mst_Kachalka_161100'),
        core.make_record('maf_t', 'maf', 'Adx_Stol_13001-1')], {}, {})
    return flora, maf


def test_match_names_exact_prefix_ambiguous_missing_and_dup_tail(tmp_path):
    flora, maf = _two_indexes(tmp_path)
    names = ['beta_bush', 'beta_bush', 'alpha_tree', 'Mst_Kachalka_161100', 'Mst_Kachalka_161100001',
             'adx_stol_13001-1_high', 'lipa_unknown', 'zeta_shrub_t3_h40_high002']
    m = core.match_names(names, [flora, maf])
    n = m['names']
    assert n['beta_bush'] == {'count': 2, 'ids': ['flora_t:beta_bush_t2_h80'], 'via': 'prefix',
                              'status': 'matched'}
    assert n['alpha_tree']['status'] == 'ambiguous' and len(n['alpha_tree']['ids']) == 2
    # the article ends in digits: the full name is kept; a Max duplicate tail is stripped only when needed
    assert n['Mst_Kachalka_161100']['count'] == 2 and n['Mst_Kachalka_161100']['via'] == 'exact'
    assert n['adx_stol_13001-1']['ids'] == ['maf_t:Adx_Stol_13001-1']
    assert n['zeta_shrub_t3_h40']['status'] == 'matched'
    assert n['lipa_unknown']['status'] == 'missing'
    assert m['totals'] == {'matched': 6, 'ambiguous': 1, 'missing': 1} and m['green'] is False
    al = core.match_names(['alpha_tree'], [flora], aliases={'alpha_tree': 'alpha_tree_t1_h500'})
    assert al['names']['alpha_tree']['via'] == 'alias' and al['green'] is True


def test_reconcile_spec_and_add_to_library_tasks(tmp_path):
    flora, maf = _two_indexes(tmp_path)
    m = core.match_names(['beta_bush'] * 3 + ['Mst_Kachalka_161100', 'extra_thing_t1_h1_high'], [flora, maf])
    rep = core.reconcile_spec([{'name': 'beta_bush', 'qty': 3}, {'name': 'Mst_Kachalka_161100', 'qty': 2},
                               {'name': 'new_species', 'qty': 4}, {'name': 'Adx_Stol_13001-1', 'qty': 1}], m, [flora, maf])
    assert [(r['name'], r['status']) for r in rep['rows']] == [
        ('beta_bush', 'ok'), ('Mst_Kachalka_161100', 'short'), ('new_species', 'not_in_library'),
        ('Adx_Stol_13001-1', 'no_helpers')]
    assert rep['tasks'] == [{'task': 'add_to_library', 'name': 'new_species', 'qty': 4}]
    assert rep['helpers_not_in_spec'] == ['extra_thing_t1_h1'] and rep['green'] is False


def test_placement_rows_rotation_rules(tmp_path):
    flora, maf = _two_indexes(tmp_path)
    helpers = [{'name': 'beta_bush', 'x': 1, 'y': 2, 'rotation_deg': 33},
               {'name': 'Mst_Kachalka_161100001', 'x': 5, 'y': 6, 'rotation_deg': 90},
               {'name': 'alpha_tree', 'x': 0, 'y': 0}]  # ambiguous: no row
    m = core.match_names([h['name'] for h in helpers], [flora, maf])
    kind = {r['id']: r['kind'] for idx in (flora, maf) for r in idx['assets']}.get
    rows = core.placement_rows(helpers, m, kind)
    assert [(r['model'], r['rotation_deg']) for r in rows] == [('beta_bush_t2_h80', 0.0),
                                                               ('Mst_Kachalka_161100', 90.0)]
    a = core.placement_rows(helpers, m, kind, seed=7)
    b = core.placement_rows(helpers, m, kind, seed=7)
    assert a == b and 0.0 <= a[0]['rotation_deg'] < 360.0 and a[1]['rotation_deg'] == 90.0
    assert set(rows[0]) >= {'id', 'model', 'x', 'y', 'rotation_deg'}  # place_core.schedule_plan row keys


# ---- journal / passport (K1) -------------------------------------------------------------------------------------------
def test_journal_line_path_and_append(tmp_path):
    p1 = core.journal_path('C:/proj/scene.max', str(tmp_path))
    assert p1 == core.journal_path('C:/proj/./scene.max', str(tmp_path))
    assert p1.replace('\\', '/').startswith(str(tmp_path).replace('\\', '/') + '/AGRTools/journal/')
    assert core.journal_path('', str(tmp_path)) != p1
    for _ in range(3):
        core.append_journal(p1, core.journal_line('assets.import', 'apply', 'done', {'merged': 2}, 'abc', 1.23456))
    lines = [json.loads(x) for x in Path(p1).read_text(encoding='utf-8').splitlines()]
    assert len(lines) == 3
    assert set(lines[0]) == {'ts', 'tool', 'mode', 'status', 'counts', 'preview_sha', 'duration', 'actor'}
    assert lines[0]['duration'] == 1.235 and lines[0]['actor'] == 'panel'


def test_passport_patch_does_not_mutate():
    p = {'id': 'X', 'assets': {'imports': [{'a': 1}]}}
    q = core.passport_patch(p, {'b': 2})
    assert p == {'id': 'X', 'assets': {'imports': [{'a': 1}]}}
    assert q['assets']['imports'] == [{'a': 1}, {'b': 2}]


def test_copy_material_names_replace_generic_max_names():
    assert core.is_generic_material_name('Material #25') and not core.is_generic_material_name('lipa_high')
    assert core.copy_material_name('a_high', set()) == 'a_high_copy'
    assert core.copy_material_name('a_high', {'a_high_copy', 'a_high_copy2'}) == 'a_high_copy3'
