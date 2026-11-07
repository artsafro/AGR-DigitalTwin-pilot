"""new-case: unified asset library for agents (#1024, assets_library.py + tools/assets/build_unified_library.py).
Synthetic names only; A101 is the truth, earlier catalogues are joined, nothing ambiguous is chosen silently."""
import importlib.util
import json
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


L = _load(ROOT / 'adapters/max/agr_tools/assets_library.py', 'agr_tools_assets_library_test')
C = _load(ROOT / 'adapters/max/agr_tools/assets_core.py', 'agr_tools_assets_core_lib_test')


def test_skeleton_absorbs_transliteration_variants():
    pairs = [('ryabinnik', 'riabinnik'), ('mozhzhevelnik', 'mojevelnik'), ('cheremukha', 'cheremuxa'),
             ('ryabinolistnyy', 'riabinolistniy'), ('boyaryshnik', 'boyarishnik')]
    for a, b in pairs:
        assert L.skeleton(a) == L.skeleton(b), (a, b)
    assert L.name_tokens('Рябинник рябинолистный') == [L.skeleton('riabinnik'), L.skeleton('riabinolistniy')]


CAT = {'library_file': 'C:/x/lib.max', 'species': [
    {'material_id': 101, 'latin': 'Tilia cordata', 'russian': 'Липа мелколистная', 'type': 'tree',
     'objects': {'NPM': 'Tilia_cordata_NPM'}, 'maps': {'review_status': 'approved'}},
    {'material_id': 212, 'latin': 'Sorbaria sorbifolia', 'russian': 'Рябинник рябинолистный', 'type': 'bush'},
    {'material_id': 219, 'latin': "Sorbaria sorbifolia 'Sem'", 'russian': 'Рябинник рябинолистный Сэм', 'type': 'bush'},
    {'material_id': 203, 'latin': 'Cornus alba', 'russian': 'Дёрен белый', 'type': 'bush'},
    {'material_id': 204, 'latin': 'Cornus sericea', 'russian': 'Дёрен отпрысковый', 'type': 'bush', 'npm_light': {}},
    {'material_id': 224, 'latin': 'Pinus mugo', 'russian': 'Сосна горная', 'type': 'bush'}]}


def test_match_species_levels():
    sp = CAT['species']
    assert L.match_species('riabinnik_riabinolistniy', sp) == {'level': 'exact', 'candidates': [1]}
    assert L.match_species('lipa', sp) == {'level': 'genus', 'candidates': [0]}
    assert L.match_species('deren', sp) == {'level': 'genus', 'candidates': [3, 4]}
    assert L.match_species('deren_belyy', sp)['level'] == 'exact'
    assert L.match_species('osoka_palmolistnaya', sp) == {'level': None, 'candidates': []}


def _flora_index(tmp_path, names):
    root = tmp_path / 'f'
    root.mkdir()
    (root / 'L.max').write_bytes(b'x')
    return C.scan_flora(str(root), names, lib='flora')


def test_unify_flora_truth_links_review_and_additions(tmp_path):
    idx = _flora_index(tmp_path, ['riabinnik_riabinolistniy_t1_h100_high', 'lipa_t1_h550_high',
                                  'deren_t1_h120_high', 'osoka_palmolistnaya_t1_h80_high'])
    u = L.unify_flora(idx, CAT, {'variants': [{'material_id': 204}]})
    by = {r['id']: r for r in u['records']}
    r = by['flora_a101:riabinnik_riabinolistniy_t1_h100']
    assert r['catalogue']['latin'] == 'Sorbaria sorbifolia' and r['catalogue']['level'] == 'exact'
    assert by['flora_a101:lipa_t1_h550']['catalogue']['level'] == 'genus'      # one candidate: linked, confirm
    assert 'catalogue' in by['flora_a101:deren_t1_h120'] and by['flora_a101:deren_t1_h120']['catalogue'] is None
    cands = by['flora_a101:deren_t1_h120']['catalogue_candidates']['candidates']
    assert [c['latin'] for c in cands] == ['Cornus alba', 'Cornus sericea'] and cands[1]['agent_light_npm']
    review = {x['id']: x for x in u['review']}
    assert review['flora_a101:lipa_t1_h550']['linked'] is True
    assert review['flora_a101:osoka_palmolistnaya_t1_h80']['level'] is None
    added = [r['latin'] for r in u['records'] if r['source'] == 'pilot_v003']
    assert added == ["Sorbaria sorbifolia 'Sem'", 'Pinus mugo']  # not linked, not a candidate
    assert u['counts']['a101'] == 4 and u['counts']['agent_light_npm'] == 1


