"""Offline specification contract for the executor-arm controls.

`evaluate_control` is a pure model of the rule in
`docs/research/harness2-vs-board.md` (positive control on a newly generated
marker file, negative control on an echoed marker, fail closed). It does not
load a profile, resolve a harness path, or launch an executor.

Synthetic marker names and contents below are fixtures, not object data.
"""
from __future__ import annotations

from pathlib import Path
import re

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = ROOT / "docs" / "research" / "harness2-vs-board.md"

MARKER_NAME = "arm/marker.txt"
MARKER_CONTENT = "predeclared-marker-v1"
SCOPED_ISOLATION = (
    "Isolation of transcripts is scoped to competing arms: "
    "no other transcript crosses between them."
)
OLD_TRANSCRIPT_PASS = "marker anywhere in transcript"


def evaluate_control(initial_files: set, final_files: dict, transcript: str,
                     marker_name, marker_content):
    """Pass only for a marker that was absent and is now the exact content.

    Transcript text, including an echo of the marker, never decides the result.
    Returns ``"pass"`` or ``"rejected"``.
    """
    if marker_name is None or marker_name == "":
        raise ValueError("marker_name is required")
    # Echoed or missing transcripts are not evidence. The length is discarded.
    _ = len(transcript) if isinstance(transcript, str) else 0
    if marker_name in initial_files:
        return "rejected"
    if marker_name not in final_files:
        return "rejected"
    found = final_files[marker_name]
    if found == "" or found != marker_content:
        return "rejected"
    return "pass"


def _doc() -> str:
    return DOC_PATH.read_text(encoding="utf-8")


def invocation_frozen(text: str) -> bool:
    """Supported launches today, and no harness-path argument on them."""
    required = (
        "hermes -p <profile> chat -q",
        "cursor-run.ps1",
        "harness-loading argument",
        "not available today",
        "must be established before scheduling",
    )
    return all(part in text for part in required)


def isolation_scoped(text: str) -> bool:
    """``no other transcript`` is limited to competing arms.

    The only carryover the text names is candidate 3 step-1 evidence.
    """
    phrase = "no other transcript"
    if text.count(phrase) != 1:
        return False
    start = text.find(phrase)
    left = max(text.rfind(".", 0, start), text.rfind("\n", 0, start))
    right = text.find(".", start)
    if right < 0:
        return False
    sentence = text[left + 1:right]
    if "competing arm" not in sentence.lower():
        return False
    if not re.search(r"candidate 3(?:'s)? step-1 evidence", text):
        return False
    carry_lines = [line for line in text.splitlines() if "carryover" in line.lower()]
    if not carry_lines:
        return False
    evidence = re.compile(r"step-1 evidence|predeclared named evidence file", re.I)
    extra = re.compile(r"step-1 evidence\b.+\band\b", re.I)
    for line in carry_lines:
        if not evidence.search(line):
            return False
        if extra.search(line):
            return False
    return True


def controls_wording(text: str) -> bool:
    """Positive control, negative control, and fail-closed; no transcript pass."""
    folded = text.lower()
    if OLD_TRANSCRIPT_PASS in folded:
        return False
    if "positive control" not in folded or "negative control" not in folded:
        return False
    return "fail closed" in folded or "fail-closed" in folded


def test_ignored_instruction_is_rejected():
    """Marker text only in the transcript, with no new artifact, is rejected."""
    transcript = f"The harness copy quotes {MARKER_CONTENT} and does not write it."
    assert evaluate_control(set(), {}, transcript, MARKER_NAME, MARKER_CONTENT) == "rejected"
    assert evaluate_control({"notes.txt"}, {"notes.txt": "unchanged"}, transcript,
                            MARKER_NAME, MARKER_CONTENT) == "rejected"


