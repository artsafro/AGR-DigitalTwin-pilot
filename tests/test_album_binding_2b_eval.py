"""new-case: one-to-one real DWG dimension-oracle controls for PDF binding #1254."""

import pytest

from tools.research.pdf_album.binding_2b_eval import dimension_oracle, score_dimensions


def test_dimension_entities_use_projected_extension_points(tmp_path):
    ezdxf = pytest.importorskip("ezdxf")
    d = ezdxf.new()
    m = d.modelspace()
    one = m.add_line((100, 0), (100, 100))
    two = m.add_line((2100, 0), (2100, 100))
    m.add_linear_dim(base=(0, -100), p1=(100, 20), p2=(2100, 50), angle=0).render()
    p = tmp_path / "oracle.dxf"
    d.saveas(p)
    rows = dimension_oracle(
        p,
        [
            {"label": "1", "handle": one.dxf.handle, "orientation": "vertical"},
            {"label": "2", "handle": two.dxf.handle, "orientation": "vertical"},
        ],
    )
    assert len(rows["dimensions"]) == 1
    assert rows["dimensions"][0]["axes"] == ["1", "2"]
    assert rows["dimensions"][0]["value_mm"] == pytest.approx(2000)


def test_changed_dxf_is_not_a_fresh_oracle(tmp_path, monkeypatch):
    ezdxf = pytest.importorskip("ezdxf")
    p = tmp_path / "source.dxf"
    ezdxf.new().saveas(p)
    real = ezdxf.readfile

    def changing(path):
        doc = real(path)
        with path.open("a") as stream:
            stream.write("\nchanged")
        return doc

    monkeypatch.setattr(ezdxf, "readfile", changing)
    with pytest.raises(ValueError, match="changed"):
        dimension_oracle(p, [])


def prediction(value=2000, axes=("1", "2"), kind="axis_pair"):
    return {
        "kind": "dimension",
        "value": value,
        "binding": {"type": kind, "axes": list(axes)},
    }


def test_dimension_oracle_one_to_one():
    truth = [{"handle": "A", "value_mm": 2000, "axes": ["1", "2"]}]
    assert score_dimensions([prediction()], truth) == {
        "found": 1,
        "correct": 1,
        "wrong": 0,
        "missed": 0,
        "truth": 1,
        "precision": 1.0,
        "recall": 1.0,
    }
    r = score_dimensions([prediction(), prediction()], truth)
    assert (r["correct"], r["wrong"], r["missed"]) == (1, 1, 0)


@pytest.mark.parametrize(
    "value,axes",
    [
        (2001, ("1", "2")),
        (2000, ("1", "3")),
        (float("nan"), ("1", "2")),
        (float("inf"), ("1", "2")),
    ],
)
def test_dimension_oracle_rejects_wrong_or_nonfinite(value, axes):
    r = score_dimensions(
        [prediction(value, axes)],
        [{"handle": "A", "value_mm": 2000, "axes": ["1", "2"]}],
    )
    assert (r["correct"], r["wrong"], r["missed"]) == (0, 1, 1)


def test_empty_oracle_is_unknown_not_perfect():
    r = score_dimensions([], [])
    assert r["precision"] is None and r["recall"] is None


def test_unbound_and_other_classes_do_not_claim_semantic_recall():
    r = score_dimensions(
        [prediction(kind="unbound")],
        [{"handle": "A", "value_mm": 2000, "axes": ["1", "2"]}],
    )
    assert r["found"] == 0 and r["missed"] == 1


def test_generated_dimension_duplicates_never_inflate_recall():
    import random

    rng = random.Random(1254)
    for size in range(1, 41):
        truth = [
            {"handle": str(i), "value_mm": 1000 + i, "axes": [str(i), str(i + 1)]}
            for i in range(size)
        ]
        values = [prediction(t["value_mm"], t["axes"]) for t in truth]
        rng.shuffle(values)
        rows = score_dimensions(values + values, truth)
        assert (rows["correct"], rows["wrong"], rows["missed"]) == (size, size, 0)
        assert rows["recall"] == 1.0 and rows["precision"] == 0.5
        # Exactly on the integer-mm rounding threshold is not a correct value.
        rows = score_dimensions(
            [prediction(t["value_mm"] + 0.5, t["axes"]) for t in truth], truth
        )
        assert rows["correct"] == 0 and rows["wrong"] == size


def test_duplicate_oracle_handle_is_error():
    with pytest.raises(ValueError, match="duplicate"):
        score_dimensions([], [{"handle": "A"}, {"handle": "A"}])