def _maf_index(names, meta=None):
    recs = []
    for n in names:
        p = C.parse_maf(n)
        recs.append(C.make_record('maf', 'maf', n, manufacturer=p['manufacturer'], title=p['title'],
                                  article=p['article'], versions={'high': {}, 'low': {}},
                                  source={'path': n + '.zip'}, meta=(meta or {}).get(n)))
    return C.new_index('maf', 'maf_zip', '/lib', recs, {}, {})


def test_unify_maf_spec_typo_legacy_and_review():
    idx = _maf_index(['Mst_Kachalka_118030', 'Hobbika_Urna_15617', 'Hobbyka_Velo_15617', 'AdxGroup_Stol_1',
                      'Adx_Stul_2'], meta={'Adx_Stul_2': {'units': 'mm', 'geometry': {'high': {'tris': 10,
                                                                                                  'bbox': {'x': 1}}}}})
    legacy = {'spec_matches': [
        {'spec_row': 3, 'spec_name': 'Качалка', 'max_names': ['Mst_Kachalka_18030_high'], 'best': []},
        {'spec_row': 4, 'spec_name': 'Урна', 'max_names': ['Hobbika_Urna_15617_high', 'Hobbika_Urna_15617_low']},
        {'spec_row': 5, 'spec_name': 'Скамья', 'max_names': [], 'best': [{'id': 'MAF_0007'}]}],
        'entries': [{'id': 'MAF_0007', 'source_object': 'M_Bench_012', 'slug': 'MAF_0007_M_Bench_012', 'tris': 99,
                     'dims_m': [1, 2, 3], 'dup_group': 0, 'max_path': 'C:/x/a.max', 'preview_path': 'C:/x/a.png'}]}
    u = L.unify_maf(idx, legacy)
    by = {r['id']: r for r in u['records']}
    assert [s['spec_row'] for s in by['maf_a101:Mst_Kachalka_118030']['spec']] == [3]
    assert u['notes'][0]['a101'] == 'Mst_Kachalka_118030'
    assert [s['spec_row'] for s in by['maf_a101:Hobbika_Urna_15617']['spec']] == [4]
    assert u['spec_without_a101_model'][0]['legacy_candidates'] == ['MAF_0007']
    leg = by['maf_legacy:MAF_0007']
    assert leg['category_hint'] == 'M_Bench' and leg['status'] == 'legacy_unidentified' and leg['dup_group'] is None
    assert by['maf_a101:Adx_Stul_2']['tris'] == {'high': 10}
    assert ['Hobbika', 'Hobbyka'] in u['review']['manufacturer_spellings']
    assert ['Adx', 'AdxGroup'] in u['review']['manufacturer_spellings']
    assert u['review']['shared_articles'] == {'15617': ['Hobbika_Urna_15617', 'Hobbyka_Velo_15617']}


