"""pytest plugin: inject an OBSERVE candidate into the in-process duplicate_guard module (t_e730ebd2).

Usage: PYTHONPATH=docs/research/autoresearch-repo-guards-harness AR_DG_CANDIDATE=r1_walk_memo
       uv run pytest -p ar_dg_inject tests/test_architecture_map_1359.py tests/test_duplicate_status_1424.py
Fresh-process CLI tests spawn an unpatched interpreter; bench.py covers CLI parity in-process.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/architecture"))
import duplicate_guard  # noqa: E402
import candidates  # noqa: E402

NAMES = [n for n in os.environ.get("AR_DG_CANDIDATE", "").split(",") if n]
candidates.apply(duplicate_guard, NAMES)


def pytest_report_header(config):
    return f"ar_dg_inject: candidate {NAMES or 'none'} applied to {duplicate_guard.__file__}"
