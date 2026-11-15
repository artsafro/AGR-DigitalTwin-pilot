"""#1421 / D311: Artem accepted the Flora catalogue v003 NPM/VPM identity for now (confirmed-interim)."""
import copy
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from dt_ai.materials import flora_catalogue as fc

ROOT = Path(__file__).resolve().parents[1]
DECISION = {"id": "D311", "date": "2026-11-15"}
STATE = ("vpm_identity", "vpm_identity_decision")


def load(name):
    return json.loads((ROOT / "library/flora" / name).read_text(encoding="utf-8"))


def inputs():
    audit = json.loads((ROOT / "experiments/flora-library-audit/catalogue.json").read_text(encoding="utf-8"))
    return audit, load("species-curation.json"), load("maps-v003-snapshot.json")


def strip(catalogue):
    return [{k: v for k, v in row.items() if k not in STATE} for row in catalogue["species"]], {
        k: v for k, v in catalogue.items() if k != "species"}


def test_committed_catalogue_is_confirmed_interim_by_d311():
    catalogue = load("catalogue.json")
    assert fc.check(catalogue) == []
    with_vpm = [row for row in catalogue["species"] if row["vpm"]]
    assert len(with_vpm) == catalogue["counts"]["with_vpm"] == 38
    for row in catalogue["species"]:
        if row["vpm"]:
            assert row["vpm_identity"] == "confirmed-interim", row["latin"]
            assert row["vpm_identity_decision"] == DECISION, row["latin"]
            # a user decision, not a geometric proof: evidence stays unverified
            assert row["vpm_evidence"] == {"relation": "unverified", "translation_dev_m": None, "scaled_dev_rel": None}
        else:
            assert row["vpm_identity"] is None and row["vpm_identity_decision"] is None, row["latin"]
    assert "confirmed" not in {row["vpm_identity"] for row in catalogue["species"]}


def test_d311_row_records_artem_decision():
    rows = re.findall(r"^\| (D\d+) \| ([0-9-]+) \| (.*)$", (ROOT / "docs/decisions.md").read_text(encoding="utf-8"), re.M)
    row = [r for r in rows if r[0] == DECISION["id"]]
    assert len(row) == 1
    assert row[0][1] == DECISION["date"]
    assert "confirmed-interim" in row[0][2] and "library/flora/catalogue.json" in row[0][2] and "#1421" in row[0][2]


def test_decision_changes_only_identity_fields_stand_in_and_maps_kept():
    """Rebuilding with D311 equals the committed catalogue; without it only the identity fields differ."""
    audit, curation, maps = inputs()
    committed = load("catalogue.json")
    assert fc.build(audit, curation, maps, committed, identity_decision=DECISION) == committed
    undecided = copy.deepcopy(committed)
    for row in undecided["species"]:
        if row["vpm"]:
            row["vpm_identity"], row["vpm_identity_decision"] = "unverified", None
    assert fc.check(undecided) == []
    plain = fc.build(audit, curation, maps, undecided)
    assert plain == undecided  # without a decision nothing is confirmed; every other field is the same
    assert strip(plain) == strip(committed)
    assert {row["vpm_identity"] for row in plain["species"] if row["vpm"]} == {"unverified"}
    assert committed["counts"]["shared_stand_in_gaps"] == len(committed["gaps"]["project_species_shared_stand_in"]) == 15


def test_previous_decision_is_carried_only_for_the_same_pair():
    audit, curation, maps = inputs()
    committed = load("catalogue.json")
    assert fc.build(audit, curation, maps, committed) == committed  # rebuild keeps D311 without the flag
    previous = copy.deepcopy(committed)
    row = next(r for r in previous["species"] if r["vpm"])
    row["vpm"]["entry_id"] = "library-999"  # the sheets showed another VPM -> not covered by D311
    rebuilt = fc.build(audit, curation, maps, previous)
    changed = next(r for r in rebuilt["species"] if r["latin"] == row["latin"])
    assert changed["vpm_identity"] == "unverified" and changed["vpm_identity_decision"] is None
    others = [r for r in rebuilt["species"] if r["vpm"] and r["latin"] != row["latin"]]
    assert len(others) == 37 and all(r["vpm_identity_decision"] == DECISION for r in others)
    assert fc.check(rebuilt) == []


