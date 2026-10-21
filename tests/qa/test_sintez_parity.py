"""new-case: synthetic SINTEZ shared-check parity contract (#432)."""
import pytest


def test_inventory_coverage():
    from sintez_parity import fixtures, inventory

    groups = inventory()
    assert len(groups) == 14
    assert {g["status"] for g in groups.values()} == {"same", "stricter"}
    cases = fixtures()
    assert len(cases) == 28
    assert {c["group"] for c in cases} == set(groups)
    for group in groups:
        assert {c["variant"] for c in cases if c["group"] == group} == {"pass", "fail"}
        assert all(c["synthetic"] is True for c in cases if c["group"] == group)
