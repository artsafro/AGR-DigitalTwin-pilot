"""new-case: fixed Flora review evidence covers the frozen v003 inventory (#1411)."""
import copy
import hashlib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RECEIPT = ROOT / 'docs/library/flora-review-1411.json'
# #1421: after Artem reviewed these sheets, D311 marked the shown NPM/VPM pairs confirmed-interim.
D311 = {'id': 'D311', 'date': '2026-11-15'}


def reviewed_sha256(catalogue):
    """sha256 of the catalogue exactly as reviewed in #1411: D311 identity fields reverted, nothing else."""
    reviewed = copy.deepcopy(catalogue)
    for row in reviewed['species']:
        decision = row.pop('vpm_identity_decision')
        if decision is not None:
            assert decision == D311 and row['vpm_identity'] == 'confirmed-interim', row['latin']
            row['vpm_identity'] = 'unverified'
    text = json.dumps(reviewed, ensure_ascii=False, indent=1) + '\n'
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def test_review_packet_covers_every_species_without_approving_catalogue():
    assert RECEIPT.is_file(), 'Missing #1411 review packet receipt'
    packet = json.loads(RECEIPT.read_text(encoding='utf-8'))
    catalogue_path = ROOT / 'library/flora/catalogue.json'
    catalogue = json.loads(catalogue_path.read_text(encoding='utf-8'))
    assert packet['catalogue_sha256'] == reviewed_sha256(catalogue)
    species = catalogue['species']
    assert [r['material_id'] for r in packet['rows']] == [s['material_id'] for s in species]
    assert len({r['material_id'] for r in packet['rows']}) == len(species)
    for row, source in zip(packet['rows'], species):
        assert row['latin'] == source['latin']
        assert row['russian'] == source['russian']
        assert row['type'] == source['type']
        assert row['objects'] == source['objects']
        assert row['triangles'] == source['triangles']
        assert row['maps_used'] == []
        assert row['map_status'] == 'missing; historical approval only'
        assert row['acceptance'] == 'pending Artem'
        assert row['sheet'] in {p['file'] for p in packet['sheets']}
        for profile, name in source['objects'].items():
            if name:
                assert row['native_triangles'][profile] == source['triangles'][profile]
            else:
                assert row['native_triangles'][profile] is None
        if source['objects']['VPM']:
            assert source['vpm_identity'] == 'confirmed-interim'  # D311 (#1421) after Artem reviewed these sheets
            assert row['surface_305']['verdict'] == 'different'
            for direction in ('npm', 'vpm'):
                metric = row['surface_305'][direction]
                assert 0 <= metric['coverage_lower_percent'] <= metric['coverage_upper_percent'] <= 100
        else:
            assert row['surface_305']['verdict'] == 'no_vpm'
    assert packet['missing_bitmap_bindings'] == sum(len(r['missing_bitmap_references']) for r in packet['rows'])
    assert packet['maps_substituted'] is False
    assert packet['catalogue_changed'] is False
    report = ROOT / 'library/flora/vpm-surface-identity.json'
    assert packet['surface_report_sha256'] == hashlib.sha256(report.read_bytes()).hexdigest()
    historical = json.loads(report.read_text(encoding='utf-8'))
    assert packet['library_sha256'] == historical['sources']['library_sha256']
    assert packet['gaps'] == catalogue['gaps']
    assert [i for page in packet['sheets'] for i in page['material_ids']] == [s['material_id'] for s in species]
    assert len({p['file'] for p in packet['sheets']}) == len(packet['sheets'])
    historical_by_id = {p['material_id']: p for p in historical['pairs']}
    for row in packet['rows']:
        original = historical_by_id[row['material_id']]
        assert row['surface_305']['verdict'] == original['verdict']
        if original['verdict'] == 'different':
            for direction in ('npm', 'vpm'):
                facts = original[direction]
                metric = row['surface_305'][direction]
                assert metric['coverage_lower_percent'] == max(0.0, 100*(1-facts['uncovered_m2']/facts['area_m2']))
                assert metric['coverage_upper_percent'] == min(100.0, 100*(1-facts['uncovered_lower_m2']/facts['area_m2']))


def test_packet_contract_rejects_each_omitted_or_duplicated_species(tmp_path, monkeypatch):
    original = json.loads(RECEIPT.read_text(encoding='utf-8'))
    target = tmp_path / 'packet.json'
    monkeypatch.setitem(globals(), 'RECEIPT', target)
    for index in range(len(original['rows'])):
        for duplicate in (False, True):
            changed = copy.deepcopy(original)
            if duplicate:
                changed['rows'].insert(index, copy.deepcopy(changed['rows'][index]))
            else:
                changed['rows'].pop(index)
            target.write_text(json.dumps(changed), encoding='utf-8')
            with pytest.raises(AssertionError):
                test_review_packet_covers_every_species_without_approving_catalogue()
    target.write_text(json.dumps(original), encoding='utf-8')
    test_review_packet_covers_every_species_without_approving_catalogue()


@pytest.mark.parametrize('defect', ['empty', 'stale', 'approved', 'standin', 'nan', 'inf', 'negative', 'over100', 'wrongcount', 'unknown', 'sheetdrop'])
def test_packet_contract_rejects_false_receipts(tmp_path, monkeypatch, defect):
    packet = json.loads(RECEIPT.read_text(encoding='utf-8'))
    if defect == 'empty':
        packet['rows'] = []
    elif defect == 'stale':
        packet['catalogue_sha256'] = '0' * 64
    elif defect == 'approved':
        packet['rows'][0]['acceptance'] = 'approved'
    elif defect == 'standin':
        packet['rows'][0]['maps_used'] = ['unapproved.png']
    elif defect in ('nan', 'inf', 'negative', 'over100'):
        value = {'nan': float('nan'), 'inf': float('inf'), 'negative': -1, 'over100': 101}[defect]
        packet['rows'][0]['surface_305']['npm']['coverage_lower_percent'] = value
    elif defect == 'wrongcount':
        packet['rows'][0]['native_triangles']['NPM'] += 1
    elif defect == 'unknown':
        packet['rows'][0]['material_id'] = 9999
    elif defect == 'sheetdrop':
        packet['sheets'][0]['material_ids'].pop()
    target = tmp_path / 'packet.json'
    target.write_text(json.dumps(packet), encoding='utf-8')
    monkeypatch.setitem(globals(), 'RECEIPT', target)
    with pytest.raises(AssertionError):
        test_review_packet_covers_every_species_without_approving_catalogue()
