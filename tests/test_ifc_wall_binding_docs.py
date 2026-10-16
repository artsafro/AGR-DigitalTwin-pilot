"""Documentation contract regression tests for experimental geometric wall binding (Issue #137).

Verifies that both the module docstring of wall_binding.py and its accompanying
README.md explicitly document provenance, classification, synthetic limitations,
and delivery gates per hypothesis #107.
"""

from __future__ import annotations

import ast
from pathlib import Path
import re

import pytest

ROOT = Path(__file__).resolve().parents[1]

TARGET_FILES = [
    "experiments/revit-ifc-offline-intake/wall_binding.py",
    "experiments/revit-ifc-offline-intake/README.md",
]

HYPOTHESIS_107_URL = "https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/107"


@pytest.mark.parametrize("relative_path", TARGET_FILES)
def test_ifc_wall_binding_documentation_contract(relative_path: str) -> None:
    """Ensure IFC wall binding docs adhere to Issue #137 and hypothesis #107 contract."""
    target_path = ROOT / relative_path
    assert target_path.is_file(), f"Target file does not exist: {target_path}"

    if target_path.suffix == ".py":
        content = target_path.read_text(encoding="utf-8")
        text = ast.get_docstring(ast.parse(content))
        assert text is not None, f"Module docstring missing in {relative_path}"
    else:
        text = target_path.read_text(encoding="utf-8")

    # 1. Classified as new-case
    assert "new-case" in text, (
        f"{relative_path} must explicitly contain 'new-case'"
    )

    # 2. Provenance link to hypothesis #107
    assert HYPOTHESIS_107_URL in text, (
        f"{relative_path} must link to hypothesis #107 issue: {HYPOTHESIS_107_URL}"
    )

    # 3. Report reference to docs/experiments/hyp-107.md (substring hyp-107.md allowed in README)
    if target_path.suffix == ".py":
        assert "docs/experiments/hyp-107.md" in text, (
            f"{relative_path} docstring must reference report 'docs/experiments/hyp-107.md'"
        )
    else:
        assert "hyp-107.md" in text, (
            f"{relative_path} must reference report 'hyp-107.md'"
        )

    # 4. Explicitly scoped as synthetic
    assert re.search(r"\bsynthetic\b", text, re.IGNORECASE), (
        f"{relative_path} must explicitly state 'synthetic'"
    )

    # 5. One wall per edge contract wording preserved
    assert re.search(r"\bone[\s\-]wall[\s\-]per[\s\-]edge\b", text, re.IGNORECASE), (
        f"{relative_path} must preserve 'one wall per edge' wording"
    )

    # 6. Strict mode is default
    assert re.search(r"\bstrict\b[^\n.]*\bdefault\b|\bdefault\b[^\n.]*\bstrict\b", text, re.IGNORECASE), (
        f"{relative_path} must state strict default contract"
    )

    # 7. Explicit opt-in for geometric mode
    assert re.search(r"\bopt[\s\-]in\b", text, re.IGNORECASE), (
        f"{relative_path} must state opt-in requirement"
    )

    # 8. Delivery gate marker delivery_passed=false
    assert "delivery_passed=false" in text, (
        f"{relative_path} must contain 'delivery_passed=false'"
    )

    # 9. Explicit disclaimer: not a proven generic IFC pattern
    assert re.search(r"not\s+(?:a\s+)?proven\s+generic\s+ifc\s+pattern", text, re.IGNORECASE), (
        f"{relative_path} must explicitly state it is 'not a proven generic IFC pattern'"
    )
