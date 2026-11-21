"""new-case: KPP1 provisional roof approval provenance, not delivery acceptance.

The rerun-1209 receipts keep their historical 'provisional' marking [D249]; for revision R1 the values are final
[D254] - later KPP1 runs drop the marking (tracked on #1244 / the next KPP1 card).
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_roof_parameters_carry_provisional_user_approval():
    spec = importlib.util.spec_from_file_location(
        "kpp1_build_parts", ROOT / "jobs/KPP1/rerun-1209/build_parts.py"
    )
    assert spec is not None and spec.loader is not None and spec.origin is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.PARAPET_T_M == 0.35
    assert module.ROOF_BASE_M == 7.700
    assert module.LEVELS[2] == 7.909
    assert module.ROOF_PROVISIONAL_NOTE == (
        "provisional, not confirmed by drawings/architect [D249]"
    )
    assert '"roof_provisional_note": ROOF_PROVISIONAL_NOTE' in Path(spec.origin).read_text(encoding="utf-8")


def test_provisional_roof_approval_is_recorded_without_closing_architect_question():
    decisions = (ROOT / "docs/decisions.md").read_text(encoding="utf-8")
    row = next((r for r in decisions.splitlines() if r.startswith("| D249 |")), "")
    assert "0.35" in row and "7.700" in row and "7.909" in row
    assert "provisional, not confirmed by drawings/architect" in row
    report = (ROOT / "jobs/KPP1/rerun-1209/RUN-LOG.md").read_text(encoding="utf-8")
    assert "provisional, not confirmed by drawings/architect [D249]" in report
    questions = (ROOT / "jobs/KPP1/questions.md").read_text(encoding="utf-8")
    assert "**Q-R1-LEVELS** (open)" in questions
    assert "[D249]" in questions