BAD_ROWS = {
    "confirmed_without_decision": ("confirmed-interim", None),
    "plain_confirmed": ("confirmed", DECISION),
    "decision_on_unverified": ("unverified", DECISION),
    "empty_decision": ("confirmed-interim", {}),
    "partial_decision": ("confirmed-interim", {"id": "D311"}),
    "extra_key": ("confirmed-interim", {**DECISION, "by": "Artem"}),
    "bad_id": ("confirmed-interim", {"id": "D", "date": "2026-11-15"}),
    "lower_id": ("confirmed-interim", {"id": "d311", "date": "2026-11-15"}),
    "zero_id": ("confirmed-interim", {"id": "D0311", "date": "2026-11-15"}),
    "int_id": ("confirmed-interim", {"id": 311, "date": "2026-11-15"}),
    "bad_date": ("confirmed-interim", {"id": "D311", "date": "2026-13-40"}),
    "short_date": ("confirmed-interim", {"id": "D311", "date": "2026-11"}),
    "nan_date": ("confirmed-interim", {"id": "D311", "date": float("nan")}),
    "string_decision": ("confirmed-interim", "D311"),
    "null_identity_with_vpm": (None, None),
}


@pytest.mark.parametrize("case", sorted(BAD_ROWS))
def test_checker_fails_closed_on_vpm_rows(case):
    catalogue = load("catalogue.json")
    row = next(r for r in catalogue["species"] if r["vpm"])
    row["vpm_identity"], row["vpm_identity_decision"] = BAD_ROWS[case]
    assert any("vpm_identity" in f for f in fc.check(catalogue)), case


@pytest.mark.parametrize("state", [("confirmed-interim", DECISION), (None, DECISION), ("unverified", None)])
def test_checker_rejects_identity_without_vpm(state):
    catalogue = load("catalogue.json")
    row = next(r for r in catalogue["species"] if not r["vpm"])
    row["vpm_identity"], row["vpm_identity_decision"] = state
    assert any("vpm_identity" in f for f in fc.check(catalogue))


def test_checker_requires_the_decision_key():
    catalogue = load("catalogue.json")
    del catalogue["species"][0]["vpm_identity_decision"]
    assert "species[0] missing key vpm_identity_decision" in fc.check(catalogue)


@pytest.mark.parametrize("decision", [{}, {"id": "D311"}, {"id": "X1", "date": "2026-11-15"}, {"id": "D311", "date": ""}])
def test_build_rejects_invalid_decision(decision):
    audit, curation, maps = inputs()
    with pytest.raises(ValueError):
        fc.build(audit, curation, maps, None, identity_decision=decision)


def _cli(tmp_path, *extra):
    out = tmp_path / "catalogue.json"
    cmd = [sys.executable, "-m", "dt_ai.materials.flora_catalogue", "build",
           "--audit", str(ROOT / "experiments/flora-library-audit/catalogue.json"),
           "--curation", str(ROOT / "library/flora/species-curation.json"),
           "--maps", str(ROOT / "library/flora/maps-v003-snapshot.json"),
           "--out", str(out), *extra]
    return subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT), out


def test_cli_fresh_process_writes_the_committed_catalogue(tmp_path):
    result, out = _cli(tmp_path, "--previous", str(ROOT / "library/flora/catalogue.json"),
                       "--identity-decision", "D311:2026-11-15")
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(out.read_text(encoding="utf-8")) == load("catalogue.json")


@pytest.mark.parametrize("value", ["D311", "D311:", ":2026-11-15", "D311:2026-02-30", "X:2026-11-15"])
def test_cli_invalid_decision_exits_nonzero_and_writes_nothing(tmp_path, value):
    result, out = _cli(tmp_path, "--identity-decision", value)
    assert result.returncode == 1
    assert not out.exists()
