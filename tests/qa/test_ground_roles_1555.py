"""new-case: Ground-family provenance roles and independent producer sources (#1555)."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from adapters.max.agr_tools import build_manifest as bm, package_core as pc


@pytest.mark.parametrize('suffix,role', [('Ground', 'ground'), ('GroundGlass', 'ground'),
    ('GroundEl', 'groundel'), ('GroundElGlass', 'groundel'), ('Flora', 'flora')])
@pytest.mark.parametrize('address', ['A', 'Syn_12', 'Underground_Floral'])
@pytest.mark.parametrize('template', ['SM_{}_{}.fbx', 'T_{}_{}_d_1.png',
    'T_{}_{}_Diffuse_1.1001.png', 'UCX_SM_{}_{}_001.fbx', 'SM_{}_{}_Light.fbx'])
def test_ground_family_role_is_shared(suffix, role, address, template):
    name = template.format(address, suffix)
    assert bm.role_of(name) == role
    assert pc.role_of(name) == role
    assert pc.classify_mesh('SM_' + address + '_' + suffix)[0] == 'ground'


@pytest.mark.parametrize('name', ['SM_Underground_Main.fbx', 'T_Floral_Diffuse_1.1001.png',
    'SM_A_GroundElse.fbx', '0000_A_01.fbx'])
def test_similar_words_are_not_ground_roles(name):
    assert bm.role_of(name) == pc.role_of(name) == 'oks'
