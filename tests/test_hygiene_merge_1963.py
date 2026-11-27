"""#1963 hygiene batch 6d: one POLY63 stage-2 command and the four a07 MAF test merges.

Pattern: n/a | new-case: regression of the #1963 merges (owner present, duplicate gone, callers switched).
"""
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
OWNER = ROOT / "tools" / "windows" / "stage2.py"
OLD_63C = "jobs/POLY63-C/hooks/stage2_63c.py"


def _owner():
    spec = importlib.util.spec_from_file_location("stage2_command_1963", OWNER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_63c_hook_merged_into_the_one_command():
    assert OWNER.is_file() and not (ROOT / OLD_63C).exists()
    skeleton = json.loads((ROOT / "jobs/POLY63-C/skeleton.json").read_text(encoding="utf-8"))
    assert [h["script"] for h in skeleton["hooks"] if "stage2_63c" in h["script"]] == []
    for test in ("test_poly63_stage2_match_1714.py", "test_poly63c_registry_1619.py"):
        text = (ROOT / "tests" / test).read_text(encoding="utf-8")
        assert "stage2_63c" not in text and "tools\" / \"windows\" / \"stage2.py" in text.replace("'", '"')


@pytest.mark.parametrize("tower, module", [("63A", "stage2_plan"), ("63B", "stage2_63b")])
def test_command_routes_63a_and_63b_to_their_kept_tower_modules(monkeypatch, tower, module):
    """63A and 63B keep their job modules (disputed paths, keep wins); the command hands them the rest of argv."""
    s2 = _owner()
    seen = []
    mod = s2.tower_module(tower)
    assert mod.__name__ == module
    monkeypatch.setattr(mod, "main", lambda argv=None: seen.append(argv) or 0)
    assert s2.main([tower, "dump.npz", "crop.npz", "out.json", "--band", "1", "2"]) == 0
    assert seen == [["dump.npz", "crop.npz", "out.json", "--band", "1", "2"]]


def test_command_refuses_an_unknown_tower():
    with pytest.raises(SystemExit) as exc:
        _owner().main(["63D", "dump.npz"])
    assert "'63D'" in str(exc.value)


def test_63c_route_has_no_own_matcher_or_writer_copy():
    """The command calls the 63A claim_openings owner and keeps one 63C plan writer."""
    text = OWNER.read_text(encoding="utf-8")
    assert "a.claim_openings(" in text and "def claim_openings" not in text and "def match_openings" not in text
    assert text.count("def write_plan") == 1


MERGED = {
    "test_maf_atlas_guards.py": {"test_maf_atlas_ids.py": "test_ids_seed_named_like_the_old_temp_of_the_output_survives",
                                 "test_maf_atlas_layout.py": "test_layout_cli_fresh_process_distinct_paths_control"},
    "test_maf_ids_v005_approved.py": {"test_maf_ids_v007.py": "test_v005_is_approved_v1_with_flat_terrazzo_and_review_flags"},
    "test_maf_ids_v006.py": {"test_maf_ids_v007.py": "test_v006_is_v005_plus_id_32_and_reproducible"},
    "test_maf_project_practice.py": {"test_maf_requirement_sheet.py": "test_maf_project_practice_links"},
}


@pytest.mark.parametrize("old", sorted(MERGED))
def test_a07_maf_test_merged_into_its_owner(old):
    assert not (ROOT / "tests" / old).exists()
    for owner, name in MERGED[old].items():
        assert f"def {name}(" in (ROOT / "tests" / owner).read_text(encoding="utf-8"), (owner, name)
