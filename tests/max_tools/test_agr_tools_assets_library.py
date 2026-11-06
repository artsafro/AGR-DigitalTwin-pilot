"""new-case: unified asset library for agents (#1024, assets_library.py + tools/assets/build_unified_library.py).
Synthetic names only; A101 is the truth, earlier catalogues are joined, nothing ambiguous is chosen silently."""
import importlib.util
import json
import subprocess
import sys
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
