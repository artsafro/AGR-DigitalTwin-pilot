"""Pattern: new-case: cold-agent 2D drawing intake regression for F14."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_2d_intake_route():
    skill = (ROOT / '.agents/skills/analyze-architectural-source/SKILL.md').read_text(encoding='utf-8')
    for token in ('## 2D drawings', 'dwg_to_dxf.py', 'plan_from_dxf.py census',
                  'plan_from_dxf.py extract', 'facade_openings_from_dxf.py', 'mesh-only'):
        assert token in skill, token
    for name in ('docs/scenarios/oks-vpm.md', 'docs/domain/areas/body.md'):
        text = (ROOT / name).read_text(encoding='utf-8')
        for tool in ('dwg_to_dxf.py', 'plan_from_dxf.py', 'facade_openings_from_dxf.py'):
            assert tool in text, (name, tool)
    mirror = (ROOT / '.claude/skills/analyze-architectural-source/SKILL.md').read_text(encoding='utf-8')
    assert mirror == skill, 'cold Claude agent must receive the same 2D route'
    registry = (ROOT / 'docs/sources/README.md').read_text(encoding='utf-8')
    assert 'АС.03 R1' in registry and 'jobs/KPP1/sources.json' in registry
