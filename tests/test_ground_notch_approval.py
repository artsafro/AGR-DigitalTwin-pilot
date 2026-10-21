"""Approved notch is finite, source-bound data, not a relaxed numeric tolerance."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def test_ground_notch_approval_records_exact_source_and_contour():
    p=json.loads((ROOT/'jobs/VATUTINO-SITE/ground-notch-approval-v015.json').read_text())
    assert p['decision']=='D169'
    assert p['source_sha256']=='82cb1e6876ba98b92966aa7fc4242a2e9f354ee5ecdd42ed12806b57db666ae5'
    assert p['triangle_xy']==[[-7691.007,-15248.688],[-7691.2305,-15248.001],[-7691.016,-15248.688]]
    assert p['source_footprint_hole']==0
    assert p['approved_by']=='Artem' and p['quote']=='принимаю'
    assert p['scope']=='local_contour_correction_only'
    assert p['outline_tolerance_m']==.0022
    assert p['xview_vertex_tolerance_m']==.002 and p['xview_face_tolerance_m']==.005
    assert p['relief_tolerance_m']==.01
    decisions=(ROOT/'docs/decisions.md').read_text()
    row=next(s for s in decisions.splitlines() if s.startswith('| D169 |'))
    assert '2026-10-21' in row and 'thresholds unchanged' in row
