"""new-case: shared headless window command, same OBJ as AGR Tools win.generate."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'adapters/max/agr_tools'))
import windowgen_core as wg


def test_fresh_agent_command_matches_max_builder(tmp_path):
    out = tmp_path / 'generated'
    result = subprocess.run([sys.executable, '-m', 'dt_ai.cli.agr', 'window-generate',
                             '--ids', 'KPP1-W01', 'KPP1-W02', 'KPP1-W03', '--out', str(out)],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    lib = wg.load_library(str(ROOT / 'library/windows'))
    for tid in ('KPP1-W01', 'KPP1-W02', 'KPP1-W03'):
        expected = wg.to_obj(wg.build_type(lib['by_id'][tid], lib['standard'], {'variant': 'vpm'}), tid)
        assert (out / (tid + '.obj')).read_text(encoding='utf-8') == expected
    assert json.loads((out / 'quality.json').read_text())['counts']['pass'] == 3
