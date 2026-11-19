"""#1423 KPP1 proof audit: the committed proof summary shows pass at one master and refusal after the roof edit."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT / 'jobs/KPP1/build-manifest-1423'
P = json.loads((HERE / 'proof-r3.json').read_text(encoding='utf-8'))


def rows(entry):
    return [(r['status'], r['code']) for r in entry['rows']]


def test_baseline_one_master_passes():
    assert [rows(e) for e in P['validate_A']] == [[('pass', None)], [('pass', None)]]
    assert P['cross_A'] == {}
    assert [b['readback_status'] for b in P['build_A']] == ['pass', 'pass']
    assert all(b['artifacts_from_other_masters'] == [] for b in P['build_A'])


def test_roof_edit_in_a_copy_changes_the_master():
    edit = P['roof_edit']
    assert edit['object'] == 'SM_Kpp_1_Main' and edit['roof_faces'] > 0 and edit['lift_m'] == 0.3
    assert P['master_sha']['A'] != P['master_sha']['B']
    assert P['master_sha']['A'] in P['inputs'].values()  # master A is the unmodified quad master copy


def test_stale_npm_and_vpm_are_refused():
    assert [rows(e) for e in P['validate_A_against_B']] == [[('fail', 'manifest_master_stale')]] * 2
    assert all(e['exit'] == 1 for e in P['validate_A_against_B'])
    assert rows(P['validate_B']) == [('fail', 'manifest_master_mismatch')] and P['validate_B']['exit'] == 1
    assert rows(P['validate_npm_in_B']) == [('fail', 'manifest_master_stale')]
    assert {k: [c for c, _ in v] for k, v in P['cross_B'].items()} == {
        '0000_Kpp_1.zip': ['manifest_cross_master'], 'SM_Kpp_1.zip': ['manifest_cross_master']}


def test_vpm_readback_binds_every_ucx_to_the_visual_mesh():
    assert P['vpm_A_export']['ucx'] == ['UCX_SM_Kpp_1_Main_00{}'.format(i) for i in range(1, 5)]
    assert set(P['vpm_A_export']['triangles']) == {'SM_Kpp_1_Main', 'SM_Kpp_1_MainGlass'}
