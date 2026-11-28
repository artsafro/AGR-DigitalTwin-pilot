import runpy
from pathlib import Path

ns = runpy.run_path(str(Path(__file__).with_name('run.py')))
length_veto, two_sided = ns['length_veto'], ns['two_sided']
RW = {'W19': 72.068, 'W07': 28.287}


def test_short_full_view_vetoed():
    assert length_veto('W19', 'full', 55.75, RW, 0.10) is None


def test_matching_full_view_kept():
    assert length_veto('W19', 'full', 74.25, RW, 0.10) == 'W19'


def test_fragment_exempt():
    assert length_veto('W19', 'fragment', 10.75, RW, 0.10) == 'W19'


def test_never_creates_answer():
    assert length_veto(None, 'full', 72.0, RW, 0.10) is None
    assert length_veto(None, 'fragment', 10.0, RW, 0.10) is None


def test_two_sided_diagnostic_narrows_competitors():
    scores = {'W07': 0.5683, 'W08': 0.1204, 'W19': 0.3857}
    rw = {'W07': 28.287, 'W08': 26.247, 'W19': 72.068}
    ans, elig = two_sided(27.0, 'full', scores, rw, dict(fit_tol=0.10, tau=0.30, delta=0.10))
    assert elig == ['W07', 'W08'] and ans == 'W07'
