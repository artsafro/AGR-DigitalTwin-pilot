"""Synthetic witnesses for the #63 signed guard and frozen verdict (replay checks native parity)."""
import math
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
R62 = '75257229cb561c64bace8250f632c13bc4d694af'


@pytest.fixture(scope='module')
def p63(tmp_path_factory):
    stage = tmp_path_factory.mktemp('r62')
    try:
        raw = subprocess.check_output(['git', 'show', f'{R62}:docs/research/atlas-native-phase-r62/phase.py'],
                                      cwd=HERE)
    except subprocess.CalledProcessError:
        pytest.skip('#62 Git object not available')
    (stage / 'phase.py').write_bytes(raw)
    sys.path[:0] = [str(stage), str(HERE)]
    try:
        import phase63
        yield phase63
    finally:
        sys.path.remove(str(stage))
        sys.path.remove(str(HERE))
        sys.modules.pop('phase63', None)
        sys.modules.pop('phase', None)


U0, SIDE = 6 / 2048, 397 / 2048


def test_signed_shift_stays_in_padded_cell(p63):
    assert p63.shifted(U0, U0, SIDE, 6, 2048, -5.0) < U0
    assert p63.shifted(U0 + SIDE, U0, SIDE, 6, 2048, 5.0) > U0 + SIDE
    with pytest.raises(ValueError, match='leaves'):
        p63.shifted(U0 - 2 / 2048, U0, SIDE, 6, 2048, -5.0)


def test_limit_and_verdict(p63):
    quiet = {s: 0 for s in p63.GRID}
    detect = quiet | {2.0: 3, -2.0: 3, 5.0: 320, -5.0: 320}
    assert p63.limit(detect) == 2.0 and p63.verdict(detect, 202, 0) == 'confirmed'
    assert p63.limit(quiet) == math.inf and p63.verdict(quiet, 202, 0) == 'refuted'
    one_sided = detect | {1.0: 5}
    assert p63.verdict(one_sided, 202, 0) == 'refuted'
    assert p63.verdict(detect, 0, 0) == 'inconclusive'
    gap = detect | {2.0: 0, 1.0: 4, -1.0: 4}
    assert p63.limit(gap) == 5.0
