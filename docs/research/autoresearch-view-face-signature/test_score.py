"""Unit checks for #157 score.py (frozen matching rules)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import score as S  # noqa: E402


def wall(W, H, cls="inner", az=0.0, ncol=0, nrow=0):
    return {"az": az, "d0": 0.0, "d1": 0.1, "u0": 0.0, "u1": W, "z0": 0.0, "z1": H, "W": W, "H": H, "cls": cls,
            "ncol": ncol, "nrow": nrow}


def test_clusters_gap():
    assert S.clusters([]) == 0
    assert S.clusters([0.0, 0.5, 1.2, 5.0]) == 3


def test_tolerances_are_frozen():
    a = wall(10.0, 12.0)
    assert S.match(a, wall(11.2, 13.0), "A")
    assert not S.match(a, wall(11.3, 12.0), "A")
    assert not S.match(a, wall(10.0, 12.0, ncol=1), "B")


def test_twins_abstain_and_unique_answers():
    walls = [wall(10, 12, ncol=3, nrow=3), wall(10, 12, ncol=3, nrow=3, az=180), wall(30, 12, "open", ncol=8, nrow=3)]
    res = S.score_model(walls)
    rows = res["rows"]
    assert [r["unique_B"] for r in rows] == [False, False, True]
    assert rows[0]["perturbed"][:2] == ["abstain", "abstain"]
    assert rows[2]["perturbed"][:2] == ["correct", "correct"]
    assert res["summary"]["inner_unique_B"] == 0.0


def test_window_attach_counts_columns_rows():
    w = wall(10.0, 9.0)
    win = [[0.05, u, z] for u in (1.0, 4.0, 7.0) for z in (1.5, 4.5)]  # az 0 -> t = (0, 1), u = y
    S.attach_windows([w], win)
    assert (w["ncol"], w["nrow"]) == (3, 2)
