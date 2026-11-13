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
    assert "No fresh model/image inference" not in text


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


def _check_batch2(data):
    """#1303 batch-2 receipt invariants: caps, new albums only, ledger = snapshot deltas."""
    b = data["batch2"]
    albums = b["albums"]
    assert 1 <= len(albums) <= data["batch_policy"]["max_albums"] == 2
    assert sum(a["pages"] for a in albums) <= data["batch_policy"]["max_pages"] == 40
    first = {a["sha256"] for a in data["albums"]}
    hashes = [a["sha256"] for a in albums]
    assert len(set(hashes)) == len(hashes) and not first & set(hashes)
    assert len({a["id"] for a in albums}) == len(albums)
    snaps = b["usage_snapshots"]
    assert len(snaps) == len(albums) + 1
    for key in ("new_tokens", "cached_tokens"):
        vals = [s[key] for s in snaps]
        assert all(isinstance(v, int) and not isinstance(v, bool) and v >= 0 for v in vals)
        assert vals == sorted(vals)
    for i, a in enumerate(albums):
        assert len(a["sha256"]) == 64 and a["source_unchanged"] is True
        assert len(a["page_text_bytes"]) == a["pages"] >= 1
        assert a["local_model_new_tokens"] == a["local_model_cached_tokens"] == 0
        assert a["window_new_tokens"] == snaps[i + 1]["new_tokens"] - snaps[i]["new_tokens"]
        assert a["window_cached_tokens"] == snaps[i + 1]["cached_tokens"] - snaps[i]["cached_tokens"]
        assert math.isfinite(a["extraction_seconds"]) and a["extraction_seconds"] >= 0
    total = sum(a["window_new_tokens"] for a in albums)
    assert b["new_token_cap"] == 100000 and b["reserve_tokens"] == 30000
    assert total <= b["new_token_cap"]
    assert b["currency_cost"] is None
    assert len(b["evidence_manifest_sha256"]) == 64


def test_ntr_batch2_receipt_and_report():
    data = json.loads(RECEIPT.read_text(encoding="utf-8"))
    _check_batch2(data)
    text = REPORT.read_text(encoding="utf-8")
    section = text.split("## Batch 2 (#1303)", 1)[1]
    for required in ["B01 p1", "B02 p1", "Go/no-go", "NO-GO", "unknown", "11,993", "3,694",
                     "Alutech ALT F50", "RAL 7021", "щучка дернистая", "[D267]", "1303-ntr-pdf-batch2"]:
        assert required in section, required


@pytest.mark.parametrize("case", ["empty", "three_albums", "too_many_pages", "first10_hash", "duplicate",
                                  "nan", "inf", "string", "over_cap", "non_monotonic", "ledger_mismatch",
                                  "changed_source", "zero_pages"])
def test_ntr_batch2_mutations_fail_closed(case):
    data = json.loads(RECEIPT.read_text(encoding="utf-8"))
    b = data["batch2"]
    a0 = b["albums"][0]
    if case == "empty":
        data = {}
    elif case == "three_albums":
        b["albums"].append(dict(a0, id="B03", sha256="f" * 64))
        b["usage_snapshots"].append(dict(b["usage_snapshots"][-1]))
    elif case == "too_many_pages":
        a0["pages"] = 40
        a0["page_text_bytes"] = [1] * 40
    elif case == "first10_hash":
        a0["sha256"] = data["albums"][0]["sha256"]
    elif case == "duplicate":
        b["albums"][1] = dict(a0)
    elif case in ("nan", "inf"):
        b["usage_snapshots"][1]["new_tokens"] = float(case)
    elif case == "string":
        b["usage_snapshots"][1]["new_tokens"] = "unknown"
    elif case == "over_cap":
        b["usage_snapshots"][1]["new_tokens"] = b["usage_snapshots"][0]["new_tokens"] + 100001
        b["usage_snapshots"][2]["new_tokens"] = b["usage_snapshots"][1]["new_tokens"]
        a0["window_new_tokens"] = 100001
        b["albums"][1]["window_new_tokens"] = 0
    elif case == "non_monotonic":
        b["usage_snapshots"][2]["cached_tokens"] = 0
    elif case == "ledger_mismatch":
        a0["window_new_tokens"] += 1
    elif case == "changed_source":
        a0["source_unchanged"] = False
    elif case == "zero_pages":
        a0["pages"] = 0
        a0["page_text_bytes"] = []
    with pytest.raises((AssertionError, KeyError, TypeError)):
        _check_batch2(data)


def test_ntr_batch2_cap_exactly_at_threshold_passes():
    data = json.loads(RECEIPT.read_text(encoding="utf-8"))
    b = data["batch2"]
    s = b["usage_snapshots"]
    s[1]["new_tokens"] = s[0]["new_tokens"] + 100000
    s[2]["new_tokens"] = s[1]["new_tokens"]
    b["albums"][0]["window_new_tokens"] = 100000
    b["albums"][1]["window_new_tokens"] = 0
    _check_batch2(data)
