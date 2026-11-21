"""new-case: repository-wide job STATE start-here header contract (#1208)."""

from itertools import permutations
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LABELS = ("Current run:", "Source:", "Next gate:")
STATE_FILES = sorted((ROOT / "jobs").glob("*/STATE.md"))


def assert_header(text: str) -> None:
    lines = text.splitlines()
    assert len(lines) >= 3, "Missing three-line STATE header"
    for label, line in zip(LABELS, lines[:3], strict=True):
        assert line.startswith(label), f"Expected {label!r}, got {line!r}"
        value = line[len(label):].strip()
        assert value, f"Empty {label}"
        if value.lower().startswith("unknown"):
            assert value.startswith("unknown — ") and value[10:].strip(), (
                f"{label} needs unknown — <why>"
            )


@pytest.mark.parametrize("path", STATE_FILES, ids=lambda path: path.parent.name)
def test_job_state_starts_with_header(path):
    assert_header(path.read_text(encoding="utf-8"))


def test_job_state_inventory_is_not_empty():
    assert STATE_FILES, "No jobs/*/STATE.md found; check repository root"


def test_job_contract_documents_header():
    workflow = (ROOT / "docs/agents/WORKFLOW.md").read_text(encoding="utf-8")
    contract = workflow.split("## Job contract (#130)", 1)[1].split("\n## ", 1)[0]
    template = contract.split("```markdown\n", 1)[1].split("```", 1)[0]
    assert_header(template)
    assert "unknown — <why>" in contract
    assert "every" in contract.lower()


def test_kpp1_header_routes_to_current_r1_placement_without_claiming_acceptance():
    import yaml

    lines = (ROOT / "jobs/KPP1/STATE.md").read_text(encoding="utf-8").splitlines()
    job = yaml.safe_load((ROOT / "jobs/KPP1/job.yaml").read_text(encoding="utf-8"))
    assert f"`{job['run_id']}`" in lines[0]
    assert "site-1255/REPORT.md" in lines[0] and "passed=false" in lines[0]
    assert "sources.json" in lines[1] and "object.json" in lines[1]
    assert "R1 dimensions final D254" in lines[1]
    assert "job.yaml" in lines[2]
    assert "visual waits-user, checker waits-visual" in lines[2]


VALID = "Current run: x\nSource: y\nNext gate: z\n"


def test_header_accepts_minimum_values():
    assert_header(VALID)
    assert_header(VALID.replace("\n", "\r\n") + "\r\n# History\r\n")


@pytest.mark.parametrize("size", range(3))
def test_header_rejects_empty_or_partial(size):
    with pytest.raises(AssertionError, match="Missing three-line"):
        assert_header("\n".join(VALID.splitlines()[:size]))


@pytest.mark.parametrize("field", range(3))
@pytest.mark.parametrize("blank", ["", " ", "\t", "\u2003"])
def test_header_rejects_blank_values(field, blank):
    lines = VALID.splitlines()
    lines[field] = LABELS[field] + blank
    with pytest.raises(AssertionError, match=f"Empty {LABELS[field]}"):
        assert_header("\n".join(lines))


def test_header_rejects_wrong_order_or_position():
    for order in permutations(VALID.splitlines()):
        if list(order) != VALID.splitlines():
            with pytest.raises(AssertionError, match="Expected"):
                assert_header("\n".join(order))
    for prefix in ["\n", "# History\n", "Current run: duplicate\n"]:
        with pytest.raises(AssertionError, match="Expected"):
            assert_header(prefix + VALID)
    for field in range(3):
        lines = VALID.splitlines()
        lines[field] = "Unsupported: x"
        with pytest.raises(AssertionError, match="Expected"):
            assert_header("\n".join(lines))


@pytest.mark.parametrize("field", range(3))
def test_header_requires_unknown_reason(field):
    for value in ["unknown", "unknown —", "unknown — \t", "unknown - guessed", "UNKNOWN"]:
        lines = VALID.splitlines()
        lines[field] = LABELS[field] + " " + value
        with pytest.raises(AssertionError, match="needs unknown"):
            assert_header("\n".join(lines))
    lines[field] = LABELS[field] + " unknown — no gate recorded"
    assert_header("\n".join(lines))


def test_header_has_no_cached_success():
    assert_header(VALID)
    for _ in range(2):
        with pytest.raises(AssertionError):
            assert_header(VALID.replace("Source: y", "Source:"))
    assert_header(VALID)
