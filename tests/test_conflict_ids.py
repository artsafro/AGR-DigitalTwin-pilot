"""Checks docs/domain/conflicts.md conflict IDs are unique, issue #219."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFLICTS = ROOT / "docs/domain/conflicts.md"
AREAS = ROOT / "docs/domain/areas"
ENTRY = re.compile(r"^(\d+)\. ", re.MULTILINE)


def conflict_ids(text: str) -> list[int]:
    return [int(number) for number in ENTRY.findall(text)]


def duplicate_conflict_ids(text: str) -> list[int]:
    ids = conflict_ids(text)
    return sorted({number for number in ids if ids.count(number) > 1})


def _entry_lines(text: str) -> list[str]:
    return [line for line in text.splitlines() if ENTRY.match(line)]


def test_conflict_ids_are_unique():
    text = CONFLICTS.read_text(encoding="utf-8")
    duplicates = duplicate_conflict_ids(text)
    assert duplicates == [], f"duplicate conflict ids: {duplicates}"
    assert conflict_ids(text)


def test_window_frames_and_maf_entries_have_distinct_ids():
    lines = CONFLICTS.read_text(encoding="utf-8").splitlines()
    frames = [line for line in lines if line.startswith("35. ")]
    maf = [line for line in lines if line.startswith("38. ")]
    assert len(frames) == 1
    assert "VPM window frames" in frames[0]
    assert maf and "MAF sunk bottoms" in maf[0] and "[D096]" in maf[0]


def test_duplicate_detector_generated_probes():
    text = CONFLICTS.read_text(encoding="utf-8")
    entries = _entry_lines(text)
    for line in entries:
        number = int(ENTRY.match(line).group(1))
        mutated = text if text.endswith("\n") else text + "\n"
        assert duplicate_conflict_ids(mutated + line) == [number]
    for first, second in zip(entries, entries[1:]):
        number = int(ENTRY.match(first).group(1))
        renumbered = ENTRY.sub(f"{number}. ", second, count=1)
        assert duplicate_conflict_ids(text.replace(second, renumbered, 1)) == [number]
    assert duplicate_conflict_ids("") == []
    assert duplicate_conflict_ids("1. alpha\n2. beta\n3. gamma\n") == []
    assert conflict_ids("see 35. above") == []
    assert conflict_ids("  35. indented") == []


def test_every_c_reference_in_area_sheets_exists():
    known = set(conflict_ids(CONFLICTS.read_text(encoding="utf-8")))
    missing = []
    for path in sorted(AREAS.glob("*.md")):
        for number in re.findall(r"\bC(\d+)\b", path.read_text(encoding="utf-8")):
            if int(number) not in known:
                missing.append(f"{path.name}: C{number}")
    assert missing == [], missing
