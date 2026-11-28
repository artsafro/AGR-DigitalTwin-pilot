"""Unit checks for the #167 ELV adapter pieces (no PDF/FBX needed)."""

import importlib.util
from pathlib import Path

import numpy as np

spec = importlib.util.spec_from_file_location('ar167', Path(__file__).with_name('run.py'))
ar = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ar)


def wall(i, az, d, u0, u1):
    return dict(id=i, az=az, d=d, u0=u0, u1=u1, length=u1 - u0)


def test_outer_wall_ignores_parapet_inner_face_behind_shell():
    walls = [wall('S', 270, 50.0, 0, 76), wall('P', 270, 0.0, -8, 76), wall('A', 270, 11.0, -9, -4)]
    out = ar.outer_walls(walls)
    assert out == {'S': True, 'P': False, 'A': True}


def test_glass_rule_excludes_white_and_grey_fills():
    rgb = np.array([[255, 255, 255], [236, 238, 238], [236, 244, 253], [207, 227, 250]])
    dist = np.min([np.sqrt(((rgb - np.array(s)) ** 2).sum(-1)) for s in ar.GLASS_RGB], axis=0)
    assert list(dist <= ar.GLASS_DIST) == [False, False, True, True]


def test_tally_groups_full_and_fragment():
    rows = [dict(view='p18 I-A', states=dict(clean=dict(outcome=dict(C166='correct')))),
            dict(view='p23 frag D-G', states=dict(clean=dict(outcome=dict(C166='abstain'))))]
    assert ar.tally(rows, 'C166', 'clean', 'full') == dict(correct=1, wrong=0, abstain=0)
    assert ar.tally(rows, 'C166', 'clean', 'fragment') == dict(correct=0, wrong=0, abstain=1)
