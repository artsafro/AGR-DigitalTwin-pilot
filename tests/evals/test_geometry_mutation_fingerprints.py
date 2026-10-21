"""new-case: self-source fingerprint controls for the seeded geometry mutation evaluator.

The evaluator must bind its own repository-relative source file into the input
fingerprint receipt, so a persistent edit to the evaluator itself during a run is
rejected by the existing before/after check. These controls exercise only private
tmp ROOT copies of the declared inputs; no live repository input is ever modified.
Source-byte hashing is not a runtime/environment/transitive-import attestation and
does not catch a change restored between snapshots.
"""
import hashlib
import importlib.util
from pathlib import Path

import pytest


SELF = "tools/evals_geometry_mutation.py"

# Committed baseline: the measurement outputs must not move when only the input
# hash receipt field is expanded. Source: docs/evals/geometry_mutation_2026-10-21.md
CORPUS_SHA256 = "ccf5f56dbce411b1757f4002ae9adf6c3affdaf68e1e3300013847c5306e4fae"

# The exact prior entries the source binding must preserve (order-independent).
PRIOR_INPUTS = (
    "tests/fixtures/spec-b01-v0.3.json",
    "benchmark/bench-b01-box/tolerances.json",
    "standards/material_id_ranges.yaml",
    "src/twinqa/geometry/checks.py",
    "src/twinqa/geometry/mesh.py",
    "src/twinqa/geometry/topology.py",
    "src/twinqa/geometry/complexity.py",
    "src/twinqa/clearance.py",
    "src/twinqa/uv.py",
)


def evaluator():
    path = Path(__file__).resolve().parents[2] / SELF
    assert path.is_file(), "geometry mutation evaluator must exist"
    spec = importlib.util.spec_from_file_location("geometry_mutation_fingerprints", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _copy_inputs(ev, root):
    """Copy every declared input (including the evaluator itself) under root/."""
    for p in ev.INPUTS:
        dst = root / p
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes((ev.ROOT / p).read_bytes())


def test_input_hashes_includes_self_source():
    ev = evaluator()
    assert SELF in ev.INPUTS
    for p in PRIOR_INPUTS:
        assert p in ev.INPUTS, f"prior input dropped: {p}"
    hashes = ev.input_hashes()
    assert SELF in hashes
    assert hashes[SELF] == hashlib.sha256((ev.ROOT / SELF).read_bytes()).hexdigest()
    for p in ev.INPUTS:
        assert p in hashes
        assert hashes[p] == hashlib.sha256((ev.ROOT / p).read_bytes()).hexdigest()


def test_isolated_tmp_root_reproduces_mapping(tmp_path, monkeypatch):
    ev = evaluator()
    original = ev.input_hashes()
    _copy_inputs(ev, tmp_path)
    monkeypatch.setattr(ev, "ROOT", tmp_path)
    assert ev.input_hashes() == original


def test_self_source_comment_change_only_affects_self(tmp_path, monkeypatch):
    ev = evaluator()
    _copy_inputs(ev, tmp_path)
    monkeypatch.setattr(ev, "ROOT", tmp_path)
    original = ev.input_hashes()
    src = tmp_path / SELF
    before = src.read_bytes()
    # Change only a comment line; semantics untouched.
    src.write_bytes(before + b"\n# probe: self-source fingerprint edit\n")
    after = ev.input_hashes()
    assert after[SELF] != original[SELF]
    assert after[SELF] == hashlib.sha256(src.read_bytes()).hexdigest()
    for p in ev.INPUTS:
        if p != SELF:
            assert after[p] == original[p], f"untouched input moved: {p}"
    # Restore the exact bytes -> the original mapping returns exactly.
    src.write_bytes(before)
    assert ev.input_hashes() == original


def test_missing_self_source_errors(tmp_path, monkeypatch):
    ev = evaluator()
    _copy_inputs(ev, tmp_path)
    (tmp_path / SELF).unlink()
    monkeypatch.setattr(ev, "ROOT", tmp_path)
    with pytest.raises(FileNotFoundError):
        ev.input_hashes()


def test_self_source_change_during_evaluate_rejected(tmp_path, monkeypatch):
    ev = evaluator()
    live_src = ev.ROOT / SELF
    live_before = live_src.read_bytes()
    _copy_inputs(ev, tmp_path)
    monkeypatch.setattr(ev, "ROOT", tmp_path)
    real = ev.run_checker
    target = tmp_path / SELF
    tampered = False

    def tamper(name, scene):
        nonlocal tampered
        if not tampered:
            # Persistent edit to the evaluator's own copy, injected at an ordinary
            # checker callback (a real checker still runs and returns its verdict).
            with target.open("ab") as f:
                f.write(b"\n# tampered during evaluation\n")
            tampered = True
        return real(name, scene)

    monkeypatch.setattr(ev, "run_checker", tamper)
    with pytest.raises(ValueError, match="inputs changed"):
        ev.evaluate()
    # Only the private tmp copy changed; the live repository source is untouched.
    assert target.read_bytes() != live_before
    assert live_src.read_bytes() == live_before


def test_source_binding_only_expands_receipt_field():
    ev = evaluator()
    report = ev.evaluate()
    assert "input_sha256" in report
    assert SELF in report["input_sha256"]
    # Stripping only the expanded receipt field leaves the measurement identical
    # to the committed baseline: same corpus hash, detection rows and counts.
    stripped = {k: v for k, v in report.items() if k != "input_sha256"}
    assert stripped["corpus_sha256"] == CORPUS_SHA256
    assert stripped["summary"] == {"caught": 7, "total": 8}
    assert stripped["false_positives"] == 0
    assert len(stripped["defects"]) == 8
    assert [row["defect"] for row in stripped["defects"]] == sorted(ev.CASES)
