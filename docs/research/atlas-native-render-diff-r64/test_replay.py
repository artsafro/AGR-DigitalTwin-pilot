from replay import grade, graft


def rounds(trigger=0.004, small=0.001):
    def label(base, je, shift_je):
        return {state: {"JE": j, "paired_rgb": {"mean": value, "views": {"west": {"pixels": 12}}}}
                for state, value, j in (("clean", base, je), ("small", base + small, je),
                                        ("trigger", base + trigger, shift_je))}
    return [{"v007": label(0.002, 202, 320), "v010": label(0.007, 0, 320)} for _ in range(3)]


def test_response_is_not_clean_label_calibration():
    result = grade(rounds())
    assert result["hypothesis"] == "confirmed"
    assert result["clean_label_order"] == "refuted"
    assert result["paired_spread"] == 0


def test_bounds_and_invalid_evidence_are_distinct():
    assert grade(rounds(trigger=0.001))["hypothesis"] == "refuted"
    assert grade(rounds(small=-0.003))["hypothesis"] == "refuted"
    rows = rounds()
    rows[1]["v010"]["trigger"]["JE"] = 0
    assert grade(rows)["hypothesis"] == "inconclusive"
    rows = rounds()
    rows[1]["v007"]["small"]["paired_rgb"]["views"]["west"]["pixels"] -= 1
    assert grade(rows)["hypothesis"] == "inconclusive"
    assert grade(rows[:2])["hypothesis"] == "inconclusive"


def test_nonfinite_and_unstable_series_are_inconclusive():
    rows = rounds()
    rows[1]["v007"]["trigger"]["paired_rgb"]["mean"] += 0.002
    rows[1]["v010"]["trigger"]["paired_rgb"]["mean"] += 0.002
    assert grade(rows)["hypothesis"] == "inconclusive"
    assert grade(rounds(trigger=float("nan")))["hypothesis"] == "inconclusive"


def test_driver_anchor_fails_closed():
    for source in (b"", b"xx"):
        try:
            graft(source, b"x", b"y")
        except ValueError:
            continue
        raise AssertionError("missing or duplicate anchor accepted")
    assert graft(b"axb", b"x", b"y") == b"ayb"
