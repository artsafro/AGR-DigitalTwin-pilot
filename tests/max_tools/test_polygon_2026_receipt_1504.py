"""new-case: frozen current-main Max 2026 polygon receipt, not a live UI certificate."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RECEIPT = ROOT / 'docs/evidence/1504-polygon-max2026/receipt.json'


def test_native_receipt_is_complete_and_green():
    receipt = json.loads(RECEIPT.read_text(encoding='utf-8'))
    assert receipt['source_commit'] == '9b7945d0b6ce0058020f63215b6497eb507190ef'
    assert receipt['max_build'] == '28.3.0.30732'
    assert receipt['native_exit'] == 0
    assert receipt['diffs'] == receipt['known_bug'] == 0
    assert receipt['runs'] == 127
    assert receipt['stations'] == 94
    assert receipt['rows'] == 876
    assert receipt['mode'] == 'synthetic batch; staged current-main runtime; not UI acceptance'
    for base in receipt['bases']:
        assert base['station_pass'] == base['station_total']
        assert base['row_pass'] == base['row_total']
    assert sum(base['station_total'] for base in receipt['bases']) == receipt['stations']
    assert sum(base['row_total'] for base in receipt['bases']) == receipt['rows']
    for station, button in {
        '1.0.3': 'scene.source_class', '1.0.5': 'model.attach_by_material',
        '1.0.6': 'model.move_apart', '1.0.7': 'model.grid_cleanup',
        '1.0.8': 'scene.small_parts', '1.0.11': 'model.glass_planes',
    }.items():
        assert receipt['required_stations'][station]['button'] == button
        assert receipt['required_stations'][station]['passed'] is True
    assert receipt['evidence_path'].startswith('G:/Мой диск/AGR-evidence/1504-polygon-max2026/')
    manifest = (RECEIPT.parent / 'SHA256SUMS.txt').read_text(encoding='utf-8')
    for name in ('report.json', 'actual.json', 'max.log', 'station-results.png'):
        digest = receipt['hashes'][name]
        assert len(digest) == 64 and all(c in '0123456789abcdef' for c in digest)
        assert f'{digest}  {name}' in manifest
    report = (RECEIPT.parent / 'REPORT.md').read_text(encoding='utf-8')
    assert receipt['job_id'] in report
    assert 'not UI acceptance' in report
    assert '0 diffs' in report
