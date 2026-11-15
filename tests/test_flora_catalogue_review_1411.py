"""new-case: fixed Flora review evidence covers the frozen v003 inventory (#1411)."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECEIPT = ROOT / 'docs/library/flora-review-1411.json'


def test_review_packet_covers_every_species_without_approving_catalogue():
    assert RECEIPT.is_file(), 'Missing #1411 review packet receipt'
    packet = json.loads(RECEIPT.read_text(encoding='utf-8'))
    catalogue_path = ROOT / 'library/flora/catalogue.json'
    catalogue = json.loads(catalogue_path.read_text(encoding='utf-8'))
    assert packet['catalogue_sha256'] == hashlib.sha256(catalogue_path.read_bytes()).hexdigest()
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
            assert source['vpm_identity'] == 'unverified'
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