def test_cli_builds_and_refuses_overwrite(tmp_path):
    fl = _flora_index(tmp_path, ['lipa_t1_h550_high'])
    mf = _maf_index(['Adx_Stul_2'])
    for name, data in (('fl.json', fl), ('mf.json', mf), ('cat.json', CAT), ('light.json', {'variants': []}),
                       ('maf.json', {'entries': [], 'spec_matches': []})):
        (tmp_path / name).write_text(json.dumps(data), encoding='utf-8')
    cmd = [sys.executable, str(ROOT / 'tools/assets/build_unified_library.py'), '--flora-index', str(tmp_path / 'fl.json'),
           '--maf-index', str(tmp_path / 'mf.json'), '--flora-catalogue', str(tmp_path / 'cat.json'),
           '--npm-light', str(tmp_path / 'light.json'), '--maf-catalogue', str(tmp_path / 'maf.json'),
           '--out', str(tmp_path / 'out')]
    assert subprocess.run(cmd, capture_output=True).returncode == 0
    assert json.loads((tmp_path / 'out/flora_unified.json').read_text(encoding='utf-8'))['schema'] == L.UNIFIED_SCHEMA
    again = subprocess.run(cmd, capture_output=True, text=True)
    assert again.returncode != 0 and 'exists' in again.stderr + again.stdout
    assert subprocess.run(cmd + ['--replace'], capture_output=True).returncode == 0


@pytest.mark.parametrize('name', ['flora_unified.json', 'maf_unified.json'])
def test_committed_unified_files_are_current_schema(name):
    data = json.loads((ROOT / 'library/assets' / name).read_text(encoding='utf-8'))
    assert data['schema'] == L.UNIFIED_SCHEMA and data['truth'] == 'a101'
    ids = [r['id'] for r in data['records']]
    assert len(ids) == len(set(ids))


def test_maf_category_from_title():
    cat = C.maf_category
    assert cat('KacheliGamak') == 'Гамак' and cat('Kacheli') == 'Качели' and cat('KachalkaBalansir') == 'Качалка'
    assert cat('StolikSPechenkami') == 'Игровое оборудование' and cat('StolLion') == 'Стол'
    assert cat('UkorochenniNavesPodPloshadkySimpl4156') == 'Навес'
    assert cat('ElementPolosyPrepyatstviyNature') == 'Спортивное оборудование'
    assert cat('NoName3415') is None and cat('Anapa') is None


def _sidecar(name, **over):
    geo = lambda v, tris: {'object_names': [name + '_' + v], 'object_count': 1, 'tris': tris,  # noqa: E731
                           'bbox': {'x': 1000, 'y': 500, 'z': 900},
                           'pivot': {'above_bbox_base_mm': 200, 'offset_x_mm': 0, 'offset_y_mm': 0,
                                     'inside_bbox': True},
                           'transform': {'scale': [1, 1, 1], 'rotation_deg': [0, 0, 0], 'has_negative_scale': False},
                           'smoothing_groups_present': True}
    m = {'units': 'mm', 'up_axis': 'Z', 'geometry': {'high': geo('high', 900), 'low': geo('low', 300)},
         'materials': {v: [{'name': 'M_{}_{}'.format(name, v), 'class': 'Standardmaterial'}] for v in ('high', 'low')},
         'textures': {'high': [{'file': 'T_{}_high_{}.png'.format(name, s), 'slot': k, 'resolution': [4096, 4096]}
                               for s, k in (('Diffuse', 'base_color'), ('Normal', 'bump'), ('ERM', 'metalness'))],
                      'low': [{'file': 'T_{}_low_d.png'.format(name), 'slot': 'base_color', 'resolution': [512, 512]}]}}
    for k, v in over.items():
        m[k] = v
    return m


