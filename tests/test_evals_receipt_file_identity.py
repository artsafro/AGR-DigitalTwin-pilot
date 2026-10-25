"""Receipt file-identity controls; synthetic reports only (improve card t_9e39d838).

Attests counts and filesystem identity only, never all-not-measured readiness.
"""
import json
import os
from pathlib import Path

import pytest

from twinqa.evals import receipt as receipt_mod
from twinqa.evals.receipt import check_receipt

COUNTS = (3, 0, 2)


def _report(counts=COUNTS):
    return {"selector": {"suite": "regression", "task": None, "references": False},
            "passed": counts[0], "failed": counts[1], "not_measured": counts[2],
            "checks": [{"passed": v} for v, c in zip((True, False, None), counts)
                       for _ in range(c)]}


def _write(path, counts=COUNTS):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_report(counts)), encoding="utf-8")
    return path


def _line(path, counts=COUNTS):
    return (f"Regression evals: {path}; {counts[0]} passed / {counts[1]} failed / "
            f"{counts[2]} not measured (no Claude transcript)")


def _snapshot(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def _dirs(root):
    return sorted(str(p.relative_to(root)) for p in root.rglob("*"))


def _reject(root, receipt, output, fragment="report path differs"):
    files, tree = _snapshot(root), _dirs(root)
    with pytest.raises(ValueError, match=fragment):
        check_receipt(receipt, output)
    assert _snapshot(root) == files and _dirs(root) == tree


def _accept(root, receipt, output):
    files, tree = _snapshot(root), _dirs(root)
    assert check_receipt(receipt, output) is None
    assert _snapshot(root) == files and _dirs(root) == tree


def _separate_identical_copy(tmp_path):
    out = tmp_path / "output"
    original = _write(out / "report.json")
    copy = tmp_path / "copy.json"
    copy.write_bytes(original.read_bytes())
    _reject(tmp_path, _line(copy), out)


def test_receipt_naming_the_exact_report_accepted(tmp_path):
    out = tmp_path / "output"
    _write(out / "report.json")
    _accept(tmp_path, _line(out / "report.json"), out)


def test_separate_file_with_identical_bytes_rejected(tmp_path):
    _separate_identical_copy(tmp_path)


def test_different_report_with_same_counts_rejected(tmp_path):
    out = tmp_path / "output"
    _write(out / "report.json")
    other = _write(tmp_path / "other.json")
    other.write_text(json.dumps({**_report(), "branch": "different"}), encoding="utf-8")
    assert other.read_bytes() != (out / "report.json").read_bytes()
    _reject(tmp_path, _line(other), out)


def test_other_directory_with_identical_report_rejected(tmp_path):
    out = tmp_path / "output"
    _write(out / "report.json")
    other = tmp_path / "elsewhere"
    (other / "report.json").parent.mkdir()
    (other / "report.json").write_bytes((out / "report.json").read_bytes())
    _reject(tmp_path, _line(other / "report.json"), out)


def test_receipt_names_original_output_names_second_directory_rejected(tmp_path):
    original = _write(tmp_path / "original" / "output" / "report.json")
    second = tmp_path / "second"
    (second / "report.json").parent.mkdir()
    (second / "report.json").write_bytes(original.read_bytes())
    _reject(tmp_path, _line(original), second)


def test_dotdot_alias_of_same_file_accepted(tmp_path):
    out = tmp_path / "output"
    _write(out / "report.json")
    (out / "sub").mkdir()
    alias = out / "sub" / ".." / "report.json"
    assert str(alias) != str(out / "report.json")
    _accept(tmp_path, _line(alias), out)


def test_hardlink_alias_accepted_under_samefile_contract(tmp_path):
    out = tmp_path / "output"
    original = _write(out / "report.json")
    link = tmp_path / "link.json"
    try:
        os.link(original, link)
    except OSError as exc:
        pytest.skip(f"hardlink not creatable here: {exc!r}")
    _accept(tmp_path, _line(link), out)


def test_content_equality_mutant_is_killed_by_separate_file_witness(tmp_path, monkeypatch):
    # Baseline: witness passes with real samefile.
    _separate_identical_copy(tmp_path / "base")

    def by_content(self, other):
        return Path(self).read_bytes() == Path(other).read_bytes()

    mutant_root = tmp_path / "mutant"
    monkeypatch.setattr(receipt_mod.Path, "samefile", by_content)
    with pytest.raises(BaseException) as killed:
        _separate_identical_copy(mutant_root)
    assert "DID NOT RAISE" in str(killed.value)
