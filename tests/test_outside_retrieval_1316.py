"""Regression for #1316 portable map routes and honest missing-byte states."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_flora_map_routes_do_not_depend_on_deleted_workstation_cache():
    maps = json.loads((ROOT / 'library/flora/maps.json').read_text(encoding='utf-8'))
    assert maps
    for latin, record in maps.items():
        for slot in ('diffuse', 'opacity'):
            path = record[slot]
            assert path is None or path.startswith('G:/Мой диск/AGR-assets/flora/'), (latin, slot, path)
        if not record['diffuse'] or not record['opacity']:
            assert record['review_status'] == 'missing', latin
            assert record['evidence'], latin