def test_audit_maf_contract_findings_and_measured_attach():
    names = ['Adx_Skameya_1', 'Adx_Kacheli_2', 'Adx_Urna_3', 'Adx_Stol_4']
    good = _sidecar(names[0])
    bad = _sidecar(names[1])
    bad['geometry']['high']['pivot'] = {'above_bbox_base_mm': 956, 'offset_x_mm': 400, 'offset_y_mm': 0,
                                        'inside_bbox': True}
    bad['geometry']['low']['tris'] = 900
    bad['materials']['high'] = [{'name': 'M_Other_Thing_9_high', 'class': 'Standardmaterial'}]
    bad['textures']['high'][0]['file'] = 'Other_Thing_9_high_Diffuse.png'
    bad['textures']['high'][0]['resolution'] = None  # not in the archive -> packing error
    idx = _maf_index(names, meta={names[0]: good, names[1]: bad})
    for r in idx['assets']:
        r['category'] = C.maf_category(r['title'])
    measured = {names[2]: _sidecar(names[2]), 'Ghost_X_1': {}}
    idx2, unknown = L.attach_measured(idx, measured)
    assert unknown == ['Ghost_X_1'] and idx['assets'][2].get('meta') is None  # input untouched
    rep = L.audit_maf(idx2)
    by = {r['name']: r for r in rep['rows']}
    assert by[names[0]]['findings'] == [] and by[names[0]]['warnings'] == []
    codes = [f['code'] for f in by[names[1]]['findings']]
    assert {'pivot_height', 'pivot_offset_xy', 'foreign_texture'} <= set(codes)
    assert [w['code'] for w in by[names[1]]['warnings']] == ['material_name', 'low_not_reduced']
    assert [w['code'] for w in by[names[2]]['warnings']] == ['measured'] and not by[names[2]]['findings']
    assert [f['code'] for f in by[names[3]]['findings']] == ['no_metadata']
    assert rep['clean'] == 2 and rep['stats']['high_tris']['n'] == 3
    assert rep['categories'] == {'Скамья': 1, 'Качели': 1, 'Урна': 1, 'Стол': 1}


def test_shared_family_atlas_is_a_warning_not_an_error():
    name = 'Mst_Kachalka_170100'
    m = _sidecar(name)
    m['materials']['high'] = [{'name': 'M_Mst_Kompleks_118030_high', 'class': 'Standardmaterial'}]
    for t in m['textures']['high']:
        t['file'] = t['file'].replace(name, 'Mst_Kompleks_118030')  # present in the archive: resolution read
    rep = L.audit_maf(_maf_index([name], meta={name: m}))
    row = rep['rows'][0]
    assert row['findings'] == []
    assert {w['code'] for w in row['warnings']} - {'no_category'} == {'shared_material', 'shared_texture'}

def test_maf_template_fills_fields_with_provenance_and_fixes():
    name = 'Adx_Skameya_1'
    asset = C.make_record('maf', 'maf', name, manufacturer='Adx', title='Skameya', article='1', category='Скамья')
    meta = _sidecar(name)
    research = {'title_ru': 'Скамья «Тест»', 'category': 'Скамья', 'description_ru': 'Скамья из стали.',
                'tags': ['скамья'], 'manufacturer_url': 'https://adx.example', 'product_url': None,
                'dimensions_text': '1000×500×700', 'materials': ['сталь'], 'confidence': 'found', 'sources': []}
    enrich = {'product_url': 'https://shop.example/p', 'materials_text': 'Сталь', 'schedule_names': ['Скамья X']}
    fix = {'fixes': ['high: pivot XY -> bbox centre'], 'after': {'high': {'above_base_mm': 200.0,
                                                                         'offset_xy_mm': [0.0, 0.0],
                                                                         'material': 'M_Adx_Skameya_1_high'}}}
    t = L.maf_template(asset, meta, research, enrich, {'findings': [], 'warnings': []}, fix)
    assert t['schema'] == 3 and t['title'] == 'Скамья «Тест»' and t['category'] == 'Скамья'
    assert t['download_url'] == 'https://shop.example/p' and t['agr']['provenance']['download_url'] == 'project_schedule'
    assert t['agr']['provenance']['title'] == 'web' and t['agr']['template'] == L.MAF_TEMPLATE
    assert t['geometry']['high']['pivot']['offset_x_mm'] == 0.0 and t['agr']['fixes'] == fix['fixes']
    assert meta['geometry']['high']['pivot']['offset_x_mm'] == 0  # input untouched
    bare = L.maf_template(asset, None)
    assert bare['title'] is None and bare['category'] == 'Скамья' and bare['agr']['provenance']['category'] == 'title'