@pytest.mark.parametrize("transcript", [
    "",
    f"echo {MARKER_CONTENT}",
    "the executor refused the instruction",
])
def test_generated_marker_is_accepted(transcript):
    final = {"notes.txt": "unchanged", MARKER_NAME: MARKER_CONTENT}
    assert evaluate_control({"notes.txt"}, final, transcript,
                            MARKER_NAME, MARKER_CONTENT) == "pass"


@pytest.mark.parametrize("final", [
    {},
    {MARKER_NAME: ""},
    {MARKER_NAME: MARKER_CONTENT[:4]},
    {"arm/other.txt": MARKER_CONTENT},
    {MARKER_NAME: MARKER_CONTENT + "-mutated"},
], ids=["missing", "empty", "partial", "wrong_name", "wrong_content"])
def test_absent_or_partial_output_is_rejected(final):
    transcript = f"claimed {MARKER_CONTENT}"
    assert evaluate_control(set(), final, transcript, MARKER_NAME, MARKER_CONTENT) == "rejected"


def test_marker_copied_from_initial_state_is_rejected():
    final = {MARKER_NAME: MARKER_CONTENT}
    assert evaluate_control({MARKER_NAME}, final, "", MARKER_NAME, MARKER_CONTENT) == "rejected"
    assert evaluate_control({MARKER_NAME}, final, MARKER_CONTENT,
                            MARKER_NAME, MARKER_CONTENT) == "rejected"


def test_doc_names_frozen_invocations_without_a_harness_argument():
    text = _doc()
    assert invocation_frozen(text)


def test_isolation_is_scoped_to_competing_arms_with_one_carryover():
    text = _doc()
    assert SCOPED_ISOLATION in text
    assert isolation_scoped(text)
    unscoped = text.replace(
        SCOPED_ISOLATION,
        "no other transcript is an input to every arm.",
    )
    assert not isolation_scoped(unscoped)


def test_control_wording_rejects_a_transcript_anywhere_pass():
    text = _doc()
    assert controls_wording(text)
    mutated = text.replace(
        "Text in the prompt",
        f"{OLD_TRANSCRIPT_PASS} counts as a hit. Text in the prompt",
        1,
    )
    assert OLD_TRANSCRIPT_PASS in mutated
    assert not controls_wording(mutated)


@pytest.mark.parametrize("marker_name", [None, ""])
def test_empty_marker_name_raises(marker_name):
    with pytest.raises(ValueError):
        evaluate_control(set(), {MARKER_NAME: MARKER_CONTENT}, "", marker_name, MARKER_CONTENT)


_FINAL_KINDS = ("missing", "empty", "partial", "exact", "wrong", "wrong_name")
_TRANSCRIPTS = ("", f"echo {MARKER_CONTENT}", "unrelated note")


def _probe_final(kind: str) -> dict:
    if kind == "missing":
        return {}
    if kind == "empty":
        return {MARKER_NAME: ""}
    if kind == "partial":
        return {MARKER_NAME: MARKER_CONTENT[:4]}
    if kind == "exact":
        return {MARKER_NAME: MARKER_CONTENT}
    if kind == "wrong":
        return {MARKER_NAME: "other-bytes"}
    if kind == "wrong_name":
        return {"arm/not-the-marker.txt": MARKER_CONTENT}
    raise AssertionError(kind)


@pytest.mark.parametrize("present", [False, True])
@pytest.mark.parametrize("kind", _FINAL_KINDS)
@pytest.mark.parametrize("transcript", _TRANSCRIPTS)
def test_generated_output_invariant_probe(present, kind, transcript):
    """Exhaustive synthetic probe: pass iff absent initially and exact finally.

    Bounds: initial membership {absent, present} x final
    {missing, empty, partial, exact, wrong, wrong_name} x transcript
    {empty, echo, unrelated} = 36. Transcript never flips the result.
    """
    initial = {MARKER_NAME} if present else set()
    result = evaluate_control(initial, _probe_final(kind), transcript,
                              MARKER_NAME, MARKER_CONTENT)
    expect = "pass" if (not present and kind == "exact") else "rejected"
    assert result == expect
