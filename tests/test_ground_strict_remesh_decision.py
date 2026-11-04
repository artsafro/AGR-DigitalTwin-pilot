"""Keep the resumed strict-remesh authorization narrower than a texel waiver."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_strict_remesh_authorization_retains_all_numeric_contracts():
    row = next(line for line in (ROOT / 'docs/decisions.md').read_text(encoding='utf-8').splitlines()
               if line.startswith('| D157 |'))
    for token in ('2026-10-21 22:57', 'strict-remesh', '7ac17a9', 'texel_ready',
                  'aspect <=8', 'VPM edge <=4 m', 'no texel exception', '50,000', '180,000'):
        assert token in row, token
    text = (ROOT / 'jobs/VATUTINO-SITE/ground-v015-strict-remesh-plan.md').read_text(encoding='utf-8')
    for token in ('NOT_DELIVERY', 'D150', '2.2 mm', '10 mm', '0.002/0.005 m',
                  '50,000', '180,000', 'texel_ready', 'both diagonals'):
        assert token in text, token
