"""new-case: roof research data partition, source bindings and shared catalogue integrity."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load(relative):
    return json.loads((ROOT/relative).read_text(encoding='utf-8'))


def test_five_observed_objects_and_no_invented_counterprofile():
    doc = load('library/roof_equipment/observations.json')
    sources = {s['id']: s for s in doc['sources']}
    assert set(sources) == {'G01', 'G02', 'OLY', 'SKO', 'VOL'}
    assert {s['input']['profile'] for s in sources.values()} == {'npm', 'vpm'}
    seen = set()
    for row in doc['observations']:
        assert row['profile'] == sources[row['object']]['input']['profile']
        assert row['count_components'] == len(row['members']) > 0
        assert 0 < row['triangle_range'][0] <= row['triangle_range'][1]
        assert all(0 <= a <= b for a, b in zip(*row['size_range_m']))
        for member in row['members']:
            assert member.startswith(row['object']+'-o')
            assert member not in seen
            seen.add(member)
    context = doc['context_or_unclassified']
    assert sum(context['counts_by_object'].values()) == context['count']
    for key, source in sources.items():
        typed = sum(r['count_components'] for r in doc['observations'] if r['object'] == key)
        assert typed > 0
        assert typed + context['counts_by_object'][key] == source['candidate_components']


def test_twelve_source_bound_assets_and_no_synthetic_budget_claim():
    doc = load('library/roof_equipment/observations.json')
    members = {c for row in doc['observations'] for c in row['members']}
    extraction = load('library/roof_equipment/extraction.json')
    catalogue = load('library/roof_equipment/catalogue.json')
    plans = extraction['plans']
    prototypes = {a['id']: (p, a) for p in plans for a in p['assets']}
    assert len(prototypes) == len(catalogue['assets']) == 12
    for asset in catalogue['assets']:
        plan, prototype = prototypes[asset['id']]
        assert prototype['component'] in members
        assert asset['source']['component'] == prototype['component']
        assert asset['source']['source_sha256'] == plan['source_sha256']
        assert asset['confirmation'] == 'unconfirmed'
        assert set(asset['variants']) == {'npm', 'vpm'}
        assert all(v['triangles'] == prototype['triangles'] for v in asset['variants'].values())
        assert asset['variants']['npm']['size_m'] == asset['variants']['vpm']['size_m']
    path = ROOT/'tools/library/check_library.py'
    spec = importlib.util.spec_from_file_location('roof_catalogue_contract', path)
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    checker.validate_catalogue(catalogue)
    for entry in catalogue['inputs']:
        assert checker.digest(ROOT/entry['path']) == entry['sha256']
