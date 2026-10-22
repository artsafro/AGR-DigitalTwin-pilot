"""new-case: AC06 isolated-ID correction and orchestrator finish policy."""
import json
from pathlib import Path

PACKET = Path(__file__).resolve().parents[1] / 'jobs/TEC26-OKS/AC06/materials.json'


def test_ac06_isolated_downpipes_not_window_reveals():
    data = json.loads(PACKET.read_text(encoding='utf-8'))
    rows = {r['id']:r for r in data['materials']}
    assert rows[4]['finish'] == 'Rainwater downpipes'
    assert rows[4]['ral'] == '7004'
    assert rows[9]['finish'] == '?'
    assert rows[9]['proposal']['component'] == 'Window perimeter reveals'
    assert rows[9]['proposal']['ral'] == '9016'
    assert all('ids-isolated-unknowns.png' in r['evidence'] for r in [rows[4],rows[5],rows[6],rows[8],rows[9],rows[11]])
    assert data['scene']['layer_question'] is None
    assert rows[3]['map_type'] == 'solid'
    assert rows[12]['glass_policy']['material'] == 'M_Glass_01'
    assert rows[12]['glass_policy']['npm_alpha'] == 0.5
    assert rows[12]['question'] is None
    assert all(r['proposal']['rationale'] and r['proposal']['map_type'] for r in rows.values() if r['finish'] == '?')