def test_scan_maf_override_dir_and_template_meta(tmp_path):
    import json as _json
    lib_dir = tmp_path / 'maf' / 'a101'
    _mk = sys.modules['agr_tools_assets_core_lib_test']
    for n in ('Adx_Stol_1', 'Adx_Stul_2'):
        p = lib_dir / (n + '.zip')
        p.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(p, 'w') as z:
            z.writestr(n + '_high.fbx', b'old')
            z.writestr(n + '.png', b'png')
    fixed = tmp_path / 'maf' / 'a101_fixed'
    fixed.mkdir()
    with zipfile.ZipFile(fixed / 'Adx_Stol_1.zip', 'w') as z:
        z.writestr('Adx_Stol_1_high.fbx', b'new')
        z.writestr('Adx_Stol_1.png', b'png')
    meta = tmp_path / 'maf' / 'a101_meta'
    meta.mkdir()
    (meta / 'Adx_Stul_2.json').write_text(_json.dumps({'schema': 3, 'category': 'Кресло', 'title': 'Стул'}),
                                          encoding='utf-8')
    idx = _mk.scan_maf(str(lib_dir), str(tmp_path / 'c'), lib='maf', override_dir=str(fixed), meta_dir=str(meta))
    by = {r['name']: r for r in idx['assets']}
    assert by['Adx_Stol_1']['source']['path'] == '../a101_fixed/Adx_Stol_1.zip'
    assert by['Adx_Stul_2']['meta']['title'] == 'Стул' and by['Adx_Stul_2']['category'] == 'Кресло'
    assert idx['report']['overridden'] == 1 and idx['report']['templated'] == 1


def test_repack_keeps_members_replaces_fixed_and_sidecar(tmp_path):
    spec = importlib.util.spec_from_file_location('build_maf_template_t', ROOT / 'tools/assets/build_maf_template.py')
    b = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(b)
    src = tmp_path / 'A_B_1.zip'
    with zipfile.ZipFile(src, 'w') as z:
        for n, d in (('A_B_1.max', b'oldmax'), ('A_B_1.png', b'png'), ('A_B_1_high.fbx', b'oldfbx'),
                     ('A_B_1.json', b'{}'), ('T_A_B_1_high_Diffuse.png', b'tex')):
            z.writestr(n, d)
    fx = tmp_path / 'fixed'
    (fx / 'A_B_1.fbm').mkdir(parents=True)
    (fx / 'A_B_1.max').write_bytes(b'newmax')
    (fx / 'A_B_1_high.fbx').write_bytes(b'newfbx')
    (fx / 'A_B_1.fbm' / 'junk.png').write_bytes(b'x')
    dst = tmp_path / 'out.zip'
    b.repack(str(src), str(fx), {'name': 'A_B_1', 'title': 'Т'}, dst)
    with zipfile.ZipFile(dst) as z:
        assert sorted(z.namelist()) == sorted(['A_B_1.max', 'A_B_1.png', 'A_B_1_high.fbx', 'T_A_B_1_high_Diffuse.png',
                                               'A_B_1.json'])
        assert z.read('A_B_1.max') == b'newmax' and z.read('A_B_1.png') == b'png'
        assert json.loads(z.read('A_B_1.json').decode('utf-8'))['title'] == 'Т'


def test_propose_maf_name_q28():
    assert L.propose_maf_name('Города или аналог', 'Скамейка стальная «Андромеда» / Артикул: 14122', '14122') == \
        'Goroda_SkameykaStalnayaAndromeda_14122'
    assert L.propose_maf_name('Города', 'Стул на ножке "Бар"', None) == 'Goroda_StulNaNozhkeBar_0000'
    assert L.propose_maf_name(None, 'Качалка балансир / Артикул: ИО 0410-2', 'ИО 0410-2') == \
        'NoName_KachalkaBalansir_IO0410-2'
    assert C.parse_maf(L.propose_maf_name('Города', 'Урна «Арго»', '19648')) is not None
