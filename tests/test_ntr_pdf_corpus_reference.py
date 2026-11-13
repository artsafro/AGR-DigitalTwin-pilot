"""new-case: source-bound NTR research receipts, not semantic accuracy certification."""
import json
from pathlib import Path

import math
import pytest

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "docs/research/ntr-pdf-corpus-pilot.md"
RECEIPT = ROOT / "docs/research/ntr-pdf-corpus-pilot.json"


def test_ntr_pilot_complete_source_accounting():
    data = json.loads(RECEIPT.read_text(encoding="utf-8"))
    albums = data["albums"]
    assert len(albums) == 10
    assert len({a["id"] for a in albums}) == 10
    assert len({a["sha256"] for a in albums}) == 10
    assert sum(a["pages"] for a in albums) == 261
    for a in albums:
        assert len(a["sha256"]) == 64
        assert len(a["page_text_bytes"]) == a["pages"]
        assert a["source_unchanged"] is True
        assert a["local_model_new_tokens"] == a["local_model_cached_tokens"] == 0
        assert a["shared_model_new_tokens"] is None
        assert a["shared_model_cached_tokens"] is None
    assert [a["id"] for a in albums if a["zero_text_pages"] == [12, 13, 14]] == ["A08"]


def test_ntr_cost_boundaries_and_inventory():
    data = json.loads(RECEIPT.read_text(encoding="utf-8"))
    assert data["inventory"]["unique_albums"] == 645
    assert data["inventory"]["unique_pages"] == 10119
    assert data["inventory"]["ntr_pages"] == 269
    assert data["usage"]["prior"]["new_tokens"] == 139341
    for key in ["new_tokens", "cached_tokens"]:
        assert math.isfinite(data["usage"][key]) and data["usage"][key] >= 0
    assert 0 <= data["usage"]["continuation"]["new_tokens"] < 300000
    assert data["usage"]["new_tokens"] < 2000000
    assert data["usage"]["cached_tokens"] > 0
    assert data["usage"]["currency_cost"] is None
    assert data["semantic_accuracy"] == "not_independently_measured"
    assert data["batch_policy"]["new_token_cap"] == 100000
    assert data["batch_policy"]["reserve_tokens"] == 30000


def test_ntr_reference_keeps_negative_and_conflicting_results():
    text = REPORT.read_text(encoding="utf-8")
    for required in ["[D267]", "A01", "A02", "A03", "A04", "A05", "A06", "A07", "A08", "A09", "A10",
                     "NO-GO", "Conditional GO", "not measured", "Darmera", "Bergenia", "RAL 7004",
                     "#425", "window-block schedule", "10119", "9850", "shared", "cached", "17608-2017"]:
        assert required in text
    assert "all pages are semantically verified" not in text


@pytest.mark.parametrize("case", ["empty", "partial", "duplicate", "changed_hash",
                                  "unsupported", "nan", "inf", "threshold", "failing_status"])
def test_ntr_receipt_mutation_witnesses_fail_closed(case, tmp_path, monkeypatch):
    data = json.loads(RECEIPT.read_text(encoding="utf-8"))
    if case == "empty":
        data = {}
    elif case == "partial":
        data["albums"].pop()
    elif case == "duplicate":
        data["albums"][1] = data["albums"][0]
    elif case == "changed_hash":
        data["albums"][0]["sha256"] = "stale"
    elif case == "unsupported":
        data["usage"]["new_tokens"] = "unknown"
    elif case in ("nan", "inf"):
        data["usage"]["new_tokens"] = float(case)
    elif case == "threshold":
        data["usage"]["continuation"]["new_tokens"] = 300000
    elif case == "failing_status":
        data["albums"][0]["source_unchanged"] = False
    witness = tmp_path / "mutated.json"
    witness.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setitem(globals(), "RECEIPT", witness)
    with pytest.raises((AssertionError, KeyError, TypeError)):
        test_ntr_pilot_complete_source_accounting()
        test_ntr_cost_boundaries_and_inventory()
